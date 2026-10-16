from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ubicacion import UserLocationPreferenceRead, UserLocationPreferenceUpsert
from app.services.geocodificacion import buscar_direccion
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
def geocodificar(q: str = Query(min_length=3, max_length=300)) -> list[dict]:
    return buscar_direccion(q)
