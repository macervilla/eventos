# Plataforma digital de eventos

Base técnica para una plataforma web/PWA de eventos con portal público, espacios permanentes, módulos activables, proveedores con página pública y búsqueda por cercanía.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, JWT-ready.
- Frontend: React, TypeScript, Vite, React Router, Axios.
- Infraestructura local: Docker Compose con PostgreSQL, Redis, backend y frontend.

## Ejecutar en desarrollo

```bash
cp .env.example .env
docker compose up -d --build frontend
```
//ssh -N -L 15433:172.19.0.2:5432 vps


git status
git add .
git commit -m "actualizo "
git push origin main

Backend: http://localhost:8009/docs  
Frontend: http://localhost:5179

Localhost usa siempre por defecto la API, los datos y las imagenes del VPS. Consultar
[localhost con API del VPS](docs/localhost-con-vps.md). Esta modalidad ejecuta
el frontend local y realiza las operaciones con el backend de produccion.

Aplicar migraciones:

```bash
docker compose exec backend alembic upgrade head
```

## Estructura

```text
backend/
  app/
    api/
    core/
    db/
    models/
    schemas/
    services/
  alembic/
frontend/
  src/
    api/
    components/
    pages/
    types/
```

## Modelo inicial

Entidades principales:

- `User`: identidad base para organizadores, invitados y proveedores.
- `Evento`: evento genérico con URL permanente, privacidad, estado, plan y ubicación propia.
- `EventoModulo`: módulos activables por evento con configuración JSON.
- `EventoUsuario`: roles por evento.
- `Invitacion` y `Participante`: confirmaciones y acompañantes.
- `OpcionEvento`: preferencias configurables por evento.
- `TemaMusical`, `Media`, `Publicacion`: módulos del MVP.
- `Proveedor`: negocio público con slug único, CUIT opcional, ubicación comercial compartible por Google Maps, plan, contacto, página pública y baja lógica.
- `CategoriaProveedor` y `ProveedorCategoriaLink`: categorías múltiples por proveedor.
- `ProveedorDominio`: dominio personalizado preparado para resolución futura por hostname.
- `UserLocationPreference`: ubicación habitual de consulta persistente.

## Portal y rutas públicas

```text
/                         Portal principal público
/proveedores              Búsqueda pública de proveedores
/proveedores/nuevo        Alta inicial de proveedor
/proveedores/{slug}/editar Redirige a /p/{slug}
/p/{slug}                 Página pública del proveedor (modo edición si el usuario la administra)
/eventos/nuevo            Alta de evento
/e/{slug}                 Página del evento (modo edición para su propietario)
```

La home separa los dos flujos principales:

```text
Quiero crear un evento
Quiero ser proveedor
```

## Acceso y sesión

El ingreso habitual se realiza seleccionando la cuenta de Google. La bienvenida
y validacion inicial por correo se registran una sola vez; la recuperacion por
email sigue siendo opcional. Todas las paginas incluyen controles de sesion.
Ver [flujo de acceso, cuentas externas y pruebas](docs/ingreso-google.md).

- Google: el backend verifica el token contra Google y, si el email administra algo, devuelve un JWT de sesión.
- Email manual: `POST /acceso/solicitar-enlace` envía un enlace mágico (vence en 30 min). Al abrirlo, `/ingresar?enlace=...` lo canjea en `POST /acceso/enlace` por el JWT de sesión.
- El frontend guarda el JWT en `localStorage` y lo envía como `Authorization: Bearer`.
- `PUT`/`DELETE /proveedores/{slug}` y la subida de media exigen sesión del dueño del proveedor.
- El dueño que entra a `/p/{slug}` ve íconos para cambiar la portada, editar datos y cambiar la ubicación en ventanas emergentes.
- Al guardar un enlace de Google Maps, el backend intenta extraer latitud/longitud (sigue enlaces cortos `maps.app.goo.gl`).

### Configurar el acceso con Google en desarrollo

