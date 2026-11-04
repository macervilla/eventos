# Autocompletado mundial GeoNames

## Arquitectura

React consulta exclusivamente FastAPI. `/geografia/localidades` busca en el
PostgreSQL existente de Eventos, mediante SQL parametrizado y sin llamadas a
Internet. En el VPS la URL publica es
`https://acersistemas.site/eventos/api/geografia/localidades?q=rio%20ga`.
El modo localhost con API del VPS usa el mismo catalogo.

Se reviso el VPS antes de modificarlo: contenedor `eventos-db-1`, PostgreSQL 16,
base `eventos`, esquema operativo `public`, revision previa
`0012_email_compartido`. El 31/10/2026 habia unos 78 GiB de disco libre y
2 GiB de memoria disponible. No se usa MySQL ni Redis de otros proyectos.
No se modifican puertos ni se instala otro servidor de base de datos.

## Esquema y compatibilidad

La migracion `0013_geografia` crea:

- `geo_paises`: codigo ISO, nombre original y normalizado.
- `geo_provincias`: ID `pais.admin1`, codigo administrativo textual y nombres.
- `geo_subdivisiones`: ID `pais.admin1.admin2` y referencias administrativas.
- `geo_localidades`: ID GeoNames, nombres, codigos textuales, coordenadas,
  poblacion, feature code y estado.
- `geo_nombres`: nombres oficiales, ASCII y variantes normalizadas por localidad.
- `geo_importaciones`: fechas, version del importador, fuentes con SHA256,
  cantidades, estado y errores.

Activa `pg_trgm`, crea un indice B-tree `varchar_pattern_ops` para prefijos y
un indice GIN `gin_trgm_ops` para coincidencias internas. Las claves primarias
impiden duplicar IDs y variantes. Hay claves foraneas entre localidades, paises,
provincias y subdivisiones cuando GeoNames provee una correspondencia.

Anade solamente `geoname_id` (FK opcional) y `codigo_pais` a `eventos`,
`proveedores` y `user_location_preferences`. Los valores existentes quedan
intactos, con ID nulo; no se asignan coincidencias ambiguas. Se revisaron antes
los tipos y longitudes de los campos operativos. La fuente inicial cabe en ellos
(nombre de localidad maximo 97 caracteres y provincia maximo 50).

Los textos de una seleccion se resuelven de nuevo desde PostgreSQL al guardar,
para no confiar en un ID combinado con nombres manipulados. La direccion y el
pin exacto se mantienen separados del centro geografico: solo se usan las
coordenadas del catalogo como valor inicial cuando faltan ambas coordenadas.
No se modifican slugs ni nombres de eventos. La carga manual guarda ID nulo.

## Fuentes y licencia

Fuentes oficiales: https://download.geonames.org/export/dump/

Primera descarga: `countryInfo.txt`, `admin1CodesASCII.txt`, `admin2Codes.txt`,
`cities500.zip`. No se usa cities15000. La descarga registra fecha UTC,
Last-Modified, URL, tamano y SHA256 en `manifest.json`; ese manifiesto tambien
se conserva en `geo_importaciones.fuentes`.

El archivo cities500 tiene las variantes en su columna `alternatenames`.
Se importan esas variantes por fila sin cargar todo el fichero en memoria.
Esto permite nombres sin acentos, transliteraciones y variantes internacionales.
Se evaluo alternateNamesV2: no se descarga inicialmente porque duplicaria buena
parte de esas variantes y agregaria un volumen innecesario; seria util para
elegir etiquetas preferidas por idioma, no necesario para esta primera busqueda.

Fuente inicial descargada el 31/10/2026: 236.857 localidades, 252 paises,
3.865 divisiones admin1, 47.762 divisiones admin2 y 1.141.832 nombres normalizados.
Estos numeros se obtuvieron de una importacion real; consultar `status` para
la version efectivamente cargada en produccion y su tamano.

