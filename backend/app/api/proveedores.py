from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.seguridad import (
    crear_token_alta,
    exigir_duenio_proveedor,
    obtener_usuario_actual,
    validar_token_alta,
)
from app.db.session import get_db
from app.models.enums import Plan
from app.models.usuarios import User
from app.schemas.portada import EncuadrePortada
from app.schemas.proveedores import (
    ProveedorCreado,
    ProveedorCreate,
    ProveedorEmailRequest,
    ProveedorRead,
)
from app.services.proveedores import (
    create_proveedor,
    get_proveedor_by_slug,
    proveedor_to_read,
    request_provider_edit_access,
    resend_provider_confirmation,
    search_proveedores,
    soft_delete_proveedor,
    update_proveedor,
)

router = APIRouter(prefix="/proveedores", tags=["proveedores"])


@router.get("", response_model=list[ProveedorRead])
def list_proveedores(
    categoria: str | None = None,
    localidad: str | None = None,
    provincia: str | None = None,
    nombre: str | None = None,
    plan: Plan | None = None,
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radio_km: float | None = Query(default=None, gt=0, le=500),
    db: Session = Depends(get_db),
) -> list[ProveedorRead]:
    return search_proveedores(
        db,
        categoria=categoria,
        localidad=localidad,
        provincia=provincia,
        nombre=nombre,
        plan=plan,
        lat=lat,
        lng=lng,
        radio_km=radio_km,
    )


@router.post("", response_model=ProveedorCreado, status_code=201)
def create_proveedor_endpoint(
    data: ProveedorCreate,
    db: Session = Depends(get_db),
) -> ProveedorCreado:
    proveedor = create_proveedor(db, data)
    return ProveedorCreado(
        **proveedor_to_read(proveedor).model_dump(),
        token_alta=crear_token_alta(proveedor.slug),
    )


@router.get("/{slug}", response_model=ProveedorRead)
def read_proveedor(slug: str, db: Session = Depends(get_db)) -> ProveedorRead:
    proveedor = get_proveedor_by_slug(db, slug)
    return proveedor_to_read(proveedor)


@router.put("/{slug}", response_model=ProveedorRead)
def update_proveedor_endpoint(
    slug: str,
    data: ProveedorCreate,
    db: Session = Depends(get_db),
    usuario: User = Depends(obtener_usuario_actual),
) -> ProveedorRead:
    exigir_duenio_proveedor(db, slug, usuario)
    proveedor = update_proveedor(db, slug, data)
    return proveedor_to_read(proveedor)


@router.put("/{slug}/portada-encuadre", response_model=ProveedorRead)
def guardar_encuadre_portada_endpoint(
    slug: str,
    data: EncuadrePortada,
    db: Session = Depends(get_db),
    usuario: User = Depends(obtener_usuario_actual),
) -> ProveedorRead:
    proveedor = exigir_duenio_proveedor(db, slug, usuario)
    proveedor.portada_encuadre = data.model_dump()
    db.commit()
    db.refresh(proveedor)
    return proveedor_to_read(proveedor)


@router.post("/{slug}/solicitar-edicion")
def request_provider_edit_access_endpoint(
    slug: str,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    request_provider_edit_access(db, slug)
    return {"message": "Se envio el enlace de edicion al email del proveedor"}


@router.post("/{slug}/reenviar-confirmacion", response_model=ProveedorRead)
def resend_provider_confirmation_endpoint(
    slug: str,
    data: ProveedorEmailRequest,
    db: Session = Depends(get_db),
) -> ProveedorRead:
    validar_token_alta(data.token_alta, slug)
    proveedor = resend_provider_confirmation(db, slug, str(data.email))
    return proveedor_to_read(proveedor)


@router.delete("/{slug}", status_code=204)
def delete_proveedor_endpoint(
    slug: str,
    db: Session = Depends(get_db),
    usuario: User = Depends(obtener_usuario_actual),
) -> None:
    exigir_duenio_proveedor(db, slug, usuario)
    soft_delete_proveedor(db, slug)
