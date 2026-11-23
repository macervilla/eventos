# Confirmacion directa desde WhatsApp, 15/11/2026

Registro historico: esta autorizacion por enlace fue reemplazada por la
[verificacion de cuenta](despliegue-identidad-invitado-2026-11-15.md) tras
comprobar el acceso de terceros mediante enlaces reenviados.

Se restauro el acceso directo solicitado por el administrador. Una invitacion
personal distribuida por WhatsApp por un administrador o agasajado autorizado
muestra **Confirmar asistencia** sin pedir correo, Google ni codigo. Tambien
permite recuperar el QR. La existencia de una cuenta diferente en el navegador
no impide utilizar ese enlace personal. Para otros enlaces se conserva el flujo
de correo verificado.

`acceso_confirmacion` comprueba la distribucion de tipo invitacion y estado
PREPARADO o ENVIADO, ademas del enlace vigente, evento y estado de invitacion.
Se conservan los limites de cupo, cierre y modificaciones y el bloqueo de
invitaciones revocadas, rechazadas o canceladas. Un envio fallido, otra clase de
distribucion o una sesion anterior sin distribucion vigente no habilita RSVP.

Despliegue limitado a `backend/app/services/invitados_portal.py`,
`frontend/src/components/ConfirmacionInvitado.tsx` y el frontend compilado con
base `/eventos/` y API `/eventos/api`. Sin migraciones ni cambios de datos
funcionales, variables privadas, Nginx o MediaMTX.

- Respaldo privado: `/var/backups/eventos/whatsapp-sin-correo-20261116T005804Z/`.
  Marca UTC; fecha local del despliegue: 15/11. Incluye codigo/dist anterior,
  referencia de imagen Docker y dump verificado con `pg_restore --list`.
- Imagen activa: `eventos-backend:whatsapp-20261116T005804Z`, tambien etiquetada
  `eventos-backend:latest` para Compose.
- Suite sobre PostgreSQL temporal: 261 pruebas aprobadas y 8 omitidas.
- UI simulada movil/escritorio: WhatsApp sin correo/login/codigo, formulario
  nominal, cupo, cancelar sin confirmar, QR persistente y otros 18 escenarios de
  cuentas/enlaces/errores. Build de produccion correcto.
- Antes del despliegue se comprobo en una transaccion de solo lectura que la
  invitacion activa de `cumpleale` tenia distribucion WhatsApp y carecia de
  correo, pero el portal devolvia `validado=False` y `puede_confirmar=False`.
- Despues se verifico el mismo enlace en produccion a 390 y 1280 px: aparece
  Confirmar asistencia y abre el formulario sin correo ni inicio de sesion.
  Se cancelo sin enviar el formulario. No se confirmo asistencia ni se enviaron
  correos, WhatsApp u otros mensajes como prueba. El token no se registro en
  esta documentacion ni se mostro en las salidas de verificacion.
