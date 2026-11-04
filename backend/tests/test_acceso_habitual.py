from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.seguridad import crear_token_bienvenida
from app.models.enums import EventoEstado
from app.models.eventos import Evento
from app.services.bienvenida import enviar_bienvenida_una_vez
from tests.test_administracion import auth


def google(monkeypatch, email, sub="google-estable", hd=None):
    monkeypatch.setattr("app.services.acceso.get_verified_google_profile",
                        lambda _: {"email": email, "sub": sub, "email_verified": True, "hd": hd})


def test_bienvenida_una_vez_y_validacion_persistida(contexto, monkeypatch):
    client, db, _, usuario, _ = contexto
    envios = []
    monkeypatch.setattr("app.services.bienvenida.send_welcome_email", lambda *args: envios.append(args))
    assert enviar_bienvenida_una_vez(db, usuario) is True
    assert enviar_bienvenida_una_vez(db, usuario) is False
    assert len(envios) == 1
    assert usuario.bienvenida_enviada_en is not None
    respuesta = client.post("/acceso/enlace", json={"token": envios[0][1]})
    assert respuesta.status_code == 200 and respuesta.json()["email_validado"] is True
    assert usuario.email_validado_en is not None
    assert enviar_bienvenida_una_vez(db, usuario) is False


def test_smtp_fallido_no_marca_bienvenida_como_enviada(contexto, monkeypatch):
    from fastapi import HTTPException

    _, db, _, usuario, _ = contexto
    def falla(*args):
        raise HTTPException(503, "SMTP no disponible")
    monkeypatch.setattr("app.services.bienvenida.send_welcome_email", falla)
    with pytest.raises(HTTPException):
        enviar_bienvenida_una_vez(db, usuario)
    db.rollback()
    assert usuario.bienvenida_enviada_en is None


def test_ingresos_google_repetidos_no_envian_email(contexto, monkeypatch):
    client, _db, _, usuario, _ = contexto
    google(monkeypatch, usuario.email, hd="example.com")
    def prohibido(*args):
        raise AssertionError("El ingreso habitual no debe enviar correo")
    monkeypatch.setattr("app.services.acceso.send_access_link_email", prohibido)
    monkeypatch.setattr("app.services.bienvenida.send_welcome_email", prohibido)
    for _ in range(3):
        respuesta = client.post("/acceso/google", json={"credential": "credencial-verificada"})
        assert respuesta.status_code == 200 and respuesta.json()["token"]
        assert respuesta.json()["google_vinculado"] is True
    assert usuario.google_subject == "google-estable" and usuario.email_validado_en is not None


def test_hotmail_vinculacion_inicial_y_luego_google_sin_mail(contexto, monkeypatch):
    client, db, _, usuario, _ = contexto
    usuario.email = "persona@hotmail.com"
    db.commit()
    google(monkeypatch, usuario.email)
    assert client.post("/acceso/google", json={"credential": "google"}).status_code == 403
    inicial = client.post("/acceso/enlace", json={"token": crear_token_bienvenida(usuario)}).json()["token"]
    assert client.post("/acceso/google", json={"credential": "google"},
                       headers={"Authorization": f"Bearer {inicial}"}).status_code == 200
    # Otro navegador sin sesion local: la identidad ya vinculada basta.
    assert client.post("/acceso/google", json={"credential": "google"}).json()["token"]


def test_google_varias_cuentas_mismo_email_sitios_y_permisos(contexto, monkeypatch):
    client, db, admin, usuario, evento = contexto
    usuario.email = admin.email
    db.commit()
    google(monkeypatch, admin.email, hd="example.com")
    respuesta = client.post("/acceso/google", json={"credential": "google"})
    assert respuesta.status_code == 200
    opciones = respuesta.json()["opciones"]
    assert {o["tipo"] for o in opciones} == {"administracion", "evento"}
    evento_op = next(o for o in opciones if o["tipo"] == "evento")
    cabeceras = {"Authorization": f"Bearer {evento_op['token']}"}
    assert client.get(f"/eventos/{evento.slug}/permisos", headers=cabeceras).json()["puede_editar"] is True
    assert client.get("/administracion/resumen", headers=cabeceras).status_code == 403
    assert len(client.get("/acceso/yo", headers=cabeceras).json()["opciones"]) == 2
    assert usuario.google_subject == admin.google_subject == "google-estable"


