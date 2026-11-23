import axios from "axios";
import { FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";

type Agasajado = { id: number; nombre: string; whatsapp_url: string | null; email_url: string | null };

export function SolicitarInvitacion({ slug }: { slug: string }) {
  const [agasajados, setAgasajados] = useState<Agasajado[]>([]);
  const [email, setEmail] = useState("");
  const [elegido, setElegido] = useState("");
  const [nombre, setNombre] = useState("");
  const [apellido, setApellido] = useState("");
  const [canal, setCanal] = useState("email");
  const [telefono, setTelefono] = useState("");
  const [cargando, setCargando] = useState(true);
  const [falloCarga, setFalloCarga] = useState(false);
  const [revision, setRevision] = useState(0);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviada, setEnviada] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setCargando(true); setFalloCarga(false);
    api.get<{ agasajados: Agasajado[]; email_verificado: string }>(`/invitados/${slug}/solicitudes/opciones`, { signal: controller.signal })
      .then(({ data }) => {
        setAgasajados(data.agasajados); setEmail(data.email_verificado);
        if (data.agasajados.length === 1) setElegido(String(data.agasajados[0].id));
      }).catch(err => {
        if (!controller.signal.aborted && !(axios.isAxiosError(err) && err.response?.status === 404)) setFalloCarga(true);
      })
      .finally(() => { if (!controller.signal.aborted) setCargando(false); });
    return () => controller.abort();
  }, [slug, revision]);
  const contacto = agasajados.find(a => String(a.id) === elegido);
  async function enviar(event: FormEvent) {
    event.preventDefault();
    if (ocupado) return;
    if (!contacto || !nombre.trim() || !apellido.trim()) {
      setError("Completá nombre, apellido y el agasajado al que conocés.");
      return;
    }
    setOcupado(true); setError(null);
    try {
      await api.post(`/invitados/${slug}/solicitudes`, {
        nombre: nombre.trim(), apellido: apellido.trim(), agasajado_id: contacto.id, canal,
        ...(canal === "email" ? { email } : { telefono: telefono.trim() }),
      });
      setEnviada(true);
    } catch {
      setError("No pudimos registrar la solicitud. Revisá tus datos y el número internacional si elegiste WhatsApp, o intentá nuevamente.");
    } finally { setOcupado(false); }
  }
  if (cargando) return <p role="status">Consultando medios de contacto...</p>;
  if (falloCarga) return <div><p>No pudimos consultar los medios de contacto. Intentá nuevamente.</p><button className="secondary-button" onClick={() => setRevision(n => n + 1)}>Reintentar</button></div>;
  if (!agasajados.length) return <p>Solicitá tu invitación por los canales habituales del evento.</p>;
  if (enviada) return <p role="status">Recibimos tu solicitud. El agasajado podrá revisarla y enviarte una invitación.</p>;
  return <div className="solicitud-publica">
    <p>Si creés que se trata de un error, podés comunicarte con el agasajado para solicitar tu invitación.</p>
    <form className="solicitud-form" onSubmit={e => void enviar(e)}>
      <label>Agasajado al que conocés<select required value={elegido} disabled={ocupado} onChange={e => setElegido(e.target.value)}>
        <option value="">Seleccioná un agasajado</option>
        {agasajados.map(a => <option value={a.id} key={a.id}>{a.nombre}</option>)}
      </select></label>
      {contacto && <div className="solicitud-contactos">
        {contacto.whatsapp_url && <a className="secondary-button" href={contacto.whatsapp_url} target="_blank" rel="noopener noreferrer">WhatsApp</a>}
        {contacto.email_url && <a className="secondary-button" href={contacto.email_url}>Enviar email</a>}
        {!contacto.whatsapp_url && !contacto.email_url && <p>Podés enviar la solicitud aquí o comunicarte por los canales habituales del evento.</p>}
      </div>}
      <h3>Solicitar invitación</h3>
      <label>Nombre<input required maxLength={160} autoComplete="given-name" value={nombre} disabled={ocupado} onChange={e => setNombre(e.target.value)} /></label>
      <label>Apellido<input required maxLength={160} autoComplete="family-name" value={apellido} disabled={ocupado} onChange={e => setApellido(e.target.value)} /></label>
      <label>Medio de contacto<select value={canal} disabled={ocupado} onChange={e => setCanal(e.target.value)}><option value="email">Email</option><option value="whatsapp">WhatsApp</option></select></label>
      {canal === "whatsapp" ? <label>WhatsApp con código de país<input required type="tel" autoComplete="tel" maxLength={60} placeholder="+54 9 2966 123456" value={telefono} disabled={ocupado} onChange={e => setTelefono(e.target.value)} /></label>
        : <label>Correo verificado de tu cuenta<input type="email" value={email} required readOnly /></label>}
      {canal === "whatsapp" && <p>Tu solicitud quedará identificada con el correo verificado de tu cuenta: <span className="invitacion-correo">{email}</span>.</p>}
      {error && <p role="alert">{error}</p>}
      <button className="action-button" disabled={ocupado || !contacto}>{ocupado ? "Enviando..." : "Enviar solicitud"}</button>
    </form>
  </div>;
}
