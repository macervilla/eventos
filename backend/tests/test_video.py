from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings
from app.core.seguridad import _leer
from app.models.eventos import Evento
from app.models.invitaciones import Invitacion
from app.models.video import CamaraVideo, SesionVideo, TransmisionEvento
from app.services import video
from app.services.invitados import ahora
from tests.test_invitados import auth, crear, enlace, habilitar


@pytest.fixture()
def vivo(contexto, monkeypatch):
    client, db, admin, owner, evento = contexto
    habilitar(client, owner)
    inv = crear(client, owner, nombre="Ana")
    token = enlace(client, owner, inv)
    otra = crear(client, owner, nombre="Otra")
    otro_token = enlace(client, owner, otra)
    monkeypatch.setattr(settings, "video_enabled", True)
    monkeypatch.setattr(settings, "mediamtx_auth_secret", SecretStr("secreto-solo-de-pruebas"))
    reales = {"path": None, "sesiones": [], "cortadas": []}
    monkeypatch.setattr(video.mediamtx, "path", lambda _: reales["path"])
    monkeypatch.setattr(video.mediamtx, "sessions", lambda: list(reales["sesiones"]))
    monkeypatch.setattr(video.mediamtx, "kick", lambda sid: reales["cortadas"].append(sid))
    return client, db, owner, evento, inv, token, otra, otro_token, reales


def permitir(vivo):
    client, _, owner, _, inv, *_ = vivo
    r = client.put("/invitados/prueba/vivo/autorizacion", headers=auth(owner), json={"invitacion_id": inv["id"]})
    assert r.status_code == 200, r.text


def media_auth(client, grant, accion="publish", sid=None):
    datos = _leer(grant["credencial"], "video")
    path = f"evt-{datos['evento_id']}-{datos['version']}"
    return client.post("/interno/mediamtx/auth", auth=("mediamtx", "secreto-solo-de-pruebas"), json={
        "token": grant["credencial"], "action": accion, "protocol": "webrtc", "path": path, "id": sid or str(uuid4())})


def test_solo_administrador_selecciona_y_solo_invitado_elegido_publica(vivo):
    client, db, owner, _, inv, token, otra, otro_token, _ = vivo
    ruta = "/invitados/prueba/vivo"
    assert client.put(ruta + "/autorizacion", json={"invitacion_id": inv["id"]}).status_code == 401
    permitir(vivo)
    assert client.post(ruta + "/iniciar", json={"token": otro_token}).status_code == 403
    assert client.post(ruta + "/iniciar", headers=auth(owner), json={}).status_code == 403
    r = client.post(ruta + "/iniciar", json={"token": token})
    assert r.status_code == 200
    assert client.post(ruta + "/iniciar", json={"token": token}).status_code == 409
    assert db.get(CamaraVideo, (1, inv["id"])).estado == "iniciando"


def test_auth_callback_rechaza_sin_secreto_rol_equivocado_y_segunda_sesion(vivo):
    client, db, owner, evento, _, token, *_ = vivo
    permitir(vivo)
    grant = client.post("/invitados/prueba/vivo/iniciar", json={"token": token}).json()
    claims = _leer(grant["credencial"], "video")
    datos = dict(token=grant["credencial"], action="publish", protocol="webrtc", path=f"evt-{evento.id}-{claims['version']}", id=str(uuid4()))
    assert client.post("/interno/mediamtx/auth", json=datos).status_code == 401
    assert media_auth(client, grant, "read").status_code == 403
    sid = str(uuid4())
    assert media_auth(client, grant, sid=sid).status_code == 204
    assert media_auth(client, grant, sid=sid).status_code == 204
    assert media_auth(client, grant).status_code == 403
    assert db.get(SesionVideo, sid).accion == "publish"


def test_estado_real_lectura_separada_desconexion_y_reinicio(vivo):
    client, db, owner, evento, inv, token, otra, otro_token, reales = vivo
    permitir(vivo)
    ruta = "/invitados/prueba/vivo"
    assert client.post(ruta + "/estado", json={"token": token}).json()["publicacion"]["estado"] == "autorizado"
    grant = client.post(ruta + "/iniciar", json={"token": token}).json()
    sid = str(uuid4()); assert media_auth(client, grant, sid=sid).status_code == 204
    assert client.post(ruta + "/estado", json={"token": token}).json()["publicacion"]["estado"] == "iniciando"
    reales["path"] = dict(ready=True, source=dict(id=sid))
    assert client.post(ruta + "/estado", json={"token": token, "sesion_media": sid}).json()["publicacion"]["estado"] == "activa"
    assert client.put(ruta + "/seleccion", headers=auth(owner), json={"invitacion_id": inv["id"]}).status_code == 200
    lectura = client.post(ruta + "/ver", json={"token": otro_token}).json()
    assert media_auth(client, lectura, "read").status_code == 204
    assert media_auth(client, lectura, "publish").status_code == 403
    reales["path"] = None
    assert client.post(ruta + "/estado", json={"token": token}).json()["publicacion"]["estado"] == "interrumpida"
    assert client.post(ruta + "/iniciar", json={"token": token}).status_code == 200


