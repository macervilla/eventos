"""Catalogo local GeoNames, separado de los datos operativos por prefijo geo_."""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeoPais(Base):
    __tablename__ = "geo_paises"
    codigo_iso: Mapped[str] = mapped_column(String(2), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    nombre_normalizado: Mapped[str] = mapped_column(String(400))


class GeoProvincia(Base):
    __tablename__ = "geo_provincias"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    codigo_pais: Mapped[str] = mapped_column(ForeignKey("geo_paises.codigo_iso"))
    codigo_administrativo: Mapped[str] = mapped_column(String(80))
    nombre: Mapped[str] = mapped_column(String(200))
    nombre_normalizado: Mapped[str] = mapped_column(String(400))


class GeoSubdivision(Base):
    __tablename__ = "geo_subdivisiones"
    id: Mapped[str] = mapped_column(String(190), primary_key=True)
    codigo_pais: Mapped[str] = mapped_column(ForeignKey("geo_paises.codigo_iso"))
    provincia_id: Mapped[str | None] = mapped_column(ForeignKey("geo_provincias.id"))
    codigo_administrativo: Mapped[str] = mapped_column(String(80))
    nombre: Mapped[str] = mapped_column(String(200))


class GeoLocalidad(Base):
    __tablename__ = "geo_localidades"
    geoname_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    nombre: Mapped[str] = mapped_column(String(200))
    nombre_ascii: Mapped[str] = mapped_column(String(200))
    nombre_normalizado: Mapped[str] = mapped_column(String(400))
    codigo_pais: Mapped[str] = mapped_column(ForeignKey("geo_paises.codigo_iso"))
    codigo_provincia: Mapped[str] = mapped_column(String(80))
    codigo_subdivision: Mapped[str | None] = mapped_column(String(80))
    provincia_id: Mapped[str | None] = mapped_column(ForeignKey("geo_provincias.id"))
    subdivision_id: Mapped[str | None] = mapped_column(ForeignKey("geo_subdivisiones.id"))
    latitud: Mapped[float] = mapped_column(Float)
    longitud: Mapped[float] = mapped_column(Float)
    poblacion: Mapped[int] = mapped_column(BigInteger)
    feature_code: Mapped[str] = mapped_column(String(20))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class GeoNombre(Base):
    __tablename__ = "geo_nombres"
    geoname_id: Mapped[int] = mapped_column(ForeignKey("geo_localidades.geoname_id"), primary_key=True)
    nombre_normalizado: Mapped[str] = mapped_column(String(400), primary_key=True)
    __table_args__ = (Index("ix_geo_nombres_prefijo", "nombre_normalizado",
                           postgresql_ops={"nombre_normalizado": "varchar_pattern_ops"}),)


class GeoImportacion(Base):
    __tablename__ = "geo_importaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    iniciada: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finalizada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(20))
    version: Mapped[str] = mapped_column(String(40))
    fuentes: Mapped[dict] = mapped_column(JSON)
    cantidades: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String(500))


class ReferenciaGeografica:
    geoname_id: Mapped[int | None] = mapped_column(ForeignKey("geo_localidades.geoname_id", ondelete="RESTRICT"))
    codigo_pais: Mapped[str | None] = mapped_column(String(2))
