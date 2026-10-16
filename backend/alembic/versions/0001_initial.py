"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def soft_delete() -> list[sa.Column]:
    return [
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    evento_estado = sa.Enum("BORRADOR", "PUBLICADO", "EN_CURSO", "FINALIZADO", "ARCHIVADO", name="evento_estado")
    evento_privacidad = sa.Enum("PRIVADO", "CON_ENLACE", "PUBLICO", name="evento_privacidad")
    plan = sa.Enum("GRATIS", "PREMIUM", name="plan")
    proveedor_plan = sa.Enum("GRATIS", "PREMIUM", name="proveedor_plan")
    rol_evento = sa.Enum("PROPIETARIO", "ENCARGADO", "MODERADOR", "DJ", "INVITADO", name="rol_evento")
    estado_confirmacion = sa.Enum("PENDIENTE", "CONFIRMADO", "NO_ASISTE", name="estado_confirmacion")
    media_tipo = sa.Enum("FOTO", "VIDEO", name="media_tipo")
    media_estado = sa.Enum("PENDIENTE", "APROBADO", "RECHAZADO", "OCULTO", name="media_estado")
    location_origen = sa.Enum("GEOLOCATION", "MANUAL", "EVENTO", name="location_preference_origen")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("nombre", sa.String(160)),
        sa.Column("password_hash", sa.Text()),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "eventos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nombre", sa.String(180), nullable=False),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("descripcion", sa.Text()),
        sa.Column("tipo_evento", sa.String(80)),
        sa.Column("fecha_inicio", sa.DateTime(timezone=True)),
        sa.Column("fecha_fin", sa.DateTime(timezone=True)),
        sa.Column("localidad", sa.String(160)),
        sa.Column("provincia", sa.String(160)),
        sa.Column("pais", sa.String(80), nullable=False, server_default="Argentina"),
        sa.Column("direccion", sa.String(255)),
        sa.Column("latitud", sa.Float()),
        sa.Column("longitud", sa.Float()),
        sa.Column("portada_url", sa.Text()),
        sa.Column("propietario_id", sa.Integer(), nullable=False),
        sa.Column("privacidad", evento_privacidad, nullable=False, server_default="PRIVADO"),
        sa.Column("estado", evento_estado, nullable=False, server_default="BORRADOR"),
        sa.Column("plan", plan, nullable=False, server_default="GRATIS"),
        sa.Column("permite_publicidad", sa.Boolean(), nullable=False, server_default=sa.true()),
        *soft_delete(),
        *timestamps(),
        sa.ForeignKeyConstraint(["propietario_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_eventos_uuid", "eventos", ["uuid"], unique=True)
    op.create_index("ix_eventos_slug", "eventos", ["slug"], unique=True)
    op.create_index("ix_eventos_activo", "eventos", ["activo"])
    op.create_index("ix_eventos_localidad", "eventos", ["localidad"])
    op.create_index("ix_eventos_provincia", "eventos", ["provincia"])
    op.create_index("ix_eventos_tipo_evento", "eventos", ["tipo_evento"])

    op.create_table(
        "categorias_proveedor",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False),
        *soft_delete(),
        *timestamps(),
        sa.UniqueConstraint("nombre", name="uq_categorias_proveedor_nombre"),
    )
    op.create_index("ix_categorias_proveedor_slug", "categorias_proveedor", ["slug"], unique=True)
    op.create_index("ix_categorias_proveedor_activo", "categorias_proveedor", ["activo"])

    op.create_table(
        "proveedores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("nombre_comercial", sa.String(180), nullable=False),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("cuit", sa.String(20)),
        sa.Column("descripcion", sa.Text()),
        sa.Column("pais", sa.String(80), nullable=False, server_default="Argentina"),
        sa.Column("localidad", sa.String(160)),
        sa.Column("provincia", sa.String(160)),
        sa.Column("direccion", sa.String(255)),
        sa.Column("google_maps_url", sa.Text()),
        sa.Column("google_place_id", sa.String(255)),
        sa.Column("ubicacion_referencia", sa.String(255)),
        sa.Column("latitud", sa.Float()),
        sa.Column("longitud", sa.Float()),
        sa.Column("whatsapp", sa.String(60)),
        sa.Column("telefono", sa.String(60)),
        sa.Column("email", sa.String(255)),
        sa.Column("web", sa.Text()),
        sa.Column("instagram", sa.String(160)),
        sa.Column("facebook", sa.String(160)),
        sa.Column("logo_url", sa.Text()),
        sa.Column("portada_url", sa.Text()),
        sa.Column("horarios", sa.Text()),
        sa.Column("plan", proveedor_plan, nullable=False, server_default="GRATIS"),
        *soft_delete(),
        *timestamps(),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_proveedores_uuid", "proveedores", ["uuid"], unique=True)
    op.create_index("ix_proveedores_slug", "proveedores", ["slug"], unique=True)
    for column in ["usuario_id", "nombre_comercial", "cuit", "localidad", "provincia", "latitud", "longitud", "activo"]:
        op.create_index(f"ix_proveedores_{column}", "proveedores", [column])

    op.create_table(
        "proveedor_categorias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proveedor_id", sa.Integer(), nullable=False),
        sa.Column("categoria_id", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["categoria_id"], ["categorias_proveedor.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("proveedor_id", "categoria_id", name="uq_proveedor_categoria"),
    )
    op.create_index("ix_proveedor_categorias_activo", "proveedor_categorias", ["activo"])

    op.create_table(
        "proveedor_dominios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proveedor_id", sa.Integer(), nullable=False),
        sa.Column("dominio", sa.String(255), nullable=False),
        sa.Column("verificado", sa.Boolean(), nullable=False, server_default=sa.false()),
        *soft_delete(),
        *timestamps(),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_proveedor_dominios_dominio", "proveedor_dominios", ["dominio"], unique=True)
    op.create_index("ix_proveedor_dominios_activo", "proveedor_dominios", ["activo"])

    op.create_table(
        "user_location_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("localidad", sa.String(160)),
        sa.Column("provincia", sa.String(160)),
        sa.Column("pais", sa.String(80), nullable=False, server_default="Argentina"),
        sa.Column("latitud", sa.Float()),
        sa.Column("longitud", sa.Float()),
        sa.Column("origen", location_origen, nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "evento_modulos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("modulo", sa.String(80), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("configuracion_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        *timestamps(),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("evento_id", "modulo", name="uq_evento_modulo"),
    )

    op.create_table(
        "evento_usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("rol", rol_evento, nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("evento_id", "usuario_id", "rol", name="uq_evento_usuario_rol"),
    )

    op.create_table(
        "invitaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer()),
        sa.Column("estado_confirmacion", estado_confirmacion, nullable=False, server_default="PENDIENTE"),
        sa.Column("cantidad_permitida", sa.Integer(), nullable=False, server_default="1"),
        *timestamps(),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "participantes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invitacion_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(160), nullable=False),
        sa.Column("tipo", sa.String(80)),
        sa.Column("edad_opcional", sa.Integer()),
        sa.Column("menu", sa.String(120)),
        sa.Column("bebida", sa.String(120)),
        sa.Column("observaciones", sa.Text()),
        *timestamps(),
        sa.ForeignKeyConstraint(["invitacion_id"], ["invitaciones.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "opciones_evento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(80), nullable=False),
        sa.Column("valor", sa.String(160), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("evento_id", "tipo", "valor", name="uq_opcion_evento"),
    )

    op.create_table(
        "temas_musicales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer()),
        sa.Column("artista", sa.String(160), nullable=False),
        sa.Column("titulo", sa.String(180), nullable=False),
        sa.Column("votos", sa.Integer(), nullable=False, server_default="0"),
        *timestamps(),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento_id", sa.Integer()),
        sa.Column("proveedor_id", sa.Integer()),
        sa.Column("usuario_id", sa.Integer()),
        sa.Column("tipo", media_tipo, nullable=False),
        sa.Column("storage_provider", sa.String(80), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text()),
        sa.Column("tamano", sa.BigInteger()),
        sa.Column("mime_type", sa.String(120)),
        sa.Column("estado", media_estado, nullable=False, server_default="PENDIENTE"),
        *soft_delete(),
        *timestamps(),
        sa.CheckConstraint(
            "(evento_id IS NOT NULL AND proveedor_id IS NULL) OR "
            "(evento_id IS NULL AND proveedor_id IS NOT NULL)",
            name="ck_media_single_owner",
        ),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_media_activo", "media", ["activo"])

    op.create_table(
        "publicaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer()),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(40), nullable=False, server_default="VISIBLE"),
        *soft_delete(),
        *timestamps(),
        sa.ForeignKeyConstraint(["evento_id"], ["eventos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_publicaciones_activo", "publicaciones", ["activo"])


def downgrade() -> None:
    for table in [
        "publicaciones",
        "media",
        "temas_musicales",
        "opciones_evento",
        "participantes",
        "invitaciones",
        "evento_usuarios",
        "evento_modulos",
        "user_location_preferences",
        "proveedor_dominios",
        "proveedor_categorias",
        "proveedores",
        "categorias_proveedor",
        "eventos",
        "users",
    ]:
        op.drop_table(table)

    for enum_name in [
        "location_preference_origen",
        "media_estado",
        "media_tipo",
        "estado_confirmacion",
        "rol_evento",
        "proveedor_plan",
        "plan",
        "evento_privacidad",
        "evento_estado",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
