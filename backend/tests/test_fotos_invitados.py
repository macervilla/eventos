import importlib.util
from io import BytesIO
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from PIL import Image
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.enums import RolEvento
from app.models.eventos import Evento, EventoUsuario
from app.models.invitaciones import FotoInvitado, Invitacion, MovimientoInvitacion
from app.models.usuarios import User
from app.services.media_storage import LocalMediaStorage
from tests.test_invitados import auth, crear, enlace, habilitar


def png():
    salida = BytesIO(); Image.new("RGB", (24, 32), "blue").save(salida, "PNG")
    return salida.getvalue()


@pytest.fixture()
def fotos(contexto, monkeypatch, tmp_path):
    client, db, admin, owner, evento = contexto
    habilitar(client, owner)
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    monkeypatch.setattr("app.services.fotos_invitados.media_storage", LocalMediaStorage(str(tmp_path)))
    return client, db, admin, owner, inv, token, tmp_path


def subir(client, token, contenido=None, nombre="imagen.png"):
    return client.post("/invitados/prueba/portal/fotos", data={"token": token},
                       files={"file": (nombre, contenido if contenido is not None else png(), "image/png")})


def test_limite_cuatro_y_contenido_privado_cifrado(fotos):
    client, db, _, owner, inv, token, root = fotos
    for _ in range(4):
        respuesta = subir(client, token, nombre="../../foto.png")
        assert respuesta.status_code == 200, respuesta.text
    assert subir(client, token).status_code == 409
    datos = client.post("/invitados/prueba/portal/fotos/listar", json={"token": token}).json()
    assert datos["limite"] == 4 and len(datos["fotos"]) == 4 and not datos["bloqueadas"]
    assert [f["slot"] for f in datos["fotos"]] == [1, 2, 3, 4]
    assert all(f["nombre"] == "foto.png" and "object_key" not in f for f in datos["fotos"])
    archivos = list(root.rglob("*.enc"))
    assert len(archivos) == 4 and all(not f.read_bytes().startswith(b"\x89PNG") for f in archivos)
    foto = datos["fotos"][0]
    r = client.post(f"/invitados/prueba/portal/fotos/{foto['id']}/imagen", json={"token": token})
    assert r.status_code == 200 and r.content.startswith(b"\x89PNG")
    assert r.headers["cache-control"] == "private, no-store"
    r = client.get(f"/invitados/prueba/lista/{inv['id']}/fotos/{foto['id']}/imagen", headers=auth(owner))
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


def test_quitar_reemplazar_conserva_historial_y_libera_cupo(fotos):
    client, db, _, _, inv, token, _ = fotos
    for _ in range(4):
        datos = subir(client, token).json()
    foto = datos["fotos"][1]
    ruta = f"/invitados/prueba/portal/fotos/{foto['id']}"
    r = client.post(ruta + "/quitar", json={"token": token})
    assert r.status_code == 200 and len(r.json()["fotos"]) == 3
    assert client.post(ruta + "/imagen", json={"token": token}).status_code == 404
    r = subir(client, token)
    assert r.status_code == 200 and len(r.json()["fotos"]) == 4
    assert foto["id"] not in {f["id"] for f in r.json()["fotos"]}
    vieja = db.get(FotoInvitado, foto["id"])
    assert not vieja.activo and vieja.deleted_at
    assert db.scalar(select(func.count()).select_from(FotoInvitado)) == 5


def test_confirmar_bloquea_modificaciones_y_desbloquear_las_habilita(fotos):
    client, db, admin, owner, inv, token, _ = fotos
    foto = subir(client, token).json()["fotos"][0]
    ruta = f"/invitados/prueba/lista/{inv['id']}/fotos/estado"
    assert client.put(ruta, headers=auth(owner), json={"bloqueadas": True}).status_code == 200
    assert subir(client, token).status_code == 409
    assert client.post(f"/invitados/prueba/portal/fotos/{foto['id']}/quitar", json={"token": token}).status_code == 409
    assert client.post(f"/invitados/prueba/portal/fotos/{foto['id']}/imagen", json={"token": token}).status_code == 200
    assert client.put(ruta, json={"bloqueadas": False}).status_code == 401
    # El superadministrador tambien puede desbloquear, sin alterar el RSVP ni el cupo.
    assert client.put(ruta, headers=auth(admin), json={"bloqueadas": False}).status_code == 200
    assert client.post(f"/invitados/prueba/portal/fotos/{foto['id']}/quitar", json={"token": token}).status_code == 200
    assert subir(client, token).status_code == 200
    invitacion = db.get(Invitacion, inv["id"])
    assert invitacion.rsvp == "PENDIENTE" and invitacion.cupo_aprobado == 0
    acciones = {a.accion for a in db.scalars(select(MovimientoInvitacion).where(MovimientoInvitacion.invitacion_id == inv["id"]))}
    assert {"fotos_invitado_confirmadas", "fotos_invitado_desbloqueadas", "foto_invitado_quitada"} <= acciones


