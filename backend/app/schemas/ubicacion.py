from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LocationPreferenceOrigen


class UserLocationPreferenceUpsert(BaseModel):
    localidad: str | None = None
    provincia: str | None = None
    pais: str = "Argentina"
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    origen: LocationPreferenceOrigen


class UserLocationPreferenceRead(UserLocationPreferenceUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
