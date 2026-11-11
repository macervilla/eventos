from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EstadoConfirmacion
from app.models.mixins import TimestampMixin


class Invitacion(TimestampMixin, Base):
    __tablename__ = "invitaciones"
    __table_args__ = (
        UniqueConstraint("evento_id", "clave_duplicado", name="uq_invitacion_duplicado"),
        CheckConstraint("cantidad_permitida >= 1 AND adultos >= 0 AND menores >= 0 AND cupo_aprobado >= 0 AND ingresados >= 0 AND ingresados <= cupo_aprobado AND cupo_aprobado <= cantidad_permitida", name="ck_invitacion_cupos"),
        CheckConstraint("adultos + menores <= cantidad_permitida", name="ck_invitacion_solicitados"),
        Index("ix_invitaciones_evento_activo", "evento_id", "activo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    estado_confirmacion: Mapped[EstadoConfirmacion] = mapped_column(
        Enum(EstadoConfirmacion, name="estado_confirmacion"),
        default=EstadoConfirmacion.PENDIENTE,
        nullable=False,
    )
    cantidad_permitida: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    apellido: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    telefono: Mapped[str | None] = mapped_column(String(60))
    instagram: Mapped[str | None] = mapped_column(String(100))
    whatsapp: Mapped[str | None] = mapped_column(String(60))
    facebook: Mapped[str | None] = mapped_column(String(255))
    telegram: Mapped[str | None] = mapped_column(String(100))
    otro_contacto: Mapped[str | None] = mapped_column(String(255))
    grupo: Mapped[str | None] = mapped_column(String(160), index=True)
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    pin_personal_hash: Mapped[str | None] = mapped_column(String(64))
    actualizado_por: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    clave_duplicado: Mapped[str | None] = mapped_column(String(64))
    adultos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    menores: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cupo_aprobado: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ingresados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    distribucion: Mapped[str] = mapped_column(String(30), default="SIN_ENVIAR", nullable=False)
    canal: Mapped[str | None] = mapped_column(String(30))
    rsvp: Mapped[str] = mapped_column(String(30), default="PENDIENTE", nullable=False)
    aprobacion: Mapped[str] = mapped_column(String(30), default="PENDIENTE", nullable=False)
    confirmado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    participantes: Mapped[list["Participante"]] = relationship(back_populates="invitacion")

    evento = relationship("Evento")
    usuario = relationship("User", foreign_keys=[usuario_id])


class Participante(TimestampMixin, Base):
    __tablename__ = "participantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitaciones.id", ondelete="CASCADE"), index=True)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    tipo: Mapped[str | None] = mapped_column(String(80))
    edad_opcional: Mapped[int | None] = mapped_column(Integer)
    menu: Mapped[str | None] = mapped_column(String(120))
    bebida: Mapped[str | None] = mapped_column(String(120))
    observaciones: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    invitacion = relationship("Invitacion", back_populates="participantes")


class CredencialInvitacion(TimestampMixin, Base):
    __tablename__ = "credenciales_invitacion"
    __table_args__ = (Index("uq_credencial_activa", "invitacion_id", "tipo", unique=True,
                           postgresql_where=text("activo = true"), sqlite_where=text("activo = 1")),)
    id: Mapped[int] = mapped_column(primary_key=True)
    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitaciones.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_cifrado: Mapped[str] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    vence_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ValidacionInvitado(TimestampMixin, Base):
    __tablename__ = "validaciones_invitado"
    id: Mapped[int] = mapped_column(primary_key=True)
    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitaciones.id"), unique=True)
    codigo_hash: Mapped[str] = mapped_column(String(64))
    email: Mapped[str] = mapped_column(String(255))
    vence_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    usado: Mapped[bool] = mapped_column(Boolean, default=False)
    metodo: Mapped[str] = mapped_column(String(20), default="email", server_default="email")
    proveedor_referencia: Mapped[str | None] = mapped_column(String(64))


class SolicitudRSVP(TimestampMixin, Base):
    __tablename__ = "solicitudes_rsvp"
    id: Mapped[int] = mapped_column(primary_key=True)
    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitaciones.id"), index=True)
    adultos: Mapped[int] = mapped_column(Integer)
    menores: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class MovimientoInvitacion(TimestampMixin, Base):
    __tablename__ = "auditoria_invitaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    invitacion_id: Mapped[int | None] = mapped_column(ForeignKey("invitaciones.id"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    accion: Mapped[str] = mapped_column(String(80))
    datos: Mapped[dict] = mapped_column(JSON, default=dict)


class MovimientoIngreso(TimestampMixin, Base):
    __tablename__ = "movimientos_ingreso"
    __table_args__ = (UniqueConstraint("evento_id", "idempotencia", name="uq_ingreso_idempotente"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitaciones.id"), index=True)
    operador_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    cantidad: Mapped[int] = mapped_column(Integer)
    idempotencia: Mapped[str] = mapped_column(String(80))
    motivo: Mapped[str | None] = mapped_column(String(500))


class DistribucionInvitacion(TimestampMixin, Base):
    __tablename__ = "distribuciones_invitacion"
    __table_args__ = (UniqueConstraint("invitacion_id", "idempotencia", name="uq_distribucion_idempotente"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitaciones.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    canal: Mapped[str] = mapped_column(String(30))
    tipo: Mapped[str] = mapped_column(String(20), default="invitacion")
    estado: Mapped[str] = mapped_column(String(30))
    detalle: Mapped[str | None] = mapped_column(String(200))
    idempotencia: Mapped[str] = mapped_column(String(80))


class ImportacionInvitados(TimestampMixin, Base):
    __tablename__ = "importaciones_invitados"
    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token: Mapped[str] = mapped_column(String(64), unique=True)
    filas: Mapped[list] = mapped_column(JSON)
    resultado: Mapped[dict | None] = mapped_column(JSON)
    actualizar: Mapped[bool] = mapped_column(Boolean, default=False)
    vence_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LimiteAcceso(TimestampMixin, Base):
    __tablename__ = "limites_acceso_invitados"
    clave: Mapped[str] = mapped_column(String(64), primary_key=True)
    cantidad: Mapped[int] = mapped_column(Integer, default=0)
    ventana: Mapped[int] = mapped_column(Integer)
