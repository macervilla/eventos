Nota de seguridad 04/11/2026: la politica vigente de identidad, PIN individual y
verificacion de invitados esta documentada en [identidad y autorizacion](identidad-y-autorizacion.md).

# Invitados, invitaciones y control de ingreso

## Uso

1. Ingresar al evento con Google y abrir **Gestion de invitados**.
2. En **Configuracion del modulo**, habilitar invitados y elegir validacion,
   aprobacion manual o automatica, plazo RSVP, listas compartidas, canales y PIN
   adicional opcional. El modulo viene desactivado para los eventos existentes.
3. Asignar los roles y permisos de cada cuenta. Un evento admite varios
   agasajados, gestores y operadores. Los roles se suman; no se concede edicion
   tecnica a agasajados o gestores.
4. Cargar invitados o grupos familiares. Email y telefono son opcionales. El
   cupo incluye al titular. El responsable identifica de quien es la invitacion.
5. Para importar, descargar la plantilla, subir el `.xlsx`, revisar la vista
   previa y confirmar. Se admiten 1000 filas, hasta 5 MB comprimidos y 20 MB
   descomprimidos. Responsable se indica mediante su email de cuenta asignada
   al evento. Las formulas se rechazan. Reintentar la confirmacion devuelve el
   resultado ya guardado; volver a subir el mismo archivo no duplica invitados.
   La opcion de actualizar conserva RSVP y nunca reduce cupos existentes.
6. Seleccionar invitados y preparar el canal privado o enviar por email.
   WhatsApp abre el mensaje preparado; Instagram y Messenger requieren copiar y
   enviar manualmente. No se registra entrega ni envio manual como verificados.
   Email registra aceptacion SMTP, que tampoco equivale a entrega. Un error se
   registra como fallido. Cada operacion tiene una clave de idempotencia.
7. El enlace `/e/{slug}/i/{token}` abre la invitacion y el formulario sin Google.
   En modo privado se acredita posesion del enlace, no identidad personal. En
   modo email una sesion activa con el mismo correo del invitado permite confirmar
   directamente, sin otro codigo. Sin sesion se valida con un codigo de un solo uso. Sin
   email previo, se verifica el correo ingresado y se lo vincula. El telefono
   requiere un proveedor oficial aun no integrado; no se simula ningun envio.
8. El invitado indica adultos incluyendo titular y solo el nombre de cada menor.
   Se guarda el total solicitado real, no el maximo. Puede corregir si las reglas
   lo permiten. Aumentar una solicitud aprobada vuelve a requerir aprobacion en
   modo manual y revoca el QR anterior. Una cancelacion invalida la credencial.
9. Solo al aprobar se habilita un QR. Se muestra y descarga en el portal,
   se envia automaticamente como adjunto al correo del invitado al aprobar (tambien
   en aprobacion automatica) y puede revocarse o regenerarse. Un fallo SMTP no
   deshace la confirmacion; guardar de nuevo permite reintentar, sin duplicar
   correos ya aceptados por SMTP.
10. El operador entra a `/e/{slug}/control-ingreso`, escanea con camara o ingresa
    la credencial leida, consulta el grupo, indica cantidad y confirma. El mismo
    QR permite ingresos parciales hasta agotar el cupo. La busqueda de
    contingencia solo consulta; no permite ingresar sin una credencial valida.
    La camara requiere permiso del usuario y HTTPS o localhost.

## Arquitectura y permisos

Se extienden `Invitacion`, `Participante`, `EventoUsuario` y `EventoModulo`.
No se reemplazan las tablas existentes. Las migraciones `0010_invitados` y
`0011_invitados_integridad` agregan los datos, indices y restricciones.
Se conservan el nombre y el slug inmutables y el flujo Google existente.

`ADMIN_EVENTO` admite configuracion y asignacion de roles. `AGASAJADO` y
`GESTOR_INVITADOS` tienen permisos configurables de gestion, distribucion,
importacion, confirmacion asistida, aprobacion y estadisticas. `CONTROL_INGRESO`
solo admite consulta y registro de asistencia, nunca aprobacion, edicion ni QR.
El propietario existente y el superadministrador conservan acceso administrativo.
Las asignaciones son por ID interno y evento, no por coincidencias especiales
con un correo. Revocar una asignacion aplica a la siguiente operacion.

