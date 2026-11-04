import io
import secrets
import zipfile
from datetime import timedelta

from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from pydantic import ValidationError
from sqlalchemy import select

from app.models.eventos import EventoUsuario
from app.models.invitaciones import ImportacionInvitados, Invitacion
from app.models.usuarios import User
from app.schemas.invitados import InvitadoDatos
from app.services.invitados import (
    ahora,
    auditar,
    clave_duplicado,
    guardar_invitado,
    normalizar,
    utc,
)

COLUMNAS = ["Nombre", "Apellido", "Email", "Telefono", "Instagram", "Grupo", "Responsable", "Cupos", "WhatsApp", "Facebook", "Telegram", "Otro contacto"]


def excel(filas, columnas=COLUMNAS):
    wb = Workbook()
    hoja = wb.active
    hoja.title = "Invitados"
    hoja.append(columnas)
    for fila in filas:
        hoja.append(
            [
                ("'" + v if v[:1] in {"=", "+", "-", "@"} else v) if isinstance(v, str) else v
                for v in fila
            ]
        )
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions
    for col in hoja.columns:
        hoja.column_dimensions[col[0].column_letter].width = 24
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def preview(db, ctx, contenido, actualizar=False):
    if len(contenido) > 5 * 1024 * 1024:
        raise HTTPException(413, "El Excel supera 5 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            if (
                sum(info.file_size for info in z.infolist()) > 20 * 1024 * 1024
                or len(z.infolist()) > 1000
            ):
                raise HTTPException(413, "Excel demasiado grande al descomprimir")
        wb = load_workbook(io.BytesIO(contenido), read_only=True, data_only=False, keep_links=False)
        hoja = wb.active
        if hoja.max_row > 1001 or hoja.max_column > 20:
            raise HTTPException(413, "La importacion admite hasta 1000 filas y 20 columnas")
        filas = hoja.iter_rows()
        titulos = [normalizar(c.value or "") for c in next(filas)]
        if "nombre" not in titulos or len(set(titulos)) != len(titulos):
            raise HTTPException(422, "Se requiere la columna Nombre y encabezados sin duplicados")
        desconocidas = [t for t in titulos if t not in [normalizar(c) for c in COLUMNAS] and t]
        if desconocidas:
            raise HTTPException(422, "Columnas no reconocidas: " + ", ".join(desconocidas))
        resultado, vistos = [], set()
        for numero, celdas in enumerate(filas, 2):
            valores = {k: c.value for k, c in zip(titulos, celdas) if k}
            if not any(v is not None and str(v).strip() for v in valores.values()):
                continue
            # Deshacer el escape de la exportacion propia sin ejecutar formulas.
            valores = {k: v[1:] if isinstance(v, str) and len(v) > 1 and v[0] == "'" and v[1] in "=+-@" else v for k, v in valores.items()}
            registro = {"fila": numero, "error": None}
            try:
                if any(c.data_type == "f" for c in celdas):
                    raise ValueError("No se admiten formulas")
                responsable = None
                if valores.get("responsable"):
                    responsable = db.scalar(
                        select(User).where(
                            User.email == str(valores["responsable"]).strip().lower(),
                            User.activo.is_(True),
                        )
                    )
                    if not responsable:
                        raise ValueError(
                            "Responsable no disponible para este evento; usar su email asignado"
                        )
                    if responsable.id not in {
                        ctx.usuario.id,
                        ctx.evento.propietario_id,
                    } and not db.scalar(
                        select(EventoUsuario.id).where(
                            EventoUsuario.evento_id == ctx.evento.id,
                            EventoUsuario.usuario_id == responsable.id,
                        )
                    ):
                        raise ValueError(
                            "Responsable no disponible para este evento; usar su email asignado"
                        )
                data = InvitadoDatos(
                    nombre=str(valores.get("nombre") or ""),
                    apellido=str(valores.get("apellido") or ""),
                    email=valores.get("email") or None,
                    telefono=str(valores["telefono"]) if valores.get("telefono") else None,
                    instagram=valores.get("instagram") or None,
                    whatsapp=str(valores["whatsapp"]) if valores.get("whatsapp") else None,
                    facebook=valores.get("facebook") or None,
                    telegram=valores.get("telegram") or None,
                    otro_contacto=valores.get("otro contacto") or None,
                    grupo=valores.get("grupo") or None,
                    responsable_id=responsable.id if responsable else ctx.usuario.id,
                    cantidad_permitida=valores.get("cupos") or 1,
                )
                key = clave_duplicado(data)
                if key in vistos:
                    raise ValueError("Duplicado dentro del archivo")
                vistos.add(key)
                existente = db.scalar(
                    select(Invitacion).where(
                        Invitacion.evento_id == ctx.evento.id, Invitacion.clave_duplicado == key
                    )
                )
                if existente and ctx.propio and existente.responsable_id != ctx.usuario.id:
                    raise ValueError("Duplicado en otra lista del evento")
                if ctx.propio and data.responsable_id != ctx.usuario.id:
                    raise ValueError("Responsable fuera de tu lista")
                registro.update(
                    contactos_presentes=[c for c in ("whatsapp", "facebook", "telegram", "otro_contacto") if c.replace("_", " ") in valores],
                    responsable_explicito=bool(valores.get("responsable")),
                    datos=data.model_dump(mode="json"),
                    existente_id=existente.id if existente else None,
                    accion="actualizar"
                    if existente and actualizar
                    else "omitir"
                    if existente
                    else "crear",
                )
            except (ValueError, ValidationError) as exc:
                registro["error"] = "Datos invalidos: " + str(exc).split("\n")[0][:160]
            resultado.append(registro)
        wb.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "Archivo XLSX invalido") from exc
    batch = ImportacionInvitados(
        evento_id=ctx.evento.id,
        actor_id=ctx.usuario.id,
        token=secrets.token_urlsafe(24),
        filas=resultado,
        actualizar=actualizar,
        vence_at=ahora() + timedelta(minutes=30),
    )
    db.add(batch)
    db.commit()
    return {"token": batch.token, "filas": resultado}


