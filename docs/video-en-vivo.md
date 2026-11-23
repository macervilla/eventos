# Video en vivo de Eventos: MediaMTX y WebRTC

Implementacion inicial local del 11/11/2026. Posteriormente, con autorizacion
explicita, se activo la configuracion en el VPS; consultar el
[registro de activacion y verificaciones](activacion-video-vps-2026-11-11.md).
Los pasos siguientes documentan el despliegue y las pruebas iniciales locales.

## Uso multicamara (17/11/2026)

1. El administrador habilita varios invitados desde sus filas. Cada camara es
   independiente: habilitar o pausar una no corta las demas. El boton Pausar
   aparece en rojo mientras ese invitado transmite.
2. Transmision en vivo muestra una tarjeta por camara habilitada: nombre,
   estado y vista previa silenciada cuando esta activa. Se admiten por defecto
   cuatro camaras habilitadas por evento y cuatro transmisiones activas o
   iniciandose en todo el servidor. Los limites se validan en el backend.
3. El tilde **Emitir en Album** elige una sola camara activa. Cambiarlo no detiene
   las publicaciones ni las vistas previas. Quitar el tilde muestra las fotos.
   Si la camara seleccionada se detiene, el album vuelve a las fotos; no cambia
   automaticamente a otra persona. Si esa misma camara reinicia, vuelve a emitirse.
4. Los invitados solo pueden ver la camara elegida para el album. Las otras
   vistas previas requieren permisos administrativos. La lista de todas las
   camaras no se entrega al invitado.
5. El invitado abre su invitacion y prepara camara/microfono en Iniciar
   transmision. Puede iniciar, detener o cambiar camara; cerrar libera los
   dispositivos. Su autorizacion persiste hasta que el administrador la pausa.
6. El album muestra solo Album de [evento] como encabezado. El video ocupa el
   escenario de las fotos; el carrusel queda suspendido mientras hay vivo.
   Al terminar, se recuperan fotos y controles. Actualizar album no reinicia video.

## Recursos y limites

- `VIDEO_MAX_CAMARAS_EVENTO=4`: maximo de invitados habilitados por evento.
- `VIDEO_MAX_TRANSMISIONES=4`: maximo global de publicadores activos o reservados.
  El candado transaccional de PostgreSQL serializa reservas entre procesos y
  eventos. Un segundo dispositivo de la misma persona recibe 409.
- `VIDEO_BITRATE=1200000`: limite de video enviado por cada camara, sin incluir
  audio ni sobrecarga de red. Aproximadamente 540 MB/h por copia del video a ese
  bitrate. No es una medicion ni un presupuesto garantizado.
- El servidor recibe cada camara una vez y envia una copia por vista previa y
  por espectador del album. Cuatro previews consumen hasta 4,8 Mbps de salida;
  cada album agrega hasta 1,2 Mbps, mas audio y protocolos. La computadora del
  administrador decodifica todas las previews.
- No hay grabacion ni transcodificacion. Hay consumo de CPU, RAM, transferencia
  del VPS y bateria/datos de los celulares. La facturacion depende del plan del
  proveedor; no se agrego un servicio de video pago.
- Los limites son un punto inicial conservador, no capacidad certificada. Antes
  de ampliarlos, medir CPU, RAM, trafico y espectadores con una carga real.
  Referencia: https://mediamtx.org/docs/features/scalability

## Arquitectura y controles

- FastAPI verifica invitacion o sesion Google y permisos del evento. No recibe
  video, audio ni grabaciones. La senalizacion WHIP/WHEP pasa por Nginx hacia
  MediaMTX; los medios usan ICE + DTLS/SRTP entre navegador y MediaMTX.
- Imagen oficial fijada en `bluenviron/mediamtx:1.21.3`, sin grabacion, HLS, RTSP,
  RTMP, SRT ni MoQ. No se agrego un servicio de pago ni un servidor externo.
