from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import select

from app.models.enums import EventoEstado, RolEvento
from app.models.eventos import Evento, EventoUsuario
from app.models.solicitudes_invitacion import ContactoPublicoAgasajado, SolicitudInvitacion
from app.models.usuarios import User
from app.schemas.invitados import InvitadoDatos
from app.services import invitados as s
from app.services.coincidencias_invitados import buscar, email_normalizado, nombre_normalizado, telefono_normalizado, telefono_con_identidad_verificada
from app.services.invitados_permisos import acceso, permisos_de_asignacion
from app.services.whatsapp import numero_whatsapp

RECIBIDA = "Recibimos tu solicitud. El agasajado podrá revisarla y enviarte una invitación."


def bloquear_evento(db, evento_id):
    # Mismo orden de locks para solicitudes, aprobaciones y altas/importaciones.
    db.scalar(select(Evento).where(Evento.id == evento_id).with_for_update())


def agasajados(db, evento_id):
    filas = db.execute(select(EventoUsuario, User).join(User, User.id == EventoUsuario.usuario_id).where(
        EventoUsuario.evento_id == evento_id, EventoUsuario.rol == RolEvento.AGASAJADO, User.activo.is_(True))).all()
    return {u.id: u for rol, u in filas if permisos_de_asignacion(rol)}


def administrador(db, ctx):
    if ctx.usuario.es_superadministrador or ctx.evento.propietario_id == ctx.usuario.id or "roles" in ctx.permisos:
        return True
    return any(permisos_de_asignacion(rol) & {"ver_invitados", "editar_invitados"}
        for rol in db.scalars(select(EventoUsuario).where(EventoUsuario.evento_id == ctx.evento.id,
        EventoUsuario.usuario_id == ctx.usuario.id, EventoUsuario.rol == RolEvento.ADMIN_EVENTO,
    )))


def contexto(db, slug, usuario, editar=False):
    ctx = acceso(db, slug, usuario, "editar_invitados" if editar else "ver_invitados")
    admin = administrador(db, ctx)
    if not admin and usuario.id not in agasajados(db, ctx.evento.id):
        raise HTTPException(403, "Solo el administrador o un agasajado autorizado gestiona solicitudes")
    return ctx, admin


def evento_publico(db, slug):
    evento = db.scalar(select(Evento).where(Evento.slug == slug, Evento.activo.is_(True),
        Evento.estado.notin_([EventoEstado.BORRADOR, EventoEstado.ARCHIVADO, EventoEstado.FINALIZADO])))
    if evento is None or not s.configuracion(db, evento)["activo"]:
        raise HTTPException(404, "Las solicitudes no estan disponibles para este evento")
    return evento


def datos_contacto(row):
    return {"nombre_publico": row.nombre_publico, "habilitado": row.habilitado,
            "email": row.email, "whatsapp": row.whatsapp,
            "publicar_email": row.publicar_email, "publicar_whatsapp": row.publicar_whatsapp}


def configuraciones(db, slug, usuario):
    ctx, admin = contexto(db, slug, usuario)
    usuarios = agasajados(db, ctx.evento.id)
    filas = {r.agasajado_id: r for r in db.scalars(select(ContactoPublicoAgasajado).where(ContactoPublicoAgasajado.evento_id == ctx.evento.id))}
    resultado = []
    for id_, persona in usuarios.items():
        if not admin and id_ != usuario.id:
            continue
        row = filas.get(id_)
        resultado.append({"agasajado_id": id_, "cuenta": persona.nombre or persona.email,
            "puede_configurar": (admin and bool(ctx.permisos & {"roles", "configurar_invitados"})) or (id_ == usuario.id and "editar_invitados" in ctx.permisos),
            **(datos_contacto(row) if row else {"nombre_publico": "", "habilitado": False, "email": None,
                "whatsapp": None, "publicar_email": False, "publicar_whatsapp": False})})
    return resultado


def guardar_contacto(db, slug, usuario, agasajado_id, data):
    ctx, admin = contexto(db, slug, usuario, editar=True)
    if not ((admin and ctx.permisos & {"roles", "configurar_invitados"}) or agasajado_id == usuario.id):
        raise HTTPException(403, "No podes publicar el contacto de otro agasajado")
    bloquear_evento(db, ctx.evento.id)
    if agasajado_id not in agasajados(db, ctx.evento.id):
        raise HTTPException(404, "Agasajado no disponible en este evento")
    values = data.model_dump(mode="json")
    if values["whatsapp"]:
        try:
            values["whatsapp"] = "+" + numero_whatsapp(values["whatsapp"], ctx.evento.codigo_pais, ctx.evento.pais)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    if values["email"]:
        values["email"] = email_normalizado(values["email"])
    row = db.scalar(select(ContactoPublicoAgasajado).where(ContactoPublicoAgasajado.evento_id == ctx.evento.id,
        ContactoPublicoAgasajado.agasajado_id == agasajado_id))
    if row is None:
        row = ContactoPublicoAgasajado(evento_id=ctx.evento.id, agasajado_id=agasajado_id)
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    s.auditar(db, ctx.evento.id, "contacto_publico_autorizado", usuario.id,
              agasajado_id=agasajado_id, habilitado=data.habilitado,
              publicar_email=data.publicar_email, publicar_whatsapp=data.publicar_whatsapp)
    db.commit()
    return datos_contacto(row)


