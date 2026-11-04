# Ingreso habitual con Google y validacion inicial

Actualizacion del 02/11/2026.

La barra superior de todas las paginas muestra el acceso al sistema, Mis sitios
cuando hay una sesion y el control para cerrar sesion. El cierre elimina la
sesion de Eventos en las pestanas abiertas; no cierra la cuenta de Google ni la
sesion del navegador. Los controles de edicion se limpian al cerrar sesion.

## Alta y bienvenida

Cuando un email aun no esta validado se envia una unica bienvenida automatica
al registrar un evento o proveedor. El estado se conserva en PostgreSQL, con
fechas `email_validado_en` y `bienvenida_enviada_en` en users. El envio usa un
bloqueo de filas por email para evitar duplicados entre cuentas con igual correo.
Una falla SMTP no se marca como entrega ni elimina el sitio registrado; la
respuesta informa el error sin invitar a crear el mismo sitio nuevamente.

El enlace inicial vence en 48 horas. Valida el email y permite vincular Google
desde esa sesion. Si la bienvenida corresponde a un evento, confirma solo ese
evento, nunca otros borradores de la cuenta. Los enlaces iniciales antiguos de
confirmacion de eventos y de recuperacion siguen siendo compatibles.

Una cuenta Gmail/Workspace validada por Google puede acreditar el email sin un
nuevo correo. Los ingresos habituales con Google no llaman al servicio SMTP.
No se agregaron contrasenas. La seccion de recuperacion permanece opcional y
plegada; el superadministrador conserva el reenvio manual para soporte.

## Google y otros proveedores

El selector pertenece a Google, no a Chrome. Una Cuenta de Google puede usar
Gmail, un dominio Workspace o una direccion de otro proveedor, como Hotmail u
Outlook, si se creo una Cuenta de Google usando esa direccion. Una cuenta
Microsoft sin Cuenta de Google no inicia sesion mediante este boton.

Referencias oficiales:
https://support.google.com/accounts/answer/27441?hl=es
https://developers.google.com/identity/gsi/web/guides/verify-google-id-token

Google solo es autoridad sobre el email en Gmail o cuando declara un dominio
Workspace (`hd`). Para correos externos, un `email_verified` historico no prueba
su propiedad actual. Por eso la primera vinculacion de una identidad Google
externa a cuentas de Eventos requiere la sesion conseguida validando ese email.
Una vez vinculada, se identifica mediante el `sub` estable de Google, sin nuevos
correos. No se permite reservar cuentas externas desconocidas mediante una
identidad Google sin prueba actual del email.

Se mantienen las verificaciones criptograficas de firma, audiencia, emisor,
vencimiento y email verificado. No se usa un Client Secret en el frontend.

## Varios sitios y emails duplicados

El ingreso muestra los sitios que administra la identidad verificada. Se admite
vincular varias filas de users con el mismo email a un mismo subject Google.
Cada destino conserva su propietario y permisos: se entrega una sesion para
esa cuenta al seleccionarlo, sin fusionar ni eliminar usuarios.

La sesion principal se conserva en localStorage y la cuenta activa por pestana
en sessionStorage. Esto permite administrar dos sitios de cuentas duplicadas
en pestanas diferentes sin intercambiar los permisos de una y otra. El cierre
de la sesion principal invalida el estado local de todas las pestanas.

La API /acceso/yo no se cachea. Sus opciones autenticadas pueden contener el
token de la cuenta correspondiente; no son una respuesta publica. En cada
peticion se sigue verificando que el usuario esta activo y que el email no cambio.
Corregir un email desde administracion desvincula Google e invalida la validacion
anterior para que el nuevo correo se compruebe una vez.

## Eventos nuevos y publicacion

Con sesion del propietario y email validado, crear otro evento no requiere un
nuevo mail y lo publica directamente. Escribir un email validado sin acreditar
una sesion no autoriza la publicacion: el evento queda en borrador y su
propietario puede ingresar con Google y pulsar Publicar evento. No se publican
automaticamente todos los borradores al iniciar sesion.

## Despliegue

La migracion `0014_acceso_google` anade las dos fechas opcionales e indexa
google_subject sin unicidad. Conserva las vinculaciones existentes y acredita
los Gmail previamente vinculados sin reenviar correos historicos. No cambia
roles, propietarios, eventos, proveedores, catalogo GeoNames ni puertos.

Antes de migrar, crear un respaldo de la base existente:

```bash
cd /var/www/eventos
bash scripts/geografia-vps.sh backup
docker compose --env-file .env.vps -f compose.vps.yml build backend
bash scripts/geografia-vps.sh migrate
docker compose --env-file .env.vps -f compose.vps.yml up -d --no-deps backend
docker compose --env-file .env.vps -f compose.vps.yml run --rm frontend-build
```

No necesita variables obligatorias nuevas ni cambios de Docker Compose. Se
conservan GOOGLE_CLIENT_ID y SMTP del VPS. El origen local debe seguir autorizado
en el cliente Google si se usa http://localhost:5179.

## Verificacion

Suite completa con PostgreSQL de pruebas aislado: 84 pruebas aprobadas. Incluye
bienvenida idempotente, fallo SMTP, Google repetido sin mails, vinculacion inicial
Hotmail, rechazo de identidades externas sin prueba, cuentas duplicadas y roles,
confirmacion de un unico evento, no publicacion por solo escribir un email y
correccion de email. Tambien se ejecutan las pruebas criptograficas de Google,
GeoNames, invitados y concurrencia de ingreso.

```bash
python scripts/verificar-acceso-ui.py
```

Prueba de navegador con API y Google simulados: seleccion de sitios, sesion de
la cuenta correcta, bienvenida inicial, URL sin token, cero solicitudes de
nuevos mails, cuentas distintas por pestana, logout compartido y ancho movil.
No envia correos ni utiliza cuentas Google reales.


## Menu de cuenta

Con sesion iniciada, la barra superior muestra **Mi cuenta**. Al desplegarlo
aparecen email, **Mis sitios**, **Dashboard** si tiene permiso y **Cerrar sesion**.
El menu inicia cerrado y se cierra al elegir una opcion, tocar fuera, pulsar
Escape o cambiar de pagina/cuenta. No cambia los permisos del backend.
