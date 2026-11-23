# Despliegue de solicitudes y confirmacion segura, 13/11/2026

Actualizacion aplicada con autorizacion del usuario al VPS de Eventos.
Incluye el flujo de correo verificado para confirmar/obtener QR y las solicitudes
de invitacion con contactos publicos autorizados.

- Respaldo privado: `/var/backups/eventos/solicitudes-20261113T184641Z/`.
  Conserva codigo/dist anteriores, referencia de imagen Docker, configuracion y
  dump PostgreSQL verificado con pg_restore --list. Mantenerlo privado.
- Migracion: `0021_slugs_publicos` a `0022_solicitudes_invitacion (head)`.
- Comparacion antes/despues de migrar: se conservaron cantidades de usuarios,
  eventos, proveedores, invitados, participantes, credenciales y fotos, ademas
  de sumas de cupos asignados, aprobados e ingresos registrados.
- Backend construido y frontend compilado con base `/eventos/`; backend recreado.
  Se conservaron .env.vps, Compose, configuracion Nginx y montajes de multimedia.
- Nginx validado; health local y publico HTTP 200; pagina publica HTTP 200.
- El endpoint nuevo de opciones de solicitudes devuelve 401 sin autenticacion.
- Navegador real sin sesion: pagina y assets cargados, tarjeta sin Confirmar,
  boton de ingreso visible y sin errores JavaScript; escritorio y movil.
- MediaMTX conserva el mismo contenedor; video habilitado y API interna accesible.
  No se afirmo una nueva prueba de transmision fisica desde celular.
- Contactos publicos habilitados tras migrar: cero. No se copiaron datos privados
  de las cuentas ni se publicaron contactos automaticamente.

No se enviaron mensajes ni se crearon solicitudes/invitaciones reales como prueba.
La validacion funcional previa en local dio 252 pruebas aprobadas y 8 omitidas,
con concurrencia PostgreSQL y UI simulada para cuentas verificadas.

Para recibir solicitudes, un administrador o agasajado autorizado debe habilitar
su nombre publico en Gestion de invitados → Solicitudes de invitacion → Nombre
y contactos publicos de los agasajados. Email y WhatsApp se publican solo cuando
se completan y se autorizan sus casillas correspondientes.
