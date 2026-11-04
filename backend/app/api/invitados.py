from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.seguridad import obtener_usuario_actual, obtener_usuario_opcional
from app.db.session import get_db
from app.models.enums import RolEvento
from app.models.eventos import EventoUsuario
from app.models.invitaciones import (
    DistribucionInvitacion,
    Invitacion,
    MovimientoIngreso,
    MovimientoInvitacion,
)
from app.models.usuarios import User
from app.schemas.invitados import (
    RSVP,
    Aprobacion,
    AsignacionRol,
    AsignarAgasajados,
    ConfigInvitados,
    CorregirIngreso,
    Distribuir,
    Escaneo,
    InvitadoDatos,
    PortalAcceso,
    PortalRSVP,
    RegistrarIngreso,
)
from app.services import invitados as s
from app.services.invitados_distribucion import distribuir
from app.services.invitados_excel import excel, importar, preview
from app.services.invitados_notificaciones import notificar_qr
from app.services.invitados_permisos import ALLOWED, DEFAULTS, acceso
from app.services.invitados_portal import (
    acceso_portal,
    enviar_codigo,
    qr_png,
    resolver_portal,
    validar_acceso,
)
from app.services.media_storage import media_storage
from app.services.portada_invitacion import imagen_invitacion
from app.services.proveedores import get_or_create_user

router = APIRouter(prefix="/invitados", tags=["invitados"])
DB = Depends(get_db)
USUARIO = Depends(obtener_usuario_actual)
OPCIONAL = Depends(obtener_usuario_opcional)


