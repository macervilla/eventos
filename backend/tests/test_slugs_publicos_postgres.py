"""Pruebas reales de triggers, migracion y concurrencia en schema aislado."""
import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.eventos import Evento
from app.models.proveedores import Proveedor
from app.models.usuarios import User


def migracion():
    ruta = Path(__file__).resolve().parents[1] / "alembic/versions/0021_slugs_publicos.py"
    spec = importlib.util.spec_from_file_location("migracion_slugs", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture()
def pg_slugs():
    url = os.getenv("SLUG_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Configurar SLUG_TEST_DATABASE_URL con PostgreSQL de pruebas")
    control = create_engine(url)
    schema = "test_slugs_" + uuid4().hex
    with control.begin() as con:
        con.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as con:
            con.execute(text("DROP TABLE slugs_publicos"))
        with Session(engine) as db:
            usuario = User(email="conservar@example.com")
            db.add(usuario); db.commit()
            usuario_id = usuario.id
        yield engine, usuario_id
    finally:
        engine.dispose()
        with control.begin() as con:
            con.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        control.dispose()


def aplicar(engine):
    with engine.begin() as con, Operations.context(MigrationContext.configure(con)):
        migracion().upgrade()


def test_backfill_reversion_y_proteccion_sql(pg_slugs):
    engine, usuario_id = pg_slugs
    with Session(engine) as db:
        db.add(Evento(nombre="Conservar", slug="evento", propietario_id=usuario_id))
        db.add(Proveedor(nombre_comercial="Conservar", slug="salon", usuario_id=usuario_id))
        db.commit()
    aplicar(engine)
    with engine.begin() as con:
        assert con.execute(text("SELECT slug, tipo FROM slugs_publicos ORDER BY slug")).all() == [
            ("evento", "evento"), ("salon", "proveedor")]
        assert con.scalar(text("SELECT nombre FROM eventos")) == "Conservar"
        assert con.scalar(text("SELECT email FROM users")) == "conservar@example.com"
        with Operations.context(MigrationContext.configure(con)):
            migracion().downgrade(); migracion().upgrade()
    for sql in ("UPDATE eventos SET slug='otro'", "UPDATE proveedores SET slug='otro'",
                "UPDATE eventos SET nombre='Otro'"):
        with pytest.raises(IntegrityError), engine.begin() as con:
            con.execute(text(sql))
    with Session(engine) as db:
        db.add(Proveedor(nombre_comercial="Reservado", slug="api", usuario_id=usuario_id))
        with pytest.raises(IntegrityError):
            db.commit()
    with engine.begin() as con:
        con.execute(text("UPDATE proveedores SET activo=false"))
        assert con.scalar(text("SELECT count(*) FROM slugs_publicos")) == 2


@pytest.mark.parametrize("slug", ["duplicado", "admin"])
def test_conflictos_detienen_migracion_sin_cambiar_datos(pg_slugs, slug):
    engine, usuario_id = pg_slugs
    with Session(engine) as db:
        db.add(Evento(nombre="Original", slug=slug, propietario_id=usuario_id))
        db.add(Proveedor(nombre_comercial="Original", slug=slug, usuario_id=usuario_id))
        db.commit()
    with pytest.raises(RuntimeError, match=slug):
        aplicar(engine)
    with engine.connect() as con:
        assert con.scalar(text("SELECT to_regclass('slugs_publicos')")) is None
        assert con.scalar(text("SELECT slug FROM eventos")) == slug
        assert con.scalar(text("SELECT slug FROM proveedores")) == slug


@pytest.mark.parametrize("tipos", [("evento", "proveedor"), ("evento", "evento"), ("proveedor", "proveedor")])
def test_concurrencia_solo_una_alta(pg_slugs, tipos):
    engine, usuario_id = pg_slugs
    aplicar(engine)
    barrera = Barrier(2)
    def crear(tipo):
        with Session(engine) as db:
            barrera.wait(timeout=10)
            entidad = (Evento(nombre="Concurrente", slug="concurrente", propietario_id=usuario_id)
                       if tipo == "evento" else Proveedor(nombre_comercial="Concurrente", slug="concurrente", usuario_id=usuario_id))
            db.add(entidad)
            try:
                db.commit()
                return 201
            except IntegrityError:
                db.rollback()
                return 409
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(crear, tipos)) == [201, 409]
    with engine.connect() as con:
        assert con.scalar(text("SELECT count(*) FROM slugs_publicos")) == 1
        assert con.scalar(text("SELECT (SELECT count(*) FROM eventos) + (SELECT count(*) FROM proveedores)")) == 1
