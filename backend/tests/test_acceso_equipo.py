from sqlalchemy import select

from app.models.usuarios import User
from tests.test_invitados import auth, crear, enlace, habilitar


def test_aviso_agasajado_indica_google_email_y_acceso_de_equipo(contexto):
    client, _, _, owner, _ = contexto
    r = client.post("/invitados/prueba/agasajados", headers=auth(owner), json={"emails":["agasajado@example.com"]})
    assert r.status_code == 200
    aviso = r.json()["avisos"][0]
    assert aviso["rol"] == "Agasajado"
    assert "Google" in aviso["mensaje"] and "agasajado@example.com" in aviso["mensaje"]
    assert "/e/prueba/acceso-equipo" in aviso["mensaje"]
    assert "/i/" not in aviso["mensaje"] and "confirmar asistencia" not in aviso["mensaje"]


def test_aviso_administrador_no_es_invitacion_de_asistencia(contexto):
    client, _, _, owner, _ = contexto
    r = client.post("/invitados/prueba/roles", headers=auth(owner), json={"email":"admin-evento@example.com","rol":"ADMIN_EVENTO"})
    assert r.status_code == 200
    aviso = r.json()["avisos"][0]
    assert aviso["rol"] == "Administrador" and "como Administrador" in aviso["mensaje"]
    assert "/acceso-equipo" in aviso["mensaje"] and "admin-evento@example.com" in aviso["mensaje"]


def test_enlace_anterior_orienta_a_google_sin_conceder_privilegios(contexto, google):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="email")
    client.post("/invitados/prueba/agasajados", headers=auth(owner), json={"emails":["agasajado@example.com"]})
    invitacion = crear(client, owner, email="agasajado@example.com")
    token = enlace(client, owner, invitacion)
    portal = client.post("/invitados/prueba/portal", json={"token":token})
    assert portal.json()["acceso_equipo"] and not portal.json()["validado"]
    assert "nombre" not in portal.json() and "sesion" not in portal.json()
    assert client.post("/invitados/prueba/portal/rsvp", json={"token":token,"rsvp":{"asiste":True,"adultos":1}}).status_code == 401
    login = client.post("/acceso/google", json={"credential":google(email="agasajado@example.com")})
    headers = {"Authorization":"Bearer " + login.json()["token"]}
    assert client.get("/invitados/prueba/lista", headers=headers).status_code == 200
    assert client.post("/invitados/prueba/lista", headers=headers, json={"nombre":"Contacto nuevo"}).status_code == 201
    otra = client.post("/acceso/google", json={"credential":google(email="otra@example.com")})
    assert client.get("/invitados/prueba/lista", headers={"Authorization":"Bearer " + otra.json()["token"]}).status_code == 403
    persona = db.scalar(select(User).where(User.email == "agasajado@example.com"))
    assert persona.google_subject


def test_invitado_sin_rol_conserva_verificacion(contexto):
    client, _, _, owner, _ = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="email")
    invitacion = crear(client, owner, email="invitado@example.com")
    token = enlace(client, owner, invitacion)
    portal = client.post("/invitados/prueba/portal", json={"token":token}).json()
    assert not portal["acceso_equipo"] and not portal["validado"]
