"""Prueba con conexiones concurrentes reales, en un esquema aislado y descartable."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.eventos import Evento, EventoModulo
from app.models.invitaciones import Invitacion, MovimientoIngreso
from app.models.usuarios import User
from app.schemas.invitados import RegistrarIngreso
from app.services.invitados import emitir, registrar_ingreso
from app.services.invitados_permisos import acceso


def test_concurrencia_e_idempotencia_en_postgres():
    if not settings.database_url.startswith("postgresql"):
        pytest.skip("Requiere PostgreSQL para comprobar bloqueos de filas")
    schema = "test_invitados_" + uuid.uuid4().hex
    admin = create_engine(settings.database_url)
    with admin.begin() as con:
        con.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        settings.database_url, connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            owner = User(email="owner@example.com")
            db.add(owner)
            db.flush()
            evento = Evento(
                nombre="Prueba concurrente", slug="concurrencia", propietario_id=owner.id
            )
            db.add(evento)
            db.flush()
            db.add(
                EventoModulo(
                    evento_id=evento.id, modulo="invitados", activo=True, configuracion_json={}
                )
            )
            invitaciones = []
            for n in range(2):
                inv = Invitacion(
                    evento_id=evento.id,
                    nombre=f"Grupo {n}",
                    cantidad_permitida=4,
                    adultos=4,
                    menores=0,
                    cupo_aprobado=4,
                    aprobacion="APROBADO",
                    rsvp="CONFIRMADO",
                )
                db.add(inv)
                db.flush()
                invitaciones.append((inv.id, emitir(db, inv, "qr")))
            db.commit()
            owner_id = owner.id

        def competir(token, cantidad, misma_clave=False):
            barrera = Barrier(2)
            key = uuid.uuid4().hex

            def trabajo(n):
                with Session(engine) as db:
                    usuario = db.get(User, owner_id)
                    ctx = acceso(db, "concurrencia", usuario, "control_ingreso")
                    barrera.wait(timeout=10)
                    try:
                        registrar_ingreso(
                            db,
                            ctx,
                            RegistrarIngreso(
                                token=token,
                                cantidad=cantidad,
                                idempotencia=key if misma_clave else key + str(n),
                            ),
                        )
                        return 200
                    except HTTPException as exc:
                        db.rollback()
                        return exc.status_code

            with ThreadPoolExecutor(max_workers=2) as pool:
                return sorted(pool.map(trabajo, [0, 1]))

        assert competir(invitaciones[0][1], 3) == [200, 409]
        assert competir(invitaciones[1][1], 2, True) == [200, 200]
        with Session(engine) as db:
            assert db.get(Invitacion, invitaciones[0][0]).ingresados == 3
            assert db.get(Invitacion, invitaciones[1][0]).ingresados == 2
            assert db.scalar(select(func.count()).select_from(MovimientoIngreso)) == 2
    finally:
        engine.dispose()
        assert schema.startswith("test_invitados_") and len(schema) == len("test_invitados_") + 32
        with admin.begin() as con:
            con.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
