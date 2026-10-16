"""evento vinculado a un salon existente

Revision ID: 0004_evento_salon
Revises: 0003_media_storage_metadata
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_evento_salon"
down_revision: str | None = "0003_media_storage_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("eventos", sa.Column("salon_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_eventos_salon_id_proveedores",
        "eventos",
        "proveedores",
        ["salon_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_eventos_salon_id", "eventos", ["salon_id"])


def downgrade() -> None:
    op.drop_index("ix_eventos_salon_id", table_name="eventos")
    op.drop_constraint("fk_eventos_salon_id_proveedores", "eventos", type_="foreignkey")
    op.drop_column("eventos", "salon_id")