Las listas pueden ser compartidas o limitarse por responsable. Listados, busqueda,
edicion, exportacion, importacion y estadisticas usan el mismo alcance. Los
operadores no reciben emails, telefonos ni nombres de menores. Los nombres de
menores solo se entregan a usuarios con permiso de consulta de invitados y al
portal de su propia invitacion validada.

Se separan distribucion, RSVP, aprobacion e ingreso. Se guardan solicitudes
historicas, movimientos de aprobacion, intentos de distribucion y auditoria con
actor y fecha. Las correcciones de asistencia agregan un movimiento negativo
con motivo; no borran el movimiento original. Los invitados se dan de baja
logicamente y sus credenciales dejan de funcionar.

Las credenciales usan 32 bytes aleatorios. Se consulta un HMAC indexado y la
copia necesaria para compartir se conserva cifrada con una clave derivada de
`SECRET_KEY`. Mantener esa variable privada y estable; cambiarla invalida
sesiones y hace inaccesibles las credenciales cifradas existentes. Los QR no
contienen nombres, contactos ni cupos. El backend comprueba siempre el estado
vigente, evento y vencimiento. Las sesiones de invitados son temporales y quedan
vinculadas al enlace y al metodo de validacion; cambiar metodo o PIN exige validar
nuevamente. Los codigos OTP solo se guardan como HMAC, tienen plazo, intentos y
consumo unico. Los limites por IP y enlace son persistentes en base de datos.

El ingreso bloquea la fila de la invitacion (`SELECT FOR UPDATE`) y usa una clave
unica por evento y operacion. Los reintentos no consumen cupos otra vez. Una
restriccion SQL impide superar aprobados o maximos. Hay una sola credencial
activa por tipo e invitacion. Una prueba usa conexiones PostgreSQL concurrentes
reales en un esquema de prueba aislado, sin modificar datos funcionales.

## Correo, medios y vistas previas

Se reutiliza SMTP por variables de entorno; no se incorporan credenciales.
No se imprimen cuerpos de correos, OTP, enlaces ni QR en logs. Los accesos
HTTP redactan enlaces privados. Si falta SMTP, se informa que no se envio.
Las pruebas automaticas sustituyen SMTP y no envian invitaciones reales.

Se valida el contenido de JPG, PNG y WebP con Pillow, ademas de firma y tamano.
Se limitan megapixeles, se eliminan metadatos y se conserva el almacenamiento
local. Se genera una portada optimizada de 1200 x 630 en JPG; tambien puede
descargarse sin datos de invitados. La portada predeterminada es un archivo
local, sin alojamiento de imagenes externo.

Vite intercepta el HTML inicial de `/e/{slug}` y `/e/{slug}/i/{token}` y obtiene
los metadatos del backend `/compartir/{slug}`. Incluye Open Graph y Twitter Card
antes de ejecutar React. La URL canonica es la pagina generica del evento; no
incluye tokens, datos personales ni cupos. El enlace personal escrito en el
mensaje es el que permite abrir el portal individual.

En produccion, configurar `FRONTEND_PUBLIC_URL=https://dominio-real` en `.env`,
servir `/media` y los assets de Vite bajo ese mismo origen y usar el middleware
de `vite preview` o enrutar los documentos de eventos hacia la respuesta HTML
del backend. Compose monta `frontend/dist` en el backend para el shell compilado.
No alcanza con subir solo archivos estaticos con fallback generico: eso perderia
los metadatos por evento. Un enlace localhost solo funciona dentro del equipo
o la red accesible al destinatario; las plataformas sociales no pueden obtener
una vista previa remota sin un dominio publico HTTPS y medios accesibles.

El servicio telefonico queda como contrato `ProveedorValidacionTelefono`, sin
proveedor concreto ni credenciales. Requiere integrar un proveedor oficial antes
de habilitar validacion telefonica para invitados reales.

## Aplicacion y verificacion

```powershell
docker compose up -d --build backend frontend
docker compose exec backend alembic upgrade head
docker compose exec backend pip install -e ".[dev]"
docker compose exec backend python -m pytest tests -q
docker compose exec frontend npm ci
docker compose exec frontend npm run build
```

La prueba concurrente necesita PostgreSQL y permiso para crear un esquema de
prueba. Lo elimina al terminar y no usa registros de eventos reales. Las pruebas
de frontend y backend no sustituyen la comprobacion de una camara fisica, la
recepcion real de correos ni las vistas previas de cada red social en produccion.

