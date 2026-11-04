"""Arrastre y visibilidad con API simulada; no modifica datos del VPS."""
import json
import os

from playwright.sync_api import expect, sync_playwright


def main():
    evento = dict(id=1, nombre="Fiesta de prueba", slug="prueba", titulo_visual="Nuestra fiesta",
                  textos_portada=None, descripcion="Nos encontramos", fecha_inicio=None,
                  lugar_tipo="domicilio", direccion="Calle 123", localidad="Rio Gallegos",
                  provincia="Santa Cruz", pais="Argentina", latitud=None, longitud=None,
                  salon=None, portada_url=None, portada_encuadre=None, template_key="classic",
                  tipografia="sistema", colores=dict(fondo="#f4f7f6", texto="#18212f", acento="#245c48"),
                  estado="PUBLICADO", confirmado=True, modulos_habilitados=[], galeria=[],
                  limite_galeria=10, galeria_config=dict(modo="grilla", filas=2, columnas=2))
    admin, fallar = True, False
    guardados = []
    colores_guardados = []

    def api(route):
        url = route.request.url
        if url.endswith("/textos-portada"):
            if fallar:
                route.fulfill(status=503, content_type="application/json", body='{"detail":"Prueba"}')
                return
            evento["textos_portada"] = route.request.post_data_json
            guardados.append(evento["textos_portada"])
            data = evento
        elif url.endswith("/permisos"):
            data = dict(puede_editar=admin, permisos_invitados=[], rol="administrador" if admin else "visitante",
                        usuario=dict(id=1, email="prueba@example.com") if admin else None)
        elif url.endswith("/acceso/yo"):
            data = dict(email="prueba@example.com", usuario_id=1, opciones=[])
        elif "/eventos/prueba" in url:
            if route.request.method == "PUT":
                actualizacion = route.request.post_data_json
                evento["colores_textos"] = actualizacion["colores_textos"]
                colores_guardados.append(actualizacion["colores_textos"])
            data = evento
        else:
            data = {}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport=dict(width=1280, height=900))
        context.add_init_script("localStorage.setItem('eventos_sesion', 'prueba')")
        context.route("**/api-vps/**", api)
        context.route("http://localhost:8009/**", api)
        page = context.new_page()
        base = os.getenv("EVENTOS_UI_URL", "http://localhost:5179")
        page.goto(base + "/e/prueba", wait_until="domcontentloaded")
        page.get_by_role("button", name="Menu del evento", exact=True).click()
        page.get_by_role("button", name="Editar evento", exact=True).click()
        page.get_by_role("button", name="Editar datos del evento", exact=True).click()
        dialog = page.get_by_role("dialog", name="Datos del evento")
        dialog.get_by_role("button", name="Rojo para titulo", exact=True).click()
        dialog.get_by_role("button", name="Dorado para fecha y hora", exact=True).click()
        dialog.get_by_role("button", name="Celeste para lugar", exact=True).click()
        expect(dialog.get_by_role("button", name="Rojo para titulo", exact=True)).to_have_attribute("aria-pressed", "true")
        dialog.get_by_role("button", name="Guardar", exact=True).click()
        expect(dialog).to_have_count(0)
        assert colores_guardados[-1] == {"titulo":"#ef4444", "fecha":"#f6c453", "lugar":"#38bdf8"}
        expect(page.locator('.provider-cover-copy [data-texto="titulo"] h1')).to_have_css("color", "rgb(239, 68, 68)")
        expect(page.locator('.provider-cover-copy [data-texto="fecha"] p')).to_have_css("color", "rgb(246, 196, 83)")
        expect(page.locator('.provider-cover-copy [data-texto="lugar"] p')).to_have_css("color", "rgb(56, 189, 248)")
        original = page.locator('.provider-cover-copy [data-texto="titulo"]').bounding_box()
        portada_original = page.locator('.provider-cover').bounding_box()
        page.get_by_role("button", name="Mover u ocultar textos").click()
        titulo = page.locator('.texto-portada[data-texto="titulo"]')
        antes = titulo.bounding_box()
        assert abs(antes["x"] - original["x"]) < 3
        portada_editada = page.locator('.provider-cover').bounding_box()
        assert abs((antes["y"] - portada_editada["y"]) - (original["y"] - portada_original["y"])) < 3
        page.mouse.move(antes["x"] + antes["width"] / 2, antes["y"] + antes["height"] / 2)
        page.mouse.down()
        page.mouse.move(antes["x"] + antes["width"] / 2 + 100, antes["y"] + antes["height"] / 2 + 60, steps=8)
        page.mouse.up()
        despues = titulo.bounding_box()
        assert abs(despues["x"] - antes["x"] - 100) < 3
        assert abs(despues["y"] - antes["y"] - 60) < 3
        page.get_by_role("checkbox", name="Mostrar fecha").uncheck()
        page.get_by_role("button", name="Guardar textos", exact=True).click()
        expect(page.get_by_role("button", name="Mover u ocultar textos")).to_be_visible()
        assert guardados[-1]["fecha"]["visible"] is False
        page.reload(wait_until="domcontentloaded")
        expect(page.locator('.texto-portada[data-texto="fecha"]')).to_have_count(0)
        expect(titulo).to_be_visible()
        expect(titulo.locator("h1")).to_have_css("color", "rgb(239, 68, 68)")

        # Vista publica y limites en escritorio y movil, sin controles administrativos.
        admin = False
        for ancho in (1280, 390):
            page.set_viewport_size(dict(width=ancho, height=900))
            page.reload(wait_until="domcontentloaded")
            expect(titulo).to_be_visible()
            expect(titulo.locator("h1")).to_have_css("color", "rgb(239, 68, 68)")
            expect(page.get_by_role("button", name="Editar evento", exact=True)).to_have_count(0)
            expect(page.locator('.texto-portada[data-texto="fecha"]')).to_have_count(0)
            cover = page.locator(".provider-cover").bounding_box()
            rect = titulo.bounding_box()
            assert rect["x"] >= cover["x"] - 1
            assert rect["x"] + rect["width"] <= cover["x"] + cover["width"] + 1
            assert rect["y"] >= cover["y"] - 1
            assert rect["y"] + rect["height"] <= cover["y"] + cover["height"] + 1

        # Recuperar texto oculto, errores de guardado y cancelar sin perder lo publicado.
        admin = True
        page.reload(wait_until="domcontentloaded")
        page.get_by_role("button", name="Menu del evento", exact=True).click()
        page.get_by_role("button", name="Editar evento", exact=True).click()
        page.get_by_role("button", name="Mover u ocultar textos").click()
        page.get_by_role("checkbox", name="Mostrar fecha").check()
        expect(page.locator('.texto-portada[data-texto="fecha"]')).to_be_visible()
        fallar = True
        page.get_by_role("button", name="Guardar textos", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("No se pudieron guardar")
        page.get_by_role("button", name="Cancelar", exact=True).click()
        expect(page.locator('.texto-portada[data-texto="fecha"]')).to_have_count(0)
        page.get_by_role("button", name="Mover u ocultar textos").click()
        for nombre in ("fecha", "titulo", "lugar"):
            page.get_by_role("checkbox", name=f"Mostrar {nombre}").uncheck()
        fallar = False
        page.get_by_role("button", name="Guardar textos", exact=True).click()
        expect(page.get_by_role("button", name="Mover u ocultar textos")).to_be_visible()
        expect(page.locator(".texto-portada")).to_have_count(0)
        browser.close()
    print("OK: paleta y guardado, colores por bloque en escritorio/movil, arrastre, persistencia, permisos y cancelacion.")


if __name__ == "__main__":
    main()
