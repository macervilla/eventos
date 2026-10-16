from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from app.models.enums import Plan
from app.models.eventos import Evento
from app.models.proveedores import CategoriaProveedor, Proveedor, ProveedorCategoriaLink
from app.models.usuarios import User
from app.schemas.proveedores import ProveedorCreate, ProveedorRead
from app.services.distance import haversine_km
from app.services.mapas import resolver_coordenadas_google_maps
from app.services.email import send_provider_confirmation_email, send_provider_edit_access_email
from app.services.slug import slugify


DEFAULT_CATEGORIAS = [
    "Salón",
    "DJ",
    "Fotografía",
    "Video",
    "Catering",
    "Decoración",
    "Animación",
    "Sonido",
    "Iluminación",
    "Barra de tragos",
    "Transporte",
    "Indumentaria",
    "Souvenirs",
    "Tortas",
    "Otros",
]


def ensure_default_categories(db: Session) -> None:
    existing = set(db.scalars(select(CategoriaProveedor.slug)).all())
    for nombre in DEFAULT_CATEGORIAS:
        slug = slugify(nombre)
        if slug not in existing:
            db.add(CategoriaProveedor(nombre=nombre, slug=slug))
    db.flush()


def validate_requested_slug(db: Session, value: str, exclude_id: int | None = None) -> str:
    candidate = slugify(value)
    provider_query = select(Proveedor.id).where(Proveedor.slug == candidate)
    if exclude_id is not None:
        provider_query = provider_query.where(Proveedor.id != exclude_id)
    if db.scalar(provider_query):
        raise HTTPException(status_code=409, detail="El slug ya esta en uso")

    if db.scalar(select(Evento.id).where(Evento.slug == candidate)):
        raise HTTPException(status_code=409, detail="El slug ya esta en uso")

    event_names = db.scalars(select(Evento.nombre)).all()
    if any(slugify(event_name) == candidate for event_name in event_names):
        raise HTTPException(status_code=409, detail="El slug ya esta en uso")
    return candidate


def _sync_categories(db: Session, proveedor: Proveedor, categorias: list[str]) -> None:
    ensure_default_categories(db)
    normalized = [slugify(categoria) for categoria in categorias if categoria.strip()]
    if not normalized:
        normalized = ["otros"]

    category_rows = list(
        db.scalars(select(CategoriaProveedor).where(CategoriaProveedor.slug.in_(normalized))).all()
    )
    found = {category.slug for category in category_rows}
    for raw_slug in normalized:
        if raw_slug not in found:
            category = CategoriaProveedor(nombre=raw_slug.replace("-", " ").title(), slug=raw_slug)
            db.add(category)
            category_rows.append(category)
            found.add(raw_slug)
    db.flush()

    db.execute(
        delete(ProveedorCategoriaLink).where(ProveedorCategoriaLink.proveedor_id == proveedor.id)
    )
    db.flush()
    for category in category_rows:
        proveedor.categorias.append(ProveedorCategoriaLink(categoria=category))


def get_or_create_user(db: Session, email: str, nombre: str) -> User:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
    if user:
        return user

    user = User(email=normalized_email, nombre=nombre.strip() or None)
    db.add(user)
    db.flush()
    return user


def _actualizar_coordenadas(proveedor: Proveedor, url_anterior: str | None) -> None:
    if not proveedor.google_maps_url:
        return
    if proveedor.google_maps_url != url_anterior:
        proveedor.latitud = None
        proveedor.longitud = None
    if proveedor.latitud is None or proveedor.longitud is None:
        coordenadas = resolver_coordenadas_google_maps(proveedor.google_maps_url)
        if coordenadas:
            proveedor.latitud, proveedor.longitud = coordenadas


def proveedor_to_read(proveedor: Proveedor, distance: float | None = None) -> ProveedorRead:
    categorias_detalle = [
        link.categoria for link in proveedor.categorias if link.activo and link.categoria.activo
    ]
    return ProveedorRead(
        id=proveedor.id,
        usuario_id=proveedor.usuario_id,
        nombre_comercial=proveedor.nombre_comercial,
        slug=proveedor.slug,
        cuit=proveedor.cuit,
        descripcion=proveedor.descripcion,
        categorias=[category.slug for category in categorias_detalle],
        categorias_detalle=categorias_detalle,
        pais=proveedor.pais,
        localidad=proveedor.localidad,
        provincia=proveedor.provincia,
        direccion=proveedor.direccion,
        google_maps_url=proveedor.google_maps_url,
        google_place_id=proveedor.google_place_id,
        ubicacion_referencia=proveedor.ubicacion_referencia,
        latitud=proveedor.latitud,
        longitud=proveedor.longitud,
        whatsapp=proveedor.whatsapp,
        telefono=proveedor.telefono,
        email=proveedor.email,
        web=proveedor.web,
        instagram=proveedor.instagram,
        facebook=proveedor.facebook,
        logo_url=proveedor.logo_url,
        portada_url=proveedor.portada_url,
        portada_encuadre=proveedor.portada_encuadre,
        horarios=proveedor.horarios,
        template_key=proveedor.template_key,
        plan=proveedor.plan,
        activo=proveedor.activo,
        distancia_km=round(distance, 1) if distance is not None else None,
    )