### Alcance de puerta y despliegue

La busqueda de puerta y su resumen general consultan todo el evento, incluso si
el operador tiene tambien un rol de gestor limitado a su propia lista. Ese acceso
solo devuelve datos minimos de asistencia; no amplifica su acceso a contactos,
nombres de menores, exportaciones ni edicion. Los permisos de gestion conservan
su alcance por responsable.

Los filtros permiten elegir separadamente RSVP, aprobacion o distribucion. Las
fechas de confirmacion sin zona se interpretan en `ZONA_HORARIA`.

Si se instala un proxy inverso, configurar en Uvicorn unicamente las IPs de proxy
confiables para los encabezados reenviados; no confiar en `X-Forwarded-For` enviado
por clientes arbitrarios. Esto permite aplicar los limites de abuso a IPs reales.

Un QR revocado no vuelve a emitirse por descargarlo o reenviarlo. Debe aprobarse,
emitirse o regenerarse mediante una accion autorizada explicita.

## Agasajados y acceso del receptor

En Gestion de invitados hay una seccion visible **Agasajados que pueden enviar
invitaciones**. El administrador puede pegar varios emails y asignarlos de una
vez. La operacion es idempotente por cuenta y evento, respeta cuentas inactivas
y no concede edicion tecnica ni privilegios globales. Las revocaciones y permisos
adicionales siguen disponibles en el panel de roles.

Cada invitacion preparada incluye una portada local optimizada y el mensaje con
su enlace personal. En dispositivos compatibles, **Compartir portada e invitacion**
abre el selector nativo con la imagen y el texto. Si el canal no conserva el texto,
debe enviarse tambien el enlace copiado. En navegadores sin soporte se descarga
la portada JPG y se adjunta manualmente al mensaje. `wa.me` prepara texto; no puede
adjuntar automaticamente una imagen. Instagram y Messenger tambien requieren
completar el envio privado en sus aplicaciones. Ninguna de estas acciones se
registra como entrega comprobada.

El acceso del receptor requiere una sesion verificada por defecto
(`requiere_login=true`). Si un evento anterior usaba solo un enlace sin PIN,
el portal exige ahora el codigo de email antes de mostrar datos personales y
aceptar el RSVP. No requiere registrar una cuenta de Google. Los eventos que
configuren un PIN exigen ese codigo privado. `requiere_login=false` se conserva
solo como compatibilidad explicita para el modo de posesion de enlace anterior;
no es el valor predeterminado ni se ofrece como acceso rapido en la pantalla.

La portada compartida y descargada es vertical e incluye fecha, titulo y lugar
sobre la foto, con el encuadre y la tipografia de la invitacion movil.
El backend usa Chromium de Playwright y conserva el resultado en cache. Para
ejecutar fuera de Docker: `pip install -e .` y `playwright install chromium`
desde `backend/`. La imagen Docker instala Chromium y sus dependencias.
# Enviar una invitacion por WhatsApp

La foto se genera con el encuadre, fuente, posiciones y visibilidad de los textos
guardados en la presentacion. Usa las hojas de estilo de la aplicacion y un ancho
movil de 400 px. La cache cambia al modificar esa configuracion o el estilo, por
lo que Reenviar o Descargar foto obtiene la version actual. Las fotos previamente
enviadas a un chat no se actualizan.

En la ventana y el email, la palabra **aqui** y la foto enlazan a la confirmacion
personal. WhatsApp manual no interpreta enlaces HTML ni Markdown con URL oculta:
el texto conserva la URL. Una foto adjunta abre el visor de fotos de WhatsApp,
sin un enlace web incrustado. Los botones con etiqueta y destino requieren una
integracion con WhatsApp Business. Las vistas previas de enlaces dependen de
WhatsApp y sus ajustes; no se garantiza que aparezcan.

Elegir **whatsapp** como canal y pulsar **Enviar invitacion** en la fila del
invitado. Para repetir, usar **Reenviar invitacion**: conserva el enlace personal
vigente y vuelve a cargar foto y texto. Para varias filas, usar
**Enviar / Reenviar seleccion**. La ventana muestra el destinatario, numero
internacional, foto, texto editable y enlace de confirmacion. Aunque se quite el
enlace del texto editable, se vuelve a incluir al compartir o copiar.

