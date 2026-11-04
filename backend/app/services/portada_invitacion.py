"""Portada vertical renderizada con el mismo encuadre y textos que la vista movil."""

import base64
import hashlib
import json
from datetime import UTC
from html import escape
from pathlib import Path
from uuid import uuid4

from app.schemas.eventos import ColoresTextosPortada, TextosPortada
from app.schemas.portada import EncuadrePortada

from PIL import Image
from playwright.sync_api import sync_playwright

from app.core.config import settings
from app.services.media_storage import media_storage

FUENTES = {
    "sistema": ("inherit", "inherit", "inherit", ""),
    "elegante": (
        "Playfair Display",
        "Lato",
        "700",
        "Playfair+Display:wght@700&family=Lato:wght@400;700",
    ),
    "romantica": ("Great Vibes", "Lora", "400", "Great+Vibes&family=Lora:wght@400;700"),
    "moderna": ("Montserrat", "Montserrat", "800", "Montserrat:wght@400;600;800"),
    "divertida": ("Fredoka", "Nunito", "600", "Fredoka:wght@600&family=Nunito:wght@400;700"),
    "clasica": (
        "Cormorant Garamond",
        "EB Garamond",
        "700",
        "Cormorant+Garamond:wght@700&family=EB+Garamond:wght@400;600",
    ),
    "fiesta": ("Pacifico", "Poppins", "400", "Pacifico&family=Poppins:wght@400;600"),
    "impacto": ("Bebas Neue", "Roboto", "400", "Bebas+Neue&family=Roboto:wght@400;700"),
}


def css_presentacion():
    """Usar las mismas reglas que la web compilada, con fuente local para desarrollo."""
    assets = Path("/app/frontend-dist/assets")
    archivos = sorted(assets.glob("*.css"))
    if archivos:
        return "\n".join(p.read_text(encoding="utf-8") for p in archivos)
    fuente = Path(__file__).resolve().parents[3] / "frontend/src/styles.css"
    return fuente.read_text(encoding="utf-8")


def textos_presentacion(evento):
    guardado = next((m.configuracion_json for m in evento.modulos if m.modulo == "textos_portada"), None)
    return TextosPortada(**guardado).model_dump() if guardado is not None else None


def colores_presentacion(evento):
    guardado = next((m.configuracion_json or {} for m in evento.modulos if m.modulo == "colores_textos"), {})
    return ColoresTextosPortada(**guardado).model_dump()


def bloques_presentacion(textos, titulo, lugar, colores=None):
    colores = ColoresTextosPortada(**(colores or {})).model_dump()
    contenidos = {
        "fecha": '<p class="eyebrow" data-fecha></p>',
        "titulo": f"<h1>{escape(titulo)}</h1>",
        "lugar": f"<p>{escape(lugar)}</p>",
    }
    if textos is None:
        return '<div class="provider-cover-copy">' + "".join(
            f'<div data-texto="{clave}" style="color:{colores[clave]}">{contenido}</div>' for clave, contenido in contenidos.items()
        ) + "</div>"
    bloques = []
    for clave, contenido in contenidos.items():
        bloque = textos[clave]
        if not bloque["visible"]:
            continue
        x, y = bloque["x"], bloque["y"]
        estilo = f"color:{colores[clave]};left:{x}%;top:{y}%;transform:translate(-{x}%,-{y}%)"
        bloques.append(f'<div class="texto-portada" data-texto="{clave}" style="{estilo}">{contenido}</div>')
    return "".join(bloques)


