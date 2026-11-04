import base64
import hashlib
import hmac
import secrets
import time
import unicodedata
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.enums import EstadoConfirmacion, EventoEstado
from app.models.eventos import Evento, EventoModulo, EventoUsuario
from app.models.invitaciones import (
    CredencialInvitacion,
    Invitacion,
    LimiteAcceso,
    MovimientoIngreso,
    MovimientoInvitacion,
    Participante,
    SolicitudRSVP,
)
from app.schemas.invitados import RSVP, Aprobacion, ConfigInvitados, InvitadoDatos
from app.services.invitados_permisos import modulo_invitados


def ahora():
    return datetime.now(timezone.utc)


def utc(valor):
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor


def digest(valor):
    return hmac.new(settings.secret_key.encode(), valor.encode(), hashlib.sha256).hexdigest()


def cifrador():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest()))


def auditar(db, evento_id, accion, actor=None, invitacion_id=None, **datos):
    db.add(
        MovimientoInvitacion(
            evento_id=evento_id,
            invitacion_id=invitacion_id,
            actor_id=actor,
            accion=accion,
            datos=datos,
        )
    )


def configuracion(db, evento):
    modulo = modulo_invitados(db, evento)
    raw = dict(modulo.configuracion_json or {}) if modulo else {}
    raw.pop("pin_hash", None)
    resultado = {
        **ConfigInvitados(**raw).model_dump(mode="json"),
        "activo": bool(modulo and modulo.activo),
        "tiene_pin": bool(modulo and (modulo.configuracion_json or {}).get("pin_hash")),
    }
    if (
        resultado["requiere_login"]
        and resultado["validacion"] == "enlace"
        and not resultado["tiene_pin"]
    ):
        resultado["validacion"] = "email"
    return resultado


def guardar_config(db, ctx, data: ConfigInvitados):
    modulo = modulo_invitados(db, ctx.evento)
    if modulo is None:
        modulo = EventoModulo(
            evento_id=ctx.evento.id, modulo="invitados", activo=data.activo, configuracion_json={}
        )
        db.add(modulo)
    cfg = data.model_dump(mode="json", exclude={"pin_acceso", "quitar_pin"})
    cfg["pin_hash"] = (modulo.configuracion_json or {}).get("pin_hash")
    if data.pin_acceso:
        cfg["pin_hash"] = digest("pin:" + str(ctx.evento.id) + ":" + data.pin_acceso)
    if data.quitar_pin:
        cfg.pop("pin_hash", None)
    modulo.activo = data.activo
    modulo.configuracion_json = cfg
    auditar(db, ctx.evento.id, "configuracion", ctx.usuario.id)
    db.commit()
    return configuracion(db, ctx.evento)


def normalizar(valor):
    return " ".join(
        "".join(
            c for c in unicodedata.normalize("NFKD", str(valor)) if not unicodedata.combining(c)
        )
        .lower()
        .split()
    )


def clave_duplicado(data):
    valor = (
        "email:" + str(data.email).strip().lower()
        if data.email
        else "tel:" + "".join(c for c in data.telefono if c.isdigit())
        if data.telefono
        else "nombre:" + normalizar(data.nombre + " " + data.apellido + " " + (data.grupo or ""))
    )
    return hashlib.sha256(valor.encode()).hexdigest()


def consulta(ctx):
    q = select(Invitacion).where(Invitacion.evento_id == ctx.evento.id)
    if ctx.propio:
        q = q.where(Invitacion.responsable_id == ctx.usuario.id)
    return q


def obtener(db, ctx, invitacion_id, lock=False):
    q = consulta(ctx).where(Invitacion.id == invitacion_id)
    inv = db.scalar(q.with_for_update() if lock else q)
    if inv is None:
        raise HTTPException(404, "Invitacion no encontrada")
    return inv


def estado_ingreso(inv):
    return (
        "SIN_INGRESAR"
        if inv.ingresados == 0
        else "COMPLETO"
        if inv.ingresados >= inv.cupo_aprobado
        else "PARCIAL"
    )


