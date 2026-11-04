"""Telefonos internacionales para enlaces click-to-chat, sin enviar mensajes."""
import re

import phonenumbers


def numero_whatsapp(valor: str | None, codigo_pais: str | None, pais: str | None) -> str:
    texto = (valor or "").strip()
    if not texto or not re.fullmatch(r"\+?[0-9\s().-]+", texto):
        raise ValueError("Completa el numero de WhatsApp con codigo de pais y area.")
    region = (codigo_pais or "").upper() or None
    if not region and (pais or "").strip().casefold() == "argentina":
        region = "AR"
    digitos = re.sub(r"[^0-9]", "", texto)
    if texto.startswith("00"):
        texto = "+" + digitos[2:]
    elif not texto.startswith("+") and region == "AR" and digitos.startswith("54") and len(digitos) in (12, 13):
        texto = "+" + digitos
    try:
        numero = phonenumbers.parse(texto, region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Revisa el numero de WhatsApp. Usa formato internacional, por ejemplo +54 9 2966 123456.") from exc
    if phonenumbers.is_possible_number_with_reason(numero) != phonenumbers.ValidationResult.IS_POSSIBLE:
        raise ValueError("El numero de WhatsApp esta incompleto o tiene una longitud incorrecta. Inclui codigo de pais y area.")
    # La biblioteca convierte 0 + area + 15 + abonado al movil +54 9.
    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164).removeprefix("+")
