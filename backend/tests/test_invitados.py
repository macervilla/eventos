import io
import secrets
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from tests.autenticacion import token_google
from app.models.enums import EventoEstado, RolEvento
from app.models.eventos import Evento, EventoUsuario
from app.models.invitaciones import (
    CredencialInvitacion,
    Invitacion,
    MovimientoIngreso,
    SolicitudRSVP,
    ValidacionInvitado,
)
from app.models.usuarios import User
from app.services.invitados import ahora, digest
from app.services.invitados_excel import excel

pytest_plugins = ["tests.test_administracion"]


def test_sesion_del_correo_autorizado_confirma_sin_otp(contexto, monkeypatch):
    client, db, admin, owner, _ = contexto
    habilitar(client, owner, requiere_login=True, validacion="email", aprobacion="automatica")
    inv = crear(client, owner, email=owner.email.upper())
    token = enlace(client, owner, inv)
    ruta = "/invitados/prueba/portal"
    assert not client.post(ruta, json={"token": token}).json()["validado"]
    assert not client.post(ruta, headers=auth(admin), json={"token": token}).json()["validado"]
    assert client.post(ruta, headers=auth(owner), json={"token": token}).json()["validado"]
    envios = []
    monkeypatch.setattr("app.services.invitados_notificaciones._send_email", lambda *a, **kw: envios.append((a, kw)))
    datos = {"token": token, "rsvp": {"asiste": True, "adultos": 2}}
    assert client.post(ruta + "/rsvp", headers=auth(admin), json=datos).status_code == 401
    respuesta = client.post(ruta + "/rsvp", headers=auth(owner), json=datos)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["correo_qr"] == "enviado"
    assert len(envios) == 1 and envios[0][1]["attachment"].startswith(b"\x89PNG")
    assert client.post(ruta + "/rsvp", headers=auth(owner), json=datos).status_code == 200
    assert len(envios) == 1
    assert db.scalar(select(func.count()).select_from(ValidacionInvitado)) == 0
    assert client.post(ruta + "/qr.png", headers=auth(owner), json={"token": token}).status_code == 200


def test_qr_se_envia_al_aprobar_y_fallo_no_deshace_confirmacion(contexto, monkeypatch):
    client, _, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner, email="invitado@example.com")
    token = enlace(client, owner, inv)
    envios = []
    def enviar(*a, **kw):
        envios.append(kw["attachment"])
        if len(envios) == 1:
            raise RuntimeError("SMTP no disponible")
    monkeypatch.setattr("app.services.invitados_notificaciones._send_email", enviar)
    assert confirmar(client, token).json()["correo_qr"] == "pendiente_aprobacion"
    assert not envios
    respuesta = aprobar(client, owner, inv, 2)
    assert respuesta.status_code == 200
    assert respuesta.json()["aprobacion"] == "APROBADO"
    assert respuesta.json()["correo_qr"] == "fallido"
    assert aprobar(client, owner, inv, 2).json()["correo_qr"] == "enviado"
    assert aprobar(client, owner, inv, 2).json()["correo_qr"] == "enviado"
    assert len(envios) == 2


def auth(u):
    return {"Authorization": "Bearer " + token_google(u)}


def habilitar(client, owner, **datos):
    r = client.put(
        "/invitados/prueba/config",
        headers=auth(owner),
        json={"activo": True, "requiere_login": False, **datos},
    )
    assert r.status_code == 200, r.text


def crear(client, owner, **datos):
    r = client.post(
        "/invitados/prueba/lista",
        headers=auth(owner),
        json={"nombre": "Familia", "cantidad_permitida": 4, **datos},
    )
    assert r.status_code == 201, r.text
    return r.json()


