from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from sqlalchemy import func, select

from app.models.enums import RolEvento
from app.models.eventos import Evento, EventoUsuario
from app.models.invitaciones import CredencialInvitacion, Invitacion, MovimientoInvitacion, ValidacionInvitado
from app.models.solicitudes_invitacion import SolicitudInvitacion
from app.models.usuarios import User
from app.services.invitados import ahora
from tests.test_invitados import auth, crear, habilitar


@pytest.fixture()
def solicitudes(contexto):
    client, db, admin, owner, evento = contexto
    habilitar(client, owner)
    lili = User(nombre="Nombre privado Lili", email="lili@example.com")
    leo = User(nombre="Nombre privado Leo", email="leo@example.com")
    ana = User(nombre="Ana", email="ana@example.com")
    otra = User(nombre="Ana", email="otra@example.com")
    db.add_all([lili, leo, ana, otra]); db.flush()
    for u in (lili, leo):
        db.add(EventoUsuario(evento_id=evento.id, usuario_id=u.id, rol=RolEvento.AGASAJADO, solo_responsable=False))
    db.commit()
    return client, db, owner, evento, lili, leo, ana, otra


def publicar(client, owner, host, **extra):
    datos = {"nombre_publico": "Lili" if "lili" in host.email else "Leo", "habilitado": True,
             "publicar_email": False, "publicar_whatsapp": False, **extra}
    r = client.put(f"/invitados/prueba/solicitudes/contactos/{host.id}", headers=auth(owner), json=datos)
    assert r.status_code == 200, r.text


def pedir(client, usuario, host, **extra):
    return client.post("/invitados/prueba/solicitudes", headers=auth(usuario), json={
        "nombre": "  Ána  Maria ", "apellido": " Pérez  ", "agasajado_id": host.id,
        "canal": "email", "email": usuario.email, **extra})


def test_contactos_solo_publicados_explicitamente_y_por_evento(solicitudes):
    client, db, owner, evento, lili, leo, ana, otra = solicitudes
    base = "/invitados/prueba/solicitudes"
    assert client.get(base + "/opciones").status_code == 401
    assert client.get(base + "/opciones", headers=auth(ana)).json()["agasajados"] == []
    publicar(client, owner, lili, email="publico@example.com", whatsapp="02966 15-123456")
    opcion = client.get(base + "/opciones", headers=auth(ana)).json()["agasajados"][0]
    assert opcion == {"id": lili.id, "nombre": "Lili", "whatsapp_url": None, "email_url": None}
    publicar(client, owner, lili, email="publico@example.com", whatsapp="02966 15-123456", publicar_email=True, publicar_whatsapp=True)
    opcion = client.get(base + "/opciones", headers=auth(ana)).json()["agasajados"][0]
    wa = urlsplit(opcion["whatsapp_url"])
    assert wa.netloc == "wa.me" and wa.path == "/5492966123456"
    mensaje = parse_qs(wa.query)["text"][0]
    assert "Prueba" in mensaje and "token" not in mensaje and ana.email not in mensaje
    assert "publico@example.com" in opcion["email_url"]
    assert "Consulta por invitación - Prueba" in unquote(opcion["email_url"])
    assert lili.email not in str(opcion) and "Nombre privado" not in str(opcion)
    # Un agasajado no administra la publicacion del otro.
    assert client.put(base + f"/contactos/{leo.id}", headers=auth(lili), json={"nombre_publico": "Leo"}).status_code == 403
    assert client.get(base + "/contactos", headers=auth(lili)).json()[0]["agasajado_id"] == lili.id
    rol = db.scalar(select(EventoUsuario).where(EventoUsuario.usuario_id == lili.id))
    rol.permisos = []; db.commit()
    assert client.get(base + "/opciones", headers=auth(ana)).json()["agasajados"] == []
    assert pedir(client, ana, lili).status_code == 422


def test_solicitud_repetida_no_duplica_invitacion_cupo_o_notificacion(solicitudes):
    client, db, owner, evento, lili, leo, ana, otra = solicitudes
    publicar(client, owner, lili); publicar(client, owner, leo)
    assert pedir(client, ana, lili).status_code == 202
    assert pedir(client, ana, leo, nombre="ANA MARIA", apellido="PEREZ").status_code == 202
    rows = db.scalars(select(SolicitudInvitacion)).all()
    assert len(rows) == 1 and rows[0].agasajado_id == lili.id
    assert rows[0].nombre == "Ána Maria" and rows[0].apellido == "Pérez"
    assert rows[0].nombre_normalizado == "ana maria" and rows[0].email_verificado == ana.email
    assert db.scalar(select(func.count()).select_from(Invitacion)) == 0
    assert db.scalar(select(func.count()).select_from(CredencialInvitacion)) == 0
    assert db.scalar(select(func.count()).select_from(MovimientoInvitacion).where(MovimientoInvitacion.accion == "solicitud_invitacion_recibida")) == 1


