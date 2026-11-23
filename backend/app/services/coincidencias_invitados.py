"""Comparaciones conservadoras: un nombre compartido no prueba identidad."""
import re
import unicodedata

from sqlalchemy import select

from app.models.invitaciones import Invitacion, ValidacionInvitado
from app.services.whatsapp import numero_whatsapp


def email_normalizado(valor):
    return re.sub(r"\s+", "", str(valor or "")).casefold()


def nombre_normalizado(valor):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", valor or "")
                            if not unicodedata.combining(c)).casefold().split())


def telefono_normalizado(valor, evento):
    if not (valor or "").strip():
        return None
    try:
        return "+" + numero_whatsapp(valor, evento.codigo_pais, evento.pais)
    except ValueError:
        return None  # Nunca tomar un numero incompleto como identidad coincidente.


def buscar(db, evento, nombre, apellido, email=None, telefono=None, excluir=None):
    correo = email_normalizado(email)
    numero = telefono_normalizado(telefono, evento)
    identidad, contacto, nombres = [], [], []
    for inv in db.scalars(select(Invitacion).where(Invitacion.evento_id == evento.id)):
        if inv.id == excluir:
            continue
        if correo and email_normalizado(inv.email) == correo:
            identidad.append(inv)
        if numero and numero in {telefono_normalizado(inv.telefono, evento), telefono_normalizado(inv.whatsapp, evento)}:
            contacto.append(inv)
        if (nombre_normalizado(inv.nombre), nombre_normalizado(inv.apellido)) == (nombre_normalizado(nombre), nombre_normalizado(apellido)):
            nombres.append(inv)
    return identidad, contacto, nombres


def telefono_con_identidad_verificada(db, evento, contactos, numero):
    if not numero or not contactos:
        return False
    return any(telefono_normalizado(v.email, evento) == numero for v in db.scalars(
        select(ValidacionInvitado).where(ValidacionInvitado.invitacion_id.in_([i.id for i in contactos]),
            ValidacionInvitado.metodo == "telefono", ValidacionInvitado.usado.is_(True))))
