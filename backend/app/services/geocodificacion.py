import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.core.config import settings

# Nominatim (OpenStreetMap) pide identificar la app y no superar ~1 pedido por segundo.
URL_NOMINATIM = "https://nominatim.openstreetmap.org/search"


def buscar_direccion(consulta: str, limite: int = 5) -> list[dict]:
    parametros = urlencode(
        {"q": consulta, "format": "jsonv2", "limit": limite, "accept-language": "es"}
    )
    pedido = Request(
        f"{URL_NOMINATIM}?{parametros}",
        headers={"User-Agent": f"EventosApp/0.1 ({settings.smtp_from_email})"},
    )
    try:
        with urlopen(pedido, timeout=8) as respuesta:
            resultados = json.loads(respuesta.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="No se pudo consultar el mapa") from exc
    return [
        {"latitud": float(item["lat"]), "longitud": float(item["lon"]), "nombre": item["display_name"]}
        for item in resultados
    ]
