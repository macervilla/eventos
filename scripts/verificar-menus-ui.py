"""Menu unificado de cuenta y evento con API simulada, sin modificar cuentas reales."""
import json
import os
import re
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
        elif "/proveedores" in url or "/categorias" in url:
            data = []
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
            cuenta = page.get_by_role("button", name="Menú", exact=True)
            opciones = cuenta
            expect(cuenta).to_be_visible()
            expect(page.locator(".barra-sesion button[aria-expanded]")).to_have_count(1)
            expect(page.get_by_role("button", name="Menu del evento", exact=True)).to_have_count(0)
            expect(page.get_by_role("link", name="Buscar proveedores", exact=True)).to_have_count(0)
            expect(cuenta).to_have_attribute("aria-expanded", "false")
            expect(page.get_by_role("button", name="Editar evento", exact=True)).to_have_count(0)
            expect(page.get_by_role("link", name="Mis sitios", exact=True)).to_have_count(0)
            expect(page.get_by_text("administrador@example.com", exact=True)).to_have_count(0)
            cuenta.click()
            expect(page.get_by_role("link", name="Mis sitios", exact=True)).to_be_visible()
            expect(page.get_by_role("link", name="Dashboard", exact=True)).to_have_count(0)
            expect(page.locator(".barra-email")).to_have_count(0)
            expect(page.locator(".evento-usuario")).to_have_count(1)
            expect(page.locator(".evento-usuario")).to_contain_text("administrador@example.com")
            expect(page.locator(".menu-desplegable-panel > :last-child")).to_have_text("Cerrar sesion")
            expect(page.get_by_role("link", name="Buscar proveedores", exact=True)).to_be_visible()
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
            expect(cuenta).to_be_visible()
            cuenta.click()
            expect(page.get_by_role("link", name="Ingresar a mi cuenta", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="Ingresar al evento", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="Editar evento", exact=True)).to_have_count(0)
            expect(page.get_by_role("link", name="Mis sitios", exact=True)).to_have_count(0)
            page.get_by_role("link", name="Buscar proveedores", exact=True).click()
            expect(page).to_have_url(re.compile(r"/proveedores$"))
            expect(cuenta).to_have_attribute("aria-expanded", "false")
            cuenta.click()
            expect(page.get_by_role("button", name="Ingresar al evento", exact=True)).to_have_count(0)
            expect(page.get_by_role("link", name="Buscar proveedores", exact=True)).to_be_visible()
            context.close()
        browser.close()
    print("OK: menu unico, proveedores, permisos, cierre exterior/Escape/acciones, edicion, logout y navegacion; movil y escritorio.")


if __name__ == "__main__":
    main()
