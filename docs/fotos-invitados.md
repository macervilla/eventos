# Fotos privadas de invitados

Actualizacion: 11/11/2026.

Cada invitacion permite guardar hasta cuatro fotos activas, independientemente
del cupo de asistencia. El invitado accede desde **Mis fotos (hasta 4)** o dentro
de **Modificar datos**. Puede subir JPG, PNG o WebP, ampliar las imagenes que ya
envio, quitarlas y subir reemplazos. No necesita volver a confirmar asistencia.
Las fotos tienen su propio estado: siguen siendo editables aunque el plazo para
corregir el RSVP este cerrado, mientras su invitacion permita el acceso y el
administrador no haya confirmado las fotos.

En **Gestion de invitados**, el administrador abre **Fotos del invitado** en la
fila correspondiente. Puede revisar, ampliar y descargar cada imagen. El boton
**Confirmar fotos** bloquea el conjunto completo; el invitado conserva la lectura,
pero no puede subir ni quitar imagenes. **Desbloquear fotos** vuelve a permitir
los cambios. Confirmar fotos requiere al menos una imagen y no modifica el QR,
el RSVP ni los cupos. La confirmacion de asistencia tampoco bloquea las fotos.

El administrador tambien puede seleccionar una o varias imagenes y usar
**Quitar seleccionadas**. Tras confirmar la baja, las imagenes se desactivan,
desaparecen del album y el conjunto queda desbloqueado para que el invitado
pueda completar los lugares liberados. Esto funciona aunque las fotos ya
estuvieran confirmadas. Se valida toda la seleccion antes de cambiar fotos;
una seleccion ajena a esa invitacion no produce una baja parcial.

## Album del evento

El boton **Álbum** en Gestion de invitados abre `/{slug}/album` en otra pestana
con la misma cuenta administrativa seleccionada. No se coloca el token de sesion
en la URL. El album requiere permiso `configurar_invitados` en ese evento y
muestra las fotos activas de conjuntos confirmados por el administrador.
Las pendientes se conservan en la revision administrativa y no se muestran en
el album. Los invitados tienen acceso de solo lectura mediante su invitacion
personal; ver [video en vivo y album](video-en-vivo.md). Las fotos quitadas quedan excluidas.

El carrusel muestra las fotos completas, sin recortarlas, y avanza cada dos
segundos desde que la foto esta cargada. Incluye pausa/reanudacion, anterior,
siguiente, pantalla completa y **Actualizar album**. El listado tambien se
actualiza cada diez segundos, sin reiniciar el video. Solo conserva en memoria la foto actual y sus
dos vecinas; las imagenes se consultan por endpoints privados autorizados.

Las fotos quedan privadas para la invitacion y para administradores autorizados
del evento. No se publican automaticamente en la galeria: el administrador puede
descargarlas para compartirlas mas adelante. Los agasajados y gestores de listas
no obtienen permiso para consultar o confirmar fotos de otras invitaciones.

## Persistencia y autorizacion

La migracion aditiva `0019_fotos_invitados`, posterior a `0018_nombres_acompanantes`,
agrega `invitaciones.fotos_bloqueadas` con valor inicial falso y la tabla
`fotos_invitado`. No cambia invitaciones ni confirmaciones existentes.

Las cuatro posiciones de cada invitacion tienen una restriccion de rango y un
indice unico parcial para las filas activas. Las subidas, bajas y cambios de
bloqueo toman el mismo bloqueo de fila de invitacion. Una pantalla que conserve
el estado anterior no puede eludir la confirmacion: el backend comprueba otra
vez el bloqueo antes de cada cambio.

La baja de una foto es logica, conservando registro y archivo cifrado. Subir una
nueva foto reutiliza una posicion libre con un registro nuevo. Las acciones de
subir, quitar, confirmar y desbloquear se registran en la auditoria existente.

Los archivos se verifican y recodifican usando el validador de imagenes existente:
JPEG, PNG o WebP reales, limite configurado `MAX_UPLOAD_BYTES` (5 MiB por defecto)
y hasta 20 megapixeles. Se almacenan cifrados con Fernet dentro del volumen
persistente de media, bajo claves aleatorias `.enc`. No se almacena una copia
publica en texto plano ni se entregan claves de almacenamiento al navegador.
Los endpoints autorizados descifran la imagen y responden con
`Cache-Control: private, no-store`. Se utiliza la misma clave de aplicacion que
protege las credenciales existentes; los respaldos deben conservar media y
configuracion privada.

## API

Para invitados, siempre con el acceso personal ya autorizado (incluido el
acceso directo de invitaciones WhatsApp):

- `POST /invitados/{slug}/portal/fotos/listar`: token/sesion de la invitacion.
- `POST /invitados/{slug}/portal/fotos`: formulario con token, sesion opcional y file.
- `POST /invitados/{slug}/portal/fotos/{foto_id}/imagen`: imagen privada.
- `POST /invitados/{slug}/portal/fotos/{foto_id}/quitar`: baja logica.

Para administradores con permiso `configurar_invitados` en ese evento:

- `GET /invitados/{slug}/lista/{inv_id}/fotos`: listado y estado.
- `GET /invitados/{slug}/lista/{inv_id}/fotos/{foto_id}/imagen`: lectura/descarga.
- `PUT /invitados/{slug}/lista/{inv_id}/fotos/estado` con `bloqueadas`: confirmar o desbloquear.
- `POST /invitados/{slug}/lista/{inv_id}/fotos/quitar-seleccionadas` con `ids`: baja multiple y desbloqueo.
- `GET /invitados/{slug}/album`: listado de fotos activas del evento.
- `GET /invitados/{slug}/album/{foto_id}/imagen`: imagen privada del carrusel.

El propietario, superadministrador y administrador de evento con ese permiso
pueden realizar la revision. Una invitacion no puede acceder a fotos de otra,
y los permisos se comprueban contra el evento solicitado.

## Verificacion y despliegue

- 183 pruebas aprobadas y 9 omitidas por configuracion ausente de PostgreSQL/geografia.
- Pruebas especificas: limite, cifrado, lectura privada, aislamiento, roles,
  bloqueo/desbloqueo, baja logica, reemplazos, formatos/tamanos y restricciones SQL.
  Tambien baja multiple atomica, exclusion de fotos quitadas y permisos del album.
- Migracion comprobada con upgrade/downgrade/upgrade en SQLite aislado, conservando
  las invitaciones previas. No se aplico la migracion en produccion.
- Compilacion TypeScript/Vite correcta.
- `scripts/verificar-fotos-invitados-ui.py`: recorrido de invitado y administrador
  en movil/escritorio con API simulada, incluyendo una baja rechazada tras un
  bloqueo concurrente del administrador y fotos accesibles desde Modificar datos.
  Tambien seleccion multiple, cancelacion de la baja y reemplazos posteriores,
  album en nueva pestana con cuenta seleccionada, avance a los dos segundos,
  pausa, navegacion y vuelta al inicio del carrusel.
- Se verificaron tambien confirmacion/QR, usuarios del evento y reenvio multiple.

Usar el paquete actualizado `actualizacion-acceso.tar.gz` y la secuencia habitual
del VPS, incluido `alembic upgrade head` antes de recrear el backend. Localhost
utiliza ese backend remoto: la funcion no queda habilitada solo con modificar
el frontend local. No se enviaron mensajes ni se modificaron fotos o invitados
reales para probarla.
La baja multiple y el album no requieren una nueva migracion posterior a `0019`.
