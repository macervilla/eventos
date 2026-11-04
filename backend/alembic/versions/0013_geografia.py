"""Catalogo GeoNames y referencias opcionales, sin alterar datos existentes."""
from alembic import op
import sqlalchemy as sa

revision = "0013_geografia"
down_revision = "0012_email_compartido"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout='5s'")
    # La extension no descarga ni consulta datos externos.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table("geo_paises", sa.Column("codigo_iso", sa.String(2), primary_key=True),
                    sa.Column("nombre", sa.String(200), nullable=False),
                    sa.Column("nombre_normalizado", sa.String(400), nullable=False))
    op.create_table("geo_provincias", sa.Column("id", sa.String(100), primary_key=True),
                    sa.Column("codigo_pais", sa.String(2), sa.ForeignKey("geo_paises.codigo_iso"), nullable=False),
                    sa.Column("codigo_administrativo", sa.String(80), nullable=False),
                    sa.Column("nombre", sa.String(200), nullable=False),
                    sa.Column("nombre_normalizado", sa.String(400), nullable=False))
    op.create_table("geo_subdivisiones", sa.Column("id", sa.String(190), primary_key=True),
                    sa.Column("codigo_pais", sa.String(2), sa.ForeignKey("geo_paises.codigo_iso"), nullable=False),
                    sa.Column("provincia_id", sa.String(100), sa.ForeignKey("geo_provincias.id")),
                    sa.Column("codigo_administrativo", sa.String(80), nullable=False),
                    sa.Column("nombre", sa.String(200), nullable=False))
    op.create_table("geo_localidades", sa.Column("geoname_id", sa.BigInteger(), primary_key=True, autoincrement=False),
                    sa.Column("nombre", sa.String(200), nullable=False),
                    sa.Column("nombre_ascii", sa.String(200), nullable=False),
                    sa.Column("nombre_normalizado", sa.String(400), nullable=False),
                    sa.Column("codigo_pais", sa.String(2), sa.ForeignKey("geo_paises.codigo_iso"), nullable=False),
                    sa.Column("codigo_provincia", sa.String(80), nullable=False),
                    sa.Column("codigo_subdivision", sa.String(80)),
                    sa.Column("provincia_id", sa.String(100), sa.ForeignKey("geo_provincias.id")),
                    sa.Column("subdivision_id", sa.String(190), sa.ForeignKey("geo_subdivisiones.id")),
                    sa.Column("latitud", sa.Float(), nullable=False), sa.Column("longitud", sa.Float(), nullable=False),
                    sa.Column("poblacion", sa.BigInteger(), nullable=False),
                    sa.Column("feature_code", sa.String(20), nullable=False),
                    sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("geo_nombres",
                    sa.Column("geoname_id", sa.BigInteger(), sa.ForeignKey("geo_localidades.geoname_id"), primary_key=True),
                    sa.Column("nombre_normalizado", sa.String(400), primary_key=True))
    op.create_index("ix_geo_nombres_prefijo", "geo_nombres", ["nombre_normalizado"],
                    postgresql_ops={"nombre_normalizado": "varchar_pattern_ops"})
    op.create_index("ix_geo_nombres_trgm", "geo_nombres", ["nombre_normalizado"],
                    postgresql_using="gin", postgresql_ops={"nombre_normalizado": "gin_trgm_ops"})
    op.create_table("geo_importaciones", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("iniciada", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("finalizada", sa.DateTime(timezone=True)),
                    sa.Column("estado", sa.String(20), nullable=False),
                    sa.Column("version", sa.String(40), nullable=False),
                    sa.Column("fuentes", sa.JSON(), nullable=False),
                    sa.Column("cantidades", sa.JSON()), sa.Column("error", sa.String(500)))
    for tabla in ("eventos", "proveedores", "user_location_preferences"):
        op.add_column(tabla, sa.Column("geoname_id", sa.BigInteger(), nullable=True))
        op.add_column(tabla, sa.Column("codigo_pais", sa.String(2), nullable=True))
        op.create_foreign_key(f"fk_{tabla}_geonames", tabla, "geo_localidades", ["geoname_id"], ["geoname_id"], ondelete="RESTRICT")


def downgrade():
    # Evitar borrar accidentalmente referencias/catalogos ya usados en produccion.
    raise RuntimeError("Reversion geografica destructiva deshabilitada. Restaurar un respaldo verificado si es necesario.")