- Captura preferida 1280x720, 24 fps y limite de video de 1.2 Mbps, ajustable con
  `VIDEO_BITRATE` (250000 a 4000000). El navegador puede reducir resolucion segun
  el dispositivo y la red. La camara frontal/trasera requiere que exista en el equipo.
- Migracion aditiva `0023_camaras_video`: una fila por invitado y evento con
  autorizacion, version y reserva independientes. `transmisiones_evento` conserva
  la seleccion unica del album. Se migra la camara anterior sin cambiar su
  generacion ni la seleccion; las fotos y la asistencia permanecen intactas.
- Bloquear la fila Evento serializa incluso la primera configuracion concurrente.
  La reserva dura 45 segundos; un segundo inicio recibe 409. MediaMTX ademas usa
  `overridePublisher: false`. Antes de iniciar se cortan conexiones abandonadas
  o de generaciones anteriores; si no se puede comprobar el corte, no se abre
  una nueva publicacion.
- FastAPI emite credenciales de un minuto, separadas para `publish` y `read`,
  ligadas al evento, a su version y al usuario o invitacion autorizados. No son
  claves fijas de publicacion. Nunca se entrega SECRET_KEY, el secreto del callback
  ni la direccion de la API administrativa al navegador.
- MediaMTX valida cada nueva conexion mediante un callback HTTP privado con
  autenticacion servidor-a-servidor. Conocer el path no permite publicar. Los
  permisos, estado activo de la cuenta/invitacion y enlace vigente se comprueban
  nuevamente en el servidor. Una credencial de lectura no sirve para publicar.
- La API de control solo existe en la red Docker. No se publica el puerto 9997.
  Solo las acciones API se excluyen del callback para que el backend pueda
  consultar/cortar sin depender de su propio callback. No exponer ese puerto.
- Las sesiones de MediaMTX se identifican por el encabezado ID. Cada navegador
  renueva su permiso cada tres segundos; el lease dura 45 segundos. Un proceso
  de reconciliacion cada cinco segundos expulsa conexiones expiradas, revocadas o
  de otro estado de autorizacion, aunque el navegador no coopere.
- La revocacion se guarda antes de contactar a MediaMTX. Si su API no responde,
  se devuelve 503 indicando que el corte no fue confirmado y se reintenta en
  segundo plano. No se declara un corte efectivo si el servidor no lo confirmo.
  Un cliente existente puede continuar fisicamente mientras esa API sea
  inaccesible; no se admiten nuevos publicadores hasta resolver el corte.
- Estados: autorizado, iniciando, activa, finalizada e interrumpida. Activa solo
  se obtiene al consultar el path real de MediaMTX y su publicador. Una reserva
  o una autorizacion no se muestran como una transmision activa. Los errores de
  MediaMTX no bloquean fotos, asistencia ni las otras funciones del sistema.

## Desarrollo aislado en Windows

El localhost habitual de este proyecto consulta el VPS. Para trabajar en backend
y video se agrego **otro entorno independiente**, con puertos y volumenes propios:

```powershell
cd C:\mentoria\proyectosvs\eventos
python scripts/preparar-video-dev.py
```

El generador escribe secretos aleatorios en `.env.video.dev`, no los muestra y no
sobrescribe un archivo existente. No subir ese archivo al repositorio. Para login
real, completar GOOGLE_CLIENT_ID y autorizar `http://localhost:5189` en Google.
No se agrega otro proveedor OAuth ni se requieren secretos OAuth en React.

```powershell
docker compose --env-file .env.video.dev -p eventos-video-dev -f compose.video.dev.yml up -d db
docker compose --env-file .env.video.dev -p eventos-video-dev -f compose.video.dev.yml build backend
docker compose --env-file .env.video.dev -p eventos-video-dev -f compose.video.dev.yml run --rm backend alembic upgrade head
docker compose --env-file .env.video.dev -p eventos-video-dev -f compose.video.dev.yml up -d --build backend mediamtx frontend
```

