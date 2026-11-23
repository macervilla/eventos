"""MediaMTX real + FastAPI aislado + dos navegadores con camara sintetica. Sin VPS."""
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from playwright.sync_api import expect, sync_playwright


def main():
    repo = Path(__file__).resolve().parents[1]
    prefix = "eventos-video-test-" + secrets.token_hex(4)
    usar_proxy = bool(os.getenv("VIDEO_TEST_PROXY"))
    base = "http://127.0.0.1:18090"
    app_url = os.getenv("EVENTOS_UI_URL", "http://127.0.0.1:5180")
    server = None
    with tempfile.TemporaryDirectory(prefix="video-integracion-") as directorio:
        taskdir = Path(directorio)
        config = taskdir / "mediamtx.yml"
        secreto = secrets.token_hex(32)
        env = {**os.environ, "DATABASE_URL": "sqlite:///" + (taskdir / "video-integracion.db").as_posix(),
            "MEDIA_ROOT": str(taskdir / "media"), "SECRET_KEY": secrets.token_hex(32), "VIDEO_ENABLED": "true",
            "MEDIAMTX_API_URL": "http://127.0.0.1:19997", "MEDIAMTX_PUBLIC_URL": "http://127.0.0.1:18890/eventos/rtc" if usar_proxy else "http://127.0.0.1:18889",
            "MEDIAMTX_AUTH_SECRET": secreto, "VIDEO_FIXTURE_PATH": str(taskdir / "fixture.json"),
            "PYTHONPATH": str(repo / "backend")}
        try:
            # Sobrescribir listeners mediante variables, evitando claves duplicadas en YAML.
            config.write_text((repo / "infra/mediamtx.yml").read_text(encoding="utf-8"), encoding="utf-8")
            subprocess.run(["docker", "run", "--rm", "-d", "--name", prefix,
                "-p", "127.0.0.1:18889:8889", "-p", "127.0.0.1:19997:9997", "-p", "18189:18189/udp", "-p", "18189:18189/tcp",
                "-v", f"{config}:/mediamtx.yml:ro", "-e", f"MTX_AUTHHTTPADDRESS=http://mediamtx:{secreto}@host.docker.internal:18090/interno/mediamtx/auth",
                "-e", "MTX_WEBRTCLOCALUDPADDRESS=" + ("" if os.getenv("VIDEO_TEST_TCP_ONLY") else ":18189"), "-e", "MTX_WEBRTCLOCALTCPADDRESS=:18189",
                "bluenviron/mediamtx:1.21.3"], check=True, capture_output=True)
            if usar_proxy:
                snippet = (repo / "docs/nginx.eventos.conf").read_text(encoding="utf-8").replace("http://127.0.0.1:8889/", "http://host.docker.internal:18889/")
                nginx = taskdir / "nginx.conf"
                nginx.write_text("events {}\nhttp { server { listen 8080;\n" + snippet + "\n} }\n", encoding="utf-8")
                subprocess.run(["docker", "run", "--rm", "-d", "--name", prefix + "-proxy", "-p", "127.0.0.1:18890:8080",
                    "-v", f"{nginx}:/etc/nginx/nginx.conf:ro", "nginx:alpine"], check=True, capture_output=True)
            with (taskdir / "server.log").open("w", encoding="utf-8") as log:
                server = subprocess.Popen([sys.executable, "-m", "tests.servidor_video_integracion"], cwd=repo / "backend", env=env, stdout=log, stderr=log)
                for _ in range(80):
                    try:
                        if (taskdir / "fixture.json").exists() and requests.get(base + "/health", timeout=1).ok: break
                    except requests.RequestException: pass
                    time.sleep(0.25)
                else: raise RuntimeError("No inicio el servidor aislado: " + (taskdir / "server.log").read_text(encoding="utf-8")[-2000:])
                fixture = json.loads((taskdir / "fixture.json").read_text())
                admin_headers = {"Authorization": "Bearer " + fixture["admin"]}
                def post(path, data, headers=None):
                    return requests.post(base + path, json=data, headers=headers, timeout=8)
                r = requests.put(base + "/invitados/video-prueba/vivo/autorizacion", json={"invitacion_id": fixture["ids"][0]}, headers=admin_headers, timeout=10)
                assert r.ok, r.text
                assert post("/invitados/video-prueba/vivo/iniciar", {"token": fixture["tokens"][1]}).status_code == 403
                assert post("/invitados/video-prueba/vivo/estado", {"token": fixture["tokens"][2]}).status_code == 404
                with sync_playwright() as p:
                    browser = p.chromium.launch(args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"])
                    publisher = browser.new_context(permissions=["camera", "microphone"])
                    viewer = browser.new_context()
                    viewer.add_init_script("sessionStorage.setItem('eventos_album_invitacion:video-prueba'," + json.dumps(json.dumps({"token": fixture["tokens"][1]})) + ")")
                    publisher.add_init_script("localStorage.setItem('eventos_sesion'," + json.dumps(fixture["cuentas"][0]) + ")")
                    viewer.add_init_script("localStorage.setItem('eventos_sesion'," + json.dumps(fixture["cuentas"][1]) + ")")
                    script = """window.pcs=[];window.streams=[];
                      const Original=window.RTCPeerConnection;window.RTCPeerConnection=class extends Original{constructor(...args){super(...args);window.pcs.push(this);}};
                      const gum=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                      navigator.mediaDevices.getUserMedia=async args=>{const s=await gum(args);window.streams.push(s);return s;};"""
                    publisher.add_init_script(script); viewer.add_init_script(script)
                    def api(route):
                        original = route.request.url
                        path = original.split("/api-vps", 1)[1]
                        response = route.fetch(url=base + path)
                        route.fulfill(response=response)
                    publisher.route("**/api-vps/**", api); viewer.route("**/api-vps/**", api)
                    cam = publisher.new_page(); album = viewer.new_page()
                    cam.goto(app_url + "/video-prueba/i/" + fixture["tokens"][0])
                    cam.get_by_role("button", name="Iniciar transmision", exact=True).click(timeout=20000)
                    modal = cam.get_by_role("dialog", name="Transmitir en vivo", exact=True)
                    expect(modal.get_by_role("button", name="Iniciar", exact=True)).to_be_enabled(timeout=15000)
                    modal.get_by_role("button", name="Iniciar", exact=True).click()
                    expect(modal.get_by_text("Transmision conectada.", exact=False)).to_be_visible(timeout=20000)
                    for _ in range(30):
                        e = post("/invitados/video-prueba/vivo/estado", {"token": fixture["tokens"][0]}).json()
                        if e["publicacion"]["estado"] == "activa": break
                        time.sleep(0.2)
                    requests.put(base + "/invitados/video-prueba/vivo/seleccion", headers=admin_headers,
                        json={"invitacion_id": fixture["ids"][0]}, timeout=10).raise_for_status()
                    album.goto(app_url + "/video-prueba/album")
                    video = album.locator(".album-evento-vivo video")
                    expect(video).to_be_visible(timeout=20000)
                    album.wait_for_function("document.querySelector('.album-evento-vivo video')?.videoWidth > 0", timeout=20000)
                    assert album.evaluate("document.querySelector('.album-evento-vivo video').srcObject.getAudioTracks().length===1")
                    cam.set_viewport_size(dict(width=396, height=900)); album.set_viewport_size(dict(width=396, height=900))
                    assert cam.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    assert album.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    cam.screenshot(path=str(Path(tempfile.gettempdir()) / "eventos-video-publicador-396.png"))
                    album.screenshot(path=str(Path(tempfile.gettempdir()) / "eventos-video-album-396.png"))
                    assert post("/invitados/video-prueba/vivo/iniciar", {"token": fixture["tokens"][0]}).status_code == 409
                    lectura = post("/invitados/video-prueba/vivo/ver", {"token": fixture["tokens"][1]}).json()
                    oferta = cam.evaluate("window.pcs[0].localDescription.sdp")
                    for headers in ({}, {"Authorization": "Bearer " + lectura["credencial"]}):
                        intento = requests.post(lectura["url"].replace("/whep", "/whip"), data=oferta,
                            headers={**headers, "Content-Type": "application/sdp", "Origin": app_url}, timeout=8)
                        assert intento.status_code in (401, 403)
                    album.evaluate("window.videoOriginal=document.querySelector('.album-evento-vivo video').srcObject;window.pcsAntes=window.pcs.length")
                    requests.put(base + f"/invitados/video-prueba/lista/{fixture['ids'][1]}/fotos/estado", headers=admin_headers, json={"bloqueadas": True}, timeout=5).raise_for_status()
                    album.get_by_role("button", name="Actualizar album", exact=True).click()
                    expect(album.locator(".album-evento-imagen")).to_have_count(0)
                    assert album.evaluate("document.querySelector('.album-evento-vivo video').srcObject===window.videoOriginal && window.pcs.length===window.pcsAntes")
                    modal.get_by_role("button", name="Cambiar camara", exact=True).click()
                    expect(modal.get_by_role("button", name="Cambiar camara", exact=True)).to_be_enabled(timeout=10000)
                    assert album.evaluate("document.querySelector('.album-evento-vivo video').srcObject===window.videoOriginal")
                    # Dos camaras reales, previews del administrador y seleccion por tilde.
                    requests.put(base + "/invitados/video-prueba/vivo/autorizacion", headers=admin_headers,
                        json={"invitacion_id": fixture["ids"][1]}, timeout=10).raise_for_status()
                    cam2 = viewer.new_page()
                    cam2.goto(app_url + "/video-prueba/i/" + fixture["tokens"][1])
                    cam2.get_by_role("button", name="Iniciar transmision", exact=True).click()
                    modal2 = cam2.get_by_role("dialog", name="Transmitir en vivo", exact=True)
                    expect(modal2.get_by_role("button", name="Iniciar", exact=True)).to_be_enabled()
                    modal2.get_by_role("button", name="Iniciar", exact=True).click()
                    expect(modal2.get_by_text("Transmision conectada.", exact=False)).to_be_visible(timeout=20000)
                    control = browser.new_context(viewport=dict(width=1280, height=920))
                    control.add_init_script("localStorage.setItem('eventos_sesion'," + json.dumps(fixture["admin"]) + ")")
                    control.route("**/api-vps/**", api)
                    panel = control.new_page(); panel.goto(app_url + "/video-prueba/invitados")
                    panel.wait_for_function("document.querySelectorAll('.video-camara-preview video').length === 2 && [...document.querySelectorAll('.video-camara-preview video')].every(v=>v.videoWidth>0)", timeout=25000)
                    checks = panel.get_by_role("checkbox", name="Emitir en Album", exact=True)
                    expect(checks).to_have_count(2)
                    checks.nth(1).click()
                    expect(checks.nth(1)).to_be_checked()
                    album.wait_for_function("window.pcs.length > window.pcsAntes && document.querySelector('.album-evento-vivo video')?.videoWidth > 0", timeout=20000)
                    activos = post("/invitados/video-prueba/vivo/estado", {}, admin_headers).json()
                    assert all(c["estado"] == "activa" for c in activos["camaras"])
                    assert activos["invitacion_id"] == fixture["ids"][1]
                    checks.nth(1).click()
                    expect(checks.nth(1)).not_to_be_checked()
                    expect(album.locator(".album-evento-vivo video")).to_have_count(0, timeout=10000)
                    expect(album.locator(".album-evento-imagen")).to_be_visible()
                    checks.nth(0).click()
                    expect(checks.nth(0)).to_be_checked()
                    album.wait_for_function("document.querySelector('.album-evento-vivo video')?.videoWidth>0", timeout=20000)
                    panel.set_viewport_size(dict(width=396, height=920))
                    assert panel.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    panel.screenshot(path=str(Path(tempfile.gettempdir()) / "eventos-multicamara-admin-396.png"))
                    control.close()
                    requests.put(base + "/invitados/video-prueba/vivo/autorizacion", headers=admin_headers, json={"invitacion_id": None}, timeout=10).raise_for_status()
                    expect(video).to_have_count(0, timeout=15000)
                    cam.wait_for_function("window.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))", timeout=15000)
                    cam2.wait_for_function("window.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))", timeout=15000)
                    cam2.close()
                    # Volver a autorizar y detener voluntariamente conserva la distincion de estados.
                    requests.put(base + "/invitados/video-prueba/vivo/autorizacion", json={"invitacion_id": fixture["ids"][0]}, headers=admin_headers, timeout=10).raise_for_status()
                    modal.get_by_role("button", name="Preparar camara", exact=True).click()
                    expect(modal.get_by_role("button", name="Iniciar", exact=True)).to_be_enabled(timeout=10000)
                    modal.get_by_role("button", name="Iniciar", exact=True).click()
                    expect(modal.get_by_text("Transmision conectada.", exact=False)).to_be_visible(timeout=20000)
                    modal.get_by_role("button", name="Detener", exact=True).click()
                    for _ in range(20):
                        e = post("/invitados/video-prueba/vivo/estado", {"token": fixture["tokens"][0]}).json()
                        if e["publicacion"]["estado"] == "finalizada": break
                        time.sleep(0.25)
                    assert e["publicacion"]["estado"] == "finalizada"
                    modal.get_by_role("button", name="Preparar camara", exact=True).click()
                    expect(modal.get_by_role("button", name="Iniciar", exact=True)).to_be_enabled()
                    modal.get_by_role("button", name="Iniciar", exact=True).click()
                    expect(modal.get_by_text("Transmision conectada.", exact=False)).to_be_visible(timeout=20000)
                    for _ in range(20):
                        if post("/invitados/video-prueba/vivo/estado", {"token": fixture["tokens"][0]}).json()["publicacion"]["estado"] == "activa": break
                        time.sleep(0.2)
                    sesiones = requests.get("http://127.0.0.1:19997/v3/webrtc/sessions/list", timeout=5).json()["items"]
                    publicador = next(s for s in sesiones if s["state"] == "publish")
                    requests.post("http://127.0.0.1:19997/v3/webrtc/sessions/kick/" + publicador["id"], timeout=5).raise_for_status()
                    for _ in range(30):
                        e = post("/invitados/video-prueba/vivo/estado", {"token": fixture["tokens"][0]}).json()
                        if e["publicacion"]["estado"] == "interrumpida": break
                        time.sleep(0.25)
                    assert e["publicacion"]["estado"] == "interrumpida"
                    cam.wait_for_function("window.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))", timeout=15000)
                    # Error al reemplazar una camara: tambien debe liberar la camara nueva que fallo.
                    modal.get_by_role("button", name="Preparar camara", exact=True).click()
                    expect(modal.get_by_role("button", name="Iniciar", exact=True)).to_be_enabled()
                    modal.get_by_role("button", name="Iniciar", exact=True).click()
                    expect(modal.get_by_text("Transmision conectada.", exact=False)).to_be_visible(timeout=20000)
                    cam.evaluate("""() => { const pc=window.pcs.findLast(p=>p.connectionState==='connected');
                      pc.getSenders().find(s=>s.track?.kind==='video').replaceTrack=async()=>{throw new Error('Fallo de camara simulado');}; }""")
                    modal.get_by_role("button", name="Cambiar camara", exact=True).click()
                    expect(modal.get_by_role("alert")).to_contain_text("Fallo de camara simulado")
                    cam.wait_for_function("window.streams.every(s=>s.getTracks().every(t=>t.readyState==='ended'))", timeout=10000)
                    cam.evaluate("() => { navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Denegado','NotAllowedError');}; }")
                    modal.get_by_role("button", name="Preparar camara", exact=True).click()
                    expect(modal.get_by_role("alert")).to_contain_text("Permiti el acceso a camara y microfono")
                    subprocess.run(["docker", "stop", prefix], check=True, capture_output=True)
                    assert post("/invitados/video-prueba/portal/fotos/listar", {"token": fixture["tokens"][0]}).ok
                    assert not post("/invitados/video-prueba/vivo/estado", {"token": fixture["tokens"][0]}).json()["disponible"]
                    print("OK: MediaMTX real" + (" mediante Nginx/subcarpeta" if usar_proxy else "") + ", invitado emisor y espectador, audio/video, permisos, exclusividad, cambio de camara, revocacion, detencion, desconexion y fotos sin reiniciar video; MediaMTX caido no bloquea fotos.")
                    publisher.unroute_all(behavior="ignoreErrors"); viewer.unroute_all(behavior="ignoreErrors")
                    publisher.close(); viewer.close(); browser.close()
        finally:
            if server:
                server.terminate()
                try: server.wait(timeout=8)
                except subprocess.TimeoutExpired: server.kill(); server.wait()
            subprocess.run(["docker", "rm", "-f", prefix], capture_output=True)
            if usar_proxy: subprocess.run(["docker", "rm", "-f", prefix + "-proxy"], capture_output=True)


if __name__ == "__main__":
    main()
