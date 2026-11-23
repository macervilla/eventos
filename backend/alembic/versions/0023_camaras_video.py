"""Camaras independientes y seleccion unica del album."""
from alembic import op
import sqlalchemy as sa

revision = "0023_camaras_video"
down_revision = "0022_solicitudes_invitacion"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("camaras_video",
        sa.Column("evento_id", sa.Integer(), sa.ForeignKey("eventos.id"), primary_key=True),
        sa.Column("invitacion_id", sa.Integer(), sa.ForeignKey("invitaciones.id"), primary_key=True),
        sa.Column("habilitada", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("estado", sa.String(24), nullable=False),
        sa.Column("reserva", sa.String(32)),
        sa.Column("reserva_hasta", sa.DateTime(timezone=True)),
        sa.Column("sesion_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    # Conserva la camara y seleccion anteriores, incluso su generacion de MediaMTX.
    op.execute("""INSERT INTO camaras_video
        (evento_id, invitacion_id, habilitada, version, estado, reserva, reserva_hasta, sesion_id)
        SELECT evento_id, invitacion_id, true, version, estado, reserva, reserva_hasta, sesion_id
        FROM transmisiones_evento WHERE invitacion_id IS NOT NULL""")


def downgrade():
    # Las generaciones multicamara no se pueden recuperar en el esquema antiguo.
    op.execute("UPDATE sesiones_video SET activo = false")
    op.execute("""UPDATE transmisiones_evento SET invitacion_id = NULL, estado = 'finalizada',
        reserva = NULL, reserva_hasta = NULL, sesion_id = NULL""")
    op.drop_table("camaras_video")
