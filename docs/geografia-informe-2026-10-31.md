# Entrega GeoNames — 31/10/2026

Implementado y desplegado en https://acersistemas.site/eventos/ . El frontend
local usa la misma API y el mismo catalogo del VPS.

## Base existente y proteccion de datos

- Contenedor: `eventos-db-1`, PostgreSQL 16. Base `eventos`, esquema `public`.
- Migracion aplicada: `0012_email_compartido` a `0013_geografia`.
- No se instalaron otras bases ni se cambiaron puertos o servicios de otros proyectos.
- Antes: 78 GiB de disco libre y unos 2 GiB de memoria disponible.
- Respaldo: `/var/backups/eventos/eventos-20261031T230605Z.dump`.
  Verificado por TOC, lectura completa del archivo comprimido con pg_restore y SHA256.
- Tambien se guardaron fuentes e ID de imagen anteriores en `/var/backups/eventos/`.
- Las cantidades de registros operativos coinciden con el respaldo: 2 usuarios,
  1 proveedor, 0 eventos y 0 preferencias. No se crearon datos de prueba en produccion.

## Datos importados

Descarga administrativa en Docker del VPS: 31/10/2026, 20:11:52–20:11:58
(America/Buenos_Aires). Importacion: 20:12:00–20:13:41, unos 101 segundos.
Version del importador: `geonames-1`. Fuentes oficiales:
https://download.geonames.org/export/dump/ . Archivo principal `cities500.zip`.

| Tabla / dato | Cantidad |
|---|---:|
| Paises y territorios | 252 |
| Provincias / divisiones admin1 | 3.865 |
| Subdivisiones admin2 | 47.762 |
| Localidades | 236.857 |
| Nombres y variantes normalizados | 1.141.832 |
| Registros omitidos por pais desconocido | 0 |

Tamano del catalogo con indices: 268.689.408 bytes, aproximadamente 256 MiB.
Memoria observada del contenedor PostgreSQL al finalizar: unos 201 MiB.

Los archivos tienen fecha de fuente 31/10/2026. URL, Last-Modified, fecha de
descarga y SHA256 estan en `/var/www/eventos/geonames/manifest.json` y en
`geo_importaciones.fuentes`. El ZIP principal ocupa 13.912.998 bytes.
No se importo alternateNamesV2; se usan las variantes incluidas en cities500.
Se puede ampliar por pais, sin filtro adicional de poblacion ni borrados.

## Tablas e indices

Se crearon `geo_paises`, `geo_provincias`, `geo_subdivisiones`, `geo_localidades`,
`geo_nombres` y `geo_importaciones`, con claves primarias y foraneas.
Extension `pg_trgm`, indice B-tree `ix_geo_nombres_prefijo` e indice GIN
`ix_geo_nombres_trgm`. En tablas operativas solo se agregaron dos columnas
opcionales: `geoname_id` y `codigo_pais`, en eventos, proveedores y preferencias.
Los registros antiguos no se asociaron automaticamente.

## Rendimiento medido en el VPS

Diez ejecuciones por consulta, desde el backend del servidor, incluyendo la
primera lectura; no incluye latencia HTTP de Internet:

| Consulta | Media | Maximo observado |
|---|---:|---:|
| `rio ga` | 12,04 ms | 76,48 ms |
| `rio gr` | 1,85 ms | 2,90 ms |
| `cordoba` | 1,70 ms | 2,35 ms |
| `san jose` | 4,04 ms | 6,83 ms |

Comprobado contra la API publica y desde localhost:

```text
rio ga → Río Gallegos, Santa Cruz, Argentina
ID: 3838859, ISO: AR, centro: -51.6253, -69.25229
rio gr + codigo_pais=AR → Río Grande, Tierra del Fuego, Argentina
```

La busqueda sin filtro es mundial: por ejemplo `rio gr` tambien muestra Rio
Grande de Brasil segun su poblacion, sin excluir la localidad argentina.
Los nombres de paises y provincias conservan las etiquetas originales de GeoNames.

## Formularios y pruebas

Integrados: alta/edicion de eventos en domicilio, herencia de localidad de
salones, alta y edicion de proveedores, ubicacion habitual del portal, filtro de
proveedores y persistencia de preferencias en la API.

Pruebas PostgreSQL y administracion: 22 casos. Incluyen primera importacion,
reimportacion sin duplicados, errores con rollback, checksum, Unicode/acentos,
homonimos internacionales, pueblos pequenos, ID/ISO/coordenadas, preferencias,
salones, datos antiguos, pin exacto e Internet deshabilitado para las busquedas.

Navegador: debounce, minimo de caracteres, respuestas desordenadas, teclado,
seleccion, autocompletado de provincia/pais, payload persistido, invalidacion
del ID al editar, modo manual y ancho movil. API y mapas simulados en pruebas
de escritura, sin enviar correos. Ademas se verifico la seleccion con la API
real en el VPS y localhost, y el alta de proveedores, sin guardar formularios.

Se importo y reimporto el catalogo mundial completo en PostgreSQL de pruebas:
236.857 localidades y 1.141.832 variantes, sin duplicados.
Compilacion TypeScript/Vite completada y revision Ruff de los modulos nuevos.

## Administracion posterior

No se necesitan variables nuevas obligatorias ni cambios de Compose. El maximo
de resultados se puede ajustar mediante `GEO_MAX_RESULTADOS`; el valor por
defecto es 30 y la consulta devuelve 10 por defecto.

```bash
cd /var/www/eventos
bash scripts/geografia-vps.sh backup
bash scripts/geografia-vps.sh download
bash scripts/geografia-vps.sh import
bash scripts/geografia-vps.sh status
bash scripts/geografia-vps.sh benchmark
```

La importacion no requiere reiniciar el backend. No hay descarga en el arranque
ni tarea automatica diaria. La informacion persiste en el volumen PostgreSQL
existente. Los comandos rechazan migrar/importar sin respaldo verificado reciente.

Detalle de archivos, arquitectura, ampliacion por pais, comandos, indices y
limites: [guia tecnica](geografia-geonames.md). La geografia local identifica la
localidad; no geocodifica calle y numero. El pin preciso se ajusta en el mapa.
