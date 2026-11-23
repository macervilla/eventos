# Despliegue de URLs sin prefijos, 15/11/2026

Actualizacion del VPS solicitada por el usuario. La version activa conservaba
`/e/` y `/p/` en generadores del backend y rutas React, aunque la base ya estaba
en `0022_solicitudes_invitacion`. Se publicaron las fuentes actuales y el build
de produccion con `VITE_API_URL=/eventos/api` y `--base=/eventos/`.

- Eventos y proveedores: `https://acersistemas.site/eventos/{slug}`.
- Invitaciones personales: `/eventos/{slug}/i/{token}#mi-confirmacion`.
- Tambien quedaron publicados los ajustes de formularios, minutos, edicion por
  doble clic, autoguardado y titulos de seccion de esta sesion.
- Sin migraciones, cambios de variables privadas ni recreacion de PostgreSQL o
  MediaMTX. Se conservo la configuracion Nginx y se valido antes de recargarla.
- Respaldo privado: `/var/backups/eventos/urls-sin-prefijos-20261116T003933Z/`.
  La marca esta en UTC; el despliegue fue el 15/11 en Argentina. Incluye codigo,
  frontend anterior, imagen Docker anterior y dump PostgreSQL cuya estructura se
  verifico con `pg_restore --list`. El directorio debe permanecer privado.
- Imagen activa: `eventos-backend:urls-20261116T003933Z`, etiquetada tambien como
  `eventos-backend:latest` para Compose.
- Se conservaron los assets anteriores para las pestanas que ya estaban abiertas.
  Durante la comprobacion se corrigio el permiso de lectura del nuevo directorio
  `frontend/dist` a 755 para Nginx; posteriormente las paginas dieron HTTP 200.

Validacion: 253 pruebas aprobadas y 8 omitidas sobre PostgreSQL temporal aislado;
build de produccion y prueba de rutas simuladas en escritorio y movil correctos.
En produccion se verificaron health, resolvedor de ambos tipos, paginas, assets,
recarga, metadatos canonicos, 404 para slugs inexistentes/prefijos anteriores y
ausencia de errores JavaScript en escritorio y movil. El generador activo de
WhatsApp se ejecuto con objetos en memoria y token ficticio: produjo la URL
personal sin `/e/`, sin acceso a la base ni envios.

Los mensajes ya enviados conservan su texto original. Los nuevos enlaces deben
generarse de nuevo desde la aplicacion. Se mantiene la decision documentada en
`urls-publicas.md`: las rutas anteriores no tienen redireccion de compatibilidad.
