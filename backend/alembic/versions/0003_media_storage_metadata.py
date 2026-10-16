"""add media storage metadata

Revision ID: 0003_media_storage_metadata
Revises: 0002_template_keys
Create Date: 2026-10-05
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_media_storage_metadata"
down_revision: str | None = "0002_template_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE media_tipo ADD VALUE IF NOT EXISTS 'PORTADA'")
    op.execute("ALTER TYPE media_tipo ADD VALUE IF NOT EXISTS 'LOGO'")
    op.execute("ALTER TYPE media_tipo ADD VALUE IF NOT EXISTS 'GALERIA'")
    op.add_column("media", sa.Column("uuid", sa.Uuid(), nullable=True))
    op.add_column("media", sa.Column("uploaded_by", sa.Integer(), nullable=True))
    op.add_column("media", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("media", sa.Column("original_filename", sa.String(length=255), nullable=True))
    op.add_column("media", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("media", sa.Column("height", sa.Integer(), nullable=True))
    op.add_column("media", sa.Column("orden", sa.Integer(), nullable=False, server_default="0"))
    connection = op.get_bind()
    media_rows = connection.execute(sa.text("SELECT id FROM media WHERE uuid IS NULL")).fetchall()
    for row in media_rows:
        connection.execute(
            sa.text("UPDATE media SET uuid = :uuid WHERE id = :id"),
            {"uuid": str(uuid.uuid4()), "id": row.id},
        )
    op.alter_column("media", "uuid", nullable=False)
    op.create_index("ix_media_uuid", "media", ["uuid"], unique=True)
    op.create_foreign_key(
        "fk_media_uploaded_by_users",
        "media",
        "users",
        ["uploaded_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_media_uploaded_by_users", "media", type_="foreignkey")
    op.drop_index("ix_media_uuid", table_name="media")
    op.drop_column("media", "orden")
    op.drop_column("media", "height")
    op.drop_column("media", "width")
    op.drop_column("media", "original_filename")
    op.drop_column("media", "size_bytes")
    op.drop_column("media", "uploaded_by")
    op.drop_column("media", "uuid")
