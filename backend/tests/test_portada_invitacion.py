from datetime import UTC, datetime
from types import SimpleNamespace

from PIL import Image

from app.services.media_storage import LocalMediaStorage
from app.services import portada_invitacion as portada


def test_portada_vertical_y_cache_se_actualiza_con_los_textos(tmp_path, monkeypatch):
    storage = LocalMediaStorage(root=str(tmp_path))
    monkeypatch.setattr(portada, "media_storage", storage)
    Image.new("RGB", (300, 600), "#c4c4c4").save(tmp_path / "foto.png")
    evento = SimpleNamespace(
        portada_url="/media/foto.png", salon=None, localidad="Salon 1",
        portada_encuadre=None, titulo_visual="Te invito a mi cumple, Liliana",
        nombre="Cumple", tipografia="sistema", uuid="prueba", modulos=[], template_key="classic",
        fecha_inicio=datetime(2026, 11, 15, 0, 30, tzinfo=UTC),
    )
    url = portada.imagen_invitacion(evento)
    archivo = storage._safe_path(url.removeprefix("/media/"))
    with Image.open(archivo) as imagen:
        assert imagen.width == 1200 and imagen.height >= 1680
        assert imagen.crop((60, 350, 1020, 1000)).getextrema()[0][1] > 245
    assert portada.imagen_invitacion(evento) == url
    evento.titulo_visual = "Otro titulo"
    assert portada.imagen_invitacion(evento) != url
