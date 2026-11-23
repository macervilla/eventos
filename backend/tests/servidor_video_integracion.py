"""Servidor exclusivo de pruebas locales; nunca usar con una DATABASE_URL de produccion."""
import json
import os
from io import BytesIO
from pathlib import Path

from PIL import Image
import uvicorn

from app.core.config import settings
from app.core.seguridad import crear_token_sesion
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.main import app
from app.models.enums import EventoEstado
from app.models.eventos import Evento, EventoModulo
from app.models.invitaciones import FotoInvitado, Invitacion
from app.models.usuarios import User
from app.services.invitados import ahora, cifrador, emitir
from app.services.media_storage import media_storage

assert settings.database_url.startswith("sqlite:///") and "video-integracion" in settings.database_url
Base.metadata.create_all(engine)
with SessionLocal() as db:
    admin = User(email="admin-video@example.com", nombre="Administrador local", google_subject="prueba-video",
                 email_validado_en=ahora(), es_superadministrador=True)
    db.add(admin); db.flush()
    evento = Evento(nombre="Evento de prueba WebRTC", slug="video-prueba", propietario_id=admin.id, estado=EventoEstado.PUBLICADO)
    otro = Evento(nombre="Otro evento privado", slug="otro-video", propietario_id=admin.id, estado=EventoEstado.PUBLICADO)
    db.add_all([evento, otro]); db.flush()
    for e in (evento, otro):
        db.add(EventoModulo(evento_id=e.id, modulo="invitados", activo=True,
            configuracion_json={"requiere_login": False, "verificar_invitados": False}))
    cuentas = [User(email=f"camara-{n}@example.com", google_subject=f"prueba-camara-{n}", email_validado_en=ahora()) for n in range(2)]
    db.add_all(cuentas); db.flush()
    a = Invitacion(evento_id=evento.id, nombre="Camara", apellido="Uno", cantidad_permitida=1, fotos_bloqueadas=True, usuario_id=cuentas[0].id)
    b = Invitacion(evento_id=evento.id, nombre="Espectador", apellido="Dos", cantidad_permitida=1, usuario_id=cuentas[1].id)
    c = Invitacion(evento_id=otro.id, nombre="Ajeno", cantidad_permitida=1)
    db.add_all([a, b, c]); db.flush()
    imagen = BytesIO(); Image.new("RGB", (80, 60), "green").save(imagen, "PNG")
    for inv in (a, b):
        key = f"fotos-invitados-privadas/prueba-{inv.id}.enc"
        path = media_storage._safe_path(key); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(cifrador().encrypt(imagen.getvalue()))
        db.add(FotoInvitado(invitacion_id=inv.id, slot=1, object_key=key, nombre_archivo="prueba.png",
                            mime_type="image/png", size_bytes=len(imagen.getvalue())))
    tokens = [emitir(db, inv, "enlace") for inv in (a, b, c)]
    datos = {"admin": crear_token_sesion(admin, metodo="google"), "tokens": tokens,
             "ids": [a.id, b.id, c.id], "cuentas": [crear_token_sesion(u, metodo="google") for u in cuentas]}
    db.commit()
Path(os.environ["VIDEO_FIXTURE_PATH"]).write_text(json.dumps(datos), encoding="utf-8")
uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("VIDEO_TEST_PORT", "18090")), log_level="warning")