Datos GeoNames, CC BY 4.0: https://www.geonames.org/ y
https://creativecommons.org/licenses/by/4.0/ . El componente muestra atribucion.
Se conservan los nombres de paises/provincias tal como vienen en las fuentes;
no se inventan traducciones. No hay costos por consulta local.

## Importador

El comando es `python -m app.cli.geonames` con subcomandos `download`, `import`,
`status` y `benchmark`. No se ejecuta al arrancar FastAPI ni al construir Docker.

La lectura es en streaming desde ZIP. Se validan estructura, IDs, coordenadas,
poblacion y checksum. Se filtra exclusivamente feature class `P` para localidades
pobladas, sin filtro adicional por poblacion. Se usa PostgreSQL COPY a tablas
temporales, un archivo temporal para variantes y upserts dentro de una sola
transaccion. Un advisory lock impide dos importaciones simultaneas. Un error
revierte todos los cambios del catalogo y deja registrado el intento fallido.
Los upserts omiten actualizaciones sin cambios. No se mantienen todas las
localidades ni todos los alias en RAM. Solo se conservan los pequenos conjuntos
de codigos de pais, provincia y subdivision para validar relaciones.

La actualizacion conserva localidades y variantes historicas ausentes de nuevas
fuentes, con sus IDs y relaciones. No se borran filas utilizadas por Eventos.
Los lectores siguen viendo el catalogo anterior hasta confirmar la transaccion.
El limite de espera de locks es 5 segundos; no se bloquean tablas operativas
durante la importacion. Los archivos fuente no se incorporan a imagenes Docker;
se montan solo en el comando de administracion.

## Procedimiento exacto en el VPS

Desde `/var/www/eventos`, con los archivos de esta actualizacion ya subidos:

```bash
cd /var/www/eventos
bash scripts/geografia-vps.sh preflight
bash scripts/geografia-vps.sh backup
docker compose --env-file .env.vps -f compose.vps.yml build backend
bash scripts/geografia-vps.sh migrate
bash scripts/geografia-vps.sh download
bash scripts/geografia-vps.sh import
docker compose --env-file .env.vps -f compose.vps.yml up -d backend
docker compose --env-file .env.vps -f compose.vps.yml run --rm frontend-build
bash scripts/geografia-vps.sh status
bash scripts/geografia-vps.sh benchmark
```

Ejecutar cada comando solo si el anterior termina bien. `backup` guarda un
pg_dump custom en `/var/backups/eventos`, fuera del sitio publico y con permisos
privados; comprueba TOC, lectura completa mediante pg_restore sin conexion a
la base activa, presencia de tablas principales y SHA256. La migracion y la
importacion rechazan continuar sin respaldo verificado de menos de 24 horas.
Los scripts tambien inspeccionan esquemas y recursos y requieren como minimo
2 GiB de disco libre y 512 MiB de memoria disponible. Para catalogos mayores,
revisar de nuevo espacio y tiempos; esos minimos no estiman allCountries.

Para una actualizacion posterior:

```bash
bash scripts/geografia-vps.sh backup
bash scripts/geografia-vps.sh download
bash scripts/geografia-vps.sh import
bash scripts/geografia-vps.sh status
bash scripts/geografia-vps.sh benchmark
```

No es necesario reiniciar el backend despues de actualizar solo el catalogo.
No hay una tarea diaria programada.

Para ampliar cobertura con localidades de un pais por debajo de la cobertura
de cities500 (por ejemplo Argentina), despues del respaldo:

```bash
bash scripts/geografia-vps.sh download --cities cities500.zip AR.zip
bash scripts/geografia-vps.sh import --cities cities500.zip AR.zip
```

Tambien se admite `--cities allCountries.zip`, previo dimensionamiento. El mismo
filtro `P` evita importar montanas, rios u otros accidentes geograficos.

## API

