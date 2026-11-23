"""Autorizacion unica por evento y sesiones temporales de MediaMTX."""
from alembic import op
import sqlalchemy as sa

revision = "0020_video_en_vivo"
down_revision = "0019_fotos_invitados"
branch_labels = None
depends_on = None


def tiempos():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    op.create_table("transmisiones_evento",
        sa.Column("evento_id", sa.Integer(), sa.ForeignKey("eventos.id"), primary_key=True),
        sa.Column("invitacion_id", sa.Integer(), sa.ForeignKey("invitaciones.id")),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("estado", sa.String(24), nullable=False),
        sa.Column("reserva", sa.String(32)), sa.Column("reserva_hasta", sa.DateTime(timezone=True)),
        sa.Column("sesion_id", sa.String(36)), *tiempos())
    op.create_table("sesiones_video",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("evento_id", sa.Integer(), sa.ForeignKey("eventos.id"), nullable=False),
        sa.Column("version", sa.String(32), nullable=False), sa.Column("accion", sa.String(12), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("invitacion_id", sa.Integer(), sa.ForeignKey("invitaciones.id")),
        sa.Column("enlace_hash", sa.String(64)), sa.Column("vence_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False), *tiempos())
    op.create_index("ix_sesiones_video_evento_id", "sesiones_video", ["evento_id"])


def downgrade():
    op.drop_table("sesiones_video")
    op.drop_table("transmisiones_evento")
