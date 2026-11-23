import re
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select, text

from app.core.config import settings
from app.core.seguridad import _firmar, _leer
from app.models.eventos import Evento
from app.models.enums import EventoEstado
from app.models.invitaciones import CredencialInvitacion, Invitacion
from app.models.usuarios import User
from app.models.video import CamaraVideo, SesionVideo, TransmisionEvento
from app.schemas.invitados import PortalAcceso
from app.services.invitados import ahora, auditar, utc
from app.services.invitados_permisos import acceso, modulo_invitados
from app.services.invitados_portal import acceso_portal, resolver_portal
from app.services.mediamtx import mediamtx

PATRON_PATH = re.compile(r"^evt-(\d+)-([a-f0-9]{32})$")
SEGUNDOS_LEASE = 45


@dataclass
class IdentidadVideo:
    evento: Evento
    usuario_id: int | None = None
    invitacion_id: int | None = None
    enlace_hash: str | None = None

    def actor(self):
        return {"usuario_id": self.usuario_id, "invitacion_id": self.invitacion_id, "enlace_hash": self.enlace_hash}


def identificar(db, slug, data, usuario):
    if data.token:
        prueba = PortalAcceso(token=data.token, sesion=data.sesion)
        acceso_portal(db, slug, prueba, exigir=True, usuario=usuario)
        inv, enlace, evento, _ = resolver_portal(db, slug, prueba)
        return IdentidadVideo(evento, invitacion_id=inv.id, enlace_hash=enlace.token_hash)
    if usuario is None:
        raise HTTPException(401, "Ingresa o abre tu invitacion personal para acceder al evento")
    ctx = acceso(db, slug, usuario, "configurar_invitados", habilitado=False)
    return IdentidadVideo(ctx.evento, usuario_id=usuario.id)


def bloquear(db, evento_id):
    # Bloquear el padre tambien serializa la primera alta concurrente de esta configuracion.
    if db.scalar(select(Evento).where(Evento.id == evento_id).with_for_update()) is None:
        raise HTTPException(404, "Evento no encontrado")
    row = db.get(TransmisionEvento, evento_id)
    if row is None:
        row = TransmisionEvento(evento_id=evento_id, estado="finalizada", version=uuid4().hex)
        db.add(row); db.flush()
    else:
        db.refresh(row)
    return row


def path(row):
    return f"evt-{row.evento_id}-{row.version}"


def camaras(db, evento_id):
    return list(db.scalars(select(CamaraVideo).where(CamaraVideo.evento_id == evento_id, CamaraVideo.habilitada.is_(True))))


def por_version(db, evento_id, version):
    return db.scalar(select(CamaraVideo).where(CamaraVideo.evento_id == evento_id, CamaraVideo.version == version))


def bloquear_capacidad(db):
    # Un mismo candado en todos los workers serializa las reservas globales.
    # Se adquiere antes del candado del evento para evitar ordenes inversos.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(73820123)"))


def actor_valido(db, evento, actor):
    if not evento or not evento.activo:
        return False
    if actor.get("usuario_id"):
        user = db.get(User, actor["usuario_id"])
        if not user or not user.activo or not user.google_subject or not user.email_validado_en:
            return False
        try:
            acceso(db, evento.slug, user, "configurar_invitados", habilitado=False)
            return True
        except HTTPException:
            return False
    inv = db.get(Invitacion, actor.get("invitacion_id"))
    modulo = modulo_invitados(db, evento)
    if not inv or not inv.activo or inv.evento_id != evento.id or evento.estado == EventoEstado.BORRADOR or not modulo or not modulo.activo:
        return False
    enlace = db.scalar(select(CredencialInvitacion).where(
        CredencialInvitacion.invitacion_id == inv.id, CredencialInvitacion.tipo == "enlace",
        CredencialInvitacion.token_hash == actor.get("enlace_hash"), CredencialInvitacion.activo.is_(True)))
    return bool(enlace and utc(enlace.vence_at) > ahora())


