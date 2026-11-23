"""Fotos privadas, confirmacion y desbloqueo con APIs simuladas, sin envios reales."""
import json
import os
import re
import tempfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image
from playwright.sync_api import expect, sync_playwright


def main():
    imagen = BytesIO(); Image.new("RGB", (180, 140), "#487a63").save(imagen, "PNG")
    foto_bytes = imagen.getvalue()
    url = os.getenv("EVENTOS_UI_URL", "http://127.0.0.1:5180")
    token = "t" * 43
    evento = dict(id=1, nombre="Fiesta", slug="prueba", titulo_visual="Nuestra fiesta",
        textos_portada=None, descripcion="Nos encontramos", fecha_inicio=None,
        lugar_tipo="domicilio", direccion="Calle 123", localidad="Rio Gallegos",
        provincia="Santa Cruz", pais="Argentina", latitud=None, longitud=None,
        salon=None, portada_url=None, portada_encuadre=None, template_key="classic",
        tipografia="sistema", colores=dict(fondo="#f4f7f6", texto="#18212f", acento="#245c48"),
        estado="PUBLICADO", confirmado=True, modulos_habilitados=[], galeria=[], limite_galeria=10,
        galeria_config=dict(modo="grilla", filas=2, columnas=2))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 396):
            estado = dict(limite=4, bloqueadas=False, fotos=[])
            contador = [0]
            cambios = []

            def api(route):
                ruta = urlparse(route.request.url).path.removeprefix("/api-vps")
                metodo = route.request.method
                status = 200
                if ruta.endswith("/vivo/estado"):
                    respuesta = dict(estado="finalizada", disponible=False, invitacion_id=None, invitado=None, puede_publicar=False, emision=None)
                elif "/album" in ruta:
                    if route.request.headers.get("authorization") != "Bearer admin":
                        status = 403; respuesta = dict(detail="Sin acceso al album")
                    elif ruta.endswith("/imagen"):
                        route.fulfill(status=200, content_type="image/png", body=foto_bytes); return
                    else:
                        respuesta = dict(evento="Fiesta", fotos=[dict(id=f["id"], nombre=f["nombre"]) for f in estado["fotos"]] if estado["bloqueadas"] else [])
                elif "/fotos" in ruta:
                    if ruta.endswith("/imagen"):
                        route.fulfill(status=200, content_type="image/png", body=foto_bytes); return
                    if ruta.endswith("/estado"):
                        estado["bloqueadas"] = route.request.post_data_json["bloqueadas"]
                        cambios.append("bloquear" if estado["bloqueadas"] else "desbloquear")
                    elif ruta.endswith("/quitar-seleccionadas"):
                        ids = route.request.post_data_json["ids"]
                        estado["fotos"] = [f for f in estado["fotos"] if f["id"] not in ids]
                        estado["bloqueadas"] = False
                        cambios.append("quitar-admin")
                    elif ruta.endswith("/quitar"):
                        if estado["bloqueadas"]:
                            status = 409
                        else:
                            foto_id = int(ruta.split("/")[-2])
                            estado["fotos"] = [f for f in estado["fotos"] if f["id"] != foto_id]
                            cambios.append("quitar")
                    elif ruta.endswith("/portal/fotos") and metodo == "POST":
                        if estado["bloqueadas"] or len(estado["fotos"]) == 4:
                            status = 409
                        else:
                            contador[0] += 1
                            archivo = re.search(rb'filename="([^"]+)"', route.request.post_data_buffer).group(1).decode()
                            slot = next(n for n in range(1, 5) if n not in {f["slot"] for f in estado["fotos"]})
                            estado["fotos"].append(dict(id=contador[0], nombre=archivo, mime_type="image/png", slot=slot))
                            estado["fotos"].sort(key=lambda f: f["slot"])
                            cambios.append("subir")
                    respuesta = estado if status == 200 else dict(detail="El administrador confirmo tus fotos. Debe desbloquearlas para que puedas modificarlas")
                elif ruta.endswith("/acceso/yo"):
                    respuesta = dict(email="owner@example.com", usuario_id=1, opciones=[])
                elif ruta.endswith("/portal/qr.png"):
                    route.fulfill(status=200, content_type="image/png", body=foto_bytes); return
                elif ruta.endswith("/portal"):
                    respuesta = dict(validado=True, validacion="enlace", sesion="sesion-invitado", nombre="Ana", apellido="Perez",
                        cantidad_permitida=1, solicitados=1, acompanantes=[], qr="qr-estable", cupo_aprobado=1,
                        ingresados=0, rsvp="CONFIRMADO", aprobacion="APROBADO", puede_modificar=ancho == 1280)
                elif ruta.endswith("/acceso"):
                    respuesta = dict(permisos=["ver_invitados", "configurar_invitados"],
                        config=dict(activo=True, canales=["whatsapp"], listas_compartidas=True), roles_disponibles={})
                elif ruta.endswith("/lista"):
                    respuesta = dict(items=[dict(id=1, nombre="Ana", apellido="Perez", activo=True, cantidad_permitida=1,
                        nombres_menores=[], distribucion="PREPARADO", canal="whatsapp")], total=1)
                elif ruta.endswith("/portal/confirmar"):
                    raise AssertionError("Las fotos no deben volver a confirmar la asistencia")
                else:
                    respuesta = evento
                route.fulfill(status=status, content_type="application/json", body=json.dumps(respuesta))

            guest = browser.new_context(viewport=dict(width=ancho, height=920))
            admin = browser.new_context(viewport=dict(width=ancho, height=920), accept_downloads=True)
            admin.add_init_script("localStorage.setItem('eventos_sesion','admin')")
            for context in (guest, admin):
                context.route("**/api-vps/**", api)
            page = guest.new_page()
            page.goto(url + "/prueba/i/" + token)
            page.get_by_role("button", name="Mis fotos (hasta 4)", exact=True).click()
            ventana = page.get_by_role("dialog", name="Mis fotos para el evento", exact=True)
            campo = ventana.locator('input[type="file"]')
            expect(campo).to_be_enabled()
            campo.set_input_files([dict(name=f"foto-{n}.png", mimeType="image/png", buffer=foto_bytes) for n in range(1, 5)])
            expect(ventana.get_by_text("4 de 4 fotos", exact=True)).to_be_visible()
            expect(campo).to_be_disabled()
            expect(ventana.get_by_role("img", name=re.compile("Foto [1-4] del invitado"))).to_have_count(4)
            ventana.get_by_role("button", name="Ver foto 1", exact=True).click()
            ampliada = page.get_by_role("dialog", name="Foto: foto-1.png", exact=True)
            expect(ampliada.get_by_alt_text("Foto ampliada del invitado")).to_be_visible()
            page.keyboard.press("Escape")
            expect(ampliada).to_have_count(0)
            expect(ventana).to_be_visible()
            ventana.get_by_role("button", name="Quitar foto 1", exact=True).click()
            baja = page.get_by_role("dialog", name="Quitar foto", exact=True)
            baja.get_by_role("button", name="Cancelar", exact=True).click()
            assert len(estado["fotos"]) == 4
            ventana.get_by_role("button", name="Quitar foto 1", exact=True).click()
            baja.get_by_role("button", name="Quitar foto", exact=True).click()
            expect(ventana.get_by_text("3 de 4 fotos", exact=True)).to_be_visible()
            expect(campo).to_be_enabled()
            campo.set_input_files(dict(name="reemplazo.png", mimeType="image/png", buffer=foto_bytes))
            expect(ventana.get_by_text("4 de 4 fotos", exact=True)).to_be_visible()
            owner = admin.new_page(); owner.goto(url + "/prueba/invitados")
            owner.get_by_role("button", name="Fotos del invitado", exact=True).click()
            revision = owner.get_by_role("dialog", name="Fotos de Perez Ana", exact=True)
            expect(revision.get_by_text("4 de 4 fotos", exact=True)).to_be_visible()
            with owner.expect_download() as descarga:
                revision.get_by_role("link", name="Descargar foto 1", exact=True).click()
            assert descarga.value.suggested_filename.endswith(".png")
            revision.get_by_role("button", name="Confirmar fotos", exact=True).click()
            confirmar = owner.get_by_role("dialog", name="Confirmar fotos", exact=True)
            confirmar.get_by_role("button", name="Cancelar", exact=True).click()
            assert not estado["bloqueadas"]
            revision.get_by_role("button", name="Confirmar fotos", exact=True).click()
            confirmar.get_by_role("button", name="Confirmar fotos", exact=True).click()
            expect(revision.get_by_role("button", name="Desbloquear fotos", exact=True)).to_be_enabled()
            # El navegador del invitado aun tiene el estado anterior: el servidor rechaza la baja.
            ventana.get_by_role("button", name="Quitar foto 1", exact=True).click()
            baja.get_by_role("button", name="Quitar foto", exact=True).click()
            expect(ventana.get_by_role("alert")).to_contain_text("El administrador confirmo tus fotos")
            expect(campo).to_be_disabled()
            expect(ventana.get_by_role("button", name="Quitar foto 1", exact=True)).to_be_disabled()
            assert len(estado["fotos"]) == 4
            page.screenshot(path=str(Path(tempfile.gettempdir()) / f"fotos-invitado-bloqueadas-{ancho}.png"))
            revision.get_by_role("button", name="Desbloquear fotos", exact=True).click()
            expect(revision.get_by_role("button", name="Confirmar fotos", exact=True)).to_be_enabled()
            ventana.get_by_role("button", name="Actualizar fotos", exact=True).click()
            expect(ventana.get_by_role("button", name="Quitar foto 1", exact=True)).to_be_enabled()
            ventana.get_by_role("button", name="Quitar foto 1", exact=True).click()
            baja.get_by_role("button", name="Quitar foto", exact=True).click()
            expect(campo).to_be_enabled()
            campo.set_input_files(dict(name="foto-nueva.png", mimeType="image/png", buffer=foto_bytes))
            expect(ventana.get_by_text("4 de 4 fotos", exact=True)).to_be_visible()
            ventana.get_by_role("button", name="Cerrar fotos", exact=True).click()
            page.get_by_role("button", name="Modificar datos", exact=True).click()
            datos = page.get_by_role("dialog", name="Confirmar asistencia", exact=True)
            expect(datos.get_by_text("4 de 4 fotos", exact=True)).to_be_visible()
            if ancho == 396:
                expect(datos.get_by_role("button", name="Confirmar", exact=True)).to_be_disabled()
                expect(datos.get_by_role("button", name="Quitar foto 1", exact=True)).to_be_enabled()
            datos.get_by_role("button", name="Cancelar", exact=True).click()
            page.reload()
            page.get_by_role("button", name="Mis fotos (hasta 4)", exact=True).click()
            expect(ventana.get_by_text("4 de 4 fotos", exact=True)).to_be_visible()
            assert ventana.evaluate("e => e.scrollWidth <= e.clientWidth")
            assert "bloquear" in cambios and "desbloquear" in cambios
            # El administrador selecciona y quita varias fotos, incluso confirmadas.
            revision.get_by_role("button", name="Actualizar fotos", exact=True).click()
            expect(revision.get_by_role("button", name="Confirmar fotos", exact=True)).to_be_enabled()
            revision.get_by_role("button", name="Confirmar fotos", exact=True).click()
            confirmar.get_by_role("button", name="Confirmar fotos", exact=True).click()
            expect(revision.get_by_role("button", name="Desbloquear fotos", exact=True)).to_be_enabled()
            revision.get_by_role("checkbox", name="Seleccionar foto 1", exact=True).check()
            revision.get_by_role("checkbox", name="Seleccionar foto 3", exact=True).check()
            revision.get_by_role("button", name="Quitar seleccionadas (2)", exact=True).click()
            baja_admin = owner.get_by_role("dialog", name="Quitar fotos seleccionadas", exact=True)
            baja_admin.get_by_role("button", name="Cancelar", exact=True).click()
            assert len(estado["fotos"]) == 4 and estado["bloqueadas"]
            revision.get_by_role("button", name="Quitar seleccionadas (2)", exact=True).click()
            baja_admin.get_by_role("button", name="Confirmar y quitar", exact=True).click()
            expect(revision.get_by_text("2 de 4 fotos", exact=True)).to_be_visible()
            assert not estado["bloqueadas"]
            ventana.get_by_role("button", name="Actualizar fotos", exact=True).click()
            expect(campo).to_be_enabled()
            campo.set_input_files([dict(name=f"nueva-{n}.png", mimeType="image/png", buffer=foto_bytes) for n in (1, 2)])
            expect(ventana.get_by_text("4 de 4 fotos", exact=True)).to_be_visible()
            revision.get_by_role("button", name="Actualizar fotos", exact=True).click()
            expect(revision.get_by_role("button", name="Confirmar fotos", exact=True)).to_be_enabled()
            revision.get_by_role("button", name="Confirmar fotos", exact=True).click()
            confirmar.get_by_role("button", name="Confirmar fotos", exact=True).click()
            expect(revision.get_by_role("button", name="Desbloquear fotos", exact=True)).to_be_enabled()
            revision.get_by_role("button", name="Cerrar fotos", exact=True).click()
            # La cuenta elegida por pestana se conserva al abrir el album, sin tokens en la URL.
            owner.evaluate("""() => {
              localStorage.setItem('eventos_sesion','base-sin-permiso');
              sessionStorage.setItem('eventos_cuenta_pestana',JSON.stringify({base:'base-sin-permiso',token:'admin'}));
            }""")
            with owner.expect_popup() as popup:
                owner.get_by_role("button", name="Álbum", exact=True).click()
            album = popup.value
            expect(album).to_have_url(url + "/prueba/album")
            assert album.evaluate("window.opener === null")
            expect(album.get_by_role("heading", name="Album de Fiesta", exact=True)).to_be_visible()
            primera = album.get_by_alt_text(re.compile("Foto 1 de 4:"))
            expect(primera).to_be_visible()
            album.get_by_role("button", name="Pausar carrusel", exact=True).click()
            album.wait_for_timeout(2300)
            expect(primera).to_be_visible()
            album.get_by_role("button", name="Reanudar carrusel", exact=True).click()
            expect(album.get_by_alt_text(re.compile("Foto 2 de 4:"))).to_be_visible(timeout=4000)
            album.get_by_role("button", name="Pausar carrusel", exact=True).click()
            album.get_by_role("button", name="Anterior", exact=True).click()
            expect(primera).to_be_visible()
            album.get_by_role("button", name="Anterior", exact=True).click()
            expect(album.get_by_alt_text(re.compile("Foto 4 de 4:"))).to_be_visible()
            album.get_by_role("button", name="Siguiente", exact=True).click()
            expect(primera).to_be_visible()
            assert album.evaluate("document.documentElement.scrollWidth <= innerWidth")
            album.evaluate("window.scrollTo(0,0)")
            expect(album.get_by_role("heading", name="Album de Fiesta", exact=True)).to_be_in_viewport()
            album.screenshot(path=str(Path(tempfile.gettempdir()) / f"album-evento-{ancho}.png"))
            album.close()
            guest.close(); admin.close()
        browser.close()
    print("OK: fotos, bloqueo, baja multiple y reemplazos; album en otra pestana con sesion, carrusel cada 2 segundos, pausa y navegacion; movil y escritorio.")


if __name__ == "__main__":
    main()
