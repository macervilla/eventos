# Identidad y autorizacion de Eventos

Actualizacion: 04/11/2026.

## Comportamiento

- Administradores de evento, agasajados, gestores y control de ingreso requieren una sesion emitida despues de verificar Google: firma, audiencia, emisor, expiracion, `sub` y `email_verified`.
- Cada peticion valida usuario activo, email vigente y el subject Google vinculado. Los roles se consultan en el evento solicitado; no se incorporan como permisos confiables al JWT.
- Se conservan usuarios, propietarios y asignaciones existentes. El propietario explicito del evento y el superadministrador mantienen sus atribuciones, tambien bajo autenticacion Google.
- Un enlace de bienvenida/recuperacion valida el correo y permite la vinculacion inicial de Google. Su credencial tiene tipo `validacion_email`; no permite administrar, consultar sitios privados ni publicar eventos.
- La confirmacion antigua de evento tampoco publica ni concede acceso administrativo: el propietario inicia sesion con Google para publicar. Los eventos ya publicados conservan su estado.
- El subject Google conserva la identidad aunque cambie su email. Para validar una invitacion por coincidencia con Google se compara el email realmente verificado en esa sesion, no un correo antiguo persistido. No se crean usuarios duplicados por ese cambio.
- Las sesiones administrativas anteriores sin prueba del metodo de autenticacion se rechazan. Es necesario volver a iniciar sesion con Google.

## Invitados sin cuenta de Google

La verificacion se configura por evento y se exige en FastAPI antes de consultar datos privados, responder RSVP o descargar el QR. El contenido publico del evento permanece visible.

| Metodo | Comprobacion |
|---|---|
| Email | Codigo temporal enviado exclusivamente al email registrado por el organizador. No se acepta asociar un nuevo email por poseer el enlace. Una sesion Google verificada cuyo email coincide con el autorizado tambien acredita ese acceso. |
| Telefono | Codigo enviado y comprobado mediante Twilio Verify, al telefono previamente registrado. No se acepta un telefono proporcionado por el visitante. Sin proveedor configurado se rechaza la operacion. |
| PIN personal | Codigo criptograficamente aleatorio de 10 digitos, distinto por invitacion, almacenado mediante HMAC con la clave del servidor. Solo un gestor autorizado puede generarlo. Se muestra una vez para su entrega presencial, por llamada u otro canal independiente del enlace. |
| Verificacion desactivada | El administrador elige expresamente permitir el acceso por posesion del enlace. La interfaz explica que quien posea el enlace podra responder. |

El PIN compartido antiguo del evento no es prueba individual de identidad. Los eventos que lo usaban pasan a exigir PIN por invitacion; el organizador debe generar y entregar esos PIN personales. No se transmiten automaticamente junto al enlace ni en la tarjeta.

La entrega independiente del PIN debe completarla el organizador. La aplicacion registra el canal declarado, pero no puede comprobar una entrega presencial o una llamada externa.

Las sesiones de invitado duran 30 minutos y se vinculan a la invitacion, el enlace activo y la regla de verificacion. Cambiar el contacto, regenerar el PIN, cambiar la regla o revocar el enlace invalida las pruebas anteriores. Los OTP expiran, tienen limite de intentos y no pueden reutilizarse despues de ser consumidos.

El JWT de invitado, el token del enlace y la validacion de correo se rechazan en las rutas administrativas. Los controles de cupo, aprobacion, QR distinto del enlace, ingreso parcial y auditoria se reutilizan.

Juan puede validar su invitacion y confirmar. Pedro, con una copia del enlace, solo ve el contenido publico hasta superar la verificacion de Juan. La interfaz le indica contactar a un organizador, agasajado o gestor para obtener una invitacion propia. El sistema no puede impedir que una persona comparta deliberadamente tambien su prueba independiente o su sesion ya validada.

## Base de datos y respaldo

Migracion aditiva `0017_verificacion_invitados`, desde `0016_textos_proveedor`:

- `invitaciones.pin_personal_hash`: opcional, 64 caracteres.
- `validaciones_invitado.metodo`: `email` por defecto, conservando los desafios existentes.
- `validaciones_invitado.proveedor_referencia`: referencia opcional del desafio del proveedor.

