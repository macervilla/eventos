from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ubicacion import UserLocationPreferenceRead, UserLocationPreferenceUpsert
from app.services.geografia import buscar_localidades
from app.services.ubicacion import get_preference, upsert_preference

router = APIRouter(prefix="/ubicacion", tags=["ubicacion"])


def get_current_user_id(x_user_id: int | None = Header(default=None)) -> int:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Falta autenticacion")
    return x_user_id


@router.get("/preferencia", response_model=UserLocationPreferenceRead | None)
def read_location_preference(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserLocationPreferenceRead | None:
    preference = get_preference(db, user_id)
    return UserLocationPreferenceRead.model_validate(preference) if preference else None


@router.put("/preferencia", response_model=UserLocationPreferenceRead)
def save_location_preference(
    data: UserLocationPreferenceUpsert,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> UserLocationPreferenceRead:
    preference = upsert_preference(db, user_id=user_id, data=data)
    return UserLocationPreferenceRead.model_validate(preference)


@router.get("/geocodificar")
def geocodificar(q: str = Query(min_length=3, max_length=300), db: Session = Depends(get_db)) -> list[dict]:
    # Compatibilidad con clientes previos: centro de localidad, no geocodificacion de calle.
    partes = [p.strip() for p in q.split(",") if p.strip()]
    consulta = partes[1] if len(partes) > 1 else partes[0] if partes else ""
    return [{"latitud": r["latitud"], "longitud": r["longitud"],
             "nombre": ", ".join(filter(None, [r["localidad"], r["provincia"], r["pais"]])), "precision": "localidad"}
            for r in buscar_localidades(db, consulta[:100])]