def enlace(client, owner, inv):
    r = client.post(
        f"/invitados/prueba/lista/{inv['id']}/credencial/enlace/emitir", headers=auth(owner)
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def confirmar(client, token, adultos=2, menores=None, sesion=None):
    return client.post(
        "/invitados/prueba/portal/rsvp",
        json={
            "token": token,
            "sesion": sesion,
            "rsvp": {"asiste": True, "adultos": adultos, "menores": menores or []},
        },
    )


def aprobar(client, owner, inv, cupo=3):
    return client.post(
        f"/invitados/prueba/lista/{inv['id']}/aprobar",
        headers=auth(owner),
        json={"estado": "APROBADO", "cupo": cupo},
    )


def test_flujo_rsvp_aprobacion_qr_ingresos(contexto):
    client, db, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    assert len(token) >= 40 and token not in inv.values()
    c = db.scalar(select(CredencialInvitacion).where(CredencialInvitacion.tipo == "enlace"))
    assert c.token_hash == digest(token) and c.token_cifrado != token
    inicial = client.post("/invitados/prueba/portal", json={"token": token}).json()
    assert inicial["qr"] is None
    assert confirmar(client, token, 4, ["Sofia"]).status_code == 409
    assert confirmar(client, token, 2, ["Sofia"]).status_code == 200
    assert confirmar(client, token, 2, ["Sofia"]).status_code == 200
    assert db.scalar(select(func.count()).select_from(SolicitudRSVP)) == 1
    r = client.post("/invitados/prueba/portal", json={"token": token}).json()
    assert (
        r["solicitados"] == 3
        and r["cantidad_permitida"] == 4
        and r["cupo_aprobado"] == 0
        and r["qr"] is None
    )
    assert aprobar(client, owner, inv, 4).status_code == 409
    assert aprobar(client, owner, inv).status_code == 200
    r = client.post("/invitados/prueba/portal", json={"token": token}).json()
    qr = r["qr"]
    assert qr and "Familia" not in qr and "Sofia" not in qr
    assert client.post("/invitados/prueba/portal/qr.png", json={"token": token}).content.startswith(
        b"\x89PNG"
    )
    dato = {"token": qr, "cantidad": 2, "idempotencia": secrets.token_urlsafe(24)}
    entrada = client.post("/invitados/prueba/control/ingreso", headers=auth(owner), json=dato)
    assert entrada.status_code == 200 and entrada.json()["restantes"] == 1
    assert (
        client.post("/invitados/prueba/control/ingreso", headers=auth(owner), json=dato).json()[
            "ingresados"
        ]
        == 2
    )
    assert db.scalar(select(func.count()).select_from(MovimientoIngreso)) == 1
    assert (
        client.post(
            "/invitados/prueba/control/ingreso",
            headers=auth(owner),
            json={**dato, "idempotencia": secrets.token_urlsafe(24)},
        ).status_code
        == 409
    )
    dato.update(cantidad=1, idempotencia=secrets.token_urlsafe(24))
    assert (
        client.post("/invitados/prueba/control/ingreso", headers=auth(owner), json=dato).json()[
            "estado_ingreso"
        ]
        == "COMPLETO"
    )
    assert (
        client.post(
            "/invitados/prueba/control/ingreso",
            headers=auth(owner),
            json={**dato, "idempotencia": secrets.token_urlsafe(24)},
        ).status_code
        == 409
    )
    stats = client.get("/invitados/prueba/estadisticas", headers=auth(owner)).json()
    assert stats["ingresados"] == 3 and stats["restantes"] == 0


def test_roles_scopes_aislamiento_y_revocacion(contexto):
    client, db, _, owner, _ = contexto
    habilitar(client, owner)
    gestor = User(email="gestor@example.com")
    puerta = User(email="puerta@example.com")
    db.add_all([gestor, puerta])
    db.commit()
    r = client.post(
        "/invitados/prueba/roles",
        headers=auth(owner),
        json={
            "email": gestor.email,
            "rol": "AGASAJADO",
            "permisos": ["ver_invitados", "editar_invitados", "importar", "estadisticas"],
            "solo_responsable": True,
        },
    )
    asignacion = r.json()["id"]
    assert (
        client.post(
            "/invitados/prueba/roles",
            headers=auth(owner),
            json={"email": puerta.email, "rol": "CONTROL_INGRESO"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/invitados/prueba/roles",
            headers=auth(owner),
            json={"email": puerta.email, "rol": "CONTROL_INGRESO", "permisos": ["aprobar"]},
        ).status_code
        == 422
    )
    inv = crear(client, owner)
    assert client.get("/invitados/prueba/lista", headers=auth(gestor)).json()["total"] == 0
    assert (
        client.post(
            f"/invitados/prueba/lista/{inv['id']}/aprobar",
            headers=auth(puerta),
            json={"estado": "APROBADO", "cupo": 1},
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/invitados/prueba/config", headers=auth(gestor), json={"activo": False}
        ).status_code
        == 403
    )
    assert not client.get("/eventos/prueba/permisos", headers=auth(gestor)).json()["puede_editar"]
    propio = crear(client, gestor, nombre="Propio")
    assert propio["responsable_id"] == gestor.id
    assert client.get("/invitados/prueba/lista", headers=auth(gestor)).json()["total"] == 1
    assert (
        client.get(f"/invitados/prueba/historial/{inv['id']}", headers=auth(gestor)).status_code
        == 404
    )
    assert (
        client.get("/invitados/prueba/lista", headers=auth(puerta))
        .json()["items"][0]
        .get("nombres_menores")
        is None
    )
    db.add(
        Evento(nombre="Otro", slug="otro", propietario_id=owner.id, estado=EventoEstado.PUBLICADO)
    )
    db.commit()
    assert client.get("/invitados/otro/lista", headers=auth(gestor)).status_code == 403
    client.post(f"/invitados/prueba/roles/{asignacion}/revocar", headers=auth(owner))
    assert client.get("/invitados/prueba/lista", headers=auth(gestor)).status_code == 403


def test_modificacion_qr_revocado_y_enlace_rotado(contexto):
    client, db, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    confirmar(client, token, 2)
    aprobar(client, owner, inv, 2)
    portal = client.post("/invitados/prueba/portal", json={"token": token}).json()
    qr, sesion = portal["qr"], portal["sesion"]
    assert confirmar(client, token, 3).json()["aprobacion"] == "PENDIENTE"
    assert (
        client.post(
            "/invitados/prueba/control/consultar", headers=auth(owner), json={"token": qr}
        ).status_code
        == 404
    )
    renovar = client.post(
        f"/invitados/prueba/lista/{inv['id']}/credencial/enlace/regenerar", headers=auth(owner)
    ).json()["token"]
    assert renovar != token
    assert (
        client.post("/invitados/prueba/portal", json={"token": token, "sesion": sesion}).status_code
        == 404
    )
    assert client.post("/invitados/otro/portal", json={"token": renovar}).status_code == 404
    assert (
        client.post(
            "/invitados/prueba/portal", json={"token": secrets.token_urlsafe(32)}
        ).status_code
        == 404
    )


def test_otp_real_no_simulado_intentos_y_uso_unico(contexto, monkeypatch):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, validacion="email", otp_intentos=2)
    inv = crear(client, owner, email="titular@example.com")
    token = enlace(client, owner, inv)
    assert not client.post("/invitados/prueba/portal", json={"token": token}).json()["validado"]
    assert confirmar(client, token).status_code == 401
    capturados = []
    monkeypatch.setattr(
        "app.services.invitados_portal._send_email", lambda *args: capturados.append(args)
    )
    assert (
        client.post(
            "/invitados/prueba/portal/codigo", json={"token": token, "email": "otra@example.com"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/invitados/prueba/portal/codigo", json={"token": token, "email": "titular@example.com"}
        ).status_code
        == 200
    )
    codigo = capturados[0][3].split(": ")[1]
    assert codigo not in client.post("/invitados/prueba/portal", json={"token": token}).text
    assert (
        client.post(
            "/invitados/prueba/portal/validar", json={"token": token, "codigo": "xxxxxx"}
        ).status_code
        == 401
    )
    r = client.post("/invitados/prueba/portal/validar", json={"token": token, "codigo": codigo})
    assert r.status_code == 200 and r.json()["validado"]
    assert confirmar(client, token, sesion=r.json()["sesion"]).status_code == 200
    assert (
        client.post(
            "/invitados/prueba/portal/validar", json={"token": token, "codigo": codigo}
        ).status_code
        == 401
    )


def test_importacion_preview_idempotencia_exportacion(contexto):
    client, db, _, owner, _ = contexto
    habilitar(client, owner)
    archivo = excel(
        [
            ["Ana", "Perez", None, None, None, "Familia", None, 4],
            ["Ana", "Perez", None, None, None, "Familia", None, 4],
            ["Mal", "", "correo invalido", None, None, None, None, 1],
        ]
    )
    r = client.post(
        "/invitados/prueba/importar/preview",
        headers=auth(owner),
        files={"file": ("invitados.xlsx", archivo)},
    )
    assert r.status_code == 200, r.text
    assert db.scalar(select(func.count()).select_from(Invitacion)) == 0
    token = r.json()["token"]
    resultado = client.post("/invitados/prueba/importar/" + token, headers=auth(owner)).json()
    assert resultado["importados"] == 1 and len(resultado["rechazados"]) == 2
    assert (
        client.post("/invitados/prueba/importar/" + token, headers=auth(owner)).json() == resultado
    )
    token2 = client.post(
        "/invitados/prueba/importar/preview",
        headers=auth(owner),
        files={"file": ("invitados.xlsx", archivo)},
    ).json()["token"]
    assert (
        client.post("/invitados/prueba/importar/" + token2, headers=auth(owner)).json()["omitidos"]
        == 1
    )
    assert db.scalar(select(func.count()).select_from(Invitacion)) == 1
    assert client.get("/invitados/prueba/exportar.xlsx", headers=auth(owner)).content.startswith(
        b"PK"
    )
    assert client.get("/invitados/prueba/plantilla.xlsx", headers=auth(owner)).content.startswith(
        b"PK"
    )


def test_distribucion_smtp_y_canales_manuales(contexto, monkeypatch):
    client, _, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner, email="ana@example.com", whatsapp="+5492966123456")
    datos = {"ids": [inv["id"]], "canal": "whatsapp", "idempotencia": secrets.token_urlsafe(24)}
    resultado = client.post("/invitados/prueba/distribuir", headers=auth(owner), json=datos).json()[
        "resultados"
    ][0]
    assert resultado["estado"] == "PREPARADO" and "wa.me" in resultado["url_canal"]
    envios = []
    monkeypatch.setattr(
        "app.services.invitados_distribucion._send_email", lambda *args, **kw: envios.append(args)
    )
    datos.update(canal="email", idempotencia=secrets.token_urlsafe(24))
    assert (
        client.post("/invitados/prueba/distribuir", headers=auth(owner), json=datos).json()[
            "resultados"
        ][0]["estado"]
        == "ENVIADO"
    )
    assert client.post("/invitados/prueba/distribuir", headers=auth(owner), json=datos).json()[
        "resultados"
    ][0]["reintento"]
    assert len(envios) == 1

    def falla(*args, **kw):
        raise RuntimeError("SMTP no disponible")

    monkeypatch.setattr("app.services.invitados_distribucion._send_email", falla)
    datos["idempotencia"] = secrets.token_urlsafe(24)
    assert (
        client.post("/invitados/prueba/distribuir", headers=auth(owner), json=datos).json()[
            "resultados"
        ][0]["estado"]
        == "FALLIDO"
    )


def test_aprobacion_automatica_y_og_sin_datos_privados(contexto):
    client, _, _, owner, _ = contexto
    habilitar(client, owner, aprobacion="automatica")
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    r = confirmar(client, token, 2, ["Sofia"])
    assert r.status_code == 200 and r.json()["cupo_aprobado"] == 3 and r.json()["qr"]
    html = client.get("/compartir/prueba?dev=true").text
    for propiedad in [
        "og:title",
        "og:description",
        "og:image",
        "og:url",
        "og:type",
        "twitter:card",
    ]:
        assert propiedad in html
    assert token not in html and "Sofia" not in html and "cantidad_permitida" not in html


def test_qr_vencido_revocado_y_correcciones_auditadas(contexto):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, aprobacion="automatica")
    inv = crear(client, owner)
    link = enlace(client, owner, inv)
    qr = confirmar(client, link, 3).json()["qr"]
    key = secrets.token_urlsafe(24)
    assert (
        client.post(
            "/invitados/prueba/control/ingreso",
            headers=auth(owner),
            json={"token": qr, "cantidad": 2, "idempotencia": key},
        ).status_code
        == 200
    )
    correccion = {
        "cantidad": 1,
        "motivo": "Se conto dos veces al titular",
        "idempotencia": secrets.token_urlsafe(24),
    }
    ruta = f"/invitados/prueba/control/{inv['id']}/corregir"
    assert client.post(ruta, headers=auth(owner), json=correccion).json()["ingresados"] == 1
    assert client.post(ruta, headers=auth(owner), json=correccion).json()["ingresados"] == 1
    assert (
        client.post(
            ruta,
            headers=auth(owner),
            json={**correccion, "cantidad": 9, "idempotencia": secrets.token_urlsafe(24)},
        ).status_code
        == 409
    )
    c = db.scalar(
        select(CredencialInvitacion).where(
            CredencialInvitacion.tipo == "qr", CredencialInvitacion.activo.is_(True)
        )
    )
    c.vence_at = ahora() - timedelta(seconds=1)
    db.commit()
    assert (
        client.post(
            "/invitados/prueba/control/consultar", headers=auth(owner), json={"token": qr}
        ).status_code
        == 404
    )
    nuevo = client.post(
        f"/invitados/prueba/lista/{inv['id']}/credencial/qr/regenerar", headers=auth(owner)
    ).json()["token"]
    assert nuevo != qr
    assert (
        client.post(
            "/invitados/prueba/control/consultar", headers=auth(owner), json={"token": nuevo}
        ).status_code
        == 200
    )
    client.post(f"/invitados/prueba/lista/{inv['id']}/credencial/qr/revocar", headers=auth(owner))
    assert (
        client.post(
            "/invitados/prueba/control/ingreso",
            headers=auth(owner),
            json={"token": nuevo, "cantidad": 1, "idempotencia": secrets.token_urlsafe(24)},
        ).status_code
        == 404
    )


