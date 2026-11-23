"""Comprueba el aviso sin invitacion por rol, con API simulada y sin envios."""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright


def main():
    dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/prueba":
                self.path = "/index.html"
            super().do_GET()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(dist)))
    Thread(target=server.serve_forever, daemon=True).start()
    evento = dict(id=1, nombre="Prueba", slug="prueba", titulo_visual=None,
        textos_portada=None, descripcion="Evento de prueba", fecha_inicio=None,
        lugar_tipo="domicilio", direccion="Calle 123", localidad="Rio Gallegos",
        provincia="Santa Cruz", pais="Argentina", latitud=None, longitud=None,
        salon=None, portada_url=None, portada_encuadre=None, template_key="classic",
        tipografia="sistema", colores=dict(fondo="#f4f7f6", texto="#18212f", acento="#245c48"),
        estado="PUBLICADO", confirmado=True, modulos_habilitados=["detalles"], galeria=[], limite_galeria=10,
        galeria_config=dict(modo="grilla", filas=2, columnas=2))
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for rol, permisos, invitado in (
                ("administrador", [], False),
                ("colaborador", ["ver_invitados"], False),
                ("visitante", [], False),
                ("visitante", [], True),
                ("administrador", [], True),
            ):
                context = browser.new_context()
                context.add_init_script("localStorage.setItem('eventos_sesion','prueba')")

                def api(route):
                    path = route.request.url.split("?")[0]
                    if "/publico/" in path:
                        datos = dict(tipo="evento")
                    elif path.endswith("/acceso/yo"):
                        datos = dict(email="cuenta@example.com", usuario_id=1, opciones=[])
                    elif path.endswith("/permisos"):
                        datos = dict(usuario=dict(id=1, email="cuenta@example.com"), rol=rol,
                            puede_editar=rol == "administrador", permisos_invitados=permisos)
                    elif path.endswith("/mis-invitaciones"):
                        datos = dict(invitaciones=[dict(id=1, token="personal", nombre="Ana", apellido="Perez")] if invitado else [])
                    elif path.endswith("/solicitudes/opciones"):
                        datos = dict(agasajados=[], email_verificado="cuenta@example.com")
                    elif path.endswith("/acceso"):
                        datos = dict(permisos=[], config=dict(activo=False))
                    elif path.endswith("/portal"):
                        datos = dict(validado=True, validacion="cuenta", nombre="Ana", apellido="Perez",
                            cantidad_permitida=1, puede_confirmar=True, qr=None)
                    else:
                        datos = evento
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(datos))

                context.route("**/api-vps/**", api)
                page = context.new_page()
                errores = []
                page.on("pageerror", lambda error: errores.append(str(error)))
                # Detecta tambien si el aviso aparece transitoriamente antes de recibir permisos.
                page.add_init_script("""window.avisoVisto = false;
                    new MutationObserver(() => {
                        if (document.body?.textContent.includes('No encontramos una invitación para tu cuenta'))
                            window.avisoVisto = true;
                    }).observe(document, {subtree: true, childList: true});""")
                page.goto(f"http://127.0.0.1:{server.server_port}/prueba")
                page.wait_for_load_state("networkidle")
                expect(page.get_by_text("Evento de prueba", exact=True)).to_be_visible()
                aviso = page.get_by_role("heading", name="No encontramos una invitación para tu cuenta")
                if rol == "visitante" and not invitado:
                    expect(aviso).to_be_visible()
                else:
                    expect(aviso).to_have_count(0)
                    assert not page.evaluate("window.avisoVisto"), "El aviso aparecio transitoriamente"
                if invitado:
                    expect(page.get_by_role("button", name="Confirmar asistencia", exact=True)).to_be_visible()
                assert not errores, errores
                print(f"OK: {rol}, invitado={invitado}")
                context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
