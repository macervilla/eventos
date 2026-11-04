from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class Datos(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigInvitados(Datos):
    activo: bool = False
    aprobacion: Literal["automatica", "manual"] = "manual"
    validacion: Literal["enlace", "email", "telefono"] = "enlace"
    requiere_login: bool = True
    permitir_modificaciones: bool = True
    cierre_rsvp: datetime | None = None
    listas_compartidas: bool = True
    canales: list[Literal["email", "whatsapp", "instagram", "messenger", "telegram", "enlace"]] = Field(
        default_factory=lambda: ["email", "whatsapp", "instagram", "messenger", "telegram", "enlace"]
    )
    otp_minutos: int = Field(default=10, ge=1, le=30)
    otp_intentos: int = Field(default=5, ge=1, le=10)
    pin_acceso: str | None = Field(default=None, min_length=4, max_length=64)
    quitar_pin: bool = False


class InvitadoDatos(Datos):
    nombre: str = Field(min_length=1, max_length=160)
    apellido: str = Field(default="", max_length=160)
    email: EmailStr | None = None
    telefono: str | None = Field(default=None, max_length=60)
    instagram: str | None = Field(default=None, max_length=100)
    whatsapp: str | None = Field(default=None, max_length=60)
    facebook: str | None = Field(default=None, max_length=255)
    telegram: str | None = Field(default=None, max_length=100)
    otro_contacto: str | None = Field(default=None, max_length=255)
    grupo: str | None = Field(default=None, max_length=160)
    responsable_id: int | None = None
    cantidad_permitida: int = Field(default=1, ge=1, le=1000)
    activo: bool = True


class AsignacionRol(Datos):
    email: EmailStr
    rol: Literal["ADMIN_EVENTO", "AGASAJADO", "GESTOR_INVITADOS", "CONTROL_INGRESO"]
    permisos: list[str] | None = None
    solo_responsable: bool = False


class AsignarAgasajados(Datos):
    emails: list[EmailStr] = Field(min_length=1, max_length=20)
    solo_responsable: bool = False


class RSVP(Datos):
    asiste: bool
    adultos: int = Field(default=1, ge=0, le=1000)
    menores: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validar(self):
        self.menores = [v.strip() for v in self.menores]
        if any(not v or len(v) > 80 for v in self.menores):
            raise ValueError("Informar solo el nombre de cada menor, hasta 80 caracteres")
        if self.asiste and self.adultos + len(self.menores) < 1:
            raise ValueError("Inclui al titular dentro del total de personas solicitadas")
        return self


class Aprobacion(Datos):
    estado: Literal["APROBADO", "RECHAZADO", "REVOCADO"]
    cupo: int = Field(default=0, ge=0, le=1000)


class Distribuir(Datos):
    ids: list[int] = Field(min_length=1, max_length=50)
    canal: Literal["email", "whatsapp", "instagram", "messenger", "telegram", "enlace"]
    tipo: Literal["invitacion", "qr"] = "invitacion"
    idempotencia: str = Field(min_length=16, max_length=60)


class PortalAcceso(Datos):
    token: str = Field(min_length=20, max_length=200)
    sesion: str | None = Field(default=None, max_length=2000)
    pin: str | None = Field(default=None, max_length=64)
    email: EmailStr | None = None
    codigo: str | None = Field(default=None, max_length=12)


class PortalRSVP(PortalAcceso):
    rsvp: RSVP


class Escaneo(Datos):
    token: str = Field(min_length=20, max_length=200)


class RegistrarIngreso(Escaneo):
    cantidad: int = Field(ge=1, le=1000)
    idempotencia: str = Field(min_length=16, max_length=80)


class CorregirIngreso(Datos):
    cantidad: int = Field(ge=1, le=1000)
    motivo: str = Field(min_length=5, max_length=500)
    idempotencia: str = Field(min_length=16, max_length=80)
