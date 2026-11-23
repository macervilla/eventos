"""Correo verificado para enlaces sin distribucion de WhatsApp autorizada."""

import pytest
from sqlalchemy import select

from app.core.seguridad import _leer
from app.models.eventos import Evento
from app.models.invitaciones import CredencialInvitacion, DistribucionInvitacion, Invitacion
from app.services.invitados_portal import crear_sesion, crear_sesion_email, regla_verificacion, resolver_portal
from app.schemas.invitados import PortalAcceso
from tests.test_invitados import auth, crear, enlace, habilitar


def preparar(contexto, **cfg):
    client, db, admin, owner, evento = contexto
    habilitar(client, owner, **cfg)
    inv = crear(client, owner, email=owner.email, nombre="Ana", apellido="Perez", cantidad_permitida=2)
    return client, db, admin, owner, evento, inv, enlace(client, owner, inv)


def personas(token, **extra):
    return {"token": token, "personas": [{"nombre": "Ana", "apellido": "Perez", "tipo": "ADULTO"}], **extra}


def test_google_correcto_confirma_y_recupera_qr(contexto, monkeypatch):
    client, db, admin, owner, evento, inv, token = preparar(contexto)
    monkeypatch.setattr("app.services.invitados_notificaciones._send_email", lambda *a, **kw: None)
    base = "/invitados/prueba/portal"
    vista = client.post(base, json={"token": token}, headers=auth(owner)).json()
    assert vista["validado"] and vista["puede_confirmar"]
    assert vista["email_asociado"] == owner.email
    r = client.post(base + "/confirmar", json=personas(token), headers=auth(owner))
    assert r.status_code == 200, r.text
    qr = r.json()["qr"]
    assert qr and r.json()["cupo_aprobado"] == 1
    regreso = client.post(base, json={"token": token}, headers=auth(owner)).json()
    assert regreso["qr"] == qr and regreso["rsvp"] == "CONFIRMADO"
    assert client.post(base + "/qr.png", json={"token": token}, headers=auth(owner)).content.startswith(b"\x89PNG")


@pytest.mark.parametrize("verificar", [True, False])
def test_enlace_sin_distribucion_whatsapp_requiere_correo(contexto, verificar):
    client, db, admin, owner, evento, inv, token = preparar(contexto, verificar_invitados=verificar)
    base = "/invitados/prueba/portal"
    for headers in ({}, auth(admin)):
        vista = client.post(base, json={"token": token}, headers=headers).json()
        assert not vista["validado"] and not vista["puede_confirmar"]
        assert owner.email not in str(vista) and "nombre" not in vista and "qr" not in vista
        assert vista["email_asociado"] is None
        assert vista["cuenta_diferente"] == bool(headers)
        for ruta, datos in (("/confirmar", personas(token)), ("/qr.png", {"token": token}),
                            ("/rsvp", {"token": token, "rsvp": {"asiste": True, "adultos": 1}})):
            assert client.post(base + ruta, json=datos, headers=headers).status_code == 401
    assert db.get(Invitacion, inv["id"]).rsvp == "PENDIENTE"
    assert db.scalar(select(CredencialInvitacion).where(CredencialInvitacion.tipo == "qr")) is None


def test_solo_google_no_acepta_codigos_ni_sesiones_anteriores(contexto, monkeypatch):
    client, db, admin, owner, evento, inv, token = preparar(contexto, verificar_invitados=False, validacion="pin")
    base = "/invitados/prueba/portal"
    datos = PortalAcceso(token=token)
    fila, credencial, ev, cfg = resolver_portal(db, "prueba", datos)
    anterior = crear_sesion(fila, credencial, regla_verificacion(fila, ev, cfg))
    assert not client.post(base, json={"token": token, "sesion": anterior}).json()["validado"]
    assert client.post(base + "/confirmar", json=personas(token, sesion=anterior)).status_code == 401
    envios = []
    monkeypatch.setattr("app.services.invitados_portal._send_email", lambda *args: envios.append(args))
    assert client.post(base + "/codigo", json={"token": token, "email": admin.email}).status_code == 403
    assert client.post(base + "/codigo", json={"token": token}).status_code == 403
    assert not envios
    sesion = crear_sesion_email(fila, credencial, regla_verificacion(fila, ev, cfg))
    for extra in ({"codigo": "123456"}, {"sesion": sesion}, {"pin": "1234567890"}):
        assert client.post(base + "/validar", json={"token": token, **extra}).status_code == 401
        assert not client.post(base, json={"token": token, **extra}).json()["validado"]
    assert client.post(base + "/validar", headers=auth(owner), json={"token": token}).json()["validado"]
    monkeypatch.setattr("app.services.invitados_notificaciones._send_email", lambda *a, **kw: None)
    assert client.post(base + "/confirmar", json=personas(token, sesion=sesion)).status_code == 401
    assert client.post(base + "/confirmar", headers=auth(owner), json=personas(token)).json()["qr"]
    # Una cuenta Google distinta tampoco puede reutilizar esa prueba de correo.
    assert client.post(base + "/qr.png", json={"token": token, "sesion": sesion}, headers=auth(admin)).status_code == 401
    fila.email = "cambiado@example.com"; db.commit()
    assert not client.post(base, json={"token": token, "sesion": sesion}).json()["validado"]


