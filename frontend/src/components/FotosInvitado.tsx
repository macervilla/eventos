import axios from "axios";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useConfirmacion } from "./useConfirmacion";
import { Ventana } from "./Ventana";

type Foto = { id: number; nombre: string; mime_type: string; slot: number };
type Fotos = { fotos: Foto[]; bloqueadas: boolean; limite: number };
type Credenciales = { token: string; sesion?: string };
function errorFotos(err: unknown) {
  const detalle = axios.isAxiosError(err) ? err.response?.data?.detail : null;
  return typeof detalle === "string" && detalle !== "Not Found" ? detalle : "No se pudieron consultar o guardar las fotos. Intenta nuevamente.";
}

export function FotosInvitado({ slug, invitadoId, credenciales, alOcupar }: {
  slug: string; invitadoId?: number; credenciales?: Credenciales; alOcupar?: (ocupado: boolean) => void;
}) {
  const admin = invitadoId !== undefined;
  const base = `/invitados/${slug}/${admin ? `lista/${invitadoId}/fotos` : "portal/fotos"}`;
  const token = credenciales?.token, sesion = credenciales?.sesion;
  const [datos, setDatos] = useState<Fotos | null>(null);
  const [imagenes, setImagenes] = useState<Record<number, string>>({});
  const [cargando, setCargando] = useState(true);
  const [ocupado, setOcupado] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [vista, setVista] = useState<Foto | null>(null);
  const [seleccion, setSeleccion] = useState<number[]>([]);
  const { confirmar, ventanaConfirmacion } = useConfirmacion();
  useEffect(() => {
    alOcupar?.(ocupado || confirmando || vista !== null);
    return () => alOcupar?.(false);
  }, [ocupado, confirmando, vista, alOcupar]);

  useEffect(() => {
    const abortar = new AbortController();
    const urls: string[] = [];
    setCargando(true); setImagenes({});
    async function cargar() {
      try {
        const { data } = admin ? await api.get<Fotos>(base, { signal: abortar.signal })
          : await api.post<Fotos>(base + "/listar", { token, sesion }, { signal: abortar.signal });
        if (!Array.isArray(data.fotos)) throw new Error("Respuesta de fotos invalida");
        setDatos(data);
        setSeleccion(actual => actual.filter(id => data.fotos.some(f => f.id === id)));
        const vistas = await Promise.all(data.fotos.map(async foto => {
          try {
            const imagen = admin ? await api.get(`${base}/${foto.id}/imagen`, { responseType: "blob", signal: abortar.signal })
              : await api.post(`${base}/${foto.id}/imagen`, { token, sesion }, { responseType: "blob", signal: abortar.signal });
            if (abortar.signal.aborted) return null;
            const url = URL.createObjectURL(imagen.data); urls.push(url);
            return [foto.id, url] as const;
          } catch (err) { if (!abortar.signal.aborted) setError(errorFotos(err)); return null; }
        }));
        if (!abortar.signal.aborted) setImagenes(Object.fromEntries(vistas.filter(v => v !== null)));
      } catch (err) {
        if (!abortar.signal.aborted) { setDatos(null); setImagenes({}); setError(errorFotos(err)); }
      } finally { if (!abortar.signal.aborted) setCargando(false); }
    }
    void cargar();
    return () => { abortar.abort(); urls.forEach(url => URL.revokeObjectURL(url)); };
  }, [base, admin, token, sesion, revision]);

  async function subir(files: File[]) {
    if (!datos || ocupado || confirmando || datos.bloqueadas || !files.length) return;
    if (files.length > datos.limite - datos.fotos.length) {
      setError(`Podes subir hasta ${datos.limite} fotos en total. Quita alguna o selecciona menos archivos.`); return;
    }
    setOcupado(true); setError(null); setAviso(null);
    let cargadas = 0;
    try {
      for (const file of files) {
        const form = new FormData(); form.append("file", file); form.append("token", token || "");
        if (sesion) form.append("sesion", sesion);
        await api.post(base, form); cargadas++;
      }
      setAviso(`${cargadas} ${cargadas === 1 ? "foto subida" : "fotos subidas"}. Podes revisarlas y cambiarlas hasta que el administrador las confirme.`);
    } catch (err) {
      setAviso(cargadas ? `${cargadas} fotos se guardaron antes del error.` : null); setError(errorFotos(err));
    } finally { setOcupado(false); setRevision(n => n + 1); }
  }

  async function quitar(foto: Foto) {
    if (ocupado || confirmando || datos?.bloqueadas) return;
    setConfirmando(true);
    const aceptado = await confirmar(`Quitar ${foto.nombre}? Despues podras subir otra foto.`, "Quitar foto", "Quitar foto");
    setConfirmando(false); if (!aceptado) return;
    setOcupado(true); setError(null); setAviso(null);
    try { await api.post(`${base}/${foto.id}/quitar`, { token, sesion }); setAviso("Foto quitada. Ya podes subir otra."); }
    catch (err) { setError(errorFotos(err)); }
    finally { setOcupado(false); setRevision(n => n + 1); }
  }

  async function bloquear() {
    if (!datos || ocupado || confirmando) return;
    if (!datos.bloqueadas) {
      setConfirmando(true);
      const aceptado = await confirmar(`Confirmar las ${datos.fotos.length} fotos? El invitado no podra cambiarlas hasta que las desbloquees.`, "Confirmar fotos", "Confirmar fotos");
      setConfirmando(false); if (!aceptado) return;
    }
    setOcupado(true); setError(null); setAviso(null);
    try {
      await api.put(base + "/estado", { bloqueadas: !datos.bloqueadas });
      setAviso(datos.bloqueadas ? "Fotos desbloqueadas. El invitado puede cambiarlas nuevamente." : "Fotos confirmadas y bloqueadas para el invitado.");
    } catch (err) { setError(errorFotos(err)); }
    finally { setOcupado(false); setRevision(n => n + 1); }
  }

  async function quitarSeleccionadas() {
    if (!admin || ocupado || confirmando || !seleccion.length) return;
    setConfirmando(true);
    const aceptado = await confirmar(`Quitar las ${seleccion.length} fotos seleccionadas? Dejaran de aparecer en el album y las fotos del invitado quedaran desbloqueadas para que pueda subir reemplazos.`, "Quitar fotos seleccionadas", "Confirmar y quitar");
    setConfirmando(false); if (!aceptado) return;
    setOcupado(true); setError(null); setAviso(null);
    try {
      await api.post(base + "/quitar-seleccionadas", { ids: seleccion });
      setSeleccion([]); setAviso("Fotos quitadas. El invitado ya puede subir nuevas fotos.");
    } catch (err) { setError(errorFotos(err)); }
    finally { setOcupado(false); setRevision(n => n + 1); }
  }

  const deshabilitado = ocupado || confirmando || cargando;
  return <section className="fotos-invitado" aria-label={admin ? "Fotos enviadas por el invitado" : "Mis fotos para el evento"}>
    <h3>{admin ? "Fotos enviadas por el invitado" : "Mis fotos para el evento"}</h3>
    <p>Hasta 4 fotos. El administrador podra revisarlas y descargarlas para compartirlas en el evento.</p>
    {cargando && <p role="status">Cargando fotos...</p>}
    {datos && <>
      <p><strong>{datos.fotos.length} de {datos.limite} fotos</strong> · {datos.bloqueadas ? "Confirmadas y bloqueadas" : "Pendientes de confirmar por el administrador"}</p>
      {datos.bloqueadas && !admin && <p>El administrador confirmo tus fotos. Para cambiarlas, pedile que las desbloquee.</p>}
      {!datos.fotos.length && <p>Todavia no hay fotos enviadas.</p>}
      <div className="fotos-invitado-grilla">
        {datos.fotos.map((foto, n) => <figure key={foto.id}>
          {admin && <label className="foto-invitado-seleccion"><input type="checkbox" aria-label={`Seleccionar foto ${n + 1}`} disabled={deshabilitado} checked={seleccion.includes(foto.id)} onChange={e => setSeleccion(actual => e.target.checked ? [...actual, foto.id] : actual.filter(id => id !== foto.id))} /> Seleccionar</label>}
          <button type="button" className="foto-invitado-miniatura" aria-label={`Ver foto ${n + 1}`} disabled={!imagenes[foto.id] || deshabilitado} onClick={() => setVista(foto)}>
            {imagenes[foto.id] ? <img src={imagenes[foto.id]} alt={`Foto ${n + 1} del invitado`} /> : <span>Vista previa no disponible</span>}
          </button>
          <figcaption>{foto.nombre}</figcaption>
          {admin ? imagenes[foto.id] && <a className="secondary-button" href={imagenes[foto.id]} download={`foto-${foto.id}.${foto.mime_type.split("/")[1] || "jpg"}`}>Descargar foto {n + 1}</a>
            : <button type="button" className="secondary-button" aria-label={`Quitar foto ${n + 1}`} disabled={deshabilitado || datos.bloqueadas} onClick={() => void quitar(foto)}>Quitar</button>}
        </figure>)}
      </div>
      {admin ? <div className="invitados-acciones"><button type="button" className="action-button" disabled={deshabilitado || !datos.fotos.length} onClick={() => void bloquear()}>{datos.bloqueadas ? "Desbloquear fotos" : "Confirmar fotos"}</button><button type="button" className="secondary-button" disabled={deshabilitado || !seleccion.length} onClick={() => void quitarSeleccionadas()}>Quitar seleccionadas ({seleccion.length})</button></div>
        : <label className="fotos-invitado-subir">Subir fotos<input type="file" accept="image/jpeg,image/png,image/webp" multiple disabled={deshabilitado || datos.bloqueadas || datos.fotos.length >= datos.limite} onChange={e => {
          const files = Array.from(e.target.files || []); e.target.value = ""; void subir(files);
        }} /><small>JPG, PNG o WebP.</small></label>}
    </>}
    {ocupado && <p role="status">Guardando fotos...</p>}
    {aviso && <p className="success-inline" role="status">{aviso}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <button type="button" className="secondary-button" disabled={deshabilitado} onClick={() => { setError(null); setRevision(n => n + 1); }}>Actualizar fotos</button>
    {vista && <Ventana titulo={`Foto: ${vista.nombre}`} alCerrar={() => setVista(null)}><img className="foto-invitado-ampliada" src={imagenes[vista.id]} alt="Foto ampliada del invitado" /><button className="secondary-button" type="button" onClick={() => setVista(null)}>Volver a las fotos</button></Ventana>}
    {ventanaConfirmacion}
  </section>;
}
