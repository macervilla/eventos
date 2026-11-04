from pydantic import BaseModel, EmailStr, Field, field_validator


class AccessRequest(BaseModel):
    email: EmailStr
    destino: str | None = Field(default=None, max_length=500)

    @field_validator("destino")
    @classmethod
    def destino_interno(cls, valor: str | None) -> str | None:
        if valor is not None and (not valor.startswith("/") or valor.startswith("//")
                                  or any(c in valor for c in "\\\r\n")):
            raise ValueError("El destino debe ser una ruta interna")
        return valor


class GoogleAccessRequest(BaseModel):
    credential: str = Field(min_length=1, max_length=16384)


class EnlaceAccesoRequest(BaseModel):
    token: str


class AccessOption(BaseModel):
    cuenta_id: int | None = None
    token: str | None = None
    tipo: str
    id: int
    nombre: str
    slug: str
    path: str


class AccessResponse(BaseModel):
    usuario_id: int | None = None
    google_vinculado: bool = False
    email_validado: bool = False
    email: EmailStr
    opciones: list[AccessOption]
    token: str | None = None
