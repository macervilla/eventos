from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.seguridad import crear_token_sesion, leer_token_confirmacion_evento
from app.models.enums import EventoEstado, RolEvento
from app.models.eventos import Evento, EventoUsuario
from app.models.proveedores import CategoriaProveedor, Proveedor, ProveedorCategoriaLink
from app.models.usuarios import User
from app.schemas.eventos import (
    EventoBase,
    EventoConfirmado,
    EventoCreate,
    EventoRead,
    SalonResumen,
)
from app.services.proveedores import get_or_create_user, validate_requested_slug


def _obtener_salon(db: Session, salon_slug: str) -> Proveedor:
    salon = db.scalar(
        select(Proveedor)
        .join(ProveedorCategoriaLink)
        .join(CategoriaProveedor)
        .where(
            Proveedor.slug == salon_slug,
            Proveedor.activo.is_(True),
            ProveedorCategoriaLink.activo.is_(True),
            CategoriaProveedor.slug == "salon",
        )
    )
    if salon is None:
        raise HTTPException(status_code=422, detail="El salon elegido no existe en el sistema")
    return salon


def _aplicar_datos(evento: Evento, data: EventoBase, salon: Proveedor | None) -> None:
    evento.nombre = data.nombre
    evento.descripcion = (data.descripcion or "").strip() or None
    evento.fecha_inicio = data.fecha_inicio
    evento.template_key = data.template_key
    evento.tipografia = data.tipografia
    if salon is None:
        # "Mi casa": la ubicacion la carga el organizador.
        evento.salon_id = None
        evento.salon = None
        evento.pais = data.pais
        evento.provincia = data.provincia
        evento.localidad = data.localidad
        evento.direccion = data.direccion
        evento.latitud = data.latitud
        evento.longitud = data.longitud
        return
    # En un salon, la ubicacion del evento es la del salon.
    evento.salon_id = salon.id
    evento.salon = salon
    evento.pais = salon.pais
    evento.provincia = salon.provincia
    evento.localidad = salon.localidad
    evento.direccion = salon.direccion
    evento.latitud = salon.latitud
    evento.longitud = salon.longitud


def evento_a_read(evento: Evento) -> EventoRead:
    salon = evento.salon
    return EventoRead(
        id=evento.id,
        nombre=evento.nombre,
        slug=evento.slug,
        descripcion=evento.descripcion,
        fecha_inicio=evento.fecha_inicio,
        template_key=evento.template_key,
        tipografia=evento.tipografia,
        estado=evento.estado.value,
        confirmado=evento.estado != EventoEstado.BORRADOR,
        lugar_tipo="salon" if evento.salon_id else "domicilio",
        pais=evento.pais,
        portada_url=evento.portada_url,
        portada_encuadre=evento.portada_encuadre,
        localidad=evento.localidad,
        provincia=evento.provincia,
        direccion=evento.direccion,
        latitud=evento.latitud,
        longitud=evento.longitud,
        salon=SalonResumen.model_validate(salon, from_attributes=True) if salon else None,
    )


def _buscar_evento(db: Session, slug: str) -> Evento:
    evento = db.scalar(select(Evento).where(Evento.slug == slug, Evento.activo.is_(True)))
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return evento


def _salon_elegido(db: Session, data: EventoBase) -> Proveedor | None:
    return _obtener_salon(db, data.salon_slug) if data.lugar_tipo == "salon" else None


def crear_evento(db: Session, data: EventoCreate) -> tuple[Evento, User]:
    salon = _salon_elegido(db, data)
    slug = validate_requested_slug(db, data.slug)
    propietario = get_or_create_user(db, str(data.email), "")
    evento = Evento(slug=slug, propietario_id=propietario.id, estado=EventoEstado.BORRADOR)
    _aplicar_datos(evento, data, salon)
    db.add(evento)
    db.flush()
    db.add(EventoUsuario(evento_id=evento.id, usuario_id=propietario.id, rol=RolEvento.PROPIETARIO))
    db.commit()
    db.refresh(evento)
    return evento, propietario


def confirmar_evento(db: Session, token: str) -> EventoConfirmado:
    slug, email = leer_token_confirmacion_evento(token)
    evento = _buscar_evento(db, slug)
    propietario = db.get(User, evento.propietario_id)
    if propietario is None or propietario.email.lower() != email or not propietario.activo:
        raise HTTPException(status_code=403, detail="El enlace no corresponde a este evento")
    if evento.estado == EventoEstado.BORRADOR:
        evento.estado = EventoEstado.PUBLICADO
        db.commit()
    return EventoConfirmado(slug=evento.slug, token=crear_token_sesion(propietario))


def obtener_evento_visible(db: Session, slug: str, usuario: User | None) -> Evento:
    """Un evento sin confirmar solo lo ve su propietario."""
    evento = _buscar_evento(db, slug)
    es_propietario = usuario is not None and evento.propietario_id == usuario.id
    if evento.estado == EventoEstado.BORRADOR and not es_propietario:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return evento


def obtener_evento_del_propietario(db: Session, slug: str, usuario: User) -> Evento:
    evento = _buscar_evento(db, slug)
    if evento.propietario_id != usuario.id:
        raise HTTPException(status_code=403, detail="No administras este evento")
    return evento


def actualizar_evento(db: Session, slug: str, data: EventoBase, usuario: User) -> Evento:
    evento = obtener_evento_del_propietario(db, slug, usuario)
    if data.slug != evento.slug:
        evento.slug = validate_requested_slug(db, data.slug)
    _aplicar_datos(evento, data, _salon_elegido(db, data))
    db.commit()
    db.refresh(evento)
    return evento


def buscar_evento_sin_confirmar(db: Session, slug: str) -> tuple[Evento, User] | None:
    evento = db.scalar(
        select(Evento).where(
            func.lower(Evento.slug) == slug.lower(),
            Evento.activo.is_(True),
            Evento.estado == EventoEstado.BORRADOR,
        )
    )
    if evento is None:
        return None
    propietario = db.get(User, evento.propietario_id)
    return (evento, propietario) if propietario else None