Abrir `http://localhost:5189`. API local: `http://127.0.0.1:18090/docs`.
Senalizacion local: puerto 18889, ICE UDP/TCP 18189. Esta configuracion anuncia
127.0.0.1: es una prueba en la computadora local, no una configuracion para celulares
externos. La API de MediaMTX no tiene puerto publicado en este entorno Compose.
No se usan datos, SMTP ni media del VPS. La migracion de superadministracion
existente tambien se aplica en esta BD nueva; no se incorpora otra cuenta admin.

Para detener sin borrar datos:

```powershell
docker compose --env-file .env.video.dev -p eventos-video-dev -f compose.video.dev.yml stop
```

## Despliegue en el VPS: configuracion adicional obligatoria

Esta actualizacion **no se habilita solamente con la secuencia habitual**. Requiere
configurar el servidor de video, el proxy y la conectividad. El servicio esta bajo
el perfil opcional `video`; los servicios y volumenes anteriores se conservan.

Desde PowerShell, con el paquete generado:

```powershell
cd C:\mentoria\proyectosvs\eventos
scp actualizacion-video.tar.gz vps:/tmp/
ssh vps
```

Los comandos siguientes son para la terminal **dentro del VPS**, no PowerShell:

```bash
set -e
cd /var/www/eventos
dc() { docker compose --env-file .env.vps -f compose.vps.yml "$@"; }
bash scripts/geografia-vps.sh backup
umask 077
tar --exclude=node_modules --exclude=dist --exclude=__pycache__ \
  -czf "/var/backups/eventos/codigo-antes-video-$(date +%Y%m%d-%H%M%S).tar.gz" \
  backend frontend docs scripts compose.vps.yml .env.vps nginx.eventos.conf
tar -xzf /tmp/actualizacion-video.tar.gz -C /var/www/eventos
nano .env.vps
```

Agregar o completar, conservando los secretos y variables anteriores:

```dotenv
VIDEO_ENABLED=true
VIDEO_BITRATE=1200000
MEDIAMTX_API_URL=http://mediamtx:9997
MEDIAMTX_PUBLIC_URL=/eventos/rtc
MEDIAMTX_AUTH_SECRET=SECRETO_HEXADECIMAL_NUEVO
WEBRTC_PUBLIC_HOST=IP_PUBLICA_REAL_DEL_VPS
```

Generar el nuevo secreto **en el VPS** con `openssl rand -hex 32`; copiarlo solo a
.env.vps. Usar hexadecimal para que sea seguro dentro de la URL del callback.
No reemplazar SECRET_KEY ni POSTGRES_PASSWORD y no publicar el nuevo secreto.
WEBRTC_PUBLIC_HOST es la direccion publica real que alcanzan los celulares,
no la IP privada del contenedor. Si se usa un dominio, debe resolver directamente
al VPS; un proxy CDN HTTP no transporta automaticamente ICE en 8189.

Antes de seguir, habilitar en el firewall del proveedor y del servidor:

| Puerto | Alcance | Funcion |
| --- | --- | --- |
| 443/TCP | Internet, existente | HTTPS de Eventos y WHIP/WHEP |
| 8189/UDP | Internet | ICE de baja latencia |
| 8189/TCP | Internet | Alternativa ICE cuando UDP no funciona |
| 8889/TCP | Solo 127.0.0.1 del VPS | Nginx hacia MediaMTX |
| 9997/TCP | Solo red Docker, sin publicar | API de control |

Si se utiliza UFW, revisar su estado y permitir unicamente `8189/udp` y `8189/tcp`;
no desactivar el firewall ni exponer PostgreSQL. Verificar tambien las reglas del
proveedor y las asignaciones Docker. No se ejecutaron esas operaciones por el agente.

```bash
dc config --quiet
dc build backend
dc run --rm --no-deps backend alembic upgrade head
dc run --rm frontend-build
dc --profile video up -d --no-deps --force-recreate backend mediamtx

# El sitio existente debe incluir /var/www/eventos/nginx.eventos.conf.
cp nginx.eventos.conf nginx.eventos.conf.antes-video
cp docs/nginx.eventos.conf nginx.eventos.conf
nginx -t
systemctl reload nginx
dc --profile video ps
curl --fail https://acersistemas.site/eventos/api/health
```

