import re

import pytest
from sqlalchemy import select

from app.core.seguridad import _firmar, crear_token_bienvenida
from app.models.enums import EventoEstado, RolEvento
from app.models.eventos import Evento, EventoUsuario
from app.models.invitaciones import Invitacion, MovimientoInvitacion, ValidacionInvitado
from app.models.usuarios import User
from tests.test_invitados import auth, crear, enlace, habilitar

pytest_plugins = ["tests.test_administracion"]


def pin_personal(client, owner, invitado):
    r = client.post(f"/invitados/prueba/lista/{invitado['id']}/pin-personal", headers=auth(owner), json={"canal":"presencial"})
    assert r.status_code == 200, r.text
    return r.json()["pin"]


def test_juan_valida_y_pedro_con_copia_no_puede_confirmar(contexto, monkeypatch):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="email")
    juan = crear(client, owner, nombre="Juan", email="juan@example.com")
    token = enlace(client, owner, juan)
    ruta = "/invitados/prueba/portal"
    publico = client.post(ruta, json={"token":token}).json()
    assert not publico["validado"] and "nombre" not in publico and "qr" not in publico
    assert client.get("/eventos/prueba").status_code == 200
    rsvp = {"token":token,"rsvp":{"asiste":True,"adultos":1}}
    for datos in [rsvp, {**rsvp,"email":"juan@example.com"}, {**rsvp,"email":"pedro@example.com"}]:
        assert client.post(ruta + "/rsvp", json=datos).status_code == 401
    envios = []
    monkeypatch.setattr("app.services.invitados_portal._send_email", lambda *args: envios.append(args))
    assert client.post(ruta + "/codigo", json={"token":token,"email":"pedro@example.com"}).status_code == 400
    assert not envios
    assert client.post(ruta + "/codigo", json={"token":token}).status_code == 200
    assert envios[0][0] == "juan@example.com"
    codigo = re.search(r"\d{6}", envios[0][3]).group()
    validacion = client.post(ruta + "/validar", json={"token":token,"codigo":codigo}).json()
    assert validacion["validado"] and validacion["nombre"] == "Juan"
    monkeypatch.setattr("app.services.invitados_notificaciones._send_email", lambda *args, **kw: None)
    assert client.post(ruta + "/rsvp", json={**rsvp,"sesion":validacion["sesion"]}).status_code == 200
    assert client.post(ruta + "/rsvp", json=rsvp).status_code == 401
    assert client.post(ruta + "/validar", json={"token":token,"codigo":codigo}).status_code == 401
    assert db.get(Invitacion, juan["id"]).rsvp == "CONFIRMADO"
    pedro = crear(client, owner, nombre="Pedro", email="pedro@example.com")
    assert enlace(client, owner, pedro) != token


def test_sin_contacto_no_se_puede_apropiar_de_invitacion(contexto, monkeypatch):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="email")
    invitado = crear(client, owner)
    token = enlace(client, owner, invitado)
    monkeypatch.setattr("app.services.invitados_portal._send_email", lambda *args: pytest.fail("No corresponde enviar"))
    r = client.post("/invitados/prueba/portal/codigo", json={"token":token,"email":"atacante@example.com"})
    assert r.status_code == 400
    assert db.get(Invitacion, invitado["id"]).email is None
    assert db.scalar(select(ValidacionInvitado)) is None


def test_pin_individual_no_compartido_y_rotacion_de_sesiones(contexto):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="pin")
    juan = crear(client, owner, nombre="Juan")
    pedro = crear(client, owner, nombre="Pedro")
    jt, pt = enlace(client, owner, juan), enlace(client, owner, pedro)
    pin = pin_personal(client, owner, juan)
    assert client.post("/invitados/prueba/portal/validar", json={"token":pt,"pin":pin}).status_code == 401
    r = client.post("/invitados/prueba/portal/validar", json={"token":jt,"pin":pin})
    assert r.status_code == 200 and r.json()["validado"]
    sesion = r.json()["sesion"]
    assert db.get(Invitacion, juan["id"]).pin_personal_hash != pin
    auditoria = list(db.scalars(select(MovimientoInvitacion)))
    assert all(pin not in str(a.datos) for a in auditoria)
    nuevo = pin_personal(client, owner, juan)
    assert nuevo != pin
    assert not client.post("/invitados/prueba/portal", json={"token":jt,"sesion":sesion}).json()["validado"]
    assert client.post("/invitados/prueba/portal/validar", json={"token":jt,"pin":pin}).status_code == 401
    assert client.post("/invitados/prueba/portal/validar", json={"token":jt,"pin":nuevo}).status_code == 200


def test_tokens_invitado_y_correo_nunca_administran(contexto):
    client, _, admin, owner, _ = contexto
    habilitar(client, owner, verificar_invitados=False)
    inv = crear(client, owner)
    enlace_inv = enlace(client, owner, inv)
    invitado = client.post("/invitados/prueba/portal", json={"token":enlace_inv}).json()["sesion"]
    correo = client.post("/acceso/enlace", json={"token":crear_token_bienvenida(admin)}).json()["token"]
    legado = _firmar({"tipo":"sesion","sub":str(admin.id),"email":admin.email}, 10)
    for token in [enlace_inv, invitado, correo, legado]:
        headers = {"Authorization":"Bearer " + token}
        assert client.get("/administracion/resumen", headers=headers).status_code == 401
        assert client.get("/invitados/prueba/lista", headers=headers).status_code == 401
        assert client.post("/invitados/prueba/agasajados", headers=headers, json={"emails":["intruso@example.com"]}).status_code == 401
        permisos = client.get("/eventos/prueba/permisos", headers=headers).json()
        assert permisos["usuario"] is None and not permisos["puede_editar"]


