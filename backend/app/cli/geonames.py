"""python -m app.cli.geonames {download,import,status,benchmark} --help"""
import argparse
import hashlib
import io
import json
import logging
import math
import re
import shutil
import tempfile
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.geografia import GeoImportacion
from app.services.geografia import buscar_localidades, normalizar

BASE = "https://download.geonames.org/export/dump/"
VERSION = "geonames-1"
LOG = logging.getLogger("geonames")
ADMIN_FILES = ("countryInfo.txt", "admin1CodesASCII.txt", "admin2Codes.txt")
COLUMNS = {
    "geo_paises": "codigo_iso,nombre,nombre_normalizado",
    "geo_provincias": "id,codigo_pais,codigo_administrativo,nombre,nombre_normalizado",
    "geo_subdivisiones": "id,codigo_pais,provincia_id,codigo_administrativo,nombre",
    "geo_localidades": "geoname_id,nombre,nombre_ascii,nombre_normalizado,codigo_pais,codigo_provincia,codigo_subdivision,provincia_id,subdivision_id,latitud,longitud,poblacion,feature_code,activo",
    "geo_nombres": "geoname_id,nombre_normalizado",
}


def utcnow():
    return datetime.now(UTC)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_name(value):
    if value in ("cities500.zip", "allCountries.zip") or re.fullmatch(r"[A-Z]{2}\.zip", value):
        return value
    raise argparse.ArgumentTypeError("Usar cities500.zip, allCountries.zip o un codigo de pais como AR.zip")


def download(directory: Path, cities: list[str]):
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"version": VERSION, "descargado": utcnow().isoformat(), "files": {}}
    for name in [*ADMIN_FILES, *cities]:
        path = directory / name
        temporary = directory / (name + ".part")
        LOG.info("Descargando %s", name)
        try:
            with urlopen(Request(BASE + name, headers={"User-Agent": "Eventos-GeoNames-Import/1.0"}), timeout=120) as response:
                expected = int(response.headers.get("Content-Length", 0))
                if expected and shutil.disk_usage(directory).free < expected * 2 + 512 * 1024**2:
                    raise ValueError("Espacio insuficiente para descargar y procesar " + name)
                written = 0
                with temporary.open("wb") as output:
                    while chunk := response.read(1024 * 1024):
                        written += len(chunk)
                        if written > 4 * 1024**3:
                            raise ValueError("Archivo excede el limite administrativo de 4 GiB")
                        output.write(chunk)
                if expected and written != expected:
                    raise ValueError("Descarga incompleta: " + name)
                modified = response.headers.get("Last-Modified")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        manifest["files"][name] = {"url": BASE + name, "sha256": digest(path), "bytes": path.stat().st_size,
                                    "descargado": utcnow().isoformat(), "last_modified": modified}
    target = directory / "manifest.json"
    target.with_suffix(".tmp").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    target.with_suffix(".tmp").replace(target)
    return manifest


def lines(path: Path, member=None):
    if member:
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo(member)
            if info.file_size > 16 * 1024**3:
                raise ValueError("Archivo descomprimido demasiado grande")
            with archive.open(info) as binary, io.TextIOWrapper(binary, encoding="utf-8") as stream:
                for number, line in enumerate(stream, 1):
                    yield number, line.rstrip("\r\n").split("\t")
    else:
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if line.strip() and not line.startswith("#"):
                    yield number, line.rstrip("\r\n").split("\t")


def checked_manifest(directory, cities):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for name in [*ADMIN_FILES, *cities]:
        entry = manifest["files"].get(name)
        if not entry or entry["sha256"] != digest(directory / name):
            raise ValueError("Falta archivo o no coincide SHA256: " + name)
    return manifest


