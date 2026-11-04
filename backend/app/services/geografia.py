import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models.geografia import GeoLocalidad, GeoNombre, GeoPais, GeoProvincia


def normalizar(valor: str) -> str:
    valor = "".join(c for c in unicodedata.normalize("NFKD", valor.casefold()) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", valor, flags=re.UNICODE).replace("_", " ").split())


def buscar_localidades(db: Session, consulta: str, limite: int = 10, codigo_pais: str | None = None) -> list[dict]:
    q = normalizar(consulta)
    if len(q) < 3:
        raise HTTPException(422, "Escribi al menos 3 caracteres de la localidad")
    patron = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    resultados = []
    for prefijo in (True, False):
        candidatos = select(GeoNombre.geoname_id).where(
            GeoNombre.nombre_normalizado.like(("" if prefijo else "%") + patron + "%", escape="\\")
        ).distinct().subquery()
        consulta_sql = (select(GeoLocalidad, GeoProvincia.nombre, GeoPais.nombre)
            .join(candidatos, GeoLocalidad.geoname_id == candidatos.c.geoname_id)
            .join(GeoPais, GeoLocalidad.codigo_pais == GeoPais.codigo_iso)
            .outerjoin(GeoProvincia, GeoLocalidad.provincia_id == GeoProvincia.id)
            .where(GeoLocalidad.activo.is_(True)))
        if codigo_pais:
            consulta_sql = consulta_sql.where(GeoLocalidad.codigo_pais == codigo_pais)
        if resultados:
            consulta_sql = consulta_sql.where(GeoLocalidad.geoname_id.not_in([r["geoname_id"] for r in resultados]))
        consulta_sql = consulta_sql.order_by(
            case((GeoLocalidad.nombre_normalizado == q, 0),
                 (GeoLocalidad.nombre_normalizado.like(patron + "%", escape="\\"), 1), else_=2),
            GeoLocalidad.poblacion.desc(), GeoLocalidad.nombre, GeoLocalidad.geoname_id,
        ).limit(limite - len(resultados))
        for localidad, provincia, pais in db.execute(consulta_sql):
            resultados.append({"geoname_id": localidad.geoname_id, "localidad": localidad.nombre,
                "provincia": provincia or "", "pais": pais, "codigo_pais": localidad.codigo_pais,
                "latitud": localidad.latitud, "longitud": localidad.longitud})
        if len(resultados) >= limite:
            break
    return resultados


def resolver_geografia(db: Session, valores: dict, existente=None) -> dict:
    """Canonicalizar selecciones; el texto manual/antiguo nunca obtiene un ID inventado."""
    valores = dict(valores)
    if "geoname_id" not in valores and existente is not None:
        if all(valores.get(c, getattr(existente, c)) == getattr(existente, c) for c in ("localidad", "provincia", "pais")):
            valores["geoname_id"] = existente.geoname_id
        else:
            valores["geoname_id"] = None
            valores["codigo_pais"] = None
    geoname_id = valores.get("geoname_id")
    if geoname_id is None:
        valores["geoname_id"] = None
        return valores
    fila = db.execute(select(GeoLocalidad, GeoProvincia.nombre, GeoPais.nombre)
        .join(GeoPais, GeoLocalidad.codigo_pais == GeoPais.codigo_iso)
        .outerjoin(GeoProvincia, GeoLocalidad.provincia_id == GeoProvincia.id)
        .where(GeoLocalidad.geoname_id == geoname_id)).first()
    if fila is None:
        raise HTTPException(422, "La localidad seleccionada no existe en el catalogo. Elegi otra o usa carga manual")
    lugar, provincia, pais = fila
    valores.update(geoname_id=lugar.geoname_id, localidad=lugar.nombre, provincia=provincia or "",
                   pais=pais, codigo_pais=lugar.codigo_pais)
    # El centro de localidad es un valor inicial, nunca reemplaza un pin/direccion exactos.
    if valores.get("latitud") is None and valores.get("longitud") is None and not valores.get("google_maps_url"):
        valores.update(latitud=lugar.latitud, longitud=lugar.longitud)
    return valores


def obtener_localidad(db: Session, geoname_id: int) -> dict:
    geo = resolver_geografia(db, {"geoname_id": geoname_id})
    return {c: geo[c] for c in ("geoname_id", "localidad", "provincia", "pais", "codigo_pais", "latitud", "longitud")}