Ejecutar cada paso solo si termina correctamente. La configuracion Nginx conserva
las rutas anteriores, bloquea el callback interno desde Internet y agrega
`/eventos/rtc/` hacia 127.0.0.1:8889. Reescribe Location para las sesiones WHIP/WHEP
en ese prefijo y conserva Authorization e ID. No requiere WebSocket/WSS: la
senalizacion de esta implementacion usa HTTPS WHIP/WHEP. No copiar configuraciones
de otros sitios ni reemplazar el server HTTPS completo.

## Pruebas y limites reales

Se comprobaron localmente:

- Suite completa: **192 pruebas aprobadas, 11 omitidas** (ocho de geografia,
  una de concurrencia previa sin BD local configurada y dos de video PostgreSQL
  que se ejecutaron aparte). Las **dos pruebas PostgreSQL de video pasaron** en
  el contenedor descartable: migracion y reservas simultaneas.

- Compilacion TypeScript y Vite.
- Suite de backend, permisos, estados, callback, exclusividad, revocacion,
  expiracion y funcionamiento de fotos si MediaMTX falla.
- Dos reservas concurrentes en PostgreSQL descartable: una 200 y otra 409.
- Upgrade/downgrade/upgrade de 0020 en PostgreSQL aislado, conservando usuarios.
- MediaMTX 1.21.3 real en Docker y dos contextos Chromium independientes con
  camara/microfono sinteticos: invitado emisor e invitado espectador, recepcion
  de video y pista de audio, cambio de camara, detencion, desconexion, revocacion,
  rechazo de publicacion sin credenciales o con una credencial de lectura.
- Fotografias aprobadas mientras existe video; Actualizar album conserva el
  mismo MediaStream y la misma conexion WebRTC.
- Prueba real repetida con UDP habilitado y forzando solo TCP.
- Prueba adicional con Nginx real y prefijo `/eventos/rtc`, incluida la
  reescritura relativa de Location con `absolute_redirect off`.
- Configuracion MediaMTX aceptada por su imagen oficial; Nginx validado con
  `nginx -t` en un contenedor descartable; Compose de VPS y desarrollo validados.

Reproducir las comprobaciones sin tocar el VPS:

```powershell
# Desde backend, con dependencias dev instaladas:
python -m pytest tests/test_video.py tests/test_fotos_invitados.py -q
# Desde la raiz, requiere Docker:
python scripts/verificar-video-postgres.py
# Con frontend compilado servido en 127.0.0.1:5180:
python scripts/verificar-video-real.py
$env:VIDEO_TEST_TCP_ONLY = '1'
python scripts/verificar-video-real.py
Remove-Item Env:VIDEO_TEST_TCP_ONLY
$env:VIDEO_TEST_PROXY = '1'
python scripts/verificar-video-real.py
Remove-Item Env:VIDEO_TEST_PROXY
```

La prueba real crea su propio FastAPI, SQLite temporal y contenedor MediaMTX, y
los elimina al terminar. Usa los puertos locales 18090, 18889, 19997 y 18189; no
ejecutarla sobre servicios que ya los ocupen.
El modo proxy usa ademas el puerto loopback 18890 y otro contenedor Nginx temporal.
La prueba PostgreSQL crea otro
contenedor local, puerto loopback 25439, y esquemas temporales. No usa DATABASE_URL
ni credenciales productivas. La prueba de camara es sintetica: no demuestra el
comportamiento de camaras fisicas ni que un celular pueda alcanzar el VPS.

**Pendiente de verificar tras configurar produccion:** publicar desde un celular
por WiFi y por datos moviles, recibir desde otra red, probar camara frontal y
trasera reales, audio, HTTPS, IP anunciada y UDP/TCP 8189. Un resultado en
localhost no demuestra NAT/ICE en esas redes. Redes que bloquean tanto UDP como
TCP 8189 pueden requerir TURN propio en el mismo VPS; esta primera version no
instala TURN ni usa un relay de pago, y no se garantiza conexion en esas redes.
No se afirmo que el streaming funcione en produccion ni se abrieron puertos reales.