def resumen_inv(inv, personales=True):
    data = {
        "id": inv.id,
        "nombre": inv.nombre,
        "apellido": inv.apellido,
        "grupo": inv.grupo,
        "cantidad_permitida": inv.cantidad_permitida,
        "solicitados": inv.adultos + inv.menores,
        "cupo_aprobado": inv.cupo_aprobado,
        "ingresados": inv.ingresados,
        "restantes": max(0, inv.cupo_aprobado - inv.ingresados),
        "estado_ingreso": estado_ingreso(inv),
        "rsvp": inv.rsvp,
        "aprobacion": inv.aprobacion,
        "activo": inv.activo,
        "distribucion": inv.distribucion,
        "canal": inv.canal,
        "responsable_id": inv.responsable_id,
        "adultos": inv.adultos,
        "menores": inv.menores,
        "confirmado_at": inv.confirmado_at,
    }
    if personales:
        data.update(
            email=inv.email,
            telefono=inv.telefono,
            instagram=inv.instagram,
            whatsapp=inv.whatsapp,
            facebook=inv.facebook,
            telegram=inv.telegram,
            otro_contacto=inv.otro_contacto,
            nombres_menores=[p.nombre for p in inv.participantes if p.activo and p.tipo == "MENOR"],
        )
    return data


def guardar_invitado(db, ctx, data: InvitadoDatos, inv=None):
    responsable = data.responsable_id or (inv.responsable_id if inv else ctx.usuario.id)
    if ctx.propio and responsable != ctx.usuario.id:
        raise HTTPException(403, "Solo podes gestionar tu propia lista")
    if responsable != ctx.evento.propietario_id and responsable != ctx.usuario.id:
        asignado = db.scalar(
            select(EventoUsuario.id).where(
                EventoUsuario.evento_id == ctx.evento.id, EventoUsuario.usuario_id == responsable
            )
        )
        if asignado is None:
            raise HTTPException(422, "El responsable debe estar asignado a este evento")
    clave = clave_duplicado(data)
    duplicado = db.scalar(
        select(Invitacion.id).where(
            Invitacion.evento_id == ctx.evento.id, Invitacion.clave_duplicado == clave
        )
    )
    if duplicado is not None and (inv is None or duplicado != inv.id):
        raise HTTPException(409, "Ya existe un invitado con esos datos en el evento")
    nuevo = inv is None
    if nuevo:
        inv = Invitacion(evento_id=ctx.evento.id, creado_por=ctx.usuario.id)
        db.add(inv)
    elif data.cantidad_permitida < max(inv.cupo_aprobado, inv.adultos + inv.menores):
        raise HTTPException(409, "El cupo maximo no puede ser menor que el solicitado o aprobado")
    if not data.nombre.strip():
        raise HTTPException(422, "El nombre no puede estar vacio")
    for campo, valor in data.model_dump().items():
        setattr(inv, campo, valor.strip() if isinstance(valor, str) else valor)
    inv.responsable_id, inv.actualizado_por, inv.clave_duplicado = (
        responsable,
        ctx.usuario.id,
        clave,
    )
    db.flush()
    auditar(db, ctx.evento.id, "alta" if nuevo else "edicion", ctx.usuario.id, inv.id)
    return inv


def credencial(db, inv, tipo):
    return db.scalar(
        select(CredencialInvitacion)
        .where(
            CredencialInvitacion.invitacion_id == inv.id,
            CredencialInvitacion.tipo == tipo,
            CredencialInvitacion.activo.is_(True),
        )
        .order_by(CredencialInvitacion.id.desc())
    )


def revocar(db, inv, tipo):
    for c in db.scalars(
        select(CredencialInvitacion).where(
            CredencialInvitacion.invitacion_id == inv.id,
            CredencialInvitacion.tipo == tipo,
            CredencialInvitacion.activo.is_(True),
        )
    ):
        c.activo = False


def emitir(db, inv, tipo, renovar=False):
    if not inv.activo or (tipo == "qr" and (inv.aprobacion != "APROBADO" or inv.cupo_aprobado < 1)):
        raise HTTPException(409, "La invitacion debe estar activa y aprobada para emitir QR")
    c = credencial(db, inv, tipo)
    if c and utc(c.vence_at) > ahora() and not renovar:
        return cifrador().decrypt(c.token_cifrado.encode()).decode()
    revocar(db, inv, tipo)
    token = secrets.token_urlsafe(32)
    evento = db.get(Evento, inv.evento_id)
    vence = (
        (utc(evento.fecha_fin or evento.fecha_inicio) + timedelta(days=2))
        if tipo == "qr" and (evento.fecha_fin or evento.fecha_inicio)
        else ahora() + timedelta(days=365)
    )
    if vence <= ahora():
        raise HTTPException(409, "El evento ya finalizo")
    db.add(
        CredencialInvitacion(
            invitacion_id=inv.id,
            tipo=tipo,
            token_hash=digest(token),
            token_cifrado=cifrador().encrypt(token.encode()).decode(),
            activo=True,
            vence_at=vence,
        )
    )
    db.flush()
    return token


