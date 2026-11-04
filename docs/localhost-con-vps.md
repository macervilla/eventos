# Usar desde localhost los datos del VPS

El frontend se ejecuta en http://localhost:5179 y utiliza la API de
https://acersistemas.site/eventos/api mediante el proxy de desarrollo de Vite.
Las consultas, cambios y subidas de imagenes se procesan en el VPS y usan su
PostgreSQL y su volumen de media. No se necesita exponer PostgreSQL ni copiar
la clave de la base. El backend local no participa en estas solicitudes.

## Activar en PowerShell

```powershell
cd C:\mentoria\proyectosvs\eventos
docker compose -f docker-compose.yml -f compose.local-vps.yml up -d --no-deps --force-recreate frontend
```

Abrir http://localhost:5179 y recargar con Ctrl+F5. La sesion del sitio del VPS
no se comparte automaticamente con localhost. Una sesion local anterior puede
ser rechazada por el backend remoto: cerrar sesion e ingresar nuevamente.

Para Google, el cliente configurado en el VPS debe autorizar el origen
http://localhost:5179. Los correos enviados por el VPS siguen apuntando al sitio
publico. Para abrir un enlace de ingreso recibido en localhost, reemplazar
solamente https://acersistemas.site/eventos/ingresar por
http://localhost:5179/ingresar, conservando toda la consulta ?enlace=... y su
destino. No compartir esos enlaces porque permiten iniciar sesion.

Todas las modificaciones realizadas desde localhost afectan los datos reales,
incluyendo edicion de cuentas, bajas logicas, eventos y reenvio de correos.
La configuracion esta destinada a probar cambios de frontend. Los cambios al
codigo del backend local no afectan a la API del VPS.

## Verificar sin modificar datos

```powershell
Invoke-RestMethod http://localhost:5179/api-vps/health
```

Debe devolver status=ok. Las URLs /media/... tambien se reenvian al backend del
VPS, por lo que los archivos que aparecen en la base compartida se pueden leer.

## Volver a la API y base locales

```powershell
docker compose -f docker-compose.yml up -d --no-deps --force-recreate frontend
```

No se borran los datos de la base local ni se cambian las variables del .env.