def test_aislamiento_entre_agasajados_y_administracion_general(solicitudes):
    client, db, owner, evento, lili, leo, ana, otra = solicitudes
    publicar(client, owner, lili); publicar(client, owner, leo)
    pedir(client, ana, lili); pedir(client, otra, leo)
    base = "/invitados/prueba/solicitudes"
    propios = client.get(base, headers=auth(lili)).json()["items"]
    ajenos = client.get(base, headers=auth(leo)).json()["items"]
    assert len(propios) == len(ajenos) == 1 and propios[0]["email"] == ana.email and ajenos[0]["email"] == otra.email
    assert len(client.get(base, headers=auth(owner)).json()["items"]) == 2
    assert client.get(base, headers=auth(ana)).status_code == 403
    assert client.post(base + f"/{ajenos[0]['id']}/resolver", headers=auth(lili), json={"estado": "APROBADA"}).status_code == 404
    assert client.post(base + f"/{propios[0]['id']}/resolver", json={"estado": "APROBADA"}).status_code == 401
    assert client.post(base + f"/{propios[0]['id']}/resolver", headers=auth(ana), json={"estado": "APROBADA"}).status_code == 403


def test_aprobar_crea_una_invitacion_pendiente_sin_qr(solicitudes):
    client, db, owner, evento, lili, leo, ana, otra = solicitudes
    publicar(client, owner, lili)
    pedir(client, ana, lili, canal="whatsapp", telefono="02966 15-123456", email=None)
    solicitud = db.scalar(select(SolicitudInvitacion))
    assert solicitud.telefono == "+5492966123456"
    ruta = f"/invitados/prueba/solicitudes/{solicitud.id}/resolver"
    r = client.post(ruta, headers=auth(lili), json={"estado": "APROBADA"})
    assert r.status_code == 200, r.text
    invitacion_id = r.json()["invitacion_id"]
    inv = db.get(Invitacion, invitacion_id)
    assert inv.responsable_id == lili.id and inv.usuario_id == ana.id and inv.canal == "whatsapp"
    assert inv.email == ana.email and inv.rsvp == "PENDIENTE" and inv.aprobacion == "PENDIENTE" and inv.cupo_aprobado == 0
    assert db.scalar(select(func.count()).select_from(CredencialInvitacion)) == 0
    assert client.post(ruta, headers=auth(lili), json={"estado": "APROBADA"}).json()["invitacion_id"] == invitacion_id
    assert db.scalar(select(func.count()).select_from(Invitacion)) == 1
    # La confirmacion existente sigue siendo una operacion posterior y autorizada.
    mis = client.post("/invitados/prueba/mis-invitaciones", headers=auth(ana)).json()["invitaciones"]
    assert len(mis) == 1
    token = mis[0]["token"]
    assert client.post("/invitados/prueba/portal/qr.png", headers=auth(ana), json={"token": token}).status_code == 409
    assert not client.post("/invitados/prueba/portal", headers=auth(otra), json={"token": token}).json()["validado"]


def test_invitacion_existente_no_duplica_solicitud_y_alta_paralela_se_reutiliza(solicitudes):
    client, db, owner, evento, lili, leo, ana, otra = solicitudes
    publicar(client, owner, lili)
    crear(client, owner, nombre="Ana", email=ana.email, responsable_id=lili.id)
    assert pedir(client, ana, lili).status_code == 202
    assert db.scalar(select(func.count()).select_from(SolicitudInvitacion)) == 0
    pedir(client, otra, lili)
    row = db.scalar(select(SolicitudInvitacion))
    existente = crear(client, owner, nombre="Otra", email=otra.email, responsable_id=lili.id)
    r = client.post(f"/invitados/prueba/solicitudes/{row.id}/resolver", headers=auth(lili), json={"estado": "APROBADA"})
    assert r.status_code == 200, r.text
    assert r.json()["invitacion_id"] == existente["id"]
    assert db.scalar(select(func.count()).select_from(Invitacion)) == 2


def test_nombres_iguales_contactos_distintos_requieren_revision_no_fusion(solicitudes):
    client, db, owner, evento, lili, leo, ana, otra = solicitudes
    publicar(client, owner, lili)
    primero = crear(client, owner, nombre="ÁNA MARIA", apellido="Pérez", email=otra.email, responsable_id=lili.id)
    pedir(client, ana, lili)
    row = db.scalar(select(SolicitudInvitacion))
    assert row.requiere_revision
    ruta = f"/invitados/prueba/solicitudes/{row.id}/resolver"
    assert client.post(ruta, headers=auth(lili), json={"estado": "APROBADA"}).status_code == 409
    assert client.post(ruta, headers=auth(lili), json={"estado": "APROBADA", "confirmar_revision": True, "invitacion_id": primero["id"]}).status_code == 409
    r = client.post(ruta, headers=auth(lili), json={"estado": "APROBADA", "confirmar_revision": True})
    assert r.status_code == 200, r.text
    assert r.json()["invitacion_id"] != primero["id"]
    assert db.get(Invitacion, primero["id"]).email == otra.email


