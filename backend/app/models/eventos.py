import uuid as uuid_lib
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EventoEstado, EventoPrivacidad, Plan, RolEvento
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Evento(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_lib.UUID] = mapped_column(default=uuid_lib.uuid4, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    tipo_evento: Mapped[str | None] = mapped_column(String(80), index=True)
    fecha_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    localidad: Mapped[str | None] = mapped_column(String(160), index=True)
    provincia: Mapped[str | None] = mapped_column(String(160), index=True)
    pais: Mapped[str] = mapped_column(String(80), default="Argentina", nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(255))
    latitud: Mapped[float | None] = mapped_column(Float)
    longitud: Mapped[float | None] = mapped_column(Float)
    portada_url: Mapped[str | None] = mapped_column(Text)
    portada_encuadre: Mapped[dict | None] = mapped_column(JSON)
    template_key: Mapped[str] = mapped_column(String(60), default="classic", nullable=False)
    tipografia: Mapped[str] = mapped_column(String(40), default="sistema", nullable=False)
    propietario_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    salon_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    salon_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), index=True
    )
    privacidad: Mapped[EventoPrivacidad] = mapped_column(
        Enum(EventoPrivacidad, name="evento_privacidad"),
        default=EventoPrivacidad.PRIVADO,
        nullable=False,
    )
    estado: Mapped[EventoEstado] = mapped_column(
        Enum(EventoEstado, name="evento_estado"),
        default=EventoEstado.BORRADOR,
        nullable=False,
    )
    plan: Mapped[Plan] = mapped_column(Enum(Plan, name="plan"), default=Plan.GRATIS, nullable=False)
    permite_publicidad: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    propietario = relationship("User")
    salon = relationship("Proveedor")
    modulos: Mapped[list["EventoModulo"]] = relationship(
        back_populates="evento",
        cascade="all, delete-orphan",
    )


class EventoModulo(TimestampMixin, Base):
    __tablename__ = "evento_modulos"
    __table_args__ = (UniqueConstraint("evento_id", "modulo", name="uq_evento_modulo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    modulo: Mapped[str] = mapped_column(String(80), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    configuracion_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    evento: Mapped[Evento] = relationship(back_populates="modulos")


class EventoUsuario(TimestampMixin, Base):
    __tablename__ = "evento_usuarios"
    __table_args__ = (UniqueConstraint("evento_id", "usuario_id", "rol", name="uq_evento_usuario_rol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rol: Mapped[RolEvento] = mapped_column(Enum(RolEvento, name="rol_evento"), nullable=False)

    evento = relationship("Evento")
    usuario = relationship("User")