def aplicar_rsvp(db, evento, inv, data: RSVP, actor=None):
    aprobacion_previa = inv.aprobacion
    cupo_previo = inv.cupo_aprobado
    cfg = configuracion(db, evento)
    if cfg["cierre_rsvp"] and ahora() > utc(datetime.fromisoformat(cfg["cierre_rsvp"])):
        raise HTTPException(409, "Finalizo el plazo para confirmar asistencia")
    if evento.estado in {EventoEstado.FINALIZADO, EventoEstado.ARCHIVADO}:
        raise HTTPException(409, "El evento ya no acepta confirmaciones")
    if inv.rsvp != "PENDIENTE" and not cfg["permitir_modificaciones"] and actor is None:
        raise HTTPException(409, "Contacta al organizador para modificar tu confirmacion")
    adultos, menores = (data.adultos, len(data.menores)) if data.asiste else (0, 0)
    total = adultos + menores
    if total > inv.cantidad_permitida or total < inv.ingresados:
        raise HTTPException(
            409, "La cantidad supera el cupo o es menor que las personas ya ingresadas"
        )
    nombres = [p.nombre for p in inv.participantes if p.activo and p.tipo == "MENOR"]
    if inv.rsvp != "PENDIENTE" and (inv.adultos, inv.menores, nombres) == (
        adultos,
        menores,
        data.menores if data.asiste else [],
    ):
        return inv
    previo = inv.rsvp
    inv.adultos, inv.menores = adultos, menores
    inv.actualizado_por = actor
    inv.rsvp = (
        ("MODIFICADO" if previo not in {"PENDIENTE", "RECHAZADO"} else "CONFIRMADO")
        if data.asiste
        else ("CANCELADO" if previo in {"CONFIRMADO", "MODIFICADO", "CANCELADO"} else "RECHAZADO")
    )
    inv.estado_confirmacion = (
        EstadoConfirmacion.CONFIRMADO if data.asiste else EstadoConfirmacion.NO_ASISTE
    )
    inv.confirmado_at = ahora()
    for p in inv.participantes:
        p.activo = False
    for nombre in data.menores if data.asiste else []:
        inv.participantes.append(Participante(nombre=nombre, tipo="MENOR", activo=True))
    if not data.asiste:
        inv.aprobacion, inv.cupo_aprobado = "RECHAZADO", 0
        revocar(db, inv, "qr")
    elif cfg["aprobacion"] == "automatica":
        inv.aprobacion, inv.cupo_aprobado = "APROBADO", total
        emitir(db, inv, "qr")
    elif inv.aprobacion != "APROBADO" or total > inv.cupo_aprobado:
        inv.aprobacion, inv.cupo_aprobado = "PENDIENTE", inv.ingresados
        revocar(db, inv, "qr")
    else:
        inv.cupo_aprobado = total
    db.add(
        SolicitudRSVP(
            invitacion_id=inv.id, adultos=adultos, menores=menores, estado=inv.rsvp, actor_id=actor
        )
    )
    auditar(db, evento.id, "rsvp", actor, inv.id, adultos=adultos, menores=menores, estado=inv.rsvp)
    if aprobacion_previa != inv.aprobacion or cupo_previo != inv.cupo_aprobado:
        auditar(
            db,
            evento.id,
            "transicion_aprobacion_rsvp",
            actor,
            inv.id,
            estado_anterior=aprobacion_previa,
            estado=inv.aprobacion,
            cupo_anterior=cupo_previo,
            cupo=inv.cupo_aprobado,
        )
    return inv


