"""Avisos del rol de agasajado, conservados en la auditoria del evento."""
from html import escape
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import or_, select

from app.core.config import settings
from app.models.invitaciones import MovimientoInvitacion
from app.models.eventos import EventoUsuario
from app.models.usuarios import User
from app.services.email import _send_email
from app.services.whatsapp import numero_whatsapp
from app.services.invitados_permisos import asignacion_con_acceso


def es_contacto_equipo(db, evento, email):
    """Solo orienta la pantalla de acceso. Nunca autentica ni concede permisos."""
    if not email:
        return False
    from sqlalchemy import func
    asignados = {a.usuario_id for a in db.scalars(select(EventoUsuario).where(
        EventoUsuario.evento_id == evento.id)) if asignacion_con_acceso(a)}
    return db.scalar(select(User.id).where(
        User.activo.is_(True), func.lower(User.email) == email.strip().lower(),
        or_(User.id == evento.propietario_id, User.id.in_(asignados), User.es_superadministrador.is_(True)),
    ).limit(1)) is not None


def ultimo_aviso(db, evento_id, asignacion_id):
    # La asignacion conserva su historial incluso despues de revocarse.
    return db.scalar(select(MovimientoInvitacion).where(
        MovimientoInvitacion.evento_id == evento_id,
        MovimientoInvitacion.accion == "aviso_agasajado",
        MovimientoInvitacion.datos["asignacion_id"].as_integer() == asignacion_id,
    ).order_by(MovimientoInvitacion.id.desc()).limit(1))


def contacto_aviso(db, evento, rol, contacto=None):
    anterior = ultimo_aviso(db, evento.id, rol.id) if rol.id else None
    datos = contacto or ((anterior.datos.get("contacto") or {}) if anterior else {})
    canal = datos.get("canal", "email")
    destino = (datos.get("destinatario") or "").strip()
    if canal == "email":
        destino = rol.usuario.email
    elif canal == "whatsapp":
        try:
            destino = numero_whatsapp(destino, evento.codigo_pais, evento.pais)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    elif canal in {"instagram", "messenger", "telegram"}:
        if not destino:
            raise HTTPException(422, "Completa el usuario o contacto para enviar el aviso")
    else:
        raise HTTPException(422, "Canal de aviso no admitido")
    return {"canal": canal, "destinatario": destino}


def preparar_aviso(db, ctx, rol, alta, contacto=None):
    contacto = contacto_aviso(db, ctx.evento, rol, contacto)
    titulo = ctx.evento.titulo_visual or ctx.evento.nombre
    enlace = settings.frontend_public_url.rstrip("/") + f"/e/{ctx.evento.slug}/acceso-equipo"
    etiqueta = "Administrador" if rol.rol.value in {"ADMIN_EVENTO", "PROPIETARIO"} else "Agasajado"
    if alta:
        mensaje = (f"{ctx.usuario.email} te asigno el rol de {etiqueta} en {titulo}.\n"
                   f"Para ingresar como {etiqueta}, selecciona en Google el email {rol.usuario.email}, "
                   "que el emisor registro en el sistema.\n"
                   "Cuando Google valide esa cuenta, ingresaras directamente al evento con tus permisos asignados. "
                   "No se requiere otro codigo de acceso.\n"
                   + ("Como Agasajado podes seleccionar contactos y cargar invitados.\n" if etiqueta == "Agasajado" else "")
                   + f"Acceder como {etiqueta}: {enlace}")
    else:
        mensaje = (f"{ctx.usuario.email} te quito el rol de {etiqueta} de {titulo}. "
                   "Ya no tenes los permisos de ese rol para cargar invitados.")
        if rol.usuario.es_superadministrador:
            mensaje += " Conservas todos tus permisos de superadministrador."
        else:
            mensaje += " Si tenes otro rol en el evento, sus permisos se conservan."
        mensaje += f"\nPara consultar otros permisos vigentes, ingresa con Google usando {rol.usuario.email}: {enlace}"
    aviso = MovimientoInvitacion(evento_id=ctx.evento.id, actor_id=ctx.usuario.id,
        accion="aviso_agasajado", datos={"asignacion_id": rol.id, "alta": alta, "rol": etiqueta,
            "contacto": contacto, "mensaje": mensaje, "estado": "PENDIENTE"})
    db.add(aviso)
    return aviso


def resumen_aviso(aviso):
    datos = aviso.datos
    contacto = datos["contacto"]
    canal = contacto["canal"]
    mensaje = datos["mensaje"]
    url = None
    if canal == "whatsapp":
        url = f"https://wa.me/{contacto['destinatario']}?text={quote(mensaje, safe='')}"
    elif canal == "telegram":
        # El selector de Telegram permite elegir al destinatario antes de enviar.
        url = f"https://t.me/share/url?url=&text={quote(mensaje, safe='')}"
    elif canal == "instagram":
        url = "https://www.instagram.com/direct/inbox/"
    elif canal == "messenger":
        url = "https://www.messenger.com/"
    return {"id": aviso.id, **datos, "url_canal": url}


def enviar_aviso(db, aviso):
    # Los permisos y el aviso se confirman juntos antes de contactar SMTP.
    datos = dict(aviso.datos)
    if datos["contacto"]["canal"] == "email":
        try:
            _send_email(datos["contacto"]["destinatario"],
                "Permisos de " + datos.get("rol", "Agasajado") + ": " + ("alta" if datos["alta"] else "baja"),
                f"<p>{escape(datos['mensaje']).replace(chr(10), '<br>')}</p>", datos["mensaje"])
            datos.update(estado="ENVIADO", detalle="Aviso aceptado por el servidor de correo; entrega no confirmada.")
        except Exception:  # noqa: BLE001 - conservar el aviso y los permisos ante un fallo de envio
            datos.update(estado="FALLIDO", detalle="No se confirmo el envio del correo. Podes reintentar el aviso; los permisos ya se actualizaron.")
    else:
        datos.update(estado="PREPARADO", detalle="Pendiente de envio: abri la app y completa el envio al contacto indicado.")
    aviso.datos = datos
    db.commit()
    return resumen_aviso(aviso)
