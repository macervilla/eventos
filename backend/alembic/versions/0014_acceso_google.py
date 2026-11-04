"""Validacion inicial independiente del ingreso habitual con Google."""
import sqlalchemy as sa

from alembic import op

revision = "0014_acceso_google"
down_revision = "0013_geografia"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout='5s'")
    op.add_column("users", sa.Column("email_validado_en", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("bienvenida_enviada_en", sa.DateTime(timezone=True)))
    # Conservar el acceso ya vinculado; no reenviar correos historicos.
    op.execute("UPDATE users SET email_validado_en=now() WHERE google_subject IS NOT NULL AND lower(email) LIKE '%@gmail.com'")
    op.drop_constraint("uq_users_google_subject", "users", type_="unique")
    op.create_index("ix_users_google_subject", "users", ["google_subject"])


def downgrade():
    raise RuntimeError("Conservar las validaciones y vinculaciones de cuentas; reversion destructiva deshabilitada")
