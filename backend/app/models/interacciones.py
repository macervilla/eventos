import uuid as uuid_lib

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MediaEstado, MediaTipo
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class OpcionEvento(TimestampMixin, Base):
    __tablename__ = "opciones_evento"
    __table_args__ = (UniqueConstraint("evento_id", "tipo", "valor", name="uq_opcion_evento"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    valor: Mapped[str] = mapped_column(String(160), nullable=False)
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)

    evento = relationship("Evento")


class TemaMusical(TimestampMixin, Base):
    __tablename__ = "temas_musicales"

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    artista: Mapped[str] = mapped_column(String(160), nullable=False)
    titulo: Mapped[str] = mapped_column(String(180), nullable=False)
    votos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    evento = relationship("Evento")
    usuario = relationship("User")


class Media(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "media"
    __table_args__ = (
        CheckConstraint(
            "(evento_id IS NOT NULL AND proveedor_id IS NULL) OR "
            "(evento_id IS NULL AND proveedor_id IS NOT NULL)",
            name="ck_media_single_owner",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_lib.UUID] = mapped_column(default=uuid_lib.uuid4, unique=True, index=True)
    evento_id: Mapped[int | None] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id", ondelete="CASCADE"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    tipo: Mapped[MediaTipo] = mapped_column(Enum(MediaTipo, name="media_tipo"), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    tamano: Mapped[int | None] = mapped_column(BigInteger)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    orden: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estado: Mapped[MediaEstado] = mapped_column(
        Enum(MediaEstado, name="media_estado"),
        default=MediaEstado.PENDIENTE,
        nullable=False,
    )

    evento = relationship("Evento")
    proveedor = relationship("Proveedor")
    usuario = relationship("User", foreign_keys=[usuario_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])


class Publicacion(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "publicaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(40), default="VISIBLE", nullable=False)

    evento = relationship("Evento")
    usuario = relationship("User")
