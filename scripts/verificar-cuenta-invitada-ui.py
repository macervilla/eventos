"""Tarjeta publica, cuenta diferente y selector Google con APIs simuladas."""
import json
import os
import tempfile
from io import BytesIO
import qrcode
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def main():
    base = os.getenv("EVENTOS_UI_URL", "http://127.0.0.1:5188/eventos").rstrip("/")
    token = "t" * 43
    imagen = BytesIO()
    qrcode.make("qr-ficticio-de-prueba").save(imagen, format="PNG")
    evento = dict(id=1, nombre="Fiesta", slug="prueba", titulo_visual="Nuestra fiesta",
                  textos_portada=None, colores_textos={}, descripcion=None, fecha_inicio=None,
                  lugar_tipo="domicilio", direccion=None, localidad=None, provincia=None, pais="Argentina",
                  latitud=None, longitud=None, salon=None, portada_url=None, portada_encuadre=None,
                  template_key="classic", tipografia="elegante", colores={}, estado="PUBLICADO",
                  confirmado=True, modulos_habilitados=[], galeria=[], limite_galeria=10,
                  galeria_config=dict(modo="grilla", filas=2, columnas=2))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 390):
            for caso in ("anonimo", "sin-invitacion", "enlace", "diferente", "pendiente", "rechazada", "revocada", "invalido", "fallo-red", "qr-vinculada", "sin-vincular"):
                estado = {"correcta": caso in {"pendiente", "qr-vinculada"}}
                errores = []
                context = browser.new_context(viewport={"width": ancho, "height": 900})
                if caso in {"sin-invitacion", "diferente", "pendiente", "fallo-red", "qr-vinculada"}:
                    context.add_init_script("localStorage.setItem('eventos_sesion','sesion-inicial')")
                context.add_init_script("""window.seleccionesGoogle=0; window.google={accounts:{id:{
                  disableAutoSelect(){window.seleccionesGoogle++},
                  initialize(opts){window.opcionesGoogle=opts},
                  renderButton(el){const b=document.createElement('button'); b.textContent='Elegir cuenta invitada';
                    b.onclick=()=>window.opcionesGoogle.callback({credential:'cuenta-correcta'}); el.appendChild(b)}
                }}};""")

                def api(route):
                    ruta = urlsplit(route.request.url).path.removeprefix("/api-vps").removeprefix("/eventos/api")
                    status = 200
                    if ruta == "/publico/prueba":
                        data = {"tipo": "evento"}
                    elif ruta == "/eventos/prueba":
                        data = evento
                    elif ruta == "/eventos/prueba/permisos":
                        usuario = None if caso in {"anonimo", "enlace", "rechazada", "revocada", "invalido", "sin-vincular"} and not estado["correcta"] else {"id": 4, "email": "juan@example.com"}
                        data = dict(usuario=usuario, rol="visitante", puede_editar=False, permisos_invitados=[])
                    elif ruta == "/invitados/prueba/mis-invitaciones":
                        status = 503 if caso == "fallo-red" else 200
                        data = {"invitaciones": [{"id": 1, "token": token, "nombre": "Juan", "apellido": "Perez"}] if estado["correcta"] else []}
                    elif ruta == "/invitados/prueba/portal":
                        if caso == "invalido":
                            status, data = 404, {"detail": "Invitacion no disponible"}
                        elif estado["correcta"]:
                            data = dict(validado=True, validacion="email", sesion="correo-verificado", email_asociado="juan@example.com",
                                        nombre="Juan", apellido="Perez", cantidad_permitida=2, solicitados=1,
                                        acompanantes=[], puede_modificar=True, puede_confirmar=True,
                                        rsvp="CONFIRMADO" if caso == "qr-vinculada" else "PENDIENTE", aprobacion="APROBADO" if caso == "qr-vinculada" else "PENDIENTE",
                                        qr="qr-ficticio" if caso == "qr-vinculada" else None, cupo_aprobado=1, ingresados=0)
                        else:
                            ajena = caso in {"diferente", "qr-vinculada"}
                            data = dict(validado=False, validacion="email", email_asociado=None if ajena or caso == "sin-vincular" else "j***@e***.com",
                                        cuenta_diferente=ajena, sin_invitacion=ajena, requiere_identidad=True, sin_contacto=caso == "sin-vincular",
                                        no_disponible=caso in {"rechazada", "revocada"}, puede_confirmar=False)
                    elif ruta.endswith("/portal/qr.png"):
                        assert estado["correcta"], "La cuenta ajena no debe pedir el QR"
                        route.fulfill(status=200, content_type="image/png", body=imagen.getvalue())
                        return
                    elif ruta == "/acceso/google-config":
                        data = {"client_id": "mock-client"}
                    elif ruta == "/acceso/google":
                        assert route.request.post_data_json["credential"] == "cuenta-correcta"
                        estado["correcta"] = True
                        data = {"token": "sesion-correcta"}
                    elif ruta == "/acceso/yo":
                        data = dict(usuario_id=4, email="juan@example.com", opciones=[])
                    elif ruta.endswith("/portal/fotos/listar"):
                        data = dict(fotos=[], bloqueadas=False, limite=4)
                    else:
                        status, data = 404, {"detail": "No disponible"}
                    route.fulfill(status=status, content_type="application/json", body=json.dumps(data))

                context.route("**/api-vps/**", api)
                context.route("**/eventos/api/**", api)
                page = context.new_page()
                page.on("pageerror", lambda err: errores.append(str(err)))
                personal = caso in {"enlace", "diferente", "rechazada", "revocada", "invalido", "qr-vinculada", "sin-vincular"}
                page.goto(base + "/prueba" + ("/i/" + token if personal else ""))
                tarjeta = page.locator(".confirmacion-invitado")
                if caso == "anonimo":
                    expect(tarjeta.get_by_role("button", name="Ingresar para verificar mi invitación")).to_be_visible()
                    expect(tarjeta).not_to_contain_text("No encontramos")
                elif caso == "sin-invitacion":
                    expect(tarjeta.get_by_role("heading", name="No encontramos una invitación para tu cuenta")).to_be_visible()
                    expect(tarjeta.get_by_role("alert")).to_have_count(0)
                    tarjeta.screenshot(path=str(Path(tempfile.gettempdir()) / f"sin-invitacion-{ancho}.png"))
                elif caso == "diferente":
                    expect(tarjeta.get_by_role("heading", name="No estás invitado con esta cuenta")).to_be_visible()
                    expect(tarjeta).to_have_attribute("role", "alert")
                    expect(tarjeta).to_contain_text("Contactá al agasajado")
                    expect(tarjeta).not_to_contain_text("juan@example.com")
                    expect(tarjeta.get_by_alt_text("QR de ingreso de mi invitacion")).to_have_count(0)
                elif caso == "sin-vincular":
                    expect(tarjeta.get_by_role("button", name="Ingresar con Google", exact=True)).to_be_visible()
                    expect(tarjeta).to_contain_text("contactá al agasajado")
                    expect(tarjeta.get_by_alt_text("QR de ingreso de mi invitacion")).to_have_count(0)
                elif caso == "enlace":
                    expect(tarjeta.get_by_role("button", name="Ingresar con Google", exact=True)).to_be_visible()
                    expect(tarjeta.get_by_role("button", name="Verificar mi correo")).to_have_count(0)
                    expect(tarjeta).not_to_contain_text("juan@example.com")
                elif caso in {"rechazada", "revocada"}:
                    expect(tarjeta.get_by_role("heading", name="Tu invitación no está habilitada para confirmar")).to_be_visible()
                elif caso == "invalido":
                    expect(tarjeta.get_by_role("alert")).to_be_visible()
                elif caso == "fallo-red":
                    expect(tarjeta.get_by_role("alert")).to_be_visible()
                    expect(tarjeta).not_to_contain_text("No encontramos")
                if caso != "pendiente":
                    expect(tarjeta.get_by_role("button", name="Confirmar asistencia", exact=True)).to_have_count(0)
                if caso in {"diferente", "sin-invitacion"}:
                    tarjeta.get_by_role("button", name="Cambiar de cuenta", exact=True).click()
                    page.get_by_role("button", name="Elegir cuenta invitada").click()
                    expect(tarjeta.get_by_role("button", name="Confirmar asistencia", exact=True)).to_be_visible()
                    assert page.evaluate("opcionesGoogle.auto_select === false && seleccionesGoogle >= 2")
                if caso == "pendiente":
                    tarjeta.get_by_role("button", name="Confirmar asistencia", exact=True).click()
                    expect(page.get_by_role("dialog").get_by_role("group", name="Titular").get_by_label("Nombre", exact=True)).to_have_value("Juan")
                if caso == "qr-vinculada":
                    qr = tarjeta.get_by_alt_text("QR de ingreso de mi invitacion")
                    expect(qr).to_be_visible()
                    page.reload()
                    expect(qr).to_be_visible()
                    estado["correcta"] = False
                    page.evaluate("localStorage.setItem('eventos_sesion','cuenta-ajena'); window.dispatchEvent(new Event('eventos:sesion'))")
                    expect(tarjeta.get_by_role("heading", name="No estás invitado con esta cuenta")).to_be_visible()
                    expect(qr).to_have_count(0)
                    expect(tarjeta.get_by_role("button", name="Confirmar asistencia", exact=True)).to_have_count(0)
                assert tarjeta.evaluate("el => el.scrollWidth <= el.clientWidth")
                assert not errores, errores
                context.close()
        browser.close()
    print("OK: 22 escenarios; cuenta ajena sin QR/confirmacion, aviso al agasajado, vinculada recupera QR al volver y lo pierde al cambiar de cuenta; movil/escritorio.")


if __name__ == "__main__":
    main()
