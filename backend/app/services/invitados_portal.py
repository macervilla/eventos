import io
import secrets
from datetime import datetime, timedelta

import qrcode
from fastapi import HTTPException
from sqlalchemy import select

from app.core.seguridad import _firmar, _leer
from app.models.enums import EventoEstado
from app.models.eventos import Evento
from app.models.invitaciones import Invitacion, ValidacionInvitado
from app.schemas.invitados import InvitadoDatos
from app.services.email import _send_email
from app.services.invitados import (
    ahora,
    auditar,
    cifrador,
    clave_duplicado,
    configuracion,
    credencial,
    digest,
    limitar,
    resolver_token,
    resumen_inv,
    utc,
)
from app.services.invitados_permisos import modulo_invitados


def resolver_portal(db, slug, data, lock=False):
    inv, enlace = resolver_token(db, slug, data.token, "enlace", lock)
    evento = db.get(Evento, inv.evento_id)
    modulo = modulo_invitados(db, evento)
    if evento.estado == EventoEstado.BORRADOR or not modulo or not modulo.activo:
        raise HTTPException(404, "Invitacion no disponible")
    return inv, enlace, evento, configuracion(db, evento)


def sesion_valida(data, inv, enlace, regla):
    if not data.sesion:
        return False
    try:
        valores = _leer(data.sesion, "invitado")
        return (
            valores.get("sub") == str(inv.id)
            and valores.get("enlace") == enlace.token_hash
            and valores.get("regla") == regla
        )
    except HTTPException:
        return False


def crear_sesion(inv, enlace, regla):
    return _firmar(
        {"tipo": "invitado", "sub": str(inv.id), "enlace": enlace.token_hash, "regla": regla}, 30
    )


def acceso_portal(db, slug, data, exigir=False, lock=False, usuario=None):
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, lock)
    pin_hash = (modulo_invitados(db, evento).configuracion_json or {}).get("pin_hash")
    regla = digest(cfg["validacion"] + ":" + (pin_hash or ""))
    valido = sesion_valida(data, inv, enlace, regla)
    if (
        cfg["validacion"] == "email"
        and usuario
        and usuario.activo
        and inv.email
        and usuario.email.strip().casefold() == inv.email.strip().casefold()
        and not pin_hash
    ):
        valido = True
    if cfg["validacion"] == "enlace" and not pin_hash:
        valido = True
    if not valido and exigir:
        raise HTTPException(401, "Valida el acceso antes de continuar")
    if not valido:
        return {"validacion": cfg["validacion"], "requiere_pin": bool(pin_hash), "validado": False}
    resultado = resumen_inv(inv)
    qr = credencial(db, inv, "qr")
    resultado.update(
        validado=True,
        sesion=crear_sesion(inv, enlace, regla),
        qr=cifrador().decrypt(qr.token_cifrado.encode()).decode()
        if qr and inv.aprobacion == "APROBADO" and utc(qr.vence_at) > ahora()
        else None,
        puede_modificar=(cfg["permitir_modificaciones"] or inv.rsvp == "PENDIENTE")
        and (not cfg["cierre_rsvp"] or utc(datetime.fromisoformat(cfg["cierre_rsvp"])) >= ahora())
        and evento.estado not in {EventoEstado.FINALIZADO, EventoEstado.ARCHIVADO},
        validacion=cfg["validacion"],
    )
    return resultado


