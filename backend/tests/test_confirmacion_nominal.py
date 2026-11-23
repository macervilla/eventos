import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, func, select, text

from app.models.eventos import Evento
from app.models.eventos import EventoUsuario
from app.models.enums import RolEvento
from app.models.invitaciones import CredencialInvitacion, DistribucionInvitacion, Invitacion, Participante
from app.models.usuarios import User
from tests.test_invitados import auth, crear, enlace, habilitar


def persona(nombre="Ana", apellido="Perez", tipo="ADULTO"):
    return {"nombre": nombre, "apellido": apellido, "tipo": tipo}


def test_confirmacion_nominal_emite_qr_inmediato_y_persistente(contexto, monkeypatch):
    client, db, _, owner, _ = contexto
    client.headers.update(auth(owner))
    habilitar(client, owner, aprobacion="manual")
    inv = crear(client, owner, nombre="Ana vieja", email=owner.email, cantidad_permitida=3)
    token = enlace(client, owner, inv)
    envios = []
    monkeypatch.setattr("app.services.invitados_notificaciones._send_email", lambda *a, **kw: envios.append(kw))
    datos = {"token": token, "personas": [persona(" Ana ", " Perez "),
        persona("Luis", "Gomez"), persona("Eva", "Gomez", "MENOR")]}
    r = client.post("/invitados/prueba/portal/confirmar", json=datos)
    assert r.status_code == 200, r.text
    resultado = r.json()
    assert resultado["nombre"] == "Ana" and resultado["apellido"] == "Perez"
    assert resultado["aprobacion"] == "APROBADO" and resultado["cupo_aprobado"] == 3
    assert resultado["qr"] and resultado["adultos"] == 2 and resultado["menores"] == 1
    assert resultado["acompanantes"] == [persona("Luis", "Gomez"), persona("Eva", "Gomez", "MENOR")]
    assert envios[0]["attachment"].startswith(b"\x89PNG")
    # Repetir o volver a consultar no rota el QR ni duplica personas o correos.
    repetida = client.post("/invitados/prueba/portal/confirmar", json=datos).json()
    assert repetida["qr"] == resultado["qr"] and len(envios) == 1
    visita = client.post("/invitados/prueba/portal", json={"token": token}).json()
    assert visita["qr"] == resultado["qr"] and visita["acompanantes"] == resultado["acompanantes"]
    assert client.post("/invitados/prueba/portal/qr.png", json={"token": token}).content.startswith(b"\x89PNG")
    assert db.scalar(select(func.count()).select_from(Participante).where(Participante.activo.is_(True))) == 2
    assert db.scalar(select(func.count()).select_from(CredencialInvitacion).where(
        CredencialInvitacion.tipo == "qr", CredencialInvitacion.activo.is_(True))) == 1


@pytest.mark.parametrize("personas", [[], [persona(apellido="")], [persona(nombre="  ")],
    [persona(tipo="MENOR")], [persona(), {"nombre": "Luis"}]])
def test_no_confirma_sin_nombres_completos(contexto, personas):
    client, db, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    r = client.post("/invitados/prueba/portal/confirmar", json={"token": token, "personas": personas})
    assert r.status_code == 422
    assert db.get(Invitacion, inv["id"]).rsvp == "PENDIENTE"


def test_no_supera_cupo_no_reactiva_revocados_y_no_expone_identidad(contexto):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="email")
    inv = crear(client, owner, email=owner.email, cantidad_permitida=1)
    token = enlace(client, owner, inv)
    datos = {"token": token, "personas": [persona()]}
    ruta = "/invitados/prueba/portal/confirmar"
    assert client.post(ruta, json=datos).status_code == 401
    assert client.post(ruta, json={**datos, "personas": [persona(), persona("Luis")]}, headers=auth(owner)).status_code == 409
    db.get(Invitacion, inv["id"]).aprobacion = "REVOCADO"; db.commit()
    assert client.post(ruta, json=datos, headers=auth(owner)).status_code == 409


