import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.seguridad import crear_token_enlace, crear_token_sesion, leer_email_de_enlace
from app.models.eventos import Evento, EventoUsuario
from app.models.proveedores import Proveedor
from app.models.usuarios import User
from app.schemas.acceso import AccessOption, AccessResponse
from app.services.email import send_access_link_email


def get_verified_google_email(access_token: str) -> str:
    token = access_token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token de Google faltante")

    request = Request(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            profile = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Token de Google invalido") from exc

    email = profile.get("email")
    verified = profile.get("email_verified")
    if not email or verified is not True:
        raise HTTPException(status_code=401, detail="Email de Google no verificado")
    return str(email)


def _buscar_usuario_activo(db: Session, email: str) -> User | None:
    return db.scalar(
        select(User).where(
            User.activo.is_(True),
            User.email.ilike(email.strip().lower()),
        )
    )


def get_access_options_by_email(db: Session, email: str) -> AccessResponse:
    normalized_email = email.strip().lower()
    user = _buscar_usuario_activo(db, normalized_email)
    if user is None:
        return AccessResponse(email=normalized_email, opciones=[])

    proveedores = db.scalars(
        select(Proveedor).where(
            Proveedor.activo.is_(True),
            Proveedor.usuario_id == user.id,
        )
    ).all()

    # Subconsulta en lugar de JOIN + DISTINCT: Postgres no puede aplicar DISTINCT a columnas JSON.
    eventos_como_miembro = select(EventoUsuario.evento_id).where(EventoUsuario.usuario_id == user.id)
    eventos = db.scalars(
        select(Evento)
        .where(
            Evento.activo.is_(True),
            or_(
                Evento.propietario_id == user.id,
                Evento.id.in_(eventos_como_miembro),
            ),
        )
        .order_by(Evento.fecha_inicio.desc().nulls_last())
    ).all()

    opciones = [
        AccessOption(
            tipo="proveedor",
            id=proveedor.id,
            nombre=proveedor.nombre_comercial,
            slug=proveedor.slug,
            path=f"/p/{proveedor.slug}",
        )
        for proveedor in proveedores
    ]
    opciones.extend(
        AccessOption(
            tipo="evento",
            id=evento.id,
            nombre=evento.nombre,
            slug=evento.slug,
            path=f"/e/{evento.slug}",
        )
        for evento in eventos
    )

    return AccessResponse(email=normalized_email, opciones=opciones)


def _respuesta_con_sesion(db: Session, email: str) -> AccessResponse:
    """Solo se llama con un email ya verificado (Google o enlace magico)."""
    respuesta = get_access_options_by_email(db, email)
    usuario = _buscar_usuario_activo(db, email)
    if usuario is not None and respuesta.opciones:
        respuesta.token = crear_token_sesion(usuario)
    return respuesta


def get_access_options_by_google_token(db: Session, access_token: str) -> AccessResponse:
    email = get_verified_google_email(access_token)
    return _respuesta_con_sesion(db, email)


def solicitar_enlace_acceso(db: Session, email: str) -> None:
    if _buscar_usuario_activo(db, email) is None:
        return
    send_access_link_email(email.strip().lower(), crear_token_enlace(email))


def iniciar_sesion_con_enlace(db: Session, token: str) -> AccessResponse:
    return _respuesta_con_sesion(db, leer_email_de_enlace(token))
