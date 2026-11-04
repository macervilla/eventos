"""Rol de superadministrador y cuenta inicial autorizada."""
import sqlalchemy as sa
from alembic import op

revision = "0007_superadministrador"
down_revision = "0006_evento_tipografia"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "es_superadministrador", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))
    op.execute(sa.text("""
        INSERT INTO users (email, nombre, activo, es_superadministrador, created_at, updated_at)
        VALUES ('macervilla1@gmail.com', 'Superadministrador', true, true, now(), now())
        ON CONFLICT (email) DO UPDATE
        SET es_superadministrador = true, activo = true, updated_at = now()
    """))


def downgrade() -> None:
    op.drop_column("users", "es_superadministrador")
