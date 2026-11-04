import axios from "axios";
import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";

type GoogleIdentity = {
  disableAutoSelect?: () => void;
  initialize: (options: {
    client_id: string;
    ux_mode: "popup";
    auto_select: boolean;
    callback: (response: { credential?: string }) => void;
  }) => void;
  renderButton: (element: HTMLElement, options: {
    type: "standard"; theme: "outline"; size: "large"; text: "signin_with"; locale: string;
  }) => void;
};

declare global {
  interface Window { google?: { accounts?: { id?: GoogleIdentity } } }
}

let cargaGoogle: Promise<void> | null = null;
function cargarGoogle() {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (cargaGoogle) return cargaGoogle;
  cargaGoogle = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    const timeout = window.setTimeout(() => {
      script.remove(); cargaGoogle = null;
      reject(new Error("Google tardo demasiado en responder. Recarga la pagina para reintentar."));
    }, 15000);
    script.onload = () => { window.clearTimeout(timeout); resolve(); };
    script.onerror = () => {
      window.clearTimeout(timeout); script.remove(); cargaGoogle = null;
      reject(new Error("No se pudo cargar Google. Revisa tu conexion o solicita un enlace por email."));
    };
    document.head.appendChild(script);
  });
  return cargaGoogle;
}

// El ID publico se obtiene del backend en cada montaje, tambien en builds de produccion.
// No se usa VITE_GOOGLE_CLIENT_ID ni se incluye un Client Secret en el navegador.
export function GoogleSignIn({ onCredential }: { onCredential: (credential: string) => void }) {
  const contenedor = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  callback.current = onCredential;
  const [error, setError] = useState<string | null>(null);
  const [listo, setListo] = useState(false);

  useEffect(() => {
    let cancelado = false;
    async function iniciar() {
      try {
        const { data } = await api.get<{ client_id: string | null }>("/acceso/google-config");
        if (!data.client_id) throw new Error("Falta configurar el ingreso con Google en Eventos. Podes usar el enlace por email.");
        await cargarGoogle();
        if (cancelado || !contenedor.current) return;
        const identity = window.google?.accounts?.id;
        if (!identity) throw new Error("Google no esta disponible. Intenta recargar la pagina.");
        identity.initialize({
          client_id: data.client_id, ux_mode: "popup", auto_select: false,
          callback: response => {
            if (cancelado) return;
            if (response.credential) callback.current(response.credential);
            else setError("Google no devolvio una credencial valida. Intenta nuevamente.");
          }
        });
        contenedor.current.replaceChildren();
        identity.renderButton(contenedor.current, {
          type: "standard", theme: "outline", size: "large", text: "signin_with", locale: "es"
        });
        setListo(true);
      } catch (err) {
        if (!cancelado) setError(axios.isAxiosError(err)
          ? "No se pudo consultar la configuracion de Google. Intenta recargar la pagina."
          : err instanceof Error ? err.message : "No se pudo iniciar Google.");
      }
    }
    void iniciar();
    return () => { cancelado = true; };
  }, []);

  return <div>
    {!listo && !error && <p role="status">Cargando acceso con Google...</p>}
    <div ref={contenedor} />
    {error && <p className="form-error" role="alert">{error}</p>}
  </div>;
}
