from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import MediaEstado, MediaTipo
from app.models.eventos import Evento
from app.models.interacciones import Media
from app.models.proveedores import Proveedor
from app.schemas.media import MediaRead
from app.services.media_storage import media_storage


MEDIA_LIMITS = {
    "GRATIS": {MediaTipo.PORTADA: 1, MediaTipo.LOGO: 1, MediaTipo.GALERIA: 10},
    "PREMIUM": {MediaTipo.PORTADA: 1, MediaTipo.LOGO: 1, MediaTipo.GALERIA: 100},
}


def _kind_for_media_type(media_type: MediaTipo) -> str:
    return {
        MediaTipo.PORTADA: "portada",
        MediaTipo.LOGO: "logo",
        MediaTipo.GALERIA: "galeria",
    }[media_type]


def media_to_read(media: Media) -> MediaRead:
    return MediaRead(
        id=media.id,
        uuid=str(media.uuid),
        tipo=media.tipo.value,
        object_key=media.object_key,
        public_url=media_storage.get_public_url(media.object_key),
        original_filename=media.original_filename,
        mime_type=media.mime_type,
        size_bytes=media.size_bytes or media.tamano,
    )


async def upload_provider_media(
    db: Session,
    *,
    slug: str,
    media_type: MediaTipo,
    file: UploadFile,
) -> Media:
    proveedor = db.scalar(select(Proveedor).where(Proveedor.slug == slug, Proveedor.activo.is_(True)))
    if proveedor is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    if media_type not in {MediaTipo.PORTADA, MediaTipo.LOGO, MediaTipo.GALERIA}:
        raise HTTPException(status_code=400, detail="Tipo de media invalido")

    active_count = db.scalar(
        select(func.count(Media.id)).where(
            Media.proveedor_id == proveedor.id,
            Media.tipo == media_type,
            Media.activo.is_(True),
        )
    ) or 0
    limit = MEDIA_LIMITS.get(proveedor.plan.value, MEDIA_LIMITS["GRATIS"])[media_type]
    if active_count >= limit and media_type == MediaTipo.GALERIA:
        raise HTTPException(status_code=400, detail="Limite de imagenes alcanzado")

    if media_type in {MediaTipo.PORTADA, MediaTipo.LOGO}:
        existing = db.scalars(
            select(Media).where(
                Media.proveedor_id == proveedor.id,
                Media.tipo == media_type,
                Media.activo.is_(True),
            )
        ).all()
        for item in existing:
            item.activo = False

    stored = await media_storage.save_image(
        file,
        owner="proveedores",
        owner_uuid=str(proveedor.uuid),
        kind=_kind_for_media_type(media_type),
    )
    next_order = active_count + 1 if media_type == MediaTipo.GALERIA else 0
    media = Media(
        proveedor_id=proveedor.id,
        usuario_id=proveedor.usuario_id,
        uploaded_by=proveedor.usuario_id,
        tipo=media_type,
        storage_provider=media_storage.provider,
        object_key=stored.object_key,
        url=stored.public_url,
        tamano=stored.size_bytes,
        size_bytes=stored.size_bytes,
        original_filename=stored.original_filename,
        mime_type=stored.mime_type,
        estado=MediaEstado.APROBADO,
        orden=next_order,
    )
    db.add(media)
    if media_type == MediaTipo.PORTADA:
        proveedor.portada_url = stored.public_url
        proveedor.portada_encuadre = None
    elif media_type == MediaTipo.LOGO:
        proveedor.logo_url = stored.public_url
    db.commit()
    db.refresh(media)
    return media


async def upload_event_cover(db: Session, *, evento: Evento, file: UploadFile) -> Media:
    for item in db.scalars(
        select(Media).where(
            Media.evento_id == evento.id,
            Media.tipo == MediaTipo.PORTADA,
            Media.activo.is_(True),
        )
    ).all():
        item.activo = False

    stored = await media_storage.save_image(
        file,
        owner="eventos",
        owner_uuid=str(evento.uuid),
        kind="portada",
    )
    media = Media(
        evento_id=evento.id,
        usuario_id=evento.propietario_id,
        uploaded_by=evento.propietario_id,
        tipo=MediaTipo.PORTADA,
        storage_provider=media_storage.provider,
        object_key=stored.object_key,
        url=stored.public_url,
        tamano=stored.size_bytes,
        size_bytes=stored.size_bytes,
        original_filename=stored.original_filename,
        mime_type=stored.mime_type,
        estado=MediaEstado.APROBADO,
        orden=0,
    )
    db.add(media)
    evento.portada_url = stored.public_url
    evento.portada_encuadre = None
    db.commit()
    db.refresh(media)
    return media
