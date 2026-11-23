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
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.enums import EventoEstado, RolEvento
from app.models.eventos import Evento, EventoModulo, EventoUsuario
from app.models.solicitudes_invitacion import ContactoPublicoAgasajado, SolicitudInvitacion
from app.models.usuarios import User
from app.schemas.invitados import InvitadoDatos
from app.schemas.solicitudes_invitacion import DecisionSolicitud, SolicitudDatos
from app.services.invitados import guardar_invitado
from app.services.invitados_permisos import acceso
from app.services.solicitudes_invitacion import crear_solicitud, decidir


@pytest.fixture()
def pg_solicitudes():
    url = os.getenv("SOLICITUDES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Configurar SOLICITUDES_TEST_DATABASE_URL con PostgreSQL de pruebas")
    control = create_engine(url)
    schema = "test_solicitudes_" + uuid4().hex
    with control.begin() as con:
        con.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            owner, host, otro, visitante = [User(email=e) for e in ("owner@example.com", "host@example.com", "otro@example.com", "visita@example.com")]
            db.add_all([owner, host, otro, visitante]); db.flush()
            evento = Evento(nombre="Prueba", slug="prueba", propietario_id=owner.id, estado=EventoEstado.PUBLICADO)
            db.add(evento); db.flush()
            db.add(EventoModulo(evento_id=evento.id, modulo="invitados", activo=True, configuracion_json={}))
            for h in (host, otro):
                db.add(EventoUsuario(evento_id=evento.id, usuario_id=h.id, rol=RolEvento.AGASAJADO))
                db.add(ContactoPublicoAgasajado(evento_id=evento.id, agasajado_id=h.id, nombre_publico="Agasajado", habilitado=True))
            db.commit()
            ids = [u.id for u in (owner, host, otro, visitante)] + [evento.id]
        yield engine, ids
    finally:
        engine.dispose()
        with control.begin() as con:
            con.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        control.dispose()


def solicitar(engine, ids, host=None):
    with Session(engine) as db:
        usuario = db.get(User, ids[3]); usuario._email_google_sesion = usuario.email
        return crear_solicitud(db, "prueba", usuario, SolicitudDatos(nombre="Ana", apellido="Perez",
            agasajado_id=host or ids[1], canal="email", email=usuario.email))


def test_solicitudes_simultaneas_mismo_correo_distintos_agasajados(pg_solicitudes):
    engine, ids = pg_solicitudes
    barrera = Barrier(2)
    def crear(host):
        barrera.wait(timeout=10)
        return solicitar(engine, ids, host)
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(crear, (ids[1], ids[2])))
    assert resultados[0] == resultados[1]
    with engine.connect() as con:
        assert con.scalar(text("SELECT count(*) FROM solicitudes_invitacion")) == 1
        assert con.scalar(text("SELECT count(*) FROM auditoria_invitaciones WHERE accion='solicitud_invitacion_recibida'")) == 1
        assert con.scalar(text("SELECT count(*) FROM invitaciones")) == 0


def test_aprobaciones_simultaneas_una_invitacion_un_cupo(pg_solicitudes):
    engine, ids = pg_solicitudes
    solicitar(engine, ids)
    with engine.connect() as con:
        solicitud_id = con.scalar(text("SELECT id FROM solicitudes_invitacion"))
    barrera = Barrier(2)
    def aprobar(actor):
        with Session(engine) as db:
            usuario = db.get(User, actor)
            barrera.wait(timeout=10)
            return decidir(db, "prueba", usuario, solicitud_id, DecisionSolicitud(estado="APROBADA"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(aprobar, (ids[0], ids[1])))
    assert resultados[0]["invitacion_id"] == resultados[1]["invitacion_id"]
    with engine.connect() as con:
        assert con.scalar(text("SELECT count(*) FROM invitaciones")) == 1
        assert con.scalar(text("SELECT sum(cantidad_permitida) FROM invitaciones")) == 1
        assert con.scalar(text("SELECT count(*) FROM credenciales_invitacion")) == 0
        assert con.scalar(text("SELECT count(*) FROM auditoria_invitaciones WHERE accion='solicitud_invitacion_resuelta'")) == 1


def test_alta_administrativa_y_aprobacion_simultaneas_no_duplican(pg_solicitudes):
    engine, ids = pg_solicitudes
    solicitar(engine, ids)
    with engine.connect() as con:
        solicitud_id = con.scalar(text("SELECT id FROM solicitudes_invitacion"))
    barrera = Barrier(2)
    def operar(tipo):
        with Session(engine) as db:
            usuario = db.get(User, ids[0])
            barrera.wait(timeout=10)
            try:
                if tipo == "alta":
                    inv = guardar_invitado(db, acceso(db, "prueba", usuario, "editar_invitados"), InvitadoDatos(
                        nombre="Ana", apellido="Perez", email="visita@example.com", responsable_id=ids[1]))
                    db.commit()
                    return inv.id
                return decidir(db, "prueba", usuario, solicitud_id, DecisionSolicitud(estado="APROBADA", confirmar_revision=True))["invitacion_id"]
            except HTTPException as exc:
                db.rollback()
                assert tipo == "alta" and exc.status_code == 409
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(operar, ("alta", "aprobacion")))
    assert resultados[1] is not None
    if resultados[0] is not None:
        assert resultados[0] == resultados[1]
    with engine.connect() as con:
        assert con.scalar(text("SELECT count(*) FROM invitaciones")) == 1


def test_restriccion_unique_solicitudes_y_migracion_no_destructiva(pg_solicitudes):
    engine, ids = pg_solicitudes
    ruta = Path(__file__).resolve().parents[1] / "alembic/versions/0022_solicitudes_invitacion.py"
    spec = importlib.util.spec_from_file_location("migracion_solicitudes", ruta)
    migracion = importlib.util.module_from_spec(spec); spec.loader.exec_module(migracion)
    with engine.begin() as con, Operations.context(MigrationContext.configure(con)):
        migracion.downgrade(); migracion.upgrade()
        assert con.scalar(text("SELECT count(*) FROM users")) == 4
        assert con.scalar(text("SELECT nombre FROM eventos")) == "Prueba"
        assert con.scalar(text("SELECT count(*) FROM solicitudes_invitacion")) == 0
        migracion.downgrade(); migracion.upgrade()
        assert con.scalar(text("SELECT count(*) FROM evento_usuarios")) == 2
    # La base rechaza una identidad duplicada aunque se evite el servicio.
    with Session(engine) as db:
        for host in (ids[1], ids[2]):
            db.add(SolicitudInvitacion(evento_id=ids[4], usuario_id=ids[3], agasajado_id=host,
                nombre="Ana", apellido="Perez", nombre_normalizado="ana", apellido_normalizado="perez",
                email_verificado="visita@example.com", canal="email"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.scalar(select(func.count()).select_from(SolicitudInvitacion)) == 0
