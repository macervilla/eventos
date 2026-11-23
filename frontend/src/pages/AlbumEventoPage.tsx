import axios from "axios";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { AccesoInvitado, ReproductorEnVivo } from "../components/VideoEvento";

type Foto = { id: number; nombre: string };
type Album = { evento: string; fotos: Foto[]; base: string };

export function AlbumEventoPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const base = `/invitados/${slug}/album`;
  const [credenciales] = useState<AccesoInvitado | undefined>(() => {
    try { return JSON.parse(sessionStorage.getItem(`eventos_album_invitacion:${slug}`) || "null") || undefined; }
    catch { return undefined; }
  });
  const [album, setAlbum] = useState<Album | null>(null);
  const [indice, setIndice] = useState(0);
  const [pausado, setPausado] = useState(false);
  const [enVivo, setEnVivo] = useState(false);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [errorImagen, setErrorImagen] = useState(false);
  const [imagen, setImagen] = useState<string | null>(null);
  const cache = useRef(new Map<number, string>());
  const pantalla = useRef<HTMLElement>(null);
  const fotos = album?.base === base ? album.fotos : [];
  const fotoActual = useRef<number | null>(null); fotoActual.current = fotos[indice]?.id || null;

  function limpiarCache() {
    cache.current.forEach(url => URL.revokeObjectURL(url)); cache.current.clear();
  }
  useEffect(() => {
    const abortar = new AbortController();
    let enCurso = false;
    const actualizar = async () => {
      if (enCurso) return; enCurso = true;
      try {
        const { data } = credenciales ? await api.post<Omit<Album, "base">>(`/invitados/${slug}/portal/album`, credenciales, { signal: abortar.signal })
          : await api.get<Omit<Album, "base">>(base, { signal: abortar.signal });
        if (abortar.signal.aborted) return;
        const actual = data.fotos.findIndex(f => f.id === fotoActual.current);
        setIndice(n => actual >= 0 ? actual : Math.max(0, Math.min(n, data.fotos.length - 1)));
        setAlbum({ ...data, base }); setError(null);
      } catch (err) {
        if (abortar.signal.aborted) return;
        if (axios.isAxiosError(err) && err.response?.status === 401) {
          navigate(`/ingresar?destino=${encodeURIComponent(`/${slug}/album`)}`, { replace: true }); return;
        }
        if (axios.isAxiosError(err) && err.response?.status === 403) setAlbum(null);
        setError(axios.isAxiosError(err) && err.response?.status === 403
          ? "Esta cuenta no tiene permiso para ver el album de este evento."
          : "No se pudo cargar el album. Intenta actualizar.");
      } finally { enCurso = false; }
    };
    void actualizar(); const intervalo = window.setInterval(() => void actualizar(), 10000);
    return () => { abortar.abort(); window.clearInterval(intervalo); };
  }, [base, revision, navigate, slug, credenciales]);
  useEffect(() => () => limpiarCache(), [base]);

  useEffect(() => {
    if (!fotos.length) { setImagen(null); return; }
    const abortar = new AbortController();
    const actual = fotos[indice];
    const necesarias = [...new Set([actual.id, fotos[(indice + 1) % fotos.length].id,
      fotos[(indice + fotos.length - 1) % fotos.length].id])];
    // Conservar como maximo la foto actual y sus dos vecinas, sin cargar todo el album en memoria.
    for (const [id, url] of cache.current) {
      if (!necesarias.includes(id)) { URL.revokeObjectURL(url); cache.current.delete(id); }
    }
    setImagen(cache.current.get(actual.id) || null); setErrorImagen(false);
    async function cargarImagenes() {
      for (const id of necesarias) {
        if (cache.current.has(id)) continue;
        try {
          const { data } = credenciales ? await api.post(`/invitados/${slug}/portal/album/${id}/imagen`, credenciales, { responseType: "blob", signal: abortar.signal })
            : await api.get(`${base}/${id}/imagen`, { responseType: "blob", signal: abortar.signal });
          if (abortar.signal.aborted) return;
          const url = URL.createObjectURL(data); cache.current.set(id, url);
          if (id === actual.id) setImagen(url);
        } catch (err) {
          if (abortar.signal.aborted) return;
          if (axios.isAxiosError(err) && [401, 403].includes(err.response?.status || 0)) {
            limpiarCache(); setImagen(null); setAlbum(null); setError("La sesion ya no permite acceder al album. Volve a ingresar."); return;
          }
          if (id === actual.id) setErrorImagen(true);
        }
      }
    }
    void cargarImagenes();
    return () => abortar.abort();
  }, [base, fotos, indice, credenciales, slug]);

  useEffect(() => {
    if (enVivo || pausado || fotos.length < 2 || (!imagen && !errorImagen)) return;
    const temporizador = window.setTimeout(() => setIndice(n => (n + 1) % fotos.length), 2000);
    return () => window.clearTimeout(temporizador);
  }, [indice, pausado, enVivo, fotos.length, imagen, errorImagen]);

  function mover(delta: number) { setIndice(n => (n + delta + fotos.length) % fotos.length); }
  async function ampliar() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await pantalla.current?.requestFullscreen();
    } catch { setError("No se pudo activar la pantalla completa en este navegador."); }
  }

  return <main className="album-evento" ref={pantalla}>
    <header className="album-evento-encabezado">
      <div><h1>{album ? `Album de ${album.evento}` : "Album del evento"}</h1></div>
      <div className="invitados-acciones"><button className="secondary-button" onClick={() => setRevision(n => n + 1)}>Actualizar album</button><button className="secondary-button" onClick={() => void ampliar()}>Pantalla completa</button><Link className="secondary-button" to={`/${slug}/invitados`}>Gestion de invitados</Link></div>
    </header>
    {error && <p className="form-error" role="alert">{error}</p>}
    {slug && <ReproductorEnVivo key={slug} slug={slug} credenciales={credenciales} alCambiarActividad={setEnVivo} />}
    {!album && !error && <p role="status">Cargando album...</p>}
    {!enVivo && album && !fotos.length && <p className="album-evento-vacio">El evento todavia no tiene fotos aprobadas.</p>}
    {!enVivo && !!fotos.length && <>
      <div className="album-evento-escenario">
        {imagen ? <img className="album-evento-imagen" src={imagen} alt={`Foto ${indice + 1} de ${fotos.length}: ${fotos[indice].nombre}`} />
          : <p role="status">{errorImagen ? "Esta foto no esta disponible." : "Cargando foto..."}</p>}
      </div>
      <footer className="album-evento-controles">
        <button className="secondary-button" disabled={fotos.length < 2} onClick={() => mover(-1)}>Anterior</button>
        <button className="action-button" onClick={() => setPausado(p => !p)}>{pausado ? "Reanudar carrusel" : "Pausar carrusel"}</button>
        <span>{indice + 1} / {fotos.length}</span>
        <button className="secondary-button" disabled={fotos.length < 2} onClick={() => mover(1)}>Siguiente</button>
      </footer>
    </>}
  </main>;
}
