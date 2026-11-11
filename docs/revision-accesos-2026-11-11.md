# Revision de accesos del 11/11/2026

Se consulto la base del VPS en una transaccion de solo lectura. No se modificaron
usuarios, propietarios, asignaciones ni datos funcionales de produccion.

## Asignaciones observadas

- `mpcssarchivos@gmail.com` (usuario 3) es propietario de `mutual` y de
  `cumple-atoto` (evento 1). El evento y la asignacion `PROPIETARIO` se crearon
  el 02/11/2026 a las 15:58:59 UTC. Esto explica ambos accesos en el selector.
- `macervilla1@gmail.com` tiene las asignaciones `ADMIN_EVENTO` y `AGASAJADO`
  en ese evento, ademas de su rol de superadministracion.
- `informesindustrial4@gmail.com` es propietario de `salon1` y `Los Sauces`.
- No se encontraron subjects de Google compartidos entre emails distintos.

Estos registros muestran la titularidad actual, pero no prueban quien decidio
originalmente asignarla. Falta que el usuario indique el propietario correcto de
`cumple-atoto` antes de transferirlo y retirar el acceso de la cuenta actual.
Actualizar el codigo no cambia esta titularidad.

## Cambios locales

- El selector y la orientacion de acceso al equipo verifican permisos efectivos,
  con la misma interseccion de permisos admitidos por rol que usa invitados.
  Las asignaciones INVITADO, DJ y MODERADOR no habilitan sitios de gestion.
- Un ENCARGADO con permisos explicitos vacios pierde tambien la edicion;
  se conserva el permiso predeterminado de asignaciones antiguas con NULL.
- El propietario y el superadministrador conservan sus atribuciones explicitas.
- Cada operacion sigue consultando asignaciones del evento solicitado y el ID
  del propietario del proveedor. No se agregan permisos a los JWT.

## Validacion

- 45 pruebas de acceso, edicion, agasajados y equipo aprobadas.
- Suite completa: 151 aprobadas, 8 omitidas por falta de configuracion geografica
  y una fallida por autenticacion contra PostgreSQL local en la prueba de
  concurrencia, antes de ejecutar sus comprobaciones.
- Se agregaron 18 casos sobre asignaciones efectivas, aislamiento de sitios y
  revocacion sin cambiar de sesion.

El VPS no tiene checkout Git en `/var/www/eventos`. Se preparo el paquete local
`actualizacion-acceso.tar.gz` con el estado actual de backend, frontend,
documentacion, scripts y configuracion de ejemplo. Excluye archivos privados
de entorno, dependencias, caches y compilados. Incluye trabajo local pendiente
anterior a esta revision; no se creo un commit ni se desplego el paquete.

## Gestion de usuarios por evento desde superadministracion

El boton **Usuarios** en cada fila de Eventos abre una ventana con el propietario,
las cuentas asignadas y los superadministradores con acceso global. Incluye cuentas
inactivas y roles antiguos sin permisos efectivos, indicados como tales.

Se buscan cuentas registradas por nombre o email, con paginacion e identificacion
por ID para distinguir correos compartidos. Se puede agregar un rol de
administrador, agasajado, gestor, control de ingreso o encargado. Agregar un rol
conserva los otros; quitar una cuenta revoca todos sus roles en ese evento mediante
`permisos=[]`, conservando las filas y su historial. No se desactiva la cuenta ni
se modifican otros eventos o negocios.

El propietario no puede quitarse hasta asignar otro. Seleccionar el rol Propietario
solicita confirmacion; al aceptar, se actualiza `propietario_id`, se revocan todos
los roles del anterior y se reactiva o crea la asignacion del nuevo propietario en
una transaccion con bloqueo del evento. Los roles PROPIETARIO revocados dejan de
conceder acceso. Los superadministradores conservan su acceso global.

Las altas, bajas y transferencias requieren superadministracion en FastAPI y se
registran con evento, actor y usuario en la auditoria existente. No se envian
mensajes ni se modifica produccion para probarlas. No requiere otra migracion.

- `GET /administracion/eventos/{evento_id}/usuarios`: cuentas y accesos.
- `PUT /administracion/eventos/{evento_id}/usuarios/{usuario_id}` con `rol`: asignar.
- `DELETE /administracion/eventos/{evento_id}/usuarios/{usuario_id}`: revocar roles.

Validacion actualizada: 159 pruebas aprobadas y 9 omitidas al ejecutar con
`DATABASE_URL=sqlite://` (geografia sin configurar y concurrencia PostgreSQL).
Compilacion TypeScript/Vite correcta. El script
`scripts/verificar-usuarios-evento-ui.py` comprueba la ventana en escritorio y
movil con API simulada: altas, bajas, transferencia, errores y cancelacion por
boton o Escape, sin dialogos nativos ni cambios reales.
