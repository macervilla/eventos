import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.seguridad import crear_token_confirmacion_evento, crear_token_enlace
from app.models.eventos import Evento
from app.models.proveedores import Proveedor


def _build_url(path: str) -> str:
    base_url = settings.frontend_public_url.rstrip("/")
    return f"{base_url}{path}"


def _build_login_url(email: str, destino: str | None = None) -> str:
    path = f"/ingresar?enlace={crear_token_enlace(email)}"
    if destino:
        path += f"&destino={quote(destino, safe='')}"
    return _build_url(path)


def _send_email(to_email: str | None, subject: str, html: str, text: str) -> None:
    if not to_email:
        return

    from_email = settings.smtp_from_email
    from_name = settings.smtp_from_name

    if settings.smtp_host and settings.smtp_username and settings.smtp_password:
        message = EmailMessage()
        message["From"] = formataddr((from_name, from_email))
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")

        security = (settings.smtp_security or "").strip().lower()
        use_ssl = security == "ssl" or settings.smtp_port == 465
        use_tls = security in {"tls", "starttls"} or (settings.smtp_use_tls and not use_ssl)

        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with smtp_class(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return

    print(
        "[mail:dev] SMTP sin credenciales completas\n"
        f"From: {formataddr((from_name, from_email))}\n"
        f"Para: {to_email}\n"
        f"Asunto: {subject}\n"
        f"{text}"
    )


def send_provider_confirmation_email(proveedor: Proveedor) -> None:
    if not proveedor.email:
        return
    edit_url = _build_login_url(proveedor.email, f"/p/{proveedor.slug}")
    subject = f"Confirma tu proveedor {proveedor.nombre_comercial}"
    text = (
        f"Guardamos tu proveedor {proveedor.nombre_comercial}.\n\n"
        f"Enlace para validar y editar el negocio: {edit_url}\n"
        "Desde este correo podras validar el negocio, modificar sus datos y volver a la app."
    )
    html = f"""
    <p>Guardamos tu proveedor <strong>{proveedor.nombre_comercial}</strong>.</p>
    <p><a href="{edit_url}">Validar y editar mi negocio</a></p>
    <p>Desde este correo podras validar el negocio, modificar sus datos y volver a la app.</p>
    """
    _send_email(proveedor.email, subject, html, text)


def send_provider_edit_access_email(proveedor: Proveedor) -> None:
    if not proveedor.email:
        return
    edit_url = _build_login_url(proveedor.email, f"/p/{proveedor.slug}")
    subject = f"Acceso para editar {proveedor.nombre_comercial}"
    text = (
        f"Solicitaste editar {proveedor.nombre_comercial}.\n\n"
        f"Enlace de edicion: {edit_url}\n"
        "Si no solicitaste este acceso, podes ignorar este correo."
    )
    html = f"""
    <p>Solicitaste editar <strong>{proveedor.nombre_comercial}</strong>.</p>
    <p><a href="{edit_url}">Editar mi negocio</a></p>
    <p>Si no solicitaste este acceso, podes ignorar este correo.</p>
    """
    _send_email(proveedor.email, subject, html, text)


def send_access_link_email(email: str, token: str) -> None:
    login_url = _build_url(f"/ingresar?enlace={token}")
    subject = "Tu enlace para ingresar a Eventos"
    text = (
        "Usa este enlace para ingresar (vence en 30 minutos):\n\n"
        f"{login_url}\n\n"
        "Si no lo solicitaste, podes ignorar este correo."
    )
    html = f"""
    <p>Usa este enlace para ingresar (vence en 30 minutos):</p>
    <p><a href="{login_url}">Ingresar a Eventos</a></p>
    <p>Si no lo solicitaste, podes ignorar este correo.</p>
    """
    _send_email(email, subject, html, text)


def send_event_confirmation_email(evento: Evento, email: str) -> None:
    token = crear_token_confirmacion_evento(evento.slug, email)
    edit_url = _build_url(f"/e/{evento.slug}?confirmar={token}")
    lugar = evento.salon.nombre_comercial if evento.salon else "Mi casa"
    if evento.direccion:
        lugar += f" ({evento.direccion}, {evento.localidad})"
    fecha = (
        # astimezone: pasa la fecha guardada en UTC a la hora local del evento
        evento.fecha_inicio.astimezone(ZoneInfo(settings.zona_horaria)).strftime("%d/%m/%Y %H:%M")
        if evento.fecha_inicio
        else "a definir"
    )
    subject = f"Confirma tu evento {evento.nombre}"
    text = (
        f"Creamos tu evento {evento.nombre}.\n"
        f"Lugar: {lugar}\n"
        f"Fecha: {fecha}\n\n"
        "El evento no sera visible hasta que lo confirmes.\n"
        f"Confirma y administra el evento desde este enlace (vence en 48 horas): {edit_url}\n"
        "Si no creaste este evento, podes ignorar este correo."
    )
    html = f"""
    <p>Creamos tu evento <strong>{escape(evento.nombre)}</strong>.</p>
    <p>Lugar: {escape(lugar)}<br>Fecha: {fecha}</p>
    <p>El evento no sera visible hasta que lo confirmes.</p>
    <p><a href="{edit_url}">Confirmar y administrar mi evento</a> (vence en 48 horas)</p>
    <p>Si no creaste este evento, podes ignorar este correo.</p>
    """
    _send_email(email, subject, html, text)
