import axios from "axios";
import { Activity, ArrowLeft, CalendarDays, LogOut, Mail, Pencil, RefreshCw, ShieldCheck, Store, Users } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { cerrarSesion } from "../api/sesion";
import { Ventana } from "../components/Ventana";

type Usuario = { id: number; nombre: string | null; email: string; activo: boolean; es_superadministrador: boolean };
type Evento = { id: number; nombre: string; slug: string; propietario_email: string; activo: boolean; estado: string; fecha_inicio: string | null };
type Negocio = { id: number; nombre: string; slug: string; propietario_email: string; activo: boolean };
type Pagina<T> = { items: T[]; total: number };
type Resumen = {
  usuarios_total: number; usuarios_activos: number; eventos_total: number; eventos_activos: number;
  eventos_publicados: number; eventos_borrador: number; eventos_proximos: number;
  proveedores_total: number; proveedores_activos: number;
};
const TAMANO = 25;

export function AdminPage() {
  const navigate = useNavigate();
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [usuarios, setUsuarios] = useState<Pagina<Usuario>>({ items: [], total: 0 });
  const [eventos, setEventos] = useState<Pagina<Evento>>({ items: [], total: 0 });
  const [negocios, setNegocios] = useState<Pagina<Negocio>>({ items: [], total: 0 });
  const [paginaNegocios, setPaginaNegocios] = useState(0);
  const [busqueda, setBusqueda] = useState("");
  const [filtro, setFiltro] = useState("");
  const [paginaUsuarios, setPaginaUsuarios] = useState(0);
  const [paginaEventos, setPaginaEventos] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [editando, setEditando] = useState<Usuario | null>(null);
  const [nombreEdicion, setNombreEdicion] = useState("");
  const [emailEdicion, setEmailEdicion] = useState("");
  const [errorEdicion, setErrorEdicion] = useState<string | null>(null);
  const [enviandoId, setEnviandoId] = useState<number | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const [r, u, e, n] = await Promise.all([
        api.get<Resumen>("/administracion/resumen"),
        api.get<Pagina<Usuario>>("/administracion/usuarios", { params: { q: filtro, offset: paginaUsuarios * TAMANO, limit: TAMANO } }),
        api.get<Pagina<Evento>>("/administracion/eventos", { params: { q: filtro, offset: paginaEventos * TAMANO, limit: TAMANO } }),
        api.get<Pagina<Negocio>>("/administracion/proveedores", { params: { q: filtro, offset: paginaNegocios * TAMANO, limit: TAMANO } })
      ]);
      setResumen(r.data); setUsuarios(u.data); setEventos(e.data); setNegocios(n.data);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        navigate("/ingresar?destino=/administracion", { replace: true });
      } else {
        setError(axios.isAxiosError(err) && err.response?.status === 403
          ? "Esta cuenta no tiene acceso a la administracion del proyecto."
          : "No se pudo cargar el dashboard. Intenta actualizar.");
        setResumen(null);
      }
    } finally { setCargando(false); }
  }, [filtro, paginaUsuarios, paginaEventos, paginaNegocios, navigate]);

  useEffect(() => { void cargar(); }, [cargar]);

  async function cambiar(tipo: "usuarios" | "eventos", item: Usuario | Evento) {
    const nombre = "email" in item ? item.email : item.nombre;
    const accion = item.activo ? "Desactivar" : "Activar";
    if (!window.confirm(`${accion} ${nombre}?${tipo === "usuarios" && item.activo ? " Se bloqueara su acceso, incluso con una sesion abierta." : ""}`)) return;
    setGuardando(true); setError(null); setAviso(null);
    try {
      await api.patch(`/administracion/${tipo}/${item.id}`, { activo: !item.activo });
      await cargar();
      setAviso(`${nombre}: ${item.activo ? "desactivado" : "activado"}.`);
    } catch (err) {
      const detalle = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detalle === "string" ? detalle : "No se pudo guardar el cambio. Intenta nuevamente.");
    } finally { setGuardando(false); }
  }

  function editar(usuario: Usuario) {
    setEditando(usuario);
    setNombreEdicion(usuario.nombre || "");
    setEmailEdicion(usuario.email);
    setErrorEdicion(null);
    setError(null); setAviso(null);
  }

  async function guardarUsuario(event: FormEvent) {
    event.preventDefault();
    if (!editando || guardando) return;
    setGuardando(true); setErrorEdicion(null);
    try {
      const { data } = await api.put<Usuario>(`/administracion/usuarios/${editando.id}`, {
        nombre: nombreEdicion.trim() || null, email: emailEdicion.trim().toLowerCase()
      });
      setEditando(null);
      await cargar();
      setAviso(`Datos de ${data.email} guardados. Podes enviarle un nuevo enlace de ingreso.`);
    } catch (err) {
      const detalle = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setErrorEdicion(typeof detalle === "string" ? detalle : "No se pudieron guardar los datos. Revisa el nombre y el email.");
    } finally { setGuardando(false); }
  }

  async function reenviarAcceso(usuario: Usuario) {
    setGuardando(true); setEnviandoId(usuario.id); setError(null); setAviso(null);
    try {
      const { data } = await api.post<{ message: string }>(`/administracion/usuarios/${usuario.id}/reenviar-acceso`);
      setAviso(data.message);
    } catch (err) {
      const detalle = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setError(typeof detalle === "string" ? detalle : "No se pudo enviar el enlace. Intenta nuevamente.");
    } finally { setGuardando(false); setEnviandoId(null); }
  }

  function buscar(event: FormEvent) {
    event.preventDefault(); setPaginaUsuarios(0); setPaginaEventos(0); setPaginaNegocios(0); setFiltro(busqueda.trim());
  }

  const bloqueado = cargando || guardando;
  return <main className="admin-page">
    <header className="admin-header">
      <div><Link to="/" className="admin-back"><ArrowLeft size={16} /> Volver al portal</Link>
        <p className="eyebrow"><ShieldCheck size={17} /> Superadministrador</p>
        <h1>El proyecto, en numeros</h1><p>Actividad de la plataforma y gestion de usuarios y eventos.</p>
      </div>
      <div className="admin-actions">
        <button className="secondary-button" disabled={bloqueado} onClick={() => void cargar()}><RefreshCw size={16} /> Actualizar</button>
        <button className="secondary-button" onClick={() => { cerrarSesion(); navigate("/ingresar"); }}><LogOut size={16} /> Salir</button>
      </div>
    </header>
    {error && <p className="form-error" role="alert">{error}</p>}
    {aviso && <p className="success-inline" role="status">{aviso}</p>}
    {cargando && <p role="status">Actualizando informacion...</p>}
    {resumen && <>
      <section className="admin-kpis" aria-label="Indicadores del proyecto">
        <article><Users /><span>Usuarios registrados</span><strong>{resumen.usuarios_total}</strong><small>{resumen.usuarios_activos} activos · {resumen.usuarios_total - resumen.usuarios_activos} inactivos</small></article>
        <article><CalendarDays /><span>Eventos creados</span><strong>{resumen.eventos_total}</strong><small>{resumen.eventos_activos} activos · {resumen.eventos_total - resumen.eventos_activos} inactivos</small></article>
        <article><Activity /><span>Proximos eventos</span><strong>{resumen.eventos_proximos}</strong><small>Publicados, activos y con fecha futura</small></article>
        <article><Store /><span>Proveedores registrados</span><strong>{resumen.proveedores_total}</strong><small>{resumen.proveedores_activos} activos</small></article>
      </section>
      <p className="admin-context">Eventos activos: <strong>{resumen.eventos_publicados} publicados</strong> y <strong>{resumen.eventos_borrador} borradores</strong>. Los otros estados tambien se incluyen en el total de activos.</p>
      <form className="admin-search" onSubmit={buscar}>
        <label htmlFor="admin-busqueda">Buscar usuarios, eventos y negocios</label>
        <div><input id="admin-busqueda" value={busqueda} onChange={e => setBusqueda(e.target.value)} placeholder="Nombre, email o identificador del evento" type="search" />
          <button className="action-button" disabled={bloqueado}>Buscar</button></div>
      </form>
      <section className="admin-panel" aria-labelledby="admin-usuarios">
        <div className="admin-panel-heading"><div><h2 id="admin-usuarios">Usuarios</h2><p>Desactivar bloquea el ingreso y las sesiones existentes.</p></div><span>{usuarios.total} resultados</span></div>
        <div className="admin-table-wrap"><table><thead><tr><th>Cuenta</th><th>Rol</th><th>Estado</th><th>Accion</th></tr></thead><tbody>
          {usuarios.items.map(u => <tr key={u.id}><td><strong>{u.nombre || "Sin nombre"}</strong><small>{u.email}</small></td><td>{u.es_superadministrador ? "Superadministrador" : "Usuario"}</td><td><Estado activo={u.activo} /></td><td><div className="admin-user-actions">
            <button className="secondary-button" disabled={bloqueado} aria-label={`Editar cuenta ${u.email}`} onClick={() => editar(u)}><Pencil size={15} /> Editar datos</button>
            <button className="secondary-button" disabled={bloqueado || !u.activo} title={u.activo ? `Enviar enlace a ${u.email}` : "Activa la cuenta para enviarle el enlace"} onClick={() => void reenviarAcceso(u)}><Mail size={15} /> {enviandoId === u.id ? "Enviando..." : "Reenviar ingreso"}</button>
            <button className="secondary-button" disabled={bloqueado || u.es_superadministrador} title={u.es_superadministrador ? "Las cuentas de superadministrador estan protegidas" : undefined} onClick={() => void cambiar("usuarios", u)}>{u.activo ? "Desactivar" : "Activar"}</button>
          </div></td></tr>)}
          {!usuarios.items.length && <tr><td colSpan={4}>No hay usuarios para esta busqueda.</td></tr>}
        </tbody></table></div>
        <Paginacion pagina={paginaUsuarios} total={usuarios.total} bloqueado={bloqueado} cambiar={setPaginaUsuarios} />
      </section>
      <section className="admin-panel" aria-labelledby="admin-eventos">
        <div className="admin-panel-heading"><div><h2 id="admin-eventos">Eventos</h2><p>Desactivar oculta el evento. Reactivar conserva su estado de publicacion.</p></div><span>{eventos.total} resultados</span></div>
        <div className="admin-table-wrap"><table><thead><tr><th>Evento</th><th>Organizador</th><th>Publicacion</th><th>Estado</th><th>Accion</th></tr></thead><tbody>
          {eventos.items.map(e => <tr key={e.id}><td><strong>{e.nombre}</strong><small>/{e.slug}</small><small>{e.fecha_inicio ? new Date(e.fecha_inicio).toLocaleString("es-AR") : "Fecha a definir"}</small></td><td>{e.propietario_email}</td><td>{e.estado.replace(/_/g, " ")}</td><td><Estado activo={e.activo} /></td><td><div className="admin-user-actions">{e.activo && <><Link className="secondary-button" to={`/e/${e.slug}`}><Pencil size={15} /> Editar evento</Link><Link className="secondary-button" to={`/e/${e.slug}/invitados`}>Invitados</Link></>}<button className="secondary-button" disabled={bloqueado} onClick={() => void cambiar("eventos", e)}>{e.activo ? "Desactivar" : "Activar"}</button></div></td></tr>)}
          {!eventos.items.length && <tr><td colSpan={5}>No hay eventos para esta busqueda.</td></tr>}
        </tbody></table></div>
        <Paginacion pagina={paginaEventos} total={eventos.total} bloqueado={bloqueado} cambiar={setPaginaEventos} />
      </section>
      <section className="admin-panel" aria-labelledby="admin-negocios">
        <div className="admin-panel-heading"><div><h2 id="admin-negocios">Negocios y proveedores</h2><p>Accede al negocio para editar sus datos, ubicacion e imagenes.</p></div><span>{negocios.total} resultados</span></div>
        <div className="admin-table-wrap"><table><thead><tr><th>Negocio</th><th>Propietario</th><th>Estado</th><th>Accion</th></tr></thead><tbody>
          {negocios.items.map(n => <tr key={n.id}><td><strong>{n.nombre}</strong><small>/{n.slug}</small></td><td>{n.propietario_email}</td><td><Estado activo={n.activo} /></td><td>{n.activo ? <Link className="secondary-button" to={`/p/${n.slug}`}><Pencil size={15} /> Editar negocio</Link> : "Inactivo"}</td></tr>)}
          {!negocios.items.length && <tr><td colSpan={4}>No hay negocios para esta busqueda.</td></tr>}
        </tbody></table></div>
        <Paginacion pagina={paginaNegocios} total={negocios.total} bloqueado={bloqueado} cambiar={setPaginaNegocios} />
      </section>
    </>}
    {editando && <Ventana titulo="Editar cuenta" alCerrar={() => { if (!guardando) setEditando(null); }}>
      <form className="admin-user-form" onSubmit={guardarUsuario}>
        <label htmlFor="admin-nombre">Nombre<input autoFocus id="admin-nombre" value={nombreEdicion} maxLength={160} disabled={guardando} onChange={e => setNombreEdicion(e.target.value)} /></label>
        <label htmlFor="admin-email">Email de ingreso<input id="admin-email" type="email" required maxLength={255} value={emailEdicion} disabled={guardando} onChange={e => setEmailEdicion(e.target.value)} /></label>
        <p>Al cambiar el email, la cuenta conserva sus proveedores y eventos. Se cierran sus sesiones anteriores y se desvincula su acceso anterior con Google. Luego podes reenviar el enlace al correo corregido.</p>
        {errorEdicion && <p className="form-error" role="alert">{errorEdicion}</p>}
        <div className="admin-actions"><button className="secondary-button" type="button" disabled={guardando} onClick={() => setEditando(null)}>Cancelar</button><button className="action-button" disabled={guardando}>{guardando ? "Guardando..." : "Guardar cambios"}</button></div>
      </form>
    </Ventana>}
  </main>;
}

function Estado({ activo }: { activo: boolean }) {
  return <span className={`admin-status ${activo ? "is-active" : "is-inactive"}`}>{activo ? "Activo" : "Inactivo"}</span>;
}

function Paginacion({ pagina, total, bloqueado, cambiar }: { pagina: number; total: number; bloqueado: boolean; cambiar: (pagina: number) => void }) {
  return <div className="admin-pagination"><span>{total ? pagina * TAMANO + 1 : 0}–{Math.min((pagina + 1) * TAMANO, total)} de {total}</span>
    <button className="secondary-button" disabled={bloqueado || pagina === 0} onClick={() => cambiar(pagina - 1)}>Anterior</button>
    <button className="secondary-button" disabled={bloqueado || (pagina + 1) * TAMANO >= total} onClick={() => cambiar(pagina + 1)}>Siguiente</button></div>;
}
