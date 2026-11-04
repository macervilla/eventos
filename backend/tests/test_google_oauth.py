import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from google.auth import crypt, jwt
from google.auth.exceptions import TransportError
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.main import app
from app.services.acceso import _motivo_rechazo_google, get_verified_google_email

pytest_plugins = ["tests.test_administracion"]

CLIENT_ID = "test-eventos.apps.googleusercontent.com"


@pytest.fixture(scope="module")
def claves():
    # Claves efimeras de pruebas. Nunca son credenciales de Google ni del proyecto.
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    public = private.public_key().public_bytes(serialization.Encoding.PEM,
                                              serialization.PublicFormat.SubjectPublicKeyInfo)
    return crypt.RSASigner.from_string(pem, key_id="test-key"), public


@pytest.fixture()
def google(monkeypatch, claves):
    signer, public = claves
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "google_clock_skew_seconds", 5)
    # Solo sustituimos la descarga de certificados; firma y claims se validan realmente.
    monkeypatch.setattr("google.oauth2.id_token._fetch_certs", lambda *args, **kwargs: {"test-key": public})

    def firmar(**cambios):
        now = int(time.time())
        claims = {"iss": "https://accounts.google.com", "aud": CLIENT_ID,
                  "sub": "google-test-user", "iat": now - 10, "exp": now + 300,
                  "email": "macervilla1@gmail.com", "email_verified": True}
        claims.update(cambios)
        if "sub" not in cambios:
            claims["sub"] = "google-" + claims["email"]
        if "hd" not in cambios and claims.get("email", "").endswith("@example.com"):
            claims["hd"] = "example.com"  # Dominio de Workspace utilizado por las pruebas.
        claims = {key: value for key, value in claims.items() if value is not None}
        return jwt.encode(signer, claims).decode()
    return firmar


def test_token_firmado_valido(google):
    assert get_verified_google_email(google()) == "macervilla1@gmail.com"


def test_desfase_pequeno_de_relojes(google):
    assert get_verified_google_email(google(iat=int(time.time()) + 3)) == "macervilla1@gmail.com"


def test_rechaza_desfase_grande(google):
    with pytest.raises(HTTPException) as exc:
        get_verified_google_email(google(iat=int(time.time()) + 60))
    assert exc.value.status_code == 401


@pytest.mark.parametrize("cambios", [
    {"aud": "otro-proyecto.apps.googleusercontent.com"},
    {"iss": "https://atacante.example"},
    {"iat": int(time.time()) - 3600, "exp": int(time.time()) - 60},
    {"iat": int(time.time()) + 3600},
    {"email_verified": False}, {"email_verified": "true"},
    {"email": ""}, {"sub": ""},
    {"aud": None}, {"iss": None}, {"exp": None}, {"iat": None},
])
def test_rechaza_claims_invalidos(google, cambios):
    with pytest.raises(HTTPException) as exc:
        get_verified_google_email(google(**cambios))
    assert exc.value.status_code == 401


def test_rechaza_firma_adulterada_y_access_tokens(google):
    token = google()
    header, payload, signature = token.split(".")
    adulterada = ("A" if signature[0] != "A" else "B") + signature[1:]
    for invalido in [f"{header}.{payload}.{adulterada}", "access-token-sin-jwt"]:
        with pytest.raises(HTTPException) as exc:
            get_verified_google_email(invalido)
        assert exc.value.status_code == 401


def test_google_no_disponible(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    def fallar(*args, **kwargs):
        raise TransportError("error de red")
    monkeypatch.setattr("google.oauth2.id_token._fetch_certs", fallar)
    with pytest.raises(HTTPException) as exc:
        get_verified_google_email("cualquier-token")
    assert exc.value.status_code == 503


def test_diagnostico_no_registra_credenciales(google, caplog):
    token = google(aud="otro-cliente")
    with pytest.raises(HTTPException):
        get_verified_google_email(token)
    assert "audiencia_incorrecta" in caplog.text
    assert token not in caplog.text
    assert "macervilla1@gmail.com" not in caplog.text
    assert _motivo_rechazo_google(ValueError("Token used too early")) == "reloj_desfasado"


def test_configuracion_propia(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", f"  {CLIENT_ID}  ")
    monkeypatch.setenv("VITE_GOOGLE_CLIENT_ID", "obsoleto.apps.googleusercontent.com")
    assert Settings(_env_file=None).google_client_id == CLIENT_ID
    with TestClient(app) as client:
        monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
        respuesta = client.get("/acceso/google-config")
        assert respuesta.json() == {"client_id": CLIENT_ID}
        assert respuesta.headers["Cache-Control"] == "no-store"
        monkeypatch.setattr(settings, "google_client_id", None)
        assert client.get("/acceso/google-config").json() == {"client_id": None}
    monkeypatch.setenv("GOOGLE_CLIENT_ID", " ")
    assert Settings(_env_file=None).google_client_id is None
    with pytest.raises(HTTPException) as exc:
        get_verified_google_email("token")
    assert exc.value.status_code == 503


def test_tolerancia_acotada():
    for valor in [-1, 31]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, GOOGLE_CLOCK_SKEW_SECONDS=valor)


def test_login_google_hasta_dashboard(contexto, google):
    client, db, admin, usuario, _ = contexto
    respuesta = client.post("/acceso/google", json={"credential": google(email=admin.email, hd="example.com")})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["opciones"][0]["path"] == "/administracion"
    assert client.get("/administracion/resumen", headers={"Authorization": f"Bearer {datos['token']}"}).status_code == 200
    assert client.post("/acceso/google", json={"credential": google(aud="otro-cliente")}).status_code == 401
    assert client.post("/acceso/google", json={"access_token": "flujo-antiguo"}).status_code == 422
    assert client.post("/acceso/google", json={"credential": ""}).status_code == 422
    # Un '_' en un email es literal, no un comodin SQL para otra cuenta.
    visitante = client.post("/acceso/google", json={"credential": google(email="admi_@example.com")}).json()
    assert visitante["opciones"] == []
    assert client.get("/administracion/resumen", headers={"Authorization": f"Bearer {visitante['token']}"}).status_code == 403
    usuario.activo = False
    db.commit()
    assert client.post("/acceso/google", json={"credential": google(email=usuario.email)}).json()["token"] is None
