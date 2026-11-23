"""Registro compartido. PostgreSQL lo mantiene mediante triggers (migracion 0021)."""
from sqlalchemy import CheckConstraint, Integer, String, UniqueConstraint, event, inspect
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.eventos import Evento
from app.models.proveedores import Proveedor


RESERVED_SLUGS = frozenset({
    "admin", "administracion", "login", "ingresar", "api", "api-vps", "eventos",
    "proveedores", "nuevo", "media", "assets", "rtc", "health", "compartir",
    "acceso", "geografia", "ubicacion", "interno", "docs", "redoc", "openapi-json",
})


class SlugPublico(Base):
    __tablename__ = "slugs_publicos"
    slug: Mapped[str] = mapped_column(String(220), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    entidad_id: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        CheckConstraint("tipo IN ('evento', 'proveedor')", name="ck_slug_tipo"),
        UniqueConstraint("tipo", "entidad_id", name="uq_slug_entidad"),
    )


# Soporte para las bases SQLite aisladas de pruebas. En produccion los triggers
# cubren tambien INSERT/UPDATE/DELETE SQL fuera del ORM.
def _registrar(_mapper, connection, target):
    if connection.dialect.name != "sqlite":
        return
    if target.slug in RESERVED_SLUGS:
        raise ValueError("Slug reservado")
    connection.execute(SlugPublico.__table__.insert().values(
        slug=target.slug, tipo="evento" if isinstance(target, Evento) else "proveedor",
        entidad_id=target.id,
    ))


def _inmutable(_mapper, connection, target):
    if connection.dialect.name != "sqlite":
        return
    campos = ("slug", "nombre") if isinstance(target, Evento) else ("slug",)
    if any(inspect(target).attrs[c].history.has_changes() for c in campos):
        raise ValueError("El slug y el nombre original del evento son inmutables")


def _eliminar(_mapper, connection, target):
    if connection.dialect.name == "sqlite":
        connection.execute(SlugPublico.__table__.delete().where(SlugPublico.slug == target.slug))


for _model in (Evento, Proveedor):
    event.listen(_model, "after_insert", _registrar)
    event.listen(_model, "before_update", _inmutable)
    event.listen(_model, "after_delete", _eliminar)
