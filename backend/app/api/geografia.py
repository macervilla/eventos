from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.geografia import buscar_localidades, obtener_localidad

router = APIRouter(prefix="/geografia", tags=["geografia"])


@router.get("/localidades")
def localidades(db: Annotated[Session, Depends(get_db)], q: str = Query(min_length=3, max_length=100),
                limit: int = Query(default=10, ge=1),
                codigo_pais: str | None = Query(default=None, pattern=r"^[A-Za-z]{2}$")) -> dict:
    if limit > settings.geo_max_resultados:
        raise HTTPException(422, f"El limite maximo es {settings.geo_max_resultados}")
    return {"resultados": buscar_localidades(db, q, limit, codigo_pais.upper() if codigo_pais else None),
            "atribucion": "GeoNames (CC BY 4.0)", "fuente": "https://www.geonames.org/"}


@router.get("/localidades/{geoname_id}")
def localidad(geoname_id: int, db: Annotated[Session, Depends(get_db)]) -> dict:
    return obtener_localidad(db, geoname_id)
