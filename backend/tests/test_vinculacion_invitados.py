"""La cuenta autorizada persiste; compartir el enlace no transfiere la invitacion."""
import pytest
from sqlalchemy import select

from app.models.eventos import EventoUsuario
from app.models.enums import RolEvento
from app.models.invitaciones import CredencialInvitacion, Invitacion
from app.models.usuarios import User
from app.services.invitados import credencial, resolver_token
from fastapi import HTTPException
from tests.test_invitados import auth, crear, enlace, habilitar


@pytest.mark.parametrize("rol", ["administrador", "agasajado"])
def test_vincula_sin_correo_y_recupera_informacion_al_volver(contexto, rol):
    client, db, ajeno, owner, evento = contexto
    habilitar(client, owner)
    remitente = owner
    if rol == "agasajado":
        remitente = User(email="agasajado-vinculo@example.com")
        db.add(remitente); db.flush()
        db.add(EventoUsuario(evento_id=evento.id, usuario_id=remitente.id, rol=RolEvento.AGASAJADO, solo_responsable=True))
        db.commit()
    inv = crear(client, owner, nombre="Ana", apellido="Perez", responsable_id=remitente.id)
    token = enlace(client, owner, inv)
    ruta = f"/invitados/prueba/lista/{inv['id']}/cuenta"
    r = client.put(ruta, headers=auth(remitente), json={"email": "ana-google@example.com"})
    assert r.status_code == 200, r.text
    assert r.json()["cuenta_email"] == "ana-google@example.com"
    invitada = db.scalar(select(User).where(User.email == "ana-google@example.com"))
    assert db.get(Invitacion, inv["id"]).usuario_id == invitada.id
    assert db.get(Invitacion, inv["id"]).email is None
    base = "/invitados/prueba/portal"
    for headers in ({}, auth(ajeno)):
        vista = client.post(base, headers=headers, json={"token": token}).json()
        assert not vista["validado"] and "qr" not in vista and "nombre" not in vista
    sesion = auth(invitada)
    datos = {"token": token, "personas": [{"nombre": "Ana", "apellido": "Perez", "tipo": "ADULTO"}]}
    confirmada = client.post(base + "/confirmar", headers=sesion, json=datos)
    assert confirmada.status_code == 200, confirmada.text
    qr = confirmada.json()["qr"]
    for _ in range(2):
        vista = client.post(base, headers=sesion, json={"token": token}).json()
        assert vista["validado"] and vista["qr"] == qr and vista["nombre"] == "Ana"
    assert client.post("/invitados/prueba/mis-invitaciones", headers=sesion).json()["invitaciones"][0]["id"] == inv["id"]
    # Ni la sesion privada ni el enlace acreditan otra cuenta Google.
    vista = client.post(base, headers=auth(ajeno), json={"token": token, "sesion": confirmada.json()["sesion"]}).json()
    assert vista["sin_invitacion"] and not vista["puede_confirmar"] and "qr" not in vista
    assert client.post(base + "/qr.png", headers=auth(ajeno), json={"token": token}).status_code == 401
    assert client.put(ruta, headers=auth(invitada), json={"email": ajeno.email}).status_code == 403


def test_correo_coincidente_vincula_una_sola_vez_y_cambiar_cuenta_rota_qr(contexto):
    client, db, otro, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner, email=owner.email)
    token = enlace(client, owner, inv)
    base = "/invitados/prueba/portal"
    headers = auth(owner)
    primera = client.post(base, headers=headers, json={"token": token})
    assert primera.json()["validado"]
    db.refresh(db.get(Invitacion, inv["id"]))
    assert db.get(Invitacion, inv["id"]).usuario_id == owner.id
    datos = {"token": token, "personas": [{"nombre": "Ana", "apellido": "Perez", "tipo": "ADULTO"}]}
    # No enviar avisos como parte de esta prueba.
    from unittest.mock import patch
    with patch("app.services.invitados_notificaciones._send_email"):
        anterior = client.post(base + "/confirmar", headers=headers, json=datos).json()
    ruta = f"/invitados/prueba/lista/{inv['id']}/cuenta"
    assert client.put(ruta, headers=headers, json={"email": otro.email}).status_code == 200
    assert not client.post(base, headers=headers, json={"token": token, "sesion": anterior["sesion"]}).json()["validado"]
    nuevo = client.post(base, headers=auth(otro), json={"token": token}).json()
    assert nuevo["validado"] and nuevo["qr"] and nuevo["qr"] != anterior["qr"]
    with pytest.raises(HTTPException):
        resolver_token(db, "prueba", anterior["qr"], "qr")


def test_no_vincula_la_primera_cuenta_que_abre_un_enlace_ajeno(contexto):
    client, db, otro, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    vista = client.post("/invitados/prueba/portal", headers=auth(otro), json={"token": token}).json()
    assert vista["sin_invitacion"] and "qr" not in vista
    assert db.get(Invitacion, inv["id"]).usuario_id is None


def test_selector_google_valida_invitado_y_no_concede_roles(contexto, google, monkeypatch):
    client, db, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner, email="invitada-selector@gmail.com")
    token = enlace(client, owner, inv)
    def prohibido(*a, **kw):
        raise AssertionError("El selector Google no debe enviar codigos ni correos")
    monkeypatch.setattr("app.services.invitados_portal._send_email", prohibido)
    monkeypatch.setattr("app.services.acceso.send_access_link_email", prohibido)
    login = client.post("/acceso/google", json={"credential": google(email="invitada-selector@gmail.com", sub="google-invitada-selector")})
    assert login.status_code == 200 and login.json()["token"]
    assert [(o["slug"], o["roles"]) for o in login.json()["opciones"]] == [("prueba", ["Invitado"])]
    headers = {"Authorization": "Bearer " + login.json()["token"]}
    vista = client.post("/invitados/prueba/portal", headers=headers, json={"token": token}).json()
    assert vista["validado"] and vista["validacion"] == "google" and vista["puede_confirmar"]
    assert db.get(Invitacion, inv["id"]).usuario_id is not None
    permisos = client.get("/eventos/prueba/permisos", headers=headers).json()
    assert not permisos["puede_editar"] and permisos["permisos_invitados"] == []
    assert client.get("/administracion/resumen", headers=headers).status_code == 403