def descarga(
    contenido, nombre, tipo="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
):
    return Response(
        contenido,
        media_type=tipo,
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{slug}/acceso")
def mi_acceso(slug: str, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, habilitado=False)
    return {
        "permisos": sorted(ctx.permisos),
        "solo_responsable": ctx.propio,
        "usuario_id": usuario.id,
        "config": s.configuracion(db, ctx.evento),
        "roles_disponibles": {k: sorted(v) for k, v in ALLOWED.items()},
    }


@router.put("/{slug}/config")
def configurar(slug: str, data: ConfigInvitados, db: Session = DB, usuario: User = USUARIO):
    return s.guardar_config(db, acceso(db, slug, usuario, "configurar_invitados", False), data)


@router.get("/{slug}/roles")
def roles(slug: str, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "roles", False)
    filas = db.execute(
        select(EventoUsuario, User.email)
        .join(User, EventoUsuario.usuario_id == User.id)
        .where(EventoUsuario.evento_id == ctx.evento.id)
    ).all()
    return [
        {
            "id": a.id,
            "usuario_id": a.usuario_id,
            "email": email,
            "rol": a.rol.value,
            "permisos": a.permisos
            if a.permisos is not None
            else sorted(DEFAULTS.get(a.rol.value, set())),
            "solo_responsable": a.solo_responsable,
        }
        for a, email in filas
    ]


@router.post("/{slug}/roles")
def asignar(slug: str, data: AsignacionRol, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "roles", False)
    if data.permisos is not None and not set(data.permisos) <= ALLOWED[data.rol]:
        raise HTTPException(422, "El rol no admite esos permisos")
    persona = get_or_create_user(db, str(data.email), "")
    rol = db.scalar(
        select(EventoUsuario).where(
            EventoUsuario.evento_id == ctx.evento.id,
            EventoUsuario.usuario_id == persona.id,
            EventoUsuario.rol == RolEvento(data.rol),
        )
    )
    if rol is None:
        rol = EventoUsuario(evento_id=ctx.evento.id, usuario_id=persona.id, rol=RolEvento(data.rol))
        db.add(rol)
    rol.permisos, rol.solo_responsable = data.permisos, data.solo_responsable
    s.auditar(
        db,
        ctx.evento.id,
        "asignacion_rol",
        usuario.id,
        usuario_destino=persona.id,
        rol=data.rol,
        permisos=data.permisos,
    )
    db.commit()
    return {"id": rol.id}


@router.post("/{slug}/agasajados")
def asignar_agasajados(
    slug: str, data: AsignarAgasajados, db: Session = DB, usuario: User = USUARIO
):
    ctx = acceso(db, slug, usuario, "roles", False)
    resultado = []
    for email in dict.fromkeys(str(e).strip().lower() for e in data.emails):
        persona = get_or_create_user(db, email, "")
        if not persona.activo:
            raise HTTPException(
                409,
                "Una de las cuentas esta desactivada. Debe reactivarla el administrador del proyecto",
            )
        asignacion = db.scalar(
            select(EventoUsuario).where(
                EventoUsuario.evento_id == ctx.evento.id,
                EventoUsuario.usuario_id == persona.id,
                EventoUsuario.rol == RolEvento.AGASAJADO,
            )
        )
        if asignacion is None:
            asignacion = EventoUsuario(
                evento_id=ctx.evento.id, usuario_id=persona.id, rol=RolEvento.AGASAJADO
            )
            db.add(asignacion)
        if asignacion.permisos is not None:
            asignacion.permisos = sorted(set(asignacion.permisos) | {"ver_invitados", "distribuir"})
        asignacion.solo_responsable = data.solo_responsable
        s.auditar(db, ctx.evento.id, "asignacion_agasajado", usuario.id, usuario_destino=persona.id)
        resultado.append({"email": persona.email, "usuario_id": persona.id})
    db.commit()
    return {"agasajados": resultado}


@router.post("/{slug}/roles/{rol_id}/revocar")
def revocar_rol(slug: str, rol_id: int, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "roles", False)
    rol = db.scalar(
        select(EventoUsuario).where(
            EventoUsuario.id == rol_id, EventoUsuario.evento_id == ctx.evento.id
        )
    )
    if rol is None or rol.rol in {RolEvento.PROPIETARIO, RolEvento.ENCARGADO}:
        raise HTTPException(409, "Asignacion no revocable desde este modulo")
    rol.permisos = []
    s.auditar(db, ctx.evento.id, "revocacion_rol", usuario.id, asignacion=rol.id)
    db.commit()
    return {"message": "Permisos revocados"}


def filtrar(
    ctx,
    q="",
    estado=None,
    canal=None,
    responsable_id=None,
    grupo=None,
    desde=None,
    hasta=None,
    activo=True,
):
    consulta = s.consulta(ctx).where(Invitacion.activo.is_(activo))
    if q:
        patron = f"%{q.strip()[:160]}%"
        consulta = consulta.where(
            or_(
                Invitacion.nombre.ilike(patron),
                Invitacion.apellido.ilike(patron),
                Invitacion.email.ilike(patron),
                Invitacion.telefono.ilike(patron),
                Invitacion.whatsapp.ilike(patron),
                Invitacion.instagram.ilike(patron),
                Invitacion.facebook.ilike(patron),
                Invitacion.telegram.ilike(patron),
                Invitacion.otro_contacto.ilike(patron),
                Invitacion.grupo.ilike(patron),
            )
        )
    if estado:
        campos_estado = {
            "rsvp": Invitacion.rsvp,
            "aprobacion": Invitacion.aprobacion,
            "distribucion": Invitacion.distribucion,
        }
        if ":" in estado:
            campo, valor = estado.split(":", 1)
            if campo not in campos_estado:
                raise HTTPException(422, "Filtro de estado invalido")
            consulta = consulta.where(campos_estado[campo] == valor)
        else:
            consulta = consulta.where(
                or_(
                    Invitacion.rsvp == estado,
                    Invitacion.aprobacion == estado,
                    Invitacion.distribucion == estado,
                )
            )
    if canal:
        consulta = consulta.where(Invitacion.canal == canal)
    if responsable_id:
        consulta = consulta.where(Invitacion.responsable_id == responsable_id)
    if grupo:
        consulta = consulta.where(Invitacion.grupo == grupo)
    if desde:
        if desde.tzinfo is None:
            desde = desde.replace(tzinfo=ZoneInfo(settings.zona_horaria))
        consulta = consulta.where(Invitacion.confirmado_at >= desde)
    if hasta:
        if hasta.tzinfo is None:
            hasta = hasta.replace(tzinfo=ZoneInfo(settings.zona_horaria))
        consulta = consulta.where(Invitacion.confirmado_at <= hasta)
    return consulta


@router.get("/{slug}/lista")
def listar(
    slug: str,
    q: str = "",
    estado: str | None = None,
    canal: str | None = None,
    responsable_id: int | None = None,
    grupo: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    activo: bool = True,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    db: Session = DB,
    usuario: User = USUARIO,
):
    ctx = acceso(db, slug, usuario)
    if "ver_invitados" not in ctx.permisos and "control_ingreso" not in ctx.permisos:
        raise HTTPException(403, "No tenes permiso para consultar invitados")
    consulta = filtrar(ctx, q, estado, canal, responsable_id, grupo, desde, hasta, activo)
    total = db.scalar(select(func.count()).select_from(consulta.subquery()))
    items = db.scalars(
        consulta.order_by(Invitacion.apellido, Invitacion.nombre, Invitacion.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "total": total,
        "items": [s.resumen_inv(inv, "ver_invitados" in ctx.permisos) for inv in items],
    }


@router.post("/{slug}/lista", status_code=201)
def crear(slug: str, data: InvitadoDatos, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "editar_invitados")
    inv = s.guardar_invitado(db, ctx, data)
    db.commit()
    return s.resumen_inv(inv)


@router.put("/{slug}/lista/{inv_id}")
def editar(slug: str, inv_id: int, data: InvitadoDatos, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "editar_invitados")
    inv = s.obtener(db, ctx, inv_id, True)
    email_anterior = inv.email
    activo_anterior = inv.activo
    s.guardar_invitado(db, ctx, data, inv)
    if not inv.activo or email_anterior != inv.email:
        s.revocar(db, inv, "enlace")
        s.revocar(db, inv, "qr")
    if activo_anterior != inv.activo:
        s.auditar(
            db, ctx.evento.id, "reactivacion" if inv.activo else "baja_logica", usuario.id, inv.id
        )
    db.commit()
    return s.resumen_inv(inv)


@router.post("/{slug}/lista/{inv_id}/rsvp")
def rsvp_asistido(slug: str, inv_id: int, data: RSVP, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "confirmar_asistido")
    inv = s.obtener(db, ctx, inv_id, True)
    if not inv.activo:
        raise HTTPException(409, "Invitacion desactivada")
    s.aplicar_rsvp(db, ctx.evento, inv, data, usuario.id)
    db.commit()
    resultado = s.resumen_inv(inv)
    resultado["correo_qr"] = notificar_qr(db, ctx.evento, inv)
    return resultado


@router.post("/{slug}/lista/{inv_id}/aprobar")
def aprobar(slug: str, inv_id: int, data: Aprobacion, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "aprobar")
    inv = s.obtener(db, ctx, inv_id, True)
    s.aprobar(db, ctx, inv, data)
    db.commit()
    resultado = s.resumen_inv(inv)
    resultado["correo_qr"] = notificar_qr(db, ctx.evento, inv)
    return resultado


@router.post("/{slug}/lista/{inv_id}/credencial/{tipo}/{accion}")
def credenciales(
    slug: str, inv_id: int, tipo: str, accion: str, db: Session = DB, usuario: User = USUARIO
):
    ctx = acceso(db, slug, usuario, "aprobar" if tipo == "qr" else "distribuir")
    if tipo not in {"qr", "enlace"} or accion not in {"emitir", "revocar", "regenerar"}:
        raise HTTPException(422, "Operacion de credencial invalida")
    inv = s.obtener(db, ctx, inv_id, True)
    token = None
    if accion == "revocar":
        s.revocar(db, inv, tipo)
    else:
        token = s.emitir(db, inv, tipo, accion == "regenerar")
    s.auditar(db, ctx.evento.id, "credencial_" + accion, usuario.id, inv.id, tipo=tipo)
    db.commit()
    return {"token": token}


@router.post("/{slug}/distribuir")
def distribucion(slug: str, data: Distribuir, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "distribuir")
    if data.canal not in s.configuracion(db, ctx.evento)["canales"]:
        raise HTTPException(403, "El canal esta deshabilitado para este evento")
    if data.tipo == "qr" and "aprobar" not in ctx.permisos:
        raise HTTPException(403, "No tenes permiso para emitir credenciales")
    return distribuir(db, ctx, data)


@router.get("/{slug}/lista/{inv_id}/qr.png")
def qr_administrativo(slug: str, inv_id: int, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "aprobar")
    inv = s.obtener(db, ctx, inv_id, True)
    c = s.credencial(db, inv, "qr")
    if not inv.activo or inv.aprobacion != "APROBADO" or not c or s.utc(c.vence_at) <= s.ahora():
        raise HTTPException(
            409, "No hay QR activo; aprobar o regenerar la credencial antes de descargar"
        )
    token = s.cifrador().decrypt(c.token_cifrado.encode()).decode()
    s.auditar(db, ctx.evento.id, "descarga_qr", usuario.id, inv.id)
    db.commit()
    return descarga(qr_png(token), "credencial.png", "image/png")


@router.get("/{slug}/plantilla.xlsx")
def plantilla(slug: str, db: Session = DB, usuario: User = USUARIO):
    acceso(db, slug, usuario, "importar")
    return descarga(excel([]), "plantilla-invitados.xlsx")


@router.get("/{slug}/portada.jpg")
def descargar_portada(slug: str, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "distribuir")
    url = imagen_invitacion(ctx.evento)
    return descarga(
        media_storage._safe_path(url.removeprefix("/media/")).read_bytes(),
        "invitacion.jpg",
        "image/jpeg",
    )


@router.post("/{slug}/importar/preview")
async def previsualizar(
    slug: str,
    actualizar: bool = False,
    file: UploadFile = File(...),
    db: Session = DB,
    usuario: User = USUARIO,
):
    ctx = acceso(db, slug, usuario, "importar")
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(422, "Usa un archivo .xlsx")
    return preview(db, ctx, await file.read(5 * 1024 * 1024 + 1), actualizar)


@router.post("/{slug}/importar/{token}")
def confirmar_importacion(slug: str, token: str, db: Session = DB, usuario: User = USUARIO):
    return importar(db, acceso(db, slug, usuario, "importar"), token)


@router.get("/{slug}/exportar.xlsx")
def exportar(
    slug: str,
    q: str = "",
    estado: str | None = None,
    canal: str | None = None,
    responsable_id: int | None = None,
    grupo: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: Session = DB,
    usuario: User = USUARIO,
):
    ctx = acceso(db, slug, usuario, "ver_invitados")
    filas = db.scalars(
        filtrar(ctx, q, estado, canal, responsable_id, grupo, desde, hasta)
        .order_by(Invitacion.id)
        .limit(10000)
    ).all()
    columnas = [
        "Nombre",
        "Apellido",
        "Email",
        "Telefono",
        "Instagram",
        "WhatsApp",
        "Facebook",
        "Telegram",
        "Otro contacto",
        "Grupo",
        "Responsable ID",
        "Cupo maximo",
        "Adultos",
        "Menores",
        "Nombres menores",
        "Solicitados",
        "Aprobados",
        "Ingresados",
        "RSVP",
        "Aprobacion",
        "Distribucion",
        "Canal",
        "Confirmado",
    ]
    valores = [
        [
            i.nombre,
            i.apellido,
            i.email,
            i.telefono,
            i.instagram,
            i.whatsapp,
            i.facebook,
            i.telegram,
            i.otro_contacto,
            i.grupo,
            i.responsable_id,
            i.cantidad_permitida,
            i.adultos,
            i.menores,
            ", ".join(p.nombre for p in i.participantes if p.activo),
            i.adultos + i.menores,
            i.cupo_aprobado,
            i.ingresados,
            i.rsvp,
            i.aprobacion,
            i.distribucion,
            i.canal,
            i.confirmado_at.isoformat() if i.confirmado_at else None,
        ]
        for i in filas
    ]
    s.auditar(db, ctx.evento.id, "exportacion", usuario.id, cantidad=len(filas))
    db.commit()
    return descarga(excel(valores, columnas), "invitados-confirmaciones.xlsx")


@router.get("/{slug}/estadisticas")
def estadisticas(
    slug: str,
    control: bool = False,
    estado: str | None = None,
    canal: str | None = None,
    responsable_id: int | None = None,
    grupo: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: Session = DB,
    usuario: User = USUARIO,
):
    ctx = acceso(db, slug, usuario)
    if not ctx.permisos & {"estadisticas", "control_ingreso", "ver_asistencia"}:
        raise HTTPException(403, "Sin permiso de estadisticas")
    if control:
        if not ctx.permisos & {"control_ingreso", "ver_asistencia"}:
            raise HTTPException(403, "Sin permiso de asistencia general")
        ctx.propio = False
    t = filtrar(
        ctx,
        estado=estado,
        canal=canal,
        responsable_id=responsable_id,
        grupo=grupo,
        desde=desde,
        hasta=hasta,
    ).subquery()
    c = t.c
    metricas = {
        "invitados_registrados": func.count(),
        "preparadas": func.sum(case((c.distribucion == "PREPARADO", 1), else_=0)),
        "enviadas": func.sum(case((c.distribucion == "ENVIADO", 1), else_=0)),
        "confirmaciones": func.sum(case((c.rsvp.in_(["CONFIRMADO", "MODIFICADO"]), 1), else_=0)),
        "pendientes": func.sum(case((c.rsvp == "PENDIENTE", 1), else_=0)),
        "aprobadas": func.sum(case((c.aprobacion == "APROBADO", 1), else_=0)),
        "rechazadas": func.sum(case((c.rsvp == "RECHAZADO", 1), else_=0)),
        "canceladas": func.sum(case((c.rsvp == "CANCELADO", 1), else_=0)),
        "cupos_aprobados": func.sum(c.cupo_aprobado),
        "adultos": func.sum(c.adultos),
        "menores": func.sum(c.menores),
        "ingresados": func.sum(c.ingresados),
        "restantes": func.sum(
            case((c.aprobacion == "APROBADO", c.cupo_aprobado - c.ingresados), else_=0)
        ),
        "parciales": func.sum(
            case(((c.ingresados > 0) & (c.ingresados < c.cupo_aprobado), 1), else_=0)
        ),
        "completos": func.sum(
            case(((c.ingresados > 0) & (c.ingresados == c.cupo_aprobado), 1), else_=0)
        ),
    }
    valores = (
        db.execute(select(*[v.label(k) for k, v in metricas.items()]).select_from(t))
        .mappings()
        .one()
    )
    return {k: int(v or 0) for k, v in valores.items()}


@router.post("/{slug}/control/consultar")
def consultar_qr(slug: str, data: Escaneo, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "control_ingreso")
    inv = s.validar_qr(db, ctx, data.token)
    s.auditar(db, ctx.evento.id, "consulta_qr", usuario.id, inv.id)
    db.commit()
    return s.resumen_inv(inv, False)


@router.get("/{slug}/control/movimientos")
def movimientos(slug: str, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "ver_asistencia")
    filas = db.execute(
        select(MovimientoIngreso, Invitacion.nombre, Invitacion.apellido, User.email)
        .join(Invitacion, MovimientoIngreso.invitacion_id == Invitacion.id)
        .join(User, MovimientoIngreso.operador_id == User.id)
        .where(MovimientoIngreso.evento_id == ctx.evento.id)
        .order_by(MovimientoIngreso.id.desc())
        .limit(50)
    ).all()
    return [
        {
            "id": m.id,
            "nombre": nombre + " " + apellido,
            "cantidad": m.cantidad,
            "operador": email,
            "fecha": m.created_at,
        }
        for m, nombre, apellido, email in filas
    ]


@router.get("/{slug}/control/buscar")
def buscar_puerta(
    slug: str, q: str = Query(default="", max_length=160), db: Session = DB, usuario: User = USUARIO
):
    ctx = acceso(db, slug, usuario, "control_ingreso")
    patron = f"%{q.strip()}%"
    filas = db.scalars(
        select(Invitacion)
        .where(
            Invitacion.evento_id == ctx.evento.id,
            Invitacion.activo.is_(True),
            or_(
                Invitacion.nombre.ilike(patron),
                Invitacion.apellido.ilike(patron),
                Invitacion.grupo.ilike(patron),
            ),
        )
        .order_by(Invitacion.nombre)
        .limit(25)
    ).all()
    return {"items": [s.resumen_inv(i, False) for i in filas]}


@router.post("/{slug}/control/ingreso")
def ingresar(slug: str, data: RegistrarIngreso, db: Session = DB, usuario: User = USUARIO):
    return s.registrar_ingreso(db, acceso(db, slug, usuario, "control_ingreso"), data)


@router.post("/{slug}/control/{inv_id}/corregir")
def corregir(
    slug: str, inv_id: int, data: CorregirIngreso, db: Session = DB, usuario: User = USUARIO
):
    ctx = acceso(db, slug, usuario, "corregir_ingresos")
    inv = s.obtener(db, ctx, inv_id, True)
    previo = db.scalar(
        select(MovimientoIngreso).where(
            MovimientoIngreso.evento_id == ctx.evento.id,
            MovimientoIngreso.idempotencia == data.idempotencia,
        )
    )
    if previo:
        if previo.invitacion_id != inv.id or previo.cantidad != -data.cantidad:
            raise HTTPException(409, "Clave ya utilizada")
        return s.resumen_inv(inv, False)
    if data.cantidad > inv.ingresados:
        raise HTTPException(409, "La correccion excede los ingresos registrados")
    inv.ingresados -= data.cantidad
    inv.actualizado_por = usuario.id
    db.add(
        MovimientoIngreso(
            evento_id=ctx.evento.id,
            invitacion_id=inv.id,
            operador_id=usuario.id,
            cantidad=-data.cantidad,
            motivo=data.motivo,
            idempotencia=data.idempotencia,
        )
    )
    s.auditar(
        db,
        ctx.evento.id,
        "correccion_ingreso",
        usuario.id,
        inv.id,
        cantidad=-data.cantidad,
        motivo=data.motivo,
    )
    db.commit()
    return s.resumen_inv(inv, False)


@router.get("/{slug}/historial/{inv_id}")
def historial(slug: str, inv_id: int, db: Session = DB, usuario: User = USUARIO):
    ctx = acceso(db, slug, usuario, "ver_invitados")
    s.obtener(db, ctx, inv_id)
    return {
        "auditoria": [
            {
                "accion": a.accion,
                "actor_id": a.actor_id,
                "actor": db.get(User, a.actor_id).email if a.actor_id else "Invitado",
                "fecha": a.created_at,
                "datos": a.datos,
            }
            for a in db.scalars(
                select(MovimientoInvitacion)
                .where(MovimientoInvitacion.invitacion_id == inv_id)
                .order_by(MovimientoInvitacion.id.desc())
                .limit(200)
            )
        ],
        "distribuciones": [
            {"canal": d.canal, "estado": d.estado, "detalle": d.detalle, "fecha": d.created_at}
            for d in db.scalars(
                select(DistribucionInvitacion)
                .where(DistribucionInvitacion.invitacion_id == inv_id)
                .order_by(DistribucionInvitacion.id.desc())
                .limit(100)
            )
        ],
    }


def ip(request):
    # No confiar en X-Forwarded-For de clientes arbitrarios.
    return request.client.host if request.client else "desconocido"


@router.post("/{slug}/portal")
def portal(
    slug: str,
    data: PortalAcceso,
    request: Request,
    db: Session = DB,
    usuario: User | None = OPCIONAL,
):
    s.limitar(db, "portal:" + ip(request), 120, 60)
    return acceso_portal(db, slug, data, usuario=usuario)


@router.post("/{slug}/portal/codigo")
def otp(slug: str, data: PortalAcceso, request: Request, db: Session = DB):
    return enviar_codigo(db, slug, data, ip(request))


@router.post("/{slug}/portal/validar")
def validar(
    slug: str,
    data: PortalAcceso,
    request: Request,
    db: Session = DB,
    usuario: User | None = OPCIONAL,
):
    return validar_acceso(db, slug, data, ip(request), usuario=usuario)


@router.post("/{slug}/portal/rsvp")
def confirmar(
    slug: str, data: PortalRSVP, request: Request, db: Session = DB, usuario: User | None = OPCIONAL
):
    s.limitar(db, "rsvp:" + ip(request), 30, 60)
    acceso_portal(db, slug, data, True, True, usuario=usuario)
    inv, enlace, evento, cfg = resolver_portal(db, slug, data, True)
    s.aplicar_rsvp(db, evento, inv, data.rsvp)
    db.commit()
    resultado = acceso_portal(db, slug, data, True, usuario=usuario)
    resultado["correo_qr"] = notificar_qr(db, evento, inv)
    return resultado


@router.post("/{slug}/portal/qr.png")
def imagen_qr(
    slug: str,
    data: PortalAcceso,
    request: Request,
    db: Session = DB,
    usuario: User | None = OPCIONAL,
):
    s.limitar(db, "imagen-qr:" + ip(request), 30, 60)
    resultado = acceso_portal(db, slug, data, True, usuario=usuario)
    if not resultado["qr"]:
        raise HTTPException(409, "La credencial no esta aprobada o fue revocada")
    return descarga(qr_png(resultado["qr"]), "credencial.png", "image/png")
