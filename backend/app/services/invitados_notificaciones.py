from html import escape

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.invitaciones import DistribucionInvitacion
from app.services.email import _send_email
from app.services.invitados import ahora, cifrador, credencial, digest, utc
from app.services.invitados_portal import qr_png


def notificar_qr(db, evento, inv):
    qr = credencial(db, inv, "qr")
    if not inv.activo or inv.aprobacion != "APROBADO" or not qr or utc(qr.vence_at) <= ahora():
        return "pendiente_aprobacion"
    if not inv.email:
        return "sin_email"
    clave = "confirmacion:" + digest(qr.token_hash + ":" + str(inv.cupo_aprobado) + ":" + inv.email)
    intento = db.scalar(
        select(DistribucionInvitacion).where(
            DistribucionInvitacion.invitacion_id == inv.id,
            DistribucionInvitacion.idempotencia == clave,
        )
    )
    if intento and intento.estado in {"ENVIADO", "PREPARADO"}:
        return intento.estado.lower()
    if intento is None:
        intento = DistribucionInvitacion(
            invitacion_id=inv.id,
            actor_id=evento.propietario_id,
            canal="email",
            tipo="qr",
            estado="PREPARADO",
            idempotencia=clave,
        )
        db.add(intento)
    intento.estado = "PREPARADO"
    try:
        db.commit()
    except IntegrityError:
        # Otro pedido reservo el mismo correo mientras se guardaba esta respuesta.
        db.rollback()
        return "preparado"
    titulo = evento.titulo_visual or evento.nombre
    texto = f"Hola {inv.nombre}! Tu asistencia a {titulo} esta confirmada. Cupo aprobado: {inv.cupo_aprobado}. Adjuntamos tu QR de ingreso."
    try:
        _send_email(
            inv.email,
            f"Tu invitacion con QR: {titulo}",
            f"<p>{escape(texto)}</p>",
            texto,
            attachment=qr_png(cifrador().decrypt(qr.token_cifrado.encode()).decode()),
        )
        intento.estado = "ENVIADO"
        intento.detalle = "QR aceptado por SMTP; entrega no confirmada"
    except Exception:  # noqa: BLE001 - el fallo de notificacion no deshace el RSVP
        intento.estado = "FALLIDO"
        intento.detalle = "No se pudo enviar el QR; la confirmacion permanece guardada"
    db.commit()
    return intento.estado.lower()