def test_fotos_aisladas_por_invitacion_evento_y_rol(fotos):
    client, db, _, owner, inv, token, _ = fotos
    foto = subir(client, token).json()["fotos"][0]
    otro = crear(client, owner, nombre="Otro")
    token_otro = enlace(client, owner, otro)
    for operacion in ("imagen", "quitar"):
        assert client.post(f"/invitados/prueba/portal/fotos/{foto['id']}/{operacion}", json={"token": token_otro}).status_code == 404
    assert client.post("/invitados/otro/portal/fotos/listar", json={"token": token}).status_code == 404
    persona = User(email="agasajado@example.com"); db.add(persona); db.flush()
    db.add(EventoUsuario(evento_id=db.get(Invitacion, inv["id"]).evento_id, usuario_id=persona.id, rol=RolEvento.AGASAJADO)); db.commit()
    ruta = f"/invitados/prueba/lista/{inv['id']}/fotos"
    assert client.get(ruta, headers=auth(persona)).status_code == 403
    assert client.put(ruta + "/estado", headers=auth(persona), json={"bloqueadas": True}).status_code == 403
    assert client.get(f"/invitados/otro/lista/{inv['id']}/fotos", headers=auth(owner)).status_code == 404


def test_exige_acceso_personal_y_valida_archivos(fotos, monkeypatch):
    client, db, _, owner, inv, token, _ = fotos
    assert subir(client, token, b"no soy una imagen").status_code == 400
    with monkeypatch.context() as m:
        m.setattr(settings, "max_upload_bytes", 20)
        assert subir(client, token).status_code == 413
    assert db.scalar(select(func.count()).select_from(FotoInvitado)) == 0
    habilitar(client, owner, verificar_invitados=True, validacion="email")
    assert client.post("/invitados/prueba/portal/fotos/listar", json={"token": token}).status_code == 401
    assert subir(client, token).status_code == 401
    assert client.post("/invitados/prueba/portal/fotos/listar", json={"token": token, "bloqueadas": False}).status_code == 422


def test_no_confirma_conjunto_vacio_y_restricciones_de_slots(fotos):
    client, db, _, owner, inv, token, _ = fotos
    assert client.put(f"/invitados/prueba/lista/{inv['id']}/fotos/estado", headers=auth(owner), json={"bloqueadas": True}).status_code == 409
    subir(client, token)
    for slot in (1, 5):
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(FotoInvitado(invitacion_id=inv["id"], slot=slot, object_key="no-se-escribe",
                    nombre_archivo="foto.png", mime_type="image/png", size_bytes=1, activo=True))
                db.flush()


def test_migracion_fotos_conserva_invitaciones():
    ruta = Path(__file__).resolve().parents[1] / "alembic/versions/0019_fotos_invitados.py"
    spec = importlib.util.spec_from_file_location("migracion_0019", ruta)
    migracion = importlib.util.module_from_spec(spec); spec.loader.exec_module(migracion)
    engine = create_engine("sqlite://")
    with engine.begin() as con:
        con.execute(text("CREATE TABLE invitaciones (id INTEGER PRIMARY KEY, nombre VARCHAR(160))"))
        con.execute(text("INSERT INTO invitaciones VALUES (1,'Existente')"))
        with Operations.context(MigrationContext.configure(con)):
            migracion.upgrade()
            assert con.execute(text("SELECT nombre,fotos_bloqueadas FROM invitaciones")).one() == ("Existente", 0)
            con.execute(text("INSERT INTO fotos_invitado (invitacion_id,slot,object_key,nombre_archivo,mime_type,size_bytes) VALUES (1,1,'prueba.enc','foto.png','image/png',10)"))
            assert con.scalar(text("SELECT activo FROM fotos_invitado")) == 1
            migracion.downgrade()
            assert con.scalar(text("SELECT nombre FROM invitaciones")) == "Existente"
            migracion.upgrade()
            assert con.scalar(text("SELECT count(*) FROM invitaciones")) == 1
    engine.dispose()


def test_admin_quita_seleccionadas_bloqueadas_y_habilita_reemplazos(fotos):
    client, db, _, owner, inv, token, _ = fotos
    for _ in range(4):
        datos = subir(client, token).json()
    ids = [datos["fotos"][0]["id"], datos["fotos"][2]["id"]]
    base = f"/invitados/prueba/lista/{inv['id']}/fotos"
    client.put(base + "/estado", headers=auth(owner), json={"bloqueadas": True})
    assert client.post(base + "/quitar-seleccionadas", json={"ids": ids}).status_code == 401
    r = client.post(base + "/quitar-seleccionadas", headers=auth(owner), json={"ids": ids})
    assert r.status_code == 200, r.text
    assert not r.json()["bloqueadas"] and len(r.json()["fotos"]) == 2
    assert all(not db.get(FotoInvitado, foto_id).activo for foto_id in ids)
    for foto_id in ids:
        assert client.get(f"/invitados/prueba/album/{foto_id}/imagen", headers=auth(owner)).status_code == 404
    assert client.get("/invitados/prueba/album", headers=auth(owner)).json()["fotos"] == []
    client.put(base + "/estado", headers=auth(owner), json={"bloqueadas": True})
    assert len(client.get("/invitados/prueba/album", headers=auth(owner)).json()["fotos"]) == 2
    client.put(base + "/estado", headers=auth(owner), json={"bloqueadas": False})
    assert subir(client, token).status_code == 200
    assert len(subir(client, token).json()["fotos"]) == 4
    auditoria = db.scalar(select(MovimientoInvitacion).where(MovimientoInvitacion.accion == "fotos_invitado_quitadas_admin"))
    assert auditoria.actor_id == owner.id and auditoria.datos["fotos"] == ids


