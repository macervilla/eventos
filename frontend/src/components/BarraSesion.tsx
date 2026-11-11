import { Globe, LogIn, LogOut, Menu, Search, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { useMenuSesion } from "./MenuSesionContext";
import { MenuDesplegable } from "./MenuDesplegable";
import { cerrarSesion, EVENTO_SESION, seleccionarCuentaSesion, obtenerTokenSesion } from "../api/sesion";

export function BarraSesion() {
  const location = useLocation();
  const { accionesEvento, alCerrarSesion } = useMenuSesion();
  const [token, setToken] = useState(obtenerTokenSesion);
  useEffect(() => {
    const actualizar = () => setToken(obtenerTokenSesion());
    window.addEventListener(EVENTO_SESION, actualizar);
    window.addEventListener("storage", actualizar);
    return () => { window.removeEventListener(EVENTO_SESION, actualizar); window.removeEventListener("storage", actualizar); };
  }, []);
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    api.get<{ email: string; usuario_id: number; opciones: { tipo: string; path: string; cuenta_id: number; token?: string }[] }>("/acceso/yo", { signal: controller.signal })
      .then(r => {
        if (controller.signal.aborted) return;
        const opcion = r.data.opciones.find(o => location.pathname === o.path || location.pathname.startsWith(o.path + "/"));
        if (opcion?.token && opcion.cuenta_id !== r.data.usuario_id) seleccionarCuentaSesion(opcion.token);
      }).catch(() => undefined);
    return () => controller.abort();
  }, [token, location.pathname]);
  const destino = location.pathname === "/ingresar" ? "/" : location.pathname + location.search + location.hash;
  return <nav className="barra-sesion" aria-label="Sesion de Eventos">
    <Link className="barra-marca" to="/"><Globe size={20} aria-hidden="true" /> Eventos</Link>
    <div className="barra-cuenta">
      <MenuDesplegable key={token || "sin-sesion"} etiqueta="Menú" icono={<Menu size={19} aria-hidden="true" />} className="menu-cuenta">
        <Link className="barra-control" to="/proveedores"><Search size={19} aria-hidden="true" /> Buscar proveedores</Link>
        {token ? <>
          <Link className="barra-control" to="/ingresar">
            <UserRound size={19} aria-hidden="true" /> Mis sitios
          </Link>
        </> : <Link className="barra-control" to={`/ingresar?destino=${encodeURIComponent(destino)}`}><LogIn size={19} aria-hidden="true" /> Ingresar a mi cuenta</Link>}
        {accionesEvento}
        {token && <button className="barra-control" type="button" onClick={alCerrarSesion ?? cerrarSesion}><LogOut size={19} aria-hidden="true" /> Cerrar sesion</button>}
      </MenuDesplegable>
    </div>
  </nav>;
}
