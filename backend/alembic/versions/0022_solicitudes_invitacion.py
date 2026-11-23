"""Solicitudes de invitacion y contactos publicos con autorizacion explicita."""
from alembic import op
import sqlalchemy as sa

revision = "0022_solicitudes_invitacion"
down_revision = "0021_slugs_publicos"
branch_labels = None
depends_on = None


def tiempos():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    op.create_table("contactos_publicos_agasajado",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento_id", sa.Integer(), sa.ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agasajado_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nombre_publico", sa.String(160), nullable=False),
        sa.Column("habilitado", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("email", sa.String(255)), sa.Column("whatsapp", sa.String(60)),
        sa.Column("publicar_email", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("publicar_whatsapp", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.UniqueConstraint("evento_id", "agasajado_id", name="uq_contacto_publico_evento_agasajado"), *tiempos())
    op.create_table("solicitudes_invitacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento_id", sa.Integer(), sa.ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agasajado_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nombre", sa.String(160), nullable=False), sa.Column("apellido", sa.String(160), nullable=False),
        sa.Column("nombre_normalizado", sa.String(160), nullable=False), sa.Column("apellido_normalizado", sa.String(160), nullable=False),
        sa.Column("email_verificado", sa.String(255), nullable=False), sa.Column("telefono", sa.String(60)),
        sa.Column("canal", sa.String(16), nullable=False),
        sa.Column("estado", sa.String(16), server_default="PENDIENTE", nullable=False),
        sa.Column("requiere_revision", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("invitacion_id", sa.Integer(), sa.ForeignKey("invitaciones.id")),
        sa.Column("revisado_por", sa.Integer(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("evento_id", "email_verificado", name="uq_solicitud_evento_email"),
        sa.CheckConstraint("estado IN ('PENDIENTE', 'APROBADA', 'RECHAZADA')", name="ck_solicitud_estado"),
        sa.CheckConstraint("canal IN ('email', 'whatsapp')", name="ck_solicitud_canal"), *tiempos())
    op.create_index("ix_solicitudes_invitacion_evento_id", "solicitudes_invitacion", ["evento_id"])
    op.create_index("ix_solicitudes_invitacion_agasajado_id", "solicitudes_invitacion", ["agasajado_id"])


def downgrade():
    op.drop_table("solicitudes_invitacion")
    op.drop_table("contactos_publicos_agasajado")
