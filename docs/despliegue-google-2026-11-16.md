# Selector Google como validacion suficiente, 16/11/2026

Se unifico el ingreso de invitados, agasajados, administradores y proveedores
con el selector de cuentas Google, segun la instruccion del usuario.

- La biblioteca oficial verifica el ID token: firma, emisor, audiencia,
  caducidad, subject y correo verificado. No se acepta un email declarado por React.
- El ingreso inicial con una cuenta Google de correo externo tampoco exige una
  segunda verificacion por correo. Se mantienen los rechazos de cuentas inactivas
  y de un email ya vinculado a una identidad Google distinta.
- Roles y permisos siguen consultandose en la base. Una cuenta nueva no recibe
  permisos administrativos ni invitaciones por el hecho de ingresar con Google.
- Portal, confirmacion y QR requieren la cuenta Google autorizada. Codigos, PIN
  y sesiones antiguas sin Google no sustituyen esa identidad. El endpoint de
  codigo del portal devuelve 403 y no envia mensajes.
- La interfaz del invitado ofrece Google, sin formulario de correo ni OTP. La
  configuracion del modulo explica el ingreso Google y retira las opciones PIN/OTP.
- Se conserva la vinculacion previa de invitados, el regreso al mismo enlace,
  el bloqueo de cuentas ajenas y la limpieza de datos al cambiar de cuenta.

Respaldo privado del VPS:
`/var/backups/eventos/google-unico-20261116T095158Z/`. Contiene codigo y frontend
anteriores, referencia Docker y dump verificado con `pg_restore --list`.
Imagen activa: `eventos-backend:google-20261116T095158Z`, tambien etiquetada
`eventos-backend:latest`. Sin migraciones, cambios de invitados/asignaciones,
variables privadas, Nginx, PostgreSQL o MediaMTX.

Validacion: 266 pruebas aprobadas y 8 omitidas sobre PostgreSQL temporal; build
con `/eventos/` y API `/eventos/api`. UI simulada movil/escritorio: selector Google,
22 escenarios de identidad y bloqueo, confirmacion nominal y QR persistente.
En el VPS se verifico el enlace real en 390 y 1280 px: ofrece ingreso Google,
abre la ventana correspondiente y no expone QR ni Confirmar antes de verificar.
La API rechaza la descarga QR/validacion anonimas con 401 y los codigos con 403.
No se inicio sesion en cuentas reales, no se confirmo asistencia y no se enviaron
mensajes durante las comprobaciones.
