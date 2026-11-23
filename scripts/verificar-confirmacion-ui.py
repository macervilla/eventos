"""Confirmacion nominal y QR persistente con API simulada, sin envios reales."""
import json
import os
import tempfile
from io import BytesIO
from pathlib import Path

import qrcode
from playwright.sync_api import expect, sync_playwright


def main():
    imagen = BytesIO()
    qrcode.make("qr-personal-de-prueba").save(imagen, format="PNG")
    evento = dict(id=1, nombre="Fiesta", slug="prueba", titulo_visual="Nuestra fiesta",
        textos_portada=None, descripcion="Nos encontramos", fecha_inicio=None,
        lugar_tipo="domicilio", direccion="Calle 123", localidad="Rio Gallegos",
        provincia="Santa Cruz", pais="Argentina", latitud=None, longitud=None,
        salon=None, portada_url=None, portada_encuadre=None, template_key="classic",
        tipografia="sistema", colores=dict(fondo="#f4f7f6", texto="#18212f", acento="#245c48"),
        estado="PUBLICADO", confirmado=True, modulos_habilitados=[], galeria=[], limite_galeria=10,
        galeria_config=dict(modo="grilla", filas=2, columnas=2))
    url = os.getenv("EVENTOS_UI_URL", "http://127.0.0.1:5180")
    token = "t" * 43
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for entrada in ("cuenta", "email", "whatsapp"):
            for ancho in (1280, 396):
                metodo = "google"
                solicitudes = []
                codigos_solicitados = []
                privado = dict(validado=True, validacion=metodo, sesion="verificada", nombre="Juan", apellido="Perez",
                    cantidad_permitida=2, adultos=0, acompanantes=[], solicitados=0, cupo_aprobado=0,
                    ingresados=0, rsvp="PENDIENTE", aprobacion="PENDIENTE", puede_modificar=True, puede_confirmar=True, email_asociado=None if entrada == "whatsapp" else "j***@e***.com", qr=None)

                def api(route):
                    if "/publico/" in route.request.url:
                        return route.fulfill(status=200, content_type="application/json", body=json.dumps({"tipo": "evento"}))
                    ruta = route.request.url.split("?")[0]
                    data = route.request.post_data_json if route.request.method == "POST" else {}
                    status = 200
                    if ruta.endswith("/acceso/yo"):
                        respuesta = dict(email="juan@example.com", usuario_id=4, opciones=[])
                    elif ruta.endswith("/permisos"):
                        respuesta = dict(usuario=dict(id=4, email="juan@example.com"), rol="visitante", puede_editar=False, permisos_invitados=[])
                    elif ruta.endswith("/mis-invitaciones"):
                        respuesta = dict(invitaciones=[dict(id=1, token=token, nombre="Juan", apellido="Perez")])
                    elif ruta.endswith("/portal/codigo"):
                        codigos_solicitados.append(data)
                        respuesta = dict(message="Codigo enviado al contacto registrado")
                    elif ruta.endswith("/portal/confirmar"):
                        solicitudes.append(data)
                        assert data["sesion"] == "verificada"
                        assert all(p["nombre"].strip() and p["apellido"].strip() for p in data["personas"])
                        privado.update(nombre=data["personas"][0]["nombre"], apellido=data["personas"][0]["apellido"],
                            acompanantes=data["personas"][1:], rsvp="CONFIRMADO", aprobacion="APROBADO",
                            cupo_aprobado=len(data["personas"]), solicitados=len(data["personas"]), qr="qr-personal-estable")
                        respuesta = privado
                    elif ruta.endswith("/portal/qr.png"):
                        route.fulfill(status=200, content_type="image/png", body=imagen.getvalue()); return
                    elif ruta.endswith("/portal/fotos/listar"):
                        respuesta = dict(fotos=[], bloqueadas=False, limite=4)
                    elif ruta.endswith("/portal"):
                        assert route.request.headers.get("authorization") == "Bearer prueba"
                        respuesta = privado
                    else:
                        respuesta = evento
                    route.fulfill(status=status, content_type="application/json", body=json.dumps(respuesta))

                context = browser.new_context(viewport=dict(width=ancho, height=900))
                context.add_init_script("localStorage.setItem('eventos_sesion','prueba')")
                context.route("**/api-vps/**", api)
                context.route("**/eventos/api/**", api)
                page = context.new_page()
                page.on("dialog", lambda d: (_ for _ in ()).throw(AssertionError("Dialogo nativo inesperado")))
                page.goto(url + "/prueba" + ("" if entrada == "cuenta" else "/i/" + token))
                if entrada == "whatsapp":
                    expect(page.get_by_role("button", name="Verificar mi correo", exact=True)).to_have_count(0)
                    expect(page.get_by_role("button", name="Ingresar con Google", exact=True)).to_have_count(0)
                expect(page.get_by_role("button", name="Verificar mi correo", exact=True)).to_have_count(0)
                page.get_by_role("button", name="Confirmar asistencia", exact=True).click()
                ventana = page.get_by_role("dialog", name="Confirmar asistencia", exact=True)
                expect(ventana).to_be_visible()
                titular = ventana.get_by_role("group", name="Titular", exact=True)
                expect(titular.get_by_label("Nombre", exact=True)).to_have_value("Juan")
                expect(titular.get_by_label("Apellido", exact=True)).to_have_value("Perez")
                # Cancelar no confirma ni entrega QR.
                ventana.get_by_role("button", name="Cancelar", exact=True).click()
                assert not solicitudes
                page.get_by_role("button", name="Confirmar asistencia", exact=True).click()
                boton = ventana.get_by_role("button", name="Confirmar", exact=True)
                boton.click()
                assert not solicitudes  # El acompanante necesita ambos campos.
                titular.get_by_label("Nombre", exact=True).fill("Juan Carlos")
                titular.get_by_label("Apellido", exact=True).fill("Perez corregido")
                acompanante = ventana.get_by_role("group", name="Acompanante 1", exact=True)
                acompanante.get_by_label("Apellido", exact=True).fill("Gomez")
                acompanante.get_by_label("Nombre", exact=True).fill("Ana")
                acompanante.get_by_label("Tipo de asistente").select_option("MENOR")
                if entrada == "cuenta":
                    page.screenshot(path=str(Path(tempfile.gettempdir()) / f"confirmacion-datos-{ancho}.png"))
                boton.click()
                expect(ventana).to_have_count(0)
                expect(page.get_by_alt_text("QR de ingreso de mi invitacion")).to_be_visible()
                assert solicitudes[0]["personas"] == [dict(nombre="Juan Carlos", apellido="Perez corregido", tipo="ADULTO"),
                                                       dict(nombre="Ana", apellido="Gomez", tipo="MENOR")]
                page.reload()
                expect(page.get_by_alt_text("QR de ingreso de mi invitacion")).to_be_visible()
                assert len(solicitudes) == 1
                assert not codigos_solicitados
                # La misma persona vuelve por la pagina general del evento.
                page.goto(url + "/prueba")
                expect(page.get_by_alt_text("QR de ingreso de mi invitacion")).to_be_visible()
                assert len(solicitudes) == 1
                assert page.locator(".confirmacion-invitado").evaluate("e => e.scrollWidth <= e.clientWidth")
                if entrada == "cuenta":
                    page.locator(".confirmacion-invitado").scroll_into_view_if_needed()
                    page.screenshot(path=str(Path(tempfile.gettempdir()) / f"confirmacion-qr-{ancho}.png"))
                context.close()
        browser.close()
    print("OK: selector Google para todos los canales; sin codigos ni correo manual; nombres, cupo y QR persistente; movil/escritorio.")


if __name__ == "__main__":
    main()
