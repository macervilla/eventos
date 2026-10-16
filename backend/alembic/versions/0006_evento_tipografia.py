"""tipografia de la pagina del evento

Revision ID: 0006_evento_tipografia
Revises: 0005_portada_encuadre
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_evento_tipografia"
down_revision: str | None = "0005_portada_encuadre"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "eventos",
        sa.Column("tipografia", sa.String(length=40), nullable=False, server_default="sistema"),
    )


def downgrade() -> None:
    op.drop_column("eventos", "tipografia")