def imagen_invitacion(evento):
    portada = (
        evento.portada_url
        or (evento.salon.portada_url if evento.salon else None)
        or "/media/sistema/evento.png"
    )
    if not portada.startswith("/media/"):
        portada = "/media/sistema/evento.png"
    archivo = media_storage._safe_path(portada.removeprefix("/media/"))
    with Image.open(archivo) as imagen:
        vertical = imagen.height > imagen.width
        formato = imagen.format.lower().replace("jpg", "jpeg")
    encuadre = EncuadrePortada(**(evento.portada_encuadre or {
        "x": 50,
        "y": 50,
        "modo": "completa" if vertical else "cubrir",
    })).model_dump()
    titulo = evento.titulo_visual or evento.nombre
    lugar = evento.salon.nombre_comercial if evento.salon else evento.localidad or ""
    fuente = FUENTES.get(evento.tipografia, FUENTES["sistema"])
    textos = textos_presentacion(evento)
    colores = colores_presentacion(evento)
    css = css_presentacion()
    # Versionar tambien el render para invalidar las imagenes al cambiar el diseno.
    datos = [
        "movil-v3-colores",
        colores,
        textos,
        evento.template_key,
        hashlib.sha256(css.encode()).hexdigest(),
        str(archivo),
        settings.zona_horaria,
        archivo.stat().st_mtime_ns,
        encuadre,
        titulo,
        lugar,
        str(evento.fecha_inicio),
        fuente,
    ]
    clave = hashlib.sha256(json.dumps(datos, sort_keys=True).encode()).hexdigest()[:24]
    destino = media_storage._safe_path(f"eventos/{evento.uuid}/invitacion/{clave}.jpg")
    if destino.exists():
        return media_storage.get_public_url(destino.relative_to(media_storage.root).as_posix())
    imagen_url = f"data:image/{formato};base64," + base64.b64encode(archivo.read_bytes()).decode()
    posicion = f"{float(encuadre['x'])}% {float(encuadre['y'])}%"
    completa = encuadre.get("modo") == "completa"
    fondo = (
        f'<div class="portada-capa portada-desenfocada" style="background-image:url({imagen_url})"></div>'
        if completa
        else ""
    )
    inicio = evento.fecha_inicio
    if inicio and inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=UTC)
    fecha = inicio.isoformat() if inicio else None
    fuentes = (
        f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={fuente[3]}&display=block">'
        if fuente[3]
        else ""
    )
    plantilla = evento.template_key if evento.template_key in {"classic", "elegant", "party", "kids", "sport", "minimal", "dark"} else "classic"
    titulo_fuente = "inherit" if fuente[0] == "inherit" else f"'{fuente[0]}',sans-serif"
    texto_fuente = "inherit" if fuente[1] == "inherit" else f"'{fuente[1]}',sans-serif"
    estilo = f"--fuente-titulo:{titulo_fuente};--fuente-texto:{texto_fuente};--peso-titulo:{fuente[2]}"
    bloques = bloques_presentacion(textos, titulo, lugar, colores)
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">{fuentes}
    <style>{css}</style></head><body>
    <main class="provider-public evento-personalizado con-tipografia event-template-{plantilla}" style="{estilo}">
    <section class="provider-cover"><div class="portada-capas" aria-hidden="true">{fondo}
    <div class="portada-capa" style="background-image:url({imagen_url});background-size:{"contain" if completa else "cover"};background-position:{posicion}"></div>
    </div>{bloques}</section></main></body></html>"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            page = browser.new_page(
                viewport={"width": 400, "height": 800},
                device_scale_factor=3,
                timezone_id=settings.zona_horaria,
            )
            page.set_content(html, wait_until="networkidle", timeout=30000)
            page.locator("[data-fecha]").evaluate_all(
                "(elementos, fecha) => { for (const el of elementos) el.textContent = fecha ? new Intl.DateTimeFormat('es-AR', {weekday:'long',day:'numeric',month:'long',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(fecha)) : 'Fecha a confirmar'; }",
                fecha,
            )
            page.evaluate("document.fonts.ready")
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_name(f"{destino.stem}-{uuid4().hex}.tmp.jpg")
            try:
                page.locator("section").screenshot(path=str(temporal), type="jpeg", quality=90)
                temporal.replace(destino)
            finally:
                temporal.unlink(missing_ok=True)
        finally:
            browser.close()
    return media_storage.get_public_url(destino.relative_to(media_storage.root).as_posix())
