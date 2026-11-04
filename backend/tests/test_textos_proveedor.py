import pytest

from app.models.proveedores import Proveedor
from app.models.usuarios import User
from app.services.proveedores import _sync_categories
from tests.test_administracion import auth


@pytest.fixture()
def proveedor(contexto):
    _, db, _, propietario, _ = contexto
    proveedor = Proveedor(
        usuario_id=propietario.id, nombre_comercial="Los Sauces", slug="los-sauces",
        email=propietario.email, provincia="Santa Cruz", localidad="Rio Gallegos",
        direccion="Calle 123",
    )
    db.add(proveedor)
    db.flush()
    _sync_categories(db, proveedor, ["salon"])
    db.commit()
    return proveedor


def configuracion():
    return {
        "textos_portada": {
            "fecha": {"x": 10, "y": 15, "visible": False},
            "titulo": {"x": 75, "y": 40, "visible": True},
            "lugar": {"x": 50, "y": 90, "visible": True},
        },
        "colores_textos": {"fecha": "#123456", "titulo": "#abcdef", "lugar": "#ff8800"},
    }


def test_textos_persisten_al_editar_datos(contexto, proveedor):
    client, db, admin, propietario, _ = contexto
    ruta = f"/proveedores/{proveedor.slug}"
    inicial = client.get(ruta).json()
    assert inicial["textos_portada"] is None
    assert set(inicial["colores_textos"].values()) == {"#ffffff"}
    for usuario in (propietario, admin):
        respuesta = client.put(ruta + "/textos-portada", json=configuracion(), headers=auth(usuario))
        assert respuesta.status_code == 200, respuesta.text
    db.expire_all()
    publico = client.get(ruta).json()
    for campo, valor in configuracion().items():
        assert publico[campo] == valor
    publico.update(categorias=["salon"], descripcion="Descripcion actualizada")
    assert client.put(ruta, json=publico, headers=auth(propietario)).status_code == 200
    for campo, valor in configuracion().items():
        assert client.get(ruta).json()[campo] == valor


def test_requiere_propietario_o_administrador(contexto, proveedor):
    client, db, _, _, _ = contexto
    otro = User(email="otro@example.com")
    db.add(otro)
    db.commit()
    ruta = f"/proveedores/{proveedor.slug}/textos-portada"
    assert client.put(ruta, json=configuracion()).status_code == 401
    assert client.put(ruta, json=configuracion(), headers=auth(otro)).status_code == 403
    assert client.get(f"/proveedores/{proveedor.slug}").json()["textos_portada"] is None


@pytest.mark.parametrize("campo,valor", [("x", -1), ("y", 101), ("x", "nan")])
def test_posiciones_validas(contexto, proveedor, campo, valor):
    client, _, _, propietario, _ = contexto
    datos = configuracion()
    datos["textos_portada"]["titulo"][campo] = valor
    assert client.put(f"/proveedores/{proveedor.slug}/textos-portada", json=datos,
                      headers=auth(propietario)).status_code == 422


def test_colores_validos(contexto, proveedor):
    client, _, _, propietario, _ = contexto
    datos = configuracion()
    datos["colores_textos"]["titulo"] = "url(javascript:alert(1))"
    assert client.put(f"/proveedores/{proveedor.slug}/textos-portada", json=datos,
                      headers=auth(propietario)).status_code == 422