def opciones(db, slug, usuario):
    evento = evento_publico(db, slug)
    activos = agasajados(db, evento.id)
    titulo = evento.titulo_visual or evento.nombre
    resultado = []
    for row in db.scalars(select(ContactoPublicoAgasajado).where(
            ContactoPublicoAgasajado.evento_id == evento.id, ContactoPublicoAgasajado.habilitado.is_(True)).order_by(ContactoPublicoAgasajado.id)):
        if row.agasajado_id not in activos:
            continue
        mensaje = f"Hola, quisiera consultar por una invitación para el evento {titulo}. Ingresé con mi cuenta, pero el sistema no encontró una invitación asociada. ¿Podrías verificarlo? Gracias."
        asunto = f"Consulta por invitación - {titulo}"
        cuerpo = f"Hola, quisiera consultar si tengo una invitación para el evento {titulo}. Ingresé al sistema, pero no encontré una invitación asociada a mi cuenta. Gracias."
        resultado.append({"id": row.agasajado_id, "nombre": row.nombre_publico,
            "whatsapp_url": "https://wa.me/" + row.whatsapp.removeprefix("+") + "?text=" + quote(mensaje, safe="") if row.publicar_whatsapp and row.whatsapp else None,
            "email_url": "mailto:" + quote(row.email, safe="@") + "?subject=" + quote(asunto, safe="") + "&body=" + quote(cuerpo, safe="") if row.publicar_email and row.email else None})
    return {"agasajados": resultado, "email_verificado": email_normalizado(usuario._email_google_sesion)}


def crear_solicitud(db, slug, usuario, data):
    evento = evento_publico(db, slug)
    bloquear_evento(db, evento.id)
    email = email_normalizado(usuario._email_google_sesion)
    if data.email and email_normalizado(data.email) != email:
        raise HTTPException(422, "Usa el correo verificado de tu cuenta")
    numero = telefono_normalizado(data.telefono, evento)
    if data.canal == "whatsapp" and not numero:
        raise HTTPException(422, "Completa un numero de WhatsApp internacional valido")
    config = db.scalar(select(ContactoPublicoAgasajado).where(ContactoPublicoAgasajado.evento_id == evento.id,
        ContactoPublicoAgasajado.agasajado_id == data.agasajado_id, ContactoPublicoAgasajado.habilitado.is_(True)))
    if config is None or data.agasajado_id not in agasajados(db, evento.id):
        raise HTTPException(422, "Selecciona un agasajado habilitado para este evento")
    anterior = db.scalar(select(SolicitudInvitacion).where(SolicitudInvitacion.evento_id == evento.id,
                                                         SolicitudInvitacion.email_verificado == email))
    identidades, contactos, nombres = buscar(db, evento, data.nombre, data.apellido, email, numero)
    vigentes = [i for i in identidades if i.activo and i.aprobacion not in {"RECHAZADO", "REVOCADO"}
                and i.rsvp not in {"RECHAZADO", "CANCELADO"}]
    if anterior or vigentes:
        db.commit()  # No duplicar ni notificar, tampoco revelar invitaciones existentes.
        return {"message": RECIBIDA}
    pendientes = db.scalars(select(SolicitudInvitacion).where(SolicitudInvitacion.evento_id == evento.id,
                                                            SolicitudInvitacion.estado == "PENDIENTE")).all()
    revision = bool(identidades or contactos or nombres or any(
        (numero and p.telefono == numero) or
        (p.nombre_normalizado, p.apellido_normalizado) == (nombre_normalizado(data.nombre), nombre_normalizado(data.apellido))
        for p in pendientes))
    for p in pendientes:
        if ((numero and p.telefono == numero) or
            (p.nombre_normalizado, p.apellido_normalizado) == (nombre_normalizado(data.nombre), nombre_normalizado(data.apellido))):
            p.requiere_revision = True
    row = SolicitudInvitacion(evento_id=evento.id, usuario_id=usuario.id, agasajado_id=data.agasajado_id,
        nombre=data.nombre, apellido=data.apellido, nombre_normalizado=nombre_normalizado(data.nombre),
        apellido_normalizado=nombre_normalizado(data.apellido), email_verificado=email, telefono=numero,
        canal=data.canal, requiere_revision=revision)
    db.add(row); db.flush()
    s.auditar(db, evento.id, "solicitud_invitacion_recibida", usuario.id, solicitud_id=row.id,
              agasajado_id=row.agasajado_id, requiere_revision=revision)
    db.commit()
    return {"message": RECIBIDA}


