from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.models.enums import EventoEstado
from app.models.eventos import Evento
from app.services.media_storage import media_storage

router = APIRouter(tags=["compartir"])


@router.get("/compartir/{slug}", response_class=HTMLResponse)
def compartir(slug: str, dev: bool = False, db=Depends(get_db)):
    evento = db.scalar(
        select(Evento).where(
            Evento.slug == slug, Evento.activo.is_(True), Evento.estado != EventoEstado.BORRADOR
        )
    )
    if evento is None:
        raise HTTPException(404, "Evento no disponible")
    base = settings.frontend_public_url.rstrip("/") + "/"
    portada = evento.portada_url or (evento.salon.portada_url if evento.salon else None)
    if not portada or not portada.startswith("/media/"):
        portada = "/media/sistema/evento.png"
    try:
        imagen = media_storage.imagen_compartida(portada.removeprefix("/media/"))
    except (OSError, ValueError, HTTPException):
        imagen = "/media/sistema/evento.png"
    absoluta = urljoin(base, imagen.lstrip("/"))
    local = urlsplit(base).hostname in {"localhost", "127.0.0.1"}
    if not local and urlsplit(base).scheme != "https":
        raise HTTPException(
            503, "Configurar FRONTEND_PUBLIC_URL con HTTPS para compartir el evento"
        )
    titulo = evento.titulo_visual or evento.nombre
    fecha = (
        evento.fecha_inicio.astimezone(ZoneInfo(settings.zona_horaria)).strftime("%d/%m/%Y %H:%M")
        if evento.fecha_inicio
        else "Fecha a confirmar"
    )
    descripcion = fecha + ". " + (evento.descripcion or "Estas invitado a nuestro evento")[:250]
    url = urljoin(base, "e/" + evento.slug)  # Nunca exponer token personal ni cupos en OG.
    tags = {
        "og:title": titulo,
        "og:description": descripcion,
        "og:image": absoluta,
        "og:url": url,
        "og:type": "website",
    }
    meta = "".join(
        f'<meta property="{k}" content="{escape(v, quote=True)}">' for k, v in tags.items()
    )
    meta += f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{escape(titulo, quote=True)}"><meta name="twitter:description" content="{escape(descripcion, quote=True)}"><meta name="twitter:image" content="{escape(absoluta, quote=True)}">'
    archivo = Path("/app/frontend-dist/index.html")
    shell = (
        archivo.read_text(encoding="utf-8")
        if archivo.exists() and not dev
        else '<!doctype html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Eventos</title></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>'
    )
    shell = shell.replace("</head>", meta + '<meta name="referrer" content="no-referrer"></head>')
    return HTMLResponse(
        shell, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
    )
