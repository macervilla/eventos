import pytest

from tests.test_administracion import auth
from tests.test_edicion_evento import datos
from app.models.usuarios import User


def test_textos_persisten_y_no_se_pierden_al_editar_datos(contexto):
    client, db, admin, propietario, evento = contexto
    ruta = "/eventos/prueba"
    assert client.get(ruta).json()["textos_portada"] is None
    config = {"titulo": {"x": 77, "y": 80, "visible": False},
              "fecha": {"x": 10, "y": 5, "visible": True},
              "lugar": {"x": 40, "y": 90, "visible": True}}
    for usuario in (propietario, admin):
        r = client.put(ruta + "/textos-portada", json=config, headers=auth(usuario))
        assert r.status_code == 200, r.text
        assert r.json()["textos_portada"] == config
    assert client.put(ruta, json=datos(), headers=auth(propietario)).status_code == 200
    db.expire_all()
    publico = client.get(ruta).json()
    assert publico["textos_portada"] == config
    assert "textos_portada" not in publico["modulos_habilitados"]


def test_textos_requieren_permisos(contexto):
    client, db, _, _, _ = contexto
    otro = User(email="otro@example.com")
    db.add(otro); db.commit()
    ruta = "/eventos/prueba/textos-portada"
    assert client.put(ruta, json={}).status_code == 401
    assert client.put(ruta, json={}, headers=auth(otro)).status_code == 403


def test_colores_textos_persisten_sin_alterar_posiciones(contexto):
    client, db, _, propietario, _ = contexto
    ruta = "/eventos/prueba"
    posiciones = {"titulo": {"x": 60, "y": 12, "visible": True},
                  "fecha": {"x": 10, "y": 70, "visible": False},
                  "lugar": {"x": 80, "y": 85, "visible": True}}
    assert client.put(ruta + "/textos-portada", json=posiciones, headers=auth(propietario)).status_code == 200
    colores = {"titulo": "#ef4444", "fecha": "#f6c453", "lugar": "#38bdf8"}
    r = client.put(ruta, json=datos(colores_textos=colores), headers=auth(propietario))
    assert r.status_code == 200, r.text
    assert r.json()["colores_textos"] == colores
    assert r.json()["textos_portada"] == posiciones
    assert client.put(ruta, json=datos(), headers=auth(propietario)).status_code == 200
    db.expire_all()
    assert client.get(ruta).json()["colores_textos"] == colores
    assert "colores_textos" not in client.get(ruta).json()["modulos_habilitados"]
    assert client.put(ruta, json=datos(colores_textos={"titulo": "red"}), headers=auth(propietario)).status_code == 422
    assert client.put(ruta, json=datos(colores_textos=colores)).status_code == 401


@pytest.mark.parametrize("cambio", [{"x": -1}, {"y": 101}, {"x": "nan"}, {"html": "texto"}])
def test_textos_rechazan_configuracion_invalida(contexto, cambio):
    client, _, _, propietario, _ = contexto
    assert client.put("/eventos/prueba/textos-portada", json={"titulo": cambio}, headers=auth(propietario)).status_code == 422
