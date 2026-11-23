"""Fotos privadas de invitados y bloqueo de su conjunto por administracion."""
from alembic import op
import sqlalchemy as sa

revision = "0019_fotos_invitados"
down_revision = "0018_nombres_acompanantes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invitaciones", sa.Column("fotos_bloqueadas", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_table("fotos_invitado",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invitacion_id", sa.Integer(), sa.ForeignKey("invitaciones.id"), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("nombre_archivo", sa.String(160), nullable=False),
        sa.Column("mime_type", sa.String(80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("slot >= 1 AND slot <= 4", name="ck_foto_invitado_slot"),
    )
    op.create_index("ix_fotos_invitado_invitacion_id", "fotos_invitado", ["invitacion_id"])
    op.create_index("ix_fotos_invitado_activo", "fotos_invitado", ["activo"])
    op.create_index("uq_foto_invitado_slot_activo", "fotos_invitado", ["invitacion_id", "slot"], unique=True,
                    postgresql_where=sa.text("activo = true"), sqlite_where=sa.text("activo = 1"))


def downgrade():
    op.drop_table("fotos_invitado")
    op.drop_column("invitaciones", "fotos_bloqueadas")
