from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from app.api.acceso import router as acceso_router
from app.api.eventos import router as eventos_router
from app.api.media import router as media_router
from app.api.proveedores import router as proveedores_router
from app.api.ubicacion import router as ubicacion_router
from app.core.config import settings

app = FastAPI(title="Eventos API", version="0.1.0")

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
app.include_router(eventos_router)
app.include_router(media_router)
Path(settings.media_root).mkdir(parents=True, exist_ok=True)
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
