from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.seguridad import obtener_usuario_actual, obtener_usuario_opcional
from app.db.session import get_db
from app.models.usuarios import User
from app.schemas.portada import EncuadrePortada
from app.schemas.eventos import (
    EventoConfirmado,
    EventoConfirmarRequest,
    EventoCreado,
    EventoCreate,
    EventoRead,
    EventoUpdate,
)
from app.services.email import send_event_confirmation_email
from app.services.eventos import (
    actualizar_evento,
    buscar_evento_sin_confirmar,
    confirmar_evento,
    crear_evento,
    evento_a_read,
    obtener_evento_del_propietario,
    obtener_evento_visible,
)

router = APIRouter(prefix="/eventos", tags=["eventos"])


@router.post("", response_model=EventoCreado, status_code=201)
def crear_evento_endpoint(data: EventoCreate, db: Session = Depends(get_db)) -> EventoCreado:
    evento, propietario = crear_evento(db, data)
    send_event_confirmation_email(evento, propietario.email)
    return EventoCreado(**evento_a_read(evento).model_dump(), email_confirmacion=propietario.email)


@router.post("/confirmar", response_model=EventoConfirmado)
def confirmar_evento_endpoint(
    data: EventoConfirmarRequest,
    db: Session = Depends(get_db),
) -> EventoConfirmado:
    return confirmar_evento(db, data.token)


@router.post("/{slug}/reenviar-confirmacion")
def reenviar_confirmacion_endpoint(slug: str, db: Session = Depends(get_db)) -> dict[str, str]:
    # Solo reenvia al email ya registrado, asi que no hace falta sesion.
    encontrado = buscar_evento_sin_confirmar(db, slug)
    if encontrado:
        evento, propietario = encontrado
        send_event_confirmation_email(evento, propietario.email)
    return {"message": "Si el evento esta pendiente, reenviamos el mail de confirmacion"}


@router.get("/{slug}", response_model=EventoRead)
def leer_evento_endpoint(
    slug: str,
    db: Session = Depends(get_db),
    usuario: User | None = Depends(obtener_usuario_opcional),
) -> EventoRead:
    return evento_a_read(obtener_evento_visible(db, slug, usuario))


@router.put("/{slug}", response_model=EventoRead)
def actualizar_evento_endpoint(
    slug: str,
    data: EventoUpdate,
    db: Session = Depends(get_db),
    usuario: User = Depends(obtener_usuario_actual),
) -> EventoRead:
    return evento_a_read(actualizar_evento(db, slug, data, usuario))


@router.put("/{slug}/portada-encuadre", response_model=EventoRead)
def guardar_encuadre_portada_endpoint(
    slug: str,
    data: EncuadrePortada,
    db: Session = Depends(get_db),
    usuario: User = Depends(obtener_usuario_actual),
) -> EventoRead:
    evento = obtener_evento_del_propietario(db, slug, usuario)
    evento.portada_encuadre = data.model_dump()
    db.commit()
    db.refresh(evento)
    return evento_a_read(evento)
