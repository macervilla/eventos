import { Building2, CalendarDays, ClipboardPaste, Crop, Home, ImageUp, LogOut, MailCheck, MapPin, MapPinned, Pencil } from "lucide-react";
import { CSSProperties, ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { GaleriaEvento } from "../components/GaleriaEvento";
import { MenuDesplegable } from "../components/MenuDesplegable";
import { TextosPortadaEvento } from "../components/TextosPortada";
import { IngresoEvento } from "../components/IngresoEvento";
import { Ventana } from "../components/Ventana";
import { api } from "../api/client";
import { cerrarSesion, guardarTokenSesion, obtenerTokenSesion } from "../api/sesion";
import { Evento, VentanaDatosEvento, VentanaSalonEvento, VentanaGaleriaEvento } from "../components/EdicionEvento";
import { mensajeDeError, urlMapaEmbebido } from "../components/EdicionProveedor";
import { CapasPortada, EncuadrePortada, useAjusteEncuadre } from "../components/PortadaAjustable";
import { leerImagenDelPortapapeles, prepararImagen, usePegarImagen } from "../components/pegarImagen";
import { estiloTipografia, useFuentesGoogle } from "../data/tipografias";
import { eventTemplates, EventTemplateKey } from "../templates/visualTemplates";

type PermisosEvento = {
  permisos_invitados: string[];
  usuario: { id: number; email: string } | null;
  rol: string;
  puede_editar: boolean;
};

const portadaPorDefecto =
  "/media/sistema/evento.png";

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

export function EventPublicPage({ alCambiarSesion }: { alCambiarSesion?: () => void } = {}) {
  const { slug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const confirmacionProcesada = useRef(false);
  const selectorPortada = useRef<HTMLInputElement>(null);

  const [evento, setEvento] = useState<Evento | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [esAdministrador, setEsAdministrador] = useState(false);
  const [usuario, setUsuario] = useState<PermisosEvento['usuario']>(null);
  const [rol, setRol] = useState("visitante");
  const [permisosInvitados, setPermisosInvitados] = useState<string[]>([]);
  const [editando, setEditando] = useState(false);
  const [ingresoAbierto, setIngresoAbierto] = useState(false);
  const [imagenPendiente, setImagenPendiente] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [destinoImagen, setDestinoImagen] = useState<{ tipo: "PORTADA" | "GALERIA"; id?: number }>({ tipo: "PORTADA" });
  // Sin sesion la pagina funciona como invitacion: no se muestra la navegacion del portal.
  const [haySesion, setHaySesion] = useState(() => Boolean(obtenerTokenSesion()));
  const [ventanaAbierta, setVentanaAbierta] = useState<"datos" | "salon" | "galeria" | null>(null);
  const [subiendoPortada, setSubiendoPortada] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [avisoError, setAvisoError] = useState<string | null>(null);
  const [controlesTextos, setControlesTextos] = useState<HTMLDivElement | null>(null);

  const cargar = useCallback(async () => {
    if (!slug) return;
    setError(null);
    try {
      const response = await api.get<Evento>(`/eventos/${slug}`);
      setEvento(response.data);
    } catch { setError("No encontramos este evento o todavia no fue confirmado."); }
    if (!obtenerTokenSesion()) {
      setEsAdministrador(false); setHaySesion(false); setUsuario(null); setEditando(false); setPermisosInvitados([]);
      return;
    }
    try {
      const { data } = await api.get<PermisosEvento>(`/eventos/${slug}/permisos`);
      setEsAdministrador(data.puede_editar); setUsuario(data.usuario); setRol(data.rol);
      setPermisosInvitados(data.permisos_invitados || []);
      setHaySesion(Boolean(data.usuario));
      if (!data.puede_editar) setEditando(false);
    } catch {
      setEsAdministrador(false); setHaySesion(false); setUsuario(null); setEditando(false); setPermisosInvitados([]);
    }
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

  useEffect(() => {
    if (evento && window.location.hash === "#mi-confirmacion") {
      document.getElementById("mi-confirmacion")?.scrollIntoView({ block: "start" });
    }
  }, [evento]);

  const salir = () => {
    cerrarSesion();
    alCambiarSesion?.();
    setEsAdministrador(false);
    setEditando(false);
    setVentanaAbierta(null);
    cargar();
  };

  const alGuardar = (actualizado: Evento) => {
    setEvento(actualizado);
    setVentanaAbierta(null);
    setAvisoError(null);
    setAviso("Cambios guardados.");
  };

  const subirPortada = useCallback(
    async (original: File) => {
      if (!slug) return;
      setSubiendoPortada(true);
      setAvisoError(null);
      try {
        const datos = new FormData();
        datos.append("file", await prepararImagen(original));
        const ruta = `/media/eventos/${slug}/${destinoImagen.tipo}${destinoImagen.id ? `/${destinoImagen.id}` : ""}`;
        if (destinoImagen.id) await api.put(ruta, datos);
        else await api.post(ruta, datos);
        setImagenPendiente(null);
        await cargar();
        setAviso("Imagen guardada.");
      } catch (err) { setAvisoError(mensajeDeError(err)); }
      finally { setSubiendoPortada(false); }

    },
    [slug, cargar, destinoImagen]
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
    esAdministrador && editando && ventanaAbierta === null && !subiendoPortada && !ajuste.editando,
    archivo => { setDestinoImagen({ tipo: "PORTADA" }); setImagenPendiente(archivo); }
  );

  const cambiarPortada = (e: ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0];
    e.target.value = "";
    if (archivo) { setAvisoError(null); setImagenPendiente(archivo); }
  };

  const pegarDesdeBoton = () => {
    leerImagenDelPortapapeles()
      .then((archivo) =>
        archivo ? (setDestinoImagen({ tipo: "PORTADA" }), setImagenPendiente(archivo)) : setAvisoError("No hay una imagen copiada en el portapapeles.")
      )
      .catch(() => setAvisoError("El navegador no permitio leer el portapapeles. Proba con Ctrl+V."));
  };

  const reenviarConfirmacion = () => {
    api
      .post(`/eventos/${slug}/reenviar-confirmacion`)
      .then(() => setAviso("Reenviamos el mail de confirmacion."))
      .catch(() => setAvisoError("No se pudo reenviar el mail."));
  };

  useEffect(() => {
    if (!imagenPendiente) { setPreview(null); return; }
    const url = URL.createObjectURL(imagenPendiente);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [imagenPendiente]);

  const elegirImagen = (tipo: "PORTADA" | "GALERIA", id?: number) => {
    setDestinoImagen({ tipo, id });
    selectorPortada.current?.click();
  };
  const acceso = <div className="evento-acceso" aria-label="Acceso al evento">
    {haySesion && usuario ? <MenuDesplegable etiqueta="Menu del evento">
    {esAdministrador && evento && !evento.confirmado && <button className="action-button" type="button" onClick={() => {
      api.post<Evento>(`/eventos/${slug}/publicar`).then(r => { setEvento(r.data); setAviso("Evento publicado."); })
        .catch(err => setAvisoError(mensajeDeError(err)));
    }}>Publicar evento</button>}
      <span className="evento-usuario">{usuario.email}<small>{rol === "visitante" ? "Visitante - sin permisos de edicion" : rol}</small></span>
      {esAdministrador && <button className="secondary-button" onClick={() => { setEditando(!editando); setAviso(null); }}>{editando ? "Ver invitacion" : "Editar evento"}</button>}
      {permisosInvitados.some(p => ["ver_invitados", "configurar_invitados", "roles", "estadisticas"].includes(p)) && <Link className="secondary-button" to={`/e/${slug}/invitados`}>Gestion de invitados</Link>}
      {permisosInvitados.includes("control_ingreso") && <Link className="secondary-button" to={`/e/${slug}/control-ingreso`}>Control de ingreso</Link>}
      <button className="secondary-button" onClick={salir}>Salir</button>
    </MenuDesplegable> : <button className="secondary-button" onClick={() => setIngresoAbierto(true)}>Ingresar</button>}
  </div>;
  const ingreso = ingresoAbierto && slug && <IngresoEvento slug={slug} alCerrar={() => setIngresoAbierto(false)} alIngresar={() => { setIngresoAbierto(false); alCambiarSesion?.(); void cargar(); }} />;

  if (error) {
    return (
      <main className="providers-page">
        {acceso}{ingreso}
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
      className={`provider-public evento-personalizado con-tipografia ${template.className}`}
      style={{ ...estiloTipografia(evento.tipografia), "--evento-fondo": evento.colores.fondo, "--evento-texto": evento.colores.texto, "--evento-acento": evento.colores.acento } as CSSProperties}
    >
      {acceso}{ingreso}
      {editando && <p className="evento-modo-edicion" role="status">Modo edicion. Usa los controles para editar. Doble clic en una imagen para cambiarla.</p>}
      <input ref={selectorPortada} accept="image/jpeg,image/png,image/webp" hidden type="file" onChange={cambiarPortada} />
      <div ref={setControlesTextos} />
      <section className="provider-cover" onDoubleClick={e => { if (esAdministrador && editando && !(e.target as HTMLElement).closest("button, a, nav, .texto-portada, .textos-portada-controles")) elegirImagen("PORTADA"); }}>
        <CapasPortada imagen={portada} encuadre={ajuste.encuadreVisible} />
        {esAdministrador && (
          <nav className="public-nav overlay-nav">
            <Link to="/proveedores">Buscar proveedores</Link>
          </nav>
        )}
        <TextosPortadaEvento key={`${slug}-${editando}-${ajuste.editando}`} configuracion={evento.textos_portada}
          colores={evento.colores_textos}
          contenedorControles={controlesTextos}
          textos={{ fecha: evento.fecha_inicio ? formatearFecha(evento.fecha_inicio) : "Fecha a confirmar",
            titulo: evento.titulo_visual || evento.nombre, lugar: salon ? salon.nombre_comercial : evento.localidad || "" }}
          editable={esAdministrador && editando && !ajuste.editando}
          alGuardar={async config => {
            const { data } = await api.put<Evento>(`/eventos/${slug}/textos-portada`, config);
            setEvento(data); setAviso("Ubicacion y visibilidad de los textos guardadas.");
          }} />

        {ajuste.editor}
        {esAdministrador && editando && !ajuste.editando && (
          <div className="barra-administrador" aria-label="Edicion del evento">
            {avisoError && <span className="aviso-edicion">{avisoError}</span>}
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
              onClick={() => elegirImagen("PORTADA")}
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
        {(editando || evento.modulos_habilitados.includes("detalles")) && <article className="provider-info">
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
        </article>}
        {(editando || evento.modulos_habilitados.includes("ubicacion")) && <aside className="provider-side">
          <h2>Lugar</h2>
          <p>{nombreLugar}</p>
          <div className="mapa-contenedor">
            {mapa ? (
              <iframe className="mapa-embebido" src={mapa} title="Mapa del lugar" loading="lazy" />
            ) : (
              <div className="map-placeholder">Ubicacion pendiente</div>
            )}
            {esAdministrador && editando && (
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
        </aside>}
      </section>

      {avisoError && <p className="form-error evento-avisos" role="alert">{avisoError}</p>}
      {(editando || (evento.modulos_habilitados.includes("galeria") && evento.galeria.length > 0)) && <section className="evento-galeria">
        <h2>Imagenes del evento</h2>
        {esAdministrador && editando && <p>
          <button className="secondary-button" type="button" onClick={() => setVentanaAbierta("galeria")}>Configurar galeria</button>
          {!evento.modulos_habilitados.includes("galeria") && <span className="galeria-oculta">Oculta en la invitacion publica. Habilitala desde Configurar galeria.</span>}
        </p>}
        <GaleriaEvento key={`${slug}-${evento.galeria_config.modo}-${evento.galeria_config.filas}-${evento.galeria_config.columnas}`}
          imagenes={evento.galeria} config={evento.galeria_config} editando={esAdministrador && editando}
          alCambiar={id => elegirImagen("GALERIA", id)} />
        {esAdministrador && editando && <><p>{evento.galeria.length} de {evento.limite_galeria} imagenes.</p><button className="secondary-button" disabled={evento.galeria.length >= evento.limite_galeria} onClick={() => elegirImagen("GALERIA")}>Agregar imagen</button></>}
      </section>}
      {ventanaAbierta === "galeria" && <VentanaGaleriaEvento evento={evento} alGuardar={alGuardar} alCerrar={() => setVentanaAbierta(null)} />}
      {imagenPendiente && <Ventana titulo="Cambiar imagen" alCerrar={() => { if (!subiendoPortada) setImagenPendiente(null); }}>
        {preview && <img className="evento-imagen-preview" src={preview} alt="Vista previa de la nueva imagen" />}
        {avisoError && <p className="form-error" role="alert">{avisoError}</p>}
        <div className="ventana-acciones"><button className="secondary-button" disabled={subiendoPortada} onClick={() => setImagenPendiente(null)}>Cancelar</button>
          <button className="action-button" disabled={subiendoPortada} onClick={() => void subirPortada(imagenPendiente)}>{subiendoPortada ? "Guardando..." : "Guardar imagen"}</button></div>
      </Ventana>}
      {ventanaAbierta === "datos" && (
        <VentanaDatosEvento evento={evento} alGuardar={alGuardar} alCerrar={() => setVentanaAbierta(null)} />
      )}
      {ventanaAbierta === "salon" && (
        <VentanaSalonEvento evento={evento} alGuardar={alGuardar} alCerrar={() => setVentanaAbierta(null)} />
      )}
    </main>
  );
}
