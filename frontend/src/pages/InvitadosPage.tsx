import axios from "axios";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { Ventana } from "../components/Ventana";

export type Invitado = {
  id: number; nombre: string; apellido: string; email: string | null; telefono: string | null;
  whatsapp: string | null; facebook: string | null; telegram: string | null; otro_contacto: string | null;
  instagram: string | null; grupo: string | null; responsable_id: number; cantidad_permitida: number;
  adultos: number; menores: number; nombres_menores: string[]; solicitados: number; cupo_aprobado: number;
  ingresados: number; restantes: number; rsvp: string; aprobacion: string; distribucion: string; canal: string | null; activo: boolean;
};
type AgendaContacto = { name?: string[]; tel?: string[]; email?: string[] };
type NavegadorContactos = Navigator & { contacts?: { select: (propiedades: string[], opciones: { multiple: boolean }) => Promise<AgendaContacto[]> } };
type Acceso = { permisos: string[]; solo_responsable: boolean; usuario_id: number; config: Config; roles_disponibles: Record<string, string[]> };
type Config = { activo: boolean; aprobacion: string; validacion: string; permitir_modificaciones: boolean; cierre_rsvp: string | null;
  listas_compartidas: boolean; canales: string[]; otp_minutos: number; otp_intentos: number; tiene_pin?: boolean; pin_acceso?: string | null; quitar_pin?: boolean };
type Rol = { id: number; email: string; usuario_id: number; rol: string; permisos: string[]; solo_responsable: boolean };
const vacio = { nombre: "", apellido: "", email: "", telefono: "", instagram: "", whatsapp: "", facebook: "", telegram: "", otro_contacto: "", grupo: "", cantidad_permitida: 1, responsable_id: 0, activo: true };
const etiquetas: Record<string, string> = { ver_invitados: "Consultar invitados y confirmaciones", editar_invitados: "Editar invitados", importar: "Importar Excel",
  distribuir: "Distribuir invitaciones", aprobar: "Aprobar y emitir QR", estadisticas: "Ver estadisticas", confirmar_asistido: "Confirmar en nombre del invitado",
  roles: "Asignar roles", configurar_invitados: "Configurar este modulo", control_ingreso: "Registrar ingresos", ver_asistencia: "Consultar asistencia",
  corregir_ingresos: "Corregir ingresos con auditoria", configurar_evento: "Editar configuracion general del evento" };
export function errorMensaje(err: unknown) {
  const detalle = axios.isAxiosError(err) ? err.response?.data?.detail : null;
  return typeof detalle === "string" ? detalle : "No se pudo completar la operacion. Revisa los datos e intenta nuevamente.";
}
export async function descargarArchivo(url: string, nombre: string, datos?: unknown) {
  const r = datos ? await api.post(url, datos, { responseType: "blob" }) : await api.get(url, { responseType: "blob" });
  const objeto = URL.createObjectURL(r.data);
  const a = document.createElement("a"); a.href = objeto; a.download = nombre; a.click();
  window.setTimeout(() => URL.revokeObjectURL(objeto), 1000);
}

