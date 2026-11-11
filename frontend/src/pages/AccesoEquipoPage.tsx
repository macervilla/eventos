import axios from "axios";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { guardarTokenSesion, obtenerTokenSesion, obtenerValidacionEmail, seleccionarCuentaSesion } from "../api/sesion";
import { GoogleSignIn } from "../components/GoogleSignIn";

type Cuenta = { token?: string | null; path: string };
type Acceso = { token?: string | null; opciones: Cuenta[] };
type Permisos = { usuario: { id: number } | null; puede_editar: boolean; permisos_invitados: string[] };

export function AccesoEquipoPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const destino = `/e/${slug}`;
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  function herramientas(resultado: { rolEdicion: boolean; permisos: string[] }) {
    if (resultado.rolEdicion || resultado.permisos.some(p => ["ver_invitados", "editar_invitados", "distribuir", "roles", "configurar_invitados", "estadisticas"].includes(p))) return `${destino}/invitados`;
    if (resultado.permisos.some(p => ["control_ingreso", "ver_asistencia"].includes(p))) return `${destino}/control-ingreso`;
    return destino;
  }

  async function comprobar(token: string, opciones: Cuenta[], signal?: AbortSignal) {
    const cuenta = opciones.find(o => o.path === destino);
    const tokenCuenta = cuenta?.token || token;
    const { data } = await api.get<Permisos>(`/eventos/${slug}/permisos`, {
      headers: { Authorization: `Bearer ${tokenCuenta}` }, signal
    });
    if (!data.usuario || (!data.puede_editar && !data.permisos_invitados.length)) {
      throw new Error("Esta cuenta de Google no tiene un rol asignado en este evento. Selecciona el email que el emisor registro para vos.");
    }
    return { tokenCuenta, rolEdicion: data.puede_editar, permisos: data.permisos_invitados };
  }

  useEffect(() => {
    const token = obtenerTokenSesion();
    if (!token) return;
    const controller = new AbortController();
    setCargando(true);
    api.get<Acceso>("/acceso/yo", { signal: controller.signal })
      .then(r => comprobar(token, r.data.opciones, controller.signal))
      .then(resultado => {
        if (controller.signal.aborted) return;
        if (resultado.tokenCuenta !== token) seleccionarCuentaSesion(resultado.tokenCuenta);
        navigate(herramientas(resultado), { replace: true });
      })
      .catch(err => { if (!controller.signal.aborted) setError(axios.isAxiosError(err) ? "Selecciona en Google el email registrado por el emisor para este evento." : err.message); })
      .finally(() => { if (!controller.signal.aborted) setCargando(false); });
    return () => controller.abort();
    // El destino depende del evento; una sesion nueva se procesa en ingresar().
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  async function ingresar(credential: string) {
    if (cargando) return;
    setCargando(true); setError(null);
    try {
      const pruebaEmail = obtenerValidacionEmail();
      const { data } = await api.post<Acceso>("/acceso/google", { credential }, pruebaEmail ? { headers: { Authorization: `Bearer ${pruebaEmail}` } } : undefined);
      if (!data.token) throw new Error("No se pudo ingresar con esta cuenta. Selecciona el email registrado por el emisor.");
      const resultado = await comprobar(data.token, data.opciones);
      guardarTokenSesion(data.token);
      if (resultado.tokenCuenta !== data.token) seleccionarCuentaSesion(resultado.tokenCuenta);
      navigate(herramientas(resultado), { replace: true });
    } catch (err) {
      const detalle = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detalle === "string" ? detalle : err instanceof Error ? err.message : "No se pudo validar la cuenta de Google.");
    } finally { setCargando(false); }
  }

  return <main className="providers-page"><section className="login-panel">
    <div><p className="eyebrow">Acceso al equipo del evento</p><h1>Ingresar como Agasajado o Administrador</h1>
      <p>Selecciona en Google el email que el emisor registro en el sistema para asignarte este rol.</p>
      <p>Cuando Google valide tu cuenta, ingresaras directamente al evento con tus permisos asignados.</p>
    </div>
    <GoogleSignIn onCredential={credential => void ingresar(credential)} />
    {cargando && <p role="status">Validando tu acceso al evento...</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <Link to={destino}>Ver evento</Link>
  </section></main>;
}
