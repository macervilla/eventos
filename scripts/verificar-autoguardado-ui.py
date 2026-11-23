"""Verifica persistencia automatica, cambios durante un guardado y reintento sin API real."""
import asyncio
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.async_api import expect, async_playwright


async def main():
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] == "/prueba":
                self.path = "/index.html"
            super().do_GET()

        def log_message(self, *_args):
            pass

    dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(dist)))
    Thread(target=server.serve_forever, daemon=True).start()
    evento = dict(id=1, nombre="Prueba", slug="prueba", titulo_visual="Nuestra fiesta",
        textos_portada=None, descripcion="Descripcion original", fecha_inicio=None,
        lugar_tipo="domicilio", direccion="Calle 123", localidad="Rio Gallegos",
        provincia="Santa Cruz", pais="Argentina", latitud=None, longitud=None,
        salon=None, portada_url="/foto.png", portada_encuadre=None, template_key="classic",
        tipografia="sistema", colores=dict(fondo="#f4f7f6", texto="#18212f", acento="#245c48"),
        estado="PUBLICADO", confirmado=True, modulos_habilitados=["detalles"], galeria=[], limite_galeria=10,
        galeria_config=dict(modo="grilla", filas=2, columnas=2))
    fallar = False
    administrador = True
    en_curso = 0
    maximo = 0
    escrituras = []

    async def api(route):
        nonlocal en_curso, maximo
        path = route.request.url.split("?")[0]
        if route.request.method == "PUT":
            en_curso += 1
            maximo = max(maximo, en_curso)
            await asyncio.sleep(0.3)
            datos = route.request.post_data_json
            if fallar:
                en_curso -= 1
                await route.fulfill(status=503, json=dict(detail="Fallo de prueba"))
                return
            if path.endswith("/textos-portada"):
                evento["textos_portada"] = datos
            elif path.endswith("/portada-encuadre"):
                evento["portada_encuadre"] = datos
            else:
                evento.update(datos)
            escrituras.append((path, datos))
            en_curso -= 1
            respuesta = evento
        elif "/publico/" in path:
            respuesta = dict(tipo="evento")
        elif path.endswith("/acceso/yo"):
            respuesta = dict(email="admin@example.com", usuario_id=1, opciones=[])
        elif path.endswith("/permisos"):
            respuesta = dict(puede_editar=administrador, permisos_invitados=[], rol="administrador" if administrador else "visitante",
                usuario=dict(id=1, email="admin@example.com"))
        elif path.endswith("/mis-invitaciones"):
            respuesta = dict(invitaciones=[])
        elif path.endswith("/solicitudes/opciones"):
            respuesta = dict(agasajados=[], email_verificado="admin@example.com")
        else:
            respuesta = evento
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(respuesta))

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(viewport=dict(width=1280, height=900))
            await context.add_init_script("localStorage.setItem('eventos_sesion','prueba')")
            await context.route("**/api-vps/**", api)
            page = await context.new_page()
            errores = []
            page.on("pageerror", lambda error: errores.append(str(error)))
            base = f"http://127.0.0.1:{server.server_port}/prueba"
            url = base + "?editar=1"
            # El acceso directo funciona para administradores incluso fuera del modo edicion.
            await page.goto(base)
            await page.wait_for_load_state("networkidle")
            await page.locator('[data-texto="titulo"]').dblclick()
            dialog = page.get_by_role("dialog", name="Datos del evento", exact=True)
            await expect(dialog.locator('[data-editor-campo="titulo_visual"]')).to_be_focused()
            await dialog.get_by_role("button", name="Cerrar", exact=True).last.click()
            await page.locator(".provider-info").dblclick(position=dict(x=5, y=5))
            await expect(dialog.locator('[data-editor-campo="fondo"]')).to_be_focused()
            await dialog.locator('[data-editor-campo="fondo"]').evaluate("el => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, '#123456'); el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }")
            await expect(dialog.get_by_role("status")).to_have_text("Cambios guardados")
            assert evento["colores"]["fondo"] == "#123456"
            await dialog.get_by_role("button", name="Cerrar", exact=True).last.click()
            await page.get_by_role("heading", name="Detalles del evento", exact=True).dblclick()
            await expect(dialog.locator('[data-editor-campo="titulo_detalles"]')).to_be_focused()
            await dialog.locator('[data-editor-campo="titulo_detalles"]').fill("Sobre nuestra fiesta")
            await expect(dialog.get_by_role("status")).to_have_text("Cambios guardados")
            await dialog.get_by_role("button", name="Cerrar", exact=True).last.click()
            await expect(page.get_by_role("heading", name="Sobre nuestra fiesta", exact=True)).to_be_visible()
            await page.locator('.provider-info > p').dblclick()
            await expect(dialog.locator('[data-editor-campo="descripcion"]')).to_be_focused()
            await dialog.get_by_role("button", name="Cerrar", exact=True).last.click()
            await page.goto(url)
            abrir = page.get_by_role("button", name="Mover u ocultar textos", exact=True)
            await abrir.click()
            titulo = page.locator('.texto-portada[data-texto="titulo"]')
            antes = await titulo.bounding_box()
            await page.mouse.move(antes["x"] + 30, antes["y"] + 20)
            await page.mouse.down()
            await page.mouse.move(antes["x"] + 130, antes["y"] + 65, steps=8)
            await page.mouse.up()
            # Mientras se escribe el movimiento, el usuario cambia visibilidad.
            await page.get_by_role("checkbox", name="Mostrar fecha").uncheck()
            await expect(page.get_by_role("status").last).to_have_text("Cambios guardados")
            assert evento["textos_portada"]["fecha"]["visible"] is False
            posicion = evento["textos_portada"]["titulo"].copy()
            await page.reload()
            await expect(titulo).to_be_visible()
            await expect(page.locator('[data-texto="fecha"]')).to_have_count(0)
            await expect(page.get_by_role("heading", name="Sobre nuestra fiesta", exact=True)).to_be_visible()
            assert abs(float((await titulo.get_attribute("style")).split("left: ")[1].split("%")[0]) - posicion["x"]) < 0.01
            await titulo.dblclick()
            await expect(dialog.locator('[data-editor-campo="titulo_visual"]')).to_be_focused()
            await dialog.get_by_role("button", name="Cerrar", exact=True).last.click()

            await abrir.click()
            await titulo.focus()
            for _ in range(4):
                await page.keyboard.press("ArrowLeft")
            await expect(page.get_by_role("status").last).to_have_text("Cambios guardados")
            assert evento["textos_portada"]["titulo"]["x"] == max(0, posicion["x"] - 4)
            fallar = True
            await page.get_by_role("checkbox", name="Mostrar fecha").check()
            await expect(page.get_by_role("alert")).to_contain_text("No se pudieron guardar")
            await expect(page.get_by_role("checkbox", name="Mostrar fecha")).to_be_checked()
            fallar = False
            await page.get_by_role("button", name="Guardar", exact=True).click()
            await expect(page.get_by_role("status").last).to_have_text("Cambios guardados")
            assert evento["textos_portada"]["fecha"]["visible"] is True
            await page.get_by_role("button", name="Cancelar", exact=True).click()

            await page.get_by_role("button", name="Editar datos del evento", exact=True).click()
            dialog = page.get_by_role("dialog", name="Datos del evento", exact=True)
            await dialog.get_by_label("Titulo visual de la invitacion").fill("Titulo automatico")
            await dialog.locator("textarea").fill("Descripcion automatica")
            await dialog.get_by_role("button", name="Rojo para titulo", exact=True).click()
            await expect(dialog.get_by_role("status")).to_have_text("Cambios guardados")
            await expect(dialog).to_be_visible()
            assert evento["titulo_visual"] == "Titulo automatico"
            assert evento["colores_textos"]["titulo"] == "#ef4444"
            await dialog.locator("textarea").fill("Cambio al cerrar")
            await dialog.get_by_role("button", name="Cerrar", exact=True).last.click()
            await expect(dialog).to_have_count(0)
            await page.reload()
            await expect(page.get_by_role("heading", name="Titulo automatico")).to_be_visible()
            await expect(page.get_by_text("Cambio al cerrar", exact=True)).to_be_visible()

            await page.get_by_role("button", name="Ajustar encuadre de la imagen", exact=True).click()
            await page.get_by_role("button", name="Completa", exact=True).click()
            await expect(page.get_by_role("status").last).to_have_text("Cambios guardados")
            assert evento["portada_encuadre"]["modo"] == "completa"
            await page.get_by_role("button", name="Cerrar ajuste", exact=True).click()
            administrador = False
            await page.goto(base)
            await page.wait_for_load_state("networkidle")
            total_escrituras = len(escrituras)
            archivos = []
            page.on("filechooser", lambda selector: archivos.append(selector))
            for selector in ('[data-texto="titulo"]', '.provider-info > h2', '.provider-info > p'):
                await page.locator(selector).dblclick()
                await expect(page.get_by_role("dialog")).to_have_count(0)
            await page.locator(".provider-info").dblclick(position=dict(x=5, y=5))
            await expect(page.get_by_role("dialog")).to_have_count(0)
            await page.wait_for_load_state("networkidle")
            assert len(escrituras) == total_escrituras
            assert not archivos
            assert maximo == 1, f"Escrituras simultaneas: {maximo}"
            assert not errores, errores
            print(f"OK: doble clic por elemento solo para admin, titulos de seccion, autoguardado, reintento, recarga y encuadre; {len(escrituras)} escrituras serializadas.")
            await browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    asyncio.run(main())
