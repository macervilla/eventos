from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError, IntegrityError

from app.api.acceso import router as acceso_router
from app.api.geografia import router as geografia_router
from app.api.administracion import router as administracion_router
from app.api.eventos import router as eventos_router
from app.api.invitados import router as invitados_router
from app.api.compartir import router as compartir_router
from app.services.media_storage import media_storage
from app.api.media import router as media_router
from app.api.proveedores import router as proveedores_router
from app.api.ubicacion import router as ubicacion_router
from app.core.config import settings
from app.core.log_privacidad import proteger_logs

app = FastAPI(title="Eventos API", version="0.1.0")
proteger_logs()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proveedores_router)
app.include_router(ubicacion_router)
app.include_router(acceso_router)
app.include_router(geografia_router)
app.include_router(administracion_router)
app.include_router(eventos_router)
app.include_router(invitados_router)
app.include_router(compartir_router)
app.include_router(media_router)
Path(settings.media_root).mkdir(parents=True, exist_ok=True)
media_storage.portada_predeterminada()
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")


@app.exception_handler(OperationalError)
def database_error_handler(_request: Request, _exc: OperationalError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "Base de datos no disponible o credenciales invalidas"},
    )


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(IntegrityError)
def conflicto_de_datos(_request: Request, _exc: IntegrityError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "La operacion entra en conflicto con datos existentes. Actualiza e intenta nuevamente"})
