"""Verifica upgrade/downgrade en PostgreSQL y revierte TODO, sin cambiar la version."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from app.db.session import engine


def main():
    assert engine.dialect.name == "postgresql"
    ruta = Path(__file__).resolve().parents[1] / "alembic/versions/0017_verificacion_invitados.py"
    spec = importlib.util.spec_from_file_location("migracion_0017", ruta)
    migracion = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migracion)
    with engine.connect() as conn:
        transaccion = conn.begin()
        try:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0016_textos_proveedor"
            tablas = ("users", "eventos", "evento_usuarios", "invitaciones", "validaciones_invitado")
            antes = {t: conn.scalar(text(f"SELECT count(*) FROM {t}")) for t in tablas}
            contexto = MigrationContext.configure(conn)
            with Operations.context(contexto):
                migracion.upgrade()
                assert "pin_personal_hash" in {c["name"] for c in inspect(conn).get_columns("invitaciones")}
                assert {"metodo", "proveedor_referencia"} <= {c["name"] for c in inspect(conn).get_columns("validaciones_invitado")}
                assert conn.scalar(text("SELECT count(*) FROM validaciones_invitado WHERE metodo != 'email' OR metodo IS NULL")) == 0
                assert antes == {t: conn.scalar(text(f"SELECT count(*) FROM {t}")) for t in tablas}
                migracion.downgrade()
                assert "pin_personal_hash" not in {c["name"] for c in inspect(conn).get_columns("invitaciones")}
                migracion.upgrade()
                assert antes == {t: conn.scalar(text(f"SELECT count(*) FROM {t}")) for t in tablas}
            print("OK: upgrade, downgrade y nuevo upgrade; filas conservadas. Se revierte toda la transaccion.")
        finally:
            transaccion.rollback()
    with engine.connect() as conn:
        assert "pin_personal_hash" not in {c["name"] for c in inspect(conn).get_columns("invitaciones")}
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0016_textos_proveedor"
    print("OK: esquema y version originales intactos despues de la prueba.")


if __name__ == "__main__":
    main()
