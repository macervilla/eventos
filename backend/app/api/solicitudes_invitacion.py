from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.seguridad import obtener_usuario_actual
from app.db.session import get_db
from app.models.usuarios import User
from app.schemas.solicitudes_invitacion import ContactoPublicoDatos, DecisionSolicitud, SolicitudDatos
from app.services import solicitudes_invitacion as s
from app.services.invitados import limitar

def sin_cache(response: Response):
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(prefix="/invitados", tags=["solicitudes-invitacion"], dependencies=[Depends(sin_cache)])
DB = Depends(get_db)
USUARIO = Depends(obtener_usuario_actual)


@router.get("/{slug}/solicitudes/opciones")
def opciones(slug: str, db: Session = DB, usuario: User = USUARIO):
    return s.opciones(db, slug, usuario)


@router.post("/{slug}/solicitudes", status_code=202)
def solicitar(slug: str, data: SolicitudDatos, request: Request, db: Session = DB, usuario: User = USUARIO):
    limitar(db, "solicitud-cuenta:" + str(usuario.id), 10, 600)
    limitar(db, "solicitud-ip:" + (request.client.host if request.client else "desconocido"), 30, 600)
    return s.crear_solicitud(db, slug, usuario, data)


@router.get("/{slug}/solicitudes/contactos")
def contactos(slug: str, db: Session = DB, usuario: User = USUARIO):
    return s.configuraciones(db, slug, usuario)


@router.put("/{slug}/solicitudes/contactos/{agasajado_id}")
def guardar_contacto(slug: str, agasajado_id: int, data: ContactoPublicoDatos, db: Session = DB, usuario: User = USUARIO):
    return s.guardar_contacto(db, slug, usuario, agasajado_id, data)


@router.get("/{slug}/solicitudes")
def listar(slug: str, estado: Literal["PENDIENTE", "APROBADA", "RECHAZADA", ""] = "PENDIENTE", db: Session = DB, usuario: User = USUARIO):
    return s.lista(db, slug, usuario, estado)


@router.post("/{slug}/solicitudes/{solicitud_id}/resolver")
def resolver(slug: str, solicitud_id: int, data: DecisionSolicitud, db: Session = DB, usuario: User = USUARIO):
    return s.decidir(db, slug, usuario, solicitud_id, data)
