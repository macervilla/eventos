import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.enums import EventoEstado
from app.models.eventos import Evento
from app.models.invitaciones import Invitacion
from app.models.usuarios import User
from app.models.video import CamaraVideo, TransmisionEvento
from app.services import video


@pytest.fixture()
def pg_video(monkeypatch):
    url = os.getenv("VIDEO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Configurar VIDEO_TEST_DATABASE_URL con PostgreSQL de pruebas")
    control = create_engine(url)
    schema = "test_video_" + uuid4().hex
    with control.begin() as con:
        con.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        monkeypatch.setattr(settings, "video_enabled", True)
        monkeypatch.setattr(settings, "mediamtx_auth_secret", SecretStr("prueba-aislada"))
        monkeypatch.setattr(video.mediamtx, "path", lambda _: None)
        monkeypatch.setattr(video.mediamtx, "sessions", lambda: [])
        yield engine
    finally:
        engine.dispose()
        with control.begin() as con:
            con.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        control.dispose()


def test_reservas_concurrentes_solo_una_gana(pg_video):
    with Session(pg_video) as db:
        user = User(email="owner@example.com"); db.add(user); db.flush()
        evento = Evento(nombre="Concurrencia", slug="video", propietario_id=user.id, estado=EventoEstado.PUBLICADO)
        db.add(evento); db.flush()
        inv = Invitacion(evento_id=evento.id, nombre="Camara")
        db.add(inv); db.flush()
        db.add(CamaraVideo(evento_id=evento.id, invitacion_id=inv.id, version=uuid4().hex, estado="autorizado"))
        db.commit(); evento_id, inv_id = evento.id, inv.id
    barrera = Barrier(2)
    def reservar(_):
        with Session(pg_video) as db:
            identidad = video.IdentidadVideo(db.get(Evento, evento_id), invitacion_id=inv_id)
            barrera.wait(timeout=10)
            try:
                video.credencial(db, identidad, publicar=True)
                return 200
            except HTTPException as exc:
                db.rollback(); return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reservar, range(2))) == [200, 409]


def test_migracion_video_postgres_conserva_datos_y_reversion(pg_video):
    ruta = Path(__file__).resolve().parents[1] / "alembic/versions/0020_video_en_vivo.py"
    spec = importlib.util.spec_from_file_location("migracion_0020", ruta)
    migracion = importlib.util.module_from_spec(spec); spec.loader.exec_module(migracion)
    with pg_video.begin() as con:
        con.execute(text("INSERT INTO users (email,activo,es_superadministrador) VALUES ('conservar@example.com',true,false)"))
        with Operations.context(MigrationContext.configure(con)):
            migracion.downgrade(); migracion.upgrade()
            assert con.scalar(text("SELECT email FROM users")) == "conservar@example.com"
            assert con.scalar(text("SELECT count(*) FROM transmisiones_evento")) == 0
            migracion.downgrade(); migracion.upgrade()
            assert con.scalar(text("SELECT count(*) FROM users")) == 1


@pytest.mark.parametrize("limite", [1, 4])
def test_tope_global_concurrente_entre_eventos(pg_video, monkeypatch, limite):
    monkeypatch.setattr(settings, "video_max_transmisiones", limite)
    identidades = []
    with Session(pg_video) as db:
        user = User(email="capacidad@example.com"); db.add(user); db.flush()
        for n in range(limite + 1):
            evento = Evento(nombre="Capacidad", slug=f"capacidad-{n}", propietario_id=user.id, estado=EventoEstado.PUBLICADO)
            db.add(evento); db.flush()
            inv = Invitacion(evento_id=evento.id, nombre="Camara")
            db.add(inv); db.flush()
            db.add(CamaraVideo(evento_id=evento.id, invitacion_id=inv.id, estado="autorizado"))
            identidades.append((evento.id, inv.id))
        db.commit()
    barrera = Barrier(limite + 1)
    def reservar(ids):
        with Session(pg_video) as db:
            identidad = video.IdentidadVideo(db.get(Evento, ids[0]), invitacion_id=ids[1])
            barrera.wait(timeout=10)
            try:
                video.credencial(db, identidad, publicar=True)
                return 200
            except HTTPException as exc:
                db.rollback(); return exc.status_code
    with ThreadPoolExecutor(max_workers=limite + 1) as pool:
        assert sorted(pool.map(reservar, identidades)) == [200] * limite + [409]


def test_migracion_multicamara_conserva_seleccion_y_generacion(pg_video):
    ruta = Path(__file__).resolve().parents[1] / "alembic/versions/0023_camaras_video.py"
    spec = importlib.util.spec_from_file_location("migracion_0023", ruta)
    migracion = importlib.util.module_from_spec(spec); spec.loader.exec_module(migracion)
    with Session(pg_video) as db:
        user = User(email="migracion-camara@example.com"); db.add(user); db.flush()
        evento = Evento(nombre="Conservar", slug="conservar", propietario_id=user.id, estado=EventoEstado.PUBLICADO)
        db.add(evento); db.flush()
        inv = Invitacion(evento_id=evento.id, nombre="Camara", cantidad_permitida=3)
        db.add(inv); db.flush()
        version = uuid4().hex
        db.add(TransmisionEvento(evento_id=evento.id, invitacion_id=inv.id, version=version, estado="autorizado"))
        db.commit(); ids = evento.id, inv.id
    with pg_video.begin() as con:
        con.execute(text("DROP TABLE camaras_video"))
        with Operations.context(MigrationContext.configure(con)):
            migracion.upgrade()
            assert con.scalar(text("SELECT version FROM camaras_video")) == version
            assert con.scalar(text("SELECT invitacion_id FROM transmisiones_evento")) == ids[1]
            assert con.scalar(text("SELECT cantidad_permitida FROM invitaciones")) == 3
            migracion.downgrade(); migracion.upgrade()
            assert con.scalar(text("SELECT count(*) FROM camaras_video")) == 0
            assert con.scalar(text("SELECT count(*) FROM invitaciones")) == 1
