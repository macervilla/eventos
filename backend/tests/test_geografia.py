"""PostgreSQL real aislado: GEO_TEST_DATABASE_URL debe apuntar al servidor de pruebas."""
import json
import os
import socket
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from app.cli.geonames import digest, import_catalog
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.eventos import Evento
from app.models.geografia import GeoImportacion, GeoLocalidad
from app.models.proveedores import CategoriaProveedor
from app.models.usuarios import User
from app.schemas.eventos import EventoCreate
from app.schemas.proveedores import ProveedorCreate
from app.schemas.ubicacion import UserLocationPreferenceUpsert
from app.services.eventos import crear_evento, evento_a_read
from app.services.geografia import buscar_localidades, normalizar, resolver_geografia
from app.services.proveedores import create_proveedor
from app.services.ubicacion import upsert_preference


@pytest.fixture()
def pg():
    url = os.getenv("GEO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Definir GEO_TEST_DATABASE_URL para pruebas PostgreSQL aisladas")
    root = create_engine(url)
    schema = "test_geo_" + uuid.uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema},public"})
    Base.metadata.create_all(engine, checkfirst=False)
    try:
        yield engine
    finally:
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        root.dispose()


def city(geoid, name, country="AR", province="20", pop=5, aliases="", lat="-51.62"):
    return [str(geoid), name, normalizar(name), aliases, lat, "-69.22", "P", "PPL", country, "", province, "", "", "", str(pop), "", "", "America/Argentina/Rio_Gallegos", "2026-10-31"]


def dataset(path: Path, rows):
    path.mkdir(exist_ok=True)
    countries = []
    for code, name in [("AR", "Argentina"), ("ES", "Spain"), ("CR", "Costa Rica")]:
        row = [""] * 19
        row[0], row[4] = code, name
        countries.append("\t".join(row))
    (path / "countryInfo.txt").write_text("\n".join(countries), encoding="utf-8")
    (path / "admin1CodesASCII.txt").write_text("AR.20\tSanta Cruz\tSanta Cruz\t1\nAR.05\tCórdoba\tCordoba\t2\nES.51\tAndalucía\tAndalucia\t3\nCR.08\tSan José\tSan Jose\t4\n", encoding="utf-8")
    (path / "admin2Codes.txt").write_text("AR.20.001\tGüer Aike\tGuer Aike\t5\n", encoding="utf-8")
    with zipfile.ZipFile(path / "cities500.zip", "w") as archive:
        archive.writestr("cities500.txt", "\n".join("\t".join(row) for row in rows))
    manifest = {"version": "fixture", "descargado": "2026-10-31T00:00:00Z", "files": {}}
    for name in ("countryInfo.txt", "admin1CodesASCII.txt", "admin2Codes.txt", "cities500.zip"):
        manifest["files"][name] = {"sha256": digest(path / name), "url": "https://download.geonames.org/export/dump/" + name}
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture()
def catalogo(pg, tmp_path):
    rows = [city(3838859, "Río Gallegos", pop=100000, aliases="Rio Gallegos,Рио-Гальегос"),
            city(1, "Río Gatito", pop=3), city(2, "Córdoba", province="05", pop=1400000),
            city(3, "Córdoba", country="ES", province="51", pop=320000),
            city(4, "San José", country="CR", province="08", pop=300000), city(5, "San José", pop=10)]
    dataset(tmp_path, rows)
    import_catalog(pg, tmp_path, ["cities500.zip"], min_free_gib=0)
    return pg, tmp_path, rows


def test_importacion_inicial_y_reimportacion_sin_duplicados(catalogo):
    engine, path, _ = catalogo
    result = import_catalog(engine, path, ["cities500.zip"], min_free_gib=0)
    assert result["geo_localidades"] == 6
    assert result["geo_paises"] == 3
    assert result["geo_provincias"] == 4
    with Session(engine) as db:
        assert db.get(GeoLocalidad, 2).codigo_provincia == "05"
        assert db.scalar(select(func.count()).select_from(GeoImportacion).where(GeoImportacion.estado == "completada")) == 2


def test_prefijos_acentos_aliases_homonimos_y_localidades_pequenas(catalogo):
    engine, _, _ = catalogo
    with Session(engine) as db:
        r = buscar_localidades(db, "rio ga")
        assert r[0]["localidad"] == "Río Gallegos" and r[0]["provincia"] == "Santa Cruz" and r[0]["pais"] == "Argentina"
        assert any(x["localidad"] == "Río Gatito" for x in r)
        assert len(buscar_localidades(db, "cordoba")) == 2
        assert len({x["codigo_pais"] for x in buscar_localidades(db, "san jose")}) == 2
        assert buscar_localidades(db, "гальегос")[0]["geoname_id"] == 3838859
        assert buscar_localidades(db, "cordoba", codigo_pais="AR")[0]["codigo_pais"] == "AR"


def test_actualizacion_preserva_referencias_y_localidades_ausentes(catalogo):
    engine, path, rows = catalogo
    with Session(engine) as db:
        user = User(email="geo@example.com")
        db.add(user); db.flush()
        evento = Evento(nombre="No cambiar", slug="no-cambiar", propietario_id=user.id,
                        geoname_id=1, localidad="Texto historico", provincia="Texto anterior", pais="Argentina")
        db.add(evento); db.commit()
        evento_id = evento.id
    dataset(path, [rows[0]])
    import_catalog(engine, path, ["cities500.zip"], min_free_gib=0)
    with Session(engine) as db:
        assert db.get(GeoLocalidad, 1) is not None
        saved = db.get(Evento, evento_id)
        assert saved.geoname_id == 1 and saved.localidad == "Texto historico" and saved.slug == "no-cambiar"