export function InvitadosPage() {
  const { slug } = useParams(); const navigate = useNavigate();
  const base = `/invitados/${slug}`;
  const [acceso, setAcceso] = useState<Acceso | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [lista, setLista] = useState<Invitado[]>([]); const [total, setTotal] = useState(0);
  const [roles, setRoles] = useState<Rol[]>([]); const [kpis, setKpis] = useState<Record<string, number>>({});
  const [pagina, setPagina] = useState(0); const [q, setQ] = useState("");
  const [filtros, setFiltros] = useState({ q: "", estado: "", canal: "", grupo: "", responsable_id: "", desde: "", hasta: "", activo: "true" });
  const [seleccion, setSeleccion] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null); const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [editor, setEditor] = useState<Invitado | "nuevo" | null>(null);
  const [form, setForm] = useState({ ...vacio });
  const [rsvp, setRsvp] = useState<Invitado | null>(null); const [adultos, setAdultos] = useState(1); const [menores, setMenores] = useState("");
  const [aprobar, setAprobar] = useState<Invitado | null>(null); const [cupo, setCupo] = useState(1);
  const [canal, setCanal] = useState("whatsapp"); const [tipo, setTipo] = useState("invitacion");
  const [compartidos, setCompartidos] = useState<{ id: number; estado: string; detalle?: string; mensaje?: string; enlace?: string; url_canal?: string; portada_url?: string; titulo?: string; canal?: string; destinatario?: string; telefono_destino?: string }[]>([]);
  const [ventanaEnvio, setVentanaEnvio] = useState<string | null>(null);
  const [emailsAgasajados, setEmailsAgasajados] = useState("");
  const [archivoPortada, setArchivoPortada] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ token: string; filas: { fila: number; error?: string; accion?: string; datos?: { nombre: string; apellido: string } }[] } | null>(null);
  const [informe, setInforme] = useState<{ importados: number; actualizados: number; omitidos: number; rechazados: { fila: number; error: string }[] } | null>(null);
  const [actualizarImportacion, setActualizarImportacion] = useState(false);
  const [rolForm, setRolForm] = useState({ email: "", rol: "AGASAJADO", permisos: ["ver_invitados", "editar_invitados", "distribuir", "estadisticas"], solo_responsable: false });
  const [historial, setHistorial] = useState<{ auditoria: { accion: string; actor_id: number | null; actor?: string; fecha: string; datos: Record<string, unknown> }[]; distribuciones: { canal: string; estado: string; detalle: string; fecha: string }[] } | null>(null);
  const tiene = (p: string) => Boolean(acceso?.permisos.includes(p));
  const params = Object.fromEntries(Object.entries(filtros).filter(([, v]) => v !== ""));

  const cargar = useCallback(async () => {
    try {
      const { data } = await api.get<Acceso>(base + "/acceso");
      setAcceso(data); setConfig(actual => actual || data.config);
      if (data.permisos.includes("roles")) setRoles((await api.get<Rol[]>(base + "/roles")).data);
      if (data.config.activo) {
        const p = Object.fromEntries(Object.entries(filtros).filter(([, v]) => v !== ""));
        if (data.permisos.some(v => ["ver_invitados", "control_ingreso"].includes(v))) {
          const r = await api.get<{ items: Invitado[]; total: number }>(base + "/lista", { params: { ...p, offset: pagina * 25 } });
          setLista(r.data.items); setTotal(r.data.total);
        }
        if (data.permisos.includes("estadisticas")) setKpis((await api.get(base + "/estadisticas", { params: p })).data);
      }
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) navigate(`/ingresar?destino=${encodeURIComponent(`/e/${slug}/invitados`)}`, { replace: true });
      else setError(errorMensaje(err));
    }
  }, [base, filtros, pagina, navigate, slug]);
  useEffect(() => { void cargar(); }, [cargar]);

  async function ejecutar(accion: () => Promise<unknown>, mensaje = "Cambios guardados.") {
    setOcupado(true); setError(null); setAviso(null);
    try { await accion(); setAviso(mensaje); await cargar(); }
    catch (err) { setError(errorMensaje(err)); }
    finally { setOcupado(false); }
  }
  function editar(inv: Invitado | "nuevo") {
    setEditor(inv); setError(null);
    setForm(inv === "nuevo" ? { ...vacio, responsable_id: acceso?.usuario_id || 0 } : {
      nombre: inv.nombre, apellido: inv.apellido, email: inv.email || "", telefono: inv.telefono || "", instagram: inv.instagram || "",
      whatsapp: inv.whatsapp || "", facebook: inv.facebook || "", telegram: inv.telegram || "", otro_contacto: inv.otro_contacto || "",
      grupo: inv.grupo || "", cantidad_permitida: inv.cantidad_permitida, responsable_id: inv.responsable_id, activo: inv.activo
    });
  }
  async function elegirContacto() {
    const agenda = (navigator as NavegadorContactos).contacts;
    if (!agenda || !window.isSecureContext) {
      setAviso("Este navegador no permite abrir la agenda. Copia el numero o usuario desde tus contactos y pegalo en el campo correspondiente.");
      return;
    }
    try {
      const [contacto] = await agenda.select(["name", "tel", "email"], { multiple: false });
      if (!contacto) return;
      setForm(actual => ({ ...actual, nombre: contacto.name?.[0] || actual.nombre, apellido: contacto.name?.[0] ? "" : actual.apellido,
        telefono: contacto.tel?.[0] || actual.telefono, email: contacto.email?.[0] || actual.email }));
      setAviso("Contacto cargado. Revisa los datos y completa WhatsApp o las redes antes de guardar.");
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError("No se pudo abrir la agenda. Podes completar o pegar el contacto manualmente.");
    }
  }
  const payload = (datos: typeof form) => ({ ...datos, email: datos.email || null, telefono: datos.telefono || null, instagram: datos.instagram || null, whatsapp: datos.whatsapp || null, facebook: datos.facebook || null, telegram: datos.telegram || null, otro_contacto: datos.otro_contacto || null, grupo: datos.grupo || null });
  function guardar(e: FormEvent) {
    e.preventDefault(); void ejecutar(async () => {
      if (editor === "nuevo") await api.post(base + "/lista", payload(form));
      else if (editor) await api.put(`${base}/lista/${editor.id}`, payload(form));
      setEditor(null);
    });
  }
  async function compartir(ids = seleccion, titulo = "Enviar invitaciones seleccionadas") {
    if (!canal) { setError("No hay canales habilitados para este evento."); return; }
    setCompartidos([]); setArchivoPortada(null); setVentanaEnvio(titulo);
    await ejecutar(async () => {
      const r = await api.post(base + "/distribuir", { ids, canal, tipo, idempotencia: crypto.randomUUID() });
      setCompartidos(r.data.resultados);
      setArchivoPortada(null);
      try {
        const imagen = await api.get(base + "/portada.jpg", { responseType: "blob" });
        setArchivoPortada(new File([imagen.data], "invitacion.jpg", { type: "image/jpeg" }));
      } catch { /* El enlace puede compartirse aunque falle la descarga de la portada. */ }
    }, canal === "email" ? "Consulta el resultado de cada envio." : "Revisa los resultados de preparacion. Los envios manuales se completan en la aplicacion elegida.");
  }
  useEffect(() => {
    const disponibles = acceso?.config.canales || [];
    if (acceso && !disponibles.includes(canal)) setCanal(disponibles[0] || "");
  }, [acceso, canal]);
  useEffect(() => { setCompartidos([]); setArchivoPortada(null); setVentanaEnvio(null); setEmailsAgasajados(""); }, [base]);
  function textoInvitacion(c: { mensaje?: string; enlace?: string }) {
    const texto = c.mensaje || "";
    return c.enlace && !texto.includes(c.enlace) ? `${texto}\n\nPresiona aqui para confirmar:\n${c.enlace}` : texto;
  }
  function enlaceWhatsApp(c: { url_canal?: string; mensaje?: string; enlace?: string }) {
    if (!c.url_canal) return "";
    const url = new URL(c.url_canal);
    url.searchParams.set("text", textoInvitacion(c));
    return url.toString();
  }
  async function compartirPortada(c: { mensaje?: string; titulo?: string; enlace?: string }) {
    if (!archivoPortada || !c.mensaje) return;
    const datos = { title: c.titulo || "Invitacion", text: textoInvitacion(c), files: [archivoPortada] };
    try {
      await navigator.share(datos);
      setAviso("Se completo la accion de compartir del dispositivo. La entrega al destinatario no esta confirmada.");
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError("No se pudo compartir el archivo desde este navegador. Descarga la portada y adjuntala junto al enlace personal.");
    }
  }
  const avisoUI = <>{error && <p role="alert" className="form-error">{error}</p>}{aviso && <p className="success-inline" role="status">{aviso}</p>}</>;
  return <main className="invitados-page">
    <header className="invitados-header"><div><Link to={`/e/${slug}`}>Volver al evento</Link><h1>Gestion de invitados</h1><p>Invitaciones, confirmaciones y cupos de este evento.</p></div>
      <div className="invitados-acciones"><button className="secondary-button" disabled={ocupado} onClick={() => void cargar()}>Actualizar</button>
      {tiene("control_ingreso") && <Link className="action-button" to={`/e/${slug}/control-ingreso`}>Control de ingreso</Link>}</div></header>
    {avisoUI}
    {!acceso && !error && <p>Cargando permisos...</p>}
    {acceso && !acceso.config.activo && <section className="empty-state"><p>El modulo esta desactivado. Habilitalo para agregar invitados individualmente o importar un Excel.</p>{tiene("configurar_invitados") ? <button className="action-button" disabled={ocupado} onClick={() => void ejecutar(async () => { const { tiene_pin, ...datos } = acceso.config; const r = await api.put(base + "/config", { ...datos, activo: true }); setConfig(r.data); }, "Modulo habilitado. Ya podes gestionar invitados.")}>Habilitar invitados</button> : <p>Un administrador debe habilitarlo para gestionar invitaciones.</p>}</section>}
    {tiene("roles") && <section className="invitados-panel agasajados-panel">
      <h2>Agasajados que pueden enviar invitaciones</h2>
      <p>Asigna una o mas cuentas. Podran ingresar con Google y compartir las invitaciones de este evento junto con el administrador, sin recibir permisos de edicion tecnica.</p>
      <form className="invitados-form" onSubmit={e => { e.preventDefault(); const emails = [...new Set(emailsAgasajados.split(/[\s,;]+/).map(v => v.trim()).filter(Boolean))]; if (!emails.length || emails.length > 20) { setError("Ingresa entre 1 y 20 emails de agasajados."); return; } void ejecutar(async () => { await api.post(base + "/agasajados", { emails }); setEmailsAgasajados(""); }, "Agasajados asignados. Ya pueden ingresar con sus cuentas y compartir invitaciones."); }}>
        <label>Emails de los agasajados, uno por linea<textarea required value={emailsAgasajados} onChange={e => setEmailsAgasajados(e.target.value)} placeholder="persona@gmail.com" /></label>
        <button className="action-button" disabled={ocupado}>Asignar agasajados</button>
      </form>
      <div className="agasajados-lista">{roles.filter(r => r.rol === "AGASAJADO" && r.permisos.includes("distribuir")).map(r => <span key={r.id}>{r.email}</span>)}</div>
      <small>Los permisos y la revocacion se administran en Agasajados, colaboradores y control de ingreso.</small>
    </section>}
    {tiene("configurar_invitados") && config && <details className="invitados-panel" open={!acceso?.config.activo}><summary>Configuracion del modulo</summary>
      <form className="invitados-form" onSubmit={e => { e.preventDefault(); void ejecutar(async () => { const { tiene_pin, ...datos } = config; const r = await api.put(base + "/config", datos); setConfig(r.data); }); }}>
        <label><input type="checkbox" checked={config.activo} onChange={e => setConfig({ ...config, activo: e.target.checked })} /> Habilitar invitados</label>
        <label>Aprobacion<select value={config.aprobacion} onChange={e => setConfig({ ...config, aprobacion: e.target.value })}><option value="manual">Manual</option><option value="automatica">Automatica</option></select></label>
        <label>Validacion del invitado<select value={config.validacion} onChange={e => setConfig({ ...config, validacion: e.target.value })}><option value="enlace">Codigo privado del evento (requiere PIN)</option><option value="email">Codigo por email</option><option value="telefono">Telefono (requiere proveedor oficial)</option></select></label>
        <p>Para confirmar, el receptor debe ingresar a su invitacion. Por defecto recibe un codigo por email; si elegis un codigo privado, configura un PIN. No necesita una cuenta de Google.</p>
        <label><input type="checkbox" checked={config.permitir_modificaciones} onChange={e => setConfig({ ...config, permitir_modificaciones: e.target.checked })} /> Permitir correcciones RSVP</label>
        <label><input type="checkbox" checked={config.listas_compartidas} onChange={e => setConfig({ ...config, listas_compartidas: e.target.checked })} /> Compartir listas entre responsables</label>
        <fieldset className="invitados-permisos"><legend>Canales habilitados</legend>{["email", "whatsapp", "instagram", "messenger", "telegram", "enlace"].map(c => <label key={c}><input type="checkbox" checked={config.canales?.includes(c) || false} onChange={e => setConfig({ ...config, canales: e.target.checked ? [...config.canales, c] : config.canales.filter(v => v !== c) })} />{c}</label>)}</fieldset>
        <label>Cierre RSVP<input type="datetime-local" value={config.cierre_rsvp ? new Date(new Date(config.cierre_rsvp).getTime() - new Date(config.cierre_rsvp).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : ""} onChange={e => setConfig({ ...config, cierre_rsvp: e.target.value ? new Date(e.target.value).toISOString() : null })} /></label>
        <label>Nuevo codigo privado opcional<input type="password" autoComplete="new-password" minLength={4} value={config.pin_acceso || ""} onChange={e => setConfig({ ...config, pin_acceso: e.target.value || null })} /><small>{config.tiene_pin ? "Ya existe un codigo configurado" : "Sin codigo adicional"}</small></label>
        <label><input type="checkbox" checked={config.quitar_pin || false} onChange={e => setConfig({ ...config, quitar_pin: e.target.checked })} /> Quitar codigo privado existente</label>
        <label>Vigencia codigo email (minutos)<input type="number" min={1} max={30} value={config.otp_minutos} onChange={e => setConfig({ ...config, otp_minutos: Number(e.target.value) })} /></label>
        <label>Intentos de codigo<input type="number" min={1} max={10} value={config.otp_intentos} onChange={e => setConfig({ ...config, otp_intentos: Number(e.target.value) })} /></label>
        <button className="action-button" disabled={ocupado}>Guardar configuracion</button>
      </form>
    </details>}
    {tiene("roles") && <details className="invitados-panel"><summary>Agasajados, colaboradores y control de ingreso</summary>
      <form className="invitados-form" onSubmit={e => { e.preventDefault(); void ejecutar(() => api.post(base + "/roles", rolForm)); }}>
        <label>Email de la cuenta<input type="email" required value={rolForm.email} onChange={e => setRolForm({ ...rolForm, email: e.target.value })} /></label>
        <label>Rol<select value={rolForm.rol} onChange={e => { const rol = e.target.value; setRolForm({ ...rolForm, rol, permisos: rol === "CONTROL_INGRESO" ? ["control_ingreso", "ver_asistencia"] : rol === "ADMIN_EVENTO" ? acceso!.roles_disponibles[rol] : ["ver_invitados", "editar_invitados", "distribuir"] }); }}>{Object.keys(acceso?.roles_disponibles || {}).map(r => <option key={r}>{r}</option>)}</select></label>
        <label><input type="checkbox" checked={rolForm.solo_responsable} onChange={e => setRolForm({ ...rolForm, solo_responsable: e.target.checked })} /> Ver solo su propia lista</label>
        <fieldset className="invitados-permisos"><legend>Permisos independientes</legend>{(acceso?.roles_disponibles[rolForm.rol] || []).map(p => <label key={p}><input type="checkbox" checked={rolForm.permisos.includes(p)} onChange={e => setRolForm({ ...rolForm, permisos: e.target.checked ? [...rolForm.permisos, p] : rolForm.permisos.filter(v => v !== p) })} />{etiquetas[p] || p}</label>)}</fieldset>
        <button className="action-button" disabled={ocupado}>Guardar asignacion</button>
      </form>
      {roles.map(r => <div className="invitados-rol" key={r.id}><span>{r.email} · {r.rol} · {r.solo_responsable ? "Lista propia" : "Lista compartida"}<small>{r.permisos.map(p => etiquetas[p] || p).join(", ") || "Sin permisos"}</small></span>
        {!['PROPIETARIO', 'ENCARGADO'].includes(r.rol) && <button className="secondary-button" disabled={ocupado} onClick={() => { if (window.confirm(`Revocar permisos de ${r.email} en este evento?`)) void ejecutar(() => api.post(`${base}/roles/${r.id}/revocar`)); }}>Revocar</button>}</div>)}
    </details>}
    {acceso?.config.activo && <>
      {!!Object.keys(kpis).length && <section className="invitados-kpis">{Object.entries(kpis).map(([k, v]) => <article key={k}><span>{k.replace(/_/g, " ")}</span><strong>{v}</strong></article>)}</section>}
      <section className="invitados-panel">
        <div className="invitados-acciones">
          {tiene("editar_invitados") && <button className="action-button" onClick={() => editar("nuevo")}>Agregar invitado individual</button>}
          {tiene("distribuir") && <button className="secondary-button" onClick={() => void ejecutar(() => descargarArchivo(base + "/portada.jpg", "invitacion.jpg"), "Portada descargada, sin datos personales.")}>Descargar portada JPG</button>}
          {tiene("ver_invitados") && <button className="secondary-button" onClick={() => void ejecutar(() => descargarArchivo(base + "/exportar.xlsx?" + new URLSearchParams(params), "invitados-confirmaciones.xlsx"), "Exportacion descargada.")}>Exportar Excel</button>}
          {tiene("importar") && <button className="secondary-button" onClick={() => void ejecutar(() => descargarArchivo(base + "/plantilla.xlsx", "plantilla-invitados.xlsx"), "Plantilla descargada.")}>Plantilla Excel</button>}
        </div>
        {tiene("importar") && <div className="invitados-importar"><p>Carga masiva: descarga la plantilla, completa los invitados y sus contactos (WhatsApp, Facebook, Instagram, Telegram u otro), y subi el Excel para revisar antes de importar.</p><label><input type="checkbox" checked={actualizarImportacion} onChange={e => setActualizarImportacion(e.target.checked)} /> Actualizar contactos existentes conservando confirmaciones</label>
          <label>Importar .xlsx (hasta 1000 filas)<input type="file" accept=".xlsx" disabled={ocupado} onChange={e => { const file = e.target.files?.[0]; e.target.value = ""; if (file) void ejecutar(async () => { const datos = new FormData(); datos.append("file", file); const r = await api.post(base + `/importar/preview?actualizar=${actualizarImportacion}`, datos); setPreview(r.data); }, "Vista previa lista. Todavia no se importaron invitados."); }} /></label></div>}
        <form className="invitados-filtros" onSubmit={e => { e.preventDefault(); setPagina(0); setSeleccion([]); setFiltros({ ...filtros, q }); }}>
          <label>Buscar<input value={q} onChange={e => setQ(e.target.value)} placeholder="Nombre, contacto o grupo" /></label>
          <label>Estado<select value={filtros.estado} onChange={e => { setPagina(0); setFiltros({ ...filtros, estado: e.target.value }); }}><option value="">Todos</option>{Object.entries({ rsvp: ["PENDIENTE", "CONFIRMADO", "MODIFICADO", "RECHAZADO", "CANCELADO"], aprobacion: ["PENDIENTE", "APROBADO", "RECHAZADO", "REVOCADO"], distribucion: ["SIN_ENVIAR", "PREPARADO", "ENVIADO", "FALLIDO"] }).map(([etapa, estados]) => <optgroup key={etapa} label={etapa}>{estados.map(estado => <option key={estado} value={`${etapa}:${estado}`}>{etapa}: {estado}</option>)}</optgroup>)}</select></label>
          <label>Canal<select value={filtros.canal} onChange={e => { setPagina(0); setFiltros({ ...filtros, canal: e.target.value }); }}><option value="">Todos</option>{["email", "whatsapp", "instagram", "messenger", "telegram", "enlace"].map(c => <option key={c}>{c}</option>)}</select></label>
          <label>Grupo<input value={filtros.grupo} onChange={e => { setPagina(0); setFiltros({ ...filtros, grupo: e.target.value }); }} /></label>
          {roles.length > 0 && <label>Responsable<select value={filtros.responsable_id} onChange={e => { setPagina(0); setFiltros({ ...filtros, responsable_id: e.target.value }); }}><option value="">Todos</option>{Array.from(new Map(roles.map(r => [r.usuario_id, r])).values()).map(r => <option value={r.usuario_id} key={r.usuario_id}>{r.email}</option>)}</select></label>}
          <label>Confirmado desde<input type="date" value={filtros.desde.slice(0, 10)} onChange={e => { setPagina(0); setFiltros({ ...filtros, desde: e.target.value ? `${e.target.value}T00:00:00` : "" }); }} /></label>
          <label>Confirmado hasta<input type="date" value={filtros.hasta.slice(0, 10)} onChange={e => { setPagina(0); setFiltros({ ...filtros, hasta: e.target.value ? `${e.target.value}T23:59:59` : "" }); }} /></label>
          <label>Registros<select value={filtros.activo} onChange={e => { setPagina(0); setFiltros({ ...filtros, activo: e.target.value }); }}><option value="true">Activos</option><option value="false">Bajas logicas</option></select></label>
          <button className="secondary-button">Buscar</button>
        </form>
        {tiene("distribuir") && <div className="invitados-acciones"><select aria-label="Canal para distribuir" value={canal} onChange={e => setCanal(e.target.value)}>{(acceso.config.canales || []).map(c => <option key={c}>{c}</option>)}</select>
          <select aria-label="Tipo de envio" value={tipo} onChange={e => setTipo(e.target.value)}><option value="invitacion">Invitacion inicial</option>{tiene("aprobar") && <option value="qr">Credencial aprobada</option>}</select>
          <button className="action-button" disabled={ocupado || !seleccion.length} onClick={() => void compartir()}>Enviar / Reenviar seleccion ({seleccion.length})</button></div>}
        <div className="admin-table-wrap"><table className="invitados-tabla"><thead><tr><th>Seleccion</th><th>Invitado / grupo</th><th>RSVP / aprobacion</th><th>Cupos</th><th>Distribucion</th><th>Acciones</th></tr></thead><tbody>
          {lista.map(i => <tr key={i.id}><td><input aria-label={`Seleccionar ${i.nombre}`} type="checkbox" checked={seleccion.includes(i.id)} onChange={e => setSeleccion(e.target.checked ? [...seleccion, i.id].slice(0, 50) : seleccion.filter(id => id !== i.id))} /></td>
            <td><strong>{i.nombre} {i.apellido}</strong><small>{i.grupo || "Individual"}</small><small>{[i.email, i.telefono, i.whatsapp && `WhatsApp: ${i.whatsapp}`, i.instagram && `Instagram: ${i.instagram}`, i.facebook && `Facebook: ${i.facebook}`, i.telegram && `Telegram: ${i.telegram}`, i.otro_contacto].filter(Boolean).join(" | ") || "Sin contacto digital"}</small>{i.nombres_menores?.length > 0 && <details><summary>Menores ({i.menores})</summary>{i.nombres_menores.join(", ")}</details>}</td>
            <td>{i.rsvp}<small>{i.aprobacion}</small></td><td>Maximo: {i.cantidad_permitida}<small>Solicitados: {i.solicitados}</small><small>Aprobados: {i.cupo_aprobado}</small><small>Ingresaron: {i.ingresados}</small></td>
            <td>{i.distribucion === "PREPARADO" ? "Pendiente de envio manual" : i.distribucion}<small>{i.canal}</small></td><td><div className="invitados-acciones">
              {tiene("editar_invitados") && <><button className="secondary-button" onClick={() => editar(i)}>Editar</button><button className="secondary-button" disabled={ocupado} onClick={() => { if (window.confirm(`${i.activo ? "Dar de baja" : "Reactivar"} a ${i.nombre} ${i.apellido}?`)) void ejecutar(() => api.put(`${base}/lista/${i.id}`, { nombre: i.nombre, apellido: i.apellido, email: i.email, telefono: i.telefono, instagram: i.instagram, whatsapp: i.whatsapp, facebook: i.facebook, telegram: i.telegram, otro_contacto: i.otro_contacto, grupo: i.grupo, responsable_id: i.responsable_id, cantidad_permitida: i.cantidad_permitida, activo: !i.activo }), i.activo ? "Invitado dado de baja." : "Invitado reactivado."); }}>{i.activo ? "Dar de baja" : "Reactivar"}</button></>}
              {tiene("confirmar_asistido") && <button className="secondary-button" onClick={() => { setRsvp(i); setAdultos(i.adultos || 1); setMenores(i.nombres_menores?.join("\n") || ""); }}>Confirmar asistido</button>}
              {tiene("aprobar") && <button className="secondary-button" onClick={() => { setAprobar(i); setCupo(i.solicitados || 1); }}>Aprobacion / QR</button>}
              {tiene("distribuir") && <button className="action-button" disabled={ocupado} onClick={() => void compartir([i.id], `${["PREPARADO", "ENVIADO"].includes(i.distribucion) ? "Reenviar" : "Enviar"} invitacion a ${i.nombre}`)}>{["PREPARADO", "ENVIADO"].includes(i.distribucion) ? "Reenviar invitacion" : "Enviar invitacion"}</button>}
              {tiene("distribuir") && <details><summary>Opciones avanzadas del enlace</summary><p>Para repetir la invitacion usa Reenviar. Invalidar el enlace impide usar el anterior.</p><button className="secondary-button" disabled={ocupado} onClick={() => { if (window.confirm("El enlace anterior dejara de funcionar. Invalidarlo y crear uno nuevo? Para repetir un envio usa Reenviar invitacion.")) void ejecutar(() => api.post(`${base}/lista/${i.id}/credencial/enlace/regenerar`), "Enlace anterior invalidado. Usa Enviar o Reenviar invitacion para compartir el nuevo."); }}>Invalidar enlace anterior</button></details>}
              {tiene("ver_invitados") && <button className="secondary-button" onClick={() => void ejecutar(async () => setHistorial((await api.get(`${base}/historial/${i.id}`)).data), "Historial consultado.")}>Historial</button>}
            </div></td></tr>)}
          {!lista.length && <tr><td colSpan={6}>No hay invitados para estos filtros.</td></tr>}
        </tbody></table></div>
        <div className="admin-pagination"><span>{total} invitados</span><button className="secondary-button" disabled={pagina === 0} onClick={() => { setSeleccion([]); setPagina(pagina - 1); }}>Anterior</button><span>Pagina {pagina + 1}</span><button className="secondary-button" disabled={(pagina + 1) * 25 >= total} onClick={() => { setSeleccion([]); setPagina(pagina + 1); }}>Siguiente</button></div>
      </section>
      {ventanaEnvio && <Ventana titulo={ventanaEnvio} alCerrar={() => { if (!ocupado) setVentanaEnvio(null); }}>
        <section className="invitacion-envio"><p>Foto de la invitacion, mensaje y enlace personal de confirmacion. Reenviar conserva el mismo enlace mientras siga vigente.</p>
        {avisoUI}
        {ocupado && !compartidos.length && <p role="status">Cargando invitacion...</p>}
        {compartidos.map((c, n) => <article key={n}>
        {c.destinatario && <h3>{c.destinatario}</h3>}
        <strong>{c.estado === "PREPARADO" ? "Pendiente de envio manual" : c.estado}</strong><p>{c.detalle}</p>
        {c.telefono_destino && <p>WhatsApp de destino: <strong>{c.telefono_destino}</strong></p>}
        {archivoPortada && c.mensaje && navigator.canShare?.({ files: [archivoPortada] }) && <div className="invitacion-envio-principal">
          <button className="action-button" disabled={ocupado} onClick={() => void compartirPortada(c)}>{ventanaEnvio.startsWith("Reenviar") ? "Reenviar foto y texto" : "Enviar foto y texto"}</button>
          <p>Selecciona WhatsApp y el contacto {c.destinatario}. Completa el envio dentro de WhatsApp. El selector no elige automaticamente el destinatario.</p>
        </div>}
        {c.mensaje && c.canal !== "email" && !(archivoPortada && navigator.canShare?.({ files: [archivoPortada] })) && <div className="invitacion-envio-pasos">
          <h4>Enviar foto y texto desde este navegador</h4>
          <p>Descarga la foto, copia el texto con el enlace y adjuntalos en el chat. Abrir el chat por si solo carga el texto; la foto se adjunta en WhatsApp.</p>
          <div className="invitados-acciones">
            {c.portada_url && <button className="secondary-button" disabled={ocupado} onClick={() => void ejecutar(() => descargarArchivo(base + "/portada.jpg", "invitacion.jpg"), "Foto descargada. Adjuntala en el chat de WhatsApp.")}>1. Descargar foto</button>}
            <button className="secondary-button" disabled={ocupado} onClick={() => void ejecutar(() => navigator.clipboard.writeText(textoInvitacion(c)), "Texto y enlace copiados. Pegalos junto a la foto en WhatsApp.")}>2. Copiar texto y enlace</button>
            {c.url_canal && <a className="action-button" href={c.canal === "whatsapp" ? enlaceWhatsApp(c) : c.url_canal} target="_blank" rel="noopener noreferrer">{c.canal === "whatsapp" ? `3. Abrir WhatsApp para ${c.destinatario || "este invitado"}` : "3. Abrir canal"}</a>}
          </div>
          <p>Por ultimo, pulsa Enviar dentro de la aplicacion. Eventos no confirma la entrega del mensaje.</p>
        </div>}
        {c.portada_url && (c.enlace ? <a href={c.enlace} target="_blank" rel="noopener noreferrer" aria-label="Abrir confirmacion desde la foto"><img className="invitacion-portada-compartir" src={c.portada_url} alt="Portada de la invitacion para compartir" /></a> : <img className="invitacion-portada-compartir" src={c.portada_url} alt="Portada de la invitacion para compartir" />)}
        {c.mensaje && <label>Texto de la invitacion<textarea rows={6} value={c.mensaje} aria-label={`Texto para ${c.destinatario || "el invitado"}`}
          onChange={e => setCompartidos(actual => actual.map((r, indice) => indice === n ? { ...r, mensaje: e.target.value } : r))} /></label>}
        {c.enlace && <p>Presiona <a href={c.enlace} target="_blank" rel="noopener noreferrer">aquí</a> para confirmar.</p>}
        {archivoPortada && c.mensaje && navigator.canShare?.({ files: [archivoPortada] }) && <p><button className="secondary-button" disabled={ocupado} onClick={() => void ejecutar(() => navigator.clipboard.writeText(textoInvitacion(c)), "Texto y enlace copiados.")}>Copiar texto y enlace</button> Si WhatsApp omite el texto al compartir la foto, pegalo en el chat.</p>}
        </article>)}</section>
      </Ventana>}
    </>}
    {informe && <section className="invitados-panel"><h2>Resultado de la importacion</h2><p>Importados: {informe.importados}. Actualizados: {informe.actualizados}. Omitidos: {informe.omitidos}. Rechazados: {informe.rechazados.length}.</p>{informe.rechazados.map(f => <p key={f.fila}>Fila {f.fila}: {f.error}</p>)}</section>}
    {editor && <Ventana titulo={editor === "nuevo" ? "Agregar invitado o grupo" : "Editar invitado"} alCerrar={() => { if (!ocupado) setEditor(null); }}><form className="invitados-form" onSubmit={guardar}>
      <button type="button" className="secondary-button" disabled={ocupado} onClick={() => void elegirContacto()}>Elegir contacto del telefono</button>
      {([['nombre', 'Nombre'], ['apellido', 'Apellido'], ['email', 'Email (opcional)'], ['telefono', 'Telefono (opcional)'], ['whatsapp', 'WhatsApp (numero con codigo de pais)'], ['instagram', 'Instagram (usuario o enlace)'], ['facebook', 'Facebook / Messenger (usuario o enlace)'], ['telegram', 'Telegram (usuario o telefono)'], ['otro_contacto', 'Otro contacto (opcional)'], ['grupo', 'Grupo familiar']] as const).map(([k, label]) => <label key={k}>{label}<input required={k === "nombre"} type={k === "email" ? "email" : "text"} value={form[k]} onChange={e => setForm({ ...form, [k]: e.target.value })} /></label>)}
      <p>Podes copiar el numero, usuario o enlace del contacto desde WhatsApp, Facebook, Instagram, Telegram u otra aplicacion. Los contactos son opcionales; no hace falta email para dar de alta un invitado.</p>
      <label>Cupo maximo, incluyendo titular<input type="number" min={1} max={1000} required value={form.cantidad_permitida} onChange={e => setForm({ ...form, cantidad_permitida: Number(e.target.value) })} /></label>
      {tiene("roles") && <label>Responsable<select value={form.responsable_id} onChange={e => setForm({ ...form, responsable_id: Number(e.target.value) })}>{Array.from(new Map([...roles, { usuario_id: acceso!.usuario_id, email: "Mi cuenta" }].map(r => [r.usuario_id, r])).values()).map(r => <option value={r.usuario_id} key={r.usuario_id}>{r.email}</option>)}</select></label>}
      <label><input type="checkbox" checked={form.activo} onChange={e => setForm({ ...form, activo: e.target.checked })} /> Invitacion activa (desmarcar para baja logica)</label>
      {avisoUI}<div className="invitados-acciones"><button className="secondary-button" type="button" disabled={ocupado} onClick={() => setEditor(null)}>Cancelar</button><button className="action-button" disabled={ocupado}>Guardar</button></div>
    </form></Ventana>}
    {rsvp && <Ventana titulo={`Confirmacion asistida: ${rsvp.nombre}`} alCerrar={() => { if (!ocupado) setRsvp(null); }}><form className="invitados-form" onSubmit={e => { e.preventDefault(); void ejecutar(async () => { await api.post(`${base}/lista/${rsvp.id}/rsvp`, { asiste: true, adultos, menores: menores.split("\n").map(n => n.trim()).filter(Boolean) }); setRsvp(null); }); }}>
      <p>El titular cuenta dentro del total. Maximo: {rsvp.cantidad_permitida}.</p><label>Adultos, incluido titular si es adulto<input type="number" min={0} max={rsvp.cantidad_permitida} value={adultos} onChange={e => setAdultos(Number(e.target.value))} /></label><label>Nombre de cada menor (uno por linea)<textarea value={menores} onChange={e => setMenores(e.target.value)} /></label>{avisoUI}
      <button className="action-button" disabled={ocupado}>Guardar confirmacion</button><button className="secondary-button" type="button" disabled={ocupado} onClick={() => void ejecutar(async () => { await api.post(`${base}/lista/${rsvp.id}/rsvp`, { asiste: false, adultos: 0, menores: [] }); setRsvp(null); })}>Rechazar invitacion</button>
    </form></Ventana>}
    {aprobar && <Ventana titulo={`Aprobacion: ${aprobar.nombre}`} alCerrar={() => { if (!ocupado) setAprobar(null); }}><div className="invitados-form"><p>Solicitados: {aprobar.solicitados}. Ingresados: {aprobar.ingresados}.</p><label>Cupo final aprobado<input type="number" min={1} max={aprobar.solicitados} value={cupo} onChange={e => setCupo(Number(e.target.value))} /></label>{avisoUI}
      {['APROBADO', 'RECHAZADO', 'REVOCADO'].map(estado => <button className="secondary-button" key={estado} disabled={ocupado} onClick={() => void ejecutar(async () => { await api.post(`${base}/lista/${aprobar.id}/aprobar`, { estado, cupo: estado === "APROBADO" ? cupo : 0 }); setAprobar(null); })}>{estado === "APROBADO" ? "Aprobar y habilitar QR" : estado === "RECHAZADO" ? "Rechazar solicitud" : "Revocar aprobacion"}</button>)}
      <button className="secondary-button" disabled={ocupado} onClick={() => void ejecutar(() => api.post(`${base}/lista/${aprobar.id}/credencial/qr/regenerar`), "QR regenerado. El anterior ya no funciona.")}>Regenerar QR aprobado</button>
      <button className="secondary-button" disabled={ocupado} onClick={() => void ejecutar(() => descargarArchivo(`${base}/lista/${aprobar.id}/qr.png`, "credencial.png"), "Credencial descargada.")}>Descargar QR aprobado</button>
    </div></Ventana>}
    {preview && <Ventana titulo="Vista previa de importacion" alCerrar={() => { if (!ocupado) setPreview(null); }}><p>Revisa los resultados antes de confirmar. No se eliminan confirmaciones.</p><div className="admin-table-wrap"><table className="invitados-tabla"><thead><tr><th>Fila</th><th>Invitado</th><th>Resultado previsto</th></tr></thead><tbody>{preview.filas.map(f => <tr key={f.fila}><td>{f.fila}</td><td>{f.datos?.nombre} {f.datos?.apellido}</td><td>{f.error || f.accion}</td></tr>)}</tbody></table></div>{avisoUI}<button className="action-button" disabled={ocupado} onClick={() => void ejecutar(async () => { const r = await api.post(`${base}/importar/${preview.token}`); setPreview(null); setInforme(r.data); })}>Confirmar importacion</button><button className="secondary-button" disabled={ocupado} onClick={() => setPreview(null)}>Cancelar</button></Ventana>}
    {historial && <Ventana titulo="Historial de la invitacion" alCerrar={() => setHistorial(null)}><div className="invitados-historial"><h3>Movimientos</h3>{historial.auditoria.map((a, n) => <article key={n}><strong>{a.accion.replace(/_/g, " ")}</strong><p>{new Date(a.fecha).toLocaleString("es-AR")} · {a.actor || (a.actor_id ? "Usuario autorizado" : "Invitado")}</p>{Object.entries(a.datos).filter(([k]) => ["cantidad", "estado", "cupo", "motivo", "canal", "adultos", "menores"].includes(k)).map(([k, v]) => <span key={k}>{k}: {String(v)}. </span>)}</article>)}<h3>Distribucion</h3>{historial.distribuciones.map((d, n) => <p key={n}>{new Date(d.fecha).toLocaleString("es-AR")} · {d.canal} · {d.estado}. {d.detalle}</p>)}</div></Ventana>}
  </main>;
}