La unica fuente del cliente OAuth es `GOOGLE_CLIENT_ID` en el `.env` de Eventos
(en la raiz). Copiar alli el ID real del cliente web **eventos**. No colocar el
Client Secret en React, Vite o el repositorio. Compose asigna explicitamente esta
variable al backend, evitando que se herede el ID de los archivos externos que
se conservan para el correo. Si falta, Google queda deshabilitado sin usar otro cliente.

El frontend obtiene el ID publico mediante `GET /acceso/google-config` en tiempo
de ejecucion. No usa `VITE_GOOGLE_CLIENT_ID` ni requiere recompilar para cambiar
el ID. `VITE_API_URL` si es una variable de Vite: se incorpora al ejecutar
`npm run build` (o al iniciar el servidor de desarrollo); cambiarla requiere
recompilar/reiniciar. Compose ejecuta Vite en desarrollo en el puerto 5179.

Se utiliza Google Identity Services (`google.accounts.id`) con boton oficial y
`ux_mode: popup`. La credencial recibida es un **ID token**, enviado como
`{ "credential": "..." }` a `POST /acceso/google`. El backend usa `google-auth`
para comprobar firma con certificados de Google, audiencia del cliente de Eventos,
emisor, fecha de emision y vencimiento, y exige email verificado y subject.
Se admite un desfase de relojes de 5 segundos mediante el parametro oficial
`clock_skew_in_seconds`. `GOOGLE_CLOCK_SKEW_SECONDS` permite ajustarlo entre 0 y
30 segundos; no se omiten las validaciones de emision ni vencimiento. Si el
desfase es mayor, sincronizar el reloj del equipo y de Docker. Los rechazos se
registran por categoria, sin guardar credenciales ni emails.
La sesion local se emite solo para usuarios activos con acceso. El flujo anterior
con `access_token` ya no se acepta. No se utiliza un Client Secret en este flujo.

