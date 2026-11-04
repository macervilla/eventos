import { Save } from "lucide-react";
import { FormEvent, useState } from "react";

import { api } from "../api/client";
import { tipografias, useFuentesGoogle } from "../data/tipografias";
import { eventTemplates } from "../templates/visualTemplates";
import { mensajeDeError } from "./EdicionProveedor";
import type { EncuadrePortada } from "./PortadaAjustable";
import { DatosLugar, lugarParaGuardar, SelectorLugar, validarLugar } from "./SelectorLugar";
import { Ventana } from "./Ventana";
import type { ConfigGaleria } from "./GaleriaEvento";
import { COLORES_TEXTOS_INICIALES, type ColoresTextos, type TextosPortada } from "./TextosPortada";

export type SalonResumen = {
  slug: string;
  nombre_comercial: string;
  direccion: string | null;
  localidad: string | null;
  provincia: string | null;
  pais: string | null;
  google_maps_url: string | null;
  latitud: number | null;
  longitud: number | null;
  portada_url: string | null;
};

export type ColoresEvento = { fondo: string; texto: string; acento: string };

export type Evento = {
  colores_textos?: ColoresTextos;
  textos_portada?: TextosPortada | null;
  geoname_id?: number | null;
  codigo_pais?: string | null;
  galeria_config: ConfigGaleria;
  titulo_visual: string | null;
  colores: ColoresEvento;
  modulos_habilitados: string[];
  galeria: { id: number; url: string }[];
  limite_galeria: number;
  id: number;
  nombre: string;
  slug: string;
  descripcion: string | null;
  fecha_inicio: string | null;
  template_key: string;
  tipografia: string;
  estado: string;
  confirmado: boolean;
  lugar_tipo: "salon" | "domicilio";
  portada_url: string | null;
  portada_encuadre: EncuadrePortada | null;
  localidad: string | null;
  provincia: string | null;
  pais: string | null;
  direccion: string | null;
  latitud: number | null;
  longitud: number | null;
  salon: SalonResumen | null;
};

type CamposEvento = {
  colores_textos: ColoresTextos;
  galeria_config: ConfigGaleria;
  titulo_visual: string;
  colores: ColoresEvento;
  modulos_habilitados: string[];
  descripcion: string;
  fecha: string;
  template_key: string;
  tipografia: string;
  lugar: DatosLugar;
};

type VentanaEventoProps = {
  evento: Evento;
  alGuardar: (evento: Evento) => void;
  alCerrar: () => void;
};

// datetime-local trabaja en hora local sin zona; el backend guarda en UTC.
export function fechaLocalAIso(valor: string) {
  // toISOString: convierte la fecha local a texto ISO en UTC
  return valor ? new Date(valor).toISOString() : null;
}

