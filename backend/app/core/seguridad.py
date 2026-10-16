from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.proveedores import Proveedor
from app.models.usuarios import User

ALGORITMO = "HS256"
MINUTOS_ENLACE = 30
MINUTOS_ALTA = 60
MINUTOS_CONFIRMACION_EVENTO = 48 * 60

esquema_bearer = HTTPBearer(auto_error=False)


def _firmar(datos: dict, minutos: int) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    return jwt.encode({**datos, "exp": expira}, settings.secret_key, algorithm=ALGORITMO)


def _leer(token: str, tipo: str) -> dict:
    try:
        datos = jwt.decode(token, settings.secret_key, algorithms=[ALGORITMO])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Token invalido o vencido") from exc
    if datos.get("tipo") != tipo:
        raise HTTPException(status_code=401, detail="Token invalido")
    return datos


def crear_token_sesion(usuario: User) -> str:
    return _firmar(
        {"tipo": "sesion", "sub": str(usuario.id), "email": usuario.email},
        settings.access_token_expire_minutes,
    )


def crear_token_enlace(email: str) -> str:
    """Token del enlace magico que se envia por mail: prueba que la persona controla el email."""
    return _firmar({"tipo": "enlace", "email": email.strip().lower()}, MINUTOS_ENLACE)


def leer_email_de_enlace(token: str) -> str:
    return str(_leer(token, "enlace")["email"])


def crear_token_alta(slug: str) -> str:
    """Permite reenviar la confirmacion justo despues del alta, sin sesion."""
    return _firmar({"tipo": "alta", "slug": slug}, MINUTOS_ALTA)


def validar_token_alta(token: str | None, slug: str) -> None:
    if not token or _leer(token, "alta").get("slug") != slug:
        raise HTTPException(status_code=403, detail="No autorizado")


def crear_token_confirmacion_evento(slug: str, email: str) -> str:
    """Enlace del mail de alta: confirma el evento e inicia sesion como su administrador."""
    return _firmar(
        {"tipo": "confirmar_evento", "slug": slug, "email": email.strip().lower()},
        MINUTOS_CONFIRMACION_EVENTO,
    )


def leer_token_confirmacion_evento(token: str) -> tuple[str, str]:
    datos = _leer(token, "confirmar_evento")
    return str(datos["slug"]), str(datos["email"])


def obtener_usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credenciales is None:
        raise HTTPException(status_code=401, detail="Inicia sesion para continuar")
    datos = _leer(credenciales.credentials, "sesion")
    usuario = db.get(User, int(datos["sub"]))
    if usuario is None or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    return usuario


def exigir_duenio_proveedor(db: Session, slug: str, usuario: User) -> Proveedor:
    proveedor = db.scalar(
        select(Proveedor).where(Proveedor.slug == slug, Proveedor.activo.is_(True))
    )
    if proveedor is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    if proveedor.usuario_id != usuario.id:
        raise HTTPException(status_code=403, detail="No administras este proveedor")
    return proveedor


def obtener_usuario_opcional(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if credenciales is None:
        return None
    try:
        return obtener_usuario_actual(credenciales, db)
    except HTTPException:
        return None
