from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.seguridad import crear_token_sesion, leer_token_confirmacion_evento
from app.models.enums import EventoEstado, RolEvento, MediaTipo
from app.models.eventos import Evento, EventoUsuario, EventoModulo
from app.models.proveedores import CategoriaProveedor, Proveedor, ProveedorCategoriaLink
from app.models.usuarios import User
from app.schemas.eventos import (
    EventoBase,
    EventoEditable,
    ColoresEvento,
    GaleriaConfig,
    EventoConfirmado,
    EventoCreate,
    EventoRead,
    SalonResumen,
    TextosPortada,
    ColoresTextosPortada,
)
from app.services.proveedores import get_or_create_user, validate_requested_slug
from app.services.geografia import resolver_geografia


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


def _aplicar_datos(evento: Evento, data: EventoEditable, salon: Proveedor | None, db: Session) -> None:
    evento.titulo_visual = (data.titulo_visual or "").strip() or None
    evento.colores = data.colores.model_dump()
    existentes = {m.modulo: m for m in evento.modulos}
    if data.colores_textos is not None:
        modulo = existentes.get("colores_textos")
        if modulo is None:
            modulo = EventoModulo(modulo="colores_textos", activo=False)
            evento.modulos.append(modulo)
        modulo.configuracion_json = data.colores_textos.model_dump()
    for clave in {"detalles", "ubicacion", "galeria"}:
        if clave in existentes:
            existentes[clave].activo = clave in data.modulos_habilitados
        else:
            evento.modulos.append(EventoModulo(modulo=clave, activo=clave in data.modulos_habilitados))
    if data.galeria_config is not None:
        modulo = next(m for m in evento.modulos if m.modulo == "galeria")
        modulo.configuracion_json = data.galeria_config.model_dump()
    evento.descripcion = (data.descripcion or "").strip() or None
    evento.fecha_inicio = data.fecha_inicio
    evento.template_key = data.template_key
    evento.tipografia = data.tipografia
    if salon is None:
        campos = {c: getattr(data, c) for c in ("localidad", "provincia", "pais", "latitud", "longitud")}
        for c in ("geoname_id", "codigo_pais"):
            if c in data.model_fields_set:
                campos[c] = getattr(data, c)
        geo = resolver_geografia(db, campos, evento)
        # "Mi casa": la ubicacion la carga el organizador.
        evento.salon_id = None
        evento.salon = None
        evento.pais = geo["pais"]
        evento.provincia = geo["provincia"]
        evento.localidad = geo["localidad"]
        evento.geoname_id = geo.get("geoname_id")
        evento.codigo_pais = geo.get("codigo_pais", evento.codigo_pais)
        evento.direccion = data.direccion
        evento.latitud = geo.get("latitud")
        evento.longitud = geo.get("longitud")
        return
    # En un salon, la ubicacion del evento es la del salon.
    evento.salon_id = salon.id
    evento.salon = salon
    evento.geoname_id = salon.geoname_id
    evento.codigo_pais = salon.codigo_pais
    evento.pais = salon.pais
    evento.provincia = salon.provincia
    evento.localidad = salon.localidad
    evento.direccion = salon.direccion
    evento.latitud = salon.latitud
    evento.longitud = salon.longitud


