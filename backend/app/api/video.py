import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.seguridad import obtener_usuario_actual, obtener_usuario_opcional
from app.db.session import get_db
from app.models.usuarios import User
from app.schemas.video import AccesoVideo, AuthMedia, AutorizarVideo, SeleccionarVideo
from app.services import video
from app.services.invitados_permisos import acceso

router = APIRouter(tags=["video en vivo"])
DB = Depends(get_db)
OPCIONAL = Depends(obtener_usuario_opcional)
USUARIO = Depends(obtener_usuario_actual)
basic = HTTPBasic(auto_error=False)


@router.post("/invitados/{slug}/vivo/estado")
def estado(slug: str, data: AccesoVideo, db: Session = DB, usuario: User | None = OPCIONAL):
    return video.estado(db, video.identificar(db, slug, data, usuario), data)


@router.put("/invitados/{slug}/vivo/autorizacion")
def autorizar(slug: str, data: AutorizarVideo, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "configurar_invitados", habilitado=False)
    return video.autorizar(db, ctx.evento, data.invitacion_id, usuario, data.habilitada)


@router.put("/invitados/{slug}/vivo/seleccion")
def seleccionar(slug: str, data: SeleccionarVideo, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "configurar_invitados", habilitado=False)
    return video.seleccionar(db, ctx.evento, data.invitacion_id, usuario)


@router.post("/invitados/{slug}/vivo/iniciar")
def iniciar(slug: str, data: AccesoVideo, db: Session = DB, usuario: User | None = OPCIONAL):
    return video.credencial(db, video.identificar(db, slug, data, usuario), publicar=True)


@router.post("/invitados/{slug}/vivo/ver")
def ver(slug: str, data: AccesoVideo, db: Session = DB, usuario: User | None = OPCIONAL):
    return video.credencial(db, video.identificar(db, slug, data, usuario), invitacion_id=data.invitacion_id)


@router.post("/invitados/{slug}/vivo/detener")
def detener(slug: str, data: AccesoVideo, db: Session = DB, usuario: User | None = OPCIONAL):
    return video.detener(db, video.identificar(db, slug, data, usuario), data.reserva, data.motivo)


@router.post("/interno/mediamtx/auth", include_in_schema=False)
def autenticar(data: AuthMedia, db: Session = DB, cred: HTTPBasicCredentials | None = Depends(basic)):
    esperado = settings.mediamtx_auth_secret.get_secret_value()
    if not settings.video_enabled or not esperado or not cred or not secrets.compare_digest(cred.username, "mediamtx") \
            or not secrets.compare_digest(cred.password, esperado):
        raise HTTPException(401, "Autenticacion de servidor requerida")
    video.autenticar_media(db, data)
    return Response(status_code=204)
