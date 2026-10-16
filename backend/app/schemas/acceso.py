from pydantic import BaseModel, EmailStr


class AccessRequest(BaseModel):
    email: EmailStr


class GoogleAccessRequest(BaseModel):
    access_token: str


class EnlaceAccesoRequest(BaseModel):
    token: str


class AccessOption(BaseModel):
    tipo: str
    id: int
    nombre: str
    slug: str
    path: str


class AccessResponse(BaseModel):
    email: EmailStr
    opciones: list[AccessOption]
    token: str | None = None