def evento_a_read(evento: Evento) -> EventoRead:
    salon = evento.salon
    return EventoRead(
        colores_textos=ColoresTextosPortada(**next((m.configuracion_json or {} for m in evento.modulos if m.modulo == "colores_textos"), {})),
        textos_portada=next((TextosPortada(**m.configuracion_json) for m in evento.modulos if m.modulo == "textos_portada"), None),
        galeria_config=GaleriaConfig(**next((m.configuracion_json or {} for m in evento.modulos if m.modulo == "galeria"), {})),
        titulo_visual=evento.titulo_visual,
        colores=ColoresEvento(**(evento.colores or {})),
        modulos_habilitados=[m.modulo for m in evento.modulos if m.activo] if evento.modulos else ["detalles", "ubicacion"],
        galeria=[{"id": m.id, "url": m.url} for m in sorted(evento.imagenes, key=lambda m: m.id) if m.activo and m.tipo == MediaTipo.GALERIA],
        limite_galeria=10,
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
        geoname_id=evento.geoname_id,
        codigo_pais=evento.codigo_pais,
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


def _salon_elegido(db: Session, data: EventoEditable) -> Proveedor | None:
    return _obtener_salon(db, data.salon_slug) if data.lugar_tipo == "salon" else None


def crear_evento(db: Session, data: EventoCreate, usuario: User | None = None) -> tuple[Evento, User]:
    salon = _salon_elegido(db, data)
    slug = validate_requested_slug(db, data.slug)
    propietario = usuario if usuario and usuario.activo and usuario.email.lower() == str(data.email).lower() else get_or_create_user(db, str(data.email), "")
    publicado = usuario is not None and usuario.id == propietario.id and propietario.email_validado_en is not None
    evento = Evento(nombre=data.nombre, slug=slug, propietario_id=propietario.id,
                    estado=EventoEstado.PUBLICADO if publicado else EventoEstado.BORRADOR)
    _aplicar_datos(evento, data, salon, db)
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
    if propietario.email_validado_en is None:
        propietario.email_validado_en = datetime.now(UTC)
    db.commit()
    return EventoConfirmado(slug=evento.slug, token=crear_token_sesion(propietario))


def obtener_evento_visible(db: Session, slug: str, usuario: User | None) -> Evento:
    """Un evento sin confirmar solo lo ve su propietario."""
    evento = _buscar_evento(db, slug)
    if evento.estado == EventoEstado.BORRADOR and not puede_editar_evento(db, evento, usuario):
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return evento


def obtener_evento_del_propietario(db: Session, slug: str, usuario: User) -> Evento:
    evento = _buscar_evento(db, slug)
    if not puede_editar_evento(db, evento, usuario):
        raise HTTPException(status_code=403, detail="No administras este evento")
    return evento


def rol_en_evento(db: Session, evento: Evento, usuario: User | None) -> str:
    if usuario is None or not usuario.activo:
        return "visitante"
    if usuario.es_superadministrador:
        return "superadministrador"
    if evento.propietario_id == usuario.id:
        return "administrador"
    roles = db.scalars(select(EventoUsuario.rol).where(
        EventoUsuario.evento_id == evento.id, EventoUsuario.usuario_id == usuario.id,
    )).all()
    if RolEvento.PROPIETARIO in roles:
        return "administrador"
    if RolEvento.ADMIN_EVENTO in roles:
        asignacion = db.scalar(select(EventoUsuario).where(EventoUsuario.evento_id == evento.id,
                              EventoUsuario.usuario_id == usuario.id, EventoUsuario.rol == RolEvento.ADMIN_EVENTO))
        if asignacion.permisos is None or "configurar_evento" in asignacion.permisos:
            return "administrador"
    if RolEvento.ENCARGADO in roles:
        return "colaborador"
    asignaciones = db.scalars(select(EventoUsuario).where(
        EventoUsuario.evento_id == evento.id, EventoUsuario.usuario_id == usuario.id)).all()
    for rol, etiqueta in [(RolEvento.AGASAJADO, "agasajado"),
                          (RolEvento.GESTOR_INVITADOS, "gestor de invitados"),
                          (RolEvento.CONTROL_INGRESO, "control de ingreso")]:
        if any(a.rol == rol and a.permisos != [] for a in asignaciones):
            return etiqueta
    return "visitante"


def puede_editar_evento(db: Session, evento: Evento, usuario: User | None) -> bool:
    return rol_en_evento(db, evento, usuario) in {"administrador", "colaborador", "superadministrador"}


def actualizar_evento(db: Session, slug: str, data: EventoEditable, usuario: User) -> Evento:
    evento = obtener_evento_del_propietario(db, slug, usuario)
    _aplicar_datos(evento, data, _salon_elegido(db, data), db)
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
