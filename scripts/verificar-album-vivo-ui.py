"""Verifica los cambios de estado del vivo con API simulada, sin modificar eventos."""
import base64
import json
import os
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


def main():
    url = os.getenv("EVENTOS_UI_URL", "http://127.0.0.1:5180")
    foto = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII=")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 396):
            estado = dict(estado="finalizada", disponible=True, invitacion_id=None,
                          invitado=None, puede_publicar=False, emision=None, camaras=[])
            autorizaciones = []

            def api(route):
                ruta = urlparse(route.request.url).path
                if ruta.endswith("/imagen"):
                    route.fulfill(content_type="image/png", body=foto)
                    return
                if ruta.endswith("/vivo/estado"):
                    respuesta = estado
                elif ruta.endswith("/vivo/autorizacion"):
                    autorizaciones.append(route.request.post_data_json)
                    estado.update(estado="finalizada", invitacion_id=None, emision=None, camaras=[])
                    respuesta = estado
                elif ruta.endswith("/vivo/ver"):
                    # El objetivo es verificar el reemplazo visual, sin servidor WebRTC.
                    route.fulfill(status=503, content_type="application/json", body='{"detail":"Video simulado"}')
                    return
                elif ruta.endswith("/album"):
                    respuesta = dict(evento="Fiesta", fotos=[dict(id=1, nombre="foto.png"), dict(id=2, nombre="otra.png")])
                elif ruta.endswith("/acceso/yo"):
                    respuesta = dict(email="owner@example.com", usuario_id=1, opciones=[])
                elif ruta.endswith("/acceso"):
                    respuesta = dict(permisos=["ver_invitados", "configurar_invitados"],
                                     config=dict(activo=True, canales=["whatsapp"], listas_compartidas=True), roles_disponibles={})
                elif ruta.endswith("/lista"):
                    respuesta = dict(items=[dict(id=1, nombre="Ana", apellido="Perez", activo=True,
                                                cantidad_permitida=1, nombres_menores=[], distribucion="PREPARADO", canal="whatsapp")], total=1)
                else:
                    respuesta = dict(id=1, nombre="Fiesta", slug="prueba")
                route.fulfill(content_type="application/json", body=json.dumps(respuesta))

            context = browser.new_context(viewport=dict(width=ancho, height=920))
            context.add_init_script("localStorage.setItem('eventos_sesion','admin')")
            context.route("**/api-vps/**", api)
            album = context.new_page()
            album.goto(url + "/prueba/album")
            expect(album.get_by_role("heading", name="Album de Fiesta", exact=True)).to_be_visible()
            expect(album.get_by_text("Cambio automatico", exact=False)).to_have_count(0)
            expect(album.get_by_role("region", name="En vivo", exact=True)).to_have_count(0)
            expect(album.locator(".album-evento-imagen")).to_be_visible()
            admin = context.new_page()
            admin.goto(url + "/prueba/invitados")
            habilitar = admin.get_by_role("button", name="Habilitar transmision", exact=True)
            expect(habilitar).to_be_visible()
            estado.update(estado="activa", invitacion_id=1, invitado="Perez Ana", emision="emision-prueba")
            estado["camaras"] = [dict(estado="activa", invitacion_id=1, invitado="Perez Ana", emision="emision-prueba", seleccionada=True)]
            for page in (album, admin):
                page.evaluate("window.dispatchEvent(new Event('eventos:video'))")
            vivo = album.get_by_role("region", name="En vivo", exact=True)
            expect(vivo).to_be_visible()
            expect(vivo.locator("video")).to_be_visible()
            expect(album.locator(".album-evento-imagen")).to_have_count(0)
            expect(album.get_by_role("button", name="Pausar carrusel", exact=True)).to_have_count(0)
            assert album.locator(".album-evento-escenario").count() == 1
            assert album.evaluate("document.documentElement.scrollWidth <= innerWidth")
            pausa = admin.get_by_role("button", name="Pausar transmision", exact=True)
            expect(pausa).to_have_css("background-color", "rgb(180, 35, 24)")
            pausa.click()
            dialogo = admin.get_by_role("dialog", name="Pausar transmision", exact=True)
            dialogo.get_by_role("button", name="Cancelar", exact=True).click()
            assert autorizaciones == []
            pausa.click()
            dialogo.get_by_role("button", name="Pausar", exact=True).click()
            expect(habilitar).to_be_visible()
            assert autorizaciones == [dict(invitacion_id=1, habilitada=False)]
            album.evaluate("window.dispatchEvent(new Event('eventos:video'))")
            expect(vivo).to_have_count(0)
            expect(album.locator(".album-evento-imagen")).to_be_visible()
            expect(album.get_by_role("button", name="Pausar carrusel", exact=True)).to_be_visible()
            context.close()
        browser.close()
    print("OK: Album y reemplazo por vivo; boton rojo, cancelar y pausar; regreso a fotos en escritorio y movil.")


if __name__ == "__main__":
    main()
