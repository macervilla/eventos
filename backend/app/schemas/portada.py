from typing import Literal

from pydantic import BaseModel, Field


class EncuadrePortada(BaseModel):
    """Punto de foco en porcentaje (0 a 100) y modo de ajuste de la imagen de portada."""

    x: float = Field(default=50, ge=0, le=100)
    y: float = Field(default=50, ge=0, le=100)
    modo: Literal["cubrir", "completa"] = "cubrir"
