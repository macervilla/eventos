from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import RolEvento
from app.models.eventos import Evento, EventoModulo, EventoUsuario
from app.models.usuarios import User

GESTION = {
    "ver_invitados",
    "editar_invitados",
    "importar",
    "distribuir",
    "aprobar",
    "estadisticas",
    "confirmar_asistido",
}
TODOS = GESTION | {
    "roles",
    "configurar_invitados",
    "control_ingreso",
    "ver_asistencia",
    "corregir_ingresos",
    "configurar_evento",
}
DEFAULTS = {
    "PROPIETARIO": TODOS,
    "ADMIN_EVENTO": TODOS,
    "AGASAJADO": {"ver_invitados", "editar_invitados", "distribuir", "estadisticas"},
    "GESTOR_INVITADOS": {"ver_invitados", "editar_invitados", "importar", "distribuir"},
    "CONTROL_INGRESO": {"control_ingreso", "ver_asistencia"},
}
ALLOWED = {
    "ADMIN_EVENTO": TODOS,
    "AGASAJADO": GESTION,
    "GESTOR_INVITADOS": GESTION,
    "CONTROL_INGRESO": {"control_ingreso", "ver_asistencia"},
}


@dataclass
class AccesoInvitados:
    evento: Evento
    usuario: User
    permisos: set[str]
    propio: bool


def permisos_de_asignacion(asignacion: EventoUsuario) -> set[str]:
    rol = asignacion.rol.value
    return (DEFAULTS.get(rol, set()) if asignacion.permisos is None
            else set(asignacion.permisos)) & ALLOWED.get(rol, set())


def asignacion_con_acceso(asignacion: EventoUsuario) -> bool:
    if asignacion.rol == RolEvento.PROPIETARIO:
        return asignacion.permisos != []
    if asignacion.rol == RolEvento.ENCARGADO:
        return asignacion.permisos is None or "configurar_evento" in asignacion.permisos
    return bool(permisos_de_asignacion(asignacion))


def modulo_invitados(db, evento):
    return db.scalar(
        select(EventoModulo).where(
            EventoModulo.evento_id == evento.id, EventoModulo.modulo == "invitados"
        )
    )


def acceso(
    db: Session, slug: str, usuario: User, permiso: str | None = None, habilitado=True
) -> AccesoInvitados:
    evento = db.scalar(select(Evento).where(Evento.slug == slug, Evento.activo.is_(True)))
    if evento is None:
        raise HTTPException(404, "Evento no encontrado")
    asignaciones = db.scalars(
        select(EventoUsuario).where(
            EventoUsuario.evento_id == evento.id, EventoUsuario.usuario_id == usuario.id
        )
    ).all()
    admin = (
        usuario.es_superadministrador
        or evento.propietario_id == usuario.id
        or any(a.rol == RolEvento.PROPIETARIO and asignacion_con_acceso(a) for a in asignaciones)
    )
    permisos, alcances = set(), []
    for a in asignaciones:
        actuales = permisos_de_asignacion(a)
        if actuales:
            permisos |= actuales
            alcances.append(a.solo_responsable)
    if admin:
        permisos = set(TODOS)
    if not usuario.activo or (permiso and permiso not in permisos) or not permisos:
        raise HTTPException(403, "No tenes permiso para esta operacion en este evento")
    modulo = modulo_invitados(db, evento)
    if habilitado and (modulo is None or not modulo.activo):
        raise HTTPException(409, "El modulo de invitados no esta habilitado")
    cfg = modulo.configuracion_json or {} if modulo else {}
    propio = (
        not admin
        and "roles" not in permisos
        and (not cfg.get("listas_compartidas", True) or (bool(alcances) and all(alcances)))
    )
    return AccesoInvitados(evento, usuario, permisos, propio)