Si el navegador admite compartir archivos, **Enviar foto y texto** abre el
selector del dispositivo con ambos contenidos. Elegir WhatsApp y el destinatario.
En escritorio o sin esa capacidad, usar los pasos visibles **Descargar foto**,
**Copiar texto y enlace** y **Abrir WhatsApp para ...**. Adjuntar la foto en el chat
y completar el envio con **Enviar** dentro de WhatsApp. La preparacion no confirma
un mensaje enviado ni entregado. Algunos destinos omiten el texto al compartir
una foto: tambien se puede copiar y pegar el mensaje con su enlace.

La accion avanzada **Invalidar enlace anterior** es independiente de reenviar:
revoca el enlace previo. No es necesaria para repetir una invitacion.

El numero del campo WhatsApp tiene prioridad sobre Telefono. Los numeros
locales se interpretan con el pais del evento; por ejemplo, el formato
argentino `02966 15-123456` se convierte en `+54 9 2966 123456`. No se modifica
el contacto original. Sin pais conocido, usar numero internacional con `+`.
Numeros vacios o incompletos producen un resultado FALLIDO para ese invitado,
sin impedir preparar los demas contactos validos del lote.

El selector nativo para compartir la portada usa el destinatario elegido
en el celular; no vincula automaticamente el invitado seleccionado en Eventos.
Para un chat dirigido usar el boton explicito de WhatsApp.

Pruebas: `python -m pytest backend/tests/test_whatsapp.py -q` y
`python scripts/verificar-whatsapp-ui.py` (API simulada, sin enviar mensajes).



## Altas y bajas de agasajados

La asignacion de agasajados permite elegir el canal de aviso por contacto: email,
WhatsApp, Instagram, Messenger o Telegram. La baja se realiza con Quitar y conserva
el canal elegido. Solo se revocan los permisos de ese rol; los permisos de otros
roles y el acceso de superadministrador se conservan.

Los emails se envian mediante SMTP al confirmar el cambio. En WhatsApp y redes,
la app prepara el mensaje y el administrador completa el envio. Un aviso preparado
no se presenta como entregado. El texto y el resultado quedan registrados en la
auditoria existente del evento. El ultimo aviso se consulta en la gestion de invitados;
los correos fallidos pueden reintentarse sin repetir la asignacion o baja. Un aviso
antiguo no puede reintentarse despues de una nueva alta o baja.

El agasajado ve la invitacion y el apartado Mis invitados: puede agregar personas
con la agenda del dispositivo (cuando el navegador lo permite), consultar quien
lo agrego como agasajado y quien cargo cada invitado. Se respetan los permisos,
el estado del modulo y el alcance de lista propia o compartida configurados.
No se necesitan nuevas migraciones para esta funcionalidad.


### Previsualizacion y reenvio

En Gestion de invitados, **Previsualizar y configurar invitacion** muestra la portada sin enviar mensajes. El acceso **Configurar foto, textos y datos** abre el editor del evento para quienes tienen permiso.

**Enviar / Reenviar** pide confirmacion y conserva el canal registrado de cada invitado, incluso en selecciones multiples. Si aun no tiene canal, usa el seleccionado en la barra. El correo se envia por SMTP; WhatsApp abre el chat con texto y enlace personal y requiere completar el envio en esa aplicacion. La foto puede descargarse desde Gestion de invitados para adjuntarla. Los resultados manuales se muestran en un panel breve, sin abrir la previsualizacion.


El reenvio por WhatsApp permite **Compartir foto y mensaje** cuando el navegador admite compartir archivos. Se adjunta la portada JPG con el texto y enlace personal; el usuario elige WhatsApp y el destinatario. Si no admite archivos, usar **Descargar foto**, copiar el texto y adjuntar ambos en el chat. **Abrir WhatsApp (solo texto y enlace)** no adjunta la imagen. La ventana de envio no muestra una previsualizacion.


El flujo de WhatsApp usa una sola ventana con destinatario y una accion principal: **Compartir foto y mensaje**. Esta accion abre el selector del dispositivo con el archivo JPG y enlace personal. Las alternativas quedan plegadas en **Mas opciones**. Si no se admite compartir archivos, se ofrece **Descargar foto y abrir chat**, indicando que debe adjuntarse manualmente. Se retiro la opcion de copiar la foto y no se pide una confirmacion previa adicional para WhatsApp. Los correos conservan la confirmacion antes del envio.
