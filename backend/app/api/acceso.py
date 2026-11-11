from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.seguridad import obtener_usuario_actual, obtener_usuario_vinculacion_opcional
from app.db.session import get_db
from app.models.usuarios import User
from app.schemas.acceso import (
    AccessRequest,
    AccessResponse,
    EnlaceAccesoRequest,
    GoogleAccessRequest,
)
from app.services.acceso import (
    get_access_options_by_user,
    get_access_options_by_google_token,
    iniciar_sesion_con_enlace,
    solicitar_enlace_acceso,
)

router = APIRouter(prefix="/acceso", tags=["acceso"])


@router.get("/google-config")
def google_config(response: Response) -> dict[str, str | None]:
    response.headers["Cache-Control"] = "no-store"
    return {"client_id": settings.google_client_id}


@router.post("/solicitar-enlace")
def solicitar_enlace_endpoint(data: AccessRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    solicitar_enlace_acceso(db, str(data.email), data.destino)
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
    actual: User | None = Depends(obtener_usuario_vinculacion_opcional),
) -> AccessResponse:
    return get_access_options_by_google_token(db, data.credential, actual)


@router.get("/yo", response_model=AccessResponse)
def sesion_actual(
    response: Response,
    usuario: User = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
) -> AccessResponse:
    response.headers["Cache-Control"] = "no-store"
    return get_access_options_by_user(db, usuario, incluir_vinculadas=True, metodo="google", email_google=usuario._email_google_sesion)
