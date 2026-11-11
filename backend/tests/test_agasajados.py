import pytest
from sqlalchemy import select

from app.models.enums import RolEvento
from app.models.eventos import EventoUsuario
from app.models.usuarios import User
from app.services.acceso import get_access_options_by_user
from tests.test_invitados import auth, crear, habilitar

pytest_plugins = ["tests.test_administracion"]


def asignar(client, owner, email, **datos):
    respuesta = client.post("/invitados/prueba/agasajados", headers=auth(owner),
                            json={"emails": [email], **datos})
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def rol_de(db, email):
    return db.scalar(select(EventoUsuario).join(User).where(
        User.email == email, EventoUsuario.rol == RolEvento.AGASAJADO))


def test_alta_baja_reasignacion_y_origen_de_invitados(contexto, monkeypatch):
    client, db, _, owner, _ = contexto
    habilitar(client, owner)
    enviados = []
    monkeypatch.setattr("app.services.agasajados._send_email", lambda *args: enviados.append(args))
    alta = asignar(client, owner, "agasajado@example.com")
    assert alta["avisos"][0]["estado"] == "ENVIADO"
    assert "cargar invitados" in enviados[0][3]
    rol = rol_de(db, "agasajado@example.com")
    persona = rol.usuario
    assert client.get("/invitados/prueba/acceso", headers=auth(persona)).json()["agasajado_asignado_por"] == owner.email
    invitado = crear(client, persona, nombre="Mi contacto", telefono="123456")
    lista = client.get("/invitados/prueba/lista", headers=auth(persona)).json()["items"]
    assert lista[0]["agregado_por"] == persona.email
    baja = client.post(f"/invitados/prueba/roles/{rol.id}/revocar", headers=auth(owner))
    assert baja.status_code == 200 and baja.json()["avisos"][0]["estado"] == "ENVIADO"
    assert "Ya no tenes" in enviados[-1][3]
    assert client.post("/invitados/prueba/lista", headers=auth(persona), json={"nombre":"Otro"}).status_code == 403
    assert get_access_options_by_user(db, persona).opciones == []
    assert db.get(EventoUsuario, rol.id).permisos == []
    asignar(client, owner, persona.email)
    assert "editar_invitados" in db.get(EventoUsuario, rol.id).permisos
    assert client.get("/invitados/prueba/lista", headers=auth(persona)).status_code == 200
    assert invitado["nombre"] == "Mi contacto"


def test_baja_preserva_superadministrador(contexto, monkeypatch):
    client, db, admin, owner, _ = contexto
    habilitar(client, owner)
    enviados = []
    monkeypatch.setattr("app.services.agasajados._send_email", lambda *args: enviados.append(args))
    asignar(client, owner, admin.email)
    rol = rol_de(db, admin.email)
    respuesta = client.post(f"/invitados/prueba/roles/{rol.id}/revocar", headers=auth(owner))
    assert respuesta.status_code == 200
    assert "Conservas todos tus permisos de superadministrador" in enviados[-1][3]
    assert admin.es_superadministrador
    assert client.get("/administracion/resumen", headers=auth(admin)).status_code == 200
    assert client.post("/invitados/prueba/lista", headers=auth(admin), json={"nombre":"Desde admin"}).status_code == 201


def test_whatsapp_alta_baja_mismo_contacto_y_sin_correo(contexto, monkeypatch):
    client, db, _, owner, _ = contexto
    monkeypatch.setattr("app.services.agasajados._send_email", lambda *args: pytest.fail("No corresponde email"))
    alta = asignar(client, owner, "celular@example.com", contactos=[{
        "email":"celular@example.com", "canal":"whatsapp", "destinatario":"+54 9 2966 123456"}])
    aviso = alta["avisos"][0]
    assert aviso["estado"] == "PREPARADO"
    assert aviso["url_canal"].startswith("https://wa.me/5492966123456?text=")
    rol = rol_de(db, "celular@example.com")
    baja = client.post(f"/invitados/prueba/roles/{rol.id}/revocar", headers=auth(owner)).json()["avisos"][0]
    assert baja["contacto"] == aviso["contacto"]
    assert not baja["alta"] and "Ya no tenes" in baja["mensaje"]
    obsoleto = client.post(f"/invitados/prueba/avisos-agasajados/{aviso['id']}/reintentar", headers=auth(owner))
    assert obsoleto.status_code == 409


def test_fallo_email_no_revierte_permisos_y_se_puede_reintentar(contexto, monkeypatch):
    client, db, _, owner, _ = contexto
    def fallar(*args):
        raise RuntimeError("SMTP no disponible")
    monkeypatch.setattr("app.services.agasajados._send_email", fallar)
    alta = asignar(client, owner, "fallo@example.com")
    aviso = alta["avisos"][0]
    assert aviso["estado"] == "FALLIDO"
    rol = rol_de(db, "fallo@example.com")
    assert client.get("/invitados/prueba/acceso", headers=auth(rol.usuario)).status_code == 200
    assert client.post(f"/invitados/prueba/avisos-agasajados/{aviso['id']}/reintentar", headers=auth(rol.usuario)).status_code == 403
    enviados = []
    monkeypatch.setattr("app.services.agasajados._send_email", lambda *args: enviados.append(args))
    ruta = f"/invitados/prueba/avisos-agasajados/{aviso['id']}/reintentar"
    assert client.post(ruta, headers=auth(owner)).json()["avisos"][0]["estado"] == "ENVIADO"
    assert client.post(ruta, headers=auth(owner)).status_code == 200
    assert len(enviados) == 1


def test_contacto_invalido_no_asigna_y_no_envia(contexto, monkeypatch):
    client, db, _, owner, _ = contexto
    monkeypatch.setattr("app.services.agasajados._send_email", lambda *args: pytest.fail("No corresponde enviar"))
    r = client.post("/invitados/prueba/agasajados", headers=auth(owner), json={
        "emails":["mal@example.com"], "contactos":[{"email":"mal@example.com", "canal":"whatsapp", "destinatario":"123"}]})
    assert r.status_code == 422
    db.rollback()
    assert rol_de(db, "mal@example.com") is None
