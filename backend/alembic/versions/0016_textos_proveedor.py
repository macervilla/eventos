"""Posicion, visibilidad y colores de los textos de portada del proveedor."""
import sqlalchemy as sa
from alembic import op

revision = "0016_textos_proveedor"
down_revision = "0015_contactos_invitados"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("proveedores", sa.Column("textos_portada", sa.JSON(), nullable=True))
    op.add_column("proveedores", sa.Column("colores_textos", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("proveedores", "colores_textos")
    op.drop_column("proveedores", "textos_portada")