def test_revocacion_corta_media_invalida_tokens_y_publisher_abandonado(vivo):
    client, db, owner, evento, inv, token, _, _, reales = vivo
    permitir(vivo)
    grant = client.post("/invitados/prueba/vivo/iniciar", json={"token": token}).json()
    sid = str(uuid4()); media_auth(client, grant, sid=sid)
    row = db.get(CamaraVideo, (evento.id, inv["id"]))
    reales["sesiones"] = [dict(id=sid, path=video.path(row))]
    client.put("/invitados/prueba/vivo/autorizacion", headers=auth(owner), json={"invitacion_id": None})
    assert sid in reales["cortadas"]
    assert media_auth(client, grant, sid=sid).status_code == 403
    permitir(vivo)
    grant = client.post("/invitados/prueba/vivo/iniciar", json={"token": token}).json()
    sid = str(uuid4()); media_auth(client, grant, sid=sid)
    sesion = db.get(SesionVideo, sid); sesion.vence_at = ahora() - timedelta(seconds=1); db.commit()
    reales["sesiones"] = [dict(id=sid, path=video.path(db.get(CamaraVideo, (evento.id, inv["id"]))))]
    video.reconciliar(db)
    assert sid in reales["cortadas"] and not sesion.activo


def test_detencion_voluntaria_y_media_caido_no_bloquea_fotos(vivo, monkeypatch):
    client, db, owner, evento, inv, token, _, _, reales = vivo
    permitir(vivo)
    grant = client.post("/invitados/prueba/vivo/iniciar", json={"token": token}).json()
    assert client.post("/invitados/prueba/vivo/detener", json={"token": token, "reserva": grant["reserva"]}).json()["estado"] == "finalizada"
    def caido(*args): raise HTTPException(503, "Media fuera de servicio")
    monkeypatch.setattr(video.mediamtx, "path", caido)
    r = client.post("/invitados/prueba/vivo/estado", json={"token": token}).json()
    assert not r["disponible"] and r["estado"] != "activa"
    assert client.post("/invitados/prueba/portal/fotos/listar", json={"token": token}).status_code == 200
    assert client.post("/invitados/prueba/vivo/iniciar", json={"token": token}).status_code == 503


def test_lectura_privada_entre_eventos_y_heartbeat_no_admite_sesion_ajena(vivo):
    client, db, owner, evento, inv, token, otra, otro_token, reales = vivo
    permitir(vivo)
    grant = client.post("/invitados/prueba/vivo/iniciar", json={"token": token}).json()
    sid = str(uuid4()); media_auth(client, grant, sid=sid)
    reales["path"] = dict(ready=True, source=dict(id=sid))
    assert client.post("/invitados/otro/vivo/estado", json={"token": token}).status_code == 404
    sesion = db.get(SesionVideo, sid); antes = sesion.vence_at
    client.post("/invitados/prueba/vivo/estado", json={"token": otro_token, "sesion_media": sid})
    assert sesion.vence_at == antes
    db.get(Invitacion, inv["id"]).activo = False; db.commit()
    reales["sesiones"] = [dict(id=sid, path=video.path(db.get(CamaraVideo, (evento.id, inv["id"]))))]
    video.reconciliar(db)
    assert sid in reales["cortadas"]


def test_no_inicia_hasta_cortar_generacion_anterior_y_revoca_aunque_api_falle(vivo, monkeypatch):
    client, db, owner, evento, inv, token, _, _, reales = vivo
    permitir(vivo)
    vieja = dict(id=str(uuid4()), path=f"evt-{evento.id}-{uuid4().hex}")
    reales["sesiones"] = [vieja]
    def falla(*args): raise HTTPException(503, "Corte pendiente")
    monkeypatch.setattr(video.mediamtx, "kick", falla)
    assert client.post("/invitados/prueba/vivo/iniciar", json={"token": token}).status_code == 503
    assert db.get(CamaraVideo, (evento.id, inv["id"])).reserva is None
    monkeypatch.setattr(video.mediamtx, "kick", lambda sid: reales["cortadas"].append(sid))
    grant = client.post("/invitados/prueba/vivo/iniciar", json={"token": token}).json()
    assert vieja["id"] in reales["cortadas"]
    monkeypatch.setattr(video.mediamtx, "sessions", falla)
    assert client.put("/invitados/prueba/vivo/autorizacion", headers=auth(owner), json={"invitacion_id": None}).status_code == 503
    assert db.get(TransmisionEvento, evento.id).invitacion_id is None
    assert media_auth(client, grant).status_code == 403


def test_error_de_cliente_libera_reserva_con_estado_interrumpido(vivo):
    client, _, _, _, _, token, *_ = vivo
    permitir(vivo)
    grant = client.post("/invitados/prueba/vivo/iniciar", json={"token": token}).json()
    r = client.post("/invitados/prueba/vivo/detener", json={"token": token, "reserva": grant["reserva"], "motivo": "interrumpida"})
    assert r.status_code == 200 and r.json()["estado"] == "interrumpida"
    assert client.post("/invitados/prueba/vivo/iniciar", json={"token": token}).status_code == 200


