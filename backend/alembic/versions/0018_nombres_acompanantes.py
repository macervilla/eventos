"""Apellido separado para las personas que acompanan al titular."""
from alembic import op
import sqlalchemy as sa

revision = "0018_nombres_acompanantes"
down_revision = "0017_verificacion_invitados"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("participantes", sa.Column("apellido", sa.String(160), server_default="", nullable=False))


def downgrade():
    op.drop_column("participantes", "apellido")
