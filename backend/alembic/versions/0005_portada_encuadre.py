"""encuadre de la portada (punto de foco y modo) para proveedores y eventos

Revision ID: 0005_portada_encuadre
Revises: 0004_evento_salon
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_portada_encuadre"
down_revision: str | None = "0004_evento_salon"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("proveedores", sa.Column("portada_encuadre", sa.JSON(), nullable=True))
    op.add_column("eventos", sa.Column("portada_encuadre", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("eventos", "portada_encuadre")
    op.drop_column("proveedores", "portada_encuadre")
