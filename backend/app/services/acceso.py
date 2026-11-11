import logging
from datetime import UTC, datetime
from functools import partial

from fastapi import HTTPException
from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.seguridad import (
    crear_token_enlace,
    crear_token_sesion,
    leer_datos_enlace,
)
from app.models.eventos import Evento, EventoUsuario
from app.models.proveedores import Proveedor
from app.models.usuarios import User
from app.schemas.acceso import AccessOption, AccessResponse
from app.services.email import send_access_link_email
from app.services.invitados_permisos import asignacion_con_acceso

logger = logging.getLogger(__name__)


def _motivo_rechazo_google(exc: Exception) -> str:
    # Clasificar sin registrar el texto de la excepcion: puede contener la credencial.
    mensaje = str(exc).lower()
    for fragmento, motivo in (
        ("too early", "reloj_desfasado"),
        ("expired", "token_vencido"),
        ("audience", "audiencia_incorrecta"),
        ("issuer", "emisor_incorrecto"),
        ("signature", "firma_invalida"),
        ("certificate", "certificado_no_disponible"),
        ("segments", "formato_incorrecto"),
    ):
        if fragmento in mensaje:
            return motivo
    return "credencial_invalida"


def get_verified_google_profile(credential: str) -> dict:
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="El ingreso con Google no esta configurado en Eventos")
    token = credential.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token de Google faltante")

    try:
        # La biblioteca oficial verifica firma RSA, aud, iss, iat y exp.
        profile = id_token.verify_oauth2_token(
            token, partial(GoogleRequest(), timeout=10), audience=settings.google_client_id,
            clock_skew_in_seconds=settings.google_clock_skew_seconds,
        )
    except TransportError as exc:
        raise HTTPException(status_code=503, detail="No se pudo conectar con Google. Intenta nuevamente") from exc
    except (ValueError, KeyError, GoogleAuthError) as exc:
        logger.warning("Google OAuth: rechazo=%s tipo=%s", _motivo_rechazo_google(exc), type(exc).__name__)
        raise HTTPException(status_code=401, detail="Token de Google invalido") from exc

    email = profile.get("email")
    verified = profile.get("email_verified")
    subject = profile.get("sub")
    if (not isinstance(email, str) or not email.strip() or verified is not True
            or not isinstance(subject, str) or not subject or len(subject) > 255):
        raise HTTPException(status_code=401, detail="Email de Google no verificado")
    profile["email"] = email.strip().lower()
    return profile


def get_verified_google_email(credential: str) -> str:
    return get_verified_google_profile(credential)["email"]


def _buscar_usuario_activo(db: Session, email: str) -> User | None:
    usuarios = db.scalars(
        select(User).where(
            User.activo.is_(True),
            func.lower(User.email) == email.strip().lower(),
        )
    ).all()
    if len(usuarios) > 1:
        raise HTTPException(409, "Hay varias cuentas con este email. Solicita nuevos enlaces de ingreso por email")
    return usuarios[0] if usuarios else None


def get_access_options_by_email(db: Session, email: str) -> AccessResponse:
    normalized_email = email.strip().lower()
    user = _buscar_usuario_activo(db, normalized_email)
    if user is None:
        return AccessResponse(email=normalized_email, opciones=[])

    return get_access_options_by_user(db, user)


def get_access_options_by_user(db: Session, user: User, incluir_vinculadas: bool = False, *, metodo: str = "email", email_google: str | None = None) -> AccessResponse:
    if not user.activo:
        return AccessResponse(email=user.email, opciones=[])
    if incluir_vinculadas and user.google_subject:
        cuentas = db.scalars(select(User).where(User.google_subject == user.google_subject,
            func.lower(User.email) == user.email.lower(), User.activo.is_(True)).order_by(User.id)).all()
        if len(cuentas) > 1:
            opciones = []
            vistos = set()
            for cuenta in cuentas:
                for opcion in get_access_options_by_user(db, cuenta, metodo=metodo, email_google=email_google).opciones:
                    clave = (opcion.tipo, opcion.id)
                    if clave not in vistos:
                        opcion.token = crear_token_sesion(cuenta, metodo=metodo, email_google=email_google)
                        opciones.append(opcion)
                        vistos.add(clave)
            return AccessResponse(email=user.email, usuario_id=user.id, opciones=opciones, email_validado=bool(user.email_validado_en), google_vinculado=True)

    proveedores = db.scalars(
        select(Proveedor).where(
            Proveedor.activo.is_(True),
            Proveedor.usuario_id == user.id,
        )
    ).all()

    # Usar los mismos permisos efectivos que las operaciones, sin comparar JSON como texto.
    eventos_como_miembro = {
        asignacion.evento_id
        for asignacion in db.scalars(select(EventoUsuario).where(EventoUsuario.usuario_id == user.id))
        if asignacion_con_acceso(asignacion)
    }
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

    if user.es_superadministrador:
        opciones.insert(0, AccessOption(
            tipo="administracion", id=user.id, nombre="Administracion del proyecto",
            slug="administracion", path="/administracion",
        ))

    for opcion in opciones:
        opcion.cuenta_id = user.id
    return AccessResponse(email=user.email, usuario_id=user.id, opciones=opciones, email_validado=bool(user.email_validado_en), google_vinculado=bool(user.google_subject))


