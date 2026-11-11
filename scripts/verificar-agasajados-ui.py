"""Flujos de agasajados con API y agenda simuladas; no envia mensajes reales."""
import json
import re

from playwright.sync_api import expect, sync_playwright


def main():
    evento = dict(id=1, nombre="Fiesta", slug="prueba", titulo_visual="Nuestra fiesta",
        textos_portada=None, descripcion="Nos encontramos", fecha_inicio=None,
        lugar_tipo="domicilio", direccion="Calle 123", localidad="Rio Gallegos",
        provincia="Santa Cruz", pais="Argentina", latitud=None, longitud=None,
        salon=None, portada_url=None, portada_encuadre=None, template_key="classic",
        tipografia="sistema", colores=dict(fondo="#f4f7f6", texto="#18212f", acento="#245c48"),
        estado="PUBLICADO", confirmado=True, modulos_habilitados=[], galeria=[], limite_galeria=10,
        galeria_config=dict(modo="grilla", filas=2, columnas=2))
    config = dict(activo=True, canales=["whatsapp"], aprobacion="manual", validacion="email",
        permitir_modificaciones=True, cierre_rsvp=None, listas_compartidas=True,
        otp_minutos=10, otp_intentos=3)
    invitado = dict(id=1, nombre="Ana", apellido="", email="ana@example.com", telefono=None,
        whatsapp=None, facebook=None, telegram=None, otro_contacto=None, instagram=None,
        grupo=None, responsable_id=2, agregado_por="agasajado@example.com", cantidad_permitida=1,
        adultos=0, menores=0, nombres_menores=[], solicitados=0, cupo_aprobado=0,
        ingresados=0, restantes=0, rsvp="PENDIENTE", aprobacion="PENDIENTE",
        distribucion="SIN_ENVIAR", canal=None, activo=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 396):
            for admin in (True, False):
                permisos = ["ver_invitados", "editar_invitados", "distribuir"] + (["roles"] if admin else [])
                roles = [dict(id=5, email="agasajado@example.com", usuario_id=2, rol="AGASAJADO",
                              permisos=permisos[:3], solo_responsable=False),
                         dict(id=6, email="otro@example.com", usuario_id=3, rol="AGASAJADO",
                              permisos=permisos[:3], solo_responsable=False)]
                enviados = []

                def api(route):
                    url = route.request.url.split("?")[0]
                    if route.request.method == "POST":
                        enviados.append((url, route.request.post_data_json))
                        if url.endswith("/revocar"):
                            roles[0]["permisos"] = []
                            roles[0]["aviso"] = dict(id=9, alta=False,
                                contacto=dict(canal="whatsapp", destinatario="5492966123456"),
                                estado="PREPARADO", detalle="Pendiente de envio desde WhatsApp",
                                mensaje="Ya no tenes los permisos para cargar invitados.",
                                url_canal="https://wa.me/5492966123456?text=Aviso")
                        data = {}
                    elif url.endswith("/acceso/yo"):
                        data = dict(email="agasajado@example.com", usuario_id=2, opciones=[])
                    elif url.endswith("/permisos"):
                        data = dict(puede_editar=False, usuario=dict(id=2, email="agasajado@example.com"),
                                    rol="agasajado", permisos_invitados=permisos)
                    elif url.endswith("/acceso"):
                        data = dict(permisos=permisos, usuario_id=2, solo_responsable=False,
                                    config=config, roles_disponibles={"AGASAJADO":permisos[:3]})
                    elif url.endswith("/roles"):
                        data = roles
                    elif url.endswith("/lista"):
                        data = dict(items=[invitado], total=1)
                    else:
                        data = evento
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

                context = browser.new_context(viewport=dict(width=ancho, height=900))
                context.add_init_script("""
                    localStorage.setItem('eventos_sesion','prueba');
                    Object.defineProperty(navigator,'contacts',{value:{select:async()=>[
                      {name:['Luis'],email:['luis@example.com'],tel:['+54 9 2966 123456']}
                    ]}});
                """)
                context.route("**/api-vps/**", api)
                page = context.new_page()
                page.goto("http://localhost:5179/e/prueba" + ("/invitados" if admin else ""))
                if admin:
                    page.on("dialog", lambda dialog: dialog.accept())
                    expect(page.locator(".agasajado-asignado")).to_have_count(2)
                    for chip in page.locator(".agasajado-asignado").all():
                        texto = chip.locator("span").bounding_box()
                        quitar = chip.get_by_role("button").bounding_box()
                        assert quitar["x"] >= texto["x"] + texto["width"]
                    page.get_by_role("button", name="Quitar agasajado agasajado@example.com").click()
                    confirmacion = page.get_by_role("dialog", name="Quitar agasajado", exact=True)
                    expect(confirmacion).to_contain_text("agasajado@example.com")
                    assert not enviados
                    confirmacion.get_by_role("button", name="Cancelar", exact=True).click()
                    expect(confirmacion).to_have_count(0)
                    expect(page.get_by_role("button", name="Quitar agasajado agasajado@example.com")).to_be_visible()
                    assert not enviados
                    page.get_by_role("button", name="Quitar agasajado agasajado@example.com").click()
                    confirmacion.get_by_role("button", name="Confirmar baja", exact=True).click()
                    expect(page.get_by_role("button", name="Quitar agasajado agasajado@example.com")).to_have_count(0)
                    expect(page.get_by_role("button", name="Quitar agasajado otro@example.com")).to_be_visible()
                    assert enviados[0][0].endswith("/roles/5/revocar")
                    expect(page.get_by_role("heading", name="Avisos a agasajados y administradores")).to_be_visible()
                    expect(page.get_by_role("link", name="Abrir whatsapp")).to_have_attribute("href", re.compile("wa.me/5492966123456"))
                    page.get_by_role("button", name="Elegir agasajados de mis contactos").click()
                    expect(page.get_by_label("Emails de los agasajados, uno por linea")).to_have_value("luis@example.com")
                    page.get_by_label("Medio para avisar a luis@example.com").select_option("whatsapp")
                    expect(page.get_by_label("Numero con codigo de pais")).to_have_value("+54 9 2966 123456")
                    page.get_by_role("button", name="Asignar agasajados", exact=True).click()
                    expect(page.get_by_label("Emails de los agasajados, uno por linea")).to_have_value("")
                    assert enviados[-1][1]["contactos"] == [dict(email="luis@example.com", canal="whatsapp", destinatario="+54 9 2966 123456")]
                else:
                    expect(page.get_by_role("heading", name="Nuestra fiesta", exact=True)).to_be_visible()
                    expect(page.get_by_role("heading", name="Mis invitados", exact=True)).to_be_visible()
                    expect(page.get_by_text("Agregado por: agasajado@example.com")).to_be_visible()
                    expect(page.get_by_role("button", name="Asignar agasajados", exact=True)).to_have_count(0)
                    page.get_by_role("button", name="Agregar invitado individual").click()
                    page.get_by_role("button", name="Elegir contacto del telefono").click()
                    expect(page.get_by_label("Nombre", exact=True)).to_have_value("Luis")
                    page.get_by_role("button", name="Guardar", exact=True).click()
                    expect(page.get_by_role("button", name="Guardar", exact=True)).to_have_count(0)
                    assert enviados[-1][1]["nombre"] == "Luis"
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                context.close()
        browser.close()
    print("OK: quitar, avisos, canal y telefono persistidos desde la agenda, invitacion con Mis invitados, autor y alta por contactos; movil y escritorio.")


if __name__ == "__main__":
    main()