def import_catalog(engine, directory: Path, cities: list[str], min_free_gib=2):
    if engine.dialect.name != "postgresql":
        raise ValueError("El importador requiere el PostgreSQL existente de Eventos")
    manifest = checked_manifest(directory, cities)
    # El staging de alias usa disco temporal; nunca se mantiene el catalogo en RAM.
    if shutil.disk_usage(tempfile.gettempdir()).free < min_free_gib * 1024**3:
        raise ValueError("Espacio temporal insuficiente para staging geografico")
    with Session(engine) as db:
        job = GeoImportacion(iniciada=utcnow(), estado="iniciada", version=VERSION, fuentes=manifest)
        db.add(job)
        db.commit()
        job_id = job.id
    counts = {"registros_leidos": 0, "localidades_procesadas": 0, "sin_pais": 0}
    try:
        with engine.begin() as conn:
            if not conn.scalar(text("SELECT pg_try_advisory_xact_lock(724280013)")):
                raise ValueError("Ya hay una importacion geografica en curso")
            conn.execute(text("SET LOCAL lock_timeout='5s'"))
            for table in COLUMNS:
                conn.execute(text(f"CREATE TEMP TABLE stage_{table} (LIKE {table} INCLUDING DEFAULTS) ON COMMIT DROP"))
            conn.execute(text("ALTER TABLE stage_geo_localidades ADD COLUMN orden BIGSERIAL"))
            countries, provinces, subdivisions = set(), set(), set()
            cursor = conn.connection.driver_connection.cursor()
            with cursor.copy(f"COPY stage_geo_paises ({COLUMNS['geo_paises']}) FROM STDIN") as copy:
                for n, row in lines(directory / "countryInfo.txt"):
                    if len(row) < 19 or not re.fullmatch(r"[A-Z]{2}", row[0]) or not row[4]:
                        raise ValueError(f"countryInfo.txt:{n}: estructura invalida")
                    countries.add(row[0])
                    copy.write_row((row[0], row[4], normalizar(row[4])))
            with cursor.copy(f"COPY stage_geo_provincias ({COLUMNS['geo_provincias']}) FROM STDIN") as copy:
                for n, row in lines(directory / "admin1CodesASCII.txt"):
                    if len(row) != 4 or "." not in row[0]:
                        raise ValueError(f"admin1CodesASCII.txt:{n}: estructura invalida")
                    country, code = row[0].split(".", 1)
                    if country in countries:
                        provinces.add(row[0])
                        copy.write_row((row[0], country, code, row[1], normalizar(row[1])))
            with cursor.copy(f"COPY stage_geo_subdivisiones ({COLUMNS['geo_subdivisiones']}) FROM STDIN") as copy:
                for n, row in lines(directory / "admin2Codes.txt"):
                    parts = row[0].split(".")
                    if len(row) != 4 or len(parts) < 3:
                        raise ValueError(f"admin2Codes.txt:{n}: estructura invalida")
                    if parts[0] in countries:
                        subdivisions.add(row[0])
                        province = ".".join(parts[:2])
                        copy.write_row((row[0], parts[0], province if province in provinces else None, ".".join(parts[2:]), row[1]))
            with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", newline="\n") as aliases:
                with cursor.copy(f"COPY stage_geo_localidades ({COLUMNS['geo_localidades']}) FROM STDIN") as copy:
                    for name in cities:
                        for n, row in lines(directory / name, name.removesuffix(".zip") + ".txt"):
                            counts["registros_leidos"] += 1
                            if len(row) != 19:
                                raise ValueError(f"{name}:{n}: se esperaban 19 columnas")
                            if row[6] != "P":
                                continue
                            if row[8] not in countries:
                                counts["sin_pais"] += 1
                                continue
                            geoid, lat, lng, pop = int(row[0]), float(row[4]), float(row[5]), int(row[14] or 0)
                            if geoid <= 0 or not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180 or pop < 0:
                                raise ValueError(f"{name}:{n}: identificador, poblacion o coordenadas invalidas")
                            if not row[1] or len(row[1]) > 200 or len(row[2]) > 200:
                                raise ValueError(f"{name}:{n}: nombre invalido")
                            province = row[8] + "." + row[10]
                            subdivision = province + "." + row[11]
                            copy.write_row((geoid, row[1], row[2], normalizar(row[1]), row[8], row[10], row[11] or None,
                                province if province in provinces else None, subdivision if subdivision in subdivisions else None,
                                lat, lng, pop, row[7], True))
                            for alias in {normalizar(v) for v in [row[1], row[2], *row[3].split(",")] if v}:
                                if alias and len(alias) <= 400:
                                    aliases.write(f"{geoid}\t{alias}\n")
                            counts["localidades_procesadas"] += 1
                            if counts["localidades_procesadas"] % 25000 == 0:
                                LOG.info("Localidades procesadas: %d", counts["localidades_procesadas"])
                aliases.seek(0)
                with cursor.copy(f"COPY stage_geo_nombres ({COLUMNS['geo_nombres']}) FROM STDIN") as copy:
                    while chunk := aliases.read(1024 * 1024):
                        copy.write(chunk)
            if not counts["localidades_procesadas"]:
                raise ValueError("La fuente no contiene localidades pobladas; no se actualizo el catalogo")
            for table, columns in COLUMNS.items():
                cols = columns.split(",")
                if table == "geo_nombres":
                    conn.execute(text(f"INSERT INTO {table} ({columns}) SELECT DISTINCT {columns} FROM stage_{table} ON CONFLICT DO NOTHING"))
                else:
                    key = cols[0]
                    update = ",".join(f"{col}=EXCLUDED.{col}" for col in cols[1:])
                    changed = "(" + ",".join(f"{table}.{col}" for col in cols[1:]) + ") IS DISTINCT FROM (" + ",".join(f"EXCLUDED.{col}" for col in cols[1:]) + ")"
                    source = f"SELECT DISTINCT ON ({key}) {columns} FROM stage_{table} ORDER BY {key}"
                    if table == "geo_localidades":
                        source += ",orden DESC"
                    conn.execute(text(f"INSERT INTO {table} ({columns}) {source} ON CONFLICT ({key}) DO UPDATE SET {update} WHERE {changed}"))
            # Se conservan localidades/alias ausentes de futuras descargas: referencias historicas intactas.
            for table in COLUMNS:
                conn.execute(text(f"ANALYZE {table}"))
            counts.update({table: conn.scalar(text(f"SELECT count(*) FROM {table}")) for table in COLUMNS})
            conn.execute(text("UPDATE geo_importaciones SET estado='completada', finalizada=:fecha, cantidades=CAST(:counts AS json) WHERE id=:id"),
                         {"fecha": utcnow(), "counts": json.dumps(counts), "id": job_id})
        return counts
    except Exception as exc:
        # Una conexion distinta conserva el diagnostico aun cuando el catalogo vuelve atras.
        with engine.begin() as conn:
            conn.execute(text("UPDATE geo_importaciones SET estado='fallida', finalizada=:fecha, error=:error WHERE id=:id"),
                         {"fecha": utcnow(), "error": type(exc).__name__ + ": " + str(exc).split("\n")[0][:400], "id": job_id})
        raise