def _respuesta_con_sesion(db: Session, usuario: User, *, metodo: str = "email", email_google: str | None = None) -> AccessResponse:
    """Un enlace valida correo; solo Google produce credenciales administrativas."""
    respuesta = (get_access_options_by_user(db, usuario, incluir_vinculadas=True, metodo=metodo, email_google=email_google)
                 if metodo == "google" else AccessResponse(email=usuario.email, opciones=[],
                     email_validado=True, google_vinculado=bool(usuario.google_subject), requiere_google=True))
    if usuario.activo:
        respuesta.token = crear_token_sesion(usuario, metodo=metodo, email_google=email_google)
    return respuesta


def get_access_options_by_google_token(db: Session, credential: str, actual: User | None = None) -> AccessResponse:
    profile = get_verified_google_profile(credential)
    vinculadas = db.scalars(select(User).where(User.google_subject == profile["sub"]).order_by(User.id)).all()
    autoridad = profile["email"].endswith("@gmail.com") or bool(profile.get("hd"))
    candidatas = db.scalars(select(User).where(func.lower(User.email) == profile["email"]).order_by(User.id)).all()
    elegibles = []
    for cuenta in candidatas:
        if cuenta.google_subject not in (None, profile["sub"]) or not cuenta.activo:
            continue
        if cuenta.google_subject is None and not autoridad:
            # Google no acredita la propiedad actual de un correo externo como Hotmail.
            # La vinculacion inicial requiere la sesion obtenida al validar ese email.
            if actual is None or actual.email.lower() != profile["email"] or not actual.email_validado_en:
                continue
        vinculada = cuenta.google_subject == profile["sub"]
        cuenta.google_subject = profile["sub"]
        if (autoridad or vinculada) and cuenta.email_validado_en is None:
            cuenta.email_validado_en = datetime.now(UTC)
        elif not autoridad and actual is not None and cuenta.email_validado_en is None:
            cuenta.email_validado_en = actual.email_validado_en
        elegibles.append(cuenta)
    if not candidatas and not vinculadas:
        if not autoridad:
            raise HTTPException(403, "Para usar este correo con Google, registra tu sitio y valida el email una sola vez")
        usuario = User(email=profile["email"], nombre=profile.get("name"), google_subject=profile["sub"],
                       email_validado_en=datetime.now(UTC) if autoridad else None)
        db.add(usuario)
        elegibles.append(usuario)
    disponibles = [u for u in vinculadas if u.activo] or elegibles
    if not disponibles:
        if candidatas and not any(u.activo for u in candidatas):
            return AccessResponse(email=profile["email"], opciones=[])
        raise HTTPException(403, "Para vincular este correo con Google por primera vez, valida tu email e ingresa desde la sesion inicial")
    usuario = disponibles[0]
    db.commit()
    return _respuesta_con_sesion(db, usuario, metodo="google", email_google=profile["email"])


def solicitar_enlace_acceso(db: Session, email: str, destino: str | None = None,
                           usuario_id: int | None = None) -> None:
    consulta = select(User).where(User.activo.is_(True), func.lower(User.email) == email.strip().lower())
    if usuario_id is not None:
        consulta = consulta.where(User.id == usuario_id)
    for usuario in db.scalars(consulta.order_by(User.id)):
        send_access_link_email(usuario.email, crear_token_enlace(usuario.email, usuario.id), destino)


def iniciar_sesion_con_enlace(db: Session, token: str) -> AccessResponse:
    datos = leer_datos_enlace(token)
    email, usuario_id = str(datos["email"]), datos.get("usuario_id")
    usuario = db.get(User, usuario_id) if usuario_id is not None else _buscar_usuario_activo(db, email)
    if usuario is None or not usuario.activo or usuario.email.lower() != email.lower():
        return AccessResponse(email=email, opciones=[])
    if usuario.email_validado_en is None:
        usuario.email_validado_en = datetime.now(UTC)
    db.commit()
    return _respuesta_con_sesion(db, usuario)