def aprobar(db, ctx, inv, data: Aprobacion):
    inv.actualizado_por = ctx.usuario.id
    if data.estado == "APROBADO":
        if (
            inv.rsvp not in {"CONFIRMADO", "MODIFICADO"}
            or not inv.ingresados
            <= data.cupo
            <= min(inv.cantidad_permitida, inv.adultos + inv.menores)
            or data.cupo < 1
        ):
            raise HTTPException(
                409, "El cupo debe estar entre los ingresos ya registrados y la cantidad solicitada"
            )
        inv.aprobacion, inv.cupo_aprobado = "APROBADO", data.cupo
        emitir(db, inv, "qr")
    else:
        inv.aprobacion, inv.cupo_aprobado = data.estado, inv.ingresados
        revocar(db, inv, "qr")
    auditar(
        db,
        ctx.evento.id,
        "aprobacion",
        ctx.usuario.id,
        inv.id,
        estado=inv.aprobacion,
        cupo=inv.cupo_aprobado,
    )


def limitar(db, clave, maximo=30, segundos=600):
    from sqlalchemy import case
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sq_insert

    insertar = pg_insert if db.bind.dialect.name == "postgresql" else sq_insert
    ventana = int(time.time()) // segundos
    stmt = insertar(LimiteAcceso).values(clave=digest(clave), cantidad=1, ventana=ventana)
    stmt = stmt.on_conflict_do_update(
        index_elements=[LimiteAcceso.clave],
        set_={
            "cantidad": case((LimiteAcceso.ventana == ventana, LimiteAcceso.cantidad + 1), else_=1),
            "ventana": ventana,
        },
    ).returning(LimiteAcceso.cantidad)
    cantidad = db.scalar(stmt)
    db.commit()
    if cantidad > maximo:
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos")


def resolver_token(db, slug, token, tipo, lock=False):
    c = db.scalar(
        select(CredencialInvitacion).where(
            CredencialInvitacion.token_hash == digest(token),
            CredencialInvitacion.tipo == tipo,
            CredencialInvitacion.activo.is_(True),
        )
    )
    if c is None or utc(c.vence_at) <= ahora():
        raise HTTPException(404, "Invitacion o credencial no disponible")
    q = (
        select(Invitacion)
        .join(Evento, Invitacion.evento_id == Evento.id)
        .where(
            Invitacion.id == c.invitacion_id,
            Invitacion.activo.is_(True),
            Evento.activo.is_(True),
            Evento.slug == slug,
        )
    )
    inv = db.scalar(q.with_for_update(of=Invitacion) if lock else q)
    if inv is None:
        raise HTTPException(404, "Invitacion o credencial no disponible")
    # Volver a comprobar despues de esperar el lock: una revocacion puede haber ocurrido.
    db.refresh(c)
    if not c.activo:
        raise HTTPException(404, "Credencial revocada")
    return inv, c


def validar_qr(db, ctx, token, lock=False):
    inv, c = resolver_token(db, ctx.evento.slug, token, "qr", lock)
    if inv.aprobacion != "APROBADO" or inv.rsvp not in {"CONFIRMADO", "MODIFICADO"}:
        raise HTTPException(409, "Invitacion no aprobada")
    return inv


def registrar_ingreso(db, ctx, data):
    # El lock de invitacion serializa varios operadores; la clave evita dobles clics/reintentos.
    inv = validar_qr(db, ctx, data.token, True)
    existente = db.scalar(
        select(MovimientoIngreso).where(
            MovimientoIngreso.evento_id == ctx.evento.id,
            MovimientoIngreso.idempotencia == data.idempotencia,
        )
    )
    if existente:
        if existente.invitacion_id != inv.id or existente.cantidad != data.cantidad:
            raise HTTPException(409, "La clave de idempotencia ya se uso para otra operacion")
        return resumen_inv(inv, False)
    if inv.ingresados + data.cantidad > inv.cupo_aprobado:
        raise HTTPException(409, "Ingreso completo o cantidad superior al cupo restante")
    inv.ingresados += data.cantidad
    inv.actualizado_por = ctx.usuario.id
    db.add(
        MovimientoIngreso(
            evento_id=ctx.evento.id,
            invitacion_id=inv.id,
            operador_id=ctx.usuario.id,
            cantidad=data.cantidad,
            idempotencia=data.idempotencia,
        )
    )
    auditar(db, ctx.evento.id, "ingreso", ctx.usuario.id, inv.id, cantidad=data.cantidad)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Operacion ya registrada; consulta el estado actualizado") from exc
    return resumen_inv(inv, False)
