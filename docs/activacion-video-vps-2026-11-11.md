# Activacion de video en el VPS, 11/11/2026

Se completo con autorizacion explicita del usuario. Antes de activar se verifico
que PostgreSQL ya estaba en `0020_video_en_vivo`. No se ejecutaron migraciones
ni se modificaron invitados, permisos del evento, fotos o volumenes persistentes.

## Configuracion aplicada

- `VIDEO_ENABLED=true`, bitrate 1200000, API interna `http://mediamtx:9997`,
  prefijo publico `/eventos/rtc` e IP ICE publica `69.6.206.81`.
- Se genero el secreto privado de autenticacion en el VPS, conservando los
  secretos anteriores de la aplicacion y la base. No se copio al repositorio.
- Se inicio `bluenviron/mediamtx:1.21.3` y se recreo el backend para leer el entorno.
- Se instalo el fragmento Nginx de `docs/nginx.eventos.conf`, se valido con
  `nginx -t` y se recargo Nginx. No se reemplazo el servidor HTTPS completo.
- Docker publica 8189 TCP/UDP; 8889 solo en loopback y 9997 solo en red Docker.
  UFW estaba inactivo; no se cambio su estado ni se agregaron reglas innecesarias.

Respaldo privado previo de entorno, fragmento Nginx, Compose y configuracion
MediaMTX: `/var/backups/eventos/activacion-video-20261112T014716Z/`.
La fecha del directorio usa UTC. Contiene secretos: mantener acceso privado.

## Comprobaciones realizadas

- Health publico HTTPS: 200; backend y MediaMTX iniciados; PostgreSQL healthy.
- API interna MediaMTX accesible desde backend; IP anunciada y listeners correctos.
- TCP 8189 accesible desde otra red. Datagrama UDP de prueba recibido en la
  interfaz publica del VPS, comprobado con captura filtrada sin datos de invitados.
- Ruta HTTPS WHIP responde 401 sin credenciales, en lugar del HTML de la SPA.
- Callback interno bloqueado por Nginx con 404 para Internet.
- Callback rechaza falta de secreto y credenciales temporales invalidas.
- Puertos 8889 y 9997 inaccesibles desde la red externa de comprobacion.

La activacion se realizo con `scripts/activar-video-vps.py --host-publico 69.6.206.81`
ejecutado dentro del VPS. El script crea respaldo y no ejecuta migraciones.

## Prueba que requiere el celular

Recargar la invitacion personal del invitado autorizado. Pulsar **Iniciar
transmision**, permitir camara y microfono, revisar la vista previa y pulsar
**Iniciar**. Abrir el album desde otro navegador y activar audio si se desea.
Comprobar WiFi y datos moviles, cambio de camara y detencion. No se ha afirmado
que una camara fisica o una transmision WebRTC completa se hayan probado en
produccion: estas comprobaciones validan servicios, autenticacion y red del VPS.
