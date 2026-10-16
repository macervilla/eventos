const CLAVE_SESION = "eventos_sesion";

export function obtenerTokenSesion(): string | null {
  try {
    // localStorage.getItem: lee un valor guardado en el navegador (persiste entre pestañas)
    return localStorage.getItem(CLAVE_SESION);
  } catch {
    return null;
  }
}

export function guardarTokenSesion(token: string) {
  try {
    localStorage.setItem(CLAVE_SESION, token);
  } catch {
    // Sin almacenamiento disponible: la sesion dura solo mientras no se recargue.
  }
}

export function cerrarSesion() {
  try {
    localStorage.removeItem(CLAVE_SESION);
  } catch {
    // nada que limpiar
  }
}
