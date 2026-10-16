from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.seguridad import obtener_usuario_actual
from app.db.session import get_db
from app.models.usuarios import User
from app.schemas.acceso import (
    AccessRequest,
    AccessResponse,
    EnlaceAccesoRequest,
    GoogleAccessRequest,
)
from app.services.acceso import (
    get_access_options_by_email,
    get_access_options_by_google_token,
    iniciar_sesion_con_enlace,
    solicitar_enlace_acceso,
)

router = APIRouter(prefix="/acceso", tags=["acceso"])


@router.get("/google-config")
def google_config() -> dict[str, str | None]:
    return {"client_id": settings.google_client_id}


@router.post("/solicitar-enlace")
def solicitar_enlace_endpoint(data: AccessRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    solicitar_enlace_acceso(db, str(data.email))
    # Misma respuesta exista o no el email, para no revelar quien esta registrado.
    return {"message": "Si el email esta registrado, te enviamos un enlace de acceso"}


@router.post("/enlace", response_model=AccessResponse)
def iniciar_sesion_con_enlace_endpoint(
    data: EnlaceAccesoRequest,
    db: Session = Depends(get_db),
) -> AccessResponse:
    return iniciar_sesion_con_enlace(db, data.token)


@router.post("/google", response_model=AccessResponse)
def validate_google_access(
    data: GoogleAccessRequest,
    db: Session = Depends(get_db),
) -> AccessResponse:
    return get_access_options_by_google_token(db, data.access_token)


@router.get("/yo", response_model=AccessResponse)
def sesion_actual(
    usuario: User = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
) -> AccessResponse:
    return get_access_options_by_email(db, usuario.email)
