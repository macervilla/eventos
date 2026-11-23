import { Route, Routes, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { BarraSesion } from "./components/BarraSesion";
import { MenuSesionProvider } from "./components/MenuSesionContext";
import { EVENTO_SESION, obtenerTokenSesion } from "./api/sesion";

import { EventFormPage } from "./pages/EventFormPage";
import { PublicPage, PaginaNoEncontrada } from "./pages/PublicPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { AccesoEquipoPage } from "./pages/AccesoEquipoPage";
import { AdminPage } from "./pages/AdminPage";
import { InvitadosPage } from "./pages/InvitadosPage";
import { AlbumEventoPage } from "./pages/AlbumEventoPage";
import { InvitacionPersonalPage } from "./pages/InvitacionPersonalPage";
import { ControlIngresoPage } from "./pages/ControlIngresoPage";
import { ProviderFormPage } from "./pages/ProviderFormPage";
import { ProveedoresPage } from "./pages/ProveedoresPage";

export function App() {
  const location = useLocation();
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const actualizar = () => { if (!obtenerTokenSesion() || location.pathname !== "/ingresar") setRevision(n => n + 1); };
    window.addEventListener(EVENTO_SESION, actualizar);
    window.addEventListener("storage", actualizar);
    return () => { window.removeEventListener(EVENTO_SESION, actualizar); window.removeEventListener("storage", actualizar); };
  }, [location.pathname]);
  return (
    <MenuSesionProvider><BarraSesion /><Routes key={revision}>
      <Route path="/" element={<HomePage />} />
      <Route path="/ingresar" element={<LoginPage />} />
      <Route path="/administracion" element={<AdminPage />} />
      <Route path="/eventos/nuevo" element={<EventFormPage />} />
      <Route path="/:slug" element={<PublicPage />} />
      <Route path="/:slug/acceso-equipo" element={<AccesoEquipoPage />} />
      <Route path="/:slug/invitados" element={<InvitadosPage />} />
      <Route path="/:slug/album" element={<AlbumEventoPage />} />
      <Route path="/:slug/i/:token" element={<InvitacionPersonalPage />} />
      <Route path="/:slug/control-ingreso" element={<ControlIngresoPage />} />
      <Route path="/proveedores" element={<ProveedoresPage />} />
      <Route path="/proveedores/nuevo" element={<ProviderFormPage />} />
      <Route path="*" element={<PaginaNoEncontrada />} />
    </Routes></MenuSesionProvider>
  );
}
