import axios from "axios";
import { Mail } from "lucide-react";
import { SolicitarInvitacion } from "./SolicitarInvitacion";
import { FormEvent, useEffect, useState } from "react";
import { useHref } from "react-router-dom";
import { api } from "../api/client";
import { abrirPestanaConSesion, EVENTO_SESION } from "../api/sesion";
import { Ventana } from "./Ventana";
import { FotosInvitado } from "./FotosInvitado";
import { PublicadorEvento } from "./VideoEvento";

type Persona = { apellido: string; nombre: string; tipo: "ADULTO" | "MENOR" };
type Invitacion = { id: number; nombre: string; apellido: string; token: string };
type Portal = {
  validado: boolean; sesion?: string; validacion: string; sin_contacto?: boolean;
  nombre?: string; apellido?: string; cantidad_permitida?: number; solicitados?: number;
  acompanantes?: Persona[]; puede_modificar?: boolean; qr?: string | null;
  rsvp?: string; aprobacion?: string; cupo_aprobado?: number; ingresados?: number;
  correo_qr?: string; email_asociado?: string | null; cuenta_diferente?: boolean;
  puede_confirmar?: boolean; no_disponible?: boolean;
  sin_invitacion?: boolean; requiere_identidad?: boolean;
};
const vacia = (): Persona => ({ apellido: "", nombre: "", tipo: "ADULTO" });
function errorSolicitud(err: unknown) {
  if (axios.isAxiosError(err)) {
    const detalle = err.response?.data?.detail;
    if (detalle === "Not Found") return "La confirmacion todavia no esta disponible en el servidor. Contacta al organizador.";
    if (typeof detalle === "string") return detalle;
    if (Array.isArray(detalle)) return "Completa apellido y nombre de todas las personas antes de confirmar.";
  }
  return "No se pudo completar la solicitud. Intenta nuevamente.";
}

