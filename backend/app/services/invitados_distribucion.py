from html import escape
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.invitaciones import DistribucionInvitacion
from app.services.email import _send_email
from app.services.invitados import (
    ahora,
    auditar,
    cifrador,
    credencial,
    emitir,
    obtener,
    utc,
)
from app.services.invitados_portal import qr_png
from app.services.portada_invitacion import imagen_invitacion
from app.services.whatsapp import numero_whatsapp


def distribuir(db, ctx, data):
    portada = imagen_invitacion(ctx.evento)
    portada_publica = settings.frontend_public_url.rstrip("/") + portada
    resultados = []
    for invitacion_id in dict.fromkeys(data.ids):
        inv = obtener(db, ctx, invitacion_id, True)
        existente = db.scalar(
            select(DistribucionInvitacion).where(
                DistribucionInvitacion.invitacion_id == inv.id,
                DistribucionInvitacion.idempotencia == data.idempotencia,
            )
        )
        if existente:
            if existente.canal != data.canal or existente.tipo != data.tipo:
                raise HTTPException(409, "La clave de operacion ya se uso para otro canal o tipo")
            detalle = existente.detalle or (
                "Envio pendiente o resultado aun no confirmado; no se repitio automaticamente"
                if existente.canal == "email"
                else "Preparacion ya registrada"
            )
            resultados.append(
                {"id": inv.id, "estado": existente.estado, "detalle": detalle, "reintento": True}
            )
            continue
        telefono_whatsapp = None
        if data.canal == "whatsapp":
            try:
                telefono_whatsapp = numero_whatsapp(inv.whatsapp or inv.telefono, ctx.evento.codigo_pais, ctx.evento.pais)
            except ValueError as exc:
                detalle = str(exc)
                db.add(DistribucionInvitacion(invitacion_id=inv.id, actor_id=ctx.usuario.id,
                       canal=data.canal, tipo=data.tipo, estado="FALLIDO", detalle=detalle, idempotencia=data.idempotencia))
                inv.distribucion, inv.canal = "FALLIDO", data.canal
                inv.actualizado_por = ctx.usuario.id
                auditar(db, ctx.evento.id, "distribucion", ctx.usuario.id, inv.id, canal=data.canal, estado="FALLIDO", tipo=data.tipo)
                db.commit()
                resultados.append({"id": inv.id, "estado": "FALLIDO", "detalle": detalle,
                                   "destinatario": f"{inv.nombre} {inv.apellido or ''}".strip(), "canal": data.canal})
                continue
        if data.tipo == "qr":
            actual = credencial(db, inv, "qr")
            if (
                not inv.activo
                or inv.aprobacion != "APROBADO"
                or not actual
                or utc(actual.vence_at) <= ahora()
            ):
                detalle = "No hay QR activo. Aprobar o regenerar la credencial primero"
                db.add(
                    DistribucionInvitacion(
                        invitacion_id=inv.id,
                        actor_id=ctx.usuario.id,
                        canal=data.canal,
                        tipo=data.tipo,
                        estado="FALLIDO",
                        detalle=detalle,
                        idempotencia=data.idempotencia,
                    )
                )
                auditar(
                    db,
                    ctx.evento.id,
                    "distribucion",
                    ctx.usuario.id,
                    inv.id,
                    canal=data.canal,
                    estado="FALLIDO",
                    tipo=data.tipo,
                )
                db.commit()
                resultados.append({"id": inv.id, "estado": "FALLIDO", "detalle": detalle})
                continue
            token = cifrador().decrypt(actual.token_cifrado.encode()).decode()
        else:
            token = emitir(db, inv, "enlace")
        # El enlace es privado; los metadatos apuntan a la pagina generica del evento.
        enlace = (
            f"{settings.frontend_public_url.rstrip('/')}/e/{ctx.evento.slug}/i/{token}"
            if data.tipo == "invitacion"
            else f"{settings.frontend_public_url.rstrip('/')}/e/{ctx.evento.slug}/i/{emitir(db, inv, 'enlace')}"
        )
        enlace += "#mi-confirmacion"
        titulo = ctx.evento.titulo_visual or ctx.evento.nombre
        mensaje = f"Hola {inv.nombre}! {titulo}.\n\nPresiona aqui para confirmar:\n{enlace}"
        intento = DistribucionInvitacion(
            invitacion_id=inv.id,
            actor_id=ctx.usuario.id,
            canal=data.canal,
            tipo=data.tipo,
            estado="PREPARADO",
            idempotencia=data.idempotencia,
        )
        db.add(intento)
        inv.distribucion, inv.canal = "PREPARADO", data.canal
        inv.actualizado_por = ctx.usuario.id
        db.commit()  # Reserva idempotente antes de comunicar con SMTP.
        if data.canal == "email":
            try:
                if not inv.email:
                    raise HTTPException(422, "El invitado no tiene email")
                destino = escape(enlace, quote=True)
                imagen = f'<a href="{destino}"><img alt="Portada del evento" width="600" style="max-width:100%;height:auto" src="{escape(portada_publica, quote=True)}"></a>'
                html = f'{imagen}<h1>{escape(titulo)}</h1><p>{escape((ctx.evento.descripcion or "")[:300])}</p><p>Presiona <a href="{destino}">aquí</a> para confirmar.</p>'
                _send_email(
                    inv.email,
                    titulo,
                    html,
                    mensaje,
                    attachment=qr_png(token) if data.tipo == "qr" else None,
                )
                intento.estado, intento.detalle = (
                    "ENVIADO",
                    "Aceptado por SMTP; entrega no confirmada",
                )
            except Exception:
                intento.estado, intento.detalle = (
                    "FALLIDO",
                    "El servidor de correo no confirmo el envio; puede reintentarse con una nueva operacion",
                )
            inv.distribucion = intento.estado
        auditar(
            db,
            ctx.evento.id,
            "distribucion",
            ctx.usuario.id,
            inv.id,
            canal=data.canal,
            estado=intento.estado,
            tipo=data.tipo,
        )
        db.commit()
        resultado = {
            "destinatario": f"{inv.nombre} {inv.apellido or ''}".strip(),
            "portada_url": portada_publica,
            "titulo": titulo,
            "canal": data.canal,
            "id": inv.id,
            "estado": intento.estado,
            "detalle": intento.detalle,
            "mensaje": mensaje,
            "enlace": enlace,
        }
        if data.canal == "whatsapp":
            resultado["telefono_destino"] = "+" + telefono_whatsapp
            resultado["url_canal"] = f"https://wa.me/{telefono_whatsapp}?text={quote(mensaje, safe='')}"
            resultado["detalle"] = "Pendiente de envio manual. Abri el chat del destinatario y pulsa Enviar en WhatsApp."
        elif data.canal == "instagram":
            resultado["url_canal"] = "https://www.instagram.com/"
        elif data.canal == "messenger":
            resultado["url_canal"] = "https://www.messenger.com/"
        elif data.canal == "telegram":
            resultado["url_canal"] = f"https://t.me/share/url?url={quote(enlace, safe='')}&text={quote('Hola ' + inv.nombre + '! ' + titulo, safe='')}"
        resultados.append(resultado)
    return {"resultados": resultados}
