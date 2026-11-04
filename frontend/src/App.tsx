import { Navigate, Route, Routes, useParams, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { BarraSesion } from "./components/BarraSesion";
import { EVENTO_SESION, obtenerTokenSesion } from "./api/sesion";

import { EventFormPage } from "./pages/EventFormPage";
import { EventPublicPage } from "./pages/EventPublicPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { AdminPage } from "./pages/AdminPage";
import { InvitadosPage } from "./pages/InvitadosPage";
import { InvitacionPersonalPage } from "./pages/InvitacionPersonalPage";
import { ControlIngresoPage } from "./pages/ControlIngresoPage";
import { ProviderFormPage } from "./pages/ProviderFormPage";
import { ProviderPublicPage } from "./pages/ProviderPublicPage";
import { ProveedoresPage } from "./pages/ProveedoresPage";

// La edicion de un proveedor ahora se hace sobre su pagina publica (modo administrador).
function RedirigirAPaginaProveedor() {
  const { slug } = useParams();
  return <Navigate to={`/p/${slug}`} replace />;
}

function RedirigirAPaginaEvento() {
  const { slug } = useParams();
  return <Navigate to={`/e/${slug}`} replace />;
}

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
    <><BarraSesion /><Routes key={revision}>
      <Route path="/" element={<HomePage />} />
      <Route path="/ingresar" element={<LoginPage />} />
      <Route path="/administracion" element={<AdminPage />} />
      <Route path="/eventos/nuevo" element={<EventFormPage />} />
      <Route path="/eventos/:slug/editar" element={<RedirigirAPaginaEvento />} />
      <Route path="/e/:slug" element={<EventPublicPage />} />
      <Route path="/e/:slug/invitados" element={<InvitadosPage />} />
      <Route path="/e/:slug/i/:token" element={<InvitacionPersonalPage />} />
      <Route path="/e/:slug/control-ingreso" element={<ControlIngresoPage />} />
      <Route path="/proveedores" element={<ProveedoresPage />} />
      <Route path="/proveedores/nuevo" element={<ProviderFormPage />} />
      <Route path="/proveedores/:slug/editar" element={<RedirigirAPaginaProveedor />} />
      <Route path="/p/:slug" element={<ProviderPublicPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes></>
  );
}