def lista(db, slug, usuario, estado="PENDIENTE"):
    ctx, admin = contexto(db, slug, usuario)
    query = select(SolicitudInvitacion).where(SolicitudInvitacion.evento_id == ctx.evento.id)
    if not admin:
        query = query.where(SolicitudInvitacion.agasajado_id == usuario.id)
    if estado:
        query = query.where(SolicitudInvitacion.estado == estado)
    items = []
    for row in db.scalars(query.order_by(SolicitudInvitacion.id.desc())):
        identidades, contactos, nombres = buscar(db, ctx.evento, row.nombre, row.apellido, row.email_verificado, row.telefono)
        candidatos = {inv.id: inv for inv in identidades + contactos + nombres}
        ambiguas = [i for i in contactos + nombres if i not in identidades]
        visibles = [inv for inv in candidatos.values() if admin or inv.responsable_id == usuario.id]
        items.append({"id": row.id, "nombre": row.nombre, "apellido": row.apellido,
            "email": row.email_verificado, "telefono": row.telefono, "telefono_verificado": False,
            "canal": row.canal, "estado": row.estado, "agasajado_id": row.agasajado_id,
            "requiere_revision": row.requiere_revision or bool(ambiguas),
            "invitacion_id": row.invitacion_id, "fecha": row.created_at,
            "coincidencias": [{"id": i.id, "nombre": i.nombre, "apellido": i.apellido,
                              "misma_identidad": i in identidades} for i in visibles],
            "revision_administrador": len(visibles) < len(candidatos)})
    return {"items": items, "puede_revisar": "editar_invitados" in ctx.permisos}


def decidir(db, slug, usuario, solicitud_id, data):
    ctx, admin = contexto(db, slug, usuario, editar=True)
    bloquear_evento(db, ctx.evento.id)
    query = select(SolicitudInvitacion).where(SolicitudInvitacion.id == solicitud_id, SolicitudInvitacion.evento_id == ctx.evento.id)
    if not admin:
        query = query.where(SolicitudInvitacion.agasajado_id == usuario.id)
    row = db.scalar(query.with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, "Solicitud no encontrada")
    if row.estado != "PENDIENTE":
        if row.estado != data.estado:
            raise HTTPException(409, "La solicitud ya fue resuelta")
        return {"estado": row.estado, "invitacion_id": row.invitacion_id}
    if row.agasajado_id not in agasajados(db, ctx.evento.id):
        raise HTTPException(409, "El agasajado ya no esta autorizado en este evento")
    if data.estado == "APROBADA":
        identidades, contactos, nombres = buscar(db, ctx.evento, row.nombre, row.apellido, row.email_verificado, row.telefono)
        # El telefono aportado es contacto, no prueba de identidad: nunca reasignar
        # un invitado de otra cuenta basandose solo en su telefono o nombre.
        ambiguas = [i for i in contactos + nombres if i not in identidades]
        if (row.requiere_revision or ambiguas) and not data.confirmar_revision:
            raise HTTPException(409, "Revisa las posibles coincidencias antes de aprobar")
        if len(identidades) > 1 and not data.invitacion_id:
            raise HTTPException(409, "Selecciona la invitacion existente que corresponde")
        inv = next((i for i in identidades if i.id == data.invitacion_id), None) if data.invitacion_id else next(iter(identidades), None)
        if data.invitacion_id and inv is None:
            raise HTTPException(409, "La invitacion elegida no corresponde al correo verificado")
        if inv is not None:
            if (not admin and inv.responsable_id != usuario.id) or (inv.responsable_id != row.agasajado_id and not data.invitacion_id):
                raise HTTPException(409, "La coincidencia requiere revision del administrador")
            if not inv.activo or inv.aprobacion in {"RECHAZADO", "REVOCADO"} or inv.rsvp in {"CANCELADO", "RECHAZADO"}:
                raise HTTPException(409, "El administrador debe revisar el estado de la invitacion existente")
            # No sobrescribir contacto, cupos, responsable ni RSVP de una invitacion existente.
        else:
            # Dos correos diferentes con el mismo telefono NO se fusionan. Si ese
            # telefono ya acredito identidad en otro invitado, pedir revision manual.
            if telefono_con_identidad_verificada(db, ctx.evento, contactos, row.telefono):
                raise HTTPException(409, "El telefono coincide con otra identidad verificada; revisa los contactos")
            inv = s.guardar_invitado(db, ctx, InvitadoDatos(nombre=row.nombre, apellido=row.apellido,
                email=row.email_verificado, telefono=row.telefono, whatsapp=row.telefono if row.canal == "whatsapp" else None,
                responsable_id=row.agasajado_id, cantidad_permitida=1))
            inv.usuario_id, inv.canal = row.usuario_id, row.canal
        row.invitacion_id = inv.id
    row.estado, row.revisado_por = data.estado, usuario.id
    s.auditar(db, ctx.evento.id, "solicitud_invitacion_resuelta", usuario.id,
              invitacion_id=row.invitacion_id, solicitud_id=row.id, estado=row.estado,
              revision_confirmada=data.confirmar_revision)
    db.commit()
    return {"estado": row.estado, "invitacion_id": row.invitacion_id}
