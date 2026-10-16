import { Building2, CalendarDays, Mail, UserCheck } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { guardarTokenSesion } from "../api/sesion";

type AccessOption = {
  tipo: "proveedor" | "evento";
  id: number;
  nombre: string;
  slug: string;
  path: string;
};

type AccessResponse = {
  email: string;
  opciones: AccessOption[];
  token: string | null;
};

type GoogleConfigResponse = {
  client_id: string | null;
};

type GoogleTokenResponse = {
  access_token?: string;
};

type GoogleTokenClient = {
  requestAccessToken: () => void;
};

declare global {
  interface Window {
    google?: {
      accounts?: {
        oauth2?: {
          initTokenClient: (options: {
            client_id: string;
            scope: string;
            callback: (response: GoogleTokenResponse) => void;
          }) => GoogleTokenClient;
        };
      };
    };
  }
}

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Solo se aceptan rutas internas como destino, para no redirigir a otros sitios.
function destinoSeguro(destino: string | null) {
  return destino && destino.startsWith("/") && !destino.startsWith("//") ? destino : null;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const enlaceProcesado = useRef(false);
  const [email, setEmail] = useState("");
  const [aviso, setAviso] = useState<string | null>(null);
  const [options, setOptions] = useState<AccessOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const resolveAccess = (response: AccessResponse, destino: string | null = null) => {
    if (response.opciones.length === 0 || !response.token) {
      setError("No encontramos eventos ni proveedores activos para ese email.");
      return;
    }
    guardarTokenSesion(response.token);
    if (destino) {
      navigate(destino, { replace: true });
      return;
    }
    if (response.opciones.length === 1) {
      navigate(response.opciones[0].path);
      return;
    }
    setOptions(response.opciones);
  };

  useEffect(() => {
    const tokenEnlace = searchParams.get("enlace");
    // useRef evita canjear el enlace dos veces (React StrictMode ejecuta efectos doble en dev)
    if (!tokenEnlace || enlaceProcesado.current) return;
    enlaceProcesado.current = true;
    setLoading(true);
    api
      .post<AccessResponse>("/acceso/enlace", { token: tokenEnlace })
      .then((response) => {
        setEmail(response.data.email);
        resolveAccess(response.data, destinoSeguro(searchParams.get("destino")));
      })
      .catch(() => setError("El enlace vencio o no es valido. Pedi uno nuevo."))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const validateAccess = (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    setError(null);
    setAviso(null);
    setOptions([]);

    const selectedEmail = email.trim();
    if (!emailPattern.test(selectedEmail)) {
      setError("Selecciona o carga un email valido.");
      return;
    }

    setLoading(true);
    api
      .post("/acceso/solicitar-enlace", { email: selectedEmail })
      .then(() =>
        setAviso(`Si ${selectedEmail} esta registrado, te enviamos un enlace para ingresar.`)
      )
      .catch(() => setError("No se pudo enviar el enlace. Intenta nuevamente."))
      .finally(() => setLoading(false));
  };

  const startGoogleSignIn = () => {
    setError(null);
    setAviso(null);
    setOptions([]);

    if (!window.google?.accounts?.oauth2) {
      setError("El ingreso con Google no esta configurado todavia.");
      return;
    }

    setGoogleLoading(true);
    api
      .get<GoogleConfigResponse>("/acceso/google-config")
      .then((configResponse) => {
        const googleClientId = configResponse.data.client_id;
        if (!googleClientId) {
          setGoogleLoading(false);
          setError("Falta configurar GOOGLE_CLIENT_ID en el .env de idiomas.");
          return;
        }

        const tokenClient = window.google!.accounts!.oauth2!.initTokenClient({
          client_id: googleClientId,
          scope: "email profile",
          callback: (googleResponse) => {
            if (!googleResponse.access_token) {
              setGoogleLoading(false);
              setError("No se pudo obtener la cuenta de Google seleccionada.");
              return;
            }

            api
              .post<AccessResponse>("/acceso/google", {
                access_token: googleResponse.access_token
              })
              .then((response) => {
                setEmail(response.data.email);
                resolveAccess(response.data);
              })
              .catch(() => setError("No se pudo validar la cuenta de Google seleccionada."))
              .finally(() => setGoogleLoading(false));
          }
        });
        tokenClient.requestAccessToken();
      })
      .catch(() => {
        setGoogleLoading(false);
        setError("No se pudo leer la configuracion de Google.");
      });
  };

  return (
    <main className="providers-page">
      <section className="login-panel">
        <div>
          <p className="eyebrow">Ingresar</p>
          <h1>Elegir cuenta</h1>
          <p>
            Ingresa con Google para seleccionar una cuenta del dispositivo, o te enviamos un
            enlace de acceso a tu email. Despues te llevamos al apartado que corresponda.
          </p>
        </div>

        <button
          className="google-login-button"
          type="button"
          onClick={startGoogleSignIn}
          disabled={googleLoading}
        >
          <span aria-hidden="true">G</span>
          {googleLoading ? "Abriendo Google..." : "Ingresar con Google"}
        </button>

        <form className="login-form" onSubmit={validateAccess}>
          <label>
            Email manual
            <input
              autoComplete="email"
              inputMode="email"
              name="email"
              placeholder="tu@email.com"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          {error && <p className="form-error">{error}</p>}
          {aviso && <p className="success-inline">{aviso}</p>}
          <div className="form-actions">
            <button className="secondary-button" type="button" onClick={() => setEmail("")}>
              <Mail size={18} aria-hidden="true" />
              Limpiar
            </button>
            <button className="action-button" type="submit" disabled={loading}>
              <UserCheck size={18} aria-hidden="true" />
              {loading ? "Enviando..." : "Enviarme enlace"}
            </button>
          </div>
        </form>

        {options.length > 1 && (
          <section className="access-options" aria-label="Opciones de ingreso">
            <h2>Elegir apartado</h2>
            <div>
              {options.map((option) => (
                <button
                  key={`${option.tipo}-${option.id}`}
                  type="button"
                  onClick={() => navigate(option.path)}
                >
                  {option.tipo === "proveedor" ? (
                    <Building2 size={20} aria-hidden="true" />
                  ) : (
                    <CalendarDays size={20} aria-hidden="true" />
                  )}
                  <span>
                    <strong>{option.nombre}</strong>
                    <small>{option.tipo === "proveedor" ? "Proveedor" : "Evento"}</small>
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}
