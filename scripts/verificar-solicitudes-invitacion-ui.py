"""Solicitudes y contactos con API simulada; no envia correos ni mensajes."""
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright


def main():
    base = os.getenv("EVENTOS_UI_URL", "http://127.0.0.1:5188/eventos").rstrip("/")
    evento = dict(id=1, nombre="Fiesta", slug="prueba", titulo_visual="Nuestra fiesta",
                  textos_portada=None, colores_textos={}, descripcion=None, fecha_inicio=None,
                  lugar_tipo="domicilio", direccion=None, localidad=None, provincia=None, pais="Argentina",
                  latitud=None, longitud=None, salon=None, portada_url=None, portada_encuadre=None,
                  template_key="classic", tipografia="sistema", colores={}, estado="PUBLICADO",
                  confirmado=True, modulos_habilitados=[], galeria=[], limite_galeria=10,
                  galeria_config=dict(modo="grilla", filas=2, columnas=2))
    config = dict(activo=True, aprobacion="manual", validacion="email", verificar_invitados=True,
                  requiere_login=True, permitir_modificaciones=True, cierre_rsvp=None,
                  listas_compartidas=True, canales=["email", "whatsapp"], otp_minutos=10, otp_intentos=5)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 390):
            for medios in ("ninguno", "sin_contactos", "whatsapp", "email", "ambos"):
                estado = {"solicitud": None, "envios": [], "resoluciones": [], "configuraciones": []}
                context = browser.new_context(viewport={"width": ancho, "height": 900})
                context.add_init_script("localStorage.setItem('eventos_sesion','cuenta-verificada')")
                errores = []

                def api(route):
                    url = urlsplit(route.request.url)
                    ruta = url.path.removeprefix("/api-vps")
                    status = 200
                    if ruta == "/publico/prueba":
                        data = {"tipo": "evento"}
                    elif ruta == "/eventos/prueba":
                        data = evento
                    elif ruta.endswith("/permisos"):
                        data = dict(usuario={"id": 20, "email": "ana@example.com"}, rol="visitante", puede_editar=False, permisos_invitados=[])
                    elif ruta == "/acceso/yo":
                        data = dict(usuario_id=20, email="ana@example.com", opciones=[])
                    elif ruta.endswith("/mis-invitaciones"):
                        data = {"invitaciones": []}
                    elif ruta.endswith("/solicitudes/opciones"):
                        hosts = [] if medios == "ninguno" else [dict(id=10, nombre="Lili",
                            whatsapp_url="https://wa.me/5492966123456?text=Consulta" if medios in {"whatsapp", "ambos"} else None,
                            email_url="mailto:publico@example.com?subject=Consulta" if medios in {"email", "ambos"} else None)]
                        if medios == "ambos":
                            hosts.append(dict(id=11, nombre="Leo", whatsapp_url=None, email_url=None))
                        data = dict(agasajados=hosts, email_verificado="ana@example.com")
                    elif ruta.endswith("/solicitudes/contactos") and route.request.method == "GET":
                        data = [dict(agasajado_id=10, cuenta="Lili", puede_configurar=True, nombre_publico="Lili", habilitado=True,
                                     email=None, whatsapp=None, publicar_email=False, publicar_whatsapp=False)]
                    elif "/solicitudes/contactos/" in ruta:
                        estado["configuraciones"].append(route.request.post_data_json)
                        data = route.request.post_data_json
                    elif ruta.endswith("/solicitudes") and route.request.method == "POST":
                        datos = route.request.post_data_json
                        assert datos["nombre"] and datos["apellido"] and datos["agasajado_id"] == 10
                        estado["envios"].append(datos)
                        if estado["solicitud"] is None:
                            estado["solicitud"] = dict(id=1, agasajado_id=10, nombre=datos["nombre"], apellido=datos["apellido"],
                                email="ana@example.com", telefono=datos.get("telefono"), canal=datos["canal"], estado="PENDIENTE",
                                requiere_revision=False, invitacion_id=None, revision_administrador=False, coincidencias=[])
                        data = {"message": "Recibimos tu solicitud. El agasajado podrá revisarla y enviarte una invitación."}
                    elif ruta.endswith("/solicitudes"):
                        filtro = parse_qs(url.query).get("estado", [""])[0]
                        solicitud = estado["solicitud"]
                        data = {"items": [solicitud] if solicitud and (not filtro or filtro == solicitud["estado"]) else [], "puede_revisar": True}
                    elif ruta.endswith("/resolver"):
                        decision = route.request.post_data_json
                        estado["resoluciones"].append(decision)
                        estado["solicitud"].update(estado=decision["estado"], invitacion_id=42 if decision["estado"] == "APROBADA" else None)
                        data = {"estado": decision["estado"], "invitacion_id": estado["solicitud"]["invitacion_id"]}
                    elif ruta.endswith("/acceso"):
                        data = dict(permisos=["ver_invitados", "editar_invitados"], usuario_id=10, solo_responsable=True,
                                    config=config, roles_disponibles={}, puede_gestionar_solicitudes=True)
                    elif ruta.endswith("/lista"):
                        data = {"items": [], "total": 0}
                    else:
                        status, data = 404, {"detail": "No disponible"}
                    assert "/qr" not in ruta and "/portal/confirmar" not in ruta
                    route.fulfill(status=status, content_type="application/json", body=json.dumps(data))

                context.route("**/api-vps/**", api)
                page = context.new_page()
                page.on("pageerror", lambda e: errores.append(str(e)))
                page.goto(base + "/prueba")
                card = page.locator(".confirmacion-invitado")
                expect(card.get_by_role("heading", name="No encontramos una invitación para tu cuenta")).to_be_visible()
                expect(card.get_by_role("button", name="Confirmar asistencia", exact=True)).to_have_count(0)
                if medios == "ninguno":
                    expect(card).to_contain_text("canales habituales")
                    expect(card.get_by_role("button", name="Enviar solicitud")).to_have_count(0)
                else:
                    if medios == "ambos":
                        card.get_by_label("Agasajado al que conocés").select_option("10")
                    expect(card.get_by_role("link", name="WhatsApp", exact=True)).to_have_count(1 if medios in {"ambos", "whatsapp"} else 0)
                    expect(card.get_by_role("link", name="Enviar email", exact=True)).to_have_count(1 if medios in {"ambos", "email"} else 0)
                    expect(card.get_by_label("Correo verificado de tu cuenta")).to_have_value("ana@example.com")
                    card.get_by_label("Nombre", exact=True).fill("Ana")
                    card.get_by_label("Apellido", exact=True).fill("Perez")
                    if medios == "whatsapp":
                        card.get_by_label("Medio de contacto").select_option("whatsapp")
                        card.get_by_label("WhatsApp con código de país").fill("+5492966123456")
                    assert card.evaluate("el => el.scrollWidth <= el.clientWidth")
                    if medios == "ambos":
                        card.screenshot(path=str(Path(tempfile.gettempdir()) / f"solicitud-publica-{ancho}.png"))
                    card.get_by_role("button", name="Enviar solicitud").click()
                    expect(card.get_by_role("status")).to_have_text("Recibimos tu solicitud. El agasajado podrá revisarla y enviarte una invitación.")
                    assert len(estado["envios"]) == 1 and not estado["resoluciones"]
                    # El panel usa los mismos datos de solicitud; cancelar no aprueba.
                    page.goto(base + "/prueba/invitados")
                    panel = page.locator(".solicitudes-panel")
                    expect(panel.get_by_role("heading", name="Solicitudes de invitación", exact=True)).to_be_visible()
                    expect(panel.get_by_role("heading", name="Ana Perez", exact=True)).to_be_visible()
                    panel.get_by_role("button", name="Aprobar solicitud", exact=True).click()
                    page.get_by_role("dialog").get_by_role("button", name="Cancelar", exact=True).click()
                    assert not estado["resoluciones"]
                    panel.get_by_role("button", name="Aprobar solicitud", exact=True).click()
                    page.get_by_role("dialog").get_by_role("button", name="Aprobar solicitud", exact=True).click()
                    expect(panel.get_by_role("status")).to_contain_text("Solicitud aprobada")
                    assert len(estado["resoluciones"]) == 1
                    panel.get_by_label("Estado de solicitudes").select_option("APROBADA")
                    expect(panel.get_by_text("Invitación registrada.", exact=False)).to_be_visible()
                    assert panel.evaluate("el => el.scrollWidth <= el.clientWidth")
                    if medios == "ambos":
                        panel.get_by_text("Nombre y contactos públicos de los agasajados", exact=True).click()
                        panel.get_by_label("Email público", exact=True).fill("publico@example.com")
                        panel.get_by_label("Autorizar publicación del email").check()
                        panel.get_by_role("button", name="Guardar contacto público").click()
                        expect(panel.get_by_role("status")).to_have_text("Configuración pública guardada.")
                        assert estado["configuraciones"][0]["publicar_email"] is True
                        panel.screenshot(path=str(Path(tempfile.gettempdir()) / f"solicitudes-panel-{ancho}.png"))
                assert not errores, errores
                context.close()
        browser.close()
    print("OK: 10 escenarios de contactos y solicitudes; formulario, aprobacion con cancelacion, estados y publicacion explicita; movil y escritorio; sin RSVP ni QR.")


if __name__ == "__main__":
    main()
