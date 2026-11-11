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
from app.services.email import _send_email
from app.services.invitados import (
    ahora,
    auditar,
    cifrador,
    configuracion,
    credencial,
    digest,
    limitar,
    resolver_token,
    resumen_inv,
    utc,
)
from app.services.invitados_permisos import modulo_invitados
from app.services import verificacion_telefono
from app.services.whatsapp import numero_whatsapp
from app.services.agasajados import es_contacto_equipo


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


def regla_verificacion(inv, evento, cfg):
    # Cambiar el contacto, el PIN, el metodo o la politica invalida sesiones anteriores.
    return digest(":".join(["verificacion-v2", str(evento.id), str(inv.id),
        str(cfg["verificar_invitados"]), cfg["validacion"], inv.email or "",
        inv.telefono or "", inv.pin_personal_hash or ""]))


def cuenta_autorizada(usuario, inv):
    # usuario solo proviene de la dependencia que verifica una sesion Google vigente.
    return bool(usuario and usuario.activo and usuario.google_subject and usuario.email_validado_en
        and inv.email and (getattr(usuario, "_email_google_sesion", "")).strip().casefold() == inv.email.strip().casefold())


def telefono_registrado(inv, evento):
    try:
        return "+" + numero_whatsapp(inv.telefono, evento.codigo_pais, evento.pais)
    except ValueError:
        raise HTTPException(400, "El organizador debe registrar un telefono valido para esta invitacion") from None


def acceso_portal(db, slug, data, exigir=False, lock=False, usuario=None):
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, lock)
    regla = regla_verificacion(inv, evento, cfg)
    acceso_equipo = es_contacto_equipo(db, evento, inv.email)
    valido = sesion_valida(data, inv, enlace, regla)
    if cfg["validacion"] == "email" and cuenta_autorizada(usuario, inv):
        valido = True
    if not cfg["verificar_invitados"]:
        valido = True
    if not valido and exigir:
        raise HTTPException(401, "Valida el acceso a tu invitacion. Si no sos su destinatario, solicita una invitacion propia al organizador")
    if not valido:
        return {"validacion": cfg["validacion"], "requiere_pin": cfg["validacion"] == "pin", "validado": False, "acceso_equipo": acceso_equipo,
            "sin_contacto": (cfg["validacion"] == "email" and not inv.email)
                or (cfg["validacion"] == "telefono" and not inv.telefono)
                or (cfg["validacion"] == "pin" and not inv.pin_personal_hash)}
    resultado = resumen_inv(inv)
    qr = credencial(db, inv, "qr")
    resultado.update(
        acceso_equipo=acceso_equipo,
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
    metodo = cfg["validacion"]
    if not cfg["verificar_invitados"] or metodo not in {"email", "telefono"}:
        raise HTTPException(400, "Esta invitacion no requiere un codigo enviado por contacto")
    if metodo == "email":
        # No se permite vincular un correo elegido por el portador de un enlace copiado.
        destino = (inv.email or "").strip().lower()
        if not destino:
            raise HTTPException(400, "El organizador debe registrar tu email o asignar un PIN personal por otro canal")
        if data.email and str(data.email).strip().lower() != destino:
            raise HTTPException(400, "Usa el correo autorizado para esta invitacion")
        code = f"{secrets.randbelow(1000000):06d}"
        referencia = None
        codigo_hash = digest(str(inv.id) + ":" + enlace.token_hash + ":" + code)
        _send_email(destino, "Codigo de acceso a tu invitacion",
            f"<p>Tu codigo es <strong>{code}</strong>. Vence en {cfg['otp_minutos']} minutos.</p>",
            f"Codigo: {code}")
    else:
        destino = telefono_registrado(inv, evento)
        referencia = verificacion_telefono.enviar(destino)
        codigo_hash = digest(f"telefono:{inv.id}:{enlace.token_hash}:{destino}")
    otp = db.scalar(select(ValidacionInvitado).where(ValidacionInvitado.invitacion_id == inv.id))
    if otp is None:
        otp = ValidacionInvitado(invitacion_id=inv.id)
        db.add(otp)
    otp.codigo_hash, otp.email, otp.metodo, otp.proveedor_referencia = codigo_hash, destino, metodo, referencia
    otp.vence_at, otp.intentos, otp.usado = ahora() + timedelta(minutes=min(cfg["otp_minutos"], 10) if metodo == "telefono" else cfg["otp_minutos"]), 0, False
    auditar(db, evento.id, "codigo_aceptado_proveedor", invitacion_id=inv.id, metodo=metodo)
    db.commit()
    return {"message": "El proveedor acepto el envio del codigo al contacto registrado. Revisa tus mensajes."}


def validar_acceso(db, slug, data, ip, usuario=None):
    limitar(db, "otp-validar:" + ip, 30, 600)
    limitar(db, "validar-enlace:" + digest(data.token), 10, 600)
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, True)
    metodo = cfg["validacion"]
    if cfg["verificar_invitados"] and metodo == "pin":
        esperado = inv.pin_personal_hash
        if not esperado or not data.pin or not secrets.compare_digest(
                esperado, digest(f"pin-personal:{evento.id}:{inv.id}:{data.pin}")):
            raise HTTPException(401, "PIN personal incorrecto o no asignado. Contacta al organizador")
    elif cfg["verificar_invitados"] and not (metodo == "email" and cuenta_autorizada(usuario, inv)):
        otp = db.scalar(select(ValidacionInvitado).where(
            ValidacionInvitado.invitacion_id == inv.id).with_for_update())
        if (metodo not in {"email", "telefono"} or otp is None or otp.metodo != metodo or otp.usado
                or utc(otp.vence_at) < ahora() or otp.intentos >= cfg["otp_intentos"]):
            raise HTTPException(401, "Codigo invalido, agotado o vencido")
        otp.intentos += 1
        valido = False
        if data.codigo and metodo == "email":
            valido = bool(inv.email and otp.email.casefold() == inv.email.casefold()
                and secrets.compare_digest(otp.codigo_hash, digest(str(inv.id) + ":" + enlace.token_hash + ":" + data.codigo)))
        elif data.codigo and metodo == "telefono":
            telefono = telefono_registrado(inv, evento)
            vinculado = secrets.compare_digest(otp.codigo_hash, digest(f"telefono:{inv.id}:{enlace.token_hash}:{telefono}"))
            if vinculado and otp.email == telefono and otp.proveedor_referencia:
                try:
                    valido = verificacion_telefono.comprobar(otp.proveedor_referencia, data.codigo)
                except HTTPException:
                    db.commit()  # Conservar el intento incluso si el proveedor rechaza la consulta.
                    raise
        if not valido:
            db.commit()
            raise HTTPException(401, "Codigo invalido, agotado o vencido")
        otp.usado = True
    sesion = crear_sesion(inv, enlace, regla_verificacion(inv, evento, cfg))
    auditar(db, evento.id, "acceso_invitado", invitacion_id=inv.id, metodo=metodo)
    db.commit()
    data.sesion = sesion
    return acceso_portal(db, slug, data)


def qr_png(token):
    salida = io.BytesIO()
    qrcode.make(token).save(salida, format="PNG")
    return salida.getvalue()
