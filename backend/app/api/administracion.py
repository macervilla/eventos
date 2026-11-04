from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.seguridad import obtener_usuario_actual
from app.db.session import get_db
from app.models.enums import EventoEstado
from app.models.eventos import Evento
from app.models.proveedores import Proveedor
from app.models.usuarios import User
from app.services.acceso import solicitar_enlace_acceso


def exigir_superadministrador(usuario: User = Depends(obtener_usuario_actual)) -> User:
    if not usuario.es_superadministrador:
        raise HTTPException(status_code=403, detail="Acceso exclusivo para superadministradores")
    return usuario


router = APIRouter(
    prefix="/administracion", tags=["administracion"],
    dependencies=[Depends(exigir_superadministrador)],
)


class EstadoRequest(BaseModel):
    activo: bool


class DatosUsuarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=255)
    nombre: str | None = Field(max_length=160)

    @field_validator("email", mode="before")
    @classmethod
    def normalizar_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("nombre", mode="before")
    @classmethod
    def normalizar_nombre(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value


def usuario_read(usuario: User) -> dict:
    return {"id": usuario.id, "email": usuario.email, "nombre": usuario.nombre,
            "activo": usuario.activo, "es_superadministrador": usuario.es_superadministrador}


def evento_read(evento: Evento, email: str) -> dict:
    return {"id": evento.id, "nombre": evento.nombre, "slug": evento.slug,
            "activo": evento.activo, "estado": evento.estado.value,
            "propietario_email": email, "fecha_inicio": evento.fecha_inicio}


@router.get("/resumen")
def resumen(db: Session = Depends(get_db)) -> dict:
    def contar(modelo, *condiciones):
        return db.scalar(select(func.count()).select_from(modelo).where(*condiciones)) or 0

    return {
        "usuarios_total": contar(User),
        "usuarios_activos": contar(User, User.activo.is_(True)),
        "eventos_total": contar(Evento),
        "eventos_activos": contar(Evento, Evento.activo.is_(True)),
        "eventos_publicados": contar(Evento, Evento.activo.is_(True), Evento.estado == EventoEstado.PUBLICADO),
        "eventos_borrador": contar(Evento, Evento.activo.is_(True), Evento.estado == EventoEstado.BORRADOR),
        "eventos_proximos": contar(Evento, Evento.activo.is_(True), Evento.estado == EventoEstado.PUBLICADO,
                                    Evento.fecha_inicio >= datetime.now(timezone.utc)),
        "proveedores_total": contar(Proveedor),
        "proveedores_activos": contar(Proveedor, Proveedor.activo.is_(True)),
    }


@router.get("/usuarios")
def usuarios(q: str = "", offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
             db: Session = Depends(get_db)) -> dict:
    consulta = select(User)
    if q.strip():
        patron = f"%{q.strip()}%"
        consulta = consulta.where(or_(User.email.ilike(patron), User.nombre.ilike(patron)))
    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    return {"total": total, "items": [usuario_read(u) for u in db.scalars(
        consulta.order_by(User.id).offset(offset).limit(limit))]}


@router.patch("/usuarios/{usuario_id}")
def cambiar_usuario(usuario_id: int, data: EstadoRequest, db: Session = Depends(get_db)) -> dict:
    usuario = db.get(User, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.es_superadministrador and not data.activo:
        raise HTTPException(status_code=409, detail="No se puede desactivar un superadministrador")
    usuario.activo = data.activo
    db.commit()
    return usuario_read(usuario)


@router.put("/usuarios/{usuario_id}")
def editar_usuario(usuario_id: int, data: DatosUsuarioRequest, db: Session = Depends(get_db)) -> dict:
    usuario = db.get(User, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    email = str(data.email)
    email_anterior = usuario.email
    if email != email_anterior:
        usuario.email_validado_en = None
        usuario.bienvenida_enviada_en = None
        # La nueva direccion debe acreditar su propia identidad de Google.
        usuario.google_subject = None
        for proveedor in db.scalars(select(Proveedor).where(
            Proveedor.usuario_id == usuario.id, func.lower(Proveedor.email) == email_anterior.lower(),
        )):
            proveedor.email = email
    usuario.email = email
    usuario.nombre = data.nombre
    db.commit()
    return usuario_read(usuario)


@router.post("/usuarios/{usuario_id}/reenviar-acceso")
def reenviar_acceso(usuario_id: int, db: Session = Depends(get_db)) -> dict:
    usuario = db.get(User, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not usuario.activo:
        raise HTTPException(status_code=409, detail="Activa la cuenta antes de enviar el enlace de ingreso")
    solicitar_enlace_acceso(db, usuario.email, usuario_id=usuario.id)
    return {"message": f"Enlace de ingreso enviado a {usuario.email}. Vence en 30 minutos."}


@router.get("/eventos")
def eventos(q: str = "", offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
            db: Session = Depends(get_db)) -> dict:
    consulta = select(Evento, User.email).join(User, Evento.propietario_id == User.id)
    if q.strip():
        patron = f"%{q.strip()}%"
        consulta = consulta.where(or_(Evento.nombre.ilike(patron), Evento.slug.ilike(patron), User.email.ilike(patron)))
    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    return {"total": total, "items": [evento_read(e, email) for e, email in db.execute(
        consulta.order_by(Evento.id.desc()).offset(offset).limit(limit))]}


@router.patch("/eventos/{evento_id}")
def cambiar_evento(evento_id: int, data: EstadoRequest, db: Session = Depends(get_db)) -> dict:
    evento = db.get(Evento, evento_id)
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    evento.activo = data.activo
    evento.deleted_at = None if data.activo else datetime.now(timezone.utc)
    db.commit()
    return evento_read(evento, evento.propietario.email)


@router.get("/proveedores")
def proveedores(q: str = "", offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
                db: Session = Depends(get_db)) -> dict:
    consulta = select(Proveedor, User.email).join(User, Proveedor.usuario_id == User.id)
    if q.strip():
        patron = f"%{q.strip()}%"
        consulta = consulta.where(or_(Proveedor.nombre_comercial.ilike(patron), Proveedor.slug.ilike(patron), User.email.ilike(patron)))
    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    return {"total": total, "items": [
        {"id": p.id, "nombre": p.nombre_comercial, "slug": p.slug, "activo": p.activo, "propietario_email": email}
        for p, email in db.execute(consulta.order_by(Proveedor.id.desc()).offset(offset).limit(limit))
    ]}
