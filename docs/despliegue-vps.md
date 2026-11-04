# Desplegar Eventos en acersistemas.site/eventos/

La configuracion usa el Nginx instalado en Ubuntu, un frontend estatico y
contenedores propios de PostgreSQL y FastAPI. No inicia Redis ni publica
PostgreSQL. El backend queda disponible solo en 127.0.0.1:8009.

## Archivos

Copiar a /var/www/eventos los archivos compose.vps.yml y .env.vps.example.
Actualizar frontend/src/main.tsx con la version que usa
`basename={import.meta.env.BASE_URL}`. Copiar docs/nginx.eventos.conf a
/var/www/eventos/nginx.eventos.conf.

## Variables privadas

En el VPS:

```bash
cd /var/www/eventos
cp -n .env.vps.example .env.vps
chmod 600 .env.vps
openssl rand -hex 32
openssl rand -hex 32
nano .env.vps
```

Colocar el primer valor en POSTGRES_PASSWORD y el segundo en SECRET_KEY.
No volver a generar estos valores en cada despliegue. El password de una base
ya inicializada no cambia por editar el archivo: debe conservarse o cambiarse
tambien en PostgreSQL. Completar GOOGLE_CLIENT_ID y las variables SMTP con
las credenciales reales de Eventos. No subir .env.vps al repositorio ni pegarlo
en el chat. No se heredan los archivos .env de otros proyectos.

## Compilar e iniciar

Desde /var/www/eventos, definir esta funcion para la terminal actual:

```bash
dc() { docker compose --env-file .env.vps -f compose.vps.yml "$@"; }
dc config --quiet
dc run --rm frontend-build
dc build backend
dc up -d db
dc run --rm backend alembic upgrade head
dc up -d backend
curl -i http://127.0.0.1:8009/health
```

Ejecutar cada comando solo si el anterior finaliza correctamente. Se usa un
archivo Compose independiente; no combinarlo con docker-compose.yml de
desarrollo. La compilacion se hace con Node 22 en Docker, sin necesitar Node
instalado en Ubuntu. Incorpora VITE_API_URL=/eventos/api y --base=/eventos/.
El montaje de frontend/dist permite al backend leer el HTML compilado.

## Nginx

Hacer una copia de seguridad antes de editar:

```bash
cp /etc/nginx/sites-enabled/acersistemas.site /etc/nginx/acersistemas.site.backup
nano /etc/nginx/sites-enabled/acersistemas.site
```

Dentro del server HTTPS, reemplazar los dos bloques anteriores de /eventos
por esta linea:

```nginx
include /var/www/eventos/nginx.eventos.conf;
```

Conservar los bloques de las demas aplicaciones. El archivo incluido contiene
las rutas de frontend, API y media. La aplicacion actual usa /media/ como ruta
absoluta de imagenes; este prefijo debe estar libre en el dominio. La configuracion
pegada del VPS no tenia un bloque /media/.

```bash
nginx -t && systemctl reload nginx
curl -i https://acersistemas.site/eventos/api/health
```

Verificar que frontend/dist/index.html apunta a /eventos/assets/. En el navegador,
abrir /eventos/, recargar con Ctrl+F5 y comprobar que los JS devuelven JavaScript,
no HTML. Abrir /eventos/ingresar directamente para comprobar el fallback de React.

## Acceso y correo

En el cliente OAuth de Eventos, autorizar el origen https://acersistemas.site
(sin /eventos). Configurar SMTP antes de probar altas o enlaces por email:
sin correo configurado el backend devuelve 503 en esos flujos.

La configuracion sirve la SPA en las paginas de eventos. Las vistas previas
sociales personalizadas del endpoint /compartir requieren una integracion
adicional; no redirigir todas las rutas /e/ a ese endpoint porque rechaza
borradores y bloquearia sus enlaces de confirmacion.

## Diagnostico

```bash
dc ps
dc logs --tail=100 backend db
tail -n 50 /var/log/nginx/error.log
```

No ejecutar down -v: elimina los volumenes persistentes de datos y media.
