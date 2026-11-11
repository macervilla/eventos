import io
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.core.config import settings
from app.services import verificacion_telefono as proveedor


def configurar(monkeypatch):
    monkeypatch.setattr(settings, "twilio_account_sid", "AC" + "1" * 32)
    monkeypatch.setattr(settings, "twilio_verify_service_sid", "VA" + "2" * 32)
    monkeypatch.setattr(settings, "twilio_auth_token", SecretStr("secreto-prueba"))


def test_proveedor_no_configurado_falla_cerrado(monkeypatch):
    monkeypatch.setattr(settings, "twilio_account_sid", None)
    monkeypatch.setattr(proveedor, "urlopen", lambda *args, **kwargs: pytest.fail("No debe consultar la red"))
    with pytest.raises(HTTPException) as error:
        proveedor.enviar("+5492966123456")
    assert error.value.status_code == 503


def test_api_oficial_validacion_y_no_simula_aprobacion(monkeypatch):
    configurar(monkeypatch)
    peticiones = []
    referencia = "VE" + "3" * 32
    def responder(request, timeout):
        peticiones.append(request)
        return io.StringIO(json.dumps({"sid":referencia,
            "status":"approved" if request.full_url.endswith("VerificationCheck") else "pending"}))
    monkeypatch.setattr(proveedor, "urlopen", responder)
    assert proveedor.enviar("+5492966123456") == referencia
    assert proveedor.comprobar(referencia,"123456")
    assert peticiones[0].full_url == f"https://verify.twilio.com/v2/Services/{settings.twilio_verify_service_sid}/Verifications"
    assert parse_qs(peticiones[0].data.decode()) == {"To":["+5492966123456"],"Channel":["sms"]}
    assert parse_qs(peticiones[1].data.decode()) == {"VerificationSid":[referencia],"Code":["123456"]}
    monkeypatch.setattr(proveedor, "_peticion", lambda *args: {"sid":referencia,"status":"pending"})
    assert not proveedor.comprobar(referencia,"000000")


def test_error_externo_no_revela_credenciales(monkeypatch):
    configurar(monkeypatch)
    def fallar(*args, **kwargs):
        raise HTTPError("https://verify.twilio.com", 503, "secreto-prueba", {}, None)
    monkeypatch.setattr(proveedor, "urlopen", fallar)
    with pytest.raises(HTTPException) as error:
        proveedor.enviar("+5492966123456")
    assert error.value.status_code == 503
    assert "secreto-prueba" not in str(error.value.detail)
