# Solicitudes de invitacion y contacto publico del agasajado

La tarjeta de una cuenta Google verificada sin invitacion ofrece una solicitud
dirigida a un agasajado del evento. No aparece en visitantes anonimos ni en el
flujo de invitacion personal valida. Solicitar, contactar y aprobar una solicitud
son operaciones distintas de confirmar asistencia; ninguna de ellas emite un QR.

## Habilitacion y contactos

En Gestion de invitados, abrir **Solicitudes de invitacion** y desplegar
**Nombre y contactos publicos de los agasajados**. El administrador puede configurar
los agasajados del evento; cada agasajado con permiso de editar invitados puede
configurar exclusivamente su propia fila.

Para recibir solicitudes, habilitar la fila y completar un nombre publico. El
nombre publico no se completa automaticamente desde el perfil. Los contactos
privados existentes de usuarios y avisos de asignacion no se publican ni copian.

WhatsApp y email se ingresan explicitamente y tienen autorizaciones independientes
para publicarlos. Al seleccionar el agasajado en la tarjeta, aparecen solamente
los botones autorizados, como maximo uno por cada medio. Si no hay contactos
publicados, se indica usar los canales habituales; el formulario sigue disponible
si ese agasajado habilito solicitudes. Si no hay ningun agasajado habilitado, se
muestra solamente el mensaje de canales habituales.

El nombre publico y los contactos dejan de ofrecerse si se deshabilita la fila,
se revoca el rol o se desactiva el usuario. El endpoint solo ofrece agasajados
activos del evento actual. Sus respuestas tienen Cache-Control private, no-store.

Los enlaces `wa.me` usan el numero E.164 sin el signo + y el mensaje solicitado.
El `mailto` incluye asunto y cuerpo codificados. Solo llevan el titulo publico
del evento; no llevan tokens, IDs ni datos del visitante. Abrirlos no envia
mensajes automaticamente ni crea registros de invitados.

## Identidad y duplicados

La solicitud requiere nombre, apellido, agasajado y medio de contacto. Email
usa exclusivamente el correo acreditado por la sesion Google. WhatsApp requiere
un numero internacional valido, pero ese numero se guarda como contacto aportado,
no como identidad verificada. La invitacion siempre queda asociada al correo
verificado de la cuenta. El proceso previo de confirmacion segura no se modifica.

Nombre y apellido se comparan sin tildes, distinguiendo sus campos, normalizando
mayusculas y espacios. Email se normaliza a minusculas y sin espacios. Telefonos
se comparan en E.164 cuando es posible, reutilizando la normalizacion existente.
Los numeros incompletos no se consideran coincidencias de identidad. El alta
administrativa conserva la presentacion original de los telefonos existentes.

La clave unica `(evento_id, email_verificado)` conserva una unica solicitud por
identidad dentro de cada evento, incluso si cambia el agasajado elegido o se
repite el envio. Se conserva el destinatario y los datos originales; no se
sobrescriben con datos contradictorios. Una solicitud ya resuelta tampoco se
reabre automaticamente. No hay una segunda notificacion: la bandeja y la
auditoria reciben una sola alta. No se agrego envio automatico de correos.

Si ya hay una invitacion vigente con ese correo, no se crea otra invitacion ni una
solicitud nueva, ni se revela al visitante informacion de otros invitados.
La respuesta publica es siempre el mensaje generico de recepcion solicitado.
Una invitacion revocada, rechazada o inactiva puede originar una solicitud para
revision, pero aprobarla no reactiva el registro: debe revisarse primero mediante
el flujo administrativo existente, sin crear otro cupo.

Coincidencias por nombre, telefono o solicitudes pendientes de otras cuentas
se marcan para revision. No se fusionan personas por compartir nombre o telefono.
Los nombres iguales con correos distintos pueden corresponder a personas
distintas: la aprobacion exige que el revisor confirme que reviso las coincidencias.
Si un telefono ya acredita otra identidad mediante la verificacion telefonica
existente, se bloquea el alta hasta revisar los contactos; no se reasigna esa
identidad. Un telefono aportado sin verificar nunca prueba que corresponda al
solicitante.

Las altas administrativas e importaciones tambien consultan las invitaciones
existentes, normalizan las comparaciones y auditan coincidencias y solicitudes
pendientes. La lista de invitados muestra una advertencia para posibles
duplicados, sin fusionarlos automaticamente.

## Revision, permisos y aprobacion

Cada agasajado con permiso de ver invitados consulta solo las solicitudes
dirigidas a el, incluso cuando las listas de invitados son compartidas. Aprobar
o rechazar requiere editar invitados. El administrador conserva supervision
general. Un rol revocado no habilita esta nueva bandeja.

El panel permite filtrar Pendiente, Aprobada y Rechazada. Solo muestra candidatos
de listas autorizadas; las coincidencias con otra lista se indican sin revelar
sus datos. Una coincidencia de identidad en otra lista necesita revision del
administrador y una seleccion explicita de la invitacion existente.