def test_pin_cambio_metodo_y_limite_de_intentos(contexto):
    client, _, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    sesion = client.post("/invitados/prueba/portal", json={"token": token}).json()["sesion"]
    habilitar(client, owner, pin_acceso="123456")
    assert not client.post(
        "/invitados/prueba/portal", json={"token": token, "sesion": sesion}
    ).json()["validado"]
    assert (
        client.post(
            "/invitados/prueba/portal/validar", json={"token": token, "pin": "xxxx"}
        ).status_code
        == 401
    )
    personal = client.post(f"/invitados/prueba/lista/{inv['id']}/pin-personal", headers=auth(owner), json={"canal":"presencial"}).json()["pin"]
    valido = client.post(
        "/invitados/prueba/portal/validar", json={"token": token, "pin": "123456"}
    ).json()
    assert "validado" not in valido  # El PIN compartido anterior ya no valida identidad.
    valido = client.post("/invitados/prueba/portal/validar", json={"token": token, "pin": personal}).json()
    assert valido["validado"]
    habilitar(client, owner, validacion="email", quitar_pin=True)
    assert confirmar(client, token, sesion=valido["sesion"]).status_code == 401
    for _ in range(10):
        client.post("/invitados/prueba/portal/validar", json={"token": token, "codigo": "xxxx"})
    assert (
        client.post(
            "/invitados/prueba/portal/validar", json={"token": token, "codigo": "xxxx"}
        ).status_code
        == 429
    )


