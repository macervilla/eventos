import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator, model_validator

from app.models.enums import Plan
from app.schemas.portada import EncuadrePortada


class CategoriaProveedorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    slug: str


class ProveedorBase(BaseModel):
    nombre_comercial: str = Field(min_length=2, max_length=180)
    slug: str = Field(min_length=1, max_length=220)
    cuit: str | None = Field(default=None, max_length=20)
    descripcion: str | None = None
    categorias: list[str] = Field(default_factory=list, min_length=1)
    pais: str = "Argentina"
    localidad: str | None = None
    provincia: str | None = None
    direccion: str | None = None
    google_maps_url: HttpUrl | None = None
    google_place_id: str | None = None
    ubicacion_referencia: str | None = None
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    whatsapp: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    web: HttpUrl | None = None
    instagram: str | None = None
    facebook: str | None = None
    logo_url: str | None = None
    portada_url: str | None = None
    horarios: str | None = None
    template_key: str = "professional"
    plan: Plan = Plan.GRATIS
    activo: bool = True

    @field_validator("nombre_comercial", "localidad", "provincia", "direccion", mode="before")
    @classmethod
    def strip_required_strings(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip()

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            raise ValueError("El slug es obligatorio")
        normalized = value.strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
            raise ValueError("Usa solo minusculas, numeros y guiones")
        return normalized

    @field_validator("cuit")
    @classmethod
    def validate_cuit(cls, value: str | None) -> str | None:
        if not value:
            return value
        if not re.fullmatch(r"\d{2}-?\d{8}-?\d", value):
            raise ValueError("CUIT invalido")
        return value

    @field_validator("google_maps_url")
    @classmethod
    def validate_google_maps_url(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is None:
            return value
        host = value.host or ""
        if "google." not in host and host != "maps.app.goo.gl":
            raise ValueError("Debe ser un enlace de Google Maps")
        return value

    @field_validator("template_key")
    @classmethod
    def validate_template_key(cls, value: str) -> str:
        allowed = {"professional", "elegant", "creative", "dark", "minimal", "photographic"}
        if value not in allowed:
            raise ValueError("Template de proveedor invalido")
        return value

    @model_validator(mode="after")
    def validate_required_business_fields(self) -> "ProveedorBase":
        required = {
            "provincia": self.provincia,
            "localidad": self.localidad,
            "direccion": self.direccion,
            "email": self.email,
        }
        missing = [field for field, value in required.items() if not value]
        if missing:
            raise ValueError(f"Campos requeridos faltantes: {', '.join(missing)}")
        return self


class ProveedorCreate(ProveedorBase):
    usuario_id: int | None = None


class ProveedorEmailRequest(BaseModel):
    email: EmailStr
    token_alta: str | None = None


class ProveedorRead(ProveedorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    slug: str
    portada_encuadre: EncuadrePortada | None = None
    distancia_km: float | None = None
    categorias_detalle: list[CategoriaProveedorRead] = Field(default_factory=list)


class ProveedorCreado(ProveedorRead):
    token_alta: str


class ProveedorSearchParams(BaseModel):
    categoria: str | None = None
    localidad: str | None = None
    provincia: str | None = None
    nombre: str | None = None
    plan: Plan | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    radio_km: float | None = Field(default=None, gt=0, le=500)
