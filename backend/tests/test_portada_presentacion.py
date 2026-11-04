from html.parser import HTMLParser

from PIL import Image

from app.models.eventos import EventoModulo
from app.services.media_storage import LocalMediaStorage
from app.services import portada_invitacion as render
from tests.test_administracion import auth
from tests.test_invitados import habilitar, crear


def blancos(archivo):
    with Image.open(archivo) as imagen:
        rgb = imagen.convert("RGB")
        mascara = Image.new("L", rgb.size)
        mascara.putdata([255 if min(pixel) > 230 else 0 for pixel in rgb.getdata()])
        return mascara.getbbox()


def test_imagen_respeta_posiciones_ocultos_y_cache(contexto, tmp_path, monkeypatch):
    _, db, _, _, evento = contexto
    storage = LocalMediaStorage(str(tmp_path), "/media")
    Image.new("RGB", (400, 560), "black").save(tmp_path / "portada.png")
    monkeypatch.setattr(render, "media_storage", storage)
    evento.portada_url, evento.tipografia, evento.titulo_visual = "/media/portada.png", "sistema", "Fiesta"
    cfg = {"titulo": {"x": 50, "y": 5, "visible": True},
           "fecha": {"x": 0, "y": 0, "visible": False},
           "lugar": {"x": 0, "y": 0, "visible": False}}
    modulo = EventoModulo(modulo="textos_portada", activo=False, configuracion_json=cfg)
    evento.modulos.append(modulo)
    db.flush()
    primera = render.imagen_invitacion(evento)
    archivo = storage._safe_path(primera.removeprefix("/media/"))
    with Image.open(archivo) as imagen:
        assert imagen.size == (1200, 1680)
    assert blancos(archivo)[1] < 150
    assert render.imagen_invitacion(evento) == primera
    evento.modulos.append(EventoModulo(modulo="colores_textos", activo=False,
                         configuracion_json={"titulo": "#ef4444", "fecha": "#ffffff", "lugar": "#ffffff"}))
    coloreada = render.imagen_invitacion(evento)
    assert coloreada != primera
    with Image.open(storage._safe_path(coloreada.removeprefix("/media/"))) as imagen:
        assert any(r > 150 and g < 100 and b < 100 for r, g, b in imagen.convert("RGB").getdata())
    evento.modulos[-1].configuracion_json = {"titulo": "#ffffff", "fecha": "#ffffff", "lugar": "#ffffff"}
    cfg["titulo"]["y"] = 90
    segunda = render.imagen_invitacion(evento)
    assert segunda != primera
    assert blancos(storage._safe_path(segunda.removeprefix("/media/")))[1] > 1200
    cfg["titulo"]["visible"] = False
    tercera = render.imagen_invitacion(evento)
    assert tercera != segunda
    assert blancos(storage._safe_path(tercera.removeprefix("/media/"))) is None


def test_email_foto_y_aqui_enlazan_a_misma_confirmacion(contexto, monkeypatch):
    client, _, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner, email="ana@example.com")
    envios = []
    monkeypatch.setattr("app.services.invitados_distribucion._send_email", lambda *a, **kw: envios.append(a))
    respuesta = client.post("/invitados/prueba/distribuir", headers=auth(owner), json={
        "ids": [inv["id"]], "canal": "email", "idempotencia": "email-con-foto-enlazada-1"})
    assert respuesta.status_code == 200
    resultado = respuesta.json()["resultados"][0]
    assert resultado["estado"] == "ENVIADO"

    class Enlaces(HTMLParser):
        def __init__(self):
            super().__init__(); self.hrefs = []; self.imagen_enlace = False; self.abierto = None
        def handle_starttag(self, tag, attrs):
            atributos = dict(attrs)
            if tag == "a":
                self.abierto = atributos["href"]; self.hrefs.append(self.abierto)
            if tag == "img" and self.abierto:
                self.imagen_enlace = True
        def handle_endtag(self, tag):
            if tag == "a": self.abierto = None

    html = envios[0][2]
    parser = Enlaces(); parser.feed(html)
    assert parser.imagen_enlace and parser.hrefs == [resultado["enlace"], resultado["enlace"]]
    assert ">aquí</a>" in html
