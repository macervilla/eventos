"""Prueba de sesion en navegador con Google/API simulados; sin correos ni cuentas reales."""
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    solicitudes = []
    opciones = [
        dict(tipo="administracion", id=1, nombre="Administracion", slug="administracion", path="/administracion", cuenta_id=1, token="cuenta-1"),
        dict(tipo="proveedor", id=2, nombre="Mi salon", slug="salon", path="/proveedores", cuenta_id=2, token="cuenta-2"),
    ]
    def sesion(token, vinculado=True):
        return dict(email="persona@gmail.com", token=token, usuario_id=2 if token=="cuenta-2" else 1,
                    google_vinculado=vinculado, email_validado=True, opciones=opciones)
    def api(route):
        request = route.request
        solicitudes.append((request.method, request.url, request.headers.get("authorization")))
        if request.url.endswith("/google-config"):
            data = {"client_id": "prueba.apps.googleusercontent.com"}
        elif request.url.endswith("/google"):
            data = sesion("cuenta-1")
        elif request.url.endswith("/enlace"):
            data = sesion("inicial", False)
        elif request.url.endswith("/yo"):
            data = sesion(request.headers.get("authorization", "").removeprefix("Bearer "))
        elif "/administracion/resumen" in request.url:
            data = dict(usuarios_total=0, usuarios_activos=0, eventos_total=0, eventos_activos=0,
                        eventos_publicados=0, eventos_borrador=0, eventos_proximos=0, proveedores_total=0, proveedores_activos=0)
        elif "/administracion/" in request.url:
            data = {"items": [], "total": 0}
        else:
            data = []
        route.fulfill(status=200, content_type="application/json", body=json.dumps(data))
    fake_google = """
    window.google = {accounts: {id: {
      initialize(options) { window._credential = options.callback; },
      renderButton(element) { const b=document.createElement('button'); b.textContent='Seleccionar cuenta de prueba'; b.onclick=()=>window._credential({credential:'credencial'}); element.appendChild(b); },
      disableAutoSelect() { window._salioDeEventos=true; }
    }}};
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width":1280,"height":900})
        context.route("**/api-vps/**", api)
        context.route("http://localhost:8009/**", api)
        context.route("https://accounts.google.com/gsi/client", lambda r: r.fulfill(content_type="application/javascript", body=fake_google))
        page = context.new_page()
        base = os.getenv("EVENTOS_UI_URL", "http://localhost:5179")
        page.goto(base + "/ingresar")
        nav = page.get_by_role("navigation", name="Sesion de Eventos")
        expect(nav.get_by_role("link",name="Ingresar",exact=True)).to_be_visible()
        expect(page.get_by_role("button",name="Recuperar acceso")).not_to_be_visible()
        page.get_by_role("button",name="Seleccionar cuenta de prueba").click()
        expect(page.get_by_role("heading",name="Elegir apartado")).to_be_visible()
        page.get_by_role("button",name="Mi salon Proveedor").click()
        expect(page).to_have_url(base + "/proveedores")
        assert page.evaluate("JSON.parse(sessionStorage.getItem('eventos_cuenta_pestana')).token") == "cuenta-2"
        nav.get_by_role("button",name="Mi cuenta",exact=True).click()
        expect(nav.get_by_role("button",name="Cerrar sesion")).to_be_visible()
        segunda = context.new_page()
        segunda.goto(base + "/proveedores")
        segunda.get_by_role("button",name="Mi cuenta",exact=True).click()
        expect(segunda.get_by_role("button",name="Cerrar sesion")).to_be_visible()
        segunda.goto(base + "/administracion")
        expect(segunda.get_by_role("heading",name="El proyecto, en numeros")).to_be_visible()
        segunda.wait_for_timeout(100)
        assert segunda.evaluate("JSON.parse(sessionStorage.getItem('eventos_cuenta_pestana')).token") == "cuenta-1"
        assert page.evaluate("JSON.parse(sessionStorage.getItem('eventos_cuenta_pestana')).token") == "cuenta-2"
        nav.get_by_role("button",name="Cerrar sesion").click()
        expect(nav.get_by_role("link",name="Ingresar",exact=True)).to_be_visible()
        expect(segunda.get_by_role("navigation",name="Sesion de Eventos").get_by_role("link",name="Ingresar",exact=True)).to_be_visible()
        assert page.evaluate("window._salioDeEventos") is True
        assert page.evaluate("localStorage.getItem('eventos_sesion')") is None
        page.goto(base + "/ingresar?enlace=bienvenida&destino=%2Fproveedores")
        expect(page.get_by_role("status").filter(has_text="Email validado")).to_be_visible()
        assert "enlace=" not in page.url
        page.get_by_role("button",name="Seleccionar cuenta de prueba").click()
        expect(page).to_have_url(base + "/proveedores")
        assert any(url.endswith("/google") and authorization == "Bearer inicial" for _,url,authorization in solicitudes)
        assert not any("solicitar-enlace" in url for _,url,_ in solicitudes)
        page.set_viewport_size({"width":390,"height":844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(Path(os.environ.get("TEMP","/tmp")) / "eventos-sesion-movil.png"),full_page=True)
        page.get_by_role("button",name="Mi cuenta",exact=True).click()
        page.get_by_role("button",name="Cerrar sesion").click()
        page.goto(base + "/eventos/nuevo")
        expect(page.get_by_role("navigation",name="Sesion de Eventos")).to_be_visible()
        page.screenshot(path=str(Path(os.environ.get("TEMP","/tmp")) / "eventos-sesion-escritorio.png"),full_page=True)
        assert sum(url.endswith("/enlace") for _,url,_ in solicitudes) == 1
        browser.close()
    print("UI OK: Google, sitios/cuenta correcta, bienvenida inicial, URL sin token, cero solicitudes de nuevos mails, logout entre pestanas y movil.")


if __name__ == "__main__":
    main()