def enviar_codigo(db, slug, data, ip):
    limitar(db, "otp-envio:" + ip, 10, 600)
    limitar(db, "otp-invitacion:" + digest(data.token), 3, 600)
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, True)
    if cfg["validacion"] == "telefono":
        # Punto de extension para un proveedor oficial. Nunca se simula un envio.
        raise HTTPException(
            503, "La validacion por telefono requiere un proveedor oficial; contacta al organizador"
        )
    if cfg["validacion"] != "email":
        raise HTTPException(400, "Esta invitacion no requiere un codigo de email")
    email = str(data.email or "").strip().lower()
    if not email or (inv.email and inv.email.lower() != email):
        raise HTTPException(400, "Usa el correo autorizado para esta invitacion")
    code = f"{secrets.randbelow(1000000):06d}"
    otp = db.scalar(select(ValidacionInvitado).where(ValidacionInvitado.invitacion_id == inv.id))
    if otp is None:
        otp = ValidacionInvitado(invitacion_id=inv.id)
        db.add(otp)
    otp.codigo_hash = digest(str(inv.id) + ":" + enlace.token_hash + ":" + code)
    otp.email, otp.vence_at, otp.intentos, otp.usado = (
        email,
        ahora() + timedelta(minutes=cfg["otp_minutos"]),
        0,
        False,
    )
    _send_email(
        email,
        "Codigo de acceso a tu invitacion",
        f"<p>Tu codigo es <strong>{code}</strong>. Vence en {cfg['otp_minutos']} minutos.</p>",
        f"Codigo: {code}",
    )
    auditar(db, evento.id, "codigo_email_aceptado_smtp", invitacion_id=inv.id)
    db.commit()
    return {"message": "El servidor de correo acepto el codigo para envio. Revisa tu bandeja."}


def validar_acceso(db, slug, data, ip, usuario=None):
    limitar(db, "otp-validar:" + ip, 30, 600)
    limitar(db, "validar-enlace:" + digest(data.token), 10, 600)
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, True)
    pin_hash = (modulo_invitados(db, evento).configuracion_json or {}).get("pin_hash")
    if pin_hash and (
        not data.pin
        or not secrets.compare_digest(pin_hash, digest("pin:" + str(evento.id) + ":" + data.pin))
    ):
        raise HTTPException(401, "Codigo de acceso incorrecto")
    cuenta_autorizada = (
        usuario
        and usuario.activo
        and inv.email
        and usuario.email.strip().casefold() == inv.email.strip().casefold()
    )
    if cfg["validacion"] == "email" and not cuenta_autorizada:
        otp = db.scalar(
            select(ValidacionInvitado)
            .where(ValidacionInvitado.invitacion_id == inv.id)
            .with_for_update()
        )
        if (
            otp is None
            or otp.usado
            or utc(otp.vence_at) < ahora()
            or otp.intentos >= cfg["otp_intentos"]
        ):
            raise HTTPException(401, "Codigo invalido, agotado o vencido")
        otp.intentos += 1
        if not data.codigo or not secrets.compare_digest(
            otp.codigo_hash, digest(str(inv.id) + ":" + enlace.token_hash + ":" + data.codigo)
        ):
            db.commit()
            raise HTTPException(401, "Codigo invalido, agotado o vencido")
        otp.usado = True
        if inv.email is None:
            key = clave_duplicado(InvitadoDatos(nombre=inv.nombre, email=otp.email))
            repetido = db.scalar(
                select(Invitacion.id).where(
                    Invitacion.evento_id == evento.id,
                    Invitacion.clave_duplicado == key,
                    Invitacion.id != inv.id,
                )
            )
            if repetido:
                raise HTTPException(
                    409,
                    "El correo ya esta asociado a otra invitacion del evento. Contacta al organizador",
                )
            inv.email = otp.email
            inv.clave_duplicado = key
    elif cfg["validacion"] == "telefono":
        raise HTTPException(503, "Proveedor telefonico no configurado; contacta al organizador")
    sesion = crear_sesion(inv, enlace, digest(cfg["validacion"] + ":" + (pin_hash or "")))
    auditar(db, evento.id, "acceso_invitado", invitacion_id=inv.id, metodo=cfg["validacion"])
    db.commit()
    data.sesion = sesion
    return acceso_portal(db, slug, data)


def qr_png(token):
    salida = io.BytesIO()
    qrcode.make(token).save(salida, format="PNG")
    return salida.getvalue()