def test_bienvenida_confirma_solo_el_evento_de_su_destino(contexto):
    client, db, _, usuario, evento = contexto
    evento.estado = EventoEstado.BORRADOR
    otro = Evento(nombre="Otro", slug="otro-pendiente", propietario_id=usuario.id, estado=EventoEstado.BORRADOR)
    db.add(otro); db.commit()
    respuesta = client.post("/acceso/enlace", json={"token": crear_token_bienvenida(usuario, f"/e/{evento.slug}")})
    assert respuesta.status_code == 200
    assert evento.estado == EventoEstado.PUBLICADO and otro.estado == EventoEstado.BORRADOR


def test_alta_eventos_verificada_no_reenvia_y_no_publica_por_solo_escribir_email(contexto, monkeypatch):
    client, db, _, usuario, _ = contexto
    usuario.email_validado_en = datetime.now(UTC)
    db.commit()
    def prohibido(*args):
        raise AssertionError("No debe reenviar una bienvenida validada")
    monkeypatch.setattr("app.services.bienvenida.send_welcome_email", prohibido)
    datos = {"nombre": "Nuevo", "slug": "nuevo", "email": usuario.email, "lugar_tipo": "domicilio", "direccion": "Calle 1",
             "localidad": "Rio Gallegos", "provincia": "Santa Cruz", "pais": "Argentina"}
    r = client.post("/eventos", json=datos, headers=auth(usuario))
    assert r.status_code == 201 and r.json()["confirmado"] is True
    assert r.json()["bienvenida_enviada"] is False
    datos["slug"] = "sin-autenticar"
    r = client.post("/eventos", json=datos)
    assert r.status_code == 201 and r.json()["confirmado"] is False
    evento = db.scalar(select(Evento).where(Evento.slug == datos["slug"]))
    assert evento.estado == EventoEstado.BORRADOR
    assert client.post(f"/eventos/{evento.slug}/publicar").status_code == 401
    assert client.post(f"/eventos/{evento.slug}/publicar", headers=auth(usuario)).json()["confirmado"] is True


def test_correo_externo_desconocido_no_puede_reservar_identidad(contexto, monkeypatch):
    client, db, _, _, _ = contexto
    google(monkeypatch, "nuevo@hotmail.com")
    assert client.post("/acceso/google", json={"credential": "google"}).status_code == 403
    from app.models.usuarios import User
    assert db.scalar(select(User).where(User.email == "nuevo@hotmail.com")) is None


def test_bienvenida_no_se_duplica_entre_cuentas_con_mismo_correo(contexto, monkeypatch):
    _, db, admin, usuario, _ = contexto
    usuario.email = admin.email
    db.commit()
    envios = []
    monkeypatch.setattr("app.services.bienvenida.send_welcome_email", lambda *args: envios.append(args))
    assert enviar_bienvenida_una_vez(db, usuario)
    assert not enviar_bienvenida_una_vez(db, admin)
    assert len(envios) == 1


def test_corregir_email_requiere_nueva_validacion_del_nuevo_correo(contexto):
    client, db, admin, usuario, _ = contexto
    usuario.email_validado_en = datetime.now(UTC)
    usuario.bienvenida_enviada_en = datetime.now(UTC)
    anterior = crear_token_bienvenida(usuario)
    db.commit()
    assert client.put(f"/administracion/usuarios/{usuario.id}", headers=auth(admin),
                      json={"nombre": "Corregido", "email": "nuevo@example.com"}).status_code == 200
    assert usuario.email_validado_en is None and usuario.bienvenida_enviada_en is None
    assert client.post("/acceso/enlace", json={"token": anterior}).json()["token"] is None
