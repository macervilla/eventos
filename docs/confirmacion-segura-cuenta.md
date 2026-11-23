# Confirmacion de asistencia y cuenta autorizada

Regla vigente del 16/11/2026: compartir un enlace, incluso distribuido por
WhatsApp, no transfiere la invitacion. Un perfil de Chrome no acredita una
cuenta dentro de Eventos. La aplicacion verifica una sesion Google vigente y
la cuenta autorizada para esa invitacion. El selector de Google es suficiente; no se requieren codigos adicionales.

## Vinculacion y regreso

- El administrador o agasajado con permiso para editar al invitado puede usar
  **Vincular cuenta Google** en Gestion de invitados. Indica la cuenta de la
  persona; no hace falta completar el correo de contacto de la invitacion.
- La vinculacion se guarda en `Invitacion.usuario_id`. No concede roles de gestion
  ni envia mensajes. Si la cuenta todavia no existe, se registra para su posterior
  ingreso Google; crear el registro no constituye una sesion verificada.
- Si todavia no hay cuenta vinculada y el correo verificado de Google coincide
  con el correo previamente autorizado por el organizador, el primer acceso
  vincula esa cuenta de forma persistente. No se vincula al primer portador de
  un enlace sin comprobar esa coincidencia.
- Con una cuenta ya vinculada, otras cuentas quedan denegadas aunque conozcan
  el enlace, coincidan con otro correo de contacto o conserven una sesion previa.
- Al volver al mismo enlace con su cuenta, la invitada recupera sus datos y su QR
  sin volver a confirmar asistencia. Al cambiar de cuenta se limpia el QR de la
  pantalla y se repite la autorizacion.

Una cuenta ajena recibe `sin_invitacion=True`, sin QR, nombres ni datos personales,
con `puede_confirmar=False`. La interfaz muestra una alerta indicando que no esta
invitada con esa cuenta y debe contactar al agasajado. La descarga de QR, RSVP y
confirmacion nominal tambien validan la identidad en el backend.

Sin sesion ni prueba valida se muestra el ingreso; no se afirma que un visitante
anonimo este invitado ni se le entrega el QR. Si la invitacion carece de cuenta
y correo autorizados, debe vincularla el administrador o agasajado. El visitante
no puede elegir libremente un correo para reclamar una invitacion reenviada.

## Sesiones y credenciales

Desde el 17/11/2026, cada nueva operacion de enviar o reenviar una invitacion
genera un enlace personal nuevo e invalida el anterior. Se conservan RSVP,
aprobacion, cupo, ingresos, cuenta autorizada y QR. Repetir la misma clave de
idempotencia no vuelve a rotar el enlace. La persona debe ingresar con su cuenta
autorizada; renovar el enlace no vincula otra cuenta ni sustituye la identidad.
Pruebas: `backend/tests/test_reenvio_invitacion.py`.

Las sesiones incluyen invitacion, enlace y huella `verificacion-v3`, que incluye
la cuenta vinculada y contactos. Las sesiones antiguas creadas solamente por el
enlace de WhatsApp no autorizan confirmacion, QR ni acceso multimedia de ese flujo.
Los codigos de correo o telefono, PIN y sesiones privadas anteriores no autorizan
confirmacion ni descarga QR. El endpoint de codigo del portal devuelve 403; el de
validacion requiere una sesion Google autorizada. El backend verifica la firma,
emisor, audiencia, caducidad y correo verificado del ID token de Google.

El ingreso inicial de una cuenta de Google con un correo externo tambien usa
esa identidad verificada, sin exigir un segundo codigo por correo. Se conservan
los bloqueos de cuentas inactivas y de correos ya asociados a otra identidad
Google. Registrar una cuenta nueva no le asigna roles o invitaciones.


Cambiar la cuenta autorizada invalida la huella de sesion y reemplaza el QR de
una invitacion aprobada. La asistencia, cupos e ingresos permanecen intactos.
La rotacion no envia correo o WhatsApp automaticamente. No hay migracion: se
reutiliza la relacion de cuenta existente en invitaciones.

## Validacion

Pruebas de identidad y vinculacion:
`backend/tests/test_confirmacion_cuenta.py`, `test_confirmacion_nominal.py` y
`test_vinculacion_invitados.py`. Suite completa sobre PostgreSQL temporal:
266 aprobadas y 8 omitidas. La UI simulada verifica 22 escenarios en escritorio y
movil: cuenta ajena sin QR/confirmacion, alerta, cuenta correcta, retorno al enlace,
QR eliminado al cambiar de cuenta y acceso Google. Tambien se comprobo la ventana
de vinculacion del administrador en escritorio y movil, sin mensajes reales.

Ver [despliegue de la correccion](despliegue-identidad-invitado-2026-11-15.md).

Ingreso unificado desplegado: [selector Google](despliegue-google-2026-11-16.md).
