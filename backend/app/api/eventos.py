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
    TextosPortada,
)
from app.services.email import send_event_confirmation_email
from app.services.bienvenida import enviar_bienvenida_una_vez
from app.models.enums import EventoEstado
from fastapi import HTTPException
from app.services.eventos import (
    actualizar_evento,
    buscar_evento_sin_confirmar,
    confirmar_evento,
    crear_evento,
    evento_a_read,
    obtener_evento_del_propietario,
    obtener_evento_visible,
    rol_en_evento,
    puede_editar_evento,
)

router = APIRouter(prefix="/eventos", tags=["eventos"])


@router.put("/{slug}/textos-portada", response_model=EventoRead)
def guardar_textos_portada(slug: str, data: TextosPortada, db: Session = Depends(get_db),
                           usuario: User = Depends(obtener_usuario_actual)) -> EventoRead:
    from app.models.eventos import EventoModulo

    evento = obtener_evento_del_propietario(db, slug, usuario)
    # Bloquear la fila para serializar la primera creacion de esta configuracion.
    from sqlalchemy import select
    from app.models.eventos import Evento
    db.execute(select(Evento.id).where(Evento.id == evento.id).with_for_update())
    db.expire(evento, ["modulos"])
    modulo = next((m for m in evento.modulos if m.modulo == "textos_portada"), None)
    if modulo is None:
        modulo = EventoModulo(modulo="textos_portada", activo=False)
        evento.modulos.append(modulo)
    modulo.configuracion_json = data.model_dump()
    db.commit()
    db.refresh(evento)
    return evento_a_read(evento)


@router.get("/{slug}/permisos")
def permisos_evento(slug: str, db: Session = Depends(get_db),
                    usuario: User | None = Depends(obtener_usuario_opcional)) -> dict:
    evento = obtener_evento_visible(db, slug, usuario)
    from app.services.invitados_permisos import acceso
    from fastapi import HTTPException
    permisos_invitados = []
    if usuario:
        try:
            permisos_invitados = sorted(acceso(db, slug, usuario, habilitado=False).permisos)
        except HTTPException:
            pass
    return {"usuario": {"id": usuario.id, "email": usuario.email} if usuario else None,
            "permisos_invitados": permisos_invitados,
            "rol": rol_en_evento(db, evento, usuario),
            "puede_editar": puede_editar_evento(db, evento, usuario)}


@router.post("", response_model=EventoCreado, status_code=201)
def crear_evento_endpoint(data: EventoCreate, db: Session = Depends(get_db),
                          usuario: User | None = Depends(obtener_usuario_opcional)) -> EventoCreado:
    evento, propietario = crear_evento(db, data, usuario)
    error_correo = None
    try:
        enviada = enviar_bienvenida_una_vez(db, propietario, f"/e/{evento.slug}")
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        enviada, error_correo = False, str(exc.detail)
    return EventoCreado(**evento_a_read(evento).model_dump(), bienvenida_enviada=enviada, error_correo=error_correo,
                        email_confirmacion=propietario.email if not propietario.email_validado_en else None)


@router.post("/{slug}/publicar", response_model=EventoRead)
def publicar_evento(slug: str, db: Session = Depends(get_db),
                    usuario: User = Depends(obtener_usuario_actual)) -> EventoRead:
    evento = obtener_evento_del_propietario(db, slug, usuario)
    if not usuario.email_validado_en:
        raise HTTPException(403, "Valida tu email una vez antes de publicar")
    if evento.estado == EventoEstado.BORRADOR:
        evento.estado = EventoEstado.PUBLICADO
        db.commit()
    return evento_a_read(evento)


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
