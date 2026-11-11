import pytest
from sqlalchemy import func, select

from app.models.enums import RolEvento
from app.models.eventos import Evento, EventoUsuario
from app.models.invitaciones import MovimientoInvitacion
from app.models.proveedores import Proveedor
from app.models.usuarios import User
from tests.test_administracion import auth


@pytest.mark.parametrize("metodo", ["get", "put", "delete"])
def test_solo_superadministrador_gestiona_asignaciones(contexto, metodo):
    client, _, _, usuario, evento = contexto
    ruta = f"/administracion/eventos/{evento.id}/usuarios"
    if metodo != "get":
        ruta += f"/{usuario.id}"
    kwargs = {"json": {"rol": "AGASAJADO"}} if metodo == "put" else {}
    assert getattr(client, metodo)(ruta, **kwargs).status_code == 401
    assert getattr(client, metodo)(ruta, headers=auth(usuario), **kwargs).status_code == 403


def test_listado_incluye_propietario_sin_fila_y_acceso_global(contexto):
    client, _, admin, owner, evento = contexto
    respuesta = client.get(f"/administracion/eventos/{evento.id}/usuarios", headers=auth(admin))
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["propietario_id"] == owner.id
    cuentas = {u["id"]: u for u in datos["items"]}
    assert cuentas[owner.id]["es_propietario"] and cuentas[owner.id]["acceso_efectivo"]
    assert cuentas[admin.id]["es_superadministrador"] and cuentas[admin.id]["acceso_efectivo"]


def test_agregar_quitar_reactivar_aislado_con_sesion_abierta_y_auditoria(contexto):
    client, db, admin, owner, evento = contexto
    cuenta = User(email="equipo@example.com")
    db.add(cuenta); db.flush()
    otro = Evento(nombre="Otro", slug="otro", propietario_id=owner.id, estado=evento.estado)
    db.add(otro); db.flush()
    db.add(EventoUsuario(evento_id=otro.id, usuario_id=cuenta.id, rol=RolEvento.ADMIN_EVENTO))
    db.commit()
    headers = auth(cuenta)
    base = f"/administracion/eventos/{evento.id}/usuarios"
    ruta = f"{base}/{cuenta.id}"
    for _ in range(2):
        assert client.put(ruta, json={"rol": "ADMIN_EVENTO"}, headers=auth(admin)).status_code == 200
    assert client.get(f"/eventos/{evento.slug}/permisos", headers=headers).json()["puede_editar"]
    assert db.scalar(select(func.count()).select_from(EventoUsuario).where(
        EventoUsuario.evento_id == evento.id, EventoUsuario.usuario_id == cuenta.id)) == 1
    assert client.put(ruta, json={"rol": "AGASAJADO"}, headers=auth(admin)).status_code == 200
    respuesta = client.delete(ruta, headers=auth(admin))
    assert respuesta.status_code == 200
    assert cuenta.id not in {u["id"] for u in respuesta.json()["items"]}
    assert not client.get(f"/eventos/{evento.slug}/permisos", headers=headers).json()["puede_editar"]
    assert client.get(f"/invitados/{evento.slug}/lista", headers=headers).status_code == 403
    assert client.get("/eventos/otro/permisos", headers=headers).json()["puede_editar"]
    assert cuenta.activo
    filas = db.scalars(select(EventoUsuario).where(EventoUsuario.evento_id == evento.id,
                                                  EventoUsuario.usuario_id == cuenta.id)).all()
    assert len(filas) == 2 and all(a.permisos == [] for a in filas)
    assert client.put(ruta, json={"rol": "ADMIN_EVENTO"}, headers=auth(admin)).status_code == 200
    assert client.get(f"/eventos/{evento.slug}/permisos", headers=headers).json()["puede_editar"]
    auditoria = db.scalars(select(MovimientoInvitacion).where(
        MovimientoInvitacion.evento_id == evento.id)).all()
    assert any(a.accion == "admin_quitar_usuario" and a.actor_id == admin.id for a in auditoria)


def test_transferencia_retira_todos_roles_del_anterior_y_conserva_proveedor(contexto):
    client, db, admin, owner, evento = contexto
    nuevo = User(email="nuevo@example.com")
    db.add(nuevo); db.flush()
    db.add_all([EventoUsuario(evento_id=evento.id, usuario_id=owner.id, rol=rol)
                for rol in (RolEvento.PROPIETARIO, RolEvento.ADMIN_EVENTO, RolEvento.AGASAJADO)])
    db.add(Proveedor(nombre_comercial="Negocio", slug="negocio", email=owner.email, usuario_id=owner.id))
    db.commit()
    sesion_anterior = auth(owner)
    base = f"/administracion/eventos/{evento.id}/usuarios"
    assert client.delete(f"{base}/{owner.id}", headers=auth(admin)).status_code == 409
    respuesta = client.put(f"{base}/{nuevo.id}", json={"rol": "PROPIETARIO"}, headers=auth(admin))
    assert respuesta.status_code == 200
    assert evento.propietario_id == nuevo.id
    assert not client.get(f"/eventos/{evento.slug}/permisos", headers=sesion_anterior).json()["puede_editar"]
    assert client.get(f"/invitados/{evento.slug}/lista", headers=sesion_anterior).status_code == 403
    sitios = client.get("/acceso/yo", headers=sesion_anterior).json()["opciones"]
    assert {(o["tipo"], o["slug"]) for o in sitios} == {("proveedor", "negocio")}
    assert client.get(f"/eventos/{evento.slug}/permisos", headers=auth(nuevo)).json()["puede_editar"]
    # Volver a transferir reactiva la misma asignacion y conserva el historial.
    assert client.put(f"{base}/{owner.id}", json={"rol": "PROPIETARIO"}, headers=auth(admin)).status_code == 200
    assert evento.propietario_id == owner.id
    assert not client.get(f"/eventos/{evento.slug}/permisos", headers=auth(nuevo)).json()["puede_editar"]


def test_validaciones_y_superadministrador_conserva_acceso_global(contexto):
    client, db, admin, owner, evento = contexto
    base = f"/administracion/eventos/{evento.id}/usuarios"
    ruta = f"{base}/{admin.id}"
    headers = auth(admin)
    assert client.put(ruta, json={"rol": "INVITADO"}, headers=headers).status_code == 422
    assert client.put(ruta, json={"rol": "AGASAJADO", "es_superadministrador": True}, headers=headers).status_code == 422
    assert client.put(f"{base}/99999", json={"rol": "AGASAJADO"}, headers=headers).status_code == 404
    owner.activo = False; db.commit()
    assert client.put(f"{base}/{owner.id}", json={"rol": "AGASAJADO"}, headers=headers).status_code == 409
    assert client.get("/administracion/eventos/99999/usuarios", headers=headers).status_code == 404
    assert client.put(ruta, json={"rol": "ADMIN_EVENTO"}, headers=headers).status_code == 200
    respuesta = client.delete(ruta, headers=headers)
    assert respuesta.status_code == 200
    cuenta = next(u for u in respuesta.json()["items"] if u["id"] == admin.id)
    assert not cuenta["roles"] and cuenta["acceso_efectivo"]
