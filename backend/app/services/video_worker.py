import asyncio
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.video import reconciliar

logger = logging.getLogger(__name__)


def revisar():
    try:
        with SessionLocal() as db:
            reconciliar(db)
    except Exception:
        # No registrar URLs privadas, credenciales ni respuestas del servidor de video.
        logger.warning("No se pudo reconciliar video; se reintentara sin afectar las fotos")


@asynccontextmanager
async def ciclo_video(app):
    async def bucle():
        while True:
            await asyncio.sleep(5)
            await asyncio.to_thread(revisar)
    tarea = asyncio.create_task(bucle()) if settings.video_enabled else None
    try:
        yield
    finally:
        if tarea:
            tarea.cancel()
            try:
                await tarea
            except asyncio.CancelledError:
                pass
