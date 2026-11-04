"""Invitados, permisos independientes, RSVP, distribucion, QR e ingresos."""
import sqlalchemy as sa
from alembic import op

revision = "0010_invitados"
down_revision = "0009_galeria_publica"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        for rol in ("ADMIN_EVENTO", "AGASAJADO", "GESTOR_INVITADOS", "CONTROL_INGRESO"):
            op.execute(f"ALTER TYPE rol_evento ADD VALUE IF NOT EXISTS '{rol}'")
    op.add_column("evento_usuarios", sa.Column("permisos", sa.JSON()))
    op.add_column("evento_usuarios", sa.Column("solo_responsable", sa.Boolean(), server_default=sa.false(), nullable=False))
    campos = [
        ("activo", sa.Boolean(), "true"), ("nombre", sa.String(160), ""), ("apellido", sa.String(160), ""),
        ("adultos", sa.Integer(), "0"), ("menores", sa.Integer(), "0"), ("cupo_aprobado", sa.Integer(), "0"),
        ("ingresados", sa.Integer(), "0"), ("distribucion", sa.String(30), "SIN_ENVIAR"),
        ("rsvp", sa.String(30), "PENDIENTE"), ("aprobacion", sa.String(30), "PENDIENTE"),
    ]
    for nombre, tipo, valor in campos:
        op.add_column("invitaciones", sa.Column(nombre, tipo, server_default=valor, nullable=False))
    for nombre, largo in [("email", 255), ("telefono", 60), ("instagram", 100), ("grupo", 160), ("clave_duplicado", 64), ("canal", 30)]:
        op.add_column("invitaciones", sa.Column(nombre, sa.String(largo)))
    for nombre in ("responsable_id", "creado_por", "actualizado_por"):
        op.add_column("invitaciones", sa.Column(nombre, sa.Integer(), sa.ForeignKey("users.id")))
    op.add_column("invitaciones", sa.Column("confirmado_at", sa.DateTime(timezone=True)))
    op.add_column("participantes", sa.Column("activo", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.create_unique_constraint("uq_invitacion_duplicado", "invitaciones", ["evento_id", "clave_duplicado"])
    op.create_check_constraint("ck_invitacion_cupos", "invitaciones", "cantidad_permitida >= 1 AND adultos >= 0 AND menores >= 0 AND cupo_aprobado >= 0 AND ingresados >= 0 AND ingresados <= cupo_aprobado AND cupo_aprobado <= cantidad_permitida")
    for nombre in ("grupo", "responsable_id"):
        op.create_index(f"ix_invitaciones_{nombre}", "invitaciones", [nombre])

    def tabla(nombre, *columnas, extras=()):
        op.create_table(nombre, sa.Column("id", sa.Integer(), primary_key=True), *columnas,
                        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), *extras)

    def fk(nombre, tabla, nullable=False):
        return sa.Column(nombre, sa.Integer(), sa.ForeignKey(tabla + ".id"), nullable=nullable, index=True)

    tabla("credenciales_invitacion", fk("invitacion_id", "invitaciones"),
          sa.Column("tipo", sa.String(20), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
          sa.Column("token_cifrado", sa.Text(), nullable=False), sa.Column("activo", sa.Boolean(), nullable=False),
          sa.Column("vence_at", sa.DateTime(timezone=True), nullable=False))
    tabla("validaciones_invitado", sa.Column("invitacion_id", sa.Integer(), sa.ForeignKey("invitaciones.id"), unique=True, nullable=False),
          sa.Column("codigo_hash", sa.String(64), nullable=False), sa.Column("email", sa.String(255), nullable=False),
          sa.Column("vence_at", sa.DateTime(timezone=True), nullable=False), sa.Column("intentos", sa.Integer(), nullable=False), sa.Column("usado", sa.Boolean(), nullable=False))
    tabla("solicitudes_rsvp", fk("invitacion_id", "invitaciones"), sa.Column("adultos", sa.Integer(), nullable=False),
          sa.Column("menores", sa.Integer(), nullable=False), sa.Column("estado", sa.String(30), nullable=False), fk("actor_id", "users", True))
    tabla("auditoria_invitaciones", fk("evento_id", "eventos"), fk("invitacion_id", "invitaciones", True),
          fk("actor_id", "users", True), sa.Column("accion", sa.String(80), nullable=False), sa.Column("datos", sa.JSON(), nullable=False))
    tabla("movimientos_ingreso", fk("evento_id", "eventos"), fk("invitacion_id", "invitaciones"), fk("operador_id", "users"),
          sa.Column("cantidad", sa.Integer(), nullable=False), sa.Column("idempotencia", sa.String(80), nullable=False), sa.Column("motivo", sa.String(500)),
          extras=(sa.UniqueConstraint("evento_id", "idempotencia", name="uq_ingreso_idempotente"),))
    tabla("distribuciones_invitacion", fk("invitacion_id", "invitaciones"), fk("actor_id", "users"),
          sa.Column("canal", sa.String(30), nullable=False), sa.Column("tipo", sa.String(20), nullable=False),
          sa.Column("estado", sa.String(30), nullable=False), sa.Column("detalle", sa.String(200)), sa.Column("idempotencia", sa.String(80), nullable=False),
          extras=(sa.UniqueConstraint("invitacion_id", "idempotencia", name="uq_distribucion_idempotente"),))
    tabla("importaciones_invitados", fk("evento_id", "eventos"), fk("actor_id", "users"), sa.Column("token", sa.String(64), unique=True, nullable=False),
          sa.Column("filas", sa.JSON(), nullable=False), sa.Column("resultado", sa.JSON()), sa.Column("actualizar", sa.Boolean(), nullable=False), sa.Column("vence_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("limites_acceso_invitados", sa.Column("clave", sa.String(64), primary_key=True), sa.Column("cantidad", sa.Integer(), nullable=False),
                    sa.Column("ventana", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    raise RuntimeError("Migracion con historial de asistencia: usar restauracion de backup para revertir sin perder auditoria")
