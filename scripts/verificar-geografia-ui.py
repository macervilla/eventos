"""Prueba de navegador con API y mapas simulados; nunca envia datos al VPS."""
import base64
import json
import os
from pathlib import Path

from playwright.sync_api import Error, expect, sync_playwright


def main():
    queries, payloads, pendientes = [], [], []
    city = dict(geoname_id=3838859, localidad="Río Gallegos", provincia="Santa Cruz", pais="Argentina",
                codigo_pais="AR", latitud=-51.6253, longitud=-69.25229)
    pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")

    def api(route):
        request = route.request
        if "/geografia/localidades" in request.url:
            queries.append(request.url)
            if "vieja" in request.url:
                pendientes.append(route)
                return
            data = {"resultados": [city] if "sinresultados" not in request.url else []}
        elif request.method == "POST":
            payloads.append(request.post_data_json)
            data = {"slug": "evento-prueba", "email_confirmacion": "geo@example.com"}
        else:
            data = []
        route.fulfill(status=201 if request.method == "POST" else 200, content_type="application/json", body=json.dumps(data))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        # Se cubren ambos modos de desarrollo, sin solicitudes externas a la API.
        page.route("**/api-vps/**", api)
        page.route("http://localhost:8009/**", api)
        page.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(status=200, content_type="image/png", body=pixel))
        base = os.getenv("EVENTOS_UI_URL", "http://localhost:5179")
        page.goto(base + "/eventos/nuevo")
        page.get_by_role("radio", name="Mi casa").click()
        combo = page.get_by_role("combobox", name="Localidad", exact=True)
        combo.fill("ri")
        page.wait_for_timeout(400)
        assert not queries
        combo.fill("vieja")
        page.wait_for_timeout(400)
        assert pendientes
        combo.fill("rio ga")
        expect(page.get_by_role("option", name="Río Gallegos Santa Cruz, Argentina")).to_be_visible()
        for route in pendientes:
            try:
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"resultados": [{**city, "localidad": "Respuesta antigua"}]}))
            except Error:
                pass  # La peticion anterior puede estar cancelada por AbortController.
        page.wait_for_timeout(100)
        expect(page.get_by_role("option", name="Río Gallegos Santa Cruz, Argentina")).to_be_visible()
        page.screenshot(path=str(Path(os.environ.get("TEMP", "/tmp")) / "eventos-geo-autocomplete.png"), full_page=True)
        combo.press("ArrowDown")
        combo.press("Enter")
        expect(combo).to_have_value("Río Gallegos")
        expect(page.get_by_label("Provincia / estado", exact=True)).to_have_value("Santa Cruz")
        expect(page.get_by_label("Pais", exact=True)).to_have_value("Argentina")
        page.get_by_label("Nombre del evento", exact=True).fill("Evento prueba")
        page.get_by_label("Direccion", exact=True).fill("Calle 2 y 29")
        page.get_by_label("Tu email", exact=False).fill("geo@example.com")
        page.get_by_role("button", name="Crear evento", exact=True).click()
        page.wait_for_timeout(200)
        assert payloads[-1]["geoname_id"] == 3838859 and payloads[-1]["codigo_pais"] == "AR"
        assert payloads[-1]["latitud"] == -51.6253
        page.goto(base + "/eventos/nuevo")
        page.get_by_role("radio", name="Mi casa").click()
        combo = page.get_by_role("combobox", name="Localidad", exact=True)
        combo.fill("rio ga")
        page.get_by_role("option", name="Río Gallegos Santa Cruz, Argentina").click()
        combo.fill("sinresultados")
        expect(page.locator(".geo-ayuda")).to_contain_text("No hay coincidencias")
        page.get_by_role("button", name="Ingresar localidad manualmente").click()
        page.get_by_label("Provincia / estado", exact=True).fill("Provincia manual")
        page.get_by_label("Pais", exact=True).fill("Pais manual")
        page.get_by_label("Nombre del evento", exact=True).fill("Manual")
        page.get_by_label("Direccion", exact=True).fill("Calle manual")
        page.get_by_label("Tu email", exact=False).fill("geo@example.com")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(Path(os.environ.get("TEMP", "/tmp")) / "eventos-geo-movil.png"), full_page=True)
        page.get_by_role("button", name="Crear evento", exact=True).click()
        page.wait_for_timeout(200)
        assert payloads[-1]["geoname_id"] is None and payloads[-1]["codigo_pais"] is None
        browser.close()
    print("UI OK: minimo 3, debounce, respuestas antiguas, teclado/Enter, provincia/pais, persistencia, invalidacion, carga manual y movil.")


if __name__ == "__main__":
    main()
