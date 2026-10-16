import {
  ClipboardPaste,
  Crop,
  Facebook,
  Globe,
  ImageUp,
  Instagram,
  LogOut,
  Mail,
  MapPin,
  MapPinned,
  MessageCircle,
  Pencil,
  Phone
} from "lucide-react";
import { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import { cerrarSesion, obtenerTokenSesion } from "../api/sesion";
import {
  mensajeDeError,
  urlMapaEmbebido,
  VentanaDatos,
  VentanaUbicacion
} from "../components/EdicionProveedor";
import { CapasPortada, EncuadrePortada, useAjusteEncuadre } from "../components/PortadaAjustable";
import { leerImagenDelPortapapeles, prepararImagen, usePegarImagen } from "../components/pegarImagen";
import { providerTemplates, ProviderTemplateKey } from "../templates/visualTemplates";
import { Proveedor } from "../types/proveedores";

type SesionActual = {
  opciones: { tipo: string; slug: string }[];
};

function urlWeb(web: string) {
  try {
    return new URL(web).hostname.replace(/^www\./, "");
  } catch {
    return web;
  }
}

export function ProviderPublicPage() {
  const { slug } = useParams();
  const [proveedor, setProveedor] = useState<Proveedor | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [esAdministrador, setEsAdministrador] = useState(false);
  const [ventanaAbierta, setVentanaAbierta] = useState<"datos" | "ubicacion" | null>(null);
  const [subiendoPortada, setSubiendoPortada] = useState(false);
  const [avisoEdicion, setAvisoEdicion] = useState<string | null>(null);
  const selectorPortada = useRef<HTMLInputElement>(null);

  const cargarProveedor = useCallback(() => {
    if (!slug) return;
    api
      .get<Proveedor>(`/proveedores/${slug}`)
      .then((response) => setProveedor(response.data))
      .catch(() => setError("No se encontro el proveedor."));
  }, [slug]);

  useEffect(cargarProveedor, [cargarProveedor]);

  useEffect(() => {
    // Solo se habilita la edicion si hay sesion y el backend confirma que administra este slug.
    setEsAdministrador(false);
    if (!slug || !obtenerTokenSesion()) return;
    api
      .get<SesionActual>("/acceso/yo")
      .then((response) =>
        setEsAdministrador(
          response.data.opciones.some((opcion) => opcion.tipo === "proveedor" && opcion.slug === slug)
        )
      )
      .catch(() => setEsAdministrador(false));
  }, [slug]);

  const salir = () => {
    cerrarSesion();
    setEsAdministrador(false);
  };

  const alGuardar = (actualizado: Proveedor) => {
    setProveedor(actualizado);
    setVentanaAbierta(null);
    setAvisoEdicion(null);
  };

  const subirPortada = useCallback(
    async (original: File) => {
      if (!slug) return;
      setSubiendoPortada(true);
      setAvisoEdicion(null);
      // FormData: arma el cuerpo multipart para enviar el archivo
      const datos = new FormData();
      datos.append("file", await prepararImagen(original));
      api
        .post(`/media/proveedores/${slug}/PORTADA`, datos)
        .then(cargarProveedor)
        .catch((err) =>
          setAvisoEdicion(
            err?.response?.status === 400 || err?.response?.status === 413
              ? "Usa una imagen JPG, PNG o WebP de hasta 5 MB."
              : mensajeDeError(err)
          )
        )
        .finally(() => setSubiendoPortada(false));
    },
    [slug, cargarProveedor]
  );

  const cover =
    proveedor?.portada_url ??
    "https://images.unsplash.com/photo-1511795409834-ef04bbd61622?auto=format&fit=crop&w=1600&q=80";
  const ajuste = useAjusteEncuadre(
    cover,
    proveedor?.portada_url ? proveedor.portada_encuadre : null,
    (encuadre: EncuadrePortada) =>
      api
        .put<Proveedor>(`/proveedores/${slug}/portada-encuadre`, encuadre)
        .then((r) => setProveedor(r.data)),
    setAvisoEdicion
  );

  usePegarImagen(
    esAdministrador && ventanaAbierta === null && !subiendoPortada && !ajuste.editando,
    subirPortada
  );

  const cambiarPortada = (evento: ChangeEvent<HTMLInputElement>) => {
    const archivo = evento.target.files?.[0];
    evento.target.value = "";
    if (archivo) subirPortada(archivo);
  };

  const pegarDesdeBoton = () => {
    leerImagenDelPortapapeles()
      .then((archivo) =>
        archivo ? subirPortada(archivo) : setAvisoEdicion("No hay una imagen copiada en el portapapeles.")
      )
      .catch(() => setAvisoEdicion("El navegador no permitio leer el portapapeles. Proba con Ctrl+V."));
  };

  if (error) {
    return (
      <main className="providers-page">
        <div className="empty-state error">{error}</div>
      </main>
    );
  }

  if (!proveedor) {
    return (
      <main className="providers-page">
        <div className="empty-state">Cargando proveedor...</div>
      </main>
    );
  }

  const template =
    providerTemplates[(proveedor.template_key as ProviderTemplateKey) ?? "professional"] ??
    providerTemplates.professional;
  const mapa = urlMapaEmbebido(proveedor);
  const enlaceMaps =
    proveedor.google_maps_url ??
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
      [proveedor.direccion, proveedor.localidad, proveedor.provincia].filter(Boolean).join(", ")
    )}`;
  const instagram = proveedor.instagram?.replace(/^@/, "");
  const whatsapp = proveedor.whatsapp?.replace(/\D/g, "");

  return (
    <main className={`provider-public ${template.className}`}>
      <section className="provider-cover">
        <CapasPortada imagen={cover} encuadre={ajuste.encuadreVisible} />
        <nav className="public-nav overlay-nav">
          <Link to="/" className="brand">
            Eventos
          </Link>
          <Link to="/proveedores">Buscar proveedores</Link>
        </nav>
        <div className="provider-cover-copy">
          <p className="eyebrow">
            {proveedor.categorias_detalle.map((category) => category.nombre).join(" · ")}
          </p>
          <h1>{proveedor.nombre_comercial}</h1>
          <p>{proveedor.descripcion ?? "Proveedor de servicios para eventos."}</p>
        </div>

        {ajuste.editor}
        {esAdministrador && !ajuste.editando && (
          <div className="barra-administrador" aria-label="Edicion de la pagina">
            {avisoEdicion && <span className="aviso-edicion">{avisoEdicion}</span>}
            <input
              ref={selectorPortada}
              accept="image/jpeg,image/png,image/webp"
              hidden
              type="file"
              onChange={cambiarPortada}
            />
            <button
              className="icono-boton flotante"
              disabled={subiendoPortada}
              title="Pegar imagen del portapapeles (tambien funciona Ctrl+V)"
              type="button"
              onClick={pegarDesdeBoton}
            >
              <ClipboardPaste size={20} aria-hidden="true" />
            </button>
            <button
              className="icono-boton flotante"
              disabled={subiendoPortada}
              title={subiendoPortada ? "Subiendo imagen..." : "Cambiar imagen de fondo"}
              type="button"
              onClick={() => selectorPortada.current?.click()}
            >
              <ImageUp size={20} aria-hidden="true" />
            </button>
            <button
              className="icono-boton flotante"
              title="Ajustar encuadre de la imagen"
              type="button"
              onClick={ajuste.empezar}
            >
              <Crop size={20} aria-hidden="true" />
            </button>
            <button
              className="icono-boton flotante"
              title="Editar datos del negocio"
              type="button"
              onClick={() => setVentanaAbierta("datos")}
            >
              <Pencil size={20} aria-hidden="true" />
            </button>
            <button className="icono-boton flotante" title="Cerrar sesion" type="button" onClick={salir}>
              <LogOut size={20} aria-hidden="true" />
            </button>
          </div>
        )}
      </section>

      <section className="provider-public-content">
        <article className="provider-info">
          <h2>Datos del negocio</h2>
          <p>{proveedor.horarios ?? "Horarios y disponibilidad a confirmar con el proveedor."}</p>
          <div className="contact-grid">
            {proveedor.localidad && (
              <span>
                <MapPin size={18} />
                {proveedor.localidad}, {proveedor.provincia}
              </span>
            )}
            {proveedor.email && (
              <a href={`mailto:${proveedor.email}`}>
                <Mail size={18} />
                {proveedor.email}
              </a>
            )}
            {whatsapp && (
              <a href={`https://wa.me/${whatsapp}`} target="_blank" rel="noreferrer">
                <MessageCircle size={18} />
                {proveedor.whatsapp}
              </a>
            )}
            {proveedor.telefono && (
              <a href={`tel:${proveedor.telefono}`}>
                <Phone size={18} />
                {proveedor.telefono}
              </a>
            )}
            {instagram && (
              <a href={`https://instagram.com/${instagram}`} target="_blank" rel="noreferrer">
                <Instagram size={18} />@{instagram}
              </a>
            )}
            {proveedor.facebook && (
              <a
                href={
                  proveedor.facebook.startsWith("http")
                    ? proveedor.facebook
                    : `https://facebook.com/${proveedor.facebook}`
                }
                target="_blank"
                rel="noreferrer"
              >
                <Facebook size={18} />
                {proveedor.facebook}
              </a>
            )}
            {proveedor.web && (
              <a href={proveedor.web} target="_blank" rel="noreferrer">
                <Globe size={18} />
                {urlWeb(proveedor.web)}
              </a>
            )}
          </div>
        </article>
        <aside className="provider-side">
          <h2>Ubicacion</h2>
          <p>{proveedor.direccion ?? "Direccion comercial no publicada."}</p>
          {proveedor.ubicacion_referencia && <p>{proveedor.ubicacion_referencia}</p>}
          <div className="mapa-contenedor">
            {mapa ? (
              <iframe className="mapa-embebido" src={mapa} title="Mapa de la ubicacion" loading="lazy" />
            ) : (
              <div className="map-placeholder">Ubicacion pendiente</div>
            )}
            {esAdministrador && (
              <button
                className="icono-boton flotante mapa-editar"
                title="Cambiar ubicacion"
                type="button"
                onClick={() => setVentanaAbierta("ubicacion")}
              >
                <MapPinned size={20} aria-hidden="true" />
              </button>
            )}
          </div>
          <a className="enlace-maps" href={enlaceMaps} target="_blank" rel="noreferrer">
            <MapPin size={18} aria-hidden="true" />
            Ver en Google Maps
          </a>
        </aside>
      </section>

      {ventanaAbierta === "datos" && (
        <VentanaDatos proveedor={proveedor} alGuardar={alGuardar} alCerrar={() => setVentanaAbierta(null)} />
      )}
      {ventanaAbierta === "ubicacion" && (
        <VentanaUbicacion
          proveedor={proveedor}
          alGuardar={alGuardar}
          alCerrar={() => setVentanaAbierta(null)}
        />
      )}
    </main>
  );
}
