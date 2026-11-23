from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ContactoPublicoAgasajado(TimestampMixin, Base):
    __tablename__ = "contactos_publicos_agasajado"
    __table_args__ = (UniqueConstraint("evento_id", "agasajado_id", name="uq_contacto_publico_evento_agasajado"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    agasajado_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    nombre_publico: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    habilitado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    whatsapp: Mapped[str | None] = mapped_column(String(60))
    publicar_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    publicar_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SolicitudInvitacion(TimestampMixin, Base):
    __tablename__ = "solicitudes_invitacion"
    __table_args__ = (
        UniqueConstraint("evento_id", "email_verificado", name="uq_solicitud_evento_email"),
        CheckConstraint("estado IN ('PENDIENTE', 'APROBADA', 'RECHAZADA')", name="ck_solicitud_estado"),
        CheckConstraint("canal IN ('email', 'whatsapp')", name="ck_solicitud_canal"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    agasajado_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    apellido: Mapped[str] = mapped_column(String(160), nullable=False)
    nombre_normalizado: Mapped[str] = mapped_column(String(160), nullable=False)
    apellido_normalizado: Mapped[str] = mapped_column(String(160), nullable=False)
    email_verificado: Mapped[str] = mapped_column(String(255), nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(60))
    canal: Mapped[str] = mapped_column(String(16), nullable=False)
    estado: Mapped[str] = mapped_column(String(16), default="PENDIENTE", nullable=False)
    requiere_revision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invitacion_id: Mapped[int | None] = mapped_column(ForeignKey("invitaciones.id"))
    revisado_por: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
