import axios from "axios";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { guardarTokenSesion, obtenerValidacionEmail } from "../api/sesion";
import { GoogleSignIn } from "./GoogleSignIn";
import { Ventana } from "./Ventana";

export function IngresoEvento({ slug, alIngresar, alCerrar }: { slug: string; alIngresar: () => void; alCerrar: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  async function ingresar(credential: string) {
    setError(null); setCargando(true);
    try {
      const validacionEmail = obtenerValidacionEmail();
      const { data } = await api.post<{ token: string | null }>("/acceso/google", { credential }, validacionEmail ? { headers: { Authorization: `Bearer ${validacionEmail}` } } : undefined);
      if (!data.token) throw new Error("Esta cuenta esta inactiva. Contacta al administrador del proyecto.");
      guardarTokenSesion(data.token);
      alIngresar();
    } catch (err) {
      const detalle = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detalle === "string" ? detalle : err instanceof Error ? err.message : "No se pudo ingresar con Google. Podes seguir viendo la invitacion.");
    } finally { setCargando(false); }
  }
  return <Ventana titulo="Ingresar al evento" alCerrar={alCerrar}>
    <p>Inicia sesion para consultar tu acceso a este evento. La invitacion sigue disponible si no podes ingresar.</p>
    <GoogleSignIn onCredential={credential => { if (!cargando) void ingresar(credential); }} />
    {cargando && <p role="status">Validando cuenta...</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <p><Link to={`/ingresar?destino=${encodeURIComponent(`/e/${slug}`)}`}>Ver mis sitios o vincular mi cuenta</Link></p>
    <button className="secondary-button" type="button" onClick={alCerrar}>Volver a la invitacion</button>
  </Ventana>;
}
