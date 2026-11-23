from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccesoVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str | None = Field(default=None, min_length=20, max_length=200)
    sesion: str | None = Field(default=None, max_length=2000)
    sesion_media: str | None = Field(default=None, max_length=36)
    reserva: str | None = Field(default=None, max_length=32)
    motivo: Literal["finalizada", "interrumpida"] = "finalizada"
    invitacion_id: int | None = Field(default=None, gt=0)


class AutorizarVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invitacion_id: int | None = Field(default=None, gt=0)
    habilitada: bool = True


class SeleccionarVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invitacion_id: int | None = Field(default=None, gt=0)


class AuthMedia(BaseModel):
    model_config = ConfigDict(extra="ignore")
    token: str = Field(default="", max_length=4000)
    action: Literal["publish", "read"]
    path: str = Field(max_length=100)
    protocol: Literal["webrtc"]
    id: str = Field(min_length=36, max_length=36)