def test_baja_multiple_es_atomica_y_no_toca_fotos_ajenas(fotos):
    client, db, _, owner, inv, token, _ = fotos
    propia = subir(client, token).json()["fotos"][0]["id"]
    otra = crear(client, owner, nombre="Otra")
    ajena = subir(client, enlace(client, owner, otra)).json()["fotos"][0]["id"]
    base = f"/invitados/prueba/lista/{inv['id']}/fotos"
    client.put(base + "/estado", headers=auth(owner), json={"bloqueadas": True})
    assert client.post(base + "/quitar-seleccionadas", headers=auth(owner), json={"ids": [propia, ajena]}).status_code == 404
    assert db.get(FotoInvitado, propia).activo and db.get(FotoInvitado, ajena).activo
    assert db.get(Invitacion, inv["id"]).fotos_bloqueadas
    for ids in ([], [-1], [propia] * 5):
        assert client.post(base + "/quitar-seleccionadas", headers=auth(owner), json={"ids": ids}).status_code == 422


def test_album_aislado_por_evento_invitacion_activa_y_permisos(fotos):
    client, db, _, owner, inv, token, _ = fotos
    foto_id = subir(client, token).json()["fotos"][0]["id"]
    assert client.get("/invitados/prueba/album").status_code == 401
    assert client.get("/invitados/prueba/album", headers=auth(owner)).json()["fotos"] == []
    client.put(f"/invitados/prueba/lista/{inv['id']}/fotos/estado", headers=auth(owner), json={"bloqueadas": True})
    data = client.get("/invitados/prueba/album", headers=auth(owner)).json()
    assert data["evento"] == "Prueba" and [f["id"] for f in data["fotos"]] == [foto_id]
    assert "object_key" not in data["fotos"][0]
    imagen = client.get(f"/invitados/prueba/album/{foto_id}/imagen", headers=auth(owner))
    assert imagen.status_code == 200 and imagen.content.startswith(b"\x89PNG")
    otro_owner = User(email="otro-owner@example.com"); db.add(otro_owner); db.flush()
    otro = Evento(nombre="Otro evento", slug="otro", propietario_id=otro_owner.id)
    db.add(otro); db.commit()
    assert client.get("/invitados/otro/album", headers=auth(otro_owner)).json()["fotos"] == []
    assert client.get(f"/invitados/otro/album/{foto_id}/imagen", headers=auth(otro_owner)).status_code == 404
    assert client.get("/invitados/prueba/album", headers=auth(otro_owner)).status_code == 403
    db.add(EventoUsuario(evento_id=db.get(Invitacion, inv["id"]).evento_id, usuario_id=otro_owner.id, rol=RolEvento.AGASAJADO)); db.commit()
    assert client.get("/invitados/prueba/album", headers=auth(otro_owner)).status_code == 403
    assert client.post(f"/invitados/prueba/lista/{inv['id']}/fotos/quitar-seleccionadas",
                       headers=auth(otro_owner), json={"ids": [foto_id]}).status_code == 403
    db.get(Invitacion, inv["id"]).activo = False; db.commit()
    assert client.get("/invitados/prueba/album", headers=auth(owner)).json()["fotos"] == []
    assert client.get(f"/invitados/prueba/album/{foto_id}/imagen", headers=auth(owner)).status_code == 404


def test_album_invitado_solo_lectura_y_fotos_aprobadas(fotos):
    client, db, _, owner, inv, token, _ = fotos
    foto_id = subir(client, token).json()["fotos"][0]["id"]
    ruta = "/invitados/prueba/portal/album"
    assert client.post(ruta, json={"token": token}).json()["fotos"] == []
    assert client.post(ruta + f"/{foto_id}/imagen", json={"token": token}).status_code == 404
    client.put(f"/invitados/prueba/lista/{inv['id']}/fotos/estado", headers=auth(owner), json={"bloqueadas": True})
    otra = crear(client, owner, nombre="Espectadora")
    otro_token = enlace(client, owner, otra)
    assert client.post(ruta, json={"token": otro_token}).json()["fotos"][0]["id"] == foto_id
    assert client.post(ruta + f"/{foto_id}/imagen", json={"token": otro_token}).content.startswith(b"\x89PNG")
    assert client.post("/invitados/otro/portal/album", json={"token": otro_token}).status_code == 404
    assert client.put(f"/invitados/prueba/lista/{inv['id']}/fotos/estado", json={"bloqueadas": False}).status_code == 401
