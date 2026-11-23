import io
import secrets
from datetime import datetime, timedelta

import qrcode
from fastapi import HTTPException
from sqlalchemy import select

from app.core.seguridad import _firmar, _leer
from app.models.enums import EventoEstado
from app.models.eventos import Evento
from app.models.invitaciones import DistribucionInvitacion, Invitacion, ValidacionInvitado
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
    return digest(":".join(["verificacion-v3", str(evento.id), str(inv.id), str(inv.usuario_id or ""),
        str(cfg["verificar_invitados"]), cfg["validacion"], inv.email or "",
        inv.telefono or "", inv.pin_personal_hash or ""]))


def cuenta_autorizada(usuario, inv):
    # usuario solo proviene de la dependencia que verifica una sesion Google vigente.
    if not (usuario and usuario.activo and usuario.google_subject and usuario.email_validado_en
            and getattr(usuario, "_email_google_sesion", "")):
        return False
    if inv.usuario_id is not None:
        return usuario.id == inv.usuario_id
    return bool(inv.email and usuario._email_google_sesion.strip().casefold() == inv.email.strip().casefold())


def email_oculto(email):
    if not email or "@" not in email:
        return None
    nombre, dominio = email.strip().split("@", 1)
    host, _, extension = dominio.rpartition(".")
    return nombre[:1] + "***@" + (host or dominio)[:1] + "***" + ("." + extension if host else "")


def sesion_email_valida(data, inv, enlace, regla):
    if not inv.email or not sesion_valida(data, inv, enlace, regla):
        return False
    try:
        datos = _leer(data.sesion, "invitado")
    except HTTPException:
        return False
    return datos.get("metodo") == "email-confirmacion-v1" and datos.get("email") == inv.email.strip().casefold()


def crear_sesion_email(inv, enlace, regla):
    return _firmar({"tipo": "invitado", "sub": str(inv.id), "enlace": enlace.token_hash,
                   "regla": regla, "metodo": "email-confirmacion-v1",
                   "email": inv.email.strip().casefold()}, 30)


def acceso_confirmacion(db, slug, data, exigir=False, lock=False, usuario=None):
    """El enlace identifica la invitacion; solo Google acredita la cuenta autorizada."""
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, lock or usuario is not None)
    if cuenta_autorizada(usuario, inv) and inv.usuario_id is None:
        inv.usuario = usuario
        auditar(db, evento.id, "cuenta_invitado_vinculada", usuario.id, inv.id, origen="correo_autorizado")
        if lock:
            db.flush()
        else:
            db.commit()
    regla = regla_verificacion(inv, evento, cfg)
    diferente = bool(usuario and not cuenta_autorizada(usuario, inv))
    valido = cuenta_autorizada(usuario, inv)
    bloqueada = inv.aprobacion in {"REVOCADO", "RECHAZADO"} or inv.rsvp in {"RECHAZADO", "CANCELADO"}
    if exigir and not valido:
        raise HTTPException(401, "Esta invitacion no esta autorizada para tu identidad. Contacta al agasajado")
    if exigir and bloqueada:
        raise HTTPException(409, "La invitacion no esta habilitada. Contacta al organizador")
    if not valido:
        return {"validado": False, "validacion": "google", "requiere_pin": False,
                "sin_contacto": not bool(inv.email), "cuenta_diferente": diferente,
                "sin_invitacion": diferente, "requiere_identidad": True,
                "email_asociado": None, "puede_confirmar": False,
                "acceso_equipo": es_contacto_equipo(db, evento, inv.email),
                "no_disponible": bloqueada}
    sesion = crear_sesion_email(inv, enlace, regla) if inv.email else crear_sesion(inv, enlace, regla)
    resultado = acceso_portal(db, slug, data.model_copy(update={"sesion": sesion}), usuario=usuario)
    resultado.update(sesion=sesion, validacion="google", email_asociado=inv.email)
    resultado.update(cuenta_diferente=False, no_disponible=bloqueada,
                     puede_confirmar=not bloqueada and resultado["puede_modificar"])
    if bloqueada:
        resultado["qr"] = None
        resultado["puede_modificar"] = False
    return resultado


def telefono_registrado(inv, evento):
    try:
        return "+" + numero_whatsapp(inv.telefono, evento.codigo_pais, evento.pais)
    except ValueError:
        raise HTTPException(400, "El organizador debe registrar un telefono valido para esta invitacion") from None


def acceso_por_whatsapp(db, inv):
    """La invitacion personal fue preparada por un usuario autorizado para WhatsApp."""
    return db.scalar(select(DistribucionInvitacion.id).where(
        DistribucionInvitacion.invitacion_id == inv.id,
        DistribucionInvitacion.canal == "whatsapp",
        DistribucionInvitacion.tipo == "invitacion",
        DistribucionInvitacion.estado.in_(["PREPARADO", "ENVIADO"]),
    ).limit(1)) is not None


