from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.seguridad import crear_token_enlace
from tests.autenticacion import token_google
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.enums import EventoEstado
from app.models.eventos import Evento
from app.models.proveedores import Proveedor
from app.models.usuarios import User


@pytest.fixture()
def contexto():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        admin = User(email="admin@example.com", es_superadministrador=True)
        usuario = User(email="usuario@example.com")
        db.add_all([admin, usuario])
        db.flush()
        evento = Evento(nombre="Prueba", slug="prueba", propietario_id=usuario.id,
                        estado=EventoEstado.PUBLICADO,
                        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=1))
        db.add(evento)
        db.commit()
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            yield client, db, admin, usuario, evento
        app.dependency_overrides.clear()
    engine.dispose()


def auth(usuario):
    return {"Authorization": f"Bearer {token_google(usuario)}"}


def test_solo_superadministrador(contexto):
    client, _, admin, usuario, evento = contexto
    for ruta in ["resumen", "usuarios", "eventos"]:
        assert client.get(f"/administracion/{ruta}").status_code == 401
        assert client.get(f"/administracion/{ruta}", headers=auth(usuario)).status_code == 403
        assert client.get(f"/administracion/{ruta}", headers=auth(admin)).status_code == 200
    for ruta in [f"usuarios/{usuario.id}", f"eventos/{evento.id}"]:
        assert client.patch(f"/administracion/{ruta}", json={"activo": False}, headers=auth(usuario)).status_code == 403


def test_login_admin_sin_eventos(contexto):
    client, _, admin, _, _ = contexto
    respuesta = client.post("/acceso/enlace", json={"token": crear_token_enlace(admin.email)})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["token"]
    assert datos["opciones"] == [] and datos["requiere_google"]
    assert client.get("/administracion/resumen", headers={"Authorization": f"Bearer {datos['token']}"}).status_code == 401


def test_desactivar_y_reactivar_usuario_revoca_acceso(contexto):
    client, _, admin, usuario, _ = contexto
    sesion = auth(usuario)
    ruta = f"/administracion/usuarios/{usuario.id}"
    assert client.patch(ruta, json={"activo": False}, headers=auth(admin)).json()["activo"] is False
    assert client.get("/acceso/yo", headers=sesion).status_code == 401
    assert client.post("/acceso/enlace", json={"token": crear_token_enlace(usuario.email)}).json()["token"] is None
    assert client.patch(ruta, json={"activo": True}, headers=auth(admin)).json()["activo"] is True
    assert client.get("/acceso/yo", headers=sesion).status_code == 200
    assert client.patch(f"/administracion/usuarios/{admin.id}", json={"activo": False}, headers=auth(admin)).status_code == 409


def test_eventos_kpis_filtros_y_baja_logica(contexto):
    client, db, admin, usuario, evento = contexto
    cabeceras = auth(admin)
    kpis = client.get("/administracion/resumen", headers=cabeceras).json()
    assert kpis["usuarios_total"] == 2
    assert kpis["eventos_proximos"] == 1
    assert client.get("/administracion/usuarios?q=usuario&limit=1", headers=cabeceras).json()["total"] == 1
    assert client.get("/administracion/eventos?q=usuario", headers=cabeceras).json()["total"] == 1
    assert client.get("/administracion/eventos?offset=1", headers=cabeceras).json()["items"] == []
    ruta = f"/administracion/eventos/{evento.id}"
    assert client.patch(ruta, json={"activo": False}, headers=cabeceras).status_code == 200
    assert db.get(Evento, evento.id).deleted_at is not None
    assert client.get("/eventos/prueba").status_code == 404
    assert client.get("/administracion/resumen", headers=cabeceras).json()["eventos_proximos"] == 0
    assert client.patch(ruta, json={"activo": True}, headers=cabeceras).json()["estado"] == "PUBLICADO"
    assert db.get(Evento, evento.id).deleted_at is None
    assert client.get("/eventos/prueba", headers=auth(usuario)).status_code == 200


def test_ids_inexistentes_y_paginacion(contexto):
    client, _, admin, _, _ = contexto
    for tipo in ["usuarios", "eventos"]:
        assert client.patch(f"/administracion/{tipo}/999999", json={"activo": False}, headers=auth(admin)).status_code == 404
        assert client.get(f"/administracion/{tipo}?limit=101", headers=auth(admin)).status_code == 422


