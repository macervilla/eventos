from uuid import uuid4

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.invitaciones import FotoInvitado, Invitacion
from app.services.invitados import ahora, auditar, cifrador
from app.services.media_storage import media_storage


def fotos_activas(db, inv):
    return list(db.scalars(select(FotoInvitado).where(
        FotoInvitado.invitacion_id == inv.id, FotoInvitado.activo.is_(True)
    ).order_by(FotoInvitado.slot)))


def listado(db, inv):
    return {"limite": 4, "bloqueadas": inv.fotos_bloqueadas, "fotos": [
        {"id": f.id, "nombre": f.nombre_archivo, "mime_type": f.mime_type,
         "size_bytes": f.size_bytes, "slot": f.slot} for f in fotos_activas(db, inv)]}


def exigir_editable(inv):
    if inv.fotos_bloqueadas:
        raise HTTPException(409, "El administrador confirmo tus fotos. Debe desbloquearlas para que puedas modificarlas")


def obtener_foto(db, inv, foto_id):
    foto = db.scalar(select(FotoInvitado).where(FotoInvitado.id == foto_id,
        FotoInvitado.invitacion_id == inv.id, FotoInvitado.activo.is_(True)))
    if foto is None:
        raise HTTPException(404, "Foto no encontrada en esta invitacion")
    return foto


async def subir(db, inv, file):
    # El llamador mantiene el lock de invitacion durante comprobacion, escritura y commit.
    exigir_editable(inv)
    ocupados = {f.slot for f in fotos_activas(db, inv)}
    libre = next((n for n in range(1, 5) if n not in ocupados), None)
    if libre is None:
        raise HTTPException(409, "Ya subiste 4 fotos. Quita una antes de subir otra")
    contenido, mime_type, _ = await media_storage.prepare_image(file)
    if len(contenido) > settings.max_upload_bytes:
        raise HTTPException(413, "La imagen supera el tamano maximo permitido")
    # Persistir en el volumen de media, exclusivamente como contenido cifrado.
    object_key = f"fotos-invitados-privadas/{uuid4()}.enc"
    path = media_storage._safe_path(object_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cifrador().encrypt(contenido))
    foto = FotoInvitado(invitacion_id=inv.id, slot=libre, object_key=object_key,
        nombre_archivo=(file.filename or "foto").replace("\\", "/").rsplit("/", 1)[-1][:160] or "foto",
        mime_type=mime_type, size_bytes=len(contenido))
    db.add(foto); db.flush()
    auditar(db, inv.evento_id, "foto_invitado_subida", invitacion_id=inv.id, foto_id=foto.id)
    db.commit()
    return listado(db, inv)


def quitar(db, inv, foto_id):
    exigir_editable(inv)
    foto = obtener_foto(db, inv, foto_id)
    foto.activo, foto.deleted_at = False, ahora()
    auditar(db, inv.evento_id, "foto_invitado_quitada", invitacion_id=inv.id, foto_id=foto.id)
    db.commit()
    return listado(db, inv)


def contenido_foto(db, inv, foto_id):
    foto = obtener_foto(db, inv, foto_id)
    try:
        contenido = cifrador().decrypt(media_storage._safe_path(foto.object_key).read_bytes())
    except (FileNotFoundError, InvalidToken):
        raise HTTPException(404, "La foto no esta disponible") from None
    return contenido, foto.mime_type


def cambiar_bloqueo(db, inv, bloqueadas, actor):
    if bloqueadas and not fotos_activas(db, inv):
        raise HTTPException(409, "El invitado todavia no subio fotos para confirmar")
    if inv.fotos_bloqueadas != bloqueadas:
        inv.fotos_bloqueadas = bloqueadas
        auditar(db, inv.evento_id, "fotos_invitado_confirmadas" if bloqueadas else "fotos_invitado_desbloqueadas",
                actor.id, inv.id)
    db.commit()
    return listado(db, inv)


def quitar_seleccionadas(db, inv, ids, actor):
    seleccion = set(ids)
    elegidas = list(db.scalars(select(FotoInvitado).where(FotoInvitado.invitacion_id == inv.id,
        FotoInvitado.id.in_(seleccion), FotoInvitado.activo.is_(True))))
    if len(elegidas) != len(seleccion):
        raise HTTPException(404, "Alguna foto seleccionada ya no esta disponible en esta invitacion")
    for foto in elegidas:
        foto.activo, foto.deleted_at = False, ahora()
    # El invitado debe poder completar los lugares liberados, incluso si el conjunto estaba confirmado.
    inv.fotos_bloqueadas = False
    auditar(db, inv.evento_id, "fotos_invitado_quitadas_admin", actor.id, inv.id, fotos=sorted(seleccion))
    db.commit()
    return listado(db, inv)


def album(db, evento):
    fotos = db.scalars(select(FotoInvitado).join(Invitacion, FotoInvitado.invitacion_id == Invitacion.id).where(
        Invitacion.evento_id == evento.id, Invitacion.activo.is_(True), FotoInvitado.activo.is_(True),
        Invitacion.fotos_bloqueadas.is_(True)
    ).order_by(FotoInvitado.invitacion_id, FotoInvitado.slot)).all()
    return {"evento": evento.nombre, "fotos": [{"id": foto.id, "nombre": foto.nombre_archivo} for foto in fotos]}


def contenido_album(db, evento, foto_id):
    inv = db.scalar(select(Invitacion).join(FotoInvitado, FotoInvitado.invitacion_id == Invitacion.id).where(
        Invitacion.evento_id == evento.id, Invitacion.activo.is_(True), FotoInvitado.id == foto_id,
        FotoInvitado.activo.is_(True), Invitacion.fotos_bloqueadas.is_(True)))
    if inv is None:
        raise HTTPException(404, "Foto no encontrada en este evento")
    return contenido_foto(db, inv, foto_id)
