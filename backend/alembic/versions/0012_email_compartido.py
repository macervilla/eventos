"""Permitir que varias cuentas compartan el mismo correo de ingreso."""
from alembic import op

revision = "0012_email_compartido"
down_revision = "0011_invitados_integridad"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=False)


def downgrade():
    # PostgreSQL rechazara el cambio si existen duplicados; no eliminar cuentas.
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=True)
