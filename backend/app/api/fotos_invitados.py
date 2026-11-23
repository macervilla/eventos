from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from sqlalchemy.orm import Session

from app.core.seguridad import obtener_usuario_actual, obtener_usuario_opcional
from app.db.session import get_db
from app.models.usuarios import User
from app.schemas.invitados import PortalAcceso
from app.services import fotos_invitados as fotos
from app.services import invitados as s
from app.services.invitados_permisos import acceso
from app.services.invitados_portal import acceso_portal, resolver_portal
from app.services.video import identificar

router = APIRouter(prefix="/invitados", tags=["fotos de invitados"])
DB = Depends(get_db)
OPCIONAL = Depends(obtener_usuario_opcional)
USUARIO = Depends(obtener_usuario_actual)


class EstadoFotos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bloqueadas: bool


class QuitarFotos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[PositiveInt] = Field(min_length=1, max_length=4)


def invitado_autorizado(db, slug, data, usuario, lock=False):
    acceso_portal(db, slug, data, exigir=True, lock=lock, usuario=usuario)
    inv, _, _, _ = resolver_portal(db, slug, data, lock=lock)
    return inv


def invitado_administrado(db, slug, inv_id, usuario, lock=False):
    ctx = acceso(db, slug, usuario, "configurar_invitados", habilitado=False)
    return s.obtener(db, ctx, inv_id, lock=lock)


def imagen(contenido, mime):
    return Response(contenido, media_type=mime,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/{slug}/portal/fotos/listar")
def listar(slug: str, data: PortalAcceso, db: Session = DB, usuario: User | None = OPCIONAL):
    return fotos.listado(db, invitado_autorizado(db, slug, data, usuario))


@router.post("/{slug}/portal/fotos")
async def subir(slug: str, token: str = Form(..., min_length=20, max_length=200),
                sesion: str | None = Form(None, max_length=2000), file: UploadFile = File(...),
                db: Session = DB, usuario: User | None = OPCIONAL):
    inv = invitado_autorizado(db, slug, PortalAcceso(token=token, sesion=sesion), usuario, lock=True)
    return await fotos.subir(db, inv, file)


@router.post("/{slug}/portal/fotos/{foto_id}/imagen")
def ver(slug: str, foto_id: int, data: PortalAcceso, db: Session = DB, usuario: User | None = OPCIONAL):
    return imagen(*fotos.contenido_foto(db, invitado_autorizado(db, slug, data, usuario), foto_id))


@router.post("/{slug}/portal/fotos/{foto_id}/quitar")
def quitar(slug: str, foto_id: int, data: PortalAcceso, db: Session = DB, usuario: User | None = OPCIONAL):
    inv = invitado_autorizado(db, slug, data, usuario, lock=True)
    return fotos.quitar(db, inv, foto_id)


@router.get("/{slug}/lista/{inv_id}/fotos")
def listar_admin(slug: str, inv_id: int, db: Session = DB, usuario: User = USUARIO):
    return fotos.listado(db, invitado_administrado(db, slug, inv_id, usuario))


@router.get("/{slug}/lista/{inv_id}/fotos/{foto_id}/imagen")
def ver_admin(slug: str, inv_id: int, foto_id: int, db: Session = DB, usuario: User = USUARIO):
    return imagen(*fotos.contenido_foto(db, invitado_administrado(db, slug, inv_id, usuario), foto_id))


@router.put("/{slug}/lista/{inv_id}/fotos/estado")
def bloquear(slug: str, inv_id: int, data: EstadoFotos, db: Session = DB, usuario: User = USUARIO):
    inv = invitado_administrado(db, slug, inv_id, usuario, lock=True)
    return fotos.cambiar_bloqueo(db, inv, data.bloqueadas, usuario)


@router.post("/{slug}/lista/{inv_id}/fotos/quitar-seleccionadas")
def quitar_admin(slug: str, inv_id: int, data: QuitarFotos, db: Session = DB, usuario: User = USUARIO):
    inv = invitado_administrado(db, slug, inv_id, usuario, lock=True)
    return fotos.quitar_seleccionadas(db, inv, data.ids, usuario)


@router.get("/{slug}/album")
def album(slug: str, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "configurar_invitados", habilitado=False)
    return fotos.album(db, ctx.evento)


@router.get("/{slug}/album/{foto_id}/imagen")
def imagen_album(slug: str, foto_id: int, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "configurar_invitados", habilitado=False)
    return imagen(*fotos.contenido_album(db, ctx.evento, foto_id))


@router.post("/{slug}/portal/album")
def album_invitado(slug: str, data: PortalAcceso, db: Session = DB, usuario: User | None = OPCIONAL):
    identidad = identificar(db, slug, data, usuario)
    return fotos.album(db, identidad.evento)


@router.post("/{slug}/portal/album/{foto_id}/imagen")
def imagen_album_invitado(slug: str, foto_id: int, data: PortalAcceso, db: Session = DB, usuario: User | None = OPCIONAL):
    identidad = identificar(db, slug, data, usuario)
    return imagen(*fotos.contenido_album(db, identidad.evento, foto_id))