def test_retorno_con_google_solo_resuelve_invitaciones_del_email_verificado(contexto, monkeypatch):
    client, db, admin, owner, evento = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="email")
    inv = crear(client, owner, email=owner.email)
    crear(client, owner, email="otro@example.com")
    otro = Evento(nombre="Otro", slug="otro", propietario_id=admin.id, estado=evento.estado)
    db.add(otro); db.flush()
    db.add(Invitacion(evento_id=otro.id, email=owner.email, nombre="Ajeno")); db.commit()
    ruta = "/invitados/prueba/mis-invitaciones"
    assert client.post(ruta).status_code == 401
    assert client.post(ruta, headers=auth(admin)).json()["invitaciones"] == []
    r = client.post(ruta, headers=auth(owner)).json()["invitaciones"]
    assert [i["id"] for i in r] == [inv["id"]]
    token = r[0]["token"]
    monkeypatch.setattr("app.services.invitados_notificaciones._send_email", lambda *a, **kw: None)
    respuesta = client.post("/invitados/prueba/portal/confirmar", headers=auth(owner),
        json={"token": token, "personas": [persona()]}).json()
    assert respuesta["qr"]
    regreso = client.post(ruta, headers=auth(owner)).json()["invitaciones"][0]
    assert regreso["token"] == token
    assert client.post("/invitados/prueba/portal", headers=auth(owner), json={"token": token}).json()["qr"] == respuesta["qr"]


def test_correcciones_nombres_guardan_historial_sin_perder_qr(contexto, monkeypatch):
    client, db, _, owner, _ = contexto
    client.headers.update(auth(owner))
    habilitar(client, owner, permitir_modificaciones=True)
    inv = crear(client, owner, email=owner.email, cantidad_permitida=2)
    token = enlace(client, owner, inv)
    datos = {"token": token, "personas": [persona(), persona("Luis", "Uno")]}
    ruta = "/invitados/prueba/portal/confirmar"
    primera = client.post(ruta, json=datos).json()
    datos["personas"][0]["apellido"] = "Corregido"
    datos["personas"][1]["apellido"] = "Dos"
    segunda = client.post(ruta, json=datos).json()
    assert segunda["apellido"] == "Corregido" and segunda["acompanantes"][0]["apellido"] == "Dos"
    assert segunda["qr"] == primera["qr"]
    filas = db.scalars(select(Participante).where(Participante.invitacion_id == inv["id"])).all()
    assert any(p.apellido == "Uno" and not p.activo for p in filas)
    assert sum(p.activo for p in filas) == 1


def test_migracion_apellidos_conserva_participantes():
    ruta = Path(__file__).resolve().parents[1] / "alembic/versions/0018_nombres_acompanantes.py"
    spec = importlib.util.spec_from_file_location("migracion_0018", ruta)
    migracion = importlib.util.module_from_spec(spec); spec.loader.exec_module(migracion)
    engine = create_engine("sqlite://")
    with engine.begin() as con:
        con.execute(text("CREATE TABLE participantes (id INTEGER PRIMARY KEY, nombre VARCHAR(160) NOT NULL)"))
        con.execute(text("INSERT INTO participantes (id,nombre) VALUES (1,'Existente')"))
        with Operations.context(MigrationContext.configure(con)):
            migracion.upgrade()
            assert con.execute(text("SELECT nombre,apellido FROM participantes")).one() == ("Existente", "")
            migracion.downgrade()
            assert con.scalar(text("SELECT nombre FROM participantes")) == "Existente"
            migracion.upgrade()
            assert con.scalar(text("SELECT count(*) FROM participantes")) == 1
    engine.dispose()


