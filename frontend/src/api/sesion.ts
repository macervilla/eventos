const CLAVE_SESION = "eventos_sesion";
export const EVENTO_SESION = "eventos:sesion";
let memoria: string | null = null;
const CLAVE_CUENTA = "eventos_cuenta_pestana";
const CLAVE_VALIDACION = "eventos_validacion_email";
export function guardarValidacionEmail(token: string) { try { sessionStorage.setItem(CLAVE_VALIDACION, token); } catch { /* Reabrir el enlace si el navegador no permite almacenar la validacion. */ } }
export function obtenerValidacionEmail() { try { return sessionStorage.getItem(CLAVE_VALIDACION); } catch { return null; } }
let activa: { base: string; token: string } | null = null;

export function obtenerTokenSesion(): string | null {
  try {
    // localStorage.getItem: lee un valor guardado en el navegador (persiste entre pestañas)
    const base = localStorage.getItem(CLAVE_SESION);
    if (!base) return null;
    try {
      const cuenta = activa ?? JSON.parse(sessionStorage.getItem(CLAVE_CUENTA) || "null");
      if (cuenta?.base === base) return cuenta.token;
    } catch { /* Si no hay almacenamiento de pestana, usar la sesion principal. */ }
    return base;
  } catch {
    return memoria;
  }
}

export function guardarTokenSesion(token: string) {
  const anterior = obtenerTokenSesion();
  memoria = token;
  activa = null;
  try {
    localStorage.setItem(CLAVE_SESION, token);
    sessionStorage.removeItem(CLAVE_CUENTA);
    sessionStorage.removeItem(CLAVE_VALIDACION);
  } catch {
    // Sin almacenamiento disponible: la sesion dura solo mientras no se recargue.
  }
  if (anterior !== token) window.dispatchEvent(new Event(EVENTO_SESION));
}

// Una cuenta duplicada puede administrar otro sitio en otra pestana sin cambiarla.
export function seleccionarCuentaSesion(token: string) {
  const anterior = obtenerTokenSesion();
  let base: string | null = null;
  try { base = localStorage.getItem(CLAVE_SESION); } catch { /* usar sesion en memoria */ }
  if (!base) { guardarTokenSesion(token); return; }
  activa = { base, token };
  try { sessionStorage.setItem(CLAVE_CUENTA, JSON.stringify(activa)); } catch { /* activa queda en memoria */ }
  if (anterior !== token) window.dispatchEvent(new Event(EVENTO_SESION));
}

export function cerrarSesion() {
  const anterior = obtenerTokenSesion();
  memoria = null;
  activa = null;
  window.google?.accounts?.id?.disableAutoSelect?.();
  try {
    localStorage.removeItem(CLAVE_SESION);
    sessionStorage.removeItem(CLAVE_CUENTA);
    sessionStorage.removeItem(CLAVE_VALIDACION);
  } catch {
    // nada que limpiar
  }
  if (anterior) window.dispatchEvent(new Event(EVENTO_SESION));
}
