"""Rutas definitivas con API simulada, sin cambiar datos ni enviar correos."""
import json
import os
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def main():
    base = os.getenv("EVENTOS_UI_URL", "http://127.0.0.1:5187/eventos").rstrip("/")
    evento = dict(id=1, nombre="Cumple", slug="cumple", titulo_visual="Nuestra fiesta",
                  textos_portada=None, descripcion="Nos encontramos", fecha_inicio=None,
                  lugar_tipo="salon", direccion=None, localidad=None, provincia=None,
                  pais="Argentina", latitud=None, longitud=None,
                  salon=dict(slug="salon", nombre_comercial="Salon del Lago"),
                  portada_url=None, portada_encuadre=None, template_key="classic",
                  tipografia="sistema", colores=dict(fondo="#f4f7f6", texto="#18212f", acento="#245c48"),
                  estado="PUBLICADO", confirmado=True, modulos_habilitados=["detalles", "ubicacion"],
                  galeria=[], limite_galeria=10, galeria_config=dict(modo="grilla", filas=2, columnas=2))
    proveedor = dict(id=2, slug="salon", nombre_comercial="Salon del Lago", descripcion="Celebraciones",
                     categorias_detalle=[], categorias=[], template_key="professional",
                     textos_portada=None, colores_textos={}, portada_url=None, portada_encuadre=None)
    solicitudes = []

    def api(route):
        ruta = urlsplit(route.request.url).path.removeprefix("/api-vps").removeprefix("/eventos/api")
        solicitudes.append(ruta)
        estado = 200
        if ruta == "/publico/cumple":
            data = {"tipo": "evento", "slug": "cumple"}
        elif ruta == "/publico/salon":
            data = {"tipo": "proveedor", "slug": "salon"}
        elif ruta == "/eventos/cumple/permisos":
            data = dict(puede_editar=False, usuario=None, rol="visitante", permisos_invitados=[])
        elif ruta == "/eventos/cumple":
            data = evento
        elif ruta == "/proveedores/salon":
            data = proveedor
        else:
            data, estado = {"detail": "No encontrado"}, 404
        route.fulfill(status=estado, content_type="application/json", body=json.dumps(data))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 390):
            context = browser.new_context(viewport={"width": ancho, "height": 900})
            context.route("**/api-vps/**", api)
            context.route("**/eventos/api/**", api)
            page = context.new_page()
            errores = []
            page.on("pageerror", lambda error: errores.append(str(error)))
            page.goto(base + "/cumple")
            expect(page.get_by_role("heading", name="Nuestra fiesta", exact=True)).to_be_visible()
            enlace = page.get_by_role("link", name="Salon del Lago", exact=True)
            expect(enlace).to_have_attribute("href", "/eventos/salon")
            enlace.click()
            expect(page.get_by_role("heading", name="Salon del Lago", exact=True)).to_be_visible()
            page.reload()
            expect(page.get_by_role("heading", name="Salon del Lago", exact=True)).to_be_visible()
            for ruta in ("/inexistente", "/e/cumple", "/p/salon"):
                page.goto(base + ruta)
                expect(page.get_by_role("heading", name="404", exact=False)).to_be_visible()
                assert page.url == base + ruta  # Sin redirigir a otra pagina.
            assert not errores, errores
            context.close()
        browser.close()
    assert "/publico/cumple" in solicitudes and "/publico/salon" in solicitudes
    print("OK: evento/proveedor, enlace entre paginas, recarga, 404, rutas antiguas sin redireccion; escritorio y movil.")


if __name__ == "__main__":
    main()
