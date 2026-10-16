from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.seguridad import exigir_duenio_proveedor, obtener_usuario_actual
from app.db.session import get_db
from app.models.enums import MediaTipo
from app.models.usuarios import User
from app.schemas.media import MediaRead
from app.services.eventos import obtener_evento_del_propietario
from app.services.media import media_to_read, upload_event_cover, upload_provider_media

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/proveedores/{slug}/{tipo}", response_model=MediaRead)
async def upload_provider_media_endpoint(
    slug: str,
    tipo: MediaTipo,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: User = Depends(obtener_usuario_actual),
) -> MediaRead:
    exigir_duenio_proveedor(db, slug, usuario)
    media = await upload_provider_media(db, slug=slug, media_type=tipo, file=file)
    return media_to_read(media)


@router.post("/eventos/{slug}/PORTADA", response_model=MediaRead)
async def upload_event_cover_endpoint(
    slug: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: User = Depends(obtener_usuario_actual),
) -> MediaRead:
    evento = obtener_evento_del_propietario(db, slug, usuario)
    media = await upload_event_cover(db, evento=evento, file=file)
    return media_to_read(media)
