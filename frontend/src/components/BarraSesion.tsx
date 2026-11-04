import { Globe, LayoutDashboard, LogIn, LogOut, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { MenuDesplegable } from "./MenuDesplegable";
import { cerrarSesion, EVENTO_SESION, seleccionarCuentaSesion, obtenerTokenSesion } from "../api/sesion";

export function BarraSesion() {
  const location = useLocation();
  const [token, setToken] = useState(obtenerTokenSesion);
  const [email, setEmail] = useState("");
  const [dashboard, setDashboard] = useState<{ sesion: string; path: string; token?: string } | null>(null);
  useEffect(() => {
    const actualizar = () => setToken(obtenerTokenSesion());
    window.addEventListener(EVENTO_SESION, actualizar);
    window.addEventListener("storage", actualizar);
    return () => { window.removeEventListener(EVENTO_SESION, actualizar); window.removeEventListener("storage", actualizar); };
  }, []);
  useEffect(() => {
    setEmail("");
    setDashboard(null);
    if (!token) return;
    const controller = new AbortController();
    api.get<{ email: string; usuario_id: number; opciones: { tipo: string; path: string; cuenta_id: number; token?: string }[] }>("/acceso/yo", { signal: controller.signal })
      .then(r => {
        if (controller.signal.aborted) return;
        setEmail(r.data.email);
        const administracion = r.data.opciones.find(o => o.tipo === "administracion");
        if (administracion) setDashboard({ sesion: token, path: administracion.path, token: administracion.token });
        const opcion = r.data.opciones.find(o => location.pathname === o.path || location.pathname.startsWith(o.path + "/"));
        if (opcion?.token && opcion.cuenta_id !== r.data.usuario_id) seleccionarCuentaSesion(opcion.token);
      }).catch(() => undefined);
    return () => controller.abort();
  }, [token, location.pathname]);
  const destino = location.pathname === "/ingresar" ? "/" : location.pathname + location.search + location.hash;
  return <nav className="barra-sesion" aria-label="Sesion de Eventos">
    <Link className="barra-marca" to="/"><Globe size={20} aria-hidden="true" /> Eventos</Link>
    <div className="barra-cuenta">
      {token ? <MenuDesplegable key={token} etiqueta="Mi cuenta" icono={<UserRound size={19} aria-hidden="true" />} className="menu-cuenta">
      {email && <span className="barra-email" title={email}>{email}</span>}
      {dashboard && dashboard.sesion === token && <Link className="barra-control" to={dashboard.path} onClick={() => { if (dashboard.token) seleccionarCuentaSesion(dashboard.token); }}>
        <LayoutDashboard size={19} aria-hidden="true" /> Dashboard
      </Link>}
      <Link className="barra-control" to="/ingresar">
        <UserRound size={19} aria-hidden="true" /> Mis sitios
      </Link>
      <button className="barra-control" type="button" onClick={cerrarSesion}><LogOut size={19} aria-hidden="true" /> Cerrar sesion</button>
      </MenuDesplegable> : <Link className="barra-control" to={`/ingresar?destino=${encodeURIComponent(destino)}`}><LogIn size={19} aria-hidden="true" /> Ingresar</Link>}
    </div>
  </nav>;
}