def status(engine):
    with engine.connect() as conn:
        counts = {t: conn.scalar(text(f"SELECT count(*) FROM {t}")) for t in COLUMNS}
        counts["bytes"] = conn.scalar(text("SELECT sum(pg_total_relation_size(oid)) FROM pg_class WHERE relname LIKE 'geo_%' AND relkind='r'"))
        counts["ultima_importacion"] = dict(conn.execute(text("SELECT id,iniciada,finalizada,estado,version,cantidades FROM geo_importaciones ORDER BY id DESC LIMIT 1")).mappings().first() or {})
    return counts


def benchmark(engine):
    measures = {}
    with Session(engine) as db:
        for q in ("rio ga", "rio gr", "cordoba", "san jose"):
            times = []
            rows = []
            for _ in range(10):
                start = time.perf_counter()
                rows = buscar_localidades(db, q)
                times.append((time.perf_counter() - start) * 1000)
            measures[q] = {"media_ms": round(sum(times) / len(times), 2), "max_ms": round(max(times), 2),
                           "resultados": len(rows), "primero": rows[0] if rows else None}
    return measures


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["download", "import", "status", "benchmark"])
    parser.add_argument("--directory", type=Path, default=Path("/data"))
    parser.add_argument("--cities", type=source_name, nargs="+", default=["cities500.zip"])
    args = parser.parse_args()
    try:
        if args.command == "download":
            result = download(args.directory, args.cities)
        else:
            engine = create_engine(settings.database_url, pool_pre_ping=True)
            if args.command == "import":
                result = import_catalog(engine, args.directory, args.cities)
            else:
                result = status(engine) if args.command == "status" else benchmark(engine)
            engine.dispose()
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    except Exception as exc:
        LOG.error("Proceso detenido (%s). %s", type(exc).__name__, str(exc) if isinstance(exc, ValueError) else "Revisar geo_importaciones y los archivos de entrada.")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
