from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EncuadrePortada(BaseModel):
    """Punto de foco en porcentaje (0 a 100) y modo de ajuste de la imagen de portada."""

    x: float = Field(default=50, ge=0, le=100)
    y: float = Field(default=50, ge=0, le=100)
    modo: Literal["cubrir", "completa"] = "cubrir"


class BloqueTextoPortada(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    x: float = Field(default=5, ge=0, le=100)
    y: float = Field(default=35, ge=0, le=100)
    visible: bool = True


class TextosPortada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fecha: BloqueTextoPortada = Field(default_factory=lambda: BloqueTextoPortada(y=30))
    titulo: BloqueTextoPortada = Field(default_factory=lambda: BloqueTextoPortada(y=43))
    lugar: BloqueTextoPortada = Field(default_factory=lambda: BloqueTextoPortada(y=70))


class ColoresTextosPortada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titulo: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    fecha: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    lugar: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
