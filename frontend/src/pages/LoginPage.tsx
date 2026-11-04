import axios from "axios";
import { Building2, CalendarDays, Mail, ShieldCheck, UserCheck } from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { guardarTokenSesion, seleccionarCuentaSesion, obtenerTokenSesion } from "../api/sesion";
import { GoogleSignIn } from "../components/GoogleSignIn";

type AccessOption = {
  token?: string | null;
  tipo: "proveedor" | "evento" | "administracion";
  id: number;
  nombre: string;
  slug: string;
  path: string;
};

type AccessResponse = {
  google_vinculado?: boolean;
  email_validado?: boolean;
  email: string;
  opciones: AccessOption[];
  token: string | null;
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Solo se aceptan rutas internas como destino, para no redirigir a otros sitios.
function destinoSeguro(destino: string | null) {
  return destino && /^\/(?![\\/])/.test(destino) && !/[\\\r\n]/.test(destino) ? destino : null;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const enlaceProcesado = useRef(false);
  const [email, setEmail] = useState("");
  const [aviso, setAviso] = useState<string | null>(null);
  const [options, setOptions] = useState<AccessOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const resolveAccess = (response: AccessResponse, destino: string | null = null) => {
    if (!response.token) {
      setError("No encontramos eventos ni proveedores activos para ese email.");
      return;
    }
    guardarTokenSesion(response.token);
    if (destino) {
      const opcion = response.opciones.find(o => destino === o.path || destino.startsWith(o.path + "/"));
      if (opcion?.token) seleccionarCuentaSesion(opcion.token);
      navigate(destino, { replace: true });
      return;
    }
    if (response.opciones.length === 0) {
      navigate("/", { replace: true });
      return;
    }
    if (response.opciones.length === 1) {
      if (response.opciones[0].token) seleccionarCuentaSesion(response.opciones[0].token);
      navigate(response.opciones[0].path);
      return;
    }
    setOptions(response.opciones);
  };

  useEffect(() => {
    const tokenEnlace = searchParams.get("enlace");
    // useRef evita canjear el enlace dos veces (React StrictMode ejecuta efectos doble en dev)
    if (!tokenEnlace) {
      if (enlaceProcesado.current) return;
      if (obtenerTokenSesion()) api.get<AccessResponse>("/acceso/yo").then(r => { setEmail(r.data.email); setOptions(r.data.opciones); }).catch(() => undefined);
      return;
    }
    if (enlaceProcesado.current) return;
    enlaceProcesado.current = true;
    const limpia = new URLSearchParams(searchParams); limpia.delete("enlace");
    setSearchParams(limpia, { replace: true });
    setLoading(true);
    api
      .post<AccessResponse>("/acceso/enlace", { token: tokenEnlace })
      .then((response) => {
        setEmail(response.data.email);
        if (response.data.token && response.data.google_vinculado === false) {
          guardarTokenSesion(response.data.token);
          setOptions(response.data.opciones);
          setAviso("Email validado. Selecciona tu cuenta de Google para vincularla una vez y usarla en tus proximos ingresos.");
          return;
        }
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
      .post("/acceso/solicitar-enlace", { email: selectedEmail, destino: destinoSeguro(searchParams.get("destino")) })
      .then(() =>
        setAviso(`Si ${selectedEmail} esta registrado, te enviamos un enlace para ingresar.`)
      )
      .catch(() => setError("No se pudo enviar el enlace. Intenta nuevamente."))
      .finally(() => setLoading(false));
  };

  const validarGoogle = (credential: string) => {
    setError(null);
    setAviso(null);
    setOptions([]);
    setGoogleLoading(true);
    api.post<AccessResponse>("/acceso/google", { credential })
      .then(response => {
        setEmail(response.data.email);
        resolveAccess(response.data, destinoSeguro(searchParams.get("destino")));
      })
      .catch(err => {
        const detalle = axios.isAxiosError(err) ? err.response?.data?.detail : null;
        setError(typeof detalle === "string" ? detalle : "No se pudo validar la cuenta de Google. Intenta nuevamente.");
      })
      .finally(() => setGoogleLoading(false));
  };

  return (
    <main className="providers-page">
      <section className="login-panel">
        <div>
          <p className="eyebrow">Ingresar</p>
          <h1>Ingresar a mis sitios</h1>
          <p>
            Selecciona tu cuenta de Google para acceder a tus eventos y proveedores.
            La validacion inicial del email se realiza una sola vez; no necesitas pedir otro correo para ingresar.
          </p>
        </div>

        <GoogleSignIn onCredential={validarGoogle} />
        {googleLoading && <p role="status">Validando cuenta de Google...</p>}
        {aviso && <p className="success-inline" role="status">{aviso}</p>}
        {error && <p className="form-error" role="alert">{error}</p>}

        <details className="acceso-recuperacion"><summary>Validacion inicial o recuperacion de acceso</summary>
        <form className="login-form" onSubmit={validateAccess}>
          <label>
            Email de la cuenta
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
          <div className="form-actions">
            <button className="secondary-button" type="button" onClick={() => setEmail("")}>
              <Mail size={18} aria-hidden="true" />
              Limpiar
            </button>
            <button className="action-button" type="submit" disabled={loading}>
              <UserCheck size={18} aria-hidden="true" />
              {loading ? "Enviando..." : "Recuperar acceso"}
            </button>
          </div>
        </form>
        </details>

        {options.length > 0 && (
          <section className="access-options" aria-label="Opciones de ingreso">
            <h2>Elegir apartado</h2>
            <div>
              {options.map((option) => (
                <button
                  key={`${option.tipo}-${option.id}`}
                  type="button"
                  onClick={() => { if (option.token) seleccionarCuentaSesion(option.token); navigate(option.path); }}
                >
                  {option.tipo === "administracion" ? <ShieldCheck size={20} aria-hidden="true" /> : option.tipo === "proveedor" ? (
                    <Building2 size={20} aria-hidden="true" />
                  ) : (
                    <CalendarDays size={20} aria-hidden="true" />
                  )}
                  <span>
                    <strong>{option.nombre}</strong>
                    <small>{option.tipo === "administracion" ? "Superadministrador" : option.tipo === "proveedor" ? "Proveedor" : "Evento"}</small>
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