def acceso_portal(db, slug, data, exigir=False, lock=False, usuario=None):
    """Acceso multimedia existente. Los endpoints RSVP/QR usan acceso_confirmacion."""
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, lock)
    regla = regla_verificacion(inv, evento, cfg)
    acceso_equipo = es_contacto_equipo(db, evento, inv.email)
    por_whatsapp = acceso_por_whatsapp(db, inv)
    valido = por_whatsapp or sesion_valida(data, inv, enlace, regla)
    if cfg["validacion"] == "email" and cuenta_autorizada(usuario, inv):
        valido = True
    if not cfg["verificar_invitados"]:
        valido = True
    if por_whatsapp:
        valido = cuenta_autorizada(usuario, inv)
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
        validacion="enlace" if por_whatsapp else cfg["validacion"],
        acceso_por_whatsapp=por_whatsapp,
    )
    return resultado


def enviar_codigo(db, slug, data, ip, confirmacion=False):
    limitar(db, "otp-envio:" + ip, 10, 600)
    limitar(db, "otp-invitacion:" + digest(data.token), 3, 600)
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, True)
    if confirmacion:
        cfg = {**cfg, "validacion": "email", "verificar_invitados": True}
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


def validar_acceso(db, slug, data, ip, usuario=None, confirmacion=False):
    limitar(db, "otp-validar:" + ip, 30, 600)
    limitar(db, "validar-enlace:" + digest(data.token), 10, 600)
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, True)
    if confirmacion and cuenta_autorizada(usuario, inv):
        return acceso_confirmacion(db, slug, data, usuario=usuario)
    if confirmacion:
        if not inv.email:
            raise HTTPException(400, "El organizador debe registrar el correo de esta invitacion")
        if usuario and not cuenta_autorizada(usuario, inv):
            raise HTTPException(401, "Ingresa con la cuenta asociada a la invitacion")
        cfg = {**cfg, "validacion": "email", "verificar_invitados": True}
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
    # La huella usa la configuracion persistida; cambiarla invalida las sesiones.
    regla = regla_verificacion(inv, evento, configuracion(db, evento))
    sesion = crear_sesion_email(inv, enlace, regla) if confirmacion else crear_sesion(inv, enlace, regla)
    auditar(db, evento.id, "acceso_invitado", invitacion_id=inv.id, metodo=metodo)
    db.commit()
    data.sesion = sesion
    if confirmacion:
        return acceso_confirmacion(db, slug, data, usuario=usuario)
    return acceso_portal(db, slug, data)


def qr_png(token):
    salida = io.BytesIO()
    qrcode.make(token).save(salida, format="PNG")
    return salida.getvalue()


def confirmar_personas(db, slug, data, usuario=None):
    """Confirmacion nominal del cupo previamente asignado, con QR automatico."""
    from app.models.invitaciones import Participante
    from app.schemas.invitados import RSVP
    from app.services import invitados as s

    acceso_confirmacion(db, slug, data, True, True, usuario=usuario)
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, True)
    if len(data.personas) > inv.cantidad_permitida or len(data.personas) < inv.ingresados:
        raise HTTPException(409, "La cantidad supera el cupo o es menor que las personas ya ingresadas")
    if inv.aprobacion == "REVOCADO" or (inv.aprobacion == "RECHAZADO" and inv.rsvp not in {"RECHAZADO", "CANCELADO"}):
        raise HTTPException(409, "El organizador debe habilitar nuevamente tu invitacion")
    identidades = [(p.nombre, p.apellido, p.tipo) for p in data.personas]
    actuales = [(inv.nombre, inv.apellido, "ADULTO")] + [
        (p.nombre, p.apellido, p.tipo or "ADULTO") for p in inv.participantes if p.activo]
    qr = s.credencial(db, inv, "qr")
    repetida = (identidades == actuales and inv.rsvp in {"CONFIRMADO", "MODIFICADO"}
                and inv.aprobacion == "APROBADO" and qr and utc(qr.vence_at) > ahora())
    if not repetida:
        # El RSVP reutiliza limites de cupo, cierre, modificaciones e ingresos previos.
        menores = [p for p in data.personas if p.tipo == "MENOR"]
        rsvp = RSVP(asiste=True, adultos=len(data.personas) - len(menores),
                    menores=[p.nombre[:80] for p in menores])
        previo = inv.rsvp
        s.aplicar_rsvp(db, evento, inv, rsvp)
        if previo in {"CONFIRMADO", "MODIFICADO"}:
            inv.rsvp = "MODIFICADO"
        inv.confirmado_at = ahora()
        inv.nombre, inv.apellido = data.personas[0].nombre, data.personas[0].apellido
        for p in inv.participantes:
            p.activo = False
        for persona in data.personas[1:]:
            inv.participantes.append(Participante(nombre=persona.nombre, apellido=persona.apellido,
                                                  tipo=persona.tipo, activo=True))
        inv.aprobacion, inv.cupo_aprobado = "APROBADO", len(data.personas)
        s.emitir(db, inv, "qr")
        auditar(db, evento.id, "confirmacion_nominal", invitacion_id=inv.id,
                personas=len(data.personas), cupo=inv.cupo_aprobado)
    db.commit()
    return acceso_confirmacion(db, slug, data, True, usuario=usuario), evento, inv