def test_fallo_de_importacion_no_modifica_catalogo(catalogo):
    engine, path, _rows = catalogo
    dataset(path, [city(3838859, "No debe guardarse"), city(99, "Invalido", lat="200")])
    with pytest.raises(ValueError):
        import_catalog(engine, path, ["cities500.zip"], min_free_gib=0)
    with Session(engine) as db:
        assert db.get(GeoLocalidad, 3838859).nombre == "Río Gallegos"
        assert db.get(GeoLocalidad, 99) is None
        assert db.scalar(select(GeoImportacion.estado).order_by(GeoImportacion.id.desc()).limit(1)) == "fallida"


def test_fuente_corrupta_rechazada(catalogo):
    engine, path, _ = catalogo
    with (path / "countryInfo.txt").open("a", encoding="utf-8") as stream:
        stream.write("corrupto")
    with pytest.raises(ValueError, match="SHA256"):
        import_catalog(engine, path, ["cities500.zip"], min_free_gib=0)


def test_endpoint_validacion_y_busqueda_sin_internet(catalogo, monkeypatch):
    engine, _, _ = catalogo
    def no_internet(*args, **kwargs):
        raise AssertionError("Una busqueda geografica no debe utilizar Internet")
    monkeypatch.setattr(socket, "create_connection", no_internet)
    with Session(engine) as db:
        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:
                response = client.get("/geografia/localidades", params={"q": "rio ga"})
                assert response.status_code == 200 and response.json()["resultados"][0]["geoname_id"] == 3838859
                for q in ("ri", "   ", "%%%", "x" * 101):
                    assert client.get("/geografia/localidades", params={"q": q}).status_code == 422
                assert client.get("/geografia/localidades?q=rio&limit=1000").status_code == 422
                assert client.get("/geografia/localidades?q=rio&codigo_pais=INVALIDO").status_code == 422
                assert client.get("/geografia/localidades/3838859").json()["localidad"] == "Río Gallegos"
                assert client.get("/ubicacion/geocodificar", params={"q": "Calle 2, Rio Gallegos, Santa Cruz, Argentina"}).json()[0]["precision"] == "localidad"
        finally:
            app.dependency_overrides.clear()


def test_persistencia_eventos_proveedores_datos_antiguos_y_coordenadas(catalogo):
    engine, _, _ = catalogo
    with Session(engine) as db:
        datos = {"geoname_id": 3838859, "localidad": "Texto falso", "provincia": "Texto falso", "pais": "Otro",
                 "direccion": "Calle 2 y 29", "latitud": None, "longitud": None}
        evento, _ = crear_evento(db, EventoCreate(**datos, nombre="Evento", slug="evento", email="geo@example.com", lugar_tipo="domicilio"))
        assert evento.geoname_id == 3838859 and evento.codigo_pais == "AR"
        assert evento.localidad == "Río Gallegos" and evento.latitud == -51.62 and evento.direccion == "Calle 2 y 29"
        assert evento_a_read(evento).geoname_id == 3838859
        db.add(CategoriaProveedor(nombre="Salon", slug="salon")); db.commit()
        proveedor = create_proveedor(db, ProveedorCreate(**datos, nombre_comercial="Salon", slug="salon", email="geo@example.com", categorias=["salon"]))
        assert proveedor.geoname_id == 3838859 and proveedor.codigo_pais == "AR"
        en_salon, _ = crear_evento(db, EventoCreate(nombre="En salon", slug="en-salon", email="geo@example.com",
                                                   lugar_tipo="salon", salon_slug="salon"))
        assert en_salon.geoname_id == proveedor.geoname_id and en_salon.latitud == proveedor.latitud
        exacto = resolver_geografia(db, {**datos, "latitud": -51.7, "longitud": -69.3})
        assert exacto["latitud"] == -51.7
        manual = resolver_geografia(db, {"localidad": "Pueblo no catalogado", "provincia": "Santa Cruz", "pais": "Argentina", "geoname_id": None})
        assert manual["geoname_id"] is None
        legacy = Evento(nombre="Antiguo", slug="antiguo", propietario_id=evento.propietario_id,
                        localidad="Texto antiguo", provincia="Provincia antigua", pais="Pais antiguo")
        db.add(legacy); db.commit()
        assert evento_a_read(legacy).geoname_id is None and legacy.localidad == "Texto antiguo"


def test_preferencia_geografica_y_rechazo_de_id_inexistente(catalogo):
    from fastapi import HTTPException

    engine, _, _ = catalogo
    with Session(engine) as db:
        usuario = User(email="preferencia@example.com")
        db.add(usuario); db.commit()
        preferencia = upsert_preference(db, user_id=usuario.id, data=UserLocationPreferenceUpsert(
            geoname_id=3838859, localidad="Texto no confiable", pais="Otro", origen="MANUAL"))
        assert preferencia.localidad == "Río Gallegos" and preferencia.codigo_pais == "AR"
        assert preferencia.latitud == -51.62 and preferencia.geoname_id == 3838859
        with pytest.raises(HTTPException) as error:
            resolver_geografia(db, {"geoname_id": 999999999})
        assert error.value.status_code == 422