def create_proveedor(db: Session, data: ProveedorCreate) -> Proveedor:
    values = data.model_dump(mode="json", exclude={"categorias", "usuario_id"})
    values["slug"] = validate_requested_slug(db, values["slug"])
    user = get_or_create_user(
        db,
        values["email"],
        values["nombre_comercial"],
    )
    values["usuario_id"] = user.id
    proveedor = Proveedor(**values)
    _actualizar_coordenadas(proveedor, None)
    db.add(proveedor)
    db.flush()
    _sync_categories(db, proveedor, data.categorias)
    db.commit()
    db.refresh(proveedor)
    return proveedor


def update_proveedor(db: Session, slug: str, data: ProveedorCreate) -> Proveedor:
    proveedor = get_proveedor_by_slug(db, slug)
    values = data.model_dump(mode="json", exclude={"categorias", "usuario_id"})
    requested_slug = values.pop("slug", None)
    url_anterior = proveedor.google_maps_url
    for key, value in values.items():
        setattr(proveedor, key, value)
    _actualizar_coordenadas(proveedor, url_anterior)
    if requested_slug and requested_slug != proveedor.slug:
        proveedor.slug = validate_requested_slug(db, requested_slug, exclude_id=proveedor.id)
    _sync_categories(db, proveedor, data.categorias)
    db.commit()
    db.refresh(proveedor)
    return proveedor


def get_proveedor_by_slug(db: Session, slug: str) -> Proveedor:
    proveedor = db.scalar(
        select(Proveedor).where(Proveedor.slug == slug, Proveedor.activo.is_(True))
    )
    if proveedor is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return proveedor


def soft_delete_proveedor(db: Session, slug: str) -> None:
    proveedor = get_proveedor_by_slug(db, slug)
    proveedor.activo = False
    proveedor.deleted_at = datetime.utcnow()
    db.commit()


def request_provider_edit_access(db: Session, slug: str) -> None:
    proveedor = get_proveedor_by_slug(db, slug)
    send_provider_edit_access_email(proveedor)


def resend_provider_confirmation(db: Session, slug: str, email: str) -> Proveedor:
    proveedor = get_proveedor_by_slug(db, slug)
    normalized_email = email.strip().lower()
    proveedor.email = normalized_email
    proveedor.usuario_id = get_or_create_user(
        db,
        normalized_email,
        proveedor.nombre_comercial,
    ).id
    db.commit()
    db.refresh(proveedor)
    send_provider_confirmation_email(proveedor)
    return proveedor


def search_proveedores(
    db: Session,
    *,
    categoria: str | None = None,
    localidad: str | None = None,
    provincia: str | None = None,
    nombre: str | None = None,
    plan: Plan | None = None,
    lat: float | None = None,
    lng: float | None = None,
    radio_km: float | None = None,
) -> list[ProveedorRead]:
    query: Select[tuple[Proveedor]] = select(Proveedor).where(Proveedor.activo.is_(True))

    if categoria:
        category_slug = slugify(categoria)
        query = (
            query.join(ProveedorCategoriaLink)
            .join(CategoriaProveedor)
            .where(
                ProveedorCategoriaLink.activo.is_(True),
                CategoriaProveedor.activo.is_(True),
                CategoriaProveedor.slug == category_slug,
            )
        )
    if localidad:
        query = query.where(Proveedor.localidad.ilike(f"%{localidad.strip()}%"))
    if provincia:
        query = query.where(Proveedor.provincia.ilike(f"%{provincia.strip()}%"))
    if nombre:
        query = query.where(
            func.lower(Proveedor.nombre_comercial).contains(nombre.strip().lower())
        )
    if plan is not None:
        query = query.where(Proveedor.plan == plan)

    proveedores = list(db.scalars(query).all())
    with_distances: list[tuple[Proveedor, float | None]] = []

    for proveedor in proveedores:
        distance = None
        if lat is not None and lng is not None and proveedor.latitud is not None and proveedor.longitud is not None:
            distance = haversine_km(lat, lng, proveedor.latitud, proveedor.longitud)
            if radio_km is not None and distance > radio_km:
                continue
        with_distances.append((proveedor, distance))

    if lat is not None and lng is not None:
        with_distances.sort(key=lambda item: item[1] if item[1] is not None else float("inf"))
    else:
        with_distances.sort(key=lambda item: item[0].nombre_comercial.lower())

    return [
        proveedor_to_read(proveedor, distance)
        for proveedor, distance in with_distances
    ]
