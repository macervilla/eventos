"""PIN por invitacion y desafios de verificacion con proveedor oficial."""
from alembic import op
import sqlalchemy as sa

revision = "0017_verificacion_invitados"
down_revision = "0016_textos_proveedor"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invitaciones", sa.Column("pin_personal_hash", sa.String(64), nullable=True))
    op.add_column("validaciones_invitado", sa.Column("metodo", sa.String(20), server_default="email", nullable=False))
    op.add_column("validaciones_invitado", sa.Column("proveedor_referencia", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("validaciones_invitado", "proveedor_referencia")
    op.drop_column("validaciones_invitado", "metodo")
    op.drop_column("invitaciones", "pin_personal_hash")
