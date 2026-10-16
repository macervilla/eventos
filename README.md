# Plataforma digital de eventos

Base técnica para una plataforma web/PWA de eventos con portal público, espacios permanentes, módulos activables, proveedores con página pública y búsqueda por cercanía.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, JWT-ready.
- Frontend: React, TypeScript, Vite, React Router, Axios.
- Infraestructura local: Docker Compose con PostgreSQL, Redis, backend y frontend.

## Ejecutar en desarrollo

```bash
cp .env.example .env
docker compose up --build
```

Backend: http://localhost:8009/docs  
Frontend: http://localhost:5179

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

- Google: el backend verifica el token contra Google y, si el email administra algo, devuelve un JWT de sesión.
- Email manual: `POST /acceso/solicitar-enlace` envía un enlace mágico (vence en 30 min). Al abrirlo, `/ingresar?enlace=...` lo canjea en `POST /acceso/enlace` por el JWT de sesión.
- El frontend guarda el JWT en `localStorage` y lo envía como `Authorization: Bearer`.
- `PUT`/`DELETE /proveedores/{slug}` y la subida de media exigen sesión del dueño del proveedor.
- El dueño que entra a `/p/{slug}` ve íconos para cambiar la portada, editar datos y cambiar la ubicación en ventanas emergentes.
- Al guardar un enlace de Google Maps, el backend intenta extraer latitud/longitud (sigue enlaces cortos `maps.app.goo.gl`).

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
