"""Restricciones e indices para solicitudes y credenciales activas."""
import sqlalchemy as sa
from alembic import op

revision = "0011_invitados_integridad"
down_revision = "0010_invitados"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint("ck_invitacion_solicitados", "invitaciones", "adultos + menores <= cantidad_permitida")
    op.create_index("ix_invitaciones_evento_activo", "invitaciones", ["evento_id", "activo"])
    op.create_index("ix_participantes_invitacion_id", "participantes", ["invitacion_id"])
    op.create_index("uq_credencial_activa", "credenciales_invitacion", ["invitacion_id", "tipo"], unique=True, postgresql_where=sa.text("activo = true"))


def downgrade():
    op.drop_index("uq_credencial_activa", "credenciales_invitacion")
    op.drop_index("ix_participantes_invitacion_id", "participantes")
    op.drop_index("ix_invitaciones_evento_activo", "invitaciones")
    op.drop_constraint("ck_invitacion_solicitados", "invitaciones", type_="check")