Al aprobar se comprueban nuevamente los duplicados. Se reutiliza la invitacion
existente del mismo correo cuando corresponde; no se sobrescriben sus contactos,
cupos, responsable ni RSVP. Las invitaciones inactivas, rechazadas o revocadas
requieren revision por el flujo de administracion existente.

Si no existe una invitacion, se utiliza guardar_invitado, con el agasajado como
responsable, cupo inicial de una persona y asistencia/aprobacion pendientes.
El medio preferido y el contacto se conservan para Enviar / Reenviar desde la
lista actual. La aprobacion no envia una invitacion automaticamente, no acredita
un telefono ni confirma asistencia. La confirmacion y el QR siguen exigiendo
el correo registrado y sus controles actuales.

## Persistencia y concurrencia

Migracion aditiva: `0022_solicitudes_invitacion`, posterior a `0021_slugs_publicos`.
Agrega contactos_publicos_agasajado y solicitudes_invitacion. No cambia ni borra
eventos, invitados, cupos, datos de agasajados, archivos o credenciales existentes.
Todas las publicaciones empiezan deshabilitadas; no hay backfill de datos privados.

Solicitudes, aprobaciones y guardar_invitado comparten un lock de la fila del
evento. La aprobacion bloquea ademas la solicitud y comprueba su estado dentro de
la transaccion. Aprobar nuevamente devuelve el mismo invitado sin crear otro
cupo. La restriccion unica de solicitudes y la clave de duplicados existente de
invitaciones complementan el bloqueo. Los estados terminales no cambian de
Aprobada a Rechazada ni viceversa mediante este endpoint.

## Archivos y API

- `backend/app/{api,schemas,models,services}/solicitudes_invitacion.py`.
- `backend/app/services/coincidencias_invitados.py`: comparaciones comunes.
- Integracion: main.py, models/__init__.py, api/invitados.py y services/invitados.py.
- `frontend/src/components/{SolicitarInvitacion,SolicitudesInvitacionPanel}.tsx`.
- Integracion: ConfirmacionInvitado.tsx, InvitadosPage.tsx y styles.css.
- `backend/tests/test_solicitudes_invitacion.py`, `test_solicitudes_postgres.py`.
- `scripts/verificar-solicitudes-invitacion-ui.py`.

Todas las rutas siguientes llevan el prefijo `/invitados/{slug}` de la API:

| Metodo y ruta | Autorizacion |
| --- | --- |
| GET /solicitudes/opciones | Cuenta Google verificada; solo nombres/contactos habilitados |
| POST /solicitudes | Cuenta Google verificada; contacto email sujeto a esa identidad |
| GET /solicitudes/contactos | Administrador o agasajado, con alcance propio |
| PUT /solicitudes/contactos/{agasajado_id} | Configuracion autorizada; agasajado solo su fila |
| GET /solicitudes | Administrador o agasajado, con alcance propio |
| POST /solicitudes/{id}/resolver | Editar invitados, evento y destinatario autorizados |

## Despliegue

Actualizar conjuntamente backend y frontend. Aplicar `alembic upgrade head`
antes de iniciar la imagen nueva. No reemplazar .env.vps ni eliminar volumenes.
No se necesitan nuevas variables, cambios de Nginx ni cambios de almacenamiento.

Desde una sesion SSH interactiva, con fuentes actualizadas y respaldo previo:

```bash
cd /var/www/eventos
dc() { docker compose --env-file .env.vps -f compose.vps.yml --profile video "$@"; }
dc build backend
dc stop backend
dc run --rm -T --interactive=false --no-deps backend alembic upgrade head < /dev/null
dc run --rm -T --interactive=false --no-deps frontend-build < /dev/null
dc up -d --no-deps --force-recreate backend
curl --fail --retry 20 --retry-all-errors --retry-delay 2 http://127.0.0.1:8009/health
```

Ejecutar cada paso solo si el anterior termina correctamente. Si se automatiza
desde PowerShell, copiar primero un archivo de script al VPS y ejecutarlo por
SSH; no compartir la entrada estandar del script con Docker interactivo.

Despues, habilitar explicitamente los nombres/contactos en Gestion de invitados.
Desplegado al VPS el 13/11/2026. Ver [acta y verificaciones](despliegue-solicitudes-2026-11-13.md).

## Validacion realizada

- Suite completa con PostgreSQL temporal: 252 pruebas aprobadas y 8 omitidas por
  sus condiciones de entorno; las 14 pruebas nuevas de solicitudes pasaron.
- Concurrencia real entre solicitudes de una cuenta dirigidas a distintos
  agasajados, aprobaciones simultaneas y alta administrativa contra aprobacion:
  una sola invitacion y un solo cupo, sin QR ni segundo aviso.
- Migracion 0022 aplicada en PostgreSQL temporal y probada con
  upgrade/downgrade/upgrade aislado, conservando usuarios, eventos y asignaciones.
- Build TypeScript/Vite con base /eventos/ correcto y chequeo de imports sin errores.
- UI en movil y escritorio: ningun contacto, solo WhatsApp, solo email, ambos,
  formulario, aprobacion/cancelacion, filtros de estado y publicacion explicita.
  APIs simuladas; no se enviaron correos ni mensajes reales.