@pytest.mark.parametrize("rol", [RolEvento.ADMIN_EVENTO, RolEvento.AGASAJADO, RolEvento.GESTOR_INVITADOS, RolEvento.CONTROL_INGRESO])
def test_google_no_concede_roles_sin_asignacion_del_evento(contexto, google, rol):
    client, db, _, owner, _evento = contexto
    habilitar(client, owner)
    usuario = User(email="gestor@example.com")
    otro = Evento(nombre="Otro", slug="otro", propietario_id=owner.id, estado=EventoEstado.PUBLICADO)
    db.add_all([usuario, otro]); db.flush()
    db.add(EventoUsuario(evento_id=otro.id, usuario_id=usuario.id, rol=rol))
    db.commit()
    r = client.post("/acceso/google", json={"credential":google(email=usuario.email)})
    headers = {"Authorization":"Bearer " + r.json()["token"]}
    assert client.get("/invitados/prueba/acceso", headers=headers).status_code == 403
    assert client.post("/invitados/prueba/lista", headers=headers, json={"nombre":"Intruso"}).status_code == 403
    assert client.get("/eventos/prueba/permisos", headers=headers).json()["permisos_invitados"] == []


def test_telefono_registrado_proveedor_oficial_y_codigo_de_un_uso(contexto, monkeypatch):
    client, _db, _, owner, _ = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="telefono")
    inv = crear(client, owner, telefono="+54 9 2966 123456")
    token = enlace(client, owner, inv)
    enviados, comprobaciones = [], []
    referencia = "VE" + "1" * 32
    monkeypatch.setattr("app.services.verificacion_telefono.enviar", lambda tel: enviados.append(tel) or referencia)
    def comprobar(ref, code):
        comprobaciones.append((ref, code))
        return code == "123456"
    monkeypatch.setattr("app.services.verificacion_telefono.comprobar", comprobar)
    ruta = "/invitados/prueba/portal"
    assert client.post(ruta + "/codigo", json={"token":token,"telefono":"+199999999"}).status_code == 422
    assert client.post(ruta + "/codigo", json={"token":token}).status_code == 200
    assert enviados == ["+5492966123456"]
    assert client.post(ruta + "/validar", json={"token":token,"codigo":"000000"}).status_code == 401
    assert client.post(ruta + "/validar", json={"token":token,"codigo":"123456"}).json()["validado"]
    assert client.post(ruta + "/validar", json={"token":token,"codigo":"123456"}).status_code == 401
    assert comprobaciones == [(referencia,"000000"),(referencia,"123456")]


def test_sesion_aislada_y_no_acepta_cambio_de_contacto(contexto, monkeypatch):
    client, db, _, owner, _evento = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="pin")
    inv = crear(client, owner, email="juan@example.com")
    token = enlace(client, owner, inv)
    pin = pin_personal(client, owner, inv)
    sesion = client.post("/invitados/prueba/portal/validar", json={"token":token,"pin":pin}).json()["sesion"]
    assert client.post("/invitados/otro/portal", json={"token":token,"sesion":sesion}).status_code == 404
    fila = db.get(Invitacion, inv["id"])
    fila.email = "cambio@example.com"; db.commit()
    assert not client.post("/invitados/prueba/portal", json={"token":token,"sesion":sesion}).json()["validado"]


def test_pin_por_evento_y_alcance_propietario(contexto):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, verificar_invitados=True, validacion="pin")
    invitado = crear(client, owner)
    ajeno = User(email="ajeno@example.com")
    db.add(ajeno); db.commit()
    ruta = f"/invitados/prueba/lista/{invitado['id']}/pin-personal"
    assert client.post(ruta, headers=auth(ajeno), json={"canal":"presencial"}).status_code == 403
    assert client.post(ruta, headers=auth(owner), json={"canal":"mismo_mensaje"}).status_code == 422


def test_cambio_de_email_google_no_acredita_el_correo_anterior(contexto, google):
    client, db, _, usuario, _ = contexto
    usuario.google_subject = "identidad-google-estable"
    db.commit()
    habilitar(client, usuario, verificar_invitados=True, validacion="email")
    inv = crear(client, usuario, email=usuario.email)
    token = enlace(client, usuario, inv)
    r = client.post("/acceso/google", json={"credential":google(email="otro@gmail.com", sub="identidad-google-estable")})
    assert r.status_code == 200  # Conserva la identidad estable y sus roles explicitos.
    headers = {"Authorization":"Bearer " + r.json()["token"]}
    assert client.get("/eventos/prueba/permisos", headers=headers).json()["puede_editar"]
    assert not client.post("/invitados/prueba/portal", json={"token":token}, headers=headers).json()["validado"]
    assert db.scalar(select(User).where(User.email == "otro@gmail.com")) is None