def test_otp_vencido_y_proveedor_no_configurado(contexto, monkeypatch, capsys):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, validacion="email", otp_intentos=1)
    inv = crear(client, owner, email="ana@example.com", telefono="+54 9 2966 123456")
    token = enlace(client, owner, inv)
    monkeypatch.setattr("app.services.invitados_portal._send_email", lambda *a: None)
    assert (
        client.post(
            "/invitados/prueba/portal/codigo", json={"token": token, "email": "ana@example.com"}
        ).status_code
        == 200
    )
    otp = db.scalar(select(ValidacionInvitado))
    otp.vence_at = ahora() - timedelta(seconds=1)
    db.commit()
    assert (
        client.post(
            "/invitados/prueba/portal/validar", json={"token": token, "codigo": "123456"}
        ).status_code
        == 401
    )
    habilitar(client, owner, validacion="telefono")
    assert (
        client.post(
            "/invitados/prueba/portal/codigo", json={"token": token, "email": "ana@example.com"}
        ).status_code
        == 503
    )
    from app.core.config import settings
    from app.services.email import _send_email

    monkeypatch.setattr(settings, "smtp_host", None)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        _send_email("ana@example.com", "Codigo", "secreto-123456", "secreto-123456")
    assert error.value.status_code == 503 and "secreto-123456" not in capsys.readouterr().out


