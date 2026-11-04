"""Contactos sociales opcionales de los invitados."""
import sqlalchemy as sa
from alembic import op

revision = "0015_contactos_invitados"
down_revision = "0014_acceso_google"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout='5s'")
    for nombre, largo in [("whatsapp", 60), ("facebook", 255), ("telegram", 100), ("otro_contacto", 255)]:
        op.add_column("invitaciones", sa.Column(nombre, sa.String(largo), nullable=True))


def downgrade():
    for nombre in ["otro_contacto", "telegram", "facebook", "whatsapp"]:
        op.drop_column("invitaciones", nombre)
