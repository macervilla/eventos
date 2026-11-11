import { Ventana } from "../components/Ventana";
import axios from "axios";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { errorMensaje, Invitado } from "./InvitadosPage";
import type { IScannerControls } from "@zxing/browser";

export function ControlIngresoPage() {
  const { slug } = useParams(); const navigate = useNavigate(); const base = `/invitados/${slug}`;
  const [correccion, setCorreccion] = useState<Invitado | null>(null);
  const [cantidadCorreccion, setCantidadCorreccion] = useState(1);
  const [motivoCorreccion, setMotivoCorreccion] = useState("");
  const [errorCorreccion, setErrorCorreccion] = useState<string | null>(null);
  const [corrigiendo, setCorrigiendo] = useState(false);
  const [permitido, setPermitido] = useState(false); const [puedeCorregir, setPuedeCorregir] = useState(false);
  const [token, setToken] = useState(""); const [invitado, setInvitado] = useState<Invitado | null>(null);
  const [cantidad, setCantidad] = useState(1); const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null); const [aviso, setAviso] = useState<string | null>(null);
  const [kpis, setKpis] = useState<Record<string, number>>({}); const [q, setQ] = useState(""); const [busqueda, setBusqueda] = useState<Invitado[]>([]);
  const [movimientos, setMovimientos] = useState<{ id: number; nombre: string; cantidad: number; operador: string; fecha: string }[]>([]);
  const [camara, setCamara] = useState(false); const video = useRef<HTMLVideoElement>(null);
  const controles = useRef<IScannerControls | null>(null); const camaraVersion = useRef(0);
  const operacion = useRef<{ idempotencia: string; cantidad: number } | null>(null);
  const parar = useCallback(() => { camaraVersion.current++; controles.current?.stop(); controles.current = null; setCamara(false); }, []);
  const actualizar = useCallback(async () => {
    try { const r = await api.get(base + "/estadisticas", { params: { control: true } }); setKpis(r.data); const m = await api.get(base + "/control/movimientos"); setMovimientos(m.data); }
    catch (err) { setError(errorMensaje(err)); }
  }, [base]);
  useEffect(() => {
    let activo = true;
    api.get(base + "/acceso").then(r => {
      if (!activo) return;
      if (!r.data.permisos.includes("control_ingreso") || !r.data.config.activo) { setError("No tenes acceso al control de ingreso o el modulo esta desactivado."); return; }
      setPermitido(true); setPuedeCorregir(r.data.permisos.includes("corregir_ingresos")); void actualizar();
    }).catch(err => {
      if (axios.isAxiosError(err) && err.response?.status === 401) navigate(`/ingresar?destino=${encodeURIComponent(`/e/${slug}/control-ingreso`)}`, { replace: true });
      else setError(errorMensaje(err));
    });
    return () => { activo = false; parar(); };
  }, [base, navigate, slug, actualizar, parar]);
  useEffect(() => {
    if (!permitido) return;
    const interval = window.setInterval(() => { if (!document.hidden) void actualizar(); }, 15000);
    return () => window.clearInterval(interval);
  }, [permitido, actualizar]);

  async function consultar(valor = token) {
    parar();
    setOcupado(true); setError(null); setAviso(null); setInvitado(null); operacion.current = null;
    try { const r = await api.post(base + "/control/consultar", { token: valor.trim() }); setInvitado(r.data); setCantidad(1); }
    catch (err) { setError(errorMensaje(err)); }
    finally { setOcupado(false); }
  }
  async function iniciarCamara() {
    if (!window.isSecureContext) { setError("La camara requiere HTTPS o localhost. Podes usar el codigo manual."); return; }
    setError(null); setCamara(true); const version = ++camaraVersion.current;
    try {
      const { BrowserQRCodeReader } = await import("@zxing/browser");
      const lector = new BrowserQRCodeReader(); let leido = false;
      const control = await lector.decodeFromVideoDevice(undefined, video.current!, (result, _err, ctrl) => {
        if (!result || leido || camaraVersion.current !== version) return;
        leido = true; ctrl.stop(); setCamara(false); const codigo = result.getText(); setToken(codigo); void consultar(codigo);
      });
      if (camaraVersion.current !== version || leido) control.stop(); else controles.current = control;
    } catch { if (camaraVersion.current === version) { setCamara(false); setError("No se pudo abrir la camara. Revisa el permiso del navegador o ingresa el codigo manualmente."); } }
  }
  async function registrar() {
    if (!invitado) return;
    setOcupado(true); setError(null); setAviso(null);
    if (!operacion.current) operacion.current = { idempotencia: crypto.randomUUID(), cantidad };
    try {
      const r = await api.post(base + "/control/ingreso", { token: token.trim(), ...operacion.current });
      setInvitado(r.data); operacion.current = null; setAviso("Ingreso registrado. El cupo restante fue actualizado."); await actualizar();
    } catch (err) {
      if (axios.isAxiosError(err) && err.response && err.response.status < 500) operacion.current = null;
      setError(errorMensaje(err));
    } finally { setOcupado(false); }
  }
  return <main className="invitados-page control-ingreso">
    <header className="invitados-header"><div><Link to={`/e/${slug}`}>Volver al evento</Link><h1>Control de ingreso</h1><p>Escanea, consulta el cupo y confirma cuantas personas ingresan.</p></div></header>
    {error && <p className="form-error" role="alert">{error}</p>}{aviso && <p className="success-inline" role="status">{aviso}</p>}
    {permitido && <>
      <section className="invitados-kpis">{["ingresados", "restantes", "parciales", "completos"].map(k => <article key={k}><span>{k}</span><strong>{kpis[k] || 0}</strong></article>)}</section>
      <section className="invitados-panel"><div className="invitados-acciones"><button className="action-button" disabled={ocupado || camara} onClick={() => void iniciarCamara()}>Escanear QR con camara</button>{camara && <button className="secondary-button" onClick={parar}>Detener camara</button>}</div>
        <video ref={video} hidden={!camara} muted playsInline className="control-video" />
        <form className="invitados-form" onSubmit={e => { e.preventDefault(); void consultar(); }}><label>Credencial QR (lectura manual)<textarea value={token} onChange={e => { setToken(e.target.value); setInvitado(null); operacion.current = null; }} placeholder="Pega el codigo leido del QR" autoComplete="off" /></label><button className="secondary-button" disabled={ocupado || !token}>Consultar credencial</button></form>
      </section>
      {invitado && <section className="invitados-panel"><h2>{invitado.nombre} {invitado.apellido}</h2><p>{invitado.grupo}</p>
        <div className="invitados-kpis"><article><span>Aprobados</span><strong>{invitado.cupo_aprobado}</strong></article><article><span>Ingresaron</span><strong>{invitado.ingresados}</strong></article><article><span>Restantes</span><strong>{invitado.restantes}</strong></article></div>
        {invitado.restantes > 0 ? <><label>Personas que ingresan ahora<input type="number" min={1} max={invitado.restantes} value={cantidad} disabled={ocupado || Boolean(operacion.current)} onChange={e => setCantidad(Number(e.target.value))} /></label><button className="action-button" disabled={ocupado || cantidad < 1 || cantidad > invitado.restantes || !Number.isInteger(cantidad)} onClick={() => void registrar()}>{ocupado ? "Registrando..." : operacion.current ? "Reintentar el mismo ingreso" : "Confirmar ingreso"}</button></> : <p className="success-inline">Ingreso completo. No hay cupos disponibles.</p>}
      </section>}
      <section className="invitados-panel"><h2>Busqueda de contingencia</h2><p>La busqueda permite consultar la invitacion. No registra ingresos ni reemplaza la validacion de una credencial aprobada.</p><form className="invitados-acciones" onSubmit={e => { e.preventDefault(); void api.get(base + "/control/buscar", { params: { q } }).then(r => setBusqueda(r.data.items)).catch(err => setError(errorMensaje(err))); }}><input value={q} onChange={e => setQ(e.target.value)} placeholder="Nombre o grupo" aria-label="Buscar invitado" /><button className="secondary-button">Buscar</button></form>
        {busqueda.map(i => <article key={i.id}><strong>{i.nombre} {i.apellido} · {i.grupo}</strong><p>{i.aprobacion}. Aprobados: {i.cupo_aprobado}. Ingresaron: {i.ingresados}. Restan: {i.restantes}.</p>
          {puedeCorregir && i.ingresados > 0 && <button className="secondary-button" onClick={() => { setCorreccion(i); setCantidadCorreccion(1); setMotivoCorreccion(""); setErrorCorreccion(null); }}>Corregir ingresos</button>}
        </article>)}
      </section>
      <section className="invitados-panel"><h2>Ultimos movimientos</h2><p>Actualizacion cada 15 segundos mientras esta pantalla esta visible.</p>{movimientos.map(m => <p key={m.id}>{new Date(m.fecha).toLocaleString("es-AR")} · {m.nombre} · {m.cantidad > 0 ? "+" : ""}{m.cantidad} · {m.operador}</p>)}</section>
    </>}
    {correccion && <Ventana titulo={`Corregir ingresos de ${correccion.nombre}`} alCerrar={() => { if (!corrigiendo) setCorreccion(null); }}>
      <form className="invitados-form" onSubmit={async e => {
        e.preventDefault();
        if (corrigiendo || !Number.isInteger(cantidadCorreccion) || cantidadCorreccion < 1 || cantidadCorreccion > correccion.ingresados || !motivoCorreccion.trim()) return;
        setCorrigiendo(true); setErrorCorreccion(null);
        try {
          await api.post(`${base}/control/${correccion.id}/corregir`, { cantidad: cantidadCorreccion, motivo: motivoCorreccion.trim(), idempotencia: crypto.randomUUID() });
          setCorreccion(null); setAviso("Correccion auditada."); await actualizar(); setBusqueda([]);
        } catch (err) { setErrorCorreccion(errorMensaje(err)); }
        finally { setCorrigiendo(false); }
      }}>
        <p>Se descontaran ingresos registrados. El motivo quedara guardado en la auditoria.</p>
        <label>Cantidad a descontar<input autoFocus required type="number" min={1} max={correccion.ingresados} step={1} value={cantidadCorreccion} onChange={e => setCantidadCorreccion(Number(e.target.value))} /></label>
        <label>Motivo de la correccion<textarea required value={motivoCorreccion} onChange={e => setMotivoCorreccion(e.target.value)} /></label>
        {errorCorreccion && <p role="alert" className="form-error">{errorCorreccion}</p>}
        <div className="form-actions"><button className="secondary-button" type="button" disabled={corrigiendo} onClick={() => setCorreccion(null)}>Cancelar</button><button className="action-button" disabled={corrigiendo || !motivoCorreccion.trim()}>Confirmar correccion</button></div>
      </form>
    </Ventana>}
  </main>;
}