def test_editar_cuenta_conserva_propiedad_y_revoca_identidad_anterior(contexto):
    client, db, admin, usuario, evento = contexto
    usuario.google_subject = "identidad-anterior"
    proveedor = Proveedor(usuario_id=usuario.id, nombre_comercial="Salon", slug="salon", email=usuario.email)
    otro_contacto = Proveedor(usuario_id=usuario.id, nombre_comercial="Otro", slug="otro", email="contacto@example.com")
    db.add_all([proveedor, otro_contacto])
    db.commit()
    sesion_anterior = auth(usuario)
    enlace_anterior = crear_token_enlace(usuario.email)
    respuesta = client.put(f"/administracion/usuarios/{usuario.id}", headers=auth(admin),
                          json={"nombre": "  Nombre corregido  ", "email": "  CORREGIDO@example.com  "})
    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Nombre corregido"
    assert respuesta.json()["email"] == "corregido@example.com"
    assert usuario.google_subject is None
    assert proveedor.usuario_id == usuario.id
    assert proveedor.email == "corregido@example.com"
    assert otro_contacto.email == "contacto@example.com"
    assert evento.propietario_id == usuario.id
    assert client.get("/acceso/yo", headers=sesion_anterior).status_code == 401
    assert client.post("/acceso/enlace", json={"token": enlace_anterior}).json()["token"] is None


def test_editar_nombre_conserva_google_y_sesion(contexto):
    client, db, admin, usuario, _ = contexto
    usuario.google_subject = "google-vigente"
    db.commit()
    sesion = auth(usuario)
    respuesta = client.put(f"/administracion/usuarios/{usuario.id}", headers=auth(admin),
                          json={"nombre": "Nombre nuevo", "email": usuario.email})
    assert respuesta.status_code == 200
    assert usuario.google_subject == "google-vigente"
    assert client.get("/acceso/yo", headers=sesion).status_code == 200
    # Tambien puede editar los datos de una cuenta de superadministrador.
    assert client.put(f"/administracion/usuarios/{admin.id}", headers=auth(admin),
                      json={"nombre": "Admin", "email": admin.email}).status_code == 200


def test_editar_rechaza_datos_invalidos_y_roles(contexto):
    client, _, admin, usuario, _ = contexto
    ruta = f"/administracion/usuarios/{usuario.id}"
    for datos, status in [
        ({"nombre": "Invalido", "email": "no-es-email"}, 422),
        ({"nombre": "x" * 161, "email": usuario.email}, 422),
        ({"nombre": "Usuario", "email": usuario.email, "es_superadministrador": True}, 422),
    ]:
        assert client.put(ruta, json=datos, headers=auth(admin)).status_code == status
    assert usuario.email == "usuario@example.com"
    assert usuario.es_superadministrador is False
    assert client.put("/administracion/usuarios/999999", headers=auth(admin),
                      json={"nombre": None, "email": "nuevo@example.com"}).status_code == 404


def test_edicion_y_reenvio_exclusivos_de_superadministrador(contexto, monkeypatch):
    client, _, admin, usuario, _ = contexto
    envios = []
    monkeypatch.setattr("app.services.acceso.send_access_link_email", lambda *args: envios.append(args))
    for cabeceras, estado in [({}, 401), (auth(usuario), 403)]:
        assert client.put(f"/administracion/usuarios/{admin.id}", headers=cabeceras,
                          json={"nombre": "Otro", "email": "otro@example.com"}).status_code == estado
        assert client.post(f"/administracion/usuarios/{usuario.id}/reenviar-acceso", headers=cabeceras).status_code == estado
    assert not envios


def test_reenvia_al_correo_corregido_con_enlace_funcional(contexto, monkeypatch):
    client, _, admin, usuario, evento = contexto
    envios = []
    monkeypatch.setattr("app.services.acceso.send_access_link_email", lambda *args: envios.append(args))
    cabeceras = auth(admin)
    client.put(f"/administracion/usuarios/{usuario.id}", headers=cabeceras,
               json={"nombre": "Usuario", "email": "corregido@example.com"})
    respuesta = client.post(f"/administracion/usuarios/{usuario.id}/reenviar-acceso", headers=cabeceras)
    assert respuesta.status_code == 200
    assert "corregido@example.com" in respuesta.json()["message"]
    assert len(envios) == 1
    assert envios[0][0] == "corregido@example.com"
    assert "token" not in respuesta.json()
    acceso = client.post("/acceso/enlace", json={"token": envios[0][1]}).json()
    assert acceso["token"]
    assert acceso["opciones"] == [] and acceso["requiere_google"]
    assert client.get("/acceso/yo", headers={"Authorization": f"Bearer {acceso['token']}"}).status_code == 401


