import { Building2, CalendarDays, ClipboardPaste, Crop, Home, ImageUp, LogOut, MailCheck, MapPin, MapPinned, Pencil } from "lucide-react";
import { ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { cerrarSesion, guardarTokenSesion, obtenerTokenSesion } from "../api/sesion";
import { Evento, VentanaDatosEvento, VentanaSalonEvento } from "../components/EdicionEvento";
import { mensajeDeError, urlMapaEmbebido } from "../components/EdicionProveedor";
import { CapasPortada, EncuadrePortada, useAjusteEncuadre } from "../components/PortadaAjustable";
import { leerImagenDelPortapapeles, prepararImagen, usePegarImagen } from "../components/pegarImagen";
import { estiloTipografia, useFuentesGoogle } from "../data/tipografias";
import { eventTemplates, EventTemplateKey } from "../templates/visualTemplates";

type SesionActual = {
  opciones: { tipo: string; slug: string }[];
};

const portadaPorDefecto =
  "https://images.unsplash.com/photo-1530103862676-de8c9debad1d?auto=format&fit=crop&w=1600&q=80";

function formatearFecha(iso: string) {
  // Intl.DateTimeFormat: formatea la fecha en castellano y en la zona horaria del navegador
  return new Intl.DateTimeFormat("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(iso));
}

export function EventPublicPage() {
  const { slug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const confirmacionProcesada = useRef(false);
  const selectorPortada = useRef<HTMLInputElement>(null);

  const [evento, setEvento] = useState<Evento | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [esAdministrador, setEsAdministrador] = useState(false);
  // Sin sesion la pagina funciona como invitacion: no se muestra la navegacion del portal.
  const [haySesion, setHaySesion] = useState(() => Boolean(obtenerTokenSesion()));
  const [ventanaAbierta, setVentanaAbierta] = useState<"datos" | "salon" | null>(null);
  const [subiendoPortada, setSubiendoPortada] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [avisoError, setAvisoError] = useState<string | null>(null);

  const cargar = useCallback(() => {
    if (!slug) return;
    api
      .get<Evento>(`/eventos/${slug}`)
      .then((response) => setEvento(response.data))
      .catch(() => setError("No encontramos este evento o todavia no fue confirmado."));

    setEsAdministrador(false);
    setHaySesion(Boolean(obtenerTokenSesion()));
    if (!obtenerTokenSesion()) return;
    api
      .get<SesionActual>("/acceso/yo")
      .then((response) =>
        setEsAdministrador(
          response.data.opciones.some((opcion) => opcion.tipo === "evento" && opcion.slug === slug)
        )
      )
      .catch(() => setEsAdministrador(false));
  }, [slug]);

  useEffect(() => {
    const token = searchParams.get("confirmar");
    if (!token) {
      cargar();
      return;
    }
    // useRef evita canjear el enlace dos veces (StrictMode ejecuta los efectos doble en desarrollo)
    if (confirmacionProcesada.current) return;
    confirmacionProcesada.current = true;
    api
      .post<{ slug: string; token: string }>("/eventos/confirmar", { token })
      .then((response) => {
        guardarTokenSesion(response.data.token);
        setAviso("Evento confirmado. Ya podes administrarlo desde esta pagina.");
      })
      .catch(() => setAvisoError("El enlace de confirmacion vencio o no es valido."))
      .finally(() => {
        // Se quita el token de la URL para que no quede en el historial ni se comparta.
        setSearchParams({}, { replace: true });
      });
  }, [searchParams, setSearchParams, cargar]);

  const salir = () => {
    cerrarSesion();
    setEsAdministrador(false);
    cargar();
  };

  const alGuardar = (actualizado: Evento) => {
    setEvento(actualizado);
    setVentanaAbierta(null);
    setAvisoError(null);
  };

  const subirPortada = useCallback(
    async (original: File) => {
      if (!slug) return;
      setSubiendoPortada(true);
      setAvisoError(null);
      const datos = new FormData();
      datos.append("file", await prepararImagen(original));
      api
        .post(`/media/eventos/${slug}/PORTADA`, datos)
        .then(cargar)
        .catch((err) =>
        setAvisoError(
          err?.response?.status === 400 || err?.response?.status === 413
            ? "Usa una imagen JPG, PNG o WebP de hasta 5 MB."
            : mensajeDeError(err)
          )
        )
        .finally(() => setSubiendoPortada(false));
    },
    [slug, cargar]
  );

  const portada = evento?.portada_url ?? evento?.salon?.portada_url ?? portadaPorDefecto;
  const ajuste = useAjusteEncuadre(
    portada,
    evento?.portada_url ? evento.portada_encuadre : null,
    (encuadre: EncuadrePortada) =>
      api.put<Evento>(`/eventos/${slug}/portada-encuadre`, encuadre).then((r) => setEvento(r.data)),
    setAvisoError
  );

  useFuentesGoogle(evento ? [evento.tipografia] : []);

  usePegarImagen(
    esAdministrador && ventanaAbierta === null && !subiendoPortada && !ajuste.editando,
    subirPortada
  );

  const cambiarPortada = (e: ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0];
    e.target.value = "";
    if (archivo) subirPortada(archivo);
  };

  const pegarDesdeBoton = () => {
    leerImagenDelPortapapeles()
      .then((archivo) =>
        archivo ? subirPortada(archivo) : setAvisoError("No hay una imagen copiada en el portapapeles.")
      )
      .catch(() => setAvisoError("El navegador no permitio leer el portapapeles. Proba con Ctrl+V."));
  };

  const reenviarConfirmacion = () => {
    api
      .post(`/eventos/${slug}/reenviar-confirmacion`)
      .then(() => setAviso("Reenviamos el mail de confirmacion."))
      .catch(() => setAvisoError("No se pudo reenviar el mail."));
  };

  if (error) {
    return (
      <main className="providers-page">
        {avisoError && <div className="empty-state error">{avisoError}</div>}
        <div className="empty-state error">{error}</div>
      </main>
    );
  }

  if (!evento) {
    return (
      <main className="providers-page">
        <div className="empty-state">
          {searchParams.get("confirmar") ? "Confirmando evento..." : "Cargando evento..."}
        </div>
      </main>
    );
  }

  const template =
    eventTemplates[evento.template_key as EventTemplateKey] ?? eventTemplates.classic;
  const salon = evento.salon;
  const mapa = urlMapaEmbebido({
    latitud: evento.latitud,
    longitud: evento.longitud,
    direccion: evento.direccion,
    localidad: evento.localidad,
    provincia: evento.provincia
  });
  const nombreLugar = salon?.nombre_comercial ?? "Mi casa";
  const enlaceMaps =
    salon?.google_maps_url ??
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
      evento.latitud != null && evento.longitud != null
        ? `${evento.latitud},${evento.longitud}`
        : [evento.direccion, evento.localidad, evento.provincia].filter(Boolean).join(", ")
    )}`;

  return (
    <main
      className={`provider-public con-tipografia ${template.className}`}
      style={estiloTipografia(evento.tipografia)}
    >
      <section className="provider-cover">
        <CapasPortada imagen={portada} encuadre={ajuste.encuadreVisible} />
        {haySesion && (
          <nav className="public-nav overlay-nav">
            <Link to="/" className="brand">
              Eventos
            </Link>
            <Link to="/proveedores">Buscar proveedores</Link>
          </nav>
        )}
        <div className="provider-cover-copy">
          <p className="eyebrow">
            {evento.fecha_inicio ? formatearFecha(evento.fecha_inicio) : "Fecha a confirmar"}
          </p>
          <h1>{evento.nombre}</h1>
          <p>{salon ? salon.nombre_comercial : evento.localidad}</p>
        </div>

        {ajuste.editor}
        {esAdministrador && !ajuste.editando && (
          <div className="barra-administrador" aria-label="Edicion del evento">
            {avisoError && <span className="aviso-edicion">{avisoError}</span>}
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
              title="Editar datos del evento"
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

      {(aviso || (esAdministrador && !evento.confirmado)) && (
        <div className="evento-avisos">
          {aviso && <p className="success-inline">{aviso}</p>}
          {esAdministrador && !evento.confirmado && (
            <p className="evento-pendiente">
              Este evento esta pendiente de confirmacion y no es visible para otros.
              <button className="secondary-button" type="button" onClick={reenviarConfirmacion}>
                <MailCheck size={18} aria-hidden="true" />
                Reenviar mail
              </button>
            </p>
          )}
        </div>
      )}

      <section className="provider-public-content">
        <article className="provider-info">
          <h2>Detalles del evento</h2>
          <p>{evento.descripcion ?? "Pronto vas a encontrar mas informacion sobre este evento."}</p>
          <div className="contact-grid">
            <span>
              <CalendarDays size={18} />
              {evento.fecha_inicio ? formatearFecha(evento.fecha_inicio) : "Fecha a confirmar"}
            </span>
            {salon ? (
              <Link to={`/p/${salon.slug}`}>
                <Building2 size={18} />
                {salon.nombre_comercial}
              </Link>
            ) : (
              <span>
                <Home size={18} />
                Mi casa
              </span>
            )}
            {evento.direccion && (
              <span>
                <MapPin size={18} />
                {[evento.direccion, evento.localidad, evento.provincia].filter(Boolean).join(", ")}
              </span>
            )}
          </div>
        </article>
        <aside className="provider-side">
          <h2>Lugar</h2>
          <p>{nombreLugar}</p>
          <div className="mapa-contenedor">
            {mapa ? (
              <iframe className="mapa-embebido" src={mapa} title="Mapa del lugar" loading="lazy" />
            ) : (
              <div className="map-placeholder">Ubicacion pendiente</div>
            )}
            {esAdministrador && (
              <button
                className="icono-boton flotante mapa-editar"
                title="Cambiar lugar (salon o mi casa)"
                type="button"
                onClick={() => setVentanaAbierta("salon")}
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
        <VentanaDatosEvento evento={evento} alGuardar={alGuardar} alCerrar={() => setVentanaAbierta(null)} />
      )}
      {ventanaAbierta === "salon" && (
        <VentanaSalonEvento evento={evento} alGuardar={alGuardar} alCerrar={() => setVentanaAbierta(null)} />
      )}
    </main>
  );
}