No hay grabacion, archivos de video, chat ni comentarios. El ancho de banda de
salida crece con la cantidad de espectadores: revisar uso real del VPS antes de
aumentar bitrate o concurrencia de lectura.

## Archivos del cambio de video

Nuevos: `backend/app/models/video.py`, `backend/app/schemas/video.py`,
`backend/app/services/mediamtx.py`, `backend/app/services/video.py`,
`backend/app/services/video_worker.py`, `backend/app/api/video.py`,
`backend/alembic/versions/0020_video_en_vivo.py`, `frontend/src/api/webrtc.ts`,
`frontend/src/components/VideoEvento.tsx`, `infra/mediamtx.yml`,
`compose.video.dev.yml`, `.env.video.dev.example`, `scripts/preparar-video-dev.py`,
`backend/tests/test_video.py`, `backend/tests/test_video_postgres.py`,
`backend/tests/servidor_video_integracion.py`, `scripts/verificar-video-real.py`,
`scripts/verificar-video-postgres.py` y esta guia.

Integraciones modificadas: `backend/app/core/config.py`, `backend/app/main.py`,
`backend/app/models/__init__.py`, `backend/app/api/fotos_invitados.py`,
`backend/app/services/fotos_invitados.py`, `backend/tests/test_fotos_invitados.py`,
`frontend/src/components/ConfirmacionInvitado.tsx`, `frontend/src/pages/InvitadosPage.tsx`,
`frontend/src/pages/AlbumEventoPage.tsx`, `frontend/src/api/sesion.ts`,
`frontend/src/styles.css`, `frontend/vite.config.ts`, `compose.vps.yml`,
`.env.example`, `.env.vps.example`, `.gitignore`, `docs/nginx.eventos.conf`,
`scripts/verificar-fotos-invitados-ui.py` y `docs/fotos-invitados.md`.
El paquete incluye tambien el trabajo local pendiente de las funcionalidades anteriores.

## Referencias oficiales consultadas

- [MediaMTX: autenticacion HTTP y tokens](https://mediamtx.org/docs/features/authentication).
- [Configuracion de MediaMTX](https://mediamtx.org/docs/references/configuration-file).
- [Control API de la version utilizada](https://github.com/bluenviron/mediamtx/blob/v1.21.3/api/openapi.yaml).
- [Proxy en subcarpeta y encabezado Location](https://mediamtx.org/docs/features/expose-the-server-in-a-subfolder).
- [Conectividad WebRTC e ICE](https://mediamtx.org/docs/features/webrtc-specific-features).

## Verificacion multicamara

- `tests/test_video.py`: publicaciones independientes, seleccion, privacidad,
  revocacion individual, idempotencia de autorizacion y limites.
- `python scripts/verificar-video-postgres.py`: base descartable; concurrencia
  del tope global entre eventos, reservas por invitado y migracion/reversion.
- `python scripts/verificar-video-real.py`: dos publicadores WebRTC sinteticos,
  previews reales, tilde administrativo, cambio de emision sin cortar camaras,
  regreso a fotos y revocacion; no usa ni modifica el VPS.
- El despliegue requiere ejecutar `alembic upgrade head` antes de iniciar el
  backend nuevo. No se ejecuto la migracion en produccion durante este cambio.


## Grabacion YouTube: evaluacion previa

Ver [propuesta de grabacion externa](youtube-live-propuesta.md). Todavia no
se incorporo el worker ni OAuth de YouTube. El limite global se redujo a cuatro
segun el nuevo requisito. Al desplegar, cualquier valor anterior
`VIDEO_MAX_TRANSMISIONES=8` debe reemplazarse por `4`; la configuracion rechaza
valores mayores para impedir sobrepasar el maximo.