def test_actualizacion_excel_preserva_rsvp_y_no_acepta_formulas(contexto):
    from openpyxl import Workbook, load_workbook

    client, _, _, owner, _ = contexto
    habilitar(client, owner, aprobacion="automatica")
    inv = crear(client, owner, nombre="Ana", email="ana@example.com")
    token = enlace(client, owner, inv)
    confirmar(client, token, 2, ["Sofia"])
    archivo = excel([["Ana", "", "ana@example.com", None, None, "Familia nueva", None, 1]])
    pre = client.post(
        "/invitados/prueba/importar/preview?actualizar=true",
        headers=auth(owner),
        files={"file": ("invitados.xlsx", archivo)},
    ).json()
    r = client.post("/invitados/prueba/importar/" + pre["token"], headers=auth(owner)).json()
    assert r["actualizados"] == 1
    guardado = client.get("/invitados/prueba/lista", headers=auth(owner)).json()["items"][0]
    assert (
        guardado["cantidad_permitida"] == 4
        and guardado["solicitados"] == 3
        and guardado["nombres_menores"] == ["Sofia"]
    )
    wb = Workbook()
    wb.active.append(["Nombre"])
    wb.active.append(["=1+1"])
    salida = io.BytesIO()
    wb.save(salida)
    formula = client.post(
        "/invitados/prueba/importar/preview",
        headers=auth(owner),
        files={"file": ("formulas.xlsx", salida.getvalue())},
    ).json()
    assert formula["filas"][0]["error"]
    seguro = load_workbook(io.BytesIO(excel([["=formula"]], ["Nombre"])))
    assert seguro.active["A2"].data_type == "s"


