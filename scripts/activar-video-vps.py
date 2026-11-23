"""Activacion autorizada de video en el VPS; no ejecuta migraciones ni modifica invitados."""
import argparse
import datetime
import ipaddress
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-publico", required=True, type=ipaddress.ip_address)
    args = parser.parse_args()
    root = Path("/var/www/eventos")
    if os.name != "posix" or not root.is_dir():
        raise SystemExit("Ejecutar solo dentro del VPS de Eventos")
    os.chdir(root)
    os.umask(0o077)
    compose = ["docker", "compose", "--env-file", ".env.vps", "-f", "compose.vps.yml"]

    def run(*command):
        subprocess.run(command, check=True)

    env_path = root / ".env.vps"
    original = env_path.read_text()
    nginx = root / "nginx.eventos.conf"
    candidate = root / "docs/nginx.eventos.conf"
    assert "/eventos/rtc/" in candidate.read_text(), "Falta configuracion nueva de Nginx"
    assert (root / "infra/mediamtx.yml").is_file()
    run(*compose, "--profile", "video", "config", "--quiet")
    run("nginx", "-t")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path("/var/backups/eventos") / ("activacion-video-" + stamp)
    backup.mkdir(parents=True, mode=0o700)
    for name in (".env.vps", "nginx.eventos.conf", "compose.vps.yml", "infra/mediamtx.yml"):
        target = backup / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target)
    print("Respaldo privado:", backup, flush=True)
    # Descargar antes de cambiar configuracion o reiniciar el backend.
    run(*compose, "--profile", "video", "pull", "mediamtx")
    existing = re.findall(r"^\s*MEDIAMTX_AUTH_SECRET\s*=\s*(.*?)\s*$", original, re.M)
    secret = existing[-1].strip("\"'") if existing else ""
    if secret and not re.fullmatch(r"[a-fA-F0-9]{64}", secret):
        raise SystemExit("El secreto existente requiere revision; no se reemplazo")
    values = {
        "VIDEO_ENABLED": "true", "VIDEO_BITRATE": "1200000",
        "MEDIAMTX_API_URL": "http://mediamtx:9997",
        "MEDIAMTX_PUBLIC_URL": "/eventos/rtc",
        "MEDIAMTX_AUTH_SECRET": secret or secrets.token_hex(32),
        "WEBRTC_PUBLIC_HOST": str(args.host_publico),
    }
    text = original
    for key, value in values.items():
        pattern = r"^\s*" + re.escape(key) + r"\s*=.*$"
        if re.search(pattern, text, re.M):
            text = re.sub(pattern, lambda _m: key + "=" + value, text, flags=re.M)
        else:
            text = text.rstrip("\n") + "\n" + key + "=" + value + "\n"
    pending = env_path.with_name(".env.vps.video-pending")
    pending.write_text(text)
    pending.chmod(0o600)
    pending.replace(env_path)
    run(*compose, "--profile", "video", "config", "--quiet")
    shutil.copy2(candidate, nginx)
    try:
        run("nginx", "-t")
    except subprocess.CalledProcessError:
        shutil.copy2(backup / "nginx.eventos.conf", nginx)
        shutil.copy2(backup / ".env.vps", env_path)
        raise SystemExit("Nginx rechazo el cambio; configuraciones restauradas")
    run(*compose, "--profile", "video", "up", "-d", "--no-deps", "--force-recreate", "backend", "mediamtx")
    for _ in range(40):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8009/health", timeout=2) as response:
                if response.status == 200:
                    break
        except OSError:
            pass
        time.sleep(1)
    else:
        raise SystemExit("Backend sin respuesta; revisar servicios antes de recargar Nginx")
    run(*compose, "exec", "-T", "backend", "python", "-c",
        "from app.core.config import settings; from app.services.mediamtx import mediamtx; "
        "assert settings.video_enabled and settings.mediamtx_auth_secret.get_secret_value(); "
        "print('Video habilitado; API MediaMTX accesible; sesiones:', len(mediamtx.sessions()))")
    run("systemctl", "reload", "nginx")
    with urllib.request.urlopen("https://acersistemas.site/eventos/api/health", timeout=15) as response:
        assert response.status == 200
    run(*compose, "--profile", "video", "ps")
    print("Activacion completa. Sin migraciones ni cambios de invitados. Falta prueba desde otra red/celular.")


if __name__ == "__main__":
    main()
