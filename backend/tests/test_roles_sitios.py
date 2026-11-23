from app.models.enums import EventoEstado, RolEvento
from app.models.eventos import Evento, EventoModulo, EventoUsuario
from app.models.invitaciones import Invitacion
from app.models.proveedores import Proveedor
from tests.test_administracion import auth


def test_roles_de_cada_sitio_y_asignaciones_revocadas(contexto):
    client, db, admin, usuario, propio = contexto
    otro = Evento(nombre="Asignado", slug="asignado-roles", propietario_id=admin.id, estado=propio.estado)
    db.add(otro); db.flush()
    db.add_all([
        EventoUsuario(evento_id=otro.id, usuario_id=usuario.id, rol=RolEvento.AGASAJADO),
        EventoUsuario(evento_id=otro.id, usuario_id=usuario.id, rol=RolEvento.CONTROL_INGRESO),
        EventoUsuario(evento_id=otro.id, usuario_id=usuario.id, rol=RolEvento.ADMIN_EVENTO, permisos=[]),
        Proveedor(nombre_comercial="Proveedor", slug="proveedor-roles", usuario_id=usuario.id, email=usuario.email),
    ])
    db.commit()
    opciones = client.get("/acceso/yo", headers=auth(usuario)).json()["opciones"]
    sitios = {o["slug"]: o for o in opciones}
    assert sitios[propio.slug]["roles"] == ["Administrador"]
    assert set(sitios[otro.slug]["roles"]) == {"Agasajado", "Control de ingreso"}
    assert sitios["proveedor-roles"]["roles"] == ["Administrador"]
    globales = client.get("/acceso/yo", headers=auth(admin)).json()["opciones"]
    assert next(o for o in globales if o["tipo"] == "administracion")["roles"] == ["Superadministrador"]


def test_invitado_aparece_solo_con_identidad_autorizada_sin_conceder_gestion(contexto):
    client, db, admin, usuario, _ = contexto
    evento = Evento(nombre="Invitado", slug="invitado-roles", propietario_id=admin.id, estado=EventoEstado.PUBLICADO)
    db.add(evento); db.flush()
    db.add(EventoModulo(evento_id=evento.id, modulo="invitados", activo=True))
    inv = Invitacion(evento_id=evento.id, nombre="Invitada", email=" " + usuario.email.upper() + " ")
    db.add(inv); db.commit()
    headers = auth(usuario)
    def sitios():
        return {o["slug"]: o for o in client.get("/acceso/yo", headers=headers).json()["opciones"]}
    assert sitios()[evento.slug]["roles"] == ["Invitado"]
    assert client.get(f"/invitados/{evento.slug}/lista", headers=headers).status_code == 403
    inv.usuario_id = admin.id; db.commit()
    assert evento.slug not in sitios()  # El correo no sustituye una cuenta vinculada diferente.
    inv.usuario_id = usuario.id; db.commit()
    assert sitios()[evento.slug]["roles"] == ["Invitado"]
    inv.aprobacion = "REVOCADO"; db.commit()
    assert evento.slug not in sitios()
    inv.aprobacion = "PENDIENTE"; evento.estado = EventoEstado.BORRADOR; db.commit()
    assert evento.slug not in sitios()
