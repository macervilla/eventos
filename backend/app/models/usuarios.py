from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import LocationPreferenceOrigen
from app.models.mixins import TimestampMixin
from app.models.geografia import ReferenciaGeografica


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    google_subject: Mapped[str | None] = mapped_column(String(255), index=True)
    email_validado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bienvenida_enviada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nombre: Mapped[str | None] = mapped_column(String(160))
    password_hash: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    es_superadministrador: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    location_preference: Mapped["UserLocationPreference | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )


class UserLocationPreference(ReferenciaGeografica, TimestampMixin, Base):
    __tablename__ = "user_location_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    localidad: Mapped[str | None] = mapped_column(String(160))
    provincia: Mapped[str | None] = mapped_column(String(160))
    pais: Mapped[str] = mapped_column(String(80), default="Argentina", nullable=False)
    latitud: Mapped[float | None] = mapped_column(Float)
    longitud: Mapped[float | None] = mapped_column(Float)
    origen: Mapped[LocationPreferenceOrigen] = mapped_column(
        Enum(LocationPreferenceOrigen, name="location_preference_origen"),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="location_preference")
