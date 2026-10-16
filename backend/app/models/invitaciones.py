from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EstadoConfirmacion
from app.models.mixins import TimestampMixin


class Invitacion(TimestampMixin, Base):
    __tablename__ = "invitaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    estado_confirmacion: Mapped[EstadoConfirmacion] = mapped_column(
        Enum(EstadoConfirmacion, name="estado_confirmacion"),
        default=EstadoConfirmacion.PENDIENTE,
        nullable=False,
    )
    cantidad_permitida: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    evento = relationship("Evento")
    usuario = relationship("User")


class Participante(TimestampMixin, Base):
    __tablename__ = "participantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    invitacion_id: Mapped[int] = mapped_column(ForeignKey("invitaciones.id", ondelete="CASCADE"))
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    tipo: Mapped[str | None] = mapped_column(String(80))
    edad_opcional: Mapped[int | None] = mapped_column(Integer)
    menu: Mapped[str | None] = mapped_column(String(120))
    bebida: Mapped[str | None] = mapped_column(String(120))
    observaciones: Mapped[str | None] = mapped_column(Text)

    invitacion = relationship("Invitacion")
