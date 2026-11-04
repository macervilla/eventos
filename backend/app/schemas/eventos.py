import re
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.portada import ColoresTextosPortada, EncuadrePortada, TextosPortada
from app.schemas.geografia import ReferenciaGeograficaSchema

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


class ColoresEvento(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fondo: str = Field(default="#f4f7f6", pattern=r"^#[0-9a-fA-F]{6}$")
    texto: str = Field(default="#18212f", pattern=r"^#[0-9a-fA-F]{6}$")
    acento: str = Field(default="#245c48", pattern=r"^#[0-9a-fA-F]{6}$")


class GaleriaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modo: Literal["grilla", "carrusel"] = "grilla"
    filas: int = Field(default=2, ge=1, le=10)
    columnas: int = Field(default=2, ge=1, le=10)

    @model_validator(mode="after")
    def capacidad(self) -> "GaleriaConfig":
        if self.modo == "grilla" and self.filas * self.columnas > 10:
            raise ValueError("La grilla admite hasta 10 espacios por pagina (filas por columnas)")
        return self


class EventoEditable(ReferenciaGeograficaSchema):
    colores_textos: ColoresTextosPortada | None = None
    galeria_config: GaleriaConfig | None = None
    titulo_visual: str | None = Field(default=None, max_length=180)
    colores: ColoresEvento = Field(default_factory=ColoresEvento)
    modulos_habilitados: list[Literal["detalles", "ubicacion", "galeria"]] = Field(default_factory=lambda: ["detalles", "ubicacion"])
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

    @field_validator("template_key")
    @classmethod
    def validar_plantilla(cls, valor: str) -> str:
        if valor not in PLANTILLAS_EVENTO:
            raise ValueError("Estilo de evento invalido")
        return valor

    @model_validator(mode="after")
    def validar_lugar(self) -> "EventoEditable":
        if self.lugar_tipo == "salon":
            if not (self.salon_slug or "").strip():
                raise ValueError("Elegi el salon del evento")
            return self
        for campo in ("direccion", "localidad", "provincia", "pais"):
            valor = (getattr(self, campo) or "").strip()
            if campo == "provincia" and self.geoname_id and not valor:
                continue
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


class EventoBase(EventoEditable):
    nombre: str = Field(min_length=2, max_length=180)
    slug: str = Field(min_length=1, max_length=220)

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


class EventoCreate(EventoBase):
    # Siempre obligatorio: el evento queda sin confirmar hasta abrir el enlace enviado a este email.
    email: EmailStr


class EventoUpdate(EventoEditable):
    model_config = ConfigDict(extra="forbid")


class EventoConfirmarRequest(BaseModel):
    token: str


class EventoConfirmado(BaseModel):
    slug: str
    token: str


class EventoRead(ReferenciaGeograficaSchema):
    colores_textos: ColoresTextosPortada = Field(default_factory=ColoresTextosPortada)
    textos_portada: TextosPortada | None = None
    galeria_config: GaleriaConfig = Field(default_factory=GaleriaConfig)
    titulo_visual: str | None
    colores: ColoresEvento
    modulos_habilitados: list[str]
    galeria: list[dict] = Field(default_factory=list)
    limite_galeria: int
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
    error_correo: str | None = None
    email_confirmacion: str | None = None
    bienvenida_enviada: bool = False
