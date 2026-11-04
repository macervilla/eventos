"""Menus de cuenta y evento con API simulada, sin modificar cuentas reales."""
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    evento = dict(id=1, nombre="Fiesta", slug="prueba", titulo_visual="Nuestra fiesta", textos_portada=None,
                  descripcion="Nos encontramos", fecha_inicio=None, lugar_tipo="domicilio", direccion="Calle 123",
                  localidad="Rio Gallegos", provincia="Santa Cruz", pais="Argentina", latitud=None, longitud=None,
                  salon=None, portada_url=None, portada_encuadre=None, template_key="classic", tipografia="sistema",
                  colores=dict(fondo="#f4f7f6", texto="#18212f", acento="#245c48"), estado="PUBLICADO",
                  confirmado=True, modulos_habilitados=[], galeria=[], limite_galeria=10,
                  galeria_config=dict(modo="grilla", filas=2, columnas=2))

    def api(route):
        url = route.request.url
        if url.endswith("/acceso/yo"):
            data = dict(email="administrador@example.com", usuario_id=1,
                        opciones=[dict(tipo="administracion", path="/administracion", cuenta_id=1)])
        elif url.endswith("/permisos"):
            data = dict(puede_editar=True, usuario=dict(id=1, email="administrador@example.com"),
                        rol="administrador", permisos_invitados=["ver_invitados", "control_ingreso"])
        else:
            data = evento
        route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 390):
            context = browser.new_context(viewport=dict(width=ancho, height=900))
            context.add_init_script("localStorage.setItem('eventos_sesion','prueba')")
            context.route("**/api-vps/**", api)
            context.route("http://localhost:8009/**", api)
            page = context.new_page()
            page.goto(os.getenv("EVENTOS_UI_URL", "http://localhost:5179") + "/e/prueba", wait_until="domcontentloaded")
            cuenta = page.get_by_role("button", name="Mi cuenta", exact=True)
            opciones = page.get_by_role("button", name="Menu del evento", exact=True)
            expect(opciones).to_be_visible()
            expect(cuenta).to_have_attribute("aria-expanded", "false")
            expect(page.get_by_role("button", name="Editar evento", exact=True)).to_have_count(0)
            expect(page.get_by_role("link", name="Mis sitios", exact=True)).to_have_count(0)
            expect(page.get_by_text("administrador@example.com", exact=True)).to_have_count(0)
            cuenta.click()
            expect(page.get_by_role("link", name="Mis sitios", exact=True)).to_be_visible()
            expect(page.get_by_role("link", name="Dashboard", exact=True)).to_be_visible()
            expect(page.get_by_text("administrador@example.com", exact=True)).to_be_visible()
            cuenta.click()
            opciones.click()
            cuenta.click()
            expect(opciones).to_have_attribute("aria-expanded", "false")
            cuenta.click()
            opciones.click()
            expect(cuenta).to_have_attribute("aria-expanded", "false")
            expect(page.get_by_role("button", name="Editar evento", exact=True)).to_be_visible()
            expect(page.get_by_role("link", name="Gestion de invitados", exact=True)).to_be_visible()
            expect(page.get_by_role("link", name="Control de ingreso", exact=True)).to_be_visible()
            page.keyboard.press("Escape")
            expect(opciones).to_have_attribute("aria-expanded", "false")
            expect(opciones).to_be_focused()
            opciones.click()
            page.locator(".provider-cover").click(position={"x":5,"y":500})
            expect(opciones).to_have_attribute("aria-expanded", "false")
            opciones.click()
            page.get_by_role("button", name="Editar evento", exact=True).click()
            expect(opciones).to_have_attribute("aria-expanded", "false")
            expect(page.get_by_text("Modo edicion.", exact=False)).to_be_visible()
            opciones.click()
            page.get_by_role("button", name="Ver invitacion", exact=True).click()
            expect(opciones).to_have_attribute("aria-expanded", "false")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(Path(os.environ.get("TEMP", "/tmp")) / f"eventos-menu-cerrado-{ancho}.png"))
            cuenta.click()
            page.get_by_role("button", name="Cerrar sesion", exact=True).click()
            expect(cuenta).to_have_count(0)
            expect(page.get_by_role("navigation", name="Sesion de Eventos").get_by_role("link", name="Ingresar", exact=True)).to_be_visible()
            context.close()
        browser.close()
    print("OK: menus ocultos por defecto, cuenta y permisos, cierre exterior/Escape/acciones, edicion y logout; movil y escritorio.")


if __name__ == "__main__":
    main()
