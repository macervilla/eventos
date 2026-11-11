import pytest

from app.models.enums import RolEvento
from app.models.eventos import Evento, EventoUsuario
from app.models.proveedores import Proveedor
from app.services.agasajados import es_contacto_equipo
from tests.test_administracion import auth


@pytest.mark.parametrize("rol,permisos,visible,edita", [
    (RolEvento.PROPIETARIO, None, True, True),
    (RolEvento.PROPIETARIO, [], False, False),
    (RolEvento.ENCARGADO, None, True, True),
    (RolEvento.ENCARGADO, [], False, False),
    (RolEvento.ENCARGADO, ["ver_invitados"], False, False),
    (RolEvento.ADMIN_EVENTO, None, True, True),
    (RolEvento.ADMIN_EVENTO, [], False, False),
    (RolEvento.ADMIN_EVENTO, ["ver_invitados"], True, False),
    (RolEvento.AGASAJADO, None, True, False),
    (RolEvento.AGASAJADO, [], False, False),
    (RolEvento.AGASAJADO, ["configurar_evento"], False, False),
    (RolEvento.GESTOR_INVITADOS, ["editar_invitados"], True, False),
    (RolEvento.CONTROL_INGRESO, ["control_ingreso"], True, False),
    (RolEvento.CONTROL_INGRESO, ["editar_invitados"], False, False),
    (RolEvento.INVITADO, None, False, False),
    (RolEvento.DJ, None, False, False),
    (RolEvento.MODERADOR, None, False, False),
])
def test_sitios_reflejan_solo_asignaciones_efectivas(contexto, rol, permisos, visible, edita):
    client, db, admin, usuario, propio = contexto
    # El propietario de este evento es otra cuenta: el acceso requiere asignacion.
    evento = Evento(nombre="Asignado", slug="asignado", propietario_id=admin.id,
                    estado=propio.estado)
    db.add(evento)
    db.flush()
    db.add(EventoUsuario(evento_id=evento.id, usuario_id=usuario.id, rol=rol, permisos=permisos))
    db.commit()
    headers = auth(usuario)
    sitios = client.get("/acceso/yo", headers=headers).json()["opciones"]
    assert (evento.slug in {o["slug"] for o in sitios}) is visible
    assert propio.slug in {o["slug"] for o in sitios}
    respuesta = client.get(f"/eventos/{evento.slug}/permisos", headers=headers)
    assert respuesta.json()["puede_editar"] is edita
    assert es_contacto_equipo(db, evento, usuario.email) is visible
    invitados = client.get(f"/invitados/{evento.slug}/lista", headers=headers)
    if not visible:
        assert invitados.status_code == 403


def test_cuenta_sin_asignacion_no_hereda_eventos_ni_proveedores(contexto):
    client, db, admin, usuario, evento = contexto
    db.add(Proveedor(nombre_comercial="Propio", slug="propio", usuario_id=usuario.id,
                     email=usuario.email))
    db.add(Proveedor(nombre_comercial="Ajeno", slug="ajeno", usuario_id=admin.id,
                     email=admin.email))
    otro = Evento(nombre="Ajeno", slug="ajeno", propietario_id=admin.id, estado=evento.estado)
    db.add(otro)
    db.commit()
    headers = auth(usuario)
    sitios = client.get("/acceso/yo", headers=headers).json()["opciones"]
    assert {(o["tipo"], o["slug"]) for o in sitios} == {
        ("evento", evento.slug), ("proveedor", "propio")}
    assert client.get("/invitados/ajeno/lista", headers=headers).status_code == 403
    assert client.delete("/proveedores/ajeno", headers=headers).status_code == 403
    assert client.get("/administracion/resumen", headers=headers).status_code == 403


def test_revocacion_quita_sitio_y_edicion_sin_cambiar_sesion(contexto):
    client, db, admin, usuario, propio = contexto
    evento = Evento(nombre="Asignado", slug="asignado", propietario_id=admin.id,
                    estado=propio.estado)
    db.add(evento)
    db.flush()
    asignacion = EventoUsuario(evento_id=evento.id, usuario_id=usuario.id, rol=RolEvento.ENCARGADO)
    db.add(asignacion)
    db.commit()
    headers = auth(usuario)
    for vigente in (True, False):
        if not vigente:
            asignacion.permisos = []
            db.commit()
        sitios = client.get("/acceso/yo", headers=headers).json()["opciones"]
        assert ("asignado" in {o["slug"] for o in sitios}) is vigente
        assert client.get("/eventos/asignado/permisos", headers=headers).json()["puede_editar"] is vigente
