import { Navigate, Route, Routes, useParams } from "react-router-dom";

import { EventFormPage } from "./pages/EventFormPage";
import { EventPublicPage } from "./pages/EventPublicPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
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
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/ingresar" element={<LoginPage />} />
      <Route path="/eventos/nuevo" element={<EventFormPage />} />
      <Route path="/eventos/:slug/editar" element={<RedirigirAPaginaEvento />} />
      <Route path="/e/:slug" element={<EventPublicPage />} />
      <Route path="/proveedores" element={<ProveedoresPage />} />
      <Route path="/proveedores/nuevo" element={<ProviderFormPage />} />
      <Route path="/proveedores/:slug/editar" element={<RedirigirAPaginaProveedor />} />
      <Route path="/p/:slug" element={<ProviderPublicPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