def sesion_permitida(db, sesion, row):
    seleccion = db.get(TransmisionEvento, row.evento_id) if row else None
    return bool(sesion and row and row.habilitada and sesion.activo and utc(sesion.vence_at) > ahora()
        and sesion.version == row.version and actor_valido(db, db.get(Evento, row.evento_id), {
            "usuario_id": sesion.usuario_id, "invitacion_id": sesion.invitacion_id, "enlace_hash": sesion.enlace_hash})
        and ((sesion.accion == "read" and (sesion.usuario_id or
            (seleccion and seleccion.invitacion_id == row.invitacion_id))) or (row.invitacion_id == sesion.invitacion_id
            and sesion.accion == "publish"
            and row.sesion_id == sesion.id and row.reserva)))


def refrescar_estado(db, row):
    estado_real = mediamtx.path(path(row))
    online = bool(estado_real and estado_real.get("ready") and
                  (estado_real.get("source") or {}).get("id") == row.sesion_id)
    if online and row.invitacion_id and row.reserva:
        row.estado = "activa"
    elif row.estado == "activa" or (row.estado == "iniciando" and row.reserva_hasta and utc(row.reserva_hasta) < ahora()):
        row.estado = "interrumpida"; row.reserva = None; row.sesion_id = None; row.reserva_hasta = None
    return online


def estado(db, identidad, data):
    seleccion = bloquear(db, identidad.evento.id)
    filas = camaras(db, identidad.evento.id)
    disponible = settings.video_enabled and bool(settings.mediamtx_auth_secret.get_secret_value())
    if data.sesion_media:
        sesion = db.get(SesionVideo, data.sesion_media)
        row = por_version(db, identidad.evento.id, sesion.version) if sesion else None
        if sesion and row and sesion.evento_id == identidad.evento.id and sesion.usuario_id == identidad.usuario_id and \
                sesion.invitacion_id == identidad.invitacion_id and sesion.enlace_hash == identidad.enlace_hash and \
                sesion_permitida(db, sesion, row):
            sesion.vence_at = ahora() + timedelta(seconds=SEGUNDOS_LEASE)
    if disponible:
        try:
            for row in filas:
                refrescar_estado(db, row)
        except HTTPException:
            disponible = False
    def vista(row):
        inv = db.get(Invitacion, row.invitacion_id) if row else None
        return {"estado": (row.estado if disponible or row.estado not in {"activa", "iniciando"} else "interrumpida") if row else "finalizada",
            "invitacion_id": row.invitacion_id if row else None,
            "invitado": f"{inv.apellido} {inv.nombre}".strip() if inv else None,
            "emision": row.sesion_id if row and disponible and row.estado == "activa" else None}
    elegida = next((c for c in filas if c.invitacion_id == seleccion.invitacion_id), None)
    propia = next((c for c in filas if c.invitacion_id == identidad.invitacion_id), None)
    inv = db.get(Invitacion, identidad.invitacion_id) if identidad.invitacion_id else None
    resultado = {**vista(elegida), "disponible": bool(disponible),
        "puede_publicar": bool(propia and inv and inv.activo), "publicacion": vista(propia)}
    if identidad.usuario_id:
        resultado.update(camaras=[{**vista(c), "seleccionada": c == elegida} for c in filas],
            limite_camaras=settings.video_max_camaras_evento, limite_servidor=settings.video_max_transmisiones)
    db.commit()
    return resultado


def exigir_servidor():
    if not settings.video_enabled or not settings.mediamtx_auth_secret.get_secret_value():
        raise HTTPException(503, "La transmision de video aun no esta habilitada en el servidor")