@pytest.mark.parametrize("con_correo", [False, True])
@pytest.mark.parametrize("emisor", ["administrador", "agasajado"])
def test_whatsapp_solo_confirma_la_identidad_autorizada(contexto, monkeypatch, con_correo, emisor):
    client, db, otra_cuenta, owner, evento = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="email", aprobacion="manual")
    remitente = owner
    if emisor == "agasajado":
        remitente = User(email="agasajado-whatsapp@example.com")
        db.add(remitente); db.flush()
        db.add(EventoUsuario(evento_id=evento.id, usuario_id=remitente.id, rol=RolEvento.AGASAJADO, solo_responsable=True))
        db.commit()
    inv = crear(client, owner, nombre="Ana", email=owner.email if con_correo else None,
                telefono="+5492966123456", cantidad_permitida=2, responsable_id=remitente.id)
    if not con_correo:
        db.get(Invitacion, inv["id"]).usuario_id = owner.id
        db.commit()
    token = enlace(client, owner, inv)
    base = "/invitados/prueba/portal"
    respuesta = client.post("/invitados/prueba/distribuir", headers=auth(remitente), json={
        "ids": [inv["id"]], "canal": "whatsapp", "tipo": "invitacion", "idempotencia": "whatsapp-identidad-prueba"})
    assert respuesta.status_code == 200
    assert "/e/" not in respuesta.json()["resultados"][0]["enlace"]
    token = respuesta.json()["resultados"][0]["enlace"].split("/i/")[1].split("#")[0]
    for headers in ({}, auth(otra_cuenta)):
        vista = client.post(base, headers=headers, json={"token": token}).json()
        assert not vista["validado"] and not vista["puede_confirmar"]
        assert "qr" not in vista and "nombre" not in vista
        assert vista["sin_invitacion"] == bool(headers)
        assert client.post(base + "/qr.png", headers=headers, json={"token": token}).status_code == 401
    vista = client.post(base, headers=auth(owner), json={"token": token}).json()
    assert vista["validado"] and vista["puede_confirmar"]
    def no_enviar_codigo(*a, **kw):
        raise AssertionError("WhatsApp no necesita codigo de correo")
    monkeypatch.setattr("app.services.invitados_portal._send_email", no_enviar_codigo)
    if not con_correo:
        assert client.post(base + "/codigo", json={"token": token}).status_code == 403
    monkeypatch.setattr("app.services.invitados_notificaciones._send_email", lambda *a, **kw: None)
    confirmada = client.post(base + "/confirmar", headers=auth(owner), json={"token": token,
        "personas": [persona(), persona("Luis", "Gomez")]})
    assert confirmada.status_code == 200, confirmada.text
    resultado = confirmada.json()
    assert resultado["qr"] and resultado["cupo_aprobado"] == 2
    assert client.post(base, headers=auth(owner), json={"token": token}).json()["qr"] == resultado["qr"]
    assert client.post(base + "/qr.png", headers=auth(owner), json={"token": token}).content.startswith(b"\x89PNG")
    assert client.post(base + "/validar", headers=auth(owner), json={"token": token}).json()["puede_confirmar"]
    for headers in ({}, auth(otra_cuenta)):
        vista = client.post(base, headers=headers, json={"token": token, "sesion": resultado["sesion"]}).json()
        if headers or not con_correo:
            assert not vista["validado"] and "qr" not in vista
    credencial = db.scalar(select(CredencialInvitacion).where(CredencialInvitacion.invitacion_id == inv["id"],
        CredencialInvitacion.tipo == "enlace", CredencialInvitacion.activo.is_(True)))
    credencial.activo = False; db.commit()
    assert client.post(base, headers=auth(owner), json={"token": token}).status_code == 404
    assert client.post(base + "/confirmar", headers=auth(owner), json={"token": token, "personas": [persona()]}).status_code == 404


@pytest.mark.parametrize("canal,tipo,estado", [("whatsapp", "invitacion", "FALLIDO"),
    ("whatsapp", "qr", "PREPARADO"), ("email", "invitacion", "ENVIADO")])
def test_otras_distribuciones_no_habilitan_acceso_directo(contexto, canal, tipo, estado):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="email")
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    db.add(DistribucionInvitacion(invitacion_id=inv["id"], actor_id=owner.id,
        canal=canal, tipo=tipo, estado=estado, idempotencia="caso-no-habilitado-12345"))
    db.commit()
    assert not client.post("/invitados/prueba/portal", json={"token": token}).json()["validado"]