def test_canales_deshabilitados_cancelacion_y_cierre(contexto):
    client, _, _, owner, _ = contexto
    habilitar(client, owner, aprobacion="automatica", canales=["enlace"])
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    assert (
        client.post(
            "/invitados/prueba/distribuir",
            headers=auth(owner),
            json={"ids": [inv["id"]], "canal": "email", "idempotencia": secrets.token_urlsafe(24)},
        ).status_code
        == 403
    )
    confirmar(client, token, 2)
    r = client.post(
        "/invitados/prueba/portal/rsvp",
        json={"token": token, "rsvp": {"asiste": False, "adultos": 0, "menores": []}},
    ).json()
    assert r["rsvp"] == "CANCELADO" and r["qr"] is None
    habilitar(client, owner, cierre_rsvp=(ahora() - timedelta(hours=1)).isoformat())
    assert confirmar(client, token).status_code == 409


def test_control_no_administra_y_no_ve_nombres_de_menores(contexto):
    client, _, _, owner, _ = contexto
    habilitar(client, owner, aprobacion="automatica")
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    confirmar(client, token, 2, ["Sofia"])
    client.post(
        "/invitados/prueba/roles",
        headers=auth(owner),
        json={"email": "puerta@example.com", "rol": "CONTROL_INGRESO"},
    )
    _, db, *_ = contexto
    operador = db.scalar(select(User).where(User.email == "puerta@example.com"))
    headers = auth(operador)
    assert "Sofia" not in client.get("/invitados/prueba/lista", headers=headers).text
    assert client.get("/invitados/prueba/exportar.xlsx", headers=headers).status_code == 403
    assert (
        client.get(f"/invitados/prueba/lista/{inv['id']}/qr.png", headers=headers).status_code
        == 403
    )
    assert (
        client.post(
            f"/invitados/prueba/lista/{inv['id']}/rsvp",
            headers=headers,
            json={"asiste": True, "adultos": 1},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/invitados/prueba/control/{inv['id']}/corregir",
            headers=headers,
            json={
                "cantidad": 1,
                "motivo": "No autorizado",
                "idempotencia": secrets.token_urlsafe(24),
            },
        ).status_code
        == 403
    )


def test_privacidad_logs_y_og_https(contexto, monkeypatch):
    import logging

    from app.core.config import settings
    from app.core.log_privacidad import OcultarCredenciales

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        1,
        '%s - "%s %s HTTP/%s" %s',
        ("cliente", "GET", "/e/prueba/i/token-privado?enlace=jwt-privado", "1.1", 200),
        None,
    )
    OcultarCredenciales().filter(record)
    assert "token-privado" not in record.getMessage() and "jwt-privado" not in record.getMessage()
    client, *_ = contexto
    monkeypatch.setattr(settings, "frontend_public_url", "http://ejemplo.invalid")
    assert client.get("/compartir/prueba").status_code == 503
    monkeypatch.setattr(settings, "frontend_public_url", "https://ejemplo.invalid")
    assert 'content="https://ejemplo.invalid/media/' in client.get("/compartir/prueba").text


def test_control_consulta_global_sin_ampliar_lista_privada(contexto):
    client, db, _, owner, _ = contexto
    habilitar(client, owner, listas_compartidas=False, aprobacion="automatica")
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    confirmar(client, token, 2, ["Sofia"])
    for rol, permisos in [
        ("GESTOR_INVITADOS", ["ver_invitados", "estadisticas"]),
        ("CONTROL_INGRESO", None),
    ]:
        assert (
            client.post(
                "/invitados/prueba/roles",
                headers=auth(owner),
                json={
                    "email": "doble@example.com",
                    "rol": rol,
                    "permisos": permisos,
                    "solo_responsable": True,
                },
            ).status_code
            == 200
        )
    operador = db.scalar(select(User).where(User.email == "doble@example.com"))
    headers = auth(operador)
    assert client.get("/invitados/prueba/lista", headers=headers).json()["total"] == 0
    assert (
        client.get("/invitados/prueba/estadisticas", headers=headers).json()[
            "invitados_registrados"
        ]
        == 0
    )
    assert (
        client.get("/invitados/prueba/estadisticas?control=true", headers=headers).json()[
            "invitados_registrados"
        ]
        == 1
    )
    r = client.get("/invitados/prueba/control/buscar", headers=headers)
    assert len(r.json()["items"]) == 1 and "Sofia" not in r.text


def test_validacion_contenido_de_imagen_y_path_seguro(contexto, monkeypatch, tmp_path):
    from fastapi import HTTPException

    from app.services.media_storage import LocalMediaStorage

    client, _, _, owner, _ = contexto
    local = LocalMediaStorage(str(tmp_path))
    monkeypatch.setattr("app.services.media.media_storage", local)
    assert (
        client.post(
            "/media/eventos/prueba/PORTADA",
            headers=auth(owner),
            files={"file": ("falsa.png", b"\x89PNG\r\n\x1a\nno-es-imagen", "image/png")},
        ).status_code
        == 400
    )
    with pytest.raises(HTTPException):
        local._safe_path("../../fuera.png")


