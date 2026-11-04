#!/usr/bin/env bash
# Solo Eventos. No inicia servidores de base de datos ni cambia puertos.
set -euo pipefail
cd "$(dirname "$0")/.."
dc() { docker compose --env-file .env.vps -f compose.vps.yml "$@"; }
backups="${EVENTOS_BACKUP_DIR:-/var/backups/eventos}"

preflight() {
  dc ps
  df -h .
  free -m
  local libres memoria
  libres=$(df -Pk . | awk 'NR==2 {print $4}')
  memoria=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
  if (( libres < 2097152 || memoria < 524288 )); then
    echo "Se requieren al menos 2 GiB libres y 512 MiB disponibles antes de importar." >&2
    exit 1
  fi
  dc exec -T db sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT current_database(), current_schema(), pg_size_pretty(pg_database_size(current_database()));
SELECT schema_name FROM information_schema.schemata;
SELECT version_num FROM alembic_version;
SELECT extname FROM pg_extension;
SELECT table_name,column_name,data_type,character_maximum_length
FROM information_schema.columns WHERE table_schema='public'
AND table_name IN ('eventos','proveedores','user_location_preferences')
AND column_name IN ('localidad','provincia','pais','latitud','longitud','geoname_id','codigo_pais');
SQL
}

backup() {
  umask 077
  mkdir -p "$backups"
  local archivo="$backups/eventos-$(date -u +%Y%m%dT%H%M%SZ).dump"
  dc exec -T db sh -c 'pg_dump -Fc --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$archivo.part"
  test -s "$archivo.part"
  # Leer tambien el contenido comprimido completo, sin restaurar sobre la base activa.
  dc exec -T db pg_restore --list < "$archivo.part" > "$archivo.list"
  dc exec -T db pg_restore --file=/dev/null < "$archivo.part"
  grep -q 'TABLE DATA public users' "$archivo.list"
  grep -q 'TABLE DATA public eventos' "$archivo.list"
  mv "$archivo.part" "$archivo"
  sha256sum "$archivo" > "$archivo.sha256"
  printf '%s\n' "$archivo" > "$backups/ultimo-geografia.path"
  echo "Respaldo verificado: $archivo"
}

require_backup() {
  test -f "$backups/ultimo-geografia.path" || { echo "Ejecutar backup primero" >&2; exit 1; }
  local archivo edad
  archivo=$(cat "$backups/ultimo-geografia.path")
  test -f "$archivo" && test -f "$archivo.sha256"
  edad=$(( $(date +%s) - $(stat -c %Y "$archivo") ))
  (( edad < 86400 )) || { echo "El respaldo tiene mas de 24 h. Crear uno nuevo." >&2; exit 1; }
  sha256sum -c "$archivo.sha256"
}

case "${1:-}" in
  preflight) preflight ;;
  backup) preflight; backup ;;
  migrate) require_backup; dc run --rm --no-deps backend alembic upgrade head ;;
  download)
    preflight
    mkdir -p geonames
    shift
    dc run --rm --no-deps -v "$PWD/geonames:/data" backend python -m app.cli.geonames download --directory /data "$@"
    ;;
  import)
    preflight; require_backup
    shift
    dc run --rm --no-deps -v "$PWD/geonames:/data" backend python -m app.cli.geonames import --directory /data "$@"
    ;;
  status|benchmark) dc run --rm --no-deps backend python -m app.cli.geonames "$1" ;;
  *) echo "Uso: bash scripts/geografia-vps.sh {preflight|backup|migrate|download|import|status|benchmark} [--cities cities500.zip AR.zip]" >&2; exit 2 ;;
esac