def credencial(db, identidad, publicar=False, invitacion_id=None):
    exigir_servidor()
    if publicar:
        bloquear_capacidad(db)
    seleccion = bloquear(db, identidad.evento.id)
    if invitacion_id is not None and not identidad.usuario_id:
        raise HTTPException(403, "Solo el administrador puede previsualizar otras camaras")
    camara_id = identidad.invitacion_id if publicar else (invitacion_id or seleccion.invitacion_id)
    row = db.get(CamaraVideo, (identidad.evento.id, camara_id)) if camara_id else None
    if not row or not row.habilitada:
        raise HTTPException(403 if publicar else 409, "Camara no habilitada" if publicar else "No hay una transmision seleccionada para el album")
    online = refrescar_estado(db, row)
    if publicar:
        if not identidad.invitacion_id or identidad.invitacion_id != row.invitacion_id:
            raise HTTPException(403, "Solo el invitado habilitado por el administrador puede transmitir")
        if online or (row.reserva and row.reserva_hasta and utc(row.reserva_hasta) > ahora()):
            raise HTTPException(409, "Este invitado ya tiene una transmision activa o iniciandose")
        ocupadas = list(db.scalars(select(CamaraVideo).where(CamaraVideo.habilitada.is_(True),
            CamaraVideo.estado.in_(["activa", "iniciando"]))))
        # Revalidar contra MediaMTX evita contar desconexiones como plazas ocupadas.
        for ocupada in ocupadas:
            refrescar_estado(db, ocupada)
        total = sum(bool(c.estado == "activa" or (c.estado == "iniciando" and c.reserva_hasta
            and utc(c.reserva_hasta) > ahora())) for c in ocupadas)
        if total >= settings.video_max_transmisiones:
            raise HTTPException(409, "Se alcanzo el limite de transmisiones simultaneas del servidor")
        # Antes de reservar, cortar generaciones anteriores o conexiones abandonadas.
        # Si la API de corte no responde, no se permite abrir una segunda publicacion.
        for remota in mediamtx.sessions():
            match = PATRON_PATH.fullmatch(remota.get("path", ""))
            if match:
                camara = por_version(db, int(match[1]), match[2])
                if not sesion_permitida(db, db.get(SesionVideo, remota["id"]), camara):
                    mediamtx.kick(remota["id"])
        row.reserva = uuid4().hex; row.sesion_id = None
        row.reserva_hasta = ahora() + timedelta(seconds=SEGUNDOS_LEASE); row.estado = "iniciando"
    elif not online:
        raise HTTPException(409, "No hay una transmision activa en este evento")
    accion = "publish" if publicar else "read"
    token = _firmar({"tipo": "video", "evento_id": row.evento_id, "version": row.version,
        "accion": accion, "actor": identidad.actor(), "reserva": row.reserva if publicar else None}, 1)
    resultado = {"url": settings.mediamtx_public_url.rstrip("/") + "/" + path(row) + ("/whip" if publicar else "/whep"),
                 "credencial": token, "reserva": row.reserva if publicar else None, "bitrate": settings.video_bitrate}
    db.commit()
    return resultado


def autenticar_media(db, data):
    try:
        session_id = str(UUID(data.id))
        claims = _leer(data.token, "video")
        evento_id = int(claims["evento_id"])
    except (HTTPException, ValueError, KeyError, TypeError):
        raise HTTPException(401, "Credencial temporal de video invalida") from None
    seleccion = bloquear(db, evento_id)
    row = por_version(db, evento_id, claims.get("version"))
    actor = claims.get("actor") or {}
    if not row or not row.habilitada or data.path != path(row) or claims.get("version") != row.version or claims.get("accion") != data.action \
            or not actor_valido(db, db.get(Evento, evento_id), actor):
        raise HTTPException(403, "Acceso a video revocado o ajeno al evento")
    if data.action == "read" and not actor.get("usuario_id") and seleccion.invitacion_id != row.invitacion_id:
        raise HTTPException(403, "La camara ya no esta seleccionada para el album")
    if data.action == "publish":
        if not row.reserva or claims.get("reserva") != row.reserva or actor.get("invitacion_id") != row.invitacion_id \
                or not row.reserva_hasta or utc(row.reserva_hasta) < ahora() \
                or row.sesion_id not in (None, session_id):
            raise HTTPException(403, "No esta autorizada esta publicacion")
        row.sesion_id = session_id
    sesion = db.get(SesionVideo, session_id)
    if sesion is None:
        sesion = SesionVideo(id=session_id, evento_id=evento_id, version=row.version, accion=data.action,
            usuario_id=actor.get("usuario_id"), invitacion_id=actor.get("invitacion_id"), enlace_hash=actor.get("enlace_hash"))
        db.add(sesion)
    elif not sesion.activo or sesion.version != row.version or sesion.accion != data.action \
            or sesion.usuario_id != actor.get("usuario_id") or sesion.invitacion_id != actor.get("invitacion_id") \
            or sesion.enlace_hash != actor.get("enlace_hash"):
        raise HTTPException(403, "Sesion de video finalizada")
    sesion.vence_at = ahora() + timedelta(seconds=SEGUNDOS_LEASE)
    db.commit()


