import axios from "axios";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { EventPublicPage } from "./EventPublicPage";
import { ProviderPublicPage } from "./ProviderPublicPage";

export function PaginaNoEncontrada() {
  return <main className="page"><h1>404 — Pagina no encontrada</h1><p>El enlace no existe o ya no esta disponible.</p></main>;
}

export function PublicPage() {
  const { slug } = useParams();
  const [resultado, setResultado] = useState<{ slug?: string; tipo: string }>({ tipo: "cargando" });
  useEffect(() => {
    const controller = new AbortController();
    setResultado({ slug, tipo: "cargando" });
    api.get<{ tipo: string }>(`/publico/${slug}`, { signal: controller.signal })
      .then(({ data }) => setResultado({ slug, tipo: data.tipo }))
      .catch(error => {
        if (!controller.signal.aborted) setResultado({ slug, tipo: axios.isAxiosError(error) && error.response?.status === 404 ? "404" : "error" });
      });
    return () => controller.abort();
  }, [slug]);
  if (resultado.slug !== slug || resultado.tipo === "cargando") return <main className="page">Cargando...</main>;
  if (resultado.tipo === "evento") return <EventPublicPage key={slug} />;
  if (resultado.tipo === "proveedor") return <ProviderPublicPage key={slug} />;
  if (resultado.tipo === "error") return <main className="page" role="alert">No se pudo cargar la pagina. Intenta nuevamente.</main>;
  return <PaginaNoEncontrada />;
}