No se crean nuevas tablas ni otra base de datos. No se cambian roles, propietarios, emails ni estados de eventos durante la migracion.

La migracion se verifico en PostgreSQL con upgrade, downgrade y un nuevo upgrade dentro de una transaccion, comprobando que las filas se conservan y revirtiendo toda la prueba. El esquema original y la version Alembic quedaron intactos al terminar esa verificacion.

Antes del despliegue se genero un dump completo y respaldo del codigo, configuracion y frontend en el VPS:

`/var/www/eventos/backups/identidad-ssmymK/`

El dump se verifico con `pg_restore --list`. Permanece en el servidor con acceso restringido; contiene datos privados. Tambien se compararon conteos y hashes de los datos existentes antes y despues de la migracion, excluyendo exclusivamente las columnas nuevas.

## Proveedor telefonico

La integracion usa la API oficial de Twilio Verify por HTTPS. Configurar exclusivamente en el servidor:

```dotenv
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_VERIFY_SERVICE_SID=
```

El token de autenticacion se maneja como secreto, nunca se entrega al navegador. Las respuestas de error externas se sustituyen por mensajes sin credenciales. El proveedor debe aceptar el envio y devolver una verificacion `approved` para validar el codigo; no hay una simulacion en produccion.

Actualmente no hay un proveedor telefonico configurado. Las pruebas de esa integracion utilizan respuestas simuladas, sin SMS reales. Se requiere una cuenta operativa, permisos del servicio y capacidad de envio a los destinos elegidos. Esta integracion de verificacion no habilita el envio automatico de invitaciones ni de avisos de roles por WhatsApp, Instagram o Messenger.

Referencias: [validacion de tokens Google](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token), [envio con Twilio Verify](https://www.twilio.com/docs/verify/api/verification), [comprobacion de codigos](https://www.twilio.com/docs/verify/api/verification-check).

## Archivos del ajuste de identidad

- Backend: `app/core/seguridad.py`, `app/core/config.py`, `app/api/acceso.py`, `app/api/invitados.py`, `app/models/invitaciones.py`, `app/schemas/acceso.py`, `app/schemas/invitados.py`.
- Servicios: `acceso.py`, `eventos.py`, `invitados.py`, `invitados_portal.py`, nuevo `verificacion_telefono.py`.
- Migracion: `backend/alembic/versions/0017_verificacion_invitados.py`.
- Frontend: `src/api/client.ts`, `src/api/sesion.ts`, `components/IngresoEvento.tsx`, `pages/LoginPage.tsx`, `pages/EventPublicPage.tsx`, `pages/InvitacionPersonalPage.tsx`, `pages/InvitadosPage.tsx`.
- Configuracion de ejemplo: `.env.example`, `.env.vps.example`.
- Pruebas: nuevos `tests/autenticacion.py`, `tests/test_identidad_invitados.py`, `tests/test_verificacion_telefono.py`, `tests/verificar_migracion_0017.py`; se actualizaron los helpers y expectativas de `test_administracion.py`, `test_acceso_habitual.py`, `test_edicion_evento.py` y `test_invitados.py`. Se ajusto el fixture antiguo de `test_portada_invitacion.py` al renderer existente, sin cambiar ese renderer.
- Interfaz: nuevo `scripts/verificar-identidad-ui.py` y actualizacion de `scripts/verificar-acceso-ui.py`.

## Verificacion ejecutada

- `python -m pytest tests -q`: 130 aprobadas, 8 omitidas por falta de `GEO_TEST_DATABASE_URL` para las pruebas de geografia. Incluye control concurrente de ingreso sobre un esquema PostgreSQL aislado y temporal.
- Pruebas nuevas de Juan/Pedro, roles aislados por evento, tokens no administrativos, PIN individual y rotacion, OTP de un uso, contacto autorizado, proveedor ausente y errores sin secretos.
- `python -m tests.verificar_migracion_0017`: upgrade/downgrade con rollback y datos conservados en PostgreSQL.
- Playwright: acceso Google, vinculacion sin permisos por email, cuenta activa por pestana, agasajados, menus y verificacion de invitado por email/telefono/PIN en movil y escritorio, con APIs simuladas.
- Compilacion TypeScript y Vite de produccion correcta.

No se enviaron mensajes reales ni se confirmaron asistencias reales para probar esta funcionalidad.
