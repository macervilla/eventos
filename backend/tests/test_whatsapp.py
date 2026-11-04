import secrets
from urllib.parse import urlsplit, parse_qs

import pytest

from app.services.whatsapp import numero_whatsapp
from tests.test_administracion import auth
from tests.test_invitados import habilitar, crear


@pytest.mark.parametrize("valor", ["02966 15-123456", "+54 9 2966 123456", "5492966123456", "0054 9 2966 123456"])
def test_normalizar_movil_argentino(valor):
    assert numero_whatsapp(valor, "AR", "Argentina") == "5492966123456"


def test_otros_paises_y_region_desconocida():
    assert numero_whatsapp("+34 612 345 678", "AR", "Argentina") == "34612345678"
    assert numero_whatsapp("0612345678", "FR", "Francia") == "33612345678"
    assert numero_whatsapp("02966 15-123456", None, "Argentina") == "5492966123456"
    with pytest.raises(ValueError):
        numero_whatsapp("2966123456", None, None)


@pytest.mark.parametrize("valor", [None, "", "1111", "1234567", "@ana", "+54 9", "12345 ext 2"])
def test_rechazar_contacto_incompleto(valor):
    with pytest.raises(ValueError):
        numero_whatsapp(valor, "AR", "Argentina")


def test_distribucion_whatsapp_no_envia_y_normaliza_sin_modificar_contacto(contexto):
    client, db, _, owner, evento = contexto
    evento.pais, evento.codigo_pais = "Argentina", "AR"
    db.commit()
    habilitar(client, owner)
    inv = crear(client, owner, nombre="Ana", telefono="02966 15-123456")
    r = client.post("/invitados/prueba/distribuir", headers=auth(owner), json={
        "ids": [inv["id"]], "canal": "whatsapp", "idempotencia": secrets.token_urlsafe(24)})
    assert r.status_code == 200, r.text
    resultado = r.json()["resultados"][0]
    assert resultado["estado"] == "PREPARADO"
    assert resultado["telefono_destino"] == "+5492966123456"
    assert resultado["destinatario"] == "Ana"
    url = urlsplit(resultado["url_canal"])
    assert url.netloc == "wa.me" and url.path == "/5492966123456"
    assert resultado["enlace"] in parse_qs(url.query)["text"][0]
    assert "Enviar" in resultado["detalle"]
    assert client.get("/invitados/prueba/lista", headers=auth(owner)).json()["items"][0]["telefono"] == "02966 15-123456"


def test_lote_invalido_no_bloquea_validos_y_whatsapp_tiene_prioridad(contexto):
    client, db, _, owner, evento = contexto
    evento.pais, evento.codigo_pais = "Argentina", "AR"
    db.commit()
    habilitar(client, owner)
    malo = crear(client, owner, nombre="Sin numero")
    bueno = crear(client, owner, nombre="Contacto", telefono="1111", whatsapp="+34 612345678")
    op = {"ids": [malo["id"], bueno["id"]], "canal": "whatsapp", "idempotencia": secrets.token_urlsafe(24)}
    resultados = client.post("/invitados/prueba/distribuir", headers=auth(owner), json=op).json()["resultados"]
    assert resultados[0]["estado"] == "FALLIDO" and "url_canal" not in resultados[0]
    assert resultados[1]["telefono_destino"] == "+34612345678"
    repetido = client.post("/invitados/prueba/distribuir", headers=auth(owner), json=op).json()["resultados"]
    assert all(r["reintento"] for r in repetido)


def test_reenviar_conserva_enlace_personal_y_foto(contexto):
    client, _, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner, nombre="Ana", whatsapp="+5492966123456")
    resultados = []
    for _ in range(2):
        r = client.post("/invitados/prueba/distribuir", headers=auth(owner), json={
            "ids": [inv["id"]], "canal": "whatsapp", "idempotencia": secrets.token_urlsafe(24)})
        assert r.status_code == 200
        resultados.append(r.json()["resultados"][0])
    assert resultados[0]["enlace"] == resultados[1]["enlace"]
    assert resultados[0]["portada_url"] == resultados[1]["portada_url"]
    assert resultados[0]["mensaje"] == resultados[1]["mensaje"]
