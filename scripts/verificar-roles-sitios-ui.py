"""Roles visibles en Elegir apartado; APIs simuladas, sin iniciar sesiones reales."""
import json
import os
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 396):
            page = browser.new_page(viewport=dict(width=ancho, height=1000))
            page.add_init_script("localStorage.setItem('eventos_sesion','prueba')")
            opciones = [dict(tipo=tipo, id=n, nombre=nombre, slug=f"sitio-{n}", path=f"/sitio-{n}", roles=roles)
                        for n, (tipo, nombre, roles) in enumerate([
                            ("proveedor", "Mutual", ["Administrador"]),
                            ("evento", "Cumple Atoto", ["Agasajado", "Control de ingreso"]),
                            ("evento", "Fiesta", ["Invitado"]),
                        ], 1)]
            def api(route):
                respuesta = dict(email="cuenta@example.com", opciones=opciones) if route.request.url.endswith("/acceso/yo") else dict(client_id=None)
                route.fulfill(content_type="application/json", body=json.dumps(respuesta))
            page.route("**/api-vps/**", api)
            page.goto(os.getenv("EVENTOS_UI_URL", "http://127.0.0.1:5180") + "/ingresar")
            lista = page.get_by_role("region", name="Opciones de ingreso", exact=True)
            expect(lista.get_by_role("button", name="Mutual Proveedor Rol: Administrador", exact=True)).to_be_visible()
            expect(lista.get_by_role("button", name="Cumple Atoto Evento Rol: Agasajado · Control de ingreso", exact=True)).to_be_visible()
            expect(lista.get_by_role("button", name="Fiesta Evento Rol: Invitado", exact=True)).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(Path(tempfile.gettempdir()) / f"eventos-roles-sitios-{ancho}.png"), full_page=True)
            page.close()
        browser.close()
    print("OK: roles de proveedor, evento, invitado y multiples roles; escritorio y movil.")


if __name__ == "__main__":
    main()
