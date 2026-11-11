import axios from "axios";
import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { Ventana } from "./Ventana";
import { useConfirmacion } from "./useConfirmacion";

type Cuenta = { id: number; email: string; nombre: string | null; activo: boolean; es_superadministrador: boolean };
type Asignada = Cuenta & { es_propietario: boolean; roles: string[]; acceso_efectivo: boolean };
type Asignaciones = { propietario_id: number; items: Asignada[] };
const ROLES: Record<string, string> = {
  ADMIN_EVENTO: "Administrador del evento", AGASAJADO: "Agasajado",
  GESTOR_INVITADOS: "Gestor de invitados", CONTROL_INGRESO: "Control de ingreso",
  ENCARGADO: "Encargado de editar el evento", PROPIETARIO: "Propietario",
};
function mensajeError(err: unknown) {
  const detalle = axios.isAxiosError(err) ? err.response?.data?.detail : null;
  return typeof detalle === "string" ? detalle : "No se pudo completar la operacion. Intenta nuevamente.";
}

export function UsuariosEventoAdmin({ evento, alCerrar, alCambiar }: {
  evento: { id: number; nombre: string }; alCerrar: () => void; alCambiar: () => void;
}) {
  const [datos, setDatos] = useState<Asignaciones | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [filtro, setFiltro] = useState("");
  const [pagina, setPagina] = useState(0);
  const [cuentas, setCuentas] = useState<{ items: Cuenta[]; total: number }>({ items: [], total: 0 });
  const [buscando, setBuscando] = useState(true);
  const [seleccionada, setSeleccionada] = useState<Cuenta | null>(null);
  const [rol, setRol] = useState("AGASAJADO");
  const { confirmar, ventanaConfirmacion } = useConfirmacion();
  const mensajes = useRef<HTMLDivElement>(null);
  const base = `/administracion/eventos/${evento.id}/usuarios`;

  useEffect(() => {
    if (error || aviso) mensajes.current?.scrollIntoView({ block: "nearest" });
  }, [error, aviso]);

  useEffect(() => {
    const abortar = new AbortController();
    api.get<Asignaciones>(base, { signal: abortar.signal }).then(r => setDatos(r.data))
      .catch(err => { if (!abortar.signal.aborted) setError(mensajeError(err)); });
    return () => abortar.abort();
  }, [base]);

  useEffect(() => {
    const abortar = new AbortController();
    setBuscando(true);
    api.get<{ items: Cuenta[]; total: number }>("/administracion/usuarios", {
      params: { q: filtro, offset: pagina * 25, limit: 25 }, signal: abortar.signal,
    }).then(r => setCuentas(r.data)).catch(err => {
      if (!abortar.signal.aborted) { setCuentas({ items: [], total: 0 }); setError(mensajeError(err)); }
    }).finally(() => { if (!abortar.signal.aborted) setBuscando(false); });
    return () => abortar.abort();
  }, [filtro, pagina]);

  async function guardar(event: FormEvent) {
    event.preventDefault();
    if (!seleccionada || ocupado || confirmando || !datos) return;
    if (rol === "PROPIETARIO") {
      setConfirmando(true);
      const aceptado = await confirmar(
        `Asignar a ${seleccionada.email} como propietario de ${evento.nombre}? El propietario anterior perdera todas sus asignaciones en este evento. Los superadministradores conservan su acceso global.`,
        "Cambiar propietario", "Cambiar propietario");
      setConfirmando(false);
      if (!aceptado) return;
    }
    setOcupado(true); setError(null); setAviso(null);
    try {
      const { data } = await api.put<Asignaciones>(`${base}/${seleccionada.id}`, { rol });
      setDatos(data); setSeleccionada(null);
      setAviso("Asignacion guardada. Los permisos ya estan vigentes."); alCambiar();
    } catch (err) { setError(mensajeError(err)); }
    finally { setOcupado(false); }
  }

  async function quitar(cuenta: Asignada) {
    if (ocupado || confirmando) return;
    setConfirmando(true);
    const aceptado = await confirmar(
      `Quitar todas las asignaciones de ${cuenta.email} en ${evento.nombre}?${cuenta.es_superadministrador ? " Conserva su acceso global de superadministrador." : " Perdera los permisos de este evento, incluso con una sesion abierta."} Sus otros sitios y su cuenta se conservan.`,
      "Quitar usuario del evento", "Quitar acceso");
    setConfirmando(false);
    if (!aceptado) return;
    setOcupado(true); setError(null); setAviso(null);
    try {
      const { data } = await api.delete<Asignaciones>(`${base}/${cuenta.id}`);
      setDatos(data); setAviso("Asignaciones quitadas de este evento."); alCambiar();
    } catch (err) { setError(mensajeError(err)); }
    finally { setOcupado(false); }
  }

  return <>
    <Ventana titulo={`Usuarios de ${evento.nombre}`} alCerrar={() => { if (!ocupado && !confirmando) alCerrar(); }}>
      <div className="admin-event-users">
        <p>Los permisos se aplican solo a este evento. Los superadministradores tienen acceso global.</p>
        <div ref={mensajes}>
          {error && <p className="form-error" role="alert">{error}</p>}
          {aviso && <p className="success-inline" role="status">{aviso}</p>}
        </div>
        {!datos && !error && <p role="status">Cargando asignaciones...</p>}
        {datos && <>
          <h3>Cuentas con asignaciones o acceso global</h3>
          <ul className="admin-assigned-users">
            {datos.items.map(cuenta => <li key={cuenta.id}>
              <div><strong>{cuenta.nombre || cuenta.email}</strong><small>{cuenta.email} · Cuenta #{cuenta.id}</small>
                <small>{cuenta.es_propietario ? "Propietario" : cuenta.roles.map(r => ROLES[r] || r).join(", ") || "Sin asignaciones"}</small>
                {cuenta.es_superadministrador && <small>Superadministrador: acceso global</small>}
                {!cuenta.acceso_efectivo && <small>Sin acceso efectivo{!cuenta.activo ? ": cuenta inactiva" : ""}</small>}
              </div>
              <button type="button" className="secondary-button" disabled={ocupado || confirmando || cuenta.es_propietario || !cuenta.roles.length}
                aria-label={`Quitar usuario ${cuenta.email}`} onClick={() => void quitar(cuenta)}>Quitar</button>
            </li>)}
          </ul>
          <p>Para quitar al propietario, selecciona otra cuenta y asignale el rol Propietario. El cambio retira las asignaciones del anterior.</p>
          <h3>Agregar usuario o asignar un rol</h3>
          <form className="admin-user-form" onSubmit={e => { e.preventDefault(); setSeleccionada(null); setPagina(0); setFiltro(busqueda.trim()); }}>
            <label>Buscar cuenta registrada<input type="search" value={busqueda} onChange={e => setBusqueda(e.target.value)} placeholder="Nombre o email" /></label>
            <button className="secondary-button" disabled={buscando || ocupado || confirmando}>Buscar cuentas</button>
          </form>
          {buscando ? <p role="status">Buscando cuentas...</p> : <>
            <div className="admin-account-select"><label htmlFor="admin-evento-cuenta">Cuenta</label><select id="admin-evento-cuenta" value={seleccionada?.id || ""} disabled={ocupado || confirmando} onChange={e => setSeleccionada(cuentas.items.find(c => c.id === Number(e.target.value)) || null)}>
              <option value="">Selecciona una cuenta</option>
              {cuentas.items.map(c => <option key={c.id} value={c.id} disabled={!c.activo}>{c.nombre ? `${c.nombre} · ` : ""}{c.email} (#{c.id}){!c.activo ? " · Inactiva" : ""}</option>)}
            </select></div>
            {!cuentas.total && <p>No hay cuentas para esta busqueda.</p>}
            {cuentas.total > 25 && <div className="admin-actions">
              <button className="secondary-button" disabled={ocupado || confirmando || pagina === 0} onClick={() => { setSeleccionada(null); setPagina(n => n - 1); }}>Anterior</button>
              <span>{pagina * 25 + 1}–{Math.min((pagina + 1) * 25, cuentas.total)} de {cuentas.total}</span>
              <button className="secondary-button" disabled={ocupado || confirmando || (pagina + 1) * 25 >= cuentas.total} onClick={() => { setSeleccionada(null); setPagina(n => n + 1); }}>Siguiente</button>
            </div>}
          </>}
          <form className="admin-user-form" onSubmit={guardar}>
            {seleccionada && <p>Cuenta seleccionada: <strong>{seleccionada.email} (#{seleccionada.id})</strong></p>}
            <div className="admin-account-select"><label htmlFor="admin-evento-rol">Rol a asignar</label><select id="admin-evento-rol" value={rol} disabled={ocupado || confirmando} onChange={e => setRol(e.target.value)}>
              {Object.entries(ROLES).map(([valor, nombre]) => <option key={valor} value={valor}>{nombre}</option>)}
            </select></div>
            <p>Agregar un rol conserva los demas permisos de la cuenta. Quitar retira todos sus roles de este evento.</p>
            <button className="action-button" disabled={!seleccionada || ocupado || confirmando || buscando}>{ocupado ? "Guardando..." : rol === "PROPIETARIO" ? "Cambiar propietario" : "Agregar usuario"}</button>
          </form>
        </>}
        <button className="secondary-button" disabled={ocupado || confirmando} onClick={alCerrar}>Cerrar</button>
      </div>
    </Ventana>
    {ventanaConfirmacion}
  </>;
}
