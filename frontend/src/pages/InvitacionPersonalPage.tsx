import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { EventPublicPage } from "./EventPublicPage";
import { errorMensaje } from "./InvitadosPage";

type Portal = { validado: boolean; validacion: string; requiere_pin?: boolean; sesion?: string; qr?: string | null;
  nombre?: string; apellido?: string; grupo?: string; cantidad_permitida?: number; adultos?: number; nombres_menores?: string[];
  solicitados?: number; cupo_aprobado?: number; ingresados?: number; rsvp?: string; aprobacion?: string; puede_modificar?: boolean; correo_qr?: string };

export function InvitacionPersonalPage() {
  const { slug, token } = useParams();
  const base = `/invitados/${slug}/portal`;
  const clave = `invitacion-${slug}-${token}`;
  const [sesion, setSesion] = useState(() => { try { return sessionStorage.getItem(clave); } catch { return null; } });
  const [revision, setRevision] = useState(0);
  const [portal, setPortal] = useState<Portal | null>(null);
  const [email, setEmail] = useState(""); const [codigo, setCodigo] = useState(""); const [pin, setPin] = useState("");
  const [asiste, setAsiste] = useState(true); const [adultos, setAdultos] = useState(1); const [menores, setMenores] = useState("");
  const [error, setError] = useState<string | null>(null); const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false); const [qr, setQr] = useState<string | null>(null);
  function recibir(data: Portal) {
    setPortal(data);
    if (data.sesion) { setSesion(data.sesion); try { sessionStorage.setItem(clave, data.sesion); } catch { /* sin almacenamiento */ } }
    if (data.validado) { setAdultos(data.adultos || 1); setMenores(data.nombres_menores?.join("\n") || ""); setAsiste(!["RECHAZADO", "CANCELADO"].includes(data.rsvp || "")); }
  }
  useEffect(() => {
    let activo = true;
    api.post<Portal>(base, { token, sesion }).then(r => { if (activo) recibir(r.data); }).catch(err => { if (activo) setError(errorMensaje(err)); });
    return () => { activo = false; };
    // La sesion devuelta se conserva para los siguientes pedidos sin volver a iniciar el efecto.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, token, revision]);
  useEffect(() => {
    let activo = true; let url: string | null = null;
    setQr(null);
    if (portal?.qr) api.post(base + "/qr.png", { token, sesion }, { responseType: "blob" }).then(r => {
      if (!activo) return; url = URL.createObjectURL(r.data); setQr(url);
    }).catch(err => { if (activo) setError(errorMensaje(err)); });
    return () => { activo = false; if (url) URL.revokeObjectURL(url); };
  }, [base, token, sesion, portal?.qr]);

  async function accion(ruta: string, datos: object, mensaje?: string) {
    setOcupado(true); setError(null); setAviso(null);
    try { const { data } = await api.post(base + ruta, { token, sesion, ...datos }); if (data.validado !== undefined) recibir(data); setAviso(data.correo_qr === "enviado" ? "Tu asistencia esta confirmada. Enviamos tu invitacion con el QR al correo registrado." : data.correo_qr === "fallido" ? "Tu respuesta fue guardada, pero no se pudo enviar el QR por correo. Podes descargarlo aqui o volver a guardar para reintentar." : mensaje || data.message); }
    catch (err) { setError(errorMensaje(err)); }
    finally { setOcupado(false); }
  }
  function confirmar(e: FormEvent) {
    e.preventDefault(); void accion("/rsvp", { rsvp: { asiste, adultos: asiste ? adultos : 0, menores: asiste ? menores.split("\n").map(v => v.trim()).filter(Boolean) : [] } }, "Tu respuesta fue guardada. Revisa el estado de aprobacion.");
  }
  return <>
    <div className="invitacion-personal-aviso"><a href="#mi-confirmacion">Ver mi invitacion y confirmar asistencia</a><span>No necesitas una cuenta de Google.</span></div>
    <EventPublicPage alCambiarSesion={() => { setSesion(null); setRevision(v => v + 1); }} />
    <section id="mi-confirmacion" className="portal-invitado" aria-labelledby="mi-confirmacion-titulo">
      <h2 id="mi-confirmacion-titulo">Ingresar y confirmar mi invitacion</h2>
      {error && <p role="alert" className="form-error">{error}</p>}{aviso && <p role="status" className="success-inline">{aviso}</p>}
      {!portal && !error && <p>Cargando invitacion...</p>}
      {portal && !portal.validado && <div className="invitados-form">
        {portal.validacion === "telefono" ? <p>La validacion telefonica requiere un proveedor oficial. Contacta al organizador para completar la confirmacion de forma asistida.</p> : <>
          <p>{portal.validacion === "email" ? "Si ya iniciaste sesion con el correo autorizado, podes confirmar directamente. Tambien podes validar tu correo con un codigo." : "Ingresa el codigo privado que te compartio el organizador."}</p>
          {portal.validacion === "email" && <><label>Email autorizado<input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" /></label><button className="secondary-button" disabled={ocupado || !email} onClick={() => void accion("/codigo", { email })}>Solicitar codigo por email</button><label>Codigo temporal<input inputMode="numeric" autoComplete="one-time-code" value={codigo} onChange={e => setCodigo(e.target.value)} maxLength={6} /></label></>}
          {portal.requiere_pin && <label>Codigo privado del evento<input type="password" value={pin} onChange={e => setPin(e.target.value)} /></label>}
          <button className="action-button" disabled={ocupado} onClick={() => void accion("/validar", { email: email || null, codigo: codigo || null, pin: pin || null })}>Ingresar a mi invitacion</button>
        </>}
      </div>}
      {portal?.validado && <>
        <h3>Hola {portal.nombre} {portal.apellido}</h3>{portal.grupo && <p>Grupo: {portal.grupo}</p>}
        <p>Cupo maximo: <strong>{portal.cantidad_permitida}</strong>. El titular esta incluido en el total.</p>
        {portal.validacion === "enlace" && <p>Este acceso acredita que tenes la invitacion privada. No compartas el enlace en espacios publicos.</p>}
        <div className="invitados-kpis"><article><span>Solicitados</span><strong>{portal.solicitados}</strong></article><article><span>Aprobados</span><strong>{portal.cupo_aprobado}</strong></article><article><span>Ingresados</span><strong>{portal.ingresados}</strong></article></div>
        <p>Respuesta: <strong>{portal.rsvp}</strong>. Aprobacion: <strong>{portal.aprobacion}</strong>.</p>
        {portal.puede_modificar ? <form className="invitados-form" onSubmit={confirmar}>
          <label>Asistencia<select value={asiste ? "si" : "no"} onChange={e => setAsiste(e.target.value === "si")}><option value="si">Voy a asistir</option><option value="no">No voy a asistir</option></select></label>
          {asiste && <><label>Adultos (incluyendo al titular si es adulto)<input type="number" min={0} max={portal.cantidad_permitida} value={adultos} onChange={e => setAdultos(Number(e.target.value))} required /></label><label>Nombre de cada menor, uno por linea<textarea value={menores} onChange={e => setMenores(e.target.value)} placeholder="Solo nombres, sin edades ni otros datos" /></label><p>Total solicitado: {adultos + menores.split("\n").filter(v => v.trim()).length} de {portal.cantidad_permitida}.</p></>}
          <button className="action-button" disabled={ocupado}>{ocupado ? "Guardando..." : "Guardar mi respuesta"}</button>
        </form> : <p>Para cambiar tu respuesta, contacta al organizador.</p>}
        {qr ? <div className="invitado-qr"><h3>Tu credencial de ingreso</h3><img src={qr} alt="QR personal de ingreso" /><a className="action-button" href={qr} download="credencial.png">Descargar QR</a><p>El QR requiere validacion en la puerta y permite ingresos parciales hasta completar el cupo aprobado.</p></div> : <p>La credencial QR se muestra despues de aprobar la asistencia. Si fue revocada, contacta al organizador.</p>}
      </>}
    </section>
  </>;
}
