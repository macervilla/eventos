from typing import Literal

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.invitados import Datos


class ContactoPublicoDatos(Datos):
    nombre_publico: str = Field(default="", max_length=160)
    habilitado: bool = False
    email: EmailStr | None = None
    whatsapp: str | None = Field(default=None, max_length=60)
    publicar_email: bool = False
    publicar_whatsapp: bool = False

    @model_validator(mode="after")
    def validar(self):
        self.nombre_publico = " ".join(self.nombre_publico.split())
        if self.habilitado and not self.nombre_publico:
            raise ValueError("Completa el nombre publico del agasajado")
        if self.publicar_email and not self.email:
            raise ValueError("Completa el email que autorizas publicar")
        if self.publicar_whatsapp and not self.whatsapp:
            raise ValueError("Completa el WhatsApp que autorizas publicar")
        return self


class SolicitudDatos(Datos):
    nombre: str = Field(min_length=1, max_length=160)
    apellido: str = Field(min_length=1, max_length=160)
    agasajado_id: int = Field(gt=0)
    canal: Literal["email", "whatsapp"]
    email: EmailStr | None = None
    telefono: str | None = Field(default=None, max_length=60)

    @field_validator("nombre", "apellido")
    @classmethod
    def limpiar(cls, valor):
        valor = " ".join(valor.split())
        if not valor:
            raise ValueError("Completa nombre y apellido")
        return valor

    @model_validator(mode="after")
    def contacto(self):
        if self.canal == "email" and not self.email:
            raise ValueError("Completa el correo verificado de tu cuenta")
        if self.canal == "whatsapp" and not (self.telefono or "").strip():
            raise ValueError("Completa tu numero de WhatsApp")
        return self


class DecisionSolicitud(Datos):
    estado: Literal["APROBADA", "RECHAZADA"]
    invitacion_id: int | None = Field(default=None, gt=0)
    confirmar_revision: bool = False
