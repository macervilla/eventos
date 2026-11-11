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


def crear_token_sesion(usuario: User, *, metodo: str = "email", email_google: str | None = None) -> str:
    if metodo not in {"google", "email"}:
        raise HTTPException(403, "Metodo de autenticacion no admitido")
    google = metodo == "google"
    if google and (not usuario.google_subject or not usuario.email_validado_en):
        raise HTTPException(403, "La sesion requiere Google y email verificado")
    return _firmar(
        {"tipo": "sesion" if google else "validacion_email", "sub": str(usuario.id),
         "email": usuario.email, "amr": metodo,
         "email_google": (email_google or usuario.email) if google else None,
         "google_sub": usuario.google_subject if google else None},
        settings.access_token_expire_minutes,
    )


def crear_token_enlace(email: str, usuario_id: int | None = None) -> str:
    """Token del enlace magico que se envia por mail: prueba que la persona controla el email."""
    datos = {"tipo": "enlace", "email": email.strip().lower()}
    if usuario_id is not None:
        datos["usuario_id"] = usuario_id
    return _firmar(datos, MINUTOS_ENLACE)


def leer_email_de_enlace(token: str) -> str:
    return str(_leer(token, "enlace")["email"])


def leer_cuenta_de_enlace(token: str) -> tuple[str, int | None]:
    datos = leer_datos_enlace(token)
    return str(datos["email"]), datos.get("usuario_id")


def leer_datos_enlace(token: str) -> dict:
    try:
        datos = _leer(token, "enlace")
    except HTTPException:
        datos = _leer(token, "bienvenida")
    return datos


def crear_token_bienvenida(usuario: User, destino: str | None = None) -> str:
    return _firmar({"tipo": "bienvenida", "email": usuario.email, "usuario_id": usuario.id, "destino": destino}, 48 * 60)


def crear_token_alta(slug: str) -> str:
    """Permite reenviar la confirmacion justo despues del alta, sin sesion."""
    return _firmar({"tipo": "alta", "slug": slug}, MINUTOS_ALTA)


def validar_token_alta(token: str | None, slug: str) -> None:
    if not token or _leer(token, "alta").get("slug") != slug:
        raise HTTPException(status_code=403, detail="No autorizado")


def crear_token_confirmacion_evento(slug: str, email: str) -> str:
    """Valida el correo de alta. Nunca concede una sesion administrativa."""
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
    try:
        usuario = db.get(User, int(datos["sub"]))
    except (ValueError, TypeError, KeyError):
        raise HTTPException(401, "Sesion invalida") from None
    if usuario is None or not usuario.activo:
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    if datos.get("email") != usuario.email:
        raise HTTPException(status_code=401, detail="El email de la cuenta cambio. Inicia sesion nuevamente")
    if (datos.get("amr") != "google" or not usuario.google_subject
            or datos.get("google_sub") != usuario.google_subject or not usuario.email_validado_en):
        raise HTTPException(401, "Inicia sesion con Google y un email verificado")
    if not isinstance(datos.get("email_google"), str) or not datos["email_google"]:
        raise HTTPException(401, "Sesion Google sin email verificado")
    # Dato exclusivo de esta peticion; no modifica el email persistido de la cuenta.
    usuario._email_google_sesion = datos["email_google"]
    return usuario


def obtener_usuario_vinculacion_opcional(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """La prueba de correo solo sirve para vincular Google, no para administrar."""
    if credenciales is None:
        return None
    try:
        return obtener_usuario_actual(credenciales, db)
    except HTTPException:
        try:
            datos = _leer(credenciales.credentials, "validacion_email")
            usuario = db.get(User, int(datos["sub"]))
            if usuario and usuario.activo and usuario.email == datos.get("email") and usuario.email_validado_en:
                return usuario
        except (HTTPException, ValueError, TypeError, KeyError):
            pass
    return None


def exigir_duenio_proveedor(db: Session, slug: str, usuario: User) -> Proveedor:
    proveedor = db.scalar(
        select(Proveedor).where(Proveedor.slug == slug, Proveedor.activo.is_(True))
    )
    if proveedor is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    if proveedor.usuario_id != usuario.id and not usuario.es_superadministrador:
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
