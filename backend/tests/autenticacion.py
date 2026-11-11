"""Identidad Google ya verificada para pruebas de autorizacion, sin red externa."""
from datetime import UTC, datetime

from sqlalchemy.orm import object_session

from app.core.seguridad import crear_token_sesion


def token_google(usuario):
    usuario.google_subject = usuario.google_subject or f"google-prueba-{usuario.id}"
    usuario.email_validado_en = usuario.email_validado_en or datetime.now(UTC)
    sesion = object_session(usuario)
    if sesion:
        sesion.flush()
    return crear_token_sesion(usuario, metodo="google")
