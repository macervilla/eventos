# URLs publicas definitivas

Eventos y proveedores comparten `https://acersistemas.site/eventos/{slug}`.
React usa `/:slug` porque BrowserRouter ya tiene el basename `/eventos/`.
`GET /publico/{slug}` en FastAPI consulta `slugs_publicos`, devuelve el tipo
y React reutiliza EventPublicPage o ProviderPublicPage. Los endpoints de datos
conservan sus controles de actividad, permisos y visibilidad de borradores.
Un slug inexistente devuelve 404 y el frontend muestra la pagina 404.

Las invitaciones personales usan `/eventos/{slug}/i/{token}`; album,
invitados, acceso-equipo y control-ingreso cuelgan del mismo slug.
Los enlaces nuevos de correos, WhatsApp, administracion y confirmacion usan
la estructura definitiva. Los QR de control de ingreso contienen credenciales
opacas, no URLs: conservan su mecanismo de validacion. Los archivos multimedia
y sus rutas de almacenamiento permanecen en su lugar.

Se eliminaron las rutas React con prefijos `p/` y `e/`, junto con los atajos
antiguos de edicion. Esas URLs dejan de ser paginas publicas; no hay redirecciones
ni compatibilidad para invitaciones o enlaces anteriores.

## Integridad y migracion

`0021_slugs_publicos` registra todos los slugs existentes, incluidos los de
entidades inactivas, sin cambiar IDs, relaciones, nombres ni slugs.
La clave primaria del registro central impide duplicados entre tipos.
Triggers PostgreSQL mantienen el registro dentro de la misma transaccion del
alta, incluso para SQL que no pasa por FastAPI, y bloquean cambios del slug
y del nombre original del evento. Una baja logica no libera el slug.

La migracion bloquea escrituras en ambas tablas mientras revisa y carga los datos.
Si encuentra duplicados o slugs reservados, informa slug, tipo e ID y aborta sin
renombrar ni eliminar registros. Alembic usa DDL transaccional PostgreSQL.
Un conflicto requiere una decision explicita sobre los datos antes de reintentar.

Las rutas reservadas incluyen admin, administracion, login, ingresar, api,
api-vps, eventos, proveedores, nuevo, media, assets, rtc, health, compartir,
acceso, geografia, ubicacion, interno, docs, redoc y openapi-json.

## Archivos principales

- `backend/alembic/versions/0021_slugs_publicos.py`: backfill, preflight y triggers.
- `backend/app/models/slugs.py`, `backend/app/api/publico.py`, `backend/app/main.py`:
  registro y resolvedor publico.
- `backend/app/services/proveedores.py`: validacion global e inmutabilidad.
- `backend/app/services/{acceso,email,agasajados,invitados_distribucion}.py` y
  `backend/app/api/{eventos,proveedores,compartir}.py`: enlaces generados.
- `frontend/src/App.tsx`, `frontend/src/pages/PublicPage.tsx`: rutas y resolucion.
- Paginas y componentes que enlazan eventos/proveedores, `frontend/vite.config.ts`:
  navegacion y metadatos de desarrollo/preview.
- `backend/tests/test_slugs_publicos*.py` y `scripts/verificar-urls-publicas-ui.py`:
  pruebas nuevas; fixtures y scripts de UI existentes actualizados a las rutas nuevas.

## Despliegue VPS

Usar las variables existentes; `FRONTEND_PUBLIC_URL` debe ser
`https://acersistemas.site/eventos` y el build debe usar `--base=/eventos/`.
Desde `/var/www/eventos`, con la funcion `dc` de `despliegue-vps.md`:

```bash
dc build backend
dc stop backend
dc run --rm backend alembic upgrade head
dc run --rm frontend-build
dc up -d backend
nginx -t && systemctl reload nginx
```

Ejecutar cada paso solo si el anterior termina correctamente. Si la migracion
informa conflictos, detener el despliegue y revisar los registros indicados.
No ejecutar eliminaciones de volumenes ni downgrade como parte del despliegue.

El fallback SPA de `docs/nginx.eventos.conf` ya sirve `/eventos/{slug}`.
No hacen falta nuevas reglas de proxy o redireccion. Si el VPS tiene reglas
personalizadas para `p/` o `e/`, quitarlas al actualizar ese archivo.

Verificar una pagina de cada tipo, una invitacion nueva, el album, un slug
inexistente y que las URLs anteriores muestren pagina no encontrada.

## Pruebas reproducibles

```powershell
cd backend
$env:DATABASE_URL = 'postgresql+psycopg://usuario:clave@localhost/base_pruebas'
$env:SLUG_TEST_DATABASE_URL = $env:DATABASE_URL
python -m pytest -q
cd ../frontend
npm run build -- --base=/eventos/
```

Las pruebas PostgreSQL de slugs crean y eliminan exclusivamente schemas
`test_slugs_<uuid>` en la base de pruebas. Comprueban migracion, rollback ante
conflictos, proteccion SQL y altas simultaneas entre tipos y dentro de cada tipo.
Para la UI, iniciar `npm run preview -- --host 127.0.0.1 --port 5187 --base=/eventos/`
desde frontend y ejecutar `python scripts/verificar-urls-publicas-ui.py` desde la raiz;
sus APIs son simuladas y no envian correos.

Validacion realizada: suite completa con PostgreSQL temporal, 228 pruebas aprobadas
y 8 omitidas por sus condiciones de entorno; las 33 pruebas nuevas de slugs pasaron.
`alembic upgrade head` completo sobre PostgreSQL temporal y build con base
`/eventos/` correctos. Prueba UI aprobada en escritorio y movil: ambos tipos,
navegacion entre paginas, recarga y 404 sin redireccion para prefijos anteriores.
