# Vinculacion persistente y enlaces reenviados, 15/11/2026

Se corrigio el acceso de terceros al QR mediante el enlace personal de WhatsApp.
La distribucion del enlace ya no acredita la identidad. La cuenta Google debe
estar autorizada para la invitacion o debe existir una prueba de correo valida;
una cuenta distinta no puede reutilizarla.

- Cuenta ajena: alerta **No estas invitado con esta cuenta**, indicacion de
  contactar al agasajado y ausencia de QR, datos personales y Confirmar asistencia.
- Sin sesion: ingreso para verificar identidad, sin entregar el QR.
- Si el correo Google coincide con el previamente autorizado y no hay vinculacion,
  se vincula de forma persistente. No se asigna un enlace sin contacto autorizado
  al primer visitante desconocido.
- Cuenta vinculada: al volver al mismo enlace recupera datos y QR. Cambiar de
  cuenta limpia la pantalla y repite la autorizacion.
- Gestion de invitados: **Vincular cuenta Google** para administradores o
  agasajados autorizados. Permite indicar la cuenta sin completar el correo de
  contacto de la invitacion. No envia mensajes. Cambiarla reemplaza el QR aprobado.
- Sesiones `verificacion-v3`: invalidan accesos anteriores por mera posesion del
  enlace. La vinculacion se guarda en `invitaciones.usuario_id`, sin migracion.

## Publicacion y validacion

- Respaldo privado: `/var/backups/eventos/identidad-invitado-20261116T013702Z/`.
  La marca es UTC; en Argentina fue el 15/11/2026. Incluye codigo, frontend,
  referencia de imagen Docker y dump verificado con `pg_restore --list`.
- Imagen: `eventos-backend:identidad-20261116T013702Z`, tambien etiquetada como
  `eventos-backend:latest`. Frontend compilado con `/eventos/` y `/eventos/api`.
- Se conservaron variables privadas, configuracion Nginx, PostgreSQL y MediaMTX.
- Se reemplazo el QR expuesto de la invitacion 5 del evento `cumpleale`, dejando
  inactiva la credencial anterior. Se conservaron RSVP, aprobacion, cupo e ingresos;
  no se envio el nuevo QR ni otros mensajes como parte de la operacion.
- La cuenta de esa invitada no estaba identificada. Se solicito al administrador
  el correo de la cuenta Google autorizada; no se asigno una cuenta por suposicion.

Pruebas: 265 aprobadas y 8 omitidas sobre PostgreSQL temporal. UI simulada:
22 escenarios de cuenta, regreso, cambio de identidad y bloqueo de QR en movil
y escritorio; vinculacion por administrador tambien comprobada en ambos anchos.
Build de produccion correcto.

En produccion se comprobo el bloqueo del servicio para una identidad ajena sin
modificar datos, y los endpoints publicos: el portal anonimo no devuelve nombres
ni QR y la descarga anonima QR responde 401. La pagina real del enlace se reviso
en movil y escritorio sin iniciar sesion: sin QR ni Confirmar asistencia, con
ingreso Google e indicacion de contactar al agasajado. Los tokens no se registran
en este documento ni se muestran en las salidas de comprobacion.