`GET /geografia/localidades?q=rio%20ga&limit=10&codigo_pais=AR`.
El filtro ISO es opcional. Minimo 3 caracteres normalizados, maximo 100 de entrada,
10 resultados por defecto. Maximo 30, configurable con `GEO_MAX_RESULTADOS` (10 a
100). Primero se consultan prefijos, con nombres exactos/oficiales antes que
alias, luego poblacion y un desempate estable; se completa con coincidencias
internas indexadas si faltan resultados. Cada resultado incluye ID, localidad,
provincia, pais, ISO y coordenadas. No se eliminan localidades pequenas.

`GET /geografia/localidades/{geoname_id}` recupera la seleccion exacta para centrar
el mapa. El endpoint previo `/ubicacion/geocodificar` conserva su formato de
respuesta, ahora con centros locales y `precision=localidad`, sin consultar
Nominatim. El boton indica "Ubicar localidad en el mapa". GeoNames no resuelve
calles ni numeros: la direccion exacta se escribe y se ajusta con el marcador.
Los mapas visuales (teselas OSM/embebidos Google) y la resolucion de enlaces
compartidos Google Maps siguen siendo funcionalidades externas independientes;
ninguna se consulta para autocompletar localidades.

## Formularios

- Alta de eventos y edicion de ubicacion: `SelectorLugar` (modo Mi casa).
- Eventos en salones: heredan la referencia geografica del proveedor seleccionado.
- Alta de proveedores y ventana de edicion de ubicacion.
- Ubicacion habitual de consulta del portal: `LocationSelector`.
- Filtro de localidades en la busqueda de proveedores.
- Preferencia de ubicacion de usuario en la API: conserva referencia y coordenadas.

El selector consulta con debounce de 300 ms, admite flechas/Enter/Escape, muestra
estado de carga, ausencia de resultados y errores. AbortController y un numero
de secuencia impiden que respuestas antiguas sustituyan las nuevas. Modificar
el nombre invalida ID e ISO anteriores. La alternativa manual es explicita y
no inventa IDs. Los datos historicos se muestran como texto y pueden asociarse
posteriormente mediante una seleccion.

## Pruebas

```bash
# Solo contra PostgreSQL de pruebas; cada prueba usa un esquema aislado.
GEO_TEST_DATABASE_URL=postgresql+psycopg://... python -m pytest tests/test_geografia.py tests/test_administracion.py -q
```

Pruebas de importacion, reimportacion, codigos con ceros, homonimos internacionales,
prefijos/acentos, alias Unicode, pueblos pequenos, rollback, checksum corrupto,
busqueda con red deshabilitada, entradas invalidas, persistencia de ID/ISO y
coordenadas, datos historicos, conservacion de pins y referencias ausentes.

Con el frontend local iniciado:

```bash
python scripts/verificar-geografia-ui.py
```

El navegador usa API y mapas simulados: prueba teclado, debounce, respuestas
antiguas, autocompletado, payload persistido, invalidacion de seleccion, modo
manual y ancho movil. No crea eventos ni envia correos reales.

La carga completa de prueba se importo y reimporto sin duplicar: 236.857
localidades y 1.141.832 variantes. El catalogo inicial con indices ocupo unos
256 MiB en PostgreSQL de prueba; usar el informe de produccion para mediciones
reales. La migracion es aditiva y el backend anterior sigue siendo compatible
con las columnas nuevas, lo que permite restaurar una imagen anterior sin
borrar los datos geograficos. El downgrade destructivo esta deshabilitado.

## Archivos principales

Backend: `models/geografia.py`, `schemas/geografia.py`, `services/geografia.py`,
`api/geografia.py`, `cli/geonames.py`, migracion `0013_geografia.py`; integraciones
en modelos/esquemas/servicios de eventos, proveedores y preferencias, router y
configuracion. Frontend: `LocalidadAutocomplete.tsx`, `SelectorLugar.tsx`,
`EdicionEvento.tsx`, `EdicionProveedor.tsx`, `ProviderFormPage.tsx`,
`LocationSelector.tsx`, `ProveedoresPage.tsx`, tipos y estilos. Administracion:
`scripts/geografia-vps.sh`; pruebas: `tests/test_geografia.py` y script UI.
