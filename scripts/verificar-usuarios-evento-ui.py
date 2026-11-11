"""Ventana de usuarios por evento con API simulada; no modifica datos reales."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for ancho in (1280, 390):
            cuentas = [
                dict(id=1, email="super@example.com", nombre="Super", activo=True, es_superadministrador=True),
                dict(id=3, email="mpcssarchivos@gmail.com", nombre="Archivos", activo=True, es_superadministrador=False),
                dict(id=4, email="nuevo@example.com", nombre="Nuevo", activo=True, es_superadministrador=False),
            ]
            asignaciones = dict(propietario_id=3, items=[
                dict(**cuentas[0], es_propietario=False, roles=[], acceso_efectivo=True),
                dict(**cuentas[1], es_propietario=True, roles=["PROPIETARIO"], acceso_efectivo=True),
            ])
            evento = dict(id=1, nombre="cumple atoto", slug="cumple-atoto", propietario_email=cuentas[1]["email"],
                          activo=True, estado="PUBLICADO", fecha_inicio=None)
            cambios = []
            fallar = [False]

            def api(route):
                ruta = urlparse(route.request.url).path.removeprefix("/api-vps")
                metodo = route.request.method
                if metodo in ("PUT", "DELETE"):
                    cambios.append((metodo, ruta, route.request.post_data_json if metodo == "PUT" else None))
                    if fallar[0]:
                        route.fulfill(status=409, content_type="application/json", body=json.dumps({"detail": "Cuenta inactiva"}))
                        return
                    uid = int(ruta.rsplit("/", 1)[1])
                    if metodo == "DELETE":
                        asignaciones["items"] = [u for u in asignaciones["items"] if u["id"] != uid]
                    else:
                        rol = route.request.post_data_json["rol"]
                        cuenta = next(c for c in cuentas if c["id"] == uid)
                        asignaciones["items"] = [u for u in asignaciones["items"] if u["id"] != uid]
                        if rol == "PROPIETARIO":
                            asignaciones["items"] = [u for u in asignaciones["items"] if u["id"] != asignaciones["propietario_id"]]
                            asignaciones["propietario_id"] = uid
                            evento["propietario_email"] = cuenta["email"]
                        asignaciones["items"].append(dict(**cuenta, roles=[rol], es_propietario=rol == "PROPIETARIO", acceso_efectivo=True))
                    data = asignaciones
                elif ruta.endswith("/acceso/yo"):
                    data = dict(email=cuentas[0]["email"], usuario_id=1, opciones=[])
                elif ruta.endswith("/resumen"):
                    data = dict(usuarios_total=3, usuarios_activos=3, eventos_total=1, eventos_activos=1,
                                eventos_publicados=1, eventos_borrador=0, eventos_proximos=0,
                                proveedores_total=0, proveedores_activos=0)
                elif ruta == "/administracion/eventos/1/usuarios":
                    data = asignaciones
                elif ruta == "/administracion/usuarios":
                    data = dict(items=cuentas, total=3)
                elif ruta == "/administracion/eventos":
                    data = dict(items=[evento], total=1)
                elif ruta == "/administracion/proveedores":
                    data = dict(items=[], total=0)
                else:
                    raise AssertionError((metodo, ruta))
                route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

            context = browser.new_context(viewport=dict(width=ancho, height=950))
            context.add_init_script("localStorage.setItem('eventos_sesion','prueba')")
            context.route("**/api-vps/**", api)
            page = context.new_page()
            page.on("dialog", lambda dialog: (_ for _ in ()).throw(AssertionError("Dialogo nativo inesperado")))
            page.goto(os.getenv("EVENTOS_UI_URL", "http://127.0.0.1:5180") + "/administracion")
            page.get_by_role("button", name="Usuarios de cumple atoto", exact=True).click()
            ventana = page.get_by_role("dialog", name="Usuarios de cumple atoto", exact=True)
            expect(ventana).to_be_visible()
            expect(ventana.get_by_role("button", name="Quitar usuario mpcssarchivos@gmail.com")).to_be_disabled()
            expect(ventana).to_contain_text("Superadministrador: acceso global")
            ventana.get_by_label("Cuenta", exact=True).select_option("4")
            ventana.get_by_label("Rol a asignar").select_option("AGASAJADO")
            ventana.get_by_role("button", name="Agregar usuario", exact=True).click()
            expect(ventana.get_by_role("button", name="Quitar usuario nuevo@example.com")).to_be_visible()
            assert len(cambios) == 1
            ventana.get_by_role("button", name="Quitar usuario nuevo@example.com").click()
            confirmacion = page.get_by_role("dialog", name="Quitar usuario del evento", exact=True)
            confirmacion.get_by_role("button", name="Cancelar", exact=True).click()
            assert len(cambios) == 1
            expect(ventana).to_be_visible()
            ventana.get_by_role("button", name="Quitar usuario nuevo@example.com").click()
            page.keyboard.press("Escape")
            expect(confirmacion).to_have_count(0)
            expect(ventana).to_be_visible()
            assert len(cambios) == 1
            ventana.get_by_role("button", name="Quitar usuario nuevo@example.com").click()
            confirmacion.get_by_role("button", name="Quitar acceso", exact=True).click()
            expect(ventana.get_by_role("button", name="Quitar usuario nuevo@example.com")).to_have_count(0)
            assert len(cambios) == 2
            ventana.get_by_label("Cuenta", exact=True).select_option("4")
            ventana.get_by_label("Rol a asignar").select_option("PROPIETARIO")
            ventana.get_by_role("button", name="Cambiar propietario", exact=True).click()
            transferencia = page.get_by_role("dialog", name="Cambiar propietario", exact=True)
            transferencia.get_by_role("button", name="Cancelar", exact=True).click()
            assert len(cambios) == 2
            ventana.get_by_role("button", name="Cambiar propietario", exact=True).click()
            transferencia.get_by_role("button", name="Cambiar propietario", exact=True).click()
            expect(ventana.get_by_role("button", name="Quitar usuario nuevo@example.com")).to_be_disabled()
            expect(ventana.get_by_role("button", name="Quitar usuario mpcssarchivos@gmail.com")).to_have_count(0)
            assert len(cambios) == 3
            # Fallo de API visible dentro de la ventana; conserva asignaciones y seleccion.
            fallar[0] = True
            ventana.get_by_label("Cuenta", exact=True).select_option("3")
            ventana.get_by_label("Rol a asignar").select_option("AGASAJADO")
            ventana.get_by_role("button", name="Agregar usuario", exact=True).click()
            expect(ventana.get_by_role("alert")).to_have_text("Cuenta inactiva")
            expect(ventana.get_by_role("alert")).to_be_in_viewport()
            expect(ventana.get_by_label("Cuenta", exact=True)).to_have_value("3")
            assert ventana.evaluate("e => e.scrollWidth <= e.clientWidth")
            page.screenshot(path=str(Path(os.environ.get("TEMP", "/tmp")) / f"usuarios-evento-{ancho}.png"))
            ventana.get_by_role("button", name="Cerrar", exact=True).last.click()
            expect(ventana).to_have_count(0)
            context.close()
        browser.close()
    print("Usuarios por evento: altas, bajas, transferencia, cancelaciones y errores OK en escritorio y movil.")


if __name__ == "__main__":
    main()
