import re
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.portada import EncuadrePortada

PLANTILLAS_EVENTO = {"classic", "elegant", "party", "kids", "sport", "minimal", "dark"}
TIPOGRAFIAS_EVENTO = {
    "sistema", "elegante", "romantica", "moderna", "divertida", "clasica", "fiesta", "impacto",
}


class SalonResumen(BaseModel):
    slug: str
    nombre_comercial: str
    direccion: str | None = None
    localidad: str | None = None
    provincia: str | None = None
    pais: str | None = None
    google_maps_url: str | None = None
    latitud: float | None = None
    longitud: float | None = None
    portada_url: str | None = None


class EventoBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=180)
    slug: str = Field(min_length=1, max_length=220)
    descripcion: str | None = None
    fecha_inicio: datetime | None = None
    lugar_tipo: Literal["salon", "domicilio"] = "salon"
    salon_slug: str | None = None
    # Solo para lugar_tipo == "domicilio" ("Mi casa")
    direccion: str | None = Field(default=None, max_length=255)
    localidad: str | None = Field(default=None, max_length=160)
    provincia: str | None = Field(default=None, max_length=160)
    pais: str | None = Field(default=None, max_length=80)
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    template_key: str = "classic"
    tipografia: str = "sistema"

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, valor: str) -> str:
        return valor.strip() if isinstance(valor, str) else valor

    @field_validator("slug")
    @classmethod
    def validar_slug(cls, valor: str) -> str:
        valor = valor.strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", valor):
            raise ValueError("Usa solo minusculas, numeros y guiones")
        return valor

    @field_validator("template_key")
    @classmethod
    def validar_plantilla(cls, valor: str) -> str:
        if valor not in PLANTILLAS_EVENTO:
            raise ValueError("Estilo de evento invalido")
        return valor

    @model_validator(mode="after")
    def validar_lugar(self) -> "EventoBase":
        if self.lugar_tipo == "salon":
            if not (self.salon_slug or "").strip():
                raise ValueError("Elegi el salon del evento")
            return self
        for campo in ("direccion", "localidad", "provincia", "pais"):
            valor = (getattr(self, campo) or "").strip()
            if not valor:
                raise ValueError(f"Para 'Mi casa' falta completar: {campo}")
            setattr(self, campo, valor)
        if (self.latitud is None) != (self.longitud is None):
            raise ValueError("La geolocalizacion debe tener latitud y longitud")
        return self

    @field_validator("tipografia")
    @classmethod
    def validar_tipografia(cls, valor: str) -> str:
        if valor not in TIPOGRAFIAS_EVENTO:
            raise ValueError("Tipografia invalida")
        return valor


class EventoCreate(EventoBase):
    # Siempre obligatorio: el evento queda sin confirmar hasta abrir el enlace enviado a este email.
    email: EmailStr


class EventoUpdate(EventoBase):
    pass


class EventoConfirmarRequest(BaseModel):
    token: str


class EventoConfirmado(BaseModel):
    slug: str
    token: str


class EventoRead(BaseModel):
    id: int
    nombre: str
    slug: str
    descripcion: str | None
    fecha_inicio: datetime | None
    template_key: str
    tipografia: str
    estado: str
    confirmado: bool
    lugar_tipo: Literal["salon", "domicilio"]
    pais: str | None
    portada_url: str | None
    portada_encuadre: EncuadrePortada | None
    localidad: str | None
    provincia: str | None
    direccion: str | None
    latitud: float | None
    longitud: float | None
    salon: SalonResumen | None


class EventoCreado(EventoRead):
    email_confirmacion: str