def test_descargar_o_reenviar_no_reactiva_qr_revocado(contexto):
    client, _, _, owner, _ = contexto
    habilitar(client, owner, aprobacion="automatica")
    inv = crear(client, owner)
    token = enlace(client, owner, inv)
    assert confirmar(client, token, 1).json()["qr"]
    client.post(f"/invitados/prueba/lista/{inv['id']}/credencial/qr/revocar", headers=auth(owner))
    assert (
        client.get(f"/invitados/prueba/lista/{inv['id']}/qr.png", headers=auth(owner)).status_code
        == 409
    )
    envio = client.post(
        "/invitados/prueba/distribuir",
        headers=auth(owner),
        json={
            "ids": [inv["id"]],
            "tipo": "qr",
            "canal": "enlace",
            "idempotencia": secrets.token_urlsafe(24),
        },
    )
    assert envio.json()["resultados"][0]["estado"] == "FALLIDO"
    assert client.post("/invitados/prueba/portal", json={"token": token}).json()["qr"] is None


def test_asignar_varios_agasajados_y_compartir_portada(contexto):
    client, db, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner, telefono="5492966123456")
    datos = {"emails": ["uno@example.com", "dos@example.com", "UNO@example.com"]}
    r = client.post("/invitados/prueba/agasajados", headers=auth(owner), json=datos)
    assert r.status_code == 200 and len(r.json()["agasajados"]) == 2
    assert (
        client.post("/invitados/prueba/agasajados", headers=auth(owner), json=datos).status_code
        == 200
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(EventoUsuario)
            .where(EventoUsuario.rol == RolEvento.AGASAJADO)
        )
        == 2
    )
    for email in ["uno@example.com", "dos@example.com"]:
        agasajado = db.scalar(select(User).where(User.email == email))
        assert not agasajado.es_superadministrador
        assert not client.get("/eventos/prueba/permisos", headers=auth(agasajado)).json()[
            "puede_editar"
        ]
        assert (
            client.post(
                "/invitados/prueba/agasajados",
                headers=auth(agasajado),
                json={"emails": ["otro@example.com"]},
            ).status_code
            == 403
        )
        resultado = client.post(
            "/invitados/prueba/distribuir",
            headers=auth(agasajado),
            json={
                "ids": [inv["id"]],
                "canal": "whatsapp",
                "idempotencia": secrets.token_urlsafe(24),
            },
        )
        assert resultado.status_code == 200
        compartido = resultado.json()["resultados"][0]
        assert compartido["estado"] == "PREPARADO"
        assert "wa.me/5492966123456" in compartido["url_canal"]
        assert compartido["portada_url"].startswith("http://localhost:5179/media/")
        assert "Presiona aqui para confirmar:" in compartido["mensaje"]
        assert compartido["enlace"].endswith("#mi-confirmacion")
        assert compartido["enlace"] in compartido["mensaje"]


def test_receptor_debe_ingresar_antes_de_confirmar_por_defecto(contexto, monkeypatch):
    client, _, _, owner, _ = contexto
    r = client.put("/invitados/prueba/config", headers=auth(owner), json={"activo": True})
    assert r.status_code == 200 and r.json()["requiere_login"] and r.json()["validacion"] == "email"
    inv = crear(client, owner, email="receptor@example.com")
    token = enlace(client, owner, inv)
    inicial = client.post("/invitados/prueba/portal", json={"token": token}).json()
    assert not inicial["validado"] and "nombre" not in inicial
    assert confirmar(client, token).status_code == 401
    enviados = []
    monkeypatch.setattr(
        "app.services.invitados_portal._send_email", lambda *args: enviados.append(args)
    )
    assert (
        client.post(
            "/invitados/prueba/portal/codigo",
            json={"token": token, "email": "receptor@example.com"},
        ).status_code
        == 200
    )
    codigo = enviados[0][3].split(": ")[1]
    acceso = client.post(
        "/invitados/prueba/portal/validar", json={"token": token, "codigo": codigo}
    ).json()
    assert acceso["validado"] and acceso["sesion"]
    assert confirmar(client, token, sesion=acceso["sesion"]).status_code == 200