def cortar_evento(db, evento_id):
    bloquear(db, evento_id)
    for sesion in mediamtx.sessions():
        match = PATRON_PATH.fullmatch(sesion.get("path", ""))
        if match and int(match[1]) == evento_id:
            row = por_version(db, evento_id, match[2])
            if not sesion_permitida(db, db.get(SesionVideo, sesion["id"]), row):
                mediamtx.kick(sesion["id"])
    db.commit()


def autorizar(db, evento, invitacion_id, actor, habilitada=True):
    seleccion = bloquear(db, evento.id)
    if invitacion_id is not None:
        inv = db.get(Invitacion, invitacion_id)
        if not inv or not inv.activo or inv.evento_id != evento.id:
            raise HTTPException(404, "Invitado no encontrado en este evento")
    row = db.get(CamaraVideo, (evento.id, invitacion_id)) if invitacion_id else None
    if invitacion_id and habilitada:
        if not row or not row.habilitada:
            if len(camaras(db, evento.id)) >= settings.video_max_camaras_evento:
                raise HTTPException(409, "Se alcanzo el limite de camaras habilitadas para este evento")
            if row is None:
                row = CamaraVideo(evento_id=evento.id, invitacion_id=invitacion_id)
                db.add(row)
            row.habilitada = True; row.version = uuid4().hex; row.estado = "autorizado"
            row.reserva = None; row.reserva_hasta = None; row.sesion_id = None
    else:
        for camara in ([row] if row else ([] if invitacion_id else camaras(db, evento.id))):
            camara.habilitada = False; camara.version = uuid4().hex
            camara.reserva = None; camara.reserva_hasta = None; camara.sesion_id = None; camara.estado = "finalizada"
        if invitacion_id is None or seleccion.invitacion_id == invitacion_id:
            seleccion.invitacion_id = None
    auditar(db, evento.id, "autorizar_video" if invitacion_id and habilitada else "revocar_video", actor.id, invitacion_id)
    db.commit()  # Primero invalida credenciales, incluso si el servidor de video no responde.
    if settings.video_enabled:
        cortar_evento(db, evento.id)  # Si falla devuelve 503; el reconciliador reintentara el corte.
    return {"invitacion_id": invitacion_id, "habilitada": bool(invitacion_id and habilitada)}


def seleccionar(db, evento, invitacion_id, actor):
    seleccion = bloquear(db, evento.id)
    row = db.get(CamaraVideo, (evento.id, invitacion_id)) if invitacion_id else None
    if invitacion_id is not None and (not row or not row.habilitada or not refrescar_estado(db, row)):
        raise HTTPException(409, "Selecciona una camara habilitada que este transmitiendo")
    seleccion.invitacion_id = invitacion_id
    auditar(db, evento.id, "seleccionar_video_album", actor.id, invitacion_id)
    db.commit()
    # El reconciliador corta lectores anteriores; los publicadores y previews continuan.
    return {"invitacion_id": invitacion_id}


def detener(db, identidad, reserva, motivo="finalizada"):
    bloquear(db, identidad.evento.id)
    row = db.get(CamaraVideo, (identidad.evento.id, identidad.invitacion_id)) if identidad.invitacion_id else None
    if not row or not row.habilitada or not reserva or row.reserva != reserva:
        raise HTTPException(409, "La transmision ya termino o cambio su autorizacion")
    session_id = row.sesion_id
    row.reserva = None; row.reserva_hasta = None; row.sesion_id = None; row.estado = motivo
    db.commit()
    if session_id:
        mediamtx.kick(session_id)
    return {"estado": motivo}


def reconciliar(db):
    """Cortar sesiones revocadas/abandonadas aunque el navegador no coopere."""
    for remota in mediamtx.sessions():
        match = PATRON_PATH.fullmatch(remota.get("path", ""))
        if not match:
            continue
        bloquear(db, int(match[1]))
        row = por_version(db, int(match[1]), match[2])
        sesion = db.get(SesionVideo, remota["id"])
        if not sesion_permitida(db, sesion, row):
            mediamtx.kick(remota["id"])
            if sesion:
                sesion.activo = False
        db.commit()
