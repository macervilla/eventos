from io import BytesIO
from PIL import Image

def png_valido():
    salida = BytesIO()
    Image.new("RGB", (2, 2), "blue").save(salida, "PNG")
    return salida.getvalue()

import pytest
from sqlalchemy import select

from app.core.seguridad import crear_token_sesion
from app.models.enums import RolEvento, MediaTipo, Plan
from app.models.eventos import Evento, EventoUsuario
from app.models.interacciones import Media
from app.models.usuarios import User
from app.services.media_storage import LocalMediaStorage

pytest_plugins = ["tests.test_administracion", "tests.test_google_oauth"]


def auth(usuario):
    return {"Authorization": f"Bearer {crear_token_sesion(usuario)}"}


def datos(**cambios):
    resultado = {"titulo_visual": "Titulo de la invitacion", "descripcion": "Nos encontramos!",
                 "fecha_inicio": "2027-01-15T21:00:00-03:00", "lugar_tipo": "domicilio",
                 "direccion": "Calle 123", "localidad": "Rio Gallegos", "provincia": "Santa Cruz",
                 "pais": "Argentina", "latitud": -51.62, "longitud": -69.22,
                 "colores": {"fondo": "#112233", "texto": "#ffffff", "acento": "#abcdef"},
                 "modulos_habilitados": ["detalles", "ubicacion", "galeria"], "tipografia": "moderna"}
    resultado.update(cambios)
    return resultado


def test_permisos_visitante_propietario_colaborador(contexto):
    client, db, admin, propietario, evento = contexto
    visitante = User(email="acersistemasweb@gmail.com")
    colaborador = User(email="colaborador@example.com")
    invitado = User(email="invitado@example.com")
    db.add_all([visitante, colaborador, invitado]); db.flush()
    db.add_all([EventoUsuario(evento_id=evento.id, usuario_id=colaborador.id, rol=RolEvento.ENCARGADO),
                EventoUsuario(evento_id=evento.id, usuario_id=invitado.id, rol=RolEvento.INVITADO)])
    db.commit()
    ruta = "/eventos/prueba"
    assert client.get(ruta + "/permisos").json() == {"usuario": None, "rol": "visitante", "puede_editar": False, "permisos_invitados": []}
    for usuario, rol, edita in [(propietario, "administrador", True), (colaborador, "colaborador", True),
                                (visitante, "visitante", False), (invitado, "visitante", False),
                                (admin, "superadministrador", True)]:
        permisos = client.get(ruta + "/permisos", headers=auth(usuario)).json()
        assert permisos["usuario"]["id"] == usuario.id
        assert permisos["rol"] == rol
        assert permisos["puede_editar"] == edita
        respuesta = client.put(ruta, json=datos(), headers=auth(usuario))
        assert respuesta.status_code == (200 if edita else 403)
        encuadre = {"x": 50, "y": 50, "zoom": 1}
        assert client.put(ruta + "/portada-encuadre", json=encuadre, headers=auth(usuario)).status_code == (200 if edita else 403)
    assert client.put(ruta, json=datos()).status_code == 401
    assert client.put("/eventos/otro-evento", json=datos(), headers=auth(propietario)).status_code == 404


def test_no_edita_evento_ajeno_y_revocacion_inmediata(contexto):
    client, db, _, propietario, evento = contexto
    otro = User(email="otro@example.com"); db.add(otro); db.flush()
    otro_evento = Evento(nombre="Ajeno", slug="ajeno", propietario_id=otro.id)
    db.add(otro_evento); db.commit()
    assert client.put("/eventos/ajeno", json=datos(), headers=auth(propietario)).status_code == 403
    miembro = EventoUsuario(evento_id=evento.id, usuario_id=otro.id, rol=RolEvento.ENCARGADO)
    db.add(miembro); db.commit()
    sesion = auth(otro)
    assert client.put("/eventos/prueba", json=datos(), headers=sesion).status_code == 200
    miembro.rol = RolEvento.INVITADO; db.commit()
    assert client.put("/eventos/prueba", json=datos(), headers=sesion).status_code == 403


def test_datos_editables_e_identidad_inmutable(contexto):
    client, db, _, propietario, evento = contexto
    ruta = "/eventos/prueba"
    r = client.put(ruta, json=datos(), headers=auth(propietario))
    assert r.status_code == 200
    guardado = client.get(ruta).json()
    assert guardado["nombre"] == "Prueba" and guardado["slug"] == "prueba"
    assert guardado["titulo_visual"] == "Titulo de la invitacion"
    assert guardado["colores"]["fondo"] == "#112233"
    assert set(guardado["modulos_habilitados"]) == {"detalles", "ubicacion", "galeria"}
    assert guardado["latitud"] == -51.62 and guardado["tipografia"] == "moderna"
    for cambios in [{"nombre": "Otro"}, {"slug": "otro"}, {"propietario_id": 99},
                     {"colores": {"fondo": "url(javascript:alert(1))"}},
                     {"modulos_habilitados": ["modulo-inexistente"]}, {"latitud": 999}]:
        assert client.put(ruta, json=datos(**cambios), headers=auth(propietario)).status_code == 422
    assert db.get(Evento, evento.id).nombre == "Prueba"
    assert client.put(ruta, json=datos(modulos_habilitados=[]), headers=auth(propietario)).json()["modulos_habilitados"] == []


