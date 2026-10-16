import { Save } from "lucide-react";
import { FormEvent, useState } from "react";

import { api } from "../api/client";
import { tipografias, useFuentesGoogle } from "../data/tipografias";
import { eventTemplates } from "../templates/visualTemplates";
import { mensajeDeError } from "./EdicionProveedor";
import type { EncuadrePortada } from "./PortadaAjustable";
import { DatosLugar, lugarParaGuardar, SelectorLugar, validarLugar } from "./SelectorLugar";
import { Ventana } from "./Ventana";

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

export type Evento = {
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
  nombre: string;
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
    nombre: campos.nombre.trim(),
    slug: evento.slug,
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
    nombre: evento.nombre,
    descripcion: evento.descripcion ?? "",
    fecha: isoAFechaLocal(evento.fecha_inicio),
    template_key: evento.template_key,
    tipografia: evento.tipografia ?? "sistema",
    lugar: {
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

  const cambiar = (clave: Exclude<keyof CamposEvento, "lugar">, valor: string) => {
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

  return { campos, cambiar, cambiarLugar, enviar, guardando, error };
}

function Pie({ guardando, error, alCerrar }: { guardando: boolean; error: string | null; alCerrar: () => void }) {
  return (
    <>
      {error && <p className="form-error wide">{error}</p>}
      <div className="ventana-acciones wide">
        <button className="secondary-button" type="button" onClick={alCerrar}>
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
  const { campos, cambiar, enviar, guardando, error } = useFormularioEvento(props);
  const validar = () => (campos.nombre.trim().length < 2 ? "Carga el nombre del evento." : null);
  // Se cargan todas las fuentes para que cada opcion se vea con su tipografia real.
  useFuentesGoogle(Object.keys(tipografias));

  return (
    <Ventana titulo="Datos del evento" alCerrar={props.alCerrar}>
      <form className="ventana-formulario" onSubmit={(e) => enviar(e, validar)} noValidate>
        <label className="wide">
          Nombre del evento
          <input value={campos.nombre} onChange={(e) => cambiar("nombre", e.target.value)} />
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
                  {campos.nombre.trim().slice(0, 22) || "Mi evento"}
                </strong>
                <span style={{ fontFamily: tipografia.texto }}>{tipografia.label} · Texto de ejemplo</span>
              </button>
            ))}
          </div>
        </fieldset>
        <Pie guardando={guardando} error={error} alCerrar={props.alCerrar} />
      </form>
    </Ventana>
  );
}

export function VentanaSalonEvento(props: VentanaEventoProps) {
  const { campos, cambiarLugar, enviar, guardando, error } = useFormularioEvento(props);

  return (
    <Ventana titulo="Lugar del evento" alCerrar={props.alCerrar}>
      <form className="ventana-formulario" onSubmit={(e) => enviar(e, () => validarLugar(campos.lugar))} noValidate>
        <SelectorLugar valor={campos.lugar} alCambiar={cambiarLugar} />
        <Pie guardando={guardando} error={error} alCerrar={props.alCerrar} />
      </form>
    </Ventana>
  );
}
