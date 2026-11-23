import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useConfirmacion } from "./useConfirmacion";

type Contacto = { agasajado_id: number; cuenta: string; puede_configurar: boolean; nombre_publico: string; habilitado: boolean; email: string | null; whatsapp: string | null; publicar_email: boolean; publicar_whatsapp: boolean };
type Solicitud = { id: number; agasajado_id: number; nombre: string; apellido: string; email: string; telefono: string | null; canal: string; estado: string; requiere_revision: boolean; invitacion_id: number | null; revision_administrador: boolean; coincidencias: { id: number; nombre: string; apellido: string; misma_identidad: boolean }[] };

export function SolicitudesInvitacionPanel({ slug, alCambiar }: { slug: string; alCambiar: () => Promise<void> }) {
  const [contactos, setContactos] = useState<Contacto[]>([]);
  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([]);
  const [estado, setEstado] = useState("PENDIENTE");
  const [puedeRevisar, setPuedeRevisar] = useState(false);
  const [revisadas, setRevisadas] = useState<number[]>([]);
  const [existentes, setExistentes] = useState<Record<number, string>>({});
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const { confirmar, ventanaConfirmacion } = useConfirmacion();
  const base = `/invitados/${slug}/solicitudes`;
  const cargar = useCallback(async () => {
    const [c, s] = await Promise.all([api.get<Contacto[]>(base + "/contactos"), api.get<{ items: Solicitud[]; puede_revisar: boolean }>(base, { params: { estado } })]);
    setContactos(c.data); setSolicitudes(s.data.items); setPuedeRevisar(s.data.puede_revisar);
  }, [base, estado]);
  useEffect(() => { void cargar().catch(() => setError("No se pudieron consultar las solicitudes.")); }, [cargar]);
  async function ejecutar(accion: () => Promise<unknown>, mensaje: string) {
    setOcupado(true); setError(null); setAviso(null);
    try { await accion(); await cargar(); await alCambiar(); setAviso(mensaje); }
    catch { setError("No se pudo guardar. Revisá los permisos, las coincidencias y el estado de la invitación. Si coincide con otra lista, pedí al administrador que la revise."); }
    finally { setOcupado(false); }
  }
  function cambiarContacto(id: number, cambio: Partial<Contacto>) {
    setContactos(actual => actual.map(c => c.agasajado_id === id ? { ...c, ...cambio } : c));
  }
  async function resolver(s: Solicitud, nuevo: string) {
    if (!await confirmar(nuevo === "APROBADA" ? "Se creará o reutilizará una invitación pendiente de confirmación. Esta acción no confirma asistencia ni genera un QR." : "¿Rechazar esta solicitud de invitación?", "Revisar solicitud", nuevo === "APROBADA" ? "Aprobar solicitud" : "Rechazar solicitud")) return;
    void ejecutar(() => api.post(`${base}/${s.id}/resolver`, {
      estado: nuevo, confirmar_revision: revisadas.includes(s.id),
      ...(existentes[s.id] ? { invitacion_id: Number(existentes[s.id]) } : {}),
    }), nuevo === "APROBADA" ? "Solicitud aprobada. Podés enviar la invitación desde la lista de invitados. La asistencia sigue pendiente." : "Solicitud rechazada.");
  }
  return <section className="invitados-panel solicitudes-panel">
    <h2>Solicitudes de invitación</h2>
    <details><summary>Nombre y contactos públicos de los agasajados</summary>
      <p>Solo se publicarán los datos que habilites aquí. No se usan automáticamente los contactos privados de la cuenta.</p>
      {contactos.map(c => <form className="solicitud-form" key={c.agasajado_id} onSubmit={e => {
        e.preventDefault(); const { agasajado_id, cuenta, puede_configurar, ...datos } = c;
        void ejecutar(() => api.put(`${base}/contactos/${agasajado_id}`, { ...datos, email: datos.email?.trim() || null, whatsapp: datos.whatsapp?.trim() || null }), "Configuración pública guardada.");
      }}><fieldset disabled={ocupado || !c.puede_configurar}>
        <legend>{c.cuenta}</legend>
        <label><input type="checkbox" checked={c.habilitado} onChange={e => cambiarContacto(c.agasajado_id, { habilitado: e.target.checked })} /> Habilitar nombre público y recepción de solicitudes</label>
        <label>Nombre público<input required={c.habilitado} maxLength={160} value={c.nombre_publico} onChange={e => cambiarContacto(c.agasajado_id, { nombre_publico: e.target.value })} /></label>
        <label>WhatsApp público<input type="tel" required={c.publicar_whatsapp} maxLength={60} value={c.whatsapp || ""} onChange={e => cambiarContacto(c.agasajado_id, { whatsapp: e.target.value })} /></label>
        <label><input type="checkbox" checked={c.publicar_whatsapp} onChange={e => cambiarContacto(c.agasajado_id, { publicar_whatsapp: e.target.checked })} /> Autorizar publicación del WhatsApp</label>
        <label>Email público<input type="email" required={c.publicar_email} value={c.email || ""} onChange={e => cambiarContacto(c.agasajado_id, { email: e.target.value })} /></label>
        <label><input type="checkbox" checked={c.publicar_email} onChange={e => cambiarContacto(c.agasajado_id, { publicar_email: e.target.checked })} /> Autorizar publicación del email</label>
        {c.puede_configurar && <button className="secondary-button" disabled={ocupado}>Guardar contacto público</button>}
      </fieldset></form>)}
      {!contactos.length && <p>El administrador debe asignar un agasajado al evento antes de habilitar solicitudes.</p>}
    </details>
    <label>Estado de solicitudes<select value={estado} disabled={ocupado} onChange={e => setEstado(e.target.value)}><option value="PENDIENTE">Pendiente</option><option value="APROBADA">Aprobada</option><option value="RECHAZADA">Rechazada</option><option value="">Todas</option></select></label>
    {!solicitudes.length && <p>No hay solicitudes en este estado.</p>}
    {solicitudes.map(s => <article key={s.id} className="solicitud-recibida">
      <h3>{s.nombre} {s.apellido}</h3><p>{s.estado === "PENDIENTE" ? "Pendiente" : s.estado === "APROBADA" ? "Aprobada" : "Rechazada"}</p>
      <p>Dirigida a: {contactos.find(c => c.agasajado_id === s.agasajado_id)?.nombre_publico || contactos.find(c => c.agasajado_id === s.agasajado_id)?.cuenta || "Agasajado del evento"}</p>
      <p className="invitacion-correo">Correo verificado: {s.email}</p>
      <p>Medio elegido: {s.canal === "whatsapp" ? "WhatsApp" : "Email"}{s.telefono ? ` · ${s.telefono}` : ""}</p>
      {s.canal === "whatsapp" && <p>Revisá el número proporcionado antes de enviar una invitación. La confirmación requiere el correo verificado.</p>}
      {s.revision_administrador && <p>Hay coincidencias en otra lista. Consultá al administrador para revisarlas.</p>}
      {!!s.coincidencias.length && <><p>Posibles coincidencias en invitados:</p><ul>{s.coincidencias.map(i => <li key={i.id}>{i.nombre} {i.apellido}{i.misma_identidad ? " — mismo correo verificado" : " — revisar, podría ser otra persona"}</li>)}</ul></>}
      {s.estado === "PENDIENTE" && puedeRevisar && <>
        {s.coincidencias.some(i => i.misma_identidad) && <label>Reutilizar invitación<select value={existentes[s.id] || ""} onChange={e => setExistentes({ ...existentes, [s.id]: e.target.value })}><option value="">Resolver por correo verificado</option>{s.coincidencias.filter(i => i.misma_identidad).map(i => <option key={i.id} value={i.id}>{i.nombre} {i.apellido} (#{i.id})</option>)}</select></label>}
        {s.requiere_revision && <label><input type="checkbox" checked={revisadas.includes(s.id)} onChange={e => setRevisadas(actual => e.target.checked ? [...actual, s.id] : actual.filter(id => id !== s.id))} /> Revisé las coincidencias y los datos de contacto</label>}
        <div className="solicitud-contactos"><button className="action-button" type="button" disabled={ocupado || (s.requiere_revision && !revisadas.includes(s.id))} onClick={() => void resolver(s, "APROBADA")}>Aprobar solicitud</button><button className="secondary-button" type="button" disabled={ocupado} onClick={() => void resolver(s, "RECHAZADA")}>Rechazar solicitud</button></div>
      </>}
      {s.estado === "APROBADA" && <p>Invitación registrada. Usá Enviar / Reenviar en la lista de invitados para comunicarla.</p>}
    </article>)}
    {error && <p className="form-error" role="alert">{error}</p>}{aviso && <p role="status">{aviso}</p>}
    {ventanaConfirmacion}
  </section>;
}
