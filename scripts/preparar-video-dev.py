"""Generar configuracion local aislada sin mostrar secretos ni sobrescribir archivos."""
import secrets
from pathlib import Path

destino = Path(__file__).resolve().parents[1] / ".env.video.dev"
try:
    with destino.open("x", encoding="utf-8") as archivo:
        for clave in ("VIDEO_DEV_DB_PASSWORD", "VIDEO_DEV_SECRET_KEY", "MEDIAMTX_AUTH_SECRET"):
            archivo.write(f"{clave}={secrets.token_hex(32)}\n")
        archivo.write("GOOGLE_CLIENT_ID=\n")
    print("Creado .env.video.dev; completa GOOGLE_CLIENT_ID si vas a iniciar sesion con Google.")
except FileExistsError:
    print("Se conserva .env.video.dev existente.")