En [Google Auth Platform > Clients](https://console.cloud.google.com/auth/clients),
seleccionar el cliente **eventos** cuyo ID coincida con `/acceso/google-config`.
Agregar en **Origenes autorizados de JavaScript**, sin rutas ni barra final:

```text
http://localhost:5179
```

Si tambien se navega con `127.0.0.1`, autorizar por separado:

```text
http://127.0.0.1:5179
```

Este popup usa un callback JavaScript: no requiere una URI de redireccionamiento
OAuth. `/ingresar` es la ruta de la aplicacion, no un origen ni una URI de callback
que haya que agregar. `http://localhost:8009` tampoco es el origen del frontend.
Si Google mantiene la app en modo de prueba y solicita usuarios de prueba, agregar
la cuenta correspondiente en **Audience / Test users**.

El error `origin_mismatch` indica que el origen del navegador no esta autorizado
para el Client ID efectivamente enviado. Configurar CORS en FastAPI no modifica
los origenes autorizados por Google.

Aplicar cambios (ya ejecutado durante la correccion):

```bash
docker compose up -d --build --force-recreate backend frontend
```

Despues de cambiar solo `GOOGLE_CLIENT_ID`, alcanza con recrear el backend y
recargar `/ingresar`:

```bash
docker compose up -d --force-recreate backend
```

Pruebas automaticas (no sustituyen un ingreso real con Google):

```bash
docker compose exec backend pip install -e ".[dev]"
docker compose exec backend python -m pytest tests -q
docker compose exec frontend npm ci
docker compose exec frontend npm run build
```

Los tests de tokens usan claves RSA efimeras y sustituyen unicamente la descarga
de certificados; verifican criptograficamente los tokens de prueba, audiencia,
emisor, vencimiento y acceso al dashboard. La autenticacion real debe comprobarse
con la cuenta del usuario en `http://localhost:5179/ingresar`.

Referencia: [Validar ID tokens de Google](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)
y [API JavaScript de Google Identity Services](https://developers.google.com/identity/gsi/web/reference/js-reference).

## Superadministracion

La migracion `0007_superadministrador` crea o habilita `macervilla1@gmail.com`
como superadministrador. El rol se guarda en la base de datos; las altas publicas
crean usuarios sin ese permiso. Aplicar con `docker compose exec backend alembic upgrade head`.

Al ingresar con Google o con el enlace de email, esta cuenta llega a
`/administracion`, incluso sin eventos o proveedores propios. Google requiere
configurar los origenes autorizados descritos arriba.

El dashboard muestra usuarios, eventos y proveedores totales y activos, eventos
publicados, borradores y proximos (publicados, activos y con fecha futura).
Incluye busqueda y paginacion de usuarios y eventos, y controles de activacion.
Desactivar un usuario bloquea sus siguientes pedidos autenticados, incluyendo
sesiones abiertas. Reactivarlo vuelve a habilitar el acceso; sus eventos y
proveedores conservan su estado. Desactivar un evento lo oculta sin eliminarlo;
reactivarlo conserva su estado de publicacion. Los superadministradores estan
protegidos contra desactivacion desde este panel.

El superadministrador puede editar el nombre y el email de cualquier cuenta desde
**Editar datos**. El email se valida y puede repetirse en varias cuentas. Los
enlaces nuevos identifican la cuenta por su ID: el reenvio del panel abre la
cuenta seleccionada. La solicitud publica envia un enlace por cuenta activa.
Cuando hay varias cuentas sin vincular con el mismo email, se utiliza el ingreso
por enlace en lugar de asignar automaticamente una cuenta de Google. Al
cambiarlo se conservan las relaciones con proveedores y eventos, se actualizan
los correos de proveedores que coincidian con el anterior, se invalidan las
sesiones anteriores y se desvincula la identidad previa de Google. Los correos
de contacto diferentes se conservan. La edicion no permite asignar roles.

**Reenviar ingreso** envia al email guardado un enlace de acceso que vence en
30 minutos. Requiere cuenta activa y SMTP configurado; los errores de envio se
muestran en el panel. Guardar los datos y reenviar son acciones separadas.

Todos los endpoints `/administracion/*` verifican sesion, cuenta activa y rol
contra la base de datos en cada pedido. La pantalla no permite asignar roles.

Pruebas de permisos, ingreso y cambios de estado (con dependencias de desarrollo):
`docker compose exec backend python -m pytest tests/test_administracion.py -q`.

## ABM de proveedores

El alta inicial usa una grilla de categorías seleccionables. Un proveedor puede tener varias categorías activas.

La ubicación no se carga con campos manuales de latitud/longitud en el formulario. El proveedor puede abrir Google Maps, seleccionar su negocio o dirección, y pegar el enlace compartido. Ese enlace queda disponible para:

```text
página pública del proveedor
invitaciones futuras
referencias de ubicación dentro del evento
```

Al guardar un proveedor se ejecuta un envío de confirmación en modo desarrollo. Por ahora el mail se imprime en logs con prefijo `mail:dev`; luego puede reemplazarse por SMTP o un proveedor transaccional.

## Ubicación y proveedores cercanos

Autocompletado mundial desde PostgreSQL: ver [GeoNames, importacion y despliegue](docs/geografia-geonames.md).

La geolocalización del navegador es opcional. La plataforma nunca bloquea la búsqueda si el usuario rechaza el permiso.

Prioridad de búsqueda:

1. Ubicación seleccionada para la búsqueda actual.
2. Ubicación del evento cuando se consulta dentro de un evento.
3. Última ubicación habitual guardada.
4. Ubicación actual del dispositivo si el usuario la autoriza.
5. Localidad/provincia elegida manualmente.

Endpoint preparado:

```http
GET /proveedores?lat=-51.62&lng=-69.22&radio_km=30
```

La respuesta incluye `distancia_km` cuando hay coordenadas de búsqueda y ordena inicialmente por distancia. Los proveedores gratuitos aparecen en búsquedas igual que los premium; el plan queda disponible para visibilidad futura.

## Eventos

La ubicación de un evento siempre es un salón existente (proveedor activo con categoría `salon`), guardado en `eventos.salon_id`. Al guardar, la dirección y las coordenadas del evento se copian del salón. El email del organizador es obligatorio: el evento se crea en `BORRADOR` y no es visible hasta abrir el enlace del mail (`/e/{slug}?confirmar=...`, vence en 48 h). Ese enlace lo pasa a `PUBLICADO`, inicia sesión y abre la página del evento `/e/{slug}` en modo administrador (portada, datos y salón editables en ventanas emergentes).

## Baja lógica

Regla del proyecto: la aplicación no debe ejecutar `DELETE` físico sobre información funcional. Las entidades principales incorporan `activo` y, cuando corresponde, `deleted_at`.

Consultas normales:

```text
activo = true
```

Esto aplica inicialmente a eventos, proveedores, categorías, dominios, media y publicaciones.

## Privacidad

- No se almacena la ubicación exacta del usuario como dato permanente por defecto.
- `UserLocationPreference` representa una ubicación de consulta elegida o aproximada.
- Las coordenadas públicas de `Proveedor` corresponden a la ubicación comercial del negocio.
- La ubicación de un evento no modifica automáticamente la ubicación habitual del usuario.

## Endpoints MVP

```text
GET    /health
POST   /acceso/google
POST   /acceso/solicitar-enlace
POST   /acceso/enlace
GET    /acceso/yo
POST   /eventos                          (email obligatorio; crea en BORRADOR y envia mail)
POST   /eventos/confirmar                (canjea el enlace del mail: confirma + sesion)
POST   /eventos/{slug}/reenviar-confirmacion
GET    /eventos/{slug}                   (publico si esta confirmado; BORRADOR solo el propietario)
PUT    /eventos/{slug}                   (solo el propietario)
POST   /media/eventos/{slug}/PORTADA     (solo el propietario)
GET    /proveedores
POST   /proveedores
GET    /proveedores/{slug}
PUT    /proveedores/{slug}
DELETE /proveedores/{slug}
GET    /ubicacion/preferencia
PUT    /ubicacion/preferencia
```

Los módulos de eventos, auth, invitaciones, media y comentarios quedan modelados y listos para sumar routers específicos en las siguientes fases.


## Modulo de invitados

Gestion por evento, importacion Excel, invitaciones personales, RSVP, aprobacion,
credenciales QR y control de ingreso: ver [guia de uso, arquitectura y pruebas](docs/modulo-invitados.md).


### Contactos de invitados y administracion

En Gestion de invitados se pueden dar de alta, editar, dar de baja y reactivar invitados individuales sin exigir email. Se admiten telefono, WhatsApp independiente del telefono, Instagram, Facebook/Messenger, Telegram y otro contacto. El boton Elegir contacto del telefono completa nombre, telefono y email cuando el navegador ofrece la agenda; los usuarios o enlaces de redes se pueden pegar manualmente. Los datos se revisan antes de guardar.

La plantilla XLSX incorpora WhatsApp, Facebook, Telegram y Otro contacto. La carga masiva conserva la vista previa, validacion por fila, control de duplicados y confirmacion explicita; las plantillas anteriores siguen funcionando y no borran los nuevos contactos al actualizar. El permiso de importar se administra por separado del permiso de editar invitados. Telegram se habilita entre los canales del evento y prepara un envio manual.

El dashboard del superadministrador incluye accesos a editar eventos, gestionar invitados y editar negocios ajenos. Los permisos se validan en el backend. Para instalar los nuevos campos: `alembic upgrade head` (revision `0015_contactos_invitados`).
tunel 
ssh -N -L 15433:172.19.0.2:5432 vps


git status
git add .
git commit -m "Agrega decision y ejecucion de multiples herramientas"
git push origin main