def test_correo_ajeno_numero_invalido_agasajado_ajeno_y_rechazo(solicitudes):
    client, db, owner, evento, lili, leo, ana, otra = solicitudes
    publicar(client, owner, lili)
    assert client.get("/invitados/prueba/solicitudes/contactos", headers=auth(ana)).status_code == 403
    assert client.post("/invitados/prueba/solicitudes", json={"nombre": "Ana", "apellido": "Perez", "agasajado_id": lili.id, "canal": "email", "email": ana.email}).status_code == 401
    assert pedir(client, ana, lili, email=otra.email).status_code == 422
    assert pedir(client, ana, lili, canal="whatsapp", telefono="123").status_code == 422
    assert pedir(client, ana, owner).status_code == 422
    pedir(client, ana, lili)
    row = db.scalar(select(SolicitudInvitacion))
    ruta = f"/invitados/prueba/solicitudes/{row.id}/resolver"
    assert client.post(ruta, headers=auth(lili), json={"estado": "RECHAZADA"}).status_code == 200
    assert client.post(ruta, headers=auth(lili), json={"estado": "APROBADA"}).status_code == 409
    assert db.scalar(select(func.count()).select_from(Invitacion)) == 0
    otro_evento = Evento(nombre="Otro", slug="otro-solicitudes", propietario_id=owner.id, estado=evento.estado)
    db.add(otro_evento); db.commit()
    assert client.post(f"/invitados/otro-solicitudes/solicitudes/{row.id}/resolver", headers=auth(owner), json={"estado": "APROBADA"}).status_code in {404, 409}


def test_no_sobrescribe_contactos_ni_fusiona_telefono_de_identidad_verificada(solicitudes):
    client, db, owner, evento, lili, leo, ana, otra = solicitudes
    publicar(client, owner, lili)
    existente = crear(client, owner, nombre="Otro", email=otra.email, telefono="+5492966123456", responsable_id=lili.id)
    db.add(ValidacionInvitado(invitacion_id=existente["id"], codigo_hash="prueba", email="+5492966123456", metodo="telefono", usado=True, vence_at=ahora()))
    db.commit()
    pedir(client, ana, lili, canal="whatsapp", telefono="02966 15-123456", email=None)
    row = db.scalar(select(SolicitudInvitacion))
    assert row.requiere_revision
    r = client.post(f"/invitados/prueba/solicitudes/{row.id}/resolver", headers=auth(lili), json={"estado": "APROBADA", "confirmar_revision": True})
    assert r.status_code == 409
    assert db.scalar(select(func.count()).select_from(Invitacion)) == 1
    assert db.get(Invitacion, existente["id"]).email == otra.email
    # Tampoco se elude el control usando el alta administrativa habitual.
    r = client.post("/invitados/prueba/lista", headers=auth(owner), json={"nombre": "Ana", "email": ana.email,
        "telefono": "+34612345678", "whatsapp": "+5492966123456", "responsable_id": lili.id})
    assert r.status_code == 409
    assert db.scalar(select(func.count()).select_from(Invitacion)) == 1


def test_invitacion_revocada_se_revisa_sin_reactivar_ni_duplicar(solicitudes):
    client, db, owner, evento, lili, leo, ana, otra = solicitudes
    publicar(client, owner, lili)
    existente = crear(client, owner, nombre="Ana", email=ana.email, responsable_id=lili.id)
    db.get(Invitacion, existente["id"]).aprobacion = "REVOCADO"; db.commit()
    assert pedir(client, ana, lili).status_code == 202
    row = db.scalar(select(SolicitudInvitacion))
    assert row.requiere_revision
    r = client.post(f"/invitados/prueba/solicitudes/{row.id}/resolver", headers=auth(owner), json={"estado": "APROBADA", "confirmar_revision": True})
    assert r.status_code == 409
    assert db.get(Invitacion, existente["id"]).aprobacion == "REVOCADO"
    assert db.scalar(select(func.count()).select_from(Invitacion)) == 1


def test_alta_normaliza_telefonos_antes_de_detectar_duplicados(solicitudes):
    client, db, owner, evento, lili, leo, ana, otra = solicitudes
    crear(client, owner, nombre="Ana", telefono="02966 15-123456", responsable_id=lili.id)
    r = client.post("/invitados/prueba/lista", headers=auth(owner), json={"nombre": "Otra", "telefono": "+5492966123456", "responsable_id": lili.id})
    assert r.status_code == 409
    assert db.scalar(select(func.count()).select_from(Invitacion)) == 1