def importar(db, ctx, token):
    batch = db.scalar(
        select(ImportacionInvitados)
        .where(
            ImportacionInvitados.token == token,
            ImportacionInvitados.evento_id == ctx.evento.id,
            ImportacionInvitados.actor_id == ctx.usuario.id,
        )
        .with_for_update()
    )
    if batch is None or utc(batch.vence_at) < ahora():
        raise HTTPException(404, "Vista previa vencida o no disponible")
    if batch.resultado is not None:
        return batch.resultado
    # Serializa importaciones de un mismo evento, incluso por responsables diferentes.
    from app.models.eventos import Evento

    db.scalar(select(Evento).where(Evento.id == ctx.evento.id).with_for_update())
    informe = {"importados": 0, "actualizados": 0, "omitidos": 0, "rechazados": []}
    for fila in batch.filas:
        if fila.get("error"):
            informe["rechazados"].append({"fila": fila["fila"], "error": fila["error"]})
            continue
        try:
            with db.begin_nested():
                data = InvitadoDatos(**fila["datos"])
                existente = db.scalar(
                    select(Invitacion).where(
                        Invitacion.evento_id == ctx.evento.id,
                        Invitacion.clave_duplicado == clave_duplicado(data),
                    )
                )
                if existente and (not batch.actualizar or not existente.activo):
                    informe["omitidos"] += 1
                    continue
                if existente:
                    for campo in ("whatsapp", "facebook", "telegram", "otro_contacto"):
                        if campo not in fila.get("contactos_presentes", []):
                            setattr(data, campo, getattr(existente, campo))
                    if not fila.get("responsable_explicito"):
                        data.responsable_id = existente.responsable_id
                    # Contactos/grupo se actualizan, pero nunca se reducen cupos ni se borran RSVP.
                    data.cantidad_permitida = max(
                        data.cantidad_permitida, existente.cantidad_permitida
                    )
                guardar_invitado(db, ctx, data, existente)
                informe["actualizados" if existente else "importados"] += 1
        except Exception:
            informe["rechazados"].append(
                {
                    "fila": fila["fila"],
                    "error": "No se pudo importar por validacion, permisos o duplicado",
                }
            )
    batch.resultado = informe
    auditar(db, ctx.evento.id, "importacion", ctx.usuario.id, filas=len(batch.filas))
    db.commit()
    return informe
