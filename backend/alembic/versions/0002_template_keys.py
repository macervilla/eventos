"""add template keys

Revision ID: 0002_template_keys
Revises: 0001_initial
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_template_keys"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "eventos",
        sa.Column("template_key", sa.String(length=60), nullable=False, server_default="classic"),
    )
    op.add_column(
        "proveedores",
        sa.Column("template_key", sa.String(length=60), nullable=False, server_default="professional"),
    )


def downgrade() -> None:
    op.drop_column("proveedores", "template_key")
    op.drop_column("eventos", "template_key")
