from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.slugs import SlugPublico
from app.models.eventos import Evento
from app.models.proveedores import Proveedor

router = APIRouter(tags=["publico"])


@router.get("/publico/{slug}")
def resolver_slug(slug: str, db: Session = Depends(get_db)):
    registro = db.get(SlugPublico, slug)
    if registro is None:
        raise HTTPException(404, "Pagina no encontrada")
    entidad = db.get(Evento if registro.tipo == "evento" else Proveedor, registro.entidad_id)
    if entidad is None or not entidad.activo:
        raise HTTPException(404, "Pagina no encontrada")
    # Las paginas existentes comprueban actividad, visibilidad y permisos.
    return {"tipo": registro.tipo, "slug": registro.slug}
