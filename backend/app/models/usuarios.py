from sqlalchemy import Boolean, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import LocationPreferenceOrigen
from app.models.mixins import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    nombre: Mapped[str | None] = mapped_column(String(160))
    password_hash: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    location_preference: Mapped["UserLocationPreference | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )


class UserLocationPreference(TimestampMixin, Base):
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