def test_publico_sin_invitacion_no_enumera_y_no_acepta_ids(contexto):
    client, db, admin, owner, evento, inv, token = preparar(contexto)
    ruta = "/invitados/prueba"
    assert client.post(ruta + "/mis-invitaciones").status_code == 401
    assert client.post(ruta + "/mis-invitaciones", headers=auth(admin)).json() == {"invitaciones": []}
    assert client.post(ruta + "/mis-invitaciones", json={"email": owner.email}, headers=auth(admin)).json() == {"invitaciones": []}
    assert client.post(ruta + "/portal/confirmar", json=personas(token, email=owner.email)).status_code == 401
    assert [i["id"] for i in client.post(ruta + "/mis-invitaciones", headers=auth(owner)).json()["invitaciones"]] == [inv["id"]]
    assert client.post(ruta + "/portal/confirmar", json=personas("x" * 43), headers=auth(owner)).status_code == 404
    assert client.post(ruta + "/portal/confirmar", json=personas(token, invitacion_id=inv["id"]), headers=auth(admin)).status_code == 422
    otro = Evento(nombre="Otro", slug="otro-cuenta", propietario_id=owner.id, estado=evento.estado)
    db.add(otro); db.commit()
    assert client.post("/invitados/otro-cuenta/portal/confirmar", json=personas(token), headers=auth(owner)).status_code == 404


@pytest.mark.parametrize("campo,estado", [("aprobacion", "REVOCADO"), ("aprobacion", "RECHAZADO"),
                                         ("rsvp", "RECHAZADO"), ("rsvp", "CANCELADO")])
def test_estados_no_reactivan_invitacion(contexto, campo, estado):
    client, db, admin, owner, evento, inv, token = preparar(contexto)
    setattr(db.get(Invitacion, inv["id"]), campo, estado); db.commit()
    base = "/invitados/prueba/portal"
    vista = client.post(base, json={"token": token}, headers=auth(owner)).json()
    assert vista["no_disponible"] and not vista["puede_confirmar"] and not vista["qr"]
    assert client.post(base + "/confirmar", json=personas(token), headers=auth(owner)).status_code == 409
    assert client.post(base + "/qr.png", json={"token": token}, headers=auth(owner)).status_code == 409
    assert client.post("/invitados/prueba/mis-invitaciones", headers=auth(owner)).json()["invitaciones"] == []


def test_sin_correo_y_enlace_revocado_no_autorizan(contexto):
    client, db, admin, owner, evento, inv, token = preparar(contexto)
    db.get(Invitacion, inv["id"]).email = None; db.commit()
    base = "/invitados/prueba/portal"
    vista = client.post(base, headers=auth(owner), json={"token": token}).json()
    assert vista["sin_contacto"] and vista["email_asociado"] is None and not vista["validado"]
    assert client.post(base + "/confirmar", json=personas(token), headers=auth(owner)).status_code == 401
    cred = db.scalar(select(CredencialInvitacion).where(CredencialInvitacion.tipo == "enlace"))
    cred.activo = False; db.commit()
    assert client.post(base, json={"token": token}, headers=auth(owner)).status_code == 404


@pytest.mark.parametrize("campo,estado", [("aprobacion", "REVOCADO"), ("aprobacion", "RECHAZADO"),
                                         ("rsvp", "RECHAZADO"), ("rsvp", "CANCELADO")])
def test_whatsapp_no_reactiva_invitaciones_bloqueadas(contexto, campo, estado):
    client, db, _, owner, _, inv, token = preparar(contexto)
    db.add(DistribucionInvitacion(invitacion_id=inv["id"], actor_id=owner.id, canal="whatsapp",
        tipo="invitacion", estado="PREPARADO", idempotencia="whatsapp-bloqueada-123"))
    setattr(db.get(Invitacion, inv["id"]), campo, estado); db.commit()
    base = "/invitados/prueba/portal"
    vista = client.post(base, headers=auth(owner), json={"token": token}).json()
    assert vista["no_disponible"] and not vista["puede_confirmar"] and vista["qr"] is None
    assert client.post(base + "/confirmar", headers=auth(owner), json=personas(token)).status_code == 409
    assert client.post(base + "/qr.png", headers=auth(owner), json={"token": token}).status_code == 409


def test_whatsapp_y_sesion_de_enlace_no_sustituyen_identidad(contexto):
    client, db, _, owner, _, inv, token = preparar(contexto)
    distribucion = DistribucionInvitacion(invitacion_id=inv["id"], actor_id=owner.id, canal="whatsapp",
        tipo="invitacion", estado="PREPARADO", idempotencia="whatsapp-retirada-123")
    db.add(distribucion); db.commit()
    base = "/invitados/prueba/portal"
    fila, credencial, evento, cfg = resolver_portal(db, "prueba", PortalAcceso(token=token))
    sesion = crear_sesion(fila, credencial, regla_verificacion(fila, evento, cfg))
    datos = {"token": token, "sesion": sesion}
    assert not client.post(base, json=datos).json()["validado"]
    assert client.post(base + "/confirmar", json=personas(token, sesion=sesion)).status_code == 401
    assert client.post(base + "/qr.png", json=datos).status_code == 401
    assert client.post(base + "/fotos/listar", json=datos).status_code == 401
