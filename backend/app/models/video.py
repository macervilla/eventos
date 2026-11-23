from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class TransmisionEvento(TimestampMixin, Base):
    __tablename__ = "transmisiones_evento"
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), primary_key=True)
    invitacion_id: Mapped[int | None] = mapped_column(ForeignKey("invitaciones.id"))
    version: Mapped[str] = mapped_column(String(32), default=lambda: uuid4().hex, nullable=False)
    estado: Mapped[str] = mapped_column(String(24), default="finalizada", nullable=False)
    reserva: Mapped[str | None] = mapped_column(String(32))
    reserva_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sesion_id: Mapped[str | None] = mapped_column(String(36))


class SesionVideo(TimestampMixin, Base):
    __tablename__ = "sesiones_video"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    accion: Mapped[str] = mapped_column(String(12), nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    invitacion_id: Mapped[int | None] = mapped_column(ForeignKey("invitaciones.id"))
    enlace_hash: Mapped[str | None] = mapped_column(String(64))
    vence_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CamaraVideo(TimestampMixin, Base):
    __tablename__ = "camaras_video"
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"), primary_key=True)
    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitaciones.id"), primary_key=True)
    habilitada: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[str] = mapped_column(String(32), default=lambda: uuid4().hex, nullable=False)
    estado: Mapped[str] = mapped_column(String(24), default="autorizado", nullable=False)
    reserva: Mapped[str | None] = mapped_column(String(32))
    reserva_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sesion_id: Mapped[str | None] = mapped_column(String(36))
