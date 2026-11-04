from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.seguridad import crear_token_bienvenida
from app.models.usuarios import User
from app.services.email import send_welcome_email


def enviar_bienvenida_una_vez(db: Session, usuario: User, destino: str | None = None) -> bool:
    # El bloqueo evita dos envios automaticos concurrentes para la misma cuenta.
    cuentas = db.scalars(select(User).where(func.lower(User.email) == usuario.email.lower()).order_by(User.id)
        .with_for_update().execution_options(populate_existing=True)).all()
    usuario = next(u for u in cuentas if u.id == usuario.id)
    if not usuario.activo or any(u.email_validado_en or u.bienvenida_enviada_en for u in cuentas):
        db.rollback()
        return False
    try:
        send_welcome_email(usuario.email, crear_token_bienvenida(usuario, destino), destino)
    except Exception:
        db.rollback()
        raise
    usuario.bienvenida_enviada_en = datetime.now(UTC)
    db.commit()
    return True