def test_identidad_google_persistente(contexto, google):
    client, db, _, propietario, _ = contexto
    r = client.post("/acceso/google", json={"credential": google(email=propietario.email, sub="google-estable")})
    assert r.status_code == 200
    db.refresh(propietario)
    assert propietario.google_subject == "google-estable"
    # El correo del token cambia: el subject sigue resolviendo al mismo ID interno.
    r = client.post("/acceso/google", json={"credential": google(email="nuevo@example.com", sub="google-estable")})
    permisos = client.get("/eventos/prueba/permisos", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()
    assert permisos["usuario"]["id"] == propietario.id and permisos["puede_editar"]
    r = client.post("/acceso/google", json={"credential": google(email=propietario.email, sub="otra-identidad")})
    assert r.status_code == 403
    assert not propietario.es_superadministrador


def test_imagenes_permisos_limites_y_reemplazos(contexto, monkeypatch, tmp_path):
    client, db, _, propietario, evento = contexto
    monkeypatch.setattr("app.services.media.media_storage", LocalMediaStorage(str(tmp_path)))
    visitante = User(email="visitante@example.com"); db.add(visitante); db.commit()
    archivo = {"file": ("imagen.png", png_valido(), "image/png")}
    portada = "/media/eventos/prueba/PORTADA"
    galeria = "/media/eventos/prueba/GALERIA"
    for ruta in [portada, galeria]:
        assert client.post(ruta, files=archivo).status_code == 401
        assert client.post(ruta, files=archivo, headers=auth(visitante)).status_code == 403
    assert client.post(portada, files=archivo, headers=auth(propietario)).status_code == 200
    assert client.post(portada, files=archivo, headers=auth(propietario)).status_code == 200
    assert len(db.scalars(select(Media).where(Media.tipo == MediaTipo.PORTADA, Media.activo.is_(True))).all()) == 1
    ids = []
    for _ in range(10):
        r = client.post(galeria, files=archivo, headers=auth(propietario))
        assert r.status_code == 200
        ids.append(r.json()["id"])
    assert client.post(galeria, files=archivo, headers=auth(propietario)).status_code == 400
    assert client.put(f"{galeria}/{ids[0]}", files=archivo, headers=auth(visitante)).status_code == 403
    assert client.put(f"{galeria}/{ids[0]}", files=archivo, headers=auth(propietario)).status_code == 200
    assert len(client.get("/eventos/prueba").json()["galeria"]) == 10
    assert not db.get(Media, ids[0]).activo
    assert client.put(f"{galeria}/999999", files=archivo, headers=auth(propietario)).status_code == 404
    evento.plan = Plan.PREMIUM
    db.commit()
    assert client.post(galeria, files=archivo, headers=auth(propietario)).status_code == 400
    assert client.get("/eventos/prueba").json()["limite_galeria"] == 10
    assert client.post(portada, files={"file": ("mal.svg", b"<svg/>", "image/svg+xml")}, headers=auth(propietario)).status_code == 400
    from app.core.config import settings
    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    assert client.post(portada, files=archivo, headers=auth(propietario)).status_code == 413


def test_enlace_email_conserva_destino(contexto, monkeypatch):
    client, _, _, propietario, _ = contexto
    enviados = []
    monkeypatch.setattr("app.services.acceso.send_access_link_email", lambda *args: enviados.append(args))
    assert client.post("/acceso/solicitar-enlace", json={"email": propietario.email, "destino": "/e/prueba"}).status_code == 200
    assert enviados[0][2] == "/e/prueba"
    for destino in ["https://otro.example", "//otro.example", "/\\otro.example"]:
        assert client.post("/acceso/solicitar-enlace", json={"email": propietario.email, "destino": destino}).status_code == 422


def test_configuracion_galeria_publica(contexto):
    client, db, _, propietario, _ = contexto
    visitante = User(email="visitante@example.com"); db.add(visitante); db.commit()
    ruta = "/eventos/prueba"
    for config in [{"modo": "carrusel", "filas": 2, "columnas": 2},
                   {"modo": "grilla", "filas": 2, "columnas": 5}]:
        assert client.put(ruta, json=datos(galeria_config=config), headers=auth(visitante)).status_code == 403
        r = client.put(ruta, json=datos(galeria_config=config), headers=auth(propietario))
        assert r.status_code == 200
        publico = client.get(ruta).json()
        assert publico["galeria_config"] == config
        assert "galeria" in publico["modulos_habilitados"]
        # Guardar otros datos no borra la configuracion si el cliente la omite.
        assert client.put(ruta, json=datos(), headers=auth(propietario)).json()["galeria_config"] == config
    for config in [{"modo": "inexistente"}, {"filas": 0}, {"columnas": 11}, {"filas": 3, "columnas": 4}, {"filas": 1.5}]:
        assert client.put(ruta, json=datos(galeria_config=config), headers=auth(propietario)).status_code == 422


def test_subir_imagen_habilita_galeria_publica(contexto, monkeypatch, tmp_path):
    client, _, _, propietario, _ = contexto
    monkeypatch.setattr("app.services.media.media_storage", LocalMediaStorage(str(tmp_path)))
    assert client.put("/eventos/prueba", json=datos(modulos_habilitados=["detalles"]), headers=auth(propietario)).status_code == 200
    assert "galeria" not in client.get("/eventos/prueba").json()["modulos_habilitados"]
    archivo = {"file": ("imagen.png", png_valido(), "image/png")}
    assert client.post("/media/eventos/prueba/GALERIA", files=archivo, headers=auth(propietario)).status_code == 200
    publico = client.get("/eventos/prueba").json()
    assert len(publico["galeria"]) == 1
    assert "galeria" in publico["modulos_habilitados"]
    assert publico["galeria_config"] == {"modo": "grilla", "filas": 2, "columnas": 2}