export function ConfirmacionInvitado({ slug, tokenPersonal, conSesion, alIngresar, ocultarSinInvitacion = false }: {
  slug: string; tokenPersonal?: string; conSesion: boolean; alIngresar: () => void;
  ocultarSinInvitacion?: boolean;
}) {
  const [buscandoInvitacion, setBuscandoInvitacion] = useState(true);
  const [invitaciones, setInvitaciones] = useState<Invitacion[]>([]);
  const [token, setToken] = useState(tokenPersonal || "");
  const [portal, setPortal] = useState<Portal | null>(null);
  const [abierta, setAbierta] = useState(false);
  const [fotosAbiertas, setFotosAbiertas] = useState(false);
  const [ocupadoFotos, setOcupadoFotos] = useState(false);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [qrImagen, setQrImagen] = useState<string | null>(null);
  const [identidad, setIdentidad] = useState(0);
  useEffect(() => {
    const limpiar = () => {
      setPortal(null); setQrImagen(null); setPersonas([]); setAbierta(false); setFotosAbiertas(false);
      setIdentidad(actual => actual + 1);
    };
    window.addEventListener(EVENTO_SESION, limpiar);
    window.addEventListener("storage", limpiar);
    return () => { window.removeEventListener(EVENTO_SESION, limpiar); window.removeEventListener("storage", limpiar); };
  }, []);
  const base = `/invitados/${slug}`;
  const enlaceAlbum = useHref(`/${slug}/album`);
  const clave = `eventos_invitado:${slug}:${token}`;
  function datosAcceso() {
    let sesion: string | null = null;
    try { sesion = sessionStorage.getItem(clave); } catch { /* Puede verificarse nuevamente. */ }
    return { token, sesion: portal?.sesion || sesion || undefined };
  }
  function recibir(datos: Portal) {
    setPortal(datos);
    try {
      if (datos.validado && datos.sesion) sessionStorage.setItem(clave, datos.sesion);
      else sessionStorage.removeItem(clave);
      if (datos.validado) sessionStorage.setItem(`eventos_ultima_invitacion:${slug}`, token);
    } catch { /* La invitacion sigue disponible en esta pagina. */ }
    if (datos.validado) {
      const anteriores = datos.acompanantes || [];
      const cantidad = Math.max(1, datos.solicitados || datos.cantidad_permitida || 1);
      setPersonas([{ apellido: datos.apellido || "", nombre: datos.nombre || "", tipo: "ADULTO" },
        ...Array.from({ length: cantidad - 1 }, (_, n) => anteriores[n] || vacia())]);
    }
  }

  useEffect(() => {
    setToken(tokenPersonal || ""); setPortal(null); setError(null); setInvitaciones([]);
    setBuscandoInvitacion(false);
    if (tokenPersonal) return;
    if (!conSesion) {
      try { setToken(sessionStorage.getItem(`eventos_ultima_invitacion:${slug}`) || ""); } catch { /* Puede abrir su enlace personal. */ }
      return;
    }
    setBuscandoInvitacion(true);
    const abortar = new AbortController();
    api.post<{ invitaciones: Invitacion[] }>(`${base}/mis-invitaciones`, {}, { signal: abortar.signal })
      .then(r => { if (!abortar.signal.aborted) { setInvitaciones(r.data.invitaciones); setToken(r.data.invitaciones[0]?.token || ""); } })
      .catch(err => { if (!abortar.signal.aborted) setError(errorSolicitud(err)); })
      .finally(() => { if (!abortar.signal.aborted) setBuscandoInvitacion(false); });
    return () => abortar.abort();
  }, [base, tokenPersonal, conSesion, identidad]);

  useEffect(() => {
    if (!token) return;
    const abortar = new AbortController();
    setPortal(null); setError(null); setAviso(null); setQrImagen(null);
    let sesion: string | undefined;
    try { sesion = sessionStorage.getItem(clave) || undefined; } catch { /* Sin persistencia. */ }
    api.post<Portal>(`${base}/portal`, { token, sesion }, { signal: abortar.signal })
      .then(r => { if (!abortar.signal.aborted) recibir(r.data); }).catch(err => { if (!abortar.signal.aborted) setError(errorSolicitud(err)); });
    return () => abortar.abort();
    // La consulta se renueva al cambiar invitacion o identidad, no al actualizar sus datos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, token, clave, conSesion, identidad]);

  useEffect(() => {
    if (!portal?.validado || !portal.qr || !token) { setQrImagen(null); return; }
    const abortar = new AbortController();
    let imagen: string | null = null;
    api.post(`${base}/portal/qr.png`, datosAcceso(), { responseType: "blob", signal: abortar.signal })
      .then(r => { if (!abortar.signal.aborted) { imagen = URL.createObjectURL(r.data); setQrImagen(imagen); } })
      .catch(err => { if (!abortar.signal.aborted) setError(errorSolicitud(err)); });
    return () => { abortar.abort(); if (imagen) URL.revokeObjectURL(imagen); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, token, portal?.validado, portal?.qr, portal?.sesion, identidad]);

  async function confirmar(event: FormEvent) {
    event.preventDefault(); if (ocupado || ocupadoFotos) return;
    if (personas.some(p => !p.nombre.trim() || !p.apellido.trim())) {
      setError("Completa apellido y nombre de todas las personas antes de confirmar."); return;
    }
    setOcupado(true); setError(null); setAviso(null);
    try {
      const { data } = await api.post<Portal>(`${base}/portal/confirmar`, {
        ...datosAcceso(), personas: personas.map(p => ({ ...p, nombre: p.nombre.trim(), apellido: p.apellido.trim() })),
      });
      recibir(data); setAbierta(false); setAviso("Asistencia confirmada. Tu QR permanece disponible al volver a ingresar.");
    } catch (err) { setError(errorSolicitud(err)); }
    finally { setOcupado(false); }
  }
  function editar(indice: number, datos: Partial<Persona>) {
    setPersonas(actuales => actuales.map((p, n) => n === indice ? { ...p, ...datos } : p));
  }
  const mensajes = <>{error && <p className="form-error" role="alert">{error}</p>}{aviso && <p className="success-inline" role="status">{aviso}</p>}</>;
  function ingresarConOtraCuenta() {
    window.google?.accounts?.id?.disableAutoSelect?.();
    setAbierta(false); setQrImagen(null);
    alIngresar();
  }
  if (!token && !tokenPersonal) {
    if (ocultarSinInvitacion && !error) return null;
    return <section className="confirmacion-invitado" aria-label="Confirmar asistencia">
      {buscandoInvitacion ? <p role="status">Buscando tu invitación...</p> : conSesion && !error ? <>
        <Mail size={22} aria-hidden="true" className="invitacion-icono" />
        <h2>No encontramos una invitación para tu cuenta</h2>
        <p>La cuenta con la que ingresaste no figura entre los invitados a este evento.</p>
        <SolicitarInvitacion slug={slug} />
        <button className="secondary-button" onClick={ingresarConOtraCuenta}>Cambiar de cuenta</button>
      </> : <>
        <h2>Verificá si tenés una invitación</h2>
        {error ? mensajes : <p>Ingresá con la cuenta registrada por el organizador o abrí el enlace personal que recibiste.</p>}
        <button className="action-button" onClick={alIngresar}>Ingresar para verificar mi invitación</button>
      </>}
    </section>;
  }
  if (!portal) return <section className="confirmacion-invitado" aria-label="Mi invitacion">
    {error ? mensajes : <p role="status">Verificando tu invitación...</p>}
  </section>;
  if (portal.no_disponible) return <section className="confirmacion-invitado" aria-label="Mi invitacion">
    <Mail size={22} aria-hidden="true" className="invitacion-icono" />
    <h2>Tu invitación no está habilitada para confirmar</h2>
    <p>Contactá al organizador si necesitás revisar el estado de tu invitación.</p>
  </section>;
  if (portal.sin_invitacion || portal.cuenta_diferente) return <section className="confirmacion-invitado" aria-label="Mi invitacion" role="alert">
    <Mail size={22} aria-hidden="true" className="invitacion-icono" />
    <h2>No estás invitado con esta cuenta</h2>
    <p>Esta invitación no corresponde a la cuenta con la que ingresaste. Contactá al agasajado para solicitar tu invitación.</p>
    <button className="action-button" onClick={ingresarConOtraCuenta}>Cambiar de cuenta</button>
  </section>;
  return <section className="confirmacion-invitado" id="mi-confirmacion" aria-label="Mi invitacion">
    <h2>{portal.qr ? "Tu QR de ingreso" : portal.validado ? "Confirma tu asistencia" : "Elegí tu cuenta de Google"}</h2>
    {invitaciones.length > 1 && <label>Mi invitacion<select value={token} disabled={ocupado} onChange={e => setToken(e.target.value)}>
      {invitaciones.map(i => <option key={i.id} value={i.token}>{i.apellido} {i.nombre}</option>)}
    </select></label>}
    {portal.validado && portal.qr ? <>
      <p>{portal.apellido} {portal.nombre} · {portal.cupo_aprobado} {portal.cupo_aprobado === 1 ? "persona" : "personas"}</p>
      {qrImagen ? <><img className="invitado-qr" src={qrImagen} alt="QR de ingreso de mi invitacion" /><a className="secondary-button" href={qrImagen} download="mi-qr.png">Descargar QR</a></> : <p role="status">Cargando QR...</p>}
      {portal.puede_confirmar && <button className="secondary-button" onClick={() => { setError(null); setAbierta(true); }}>Modificar datos</button>}
    </> : portal.validado ? (portal.puede_confirmar ? <button className="action-button" onClick={() => { setError(null); setAbierta(true); }}>Confirmar asistencia</button> : <p>Tu respuesta está registrada. Contactá al organizador para realizar cambios.</p>) : <>
      <p>Elegí la cuenta de Google autorizada por el organizador o agasajado para ver tu invitación y confirmar asistencia.</p>
      <p>Si tu cuenta no está invitada, contactá al agasajado.</p>
      <button className="action-button" onClick={alIngresar}>Ingresar con Google</button>
    </>}
    {portal?.validado && <button className="secondary-button" onClick={() => setFotosAbiertas(true)}>Mis fotos (hasta 4)</button>}
    {portal?.validado && <><button className="secondary-button" onClick={() => {
      if (!abrirPestanaConSesion(enlaceAlbum, { slug, ...datosAcceso() })) setError("Permiti abrir una nueva pestana para ver el album.");
    }}>Álbum del evento</button><PublicadorEvento slug={slug} credenciales={datosAcceso()} /></>}
    {!abierta && mensajes}
    {fotosAbiertas && portal?.validado && <Ventana titulo="Mis fotos para el evento" alCerrar={() => { if (!ocupadoFotos) setFotosAbiertas(false); }}>
      <FotosInvitado key={token} slug={slug} credenciales={datosAcceso()} alOcupar={setOcupadoFotos} />
      <button className="secondary-button" type="button" disabled={ocupadoFotos} onClick={() => setFotosAbiertas(false)}>Cerrar fotos</button>
    </Ventana>}
    {abierta && <Ventana titulo="Confirmar asistencia" alCerrar={() => { if (!ocupado && !ocupadoFotos) setAbierta(false); }}>
      {!portal ? <>{mensajes}<p role="status">Cargando tu invitacion...</p></> : !portal.validado ? <>
        <p>Verifica tu acceso para revisar los datos de tu invitacion.</p>
        <p>Si esta invitacion no es para vos, solicita una invitacion propia al organizador.</p>
        <button className="action-button" type="button" onClick={alIngresar}>Ingresar con Google</button>
      </> : <form className="confirmacion-personas" onSubmit={confirmar}>
        <p>Revisa tus datos. Completa apellido y nombre de cada asistente. El cupo incluye al titular.</p>
        <label>Cantidad de personas<input type="number" min={Math.max(1, portal.ingresados || 0)} max={portal.cantidad_permitida} value={personas.length} disabled={ocupado || !portal.puede_modificar} onChange={e => {
          const cantidad = Math.min(portal.cantidad_permitida || 1, Math.max(1, portal.ingresados || 0, Number(e.target.value) || 1));
          setPersonas(actuales => Array.from({ length: cantidad }, (_, n) => actuales[n] || vacia()));
        }} /></label>
        <p>Cupo disponible: {portal.cantidad_permitida}. Si asisten menos personas, ajusta la cantidad.</p>
        {personas.map((persona, n) => <fieldset key={n} disabled={ocupado || !portal.puede_modificar}>
          <legend>{n === 0 ? "Titular" : `Acompanante ${n}`}</legend>
          <label>Apellido<input required maxLength={160} value={persona.apellido} onChange={e => editar(n, { apellido: e.target.value })} /></label>
          <label>Nombre<input required maxLength={160} value={persona.nombre} onChange={e => editar(n, { nombre: e.target.value })} /></label>
          {n > 0 && <label>Tipo de asistente<select value={persona.tipo} onChange={e => editar(n, { tipo: e.target.value as Persona["tipo"] })}><option value="ADULTO">Adulto</option><option value="MENOR">Menor</option></select></label>}
        </fieldset>)}
        {!portal.puede_modificar && <p>La confirmacion esta cerrada. Contacta al organizador si necesitas corregir datos.</p>}
        <FotosInvitado key={token} slug={slug} credenciales={datosAcceso()} alOcupar={setOcupadoFotos} />
        {mensajes}
        <div className="form-actions"><button className="secondary-button" type="button" disabled={ocupado || ocupadoFotos} onClick={() => setAbierta(false)}>Cancelar</button><button className="action-button" disabled={ocupado || ocupadoFotos || !portal.puede_modificar}>{ocupado ? "Confirmando..." : "Confirmar"}</button></div>
      </form>}
    </Ventana>}
  </section>;
}
