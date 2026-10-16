import uuid as uuid_lib

from sqlalchemy import JSON, Boolean, Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Plan
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Proveedor(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid_lib.UUID] = mapped_column(default=uuid_lib.uuid4, unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    nombre_comercial: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True, nullable=False)
    cuit: Mapped[str | None] = mapped_column(String(20), index=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
    pais: Mapped[str] = mapped_column(String(80), default="Argentina", nullable=False)
    localidad: Mapped[str | None] = mapped_column(String(160), index=True)
    provincia: Mapped[str | None] = mapped_column(String(160), index=True)
    direccion: Mapped[str | None] = mapped_column(String(255))
    google_maps_url: Mapped[str | None] = mapped_column(Text)
    google_place_id: Mapped[str | None] = mapped_column(String(255))
    ubicacion_referencia: Mapped[str | None] = mapped_column(String(255))
    latitud: Mapped[float | None] = mapped_column(Float, index=True)
    longitud: Mapped[float | None] = mapped_column(Float, index=True)
    whatsapp: Mapped[str | None] = mapped_column(String(60))
    telefono: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(255))
    web: Mapped[str | None] = mapped_column(Text)
    instagram: Mapped[str | None] = mapped_column(String(160))
    facebook: Mapped[str | None] = mapped_column(String(160))
    logo_url: Mapped[str | None] = mapped_column(Text)
    portada_url: Mapped[str | None] = mapped_column(Text)
    portada_encuadre: Mapped[dict | None] = mapped_column(JSON)
    horarios: Mapped[str | None] = mapped_column(Text)
    template_key: Mapped[str] = mapped_column(String(60), default="professional", nullable=False)
    plan: Mapped[Plan] = mapped_column(Enum(Plan, name="proveedor_plan"), default=Plan.GRATIS)

    usuario = relationship("User")
    categorias: Mapped[list["ProveedorCategoriaLink"]] = relationship(
        back_populates="proveedor",
        cascade="all, delete-orphan",
    )
    dominios: Mapped[list["ProveedorDominio"]] = relationship(
        back_populates="proveedor",
        cascade="all, delete-orphan",
    )


class CategoriaProveedor(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "categorias_proveedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)


class ProveedorCategoriaLink(TimestampMixin, Base):
    __tablename__ = "proveedor_categorias"
    __table_args__ = (
        UniqueConstraint("proveedor_id", "categoria_id", name="uq_proveedor_categoria"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedores.id", ondelete="CASCADE"))
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias_proveedor.id", ondelete="RESTRICT"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    proveedor: Mapped[Proveedor] = relationship(back_populates="categorias")
    categoria: Mapped[CategoriaProveedor] = relationship()


class ProveedorDominio(SoftDeleteMixin, TimestampMixin, Base):
    __tablename__ = "proveedor_dominios"

    id: Mapped[int] = mapped_column(primary_key=True)
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedores.id", ondelete="CASCADE"))
    dominio: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    verificado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    proveedor: Mapped[Proveedor] = relationship(back_populates="dominios")
