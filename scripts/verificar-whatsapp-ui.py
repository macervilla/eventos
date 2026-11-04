"""Enviar y reenviar con API y selector simulados; no envia mensajes reales."""
import json
from urllib.parse import urlsplit, parse_qs

from playwright.sync_api import sync_playwright, expect


def main():
    config = dict(activo=True, canales=["enlace", "whatsapp"], listas_compartidas=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for nativo in (False, True):
            operaciones = []
            invitado = dict(id=1, nombre="Ana", apellido="", telefono="02966 15-123456", whatsapp=None,
                            email=None, instagram=None, facebook=None, telegram=None, otro_contacto=None,
                            responsable_id=1, cantidad_permitida=1, adultos=1, menores=0, solicitados=0,
                            cupo_aprobado=0, ingresados=0, restantes=0, rsvp="PENDIENTE", aprobacion="PENDIENTE",
                            distribucion="SIN_ENVIAR", canal=None, activo=True)

            def api(route):
                url = route.request.url
                if url.endswith("/acceso/yo"):
                    data = dict(email="prueba@example.com", usuario_id=1, opciones=[])
                elif url.endswith("/acceso"):
                    data = dict(permisos=["ver_invitados", "distribuir"], usuario_id=1,
                                config=config, solo_responsable=False, roles_disponibles={})
                elif "/lista" in url:
                    data = dict(items=[invitado], total=1)
                elif url.endswith("/distribuir"):
                    operaciones.append(route.request.post_data_json)
                    invitado["distribucion"], invitado["canal"] = "PREPARADO", "whatsapp"
                    data = dict(resultados=[dict(id=1, destinatario="Ana", canal="whatsapp", estado="PREPARADO",
                                telefono_destino="+5492966123456", mensaje="Invitacion personal", enlace="https://example.com/personal",
                                portada_url="/media/prueba.jpg", titulo="Fiesta",
                                detalle="Pendiente de envio manual. Pulsa Enviar en WhatsApp.",
                                url_canal="https://wa.me/5492966123456?text=Invitacion%20personal")])
                elif url.endswith("/portada.jpg"):
                    route.fulfill(content_type="image/jpeg", body=b"foto-simulada")
                    return
                else:
                    data = {}
                route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

            context = browser.new_context(viewport=dict(width=390 if nativo else 1280, height=900))
            context.add_init_script("""
                localStorage.setItem('eventos_sesion','prueba');
                window._shares=[];
                Object.defineProperty(navigator,'canShare',{value:()=>NATIVO});
                Object.defineProperty(navigator,'share',{value:async datos=>{
                    window._shares.push({text:datos.text, files:datos.files.map(f=>({name:f.name,size:f.size,type:f.type}))});
                }});
                Object.defineProperty(navigator,'clipboard',{value:{writeText:async texto=>window._copiado=texto}});
            """.replace("NATIVO", "true" if nativo else "false"))
            context.route("**/api-vps/**", api)
            context.route("http://localhost:8009/**", api)
            context.route("**/media/prueba.jpg", lambda r: r.fulfill(content_type="image/svg+xml", body='<svg xmlns="http://www.w3.org/2000/svg" width="360" height="240"><rect width="360" height="240" fill="#245c48"/><text x="40" y="120" fill="white">Foto invitacion</text></svg>'))
            page = context.new_page()
            page.goto("http://localhost:5179/e/prueba/invitados", wait_until="domcontentloaded")
            expect(page.get_by_role("combobox", name="Canal para distribuir")).to_have_value("whatsapp")
            page.get_by_role("button", name="Enviar invitacion", exact=True).click()
            dialog = page.get_by_role("dialog", name="Enviar invitacion a Ana")
            expect(dialog).to_be_visible()
            expect(dialog.get_by_role("img", name="Portada de la invitacion para compartir")).to_be_visible()
            expect(dialog.get_by_role("link", name="aquí", exact=True)).to_have_attribute("href", "https://example.com/personal")
            expect(dialog.get_by_role("link", name="Abrir confirmacion desde la foto")).to_have_attribute("href", "https://example.com/personal")
            expect(dialog.get_by_text("+5492966123456", exact=True)).to_be_visible()
            if not nativo:
                enlace = dialog.get_by_role("link", name="3. Abrir WhatsApp para Ana", exact=True)
                expect(enlace).to_be_visible()
                url = urlsplit(enlace.get_attribute("href"))
                assert url.netloc == "wa.me" and url.path == "/5492966123456"
                assert "https://example.com/personal" in parse_qs(url.query)["text"][0]
            texto = dialog.get_by_role("textbox", name="Texto para Ana")
            texto.fill("Te esperamos en la fiesta!")
            copiar = dialog.get_by_role("button", name="Copiar texto y enlace" if nativo else "2. Copiar texto y enlace", exact=True)
            expect(copiar).to_be_enabled()
            copiar.click()
            page.wait_for_function("window._copiado && window._copiado.includes('https://example.com/personal')")
            assert "Te esperamos" in page.evaluate("window._copiado")
            if nativo:
                dialog.get_by_role("button", name="Enviar foto y texto", exact=True).click()
                page.wait_for_function("window._shares.length===1")
                datos = page.evaluate("window._shares[0]")
                assert datos["files"][0]["name"] == "invitacion.jpg" and datos["files"][0]["size"] > 0
                assert "Te esperamos" in datos["text"] and "https://example.com/personal" in datos["text"]
            else:
                expect(dialog.get_by_role("button", name="Enviar foto y texto", exact=True)).to_have_count(0)
                expect(dialog.get_by_role("heading", name="Enviar foto y texto desde este navegador")).to_be_visible()
                with page.expect_download() as descarga:
                    dialog.get_by_role("button", name="1. Descargar foto").click()
                assert descarga.value.suggested_filename == "invitacion.jpg"
            dialog.get_by_role("button", name="Cerrar", exact=True).click()
            expect(page.get_by_role("button", name="Reenviar invitacion", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="Renovar enlace", exact=True)).to_have_count(0)
            page.get_by_role("button", name="Reenviar invitacion", exact=True).click()
            expect(page.get_by_role("dialog", name="Reenviar invitacion a Ana")).to_be_visible()
            nuevo = page.get_by_role("dialog", name="Reenviar invitacion a Ana")
            if nativo:
                expect(nuevo.get_by_role("button", name="Reenviar foto y texto", exact=True)).to_be_enabled()
            else:
                expect(nuevo.get_by_role("link", name="3. Abrir WhatsApp para Ana")).to_be_visible()
            assert len(operaciones) == 2
            assert all(o["ids"] == [1] and o["canal"] == "whatsapp" for o in operaciones)
            assert operaciones[0]["idempotencia"] != operaciones[1]["idempotencia"]
            assert len(context.pages) == 1
            context.close()
        browser.close()
    print("OK: Enviar/Reenviar, foto y texto, enlace conservado, mensaje editable, selector nativo y alternativa de escritorio. Sin envios reales.")


if __name__ == "__main__":
    main()