def test_multicamara_preview_seleccion_privada_y_revocacion_individual(vivo, monkeypatch):
    client, db, owner, evento, inv, token, otra, otro_token, reales = vivo
    ruta = "/invitados/prueba/vivo"
    paths = {}
    monkeypatch.setattr(video.mediamtx, "path", lambda nombre: paths.get(nombre))
    permitir(vivo)
    assert client.put(ruta + "/autorizacion", headers=auth(owner), json={"invitacion_id": otra["id"]}).status_code == 200
    assert client.put(ruta + "/seleccion", headers=auth(owner), json={"invitacion_id": inv["id"]}).status_code == 409
    sesiones = []
    for persona, tok in ((inv, token), (otra, otro_token)):
        grant = client.post(ruta + "/iniciar", json={"token": tok}).json()
        sid = str(uuid4())
        assert media_auth(client, grant, sid=sid).status_code == 204
        row = db.get(CamaraVideo, (evento.id, persona["id"]))
        paths[video.path(row)] = dict(ready=True, source=dict(id=sid))
        sesiones.append(dict(id=sid, path=video.path(row)))
    reales["sesiones"] = list(sesiones)
    vista = client.post(ruta + "/estado", headers=auth(owner), json={}).json()
    assert len(vista["camaras"]) == 2 and all(c["emision"] for c in vista["camaras"])
    assert vista["emision"] is None  # Habilitar no selecciona automaticamente el album.
    assert client.post(ruta + "/ver", json={"token": otro_token}).status_code == 409
    assert client.post(ruta + "/ver", json={"token": token, "invitacion_id": otra["id"]}).status_code == 403
    preview = client.post(ruta + "/ver", headers=auth(owner), json={"invitacion_id": inv["id"]}).json()
    preview_sid = str(uuid4())
    assert media_auth(client, preview, "read", preview_sid).status_code == 204
    assert client.put(ruta + "/seleccion", json={"invitacion_id": inv["id"]}).status_code == 401
    assert client.put(ruta + "/seleccion", headers=auth(owner), json={"invitacion_id": inv["id"]}).status_code == 200
    lector = client.post(ruta + "/ver", json={"token": otro_token}).json()
    lector_sid = str(uuid4())
    assert media_auth(client, lector, "read", lector_sid).status_code == 204
    reales["sesiones"] += [dict(id=preview_sid, path=sesiones[0]["path"]), dict(id=lector_sid, path=sesiones[0]["path"])]
    assert client.put(ruta + "/seleccion", headers=auth(owner), json={"invitacion_id": otra["id"]}).status_code == 200
    assert media_auth(client, lector, "read").status_code == 403
    video.reconciliar(db)
    assert lector_sid in reales["cortadas"]
    assert not any(s["id"] in reales["cortadas"] for s in sesiones)
    assert preview_sid not in reales["cortadas"]
    estado = client.post(ruta + "/estado", json={"token": token}).json()
    assert estado["invitacion_id"] == otra["id"] and "camaras" not in estado
    assert estado["puede_publicar"] and estado["publicacion"]["invitacion_id"] == inv["id"]
    assert client.put(ruta + "/autorizacion", headers=auth(owner), json={"invitacion_id": otra["id"], "habilitada": False}).status_code == 200
    assert sesiones[1]["id"] in reales["cortadas"] and sesiones[0]["id"] not in reales["cortadas"]
    assert client.post(ruta + "/estado", json={"token": token}).json()["emision"] is None


def test_limites_y_reservas_libera_plaza_sin_cortar_otras_camaras(vivo, monkeypatch):
    client, db, owner, evento, inv, token, otra, otro_token, _ = vivo
    ruta = "/invitados/prueba/vivo"
    monkeypatch.setattr(settings, "video_max_camaras_evento", 1)
    permitir(vivo)
    assert client.put(ruta + "/autorizacion", headers=auth(owner), json={"invitacion_id": otra["id"]}).status_code == 409
    # Habilitar dos veces no cambia la generacion ni interrumpe la camara existente.
    version = db.get(CamaraVideo, (evento.id, inv["id"])).version
    permitir(vivo)
    assert db.get(CamaraVideo, (evento.id, inv["id"])).version == version
    monkeypatch.setattr(settings, "video_max_camaras_evento", 2)
    assert client.put(ruta + "/autorizacion", headers=auth(owner), json={"invitacion_id": otra["id"]}).status_code == 200
    monkeypatch.setattr(settings, "video_max_transmisiones", 1)
    grant = client.post(ruta + "/iniciar", json={"token": token}).json()
    assert client.post(ruta + "/iniciar", json={"token": otro_token}).status_code == 409
    assert client.post(ruta + "/detener", json={"token": token, "reserva": grant["reserva"]}).status_code == 200
    assert client.post(ruta + "/iniciar", json={"token": otro_token}).status_code == 200
