import re
from urllib.error import URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

# Solo se siguen enlaces de Google Maps, para no hacer pedidos a hosts arbitrarios.
HOSTS_PERMITIDOS = re.compile(r"^(maps\.app\.goo\.gl|goo\.gl|(www\.|maps\.)?google\.[a-z]{2,3}(\.[a-z]{2})?)$")

PATRONES_COORDENADAS = [
    re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)"),  # punto exacto del lugar
    re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)"),  # centro del mapa
    re.compile(r"[?&](?:q|query|ll|destination)=(-?\d+\.\d+),\s*(-?\d+\.\d+)"),
]


def _extraer_coordenadas(texto: str) -> tuple[float, float] | None:
    texto = unquote(texto)
    for patron in PATRONES_COORDENADAS:
        encontrado = patron.search(texto)
        if encontrado:
            latitud, longitud = float(encontrado.group(1)), float(encontrado.group(2))
            if -90 <= latitud <= 90 and -180 <= longitud <= 180:
                return latitud, longitud
    return None


def resolver_coordenadas_google_maps(url: str) -> tuple[float, float] | None:
    """Obtiene lat/lng de un enlace de Google Maps, siguiendo redirecciones de enlaces cortos."""
    host = (urlparse(url).hostname or "").lower()
    if not HOSTS_PERMITIDOS.match(host):
        return None

    coordenadas = _extraer_coordenadas(url)
    if coordenadas:
        return coordenadas

    pedido = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(pedido, timeout=6) as respuesta:
            url_final = respuesta.geturl()
    except (URLError, TimeoutError, ValueError):
        return None
    return _extraer_coordenadas(url_final)
