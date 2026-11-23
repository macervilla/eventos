import axios from "axios";
import { MutableRefObject, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { conectarMedia, ConexionMedia, CredencialMedia } from "../api/webrtc";
import { Ventana } from "./Ventana";
import { useConfirmacion } from "./useConfirmacion";

export type AccesoInvitado = { token: string; sesion?: string };
export type EstadoCamara = { estado: string; invitacion_id: number | null; invitado: string | null; emision: string | null; seleccionada?: boolean };
export type EstadoVideo = EstadoCamara & { disponible: boolean; puede_publicar: boolean; publicacion?: EstadoCamara; camaras?: EstadoCamara[]; limite_camaras?: number; limite_servidor?: number };
function mensaje(err: unknown) {
  const detalle = axios.isAxiosError(err) ? err.response?.data?.detail : null;
  if (typeof detalle === "string") return detalle;
  if (err instanceof DOMException && err.name === "NotAllowedError") return "Permiti el acceso a camara y microfono desde el navegador para transmitir";
  return err instanceof Error ? err.message : "No se pudo conectar el video. Intenta nuevamente";
}

function useEstado(slug: string, cred: AccesoInvitado | undefined, sesion: MutableRefObject<ConexionMedia | null>, habilitado = true) {
  const [estado, setEstado] = useState<EstadoVideo | null>(null);
  useEffect(() => {
    if (!habilitado) return;
    const abortar = new AbortController(); let enCurso = false;
    const actualizar = async () => {
      if (enCurso) return; enCurso = true;
      try {
        const { data } = await api.post<EstadoVideo>(`/invitados/${slug}/vivo/estado`, { ...cred, sesion_media: sesion.current?.id || undefined }, { signal: abortar.signal });
        setEstado(data);
      } catch { if (!abortar.signal.aborted) setEstado(null); }
      finally { enCurso = false; }
    };
    void actualizar(); const timer = window.setInterval(() => void actualizar(), 3000);
    const renovar = () => void actualizar(); window.addEventListener("eventos:video", renovar);
    return () => { abortar.abort(); window.clearInterval(timer); window.removeEventListener("eventos:video", renovar); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, cred?.token, cred?.sesion, habilitado]);
  return estado;
}

export function HabilitarTransmisor({ slug, invitado, estado }: { slug: string; invitado: { id: number; nombre: string; apellido: string }; estado: EstadoVideo | null }) {
  const { confirmar, ventanaConfirmacion } = useConfirmacion();
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const camara = estado?.camaras?.find(c => c.invitacion_id === invitado.id);
  const transmitiendo = Boolean(estado?.disponible && camara?.estado === "activa");
  const habilitado = Boolean(camara);
  async function habilitar() {
    if (!await confirmar(habilitado
      ? `Pausar la transmision de ${invitado.apellido} ${invitado.nombre}? Deberas volver a habilitarlo para que pueda transmitir.`
      : `Habilitar la camara de ${invitado.apellido} ${invitado.nombre}? Podra transmitir junto a los otros invitados habilitados.`,
    habilitado ? "Pausar transmision" : "Habilitar transmision", habilitado ? "Pausar" : "Habilitar")) return;
    setOcupado(true); setError(null);
    try { await api.put(`/invitados/${slug}/vivo/autorizacion`, { invitacion_id: invitado.id, habilitada: !habilitado }); }
    catch (err) { setError(mensaje(err)); }
    finally { setOcupado(false); window.dispatchEvent(new Event("eventos:video")); }
  }
  return <><button className={`secondary-button${transmitiendo ? " transmision-activa" : ""}`} disabled={ocupado} onClick={() => void habilitar()}>{habilitado ? "Pausar transmision" : "Habilitar transmision"}</button>{error && <p className="form-error" role="alert">{error}</p>}{ventanaConfirmacion}</>;
}

export function ControlVideoAdmin({ slug, alCambiarEstado }: { slug: string; alCambiarEstado: (estado: EstadoVideo | null) => void }) {
  const sesion = useRef<ConexionMedia | null>(null);
  const estado = useEstado(slug, undefined, sesion);
  useEffect(() => { alCambiarEstado(estado); }, [estado, alCambiarEstado]);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  async function seleccionar(invitacion_id: number | null) {
    setOcupado(true); setError(null);
    try { await api.put(`/invitados/${slug}/vivo/seleccion`, { invitacion_id }); }
    catch (err) { setError(mensaje(err)); }
    finally { setOcupado(false); window.dispatchEvent(new Event("eventos:video")); }
  }
  return <section className="invitados-panel">
    <h2>Transmision en vivo</h2>
    <p>Habilita las camaras desde la fila de cada invitado. Marca con un tilde la que queres mostrar en el album. Solo se emite una a la vez.</p>
    <p>{estado?.camaras?.length || 0} / {estado?.limite_camaras ?? 4} camaras habilitadas. {estado?.invitado ? `En el album: ${estado.invitado}.` : "El album muestra las fotos."}</p>
    {!estado?.disponible && <p>El servidor de video no esta disponible. La gestion de invitados y fotos sigue funcionando.</p>}
    <div className="video-camaras">{estado?.camaras?.map(c => <article key={c.invitacion_id} className={`video-camara${c.seleccionada ? " video-camara-elegida" : ""}`}>
      <h3>{c.invitado}</h3>
      <p>{c.estado === "activa" ? "En vivo" : c.estado === "autorizado" ? "Esperando camara" : c.estado === "iniciando" ? "Conectando..." : "Sin transmision"}</p>
      {estado.disponible && c.emision ? <ReproductorEnVivo slug={slug} camara={c} /> : <div className="video-camara-espera">La vista previa aparece cuando el invitado inicia la transmision.</div>}
      <label className="video-camara-seleccion"><input type="checkbox" checked={Boolean(c.seleccionada)} disabled={ocupado || !estado.disponible || (!c.seleccionada && !c.emision)} onChange={e => void seleccionar(e.target.checked ? c.invitacion_id : null)} />Emitir en Album</label>
    </article>)}</div>
    {!!estado?.camaras?.length && <button className="secondary-button" disabled={ocupado} onClick={async () => {
      setOcupado(true); setError(null);
      try { await api.put(`/invitados/${slug}/vivo/autorizacion`, { invitacion_id: null }); }
      catch (err) { setError(mensaje(err)); }
      finally { setOcupado(false); window.dispatchEvent(new Event("eventos:video")); }
    }}>Detener todas las transmisiones</button>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </section>;
}

export function ReproductorEnVivo({ slug, credenciales, alCambiarActividad, camara }: { slug: string; credenciales?: AccesoInvitado; alCambiarActividad?: (activa: boolean) => void; camara?: EstadoCamara }) {
  const video = useRef<HTMLVideoElement>(null);
  const conexion = useRef<ConexionMedia | null>(null);
  const seleccionado = useEstado(slug, credenciales, conexion, !camara);
  const estado = camara ? { ...camara, disponible: true } : seleccionado;
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [silenciado, setSilenciado] = useState(true);
  const activa = Boolean(estado?.disponible && estado.estado === "activa" && estado.emision);
  useEffect(() => { alCambiarActividad?.(activa); }, [activa, alCambiarActividad]);
  // Las vistas previas renuevan su propia sesion, sin negociar video en cada sondeo del panel.
  useEffect(() => {
    if (!camara) return;
    const abortar = new AbortController();
    const timer = window.setInterval(() => {
      if (conexion.current) void api.post(`/invitados/${slug}/vivo/estado`, { sesion_media: conexion.current.id }, { signal: abortar.signal }).catch(() => undefined);
    }, 15000);
    return () => { abortar.abort(); window.clearInterval(timer); };
  }, [slug, Boolean(camara)]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!activa) return;
    const abortar = new AbortController(); setError(null);
    const iniciar = async () => {
      try {
        const { data } = await api.post<CredencialMedia>(`/invitados/${slug}/vivo/ver`, { ...credenciales, invitacion_id: camara?.invitacion_id || undefined }, { signal: abortar.signal });
        const nueva = await conectarMedia(data, abortar.signal, { video: video.current!, alDesconectar: () => {
          setError("Se interrumpio el video. Reintentando..."); setRevision(n => n + 1);
        } });
        if (abortar.signal.aborted) nueva.cerrar(); else conexion.current = nueva;
      } catch (err) { if (!abortar.signal.aborted) setError(mensaje(err)); }
    };
    void iniciar();
    return () => { abortar.abort(); conexion.current?.cerrar(); conexion.current = null; };
    // El componente no depende del listado de fotos ni de sus actualizaciones.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, activa, estado?.emision, credenciales?.token, credenciales?.sesion, revision, camara?.invitacion_id]);
  if (!activa) return null;
  return <section className={camara ? "video-camara-preview" : "album-evento-escenario album-evento-vivo"} aria-label={camara ? `Vista previa de ${camara.invitado}` : "En vivo"}>
    <video ref={video} autoPlay playsInline controls={!camara} muted={camara ? true : silenciado} />
    {!camara && <div className="album-evento-vivo-info"><span>En vivo · {estado?.invitado}</span>
      <button className="secondary-button" onClick={() => { setSilenciado(v => !v); if (video.current) { video.current.muted = !silenciado; void video.current.play().catch(() => undefined); } }}>{silenciado ? "Activar audio" : "Silenciar audio"}</button></div>}
    {error && activa && <p role="status">{error} <button className="secondary-button" onClick={() => setRevision(n => n + 1)}>Reintentar video</button></p>}
  </section>;
}

export function PublicadorEvento({ slug, credenciales }: { slug: string; credenciales: AccesoInvitado }) {
  const conexion = useRef<ConexionMedia | null>(null);
  const estado = useEstado(slug, credenciales, conexion);
  const stream = useRef<MediaStream | null>(null);
  const preview = useRef<HTMLVideoElement>(null);
  const operacion = useRef<AbortController | null>(null);
  const reserva = useRef<string | null>(null);
  const generacion = useRef(0);
  const [abierta, setAbierta] = useState(false);
  const [lista, setLista] = useState(false);
  const [iniciando, setIniciando] = useState(false);
  const [transmitiendo, setTransmitiendo] = useState(false);
  const [camara, setCamara] = useState<"user" | "environment">("environment");
  const [error, setError] = useState<string | null>(null);
  const credRef = useRef(credenciales); credRef.current = credenciales;

  function detener(notificar = true, interrumpida = false) {
    generacion.current++; operacion.current?.abort(); operacion.current = null;
    conexion.current?.cerrar(); conexion.current = null;
    stream.current?.getTracks().forEach(t => t.stop()); stream.current = null;
    if (preview.current) preview.current.srcObject = null;
    const anterior = reserva.current; reserva.current = null;
    if (anterior && notificar) void api.post(`/invitados/${slug}/vivo/detener`, { ...credRef.current, reserva: anterior, motivo: interrumpida ? "interrumpida" : "finalizada" }).catch(() => undefined);
    setLista(false); setTransmitiendo(false); setIniciando(false);
  }
  useEffect(() => () => detener(), [slug]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (estado && (!estado.puede_publicar || !estado.disponible || (estado.publicacion?.estado === "interrumpida" && reserva.current)) && (stream.current || reserva.current)) {
      detener(false); setError("La transmision se detuvo: cambio la autorizacion o el servidor no esta disponible");
    }
  }, [estado]); // eslint-disable-line react-hooks/exhaustive-deps

  async function preparar() {
    setAbierta(true); setError(null);
    const intento = ++generacion.current;
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error("La camara necesita HTTPS o localhost y un navegador compatible");
      const local = await navigator.mediaDevices.getUserMedia({ audio: true, video: { facingMode: { ideal: camara }, width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 24, max: 30 } } });
      if (intento !== generacion.current) { local.getTracks().forEach(t => t.stop()); return; }
      stream.current = local; if (preview.current) preview.current.srcObject = local; setLista(true);
    } catch (err) { if (intento === generacion.current) setError(mensaje(err)); }
  }
  async function iniciar() {
    if (!stream.current || iniciando || transmitiendo) return;
    setIniciando(true); setError(null);
    const abortar = new AbortController(); operacion.current = abortar;
    try {
      const { data } = await api.post<CredencialMedia>(`/invitados/${slug}/vivo/iniciar`, credRef.current, { signal: abortar.signal });
      reserva.current = data.reserva;
      const nueva = await conectarMedia(data, abortar.signal, { stream: stream.current, alDesconectar: () => {
        detener(false); setError("La transmision se interrumpio. Podes preparar la camara y volver a iniciar");
      } });
      if (abortar.signal.aborted) nueva.cerrar(); else { conexion.current = nueva; setTransmitiendo(true); }
    } catch (err) { if (!abortar.signal.aborted) { detener(true, true); setError(mensaje(err)); } }
    finally { setIniciando(false); }
  }
  async function cambiar() {
    if (!stream.current || iniciando) return;
    setIniciando(true); setError(null);
    const intento = generacion.current;
    const siguiente = camara === "user" ? "environment" : "user";
    const vieja = stream.current.getVideoTracks()[0]; vieja?.stop();
    let nueva: MediaStream | null = null;
    try {
      nueva = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: siguiente }, width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 24, max: 30 } } });
      if (intento !== generacion.current) { nueva.getTracks().forEach(t => t.stop()); return; }
      const track = nueva.getVideoTracks()[0];
      const sender = conexion.current?.pc.getSenders().find(s => s.track?.kind === "video");
      if (sender) await sender.replaceTrack(track);
      stream.current!.removeTrack(vieja); stream.current!.addTrack(track);
      if (preview.current) preview.current.srcObject = new MediaStream(stream.current!.getTracks());
      setCamara(siguiente);
    } catch (err) { nueva?.getTracks().forEach(t => t.stop()); detener(true, true); setError(mensaje(err)); }
    finally { setIniciando(false); }
  }
  if (!estado?.puede_publicar && !abierta) return null;
  return <>
    <button className="action-button" disabled={!estado?.disponible} onClick={() => void preparar()}>Iniciar transmision</button>
    {abierta && <Ventana titulo="Transmitir en vivo" alCerrar={() => { detener(); setAbierta(false); }}>
      <video ref={preview} className="video-preview" autoPlay muted playsInline />
      <p>{transmitiendo ? "Transmision conectada. El estado activo se verifica en el servidor." : "Revisa la camara y el microfono antes de iniciar."}</p>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="invitados-acciones">
        {!lista && <button className="secondary-button" onClick={() => void preparar()}>Preparar camara</button>}
        <button className="action-button" disabled={!lista || iniciando || transmitiendo || !estado?.puede_publicar || !estado?.disponible} onClick={() => void iniciar()}>{iniciando ? "Conectando..." : "Iniciar"}</button>
        <button className="secondary-button" disabled={!lista || iniciando} onClick={() => void cambiar()}>Cambiar camara</button>
        <button className="secondary-button" onClick={() => detener()}>Detener</button>
      </div>
    </Ventana>}
  </>;
}