def test_abm_contactos_sociales_sin_email_y_excel(contexto):
    from openpyxl import load_workbook
    client, db, _, owner, _ = contexto
    habilitar(client, owner)
    contactos = {"whatsapp": "+5491112345678", "instagram": "@ana", "facebook": "ana.perfil", "telegram": "@ana_tg", "otro_contacto": "Signal: ana"}
    inv = crear(client, owner, nombre="Ana", **contactos)
    for campo, valor in contactos.items():
        assert inv[campo] == valor
    ruta = f"/invitados/prueba/lista/{inv['id']}"
    datos = {"nombre": "Ana editada", **contactos, "activo": False}
    assert client.put(ruta, headers=auth(owner), json=datos).json()["activo"] is False
    assert not client.get("/invitados/prueba/lista", headers=auth(owner)).json()["items"]
    datos["activo"] = True
    assert client.put(ruta, headers=auth(owner), json=datos).json()["activo"] is True
    archivo = client.get("/invitados/prueba/exportar.xlsx", headers=auth(owner))
    hoja = load_workbook(io.BytesIO(archivo.content)).active
    encabezados = [c.value for c in hoja[1]]
    assert hoja.cell(2, encabezados.index("Facebook") + 1).value == "ana.perfil"
    contenido = excel([["Luis", "", "", "", "@luis", "", "", 2, "+5491198765432", "luis.fb", "@luis_tg", "Signal: luis"]])
    previo = client.post("/invitados/prueba/importar/preview", headers=auth(owner), files={"file": ("invitados.xlsx", contenido)})
    assert previo.status_code == 200, previo.text
    token = previo.json()["token"]
    resultado = client.post(f"/invitados/prueba/importar/{token}", headers=auth(owner))
    assert resultado.json()["importados"] == 1, resultado.text
    luis = db.scalar(select(Invitacion).where(Invitacion.nombre == "Luis"))
    assert luis.telegram == "@luis_tg" and luis.facebook == "luis.fb"


def test_contactos_sociales_respetan_permisos(contexto):
    client, db, _, owner, evento = contexto
    habilitar(client, owner)
    gestor = User(email="gestor_social@example.com")
    db.add(gestor); db.flush()
    rol = EventoUsuario(evento_id=evento.id, usuario_id=gestor.id, rol=RolEvento.GESTOR_INVITADOS,
                        permisos=["ver_invitados", "editar_invitados", "importar"], solo_responsable=True)
    db.add(rol); db.commit()
    ajeno = crear(client, owner, nombre="Ajeno", telegram="@ajeno")
    propio = crear(client, gestor, nombre="Propio", facebook="perfil")
    assert propio["responsable_id"] == gestor.id
    assert client.put(f"/invitados/prueba/lista/{ajeno['id']}", headers=auth(gestor), json={"nombre": "Cambio"}).status_code == 404
    rol.permisos = ["ver_invitados"]; db.commit()
    assert client.post("/invitados/prueba/lista", headers=auth(gestor), json={"nombre": "Sin permiso", "telegram": "@otro"}).status_code == 403
    assert client.post("/invitados/prueba/importar/preview", headers=auth(gestor), files={"file": ("lista.xlsx", excel([]))}).status_code == 403


def test_importacion_anterior_conserva_redes_y_distribucion_manual(contexto):
    client, _, _, owner, _ = contexto
    habilitar(client, owner)
    inv = crear(client, owner, nombre="Ana", email="ana@example.com", telefono="1111", whatsapp="+5491122334455", telegram="@ana")
    contenido = excel([["Ana nueva", "", "ana@example.com", "1111", "", "", "", 4]], ["Nombre", "Apellido", "Email", "Telefono", "Instagram", "Grupo", "Responsable", "Cupos"])
    previo = client.post("/invitados/prueba/importar/preview?actualizar=true", headers=auth(owner), files={"file": ("anterior.xlsx", contenido)}).json()
    resultado = client.post("/invitados/prueba/importar/" + previo["token"], headers=auth(owner))
    assert resultado.json()["actualizados"] == 1
    lista = client.get("/invitados/prueba/lista", headers=auth(owner), params={"q": "@ana"}).json()
    assert lista["total"] == 1 and lista["items"][0]["telegram"] == "@ana"
    for canal in ["whatsapp", "telegram"]:
        r = client.post("/invitados/prueba/distribuir", headers=auth(owner), json={"ids": [inv["id"]], "canal": canal, "idempotencia": secrets.token_urlsafe(24)})
        assert r.status_code == 200, r.text
        envio = r.json()["resultados"][0]
        assert envio["estado"] == "PREPARADO"
        assert ("wa.me/5491122334455" if canal == "whatsapp" else "t.me/share/url") in envio["url_canal"]
