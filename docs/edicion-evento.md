# Acceso y edicion desde la invitacion

La pagina `/e/{slug}` conserva la invitacion publica y muestra **Ingresar** en la
esquina superior derecha. Google se abre desde una ventana de ingreso; un error
de autenticacion no impide cerrar esa ventana y seguir viendo la invitacion.
El ingreso se completa sobre la misma URL. La alternativa por email tambien
conserva el destino, validado como ruta interna por frontend y backend.

La primera autenticacion con Google vincula el `sub` verificado criptograficamente
al usuario interno registrado por su email verificado, o crea un visitante sin
permisos. Las siguientes autenticaciones resuelven por `users.google_subject`.
Una identidad Google distinta no puede sustituir una vinculacion existente.
El JWT local identifica al usuario por su ID interno. No se confia en un email
enviado por el navegador para autorizar cambios.

`GET /eventos/{slug}/permisos` devuelve el usuario autenticado, su relacion y el
permiso de edicion. El propietario, miembros `PROPIETARIO` y `ENCARGADO`, y el
rol persistente de superadministrador pueden editar. Otros roles son visitantes
para estas operaciones. FastAPI vuelve a comprobar cuenta activa y permisos en
cada actualizacion de datos, encuadre o imagen. Revocar la asignacion impide la
siguiente operacion aunque exista una sesion abierta.

`acersistemasweb@gmail.com` ya es propietario de `cumple-lili` por su asignacion
existente. No hay ninguna regla que conceda permisos globales por ese email.

**Editar evento** habilita los controles. El formulario permite cambiar titulo
visual, descripcion, fecha y hora, estilos, colores, tipografia y modulos. La
ventana de lugar permite elegir salon o domicilio, direccion y coordenadas del
mapa. Cada ventana tiene Guardar y Cancelar. Los modulos disponibles corresponden
a secciones implementadas: detalles, ubicacion y galeria.

El nombre original y el slug son permanentes. El contrato de actualizacion no
los acepta y una proteccion de PostgreSQL tambien impide cambiarlos. El titulo
visual es un atributo independiente y usa el nombre original como alternativa.

En modo edicion, doble clic en la portada o en una imagen de la galeria abre el
selector. Tambien hay botones para teclado y dispositivos tactiles. Se muestra
una vista previa; solo Guardar imagen sube el archivo. Cancelar no sube nada.
Se conserva el almacenamiento local y el encuadre de portada. Se admite una
portada activa y hasta 10 imagenes de galeria por evento por el momento.
Los reemplazos no consumen un lugar adicional; la baja de la version anterior
es logica. El backend controla los limites y el tamano maximo configurado
(5 MB por defecto), y registra al usuario interno que realizo la carga.

Migracion (ya aplicada en el entorno actual):

```bash
docker compose exec backend alembic upgrade head
```

Pruebas:

```bash
docker compose exec backend python -m pytest tests -q
docker compose exec frontend npm run build
```

Las pruebas automaticas de Google utilizan claves RSA efimeras. Para verificar
el ingreso real, usar Ingresar en la pagina del evento y comprobar que aparezca
la cuenta junto a Editar evento. Un `POST /acceso/google` exitoso y la consulta
de permisos quedan reflejados en los logs sin registrar tokens.

## Presentacion de la galeria publica

Las imagenes aparecen debajo de los detalles y el lugar de la invitacion.
La migracion `0009_galeria_publica` habilita las galerias existentes con imagenes.
Al cargar una imagen tambien se habilita el modulo; el administrador puede ocultarlo
explicitamente desde **Editar evento > Configurar galeria**.

La misma ventana permite elegir **Carrusel** o **Grilla**. En grilla se configuran
filas y columnas, con hasta 10 espacios por pagina. Si la capacidad elegida es
menor que la cantidad de imagenes, hay paginacion para recorrerlas todas. En
celulares se ajustan las columnas a un maximo de dos para mantener la legibilidad.
El carrusel muestra una imagen por vez, con botones, indicadores, teclas de flecha
y deslizamiento tactil. No avanza automaticamente.

La configuracion se guarda en `evento_modulos.configuracion_json`, mediante la
API de actualizacion del evento, con los mismos permisos de administrador o
colaborador autorizado. El backend valida modo, filas, columnas y capacidad,
y limita las cargas a 10 imagenes por evento; reemplazar una no suma al limite.

## Mover y ocultar textos de portada

En **Editar evento > Mover u ocultar textos**, arrastrar por separado fecha,
titulo y lugar con mouse o pantalla tactil. Tambien se puede enfocar un bloque
y usar flechas (Shift mueve en pasos mayores). Desmarcar **Mostrar** oculta el
bloque; marcarlo nuevamente recupera su posicion. **Guardar textos** publica los
cambios y **Cancelar** conserva la configuracion anterior. Un error de guardado
mantiene el borrador disponible para reintentar.

Las posiciones son porcentajes del espacio disponible para cada bloque, para
mantenerlos dentro de la portada en distintas pantallas. Los eventos sin una
configuracion guardada conservan su presentacion original.

`PUT /eventos/{slug}/textos-portada` requiere los mismos permisos de edicion
del evento. Guarda la configuracion en el modulo interno `textos_portada`, en
`evento_modulos.configuracion_json`; no requiere migracion. Las ediciones de
datos o galeria conservan esta configuracion. La respuesta publica del evento
incluye `textos_portada` para que visitantes y administradores vean lo guardado.

Verificacion: `python -m pytest backend/tests/test_textos_portada.py -q` y,
con Vite iniciado, `python scripts/verificar-textos-portada-ui.py`. La prueba
de navegador simula la API y no modifica datos reales del VPS.


## Colores de los textos de la invitacion

En **Editar evento > Datos del evento**, debajo de la tipografia, la paleta
permite elegir colores independientes para titulo, fecha/hora y lugar. Hay ocho
muestras y un selector personalizado por bloque, con vista previa. **Guardar**
aplica los colores a la pagina publica y a la foto generada para compartir.
**Cancelar** conserva los anteriores.

Los colores no cambian posiciones ni visibilidad. Los eventos anteriores usan
blanco hasta guardar otra eleccion. La configuracion `colores_textos` se valida
como tres colores hexadecimales y se guarda en el modulo interno del mismo
nombre, sin migracion. Los clientes que omiten ese campo conservan lo guardado.
El generador de fotos incluye esos colores en la clave de cache.


## Menu del evento

Los datos de la cuenta y las acciones se encuentran en **Menu del evento**,
cerrado por defecto, encima de la foto. Incluye email y rol, edicion, gestion
de invitados, control de ingreso y salida, segun los permisos de cada cuenta.
Elegir una accion, tocar fuera o pulsar Escape vuelve a cerrarlo. Solo hay un
menu abierto a la vez; la invitacion queda libre de controles superpuestos.
