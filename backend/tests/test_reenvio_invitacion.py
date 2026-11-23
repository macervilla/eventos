"""El reenvio renueva el enlace y conserva la invitacion y su identidad."""
import secrets

import pytest
from sqlalchemy import select

from app.models.invitaciones import Invitacion
from tests.test_invitados import auth, crear, habilitar


@pytest.mark.parametrize("canal", ["whatsapp", "email"])
def test_reenvio_renueva_enlace_conserva_confirmacion_y_exige_cuenta(contexto, monkeypatch, canal):
    client, db, ajeno, titular, _ = contexto
    habilitar(client, titular)
    monkeypatch.setattr("app.services.invitados_distribucion._send_email", lambda *a, **kw: None)
    monkeypatch.setattr("app.services.invitados_notificaciones._send_email", lambda *a, **kw: None)
    invitada = crear(client, titular, nombre="Liliana", apellido="Ramirez", email=titular.email,
                     whatsapp="+5492966123456", cantidad_permitida=3)
    base = "/invitados/prueba"

    def enviar(clave):
        respuesta = client.post(base + "/distribuir", headers=auth(titular), json={
            "ids": [invitada["id"]], "canal": canal, "tipo": "invitacion", "idempotencia": clave,
        })
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.json()["resultados"][0]

    primero = enviar(secrets.token_urlsafe(24))
    token_anterior = primero["enlace"].split("/i/")[1].split("#")[0]
    confirmada = client.post(base + "/portal/confirmar", headers=auth(titular), json={
        "token": token_anterior, "personas": [{"nombre": "Liliana", "apellido": "Ramirez", "tipo": "ADULTO"}],
    })
    assert confirmada.status_code == 200, confirmada.text
    qr = confirmada.json()["qr"]
    sesion_anterior = confirmada.json()["sesion"]
    fila = db.scalar(select(Invitacion).where(Invitacion.id == invitada["id"]))
    db.refresh(fila)
    anterior = (fila.rsvp, fila.aprobacion, fila.cantidad_permitida, fila.cupo_aprobado,
                fila.ingresados, fila.usuario_id, fila.confirmado_at)
    clave = secrets.token_urlsafe(24)
    segundo = enviar(clave)
    token_nuevo = segundo["enlace"].split("/i/")[1].split("#")[0]
    assert token_nuevo != token_anterior
    db.refresh(fila)
    assert anterior == (fila.rsvp, fila.aprobacion, fila.cantidad_permitida, fila.cupo_aprobado,
                        fila.ingresados, fila.usuario_id, fila.confirmado_at)
    assert client.post(base + "/portal", headers=auth(titular), json={"token": token_anterior}).status_code == 404
    # Una sesion anterior no reemplaza el nuevo ingreso Google.
    assert not client.post(base + "/portal", json={"token": token_nuevo, "sesion": sesion_anterior}).json()["validado"]
    assert not client.post(base + "/portal", headers=auth(ajeno), json={"token": token_nuevo}).json()["validado"]
    vista = client.post(base + "/portal", headers=auth(titular), json={"token": token_nuevo}).json()
    assert vista["validado"] and vista["qr"] == qr and vista["cupo_aprobado"] == 1
    # Repetir la misma operacion por una falla de red no invalida su propio enlace.
    assert enviar(clave)["reintento"]
    assert client.post(base + "/portal", headers=auth(titular), json={"token": token_nuevo}).json()["qr"] == qr