def test_reenvio_inactivo_inexistente_y_falla_smtp(contexto, monkeypatch):
    from fastapi import HTTPException

    client, db, admin, usuario, _ = contexto
    envios = []
    monkeypatch.setattr("app.services.acceso.send_access_link_email", lambda *args: envios.append(args))
    cabeceras = auth(admin)
    assert client.post("/administracion/usuarios/999999/reenviar-acceso", headers=cabeceras).status_code == 404
    usuario.activo = False
    db.commit()
    ruta = f"/administracion/usuarios/{usuario.id}/reenviar-acceso"
    assert client.post(ruta, headers=cabeceras).status_code == 409
    assert not envios
    usuario.activo = True
    db.commit()

    def falla_smtp(*args):
        raise HTTPException(503, "No se pudo enviar el correo mediante SMTP")

    monkeypatch.setattr("app.services.acceso.send_access_link_email", falla_smtp)
    respuesta = client.post(ruta, headers=cabeceras)
    assert respuesta.status_code == 503
    assert "SMTP" in respuesta.json()["detail"]


def test_email_duplicado_reenvio_y_sesion_no_cambian_de_cuenta(contexto, monkeypatch):
    client, _, admin, usuario, evento = contexto
    envios = []
    monkeypatch.setattr("app.services.acceso.send_access_link_email", lambda *args: envios.append(args))
    respuesta = client.put(f"/administracion/usuarios/{usuario.id}", headers=auth(admin),
                          json={"nombre": "Cuenta compartida", "email": admin.email.upper()})
    assert respuesta.status_code == 200
    assert usuario.email == admin.email
    assert client.post(f"/administracion/usuarios/{usuario.id}/reenviar-acceso", headers=auth(admin)).status_code == 200
    assert len(envios) == 1
    acceso = client.post("/acceso/enlace", json={"token": envios[0][1]}).json()
    assert acceso["opciones"] == [] and acceso["requiere_google"]
    cabeceras = {"Authorization": f"Bearer {acceso['token']}"}
    assert client.get("/administracion/usuarios", headers=cabeceras).status_code == 401
    assert client.get("/acceso/yo", headers=cabeceras).status_code == 401
    assert client.post("/acceso/enlace", json={"token": crear_token_enlace(admin.email)}).status_code == 409
    envios.clear()
    assert client.post("/acceso/solicitar-enlace", json={"email": admin.email}).status_code == 200
    assert len(envios) == 2
    accesos = [client.post("/acceso/enlace", json={"token": envio[1]}).json() for envio in envios]
    assert all(a["requiere_google"] and a["opciones"] == [] for a in accesos)


def test_google_duplicado_solo_admite_identidad_previamente_vinculada(contexto, monkeypatch):
    client, db, admin, usuario, _ = contexto
    usuario.email = admin.email
    admin.google_subject = "google-admin"
    db.commit()
    monkeypatch.setattr("app.services.acceso.get_verified_google_profile",
                        lambda credential: {"email": admin.email, "sub": credential})
    assert client.post("/acceso/google", json={"credential": "sin-vinculo"}).status_code == 403
    respuesta = client.post("/acceso/google", json={"credential": "google-admin"})
    assert respuesta.status_code == 200
    assert respuesta.json()["opciones"][0]["tipo"] == "administracion"


def test_enlace_dirigido_no_funciona_despues_de_cambiar_email(contexto):
    client, _, admin, usuario, _ = contexto
    anterior = crear_token_enlace(usuario.email, usuario.id)
    assert client.put(f"/administracion/usuarios/{usuario.id}", headers=auth(admin),
                      json={"nombre": None, "email": "corregido@example.com"}).status_code == 200
    assert client.post("/acceso/enlace", json={"token": anterior}).json()["token"] is None


def test_superadmin_lista_y_edita_negocios_ajenos(contexto):
    client, db, admin, owner, _ = contexto
    from app.models.proveedores import CategoriaProveedor, ProveedorCategoriaLink
    categoria = CategoriaProveedor(nombre="Salon", slug="salon")
    db.add(categoria); db.flush()
    negocio = Proveedor(usuario_id=owner.id, nombre_comercial="Salon ajeno", slug="salon-ajeno", provincia="Santa Cruz", localidad="Rio Gallegos", direccion="Calle 123", email=owner.email)
    negocio.categorias.append(ProveedorCategoriaLink(categoria_id=categoria.id))
    intruso = User(email="intruso@example.com")
    db.add_all([negocio, intruso]); db.commit()
    ruta = "/administracion/proveedores"
    assert client.get(ruta, headers=auth(owner)).status_code == 403
    lista = client.get(ruta, headers=auth(admin), params={"q": "Salon"})
    assert lista.status_code == 200, lista.text
    assert lista.json()["items"][0]["nombre"] == "Salon ajeno"
    encuadre = {"x": 40, "y": 60, "zoom": 1}
    ruta = "/proveedores/salon-ajeno/portada-encuadre"
    assert client.put(ruta, headers=auth(intruso), json=encuadre).status_code == 403
    respuesta = client.put(ruta, headers=auth(admin), json=encuadre)
    assert respuesta.status_code == 200, respuesta.text
    db.refresh(negocio)
    assert negocio.usuario_id == owner.id
    assert negocio.portada_encuadre["x"] == 40