function isoAFechaLocal(valor: string | null) {
  if (!valor) return "";
  const fecha = new Date(valor);
  // getTimezoneOffset: minutos de diferencia con UTC; se compensa para mostrar la hora local
  const local = new Date(fecha.getTime() - fecha.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function guardarEvento(evento: Evento, campos: CamposEvento) {
  const payload = {
    colores_textos: campos.colores_textos,
    galeria_config: campos.galeria_config,
    titulo_visual: campos.titulo_visual.trim() || null,
    colores: campos.colores,
    modulos_habilitados: campos.modulos_habilitados.filter(m => m !== "invitados"),
    descripcion: campos.descripcion.trim() || null,
    fecha_inicio: fechaLocalAIso(campos.fecha),
    ...lugarParaGuardar(campos.lugar),
    template_key: campos.template_key,
    tipografia: campos.tipografia
  };
  return api.put<Evento>(`/eventos/${evento.slug}`, payload).then((r) => r.data);
}

function useFormularioEvento({ evento, alGuardar }: VentanaEventoProps) {
  const [campos, setCampos] = useState<CamposEvento>({
    colores_textos: evento.colores_textos ?? COLORES_TEXTOS_INICIALES,
    galeria_config: evento.galeria_config,
    titulo_visual: evento.titulo_visual ?? evento.nombre,
    colores: evento.colores,
    modulos_habilitados: evento.modulos_habilitados,
    descripcion: evento.descripcion ?? "",
    fecha: isoAFechaLocal(evento.fecha_inicio),
    template_key: evento.template_key,
    tipografia: evento.tipografia ?? "sistema",
    lugar: {
      geoname_id: evento.salon ? null : evento.geoname_id,
      codigo_pais: evento.salon ? null : evento.codigo_pais,
      lugar_tipo: evento.lugar_tipo,
      salon_slug: evento.salon?.slug ?? "",
      direccion: evento.salon ? "" : evento.direccion ?? "",
      localidad: evento.salon ? "" : evento.localidad ?? "",
      provincia: evento.salon ? "" : evento.provincia ?? "",
      pais: evento.salon ? "Argentina" : evento.pais ?? "Argentina",
      latitud: evento.salon ? null : evento.latitud,
      longitud: evento.salon ? null : evento.longitud
    }
  });
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cambiar = (clave: Exclude<keyof CamposEvento, "lugar" | "colores" | "colores_textos" | "modulos_habilitados" | "galeria_config">, valor: string) => {
    setCampos((actual) => ({ ...actual, [clave]: valor }));
    setError(null);
  };

  const cambiarLugar = (cambios: Partial<DatosLugar>) => {
    setCampos((actual) => ({ ...actual, lugar: { ...actual.lugar, ...cambios } }));
    setError(null);
  };

  const enviar = (e: FormEvent<HTMLFormElement>, validar: () => string | null) => {
    e.preventDefault();
    const problema = validar();
    if (problema) {
      setError(problema);
      return;
    }
    setGuardando(true);
    guardarEvento(evento, campos)
      .then(alGuardar)
      .catch((err) => setError(mensajeDeError(err)))
      .finally(() => setGuardando(false));
  };

  const cambiarColor = (clave: keyof ColoresEvento, valor: string) =>
    setCampos(actual => ({ ...actual, colores: { ...actual.colores, [clave]: valor } }));
  const cambiarColorTexto = (clave: keyof ColoresTextos, valor: string) =>
    setCampos(actual => ({ ...actual, colores_textos: { ...actual.colores_textos, [clave]: valor } }));
  const cambiarModulo = (clave: string, activo: boolean) =>
    setCampos(actual => ({ ...actual, modulos_habilitados: activo
      ? [...actual.modulos_habilitados, clave] : actual.modulos_habilitados.filter(m => m !== clave) }));
  const cambiarGaleria = (cambios: Partial<ConfigGaleria>) => {
    setCampos(actual => ({ ...actual, galeria_config: { ...actual.galeria_config, ...cambios } }));
    setError(null);
  };
  return { campos, cambiar, cambiarColor, cambiarColorTexto, cambiarModulo, cambiarGaleria, cambiarLugar, enviar, guardando, error };
}

function Pie({ guardando, error, alCerrar }: { guardando: boolean; error: string | null; alCerrar: () => void }) {
  return (
    <>
      {error && <p className="form-error wide">{error}</p>}
      <div className="ventana-acciones wide">
        <button className="secondary-button" type="button" disabled={guardando} onClick={alCerrar}>
          Cancelar
        </button>
        <button className="action-button" type="submit" disabled={guardando}>
          <Save size={18} aria-hidden="true" />
          {guardando ? "Guardando..." : "Guardar"}
        </button>
      </div>
    </>
  );
}

export function VentanaDatosEvento(props: VentanaEventoProps) {
  const { campos, cambiar, cambiarColor, cambiarColorTexto, cambiarModulo, enviar, guardando, error } = useFormularioEvento(props);
  const validar = () => (campos.titulo_visual.trim().length > 180 ? "El titulo admite hasta 180 caracteres." : null);
  // Se cargan todas las fuentes para que cada opcion se vea con su tipografia real.
  useFuentesGoogle(Object.keys(tipografias));

  return (
    <Ventana titulo="Datos del evento" alCerrar={() => { if (!guardando) props.alCerrar(); }}>
      <form className="ventana-formulario" onSubmit={(e) => enviar(e, validar)} noValidate>
        <label className="wide">
          Titulo visual de la invitacion
          <input maxLength={180} value={campos.titulo_visual} onChange={(e) => cambiar("titulo_visual", e.target.value)} />
          <small>Nombre original: {props.evento.nombre}. URL: /e/{props.evento.slug}. Son permanentes.</small>
        </label>
        <label>
          Fecha y hora
          <input type="datetime-local" value={campos.fecha} onChange={(e) => cambiar("fecha", e.target.value)} />
        </label>
        <label>
          Estilo de la pagina
          <select value={campos.template_key} onChange={(e) => cambiar("template_key", e.target.value)}>
            {Object.entries(eventTemplates).map(([clave, item]) => (
              <option key={clave} value={clave}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="wide">
          Descripcion
          <textarea value={campos.descripcion} onChange={(e) => cambiar("descripcion", e.target.value)} />
        </label>
        <fieldset className="wide evento-colores">
          <legend>Colores de la pagina</legend>
          {([['fondo', 'Fondo'], ['texto', 'Texto'], ['acento', 'Acento']] as const).map(([clave, etiqueta]) =>
            <label key={clave}>{etiqueta}<input type="color" value={campos.colores[clave]} onChange={e => cambiarColor(clave, e.target.value)} /></label>)}
        </fieldset>
        <fieldset className="wide evento-modulos">
          <legend>Modulos habilitados</legend>
          {([['detalles', 'Detalles y descripcion'], ['ubicacion', 'Lugar y mapa'], ['galeria', 'Galeria de imagenes']] as const).map(([clave, etiqueta]) =>
            <label key={clave}><input type="checkbox" checked={campos.modulos_habilitados.includes(clave)} onChange={e => cambiarModulo(clave, e.target.checked)} />{etiqueta}</label>)}
        </fieldset>
        <fieldset className="selector-tipografia wide">
          <legend>Tipografia de la invitacion</legend>
          <div>
            {Object.entries(tipografias).map(([clave, tipografia]) => (
              <button
                aria-pressed={campos.tipografia === clave}
                className={campos.tipografia === clave ? "opcion-tipografia activa" : "opcion-tipografia"}
                key={clave}
                type="button"
                onClick={() => cambiar("tipografia", clave)}
              >
                <strong style={{ fontFamily: tipografia.titulo, fontWeight: tipografia.pesoTitulo === "inherit" ? 700 : tipografia.pesoTitulo }}>
                  {campos.titulo_visual.trim().slice(0, 22) || "Mi evento"}
                </strong>
                <span style={{ fontFamily: tipografia.texto }}>{tipografia.label} · Texto de ejemplo</span>
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset className="wide paleta-textos-evento">
          <legend>Colores de los textos de la invitacion</legend>
          {([['titulo', 'Titulo'], ['fecha', 'Fecha y hora'], ['lugar', 'Lugar']] as const).map(([clave, etiqueta]) =>
            <div className="paleta-texto" key={clave}>
              <label>{etiqueta}<input type="color" value={campos.colores_textos[clave]} onChange={e => cambiarColorTexto(clave, e.target.value)} /></label>
              <div className="paleta-muestras" role="group" aria-label={`Paleta para ${etiqueta.toLowerCase()}`}>
                {([['#ffffff', 'Blanco'], ['#18212f', 'Oscuro'], ['#f6c453', 'Dorado'], ['#ef4444', 'Rojo'], ['#f472b6', 'Rosa'], ['#8b5cf6', 'Violeta'], ['#38bdf8', 'Celeste'], ['#34d399', 'Verde']] as const).map(([color, nombre]) =>
                  <button key={color} type="button" title={nombre} aria-label={`${nombre} para ${etiqueta.toLowerCase()}`} aria-pressed={campos.colores_textos[clave].toLowerCase() === color}
                    style={{ backgroundColor: color }} onClick={() => cambiarColorTexto(clave, color)} />)}
              </div>
              <span className="paleta-vista-previa" style={{ color: campos.colores_textos[clave],
                backgroundColor: [1, 3, 5].reduce((suma, inicio) => suma + parseInt(campos.colores_textos[clave].slice(inicio, inicio + 2), 16), 0) > 384 ? "#334155" : "#f1f5f9",
                fontFamily: tipografias[campos.tipografia as keyof typeof tipografias]?.titulo }}>
                {clave === 'titulo' ? campos.titulo_visual || 'Mi evento' : etiqueta}
              </span>
            </div>)}
          <p>Elegí una muestra o un color personalizado. Se aplica a la portada y a la foto enviada de la invitacion.</p>
        </fieldset>
        <Pie guardando={guardando} error={error} alCerrar={props.alCerrar} />
      </form>
    </Ventana>
  );
}

export function VentanaSalonEvento(props: VentanaEventoProps) {
  const { campos, cambiarLugar, enviar, guardando, error } = useFormularioEvento(props);

  return (
    <Ventana titulo="Lugar del evento" alCerrar={() => { if (!guardando) props.alCerrar(); }}>
      <form className="ventana-formulario" onSubmit={(e) => enviar(e, () => validarLugar(campos.lugar))} noValidate>
        <SelectorLugar valor={campos.lugar} alCambiar={cambiarLugar} />
        <Pie guardando={guardando} error={error} alCerrar={props.alCerrar} />
      </form>
    </Ventana>
  );
}

export function VentanaGaleriaEvento(props: VentanaEventoProps) {
  const { campos, cambiarGaleria, cambiarModulo, enviar, guardando, error } = useFormularioEvento(props);
  const config = campos.galeria_config;
  const validar = () => {
    if (config.modo === "grilla" && (!Number.isInteger(config.filas) || !Number.isInteger(config.columnas)
      || config.filas < 1 || config.columnas < 1 || config.filas * config.columnas > 10))
      return "Elegi filas y columnas con un maximo de 10 espacios por pagina.";
    return null;
  };
  return <Ventana titulo="Configurar imagenes de la invitacion" alCerrar={() => { if (!guardando) props.alCerrar(); }}>
    <form className="ventana-formulario" onSubmit={e => enviar(e, validar)}>
      <label className="wide galeria-visible"><input type="checkbox" checked={campos.modulos_habilitados.includes("galeria")}
        onChange={e => cambiarModulo("galeria", e.target.checked)} /> Mostrar imagenes en la invitacion publica</label>
      <label className="wide">Presentacion
        <select value={config.modo} onChange={e => cambiarGaleria({ modo: e.target.value as ConfigGaleria["modo"] })}>
          <option value="grilla">Grilla de imagenes</option><option value="carrusel">Carrusel</option>
        </select>
      </label>
      {config.modo === "grilla" ? <>
        <label>Filas por pagina<input type="number" min={1} max={10} step={1} value={config.filas} onChange={e => cambiarGaleria({ filas: Number(e.target.value) })} /></label>
        <label>Columnas<input type="number" min={1} max={10} step={1} value={config.columnas} onChange={e => cambiarGaleria({ columnas: Number(e.target.value) })} /></label>
        <p className="wide">{config.filas * config.columnas} espacios por pagina (hasta 10). Si hay mas imagenes, se pueden recorrer con Anterior y Siguiente. En celulares se ajustan las columnas al ancho disponible.</p>
      </> : <p className="wide">Una imagen por vez, con flechas, indicadores y deslizamiento en celulares.</p>}
      <p className="wide">Hasta 10 imagenes. Al agregar una imagen, la galeria se habilita automaticamente en la invitacion.</p>
      <Pie guardando={guardando} error={error} alCerrar={props.alCerrar} />
    </form>
  </Ventana>;
}
