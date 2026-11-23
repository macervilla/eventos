# Confirmacion nominal y QR de invitados

Actualizacion: 16/11/2026. Ver [identidad de correo y confirmacion segura](confirmacion-segura-cuenta.md).

El invitado contactado abre su enlace personal o entra con la cuenta Google
cuyo email coincide con el registrado por un administrador o agasajado. El boton
Confirmar abre una ventana de datos, sin abandonar la pagina del evento. En una
visita publica sin enlace se ofrece ingresar para buscar la invitacion asignada
a esa cuenta, sin mostrar Confirmar antes de autorizarla.

Se previsualizan y editan apellido y nombre del titular. El cupo incluye a ese
titular; para cada acompanante hay campos obligatorios de apellido y nombre y
una indicacion de adulto o menor. La cantidad comienza con el cupo asignado o
la confirmacion anterior; puede reducirse si asisten menos personas. El backend
rechaza campos vacios y excesos de cupo y conserva los limites de cierre,
modificaciones e ingresos ya registrados.

La confirmacion nominal aprueba automaticamente el cupo confirmado de la
invitacion registrada y emite el QR, independientemente del modo de aprobacion
de otros flujos. No crea invitaciones ni concede permisos de administracion.
No reactiva credenciales de invitaciones revocadas o rechazadas por el
organizador. El QR se muestra, se descarga y se recupera al volver a entrar.
Una confirmacion repetida no cambia el QR ni duplica acompanantes o correos.

Una invitacion por WhatsApp requiere la cuenta autorizada; reenviar el enlace
no permite ver QR ni confirmar. El administrador o agasajado puede vincular la
cuenta Google desde Gestion de invitados. Al volver al enlace con esa cuenta se
recuperan los datos y QR existentes. El correo de contacto puede seguir vacio.
Si aun no hay vinculacion, se puede establecer al ingresar con el correo Google
que coincide con el previamente autorizado. Nunca se asigna la invitacion al
primer portador desconocido del enlace. Ver la regla vigente en
[cuenta autorizada](confirmacion-segura-cuenta.md).

## API y persistencia

- `POST /invitados/{slug}/mis-invitaciones`: requiere sesion Google; recupera
  exclusivamente las invitaciones activas del email verificado en ese evento.
- `POST /invitados/{slug}/portal/confirmar`: acceso personal verificado y lista
  `personas` con `apellido`, `nombre` y `tipo` (`ADULTO` o `MENOR`). La primera
  persona es el titular adulto. Responde datos actualizados, sesion y QR.
- `POST /invitados/{slug}/portal` y `/portal/qr.png`: recuperacion de datos y QR
  sujetos a los mismos controles de acceso y vigencia de credenciales.
- Se conserva el endpoint RSVP anterior para compatibilidad con sus clientes;
  la nueva interfaz utiliza exclusivamente la confirmacion nominal.

El titular conserva su ID de invitacion y sus contactos. Los acompanantes se
guardan en Participante, con apellido separado y orden por ID. Las correcciones
desactivan las filas anteriores sin borrarlas. Se audita la confirmacion.

## Despliegue y verificacion

Aplicar `0018_nombres_acompanantes` con `alembic upgrade head` antes de recrear
el backend. Es una columna aditiva con valor inicial vacio; no se separan ni
reinterpretan los nombres anteriores. El paquete `actualizacion-acceso.tar.gz`
incluye los archivos actuales. Usar el procedimiento habitual con respaldo,
compilacion de backend, migraciones, compilacion de frontend y recreacion de
backend. Localhost consulta el VPS, por lo que editar solamente el frontend
local no habilita estas rutas en el servidor.

Verificado: 173 pruebas aprobadas y 9 omitidas por configuracion ausente de
PostgreSQL/geografia; compilacion TypeScript/Vite correcta. La migracion se
comprobo con upgrade/downgrade/upgrade en una tabla SQLite aislada conservando
filas. No se aplico la migracion ni se alteraron invitaciones reales del VPS.

`scripts/verificar-confirmacion-ui.py` comprueba enlaces, cuenta registrada,
el selector Google y WhatsApp con la cuenta autorizada, sin codigos adicionales, en movil y escritorio, con API simulada. Incluye campos
obligatorios, correcciones, cancelacion, QR inmediato, recarga y retorno por la
pagina general del evento sin una segunda confirmacion. No envia mensajes reales.
