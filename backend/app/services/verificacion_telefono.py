"""Twilio Verify. No simula codigos ni acepta un telefono declarado por el visitante."""
import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.core.config import settings


def _peticion(recurso, datos):
    cuenta = settings.twilio_account_sid or ""
    servicio = settings.twilio_verify_service_sid or ""
    if (not re.fullmatch(r"AC[0-9a-fA-F]{32}", cuenta)
            or not re.fullmatch(r"VA[0-9a-fA-F]{32}", servicio) or not settings.twilio_auth_token):
        raise HTTPException(503, "Proveedor telefonico oficial no configurado; contacta al organizador")
    credencial = base64.b64encode(f"{cuenta}:{settings.twilio_auth_token.get_secret_value()}".encode()).decode()
    peticion = Request(f"https://verify.twilio.com/v2/Services/{servicio}/{recurso}",
        data=urlencode(datos).encode(), headers={"Authorization": "Basic " + credencial,
            "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urlopen(peticion, timeout=15) as respuesta:
            return json.load(respuesta)
    except HTTPError as exc:
        if exc.code in (400, 404):
            raise HTTPException(401, "Codigo o solicitud telefonica invalida o vencida") from None
        raise HTTPException(503, "El proveedor telefonico no confirmo la operacion") from None
    except (URLError, OSError, ValueError):
        raise HTTPException(503, "No se pudo consultar el proveedor telefonico") from None


def enviar(telefono):
    respuesta = _peticion("Verifications", {"To": telefono, "Channel": "sms"})
    sid = respuesta.get("sid", "")
    if respuesta.get("status") != "pending" or not re.fullmatch(r"VE[0-9a-fA-F]{32}", sid):
        raise HTTPException(503, "El proveedor telefonico no acepto el envio del codigo")
    return sid


def comprobar(referencia, codigo):
    respuesta = _peticion("VerificationCheck", {"VerificationSid": referencia, "Code": codigo})
    return respuesta.get("status") == "approved" and respuesta.get("sid") == referencia
