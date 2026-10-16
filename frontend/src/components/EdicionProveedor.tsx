import axios from "axios";
import { MapPin, Save } from "lucide-react";
import { FormEvent, useState } from "react";

import { api } from "../api/client";
import { categoryOptions } from "../data/categoriasProveedor";
import { providerTemplates } from "../templates/visualTemplates";
import { Proveedor } from "../types/proveedores";
import { Ventana } from "./Ventana";

type CamposEditables = {
  nombre_comercial: string;
  descripcion: string;
  horarios: string;
  categorias: string[];
  whatsapp: string;
  telefono: string;
  email: string;
  web: string;
  instagram: string;
  facebook: string;
  template_key: string;
  provincia: string;
  localidad: string;
  direccion: string;
  ubicacion_referencia: string;
  google_maps_url: string;
};

type VentanaEdicionProps = {
  proveedor: Proveedor;
  alGuardar: (proveedor: Proveedor) => void;
  alCerrar: () => void;
};

const vacioANull = (valor: string | null | undefined) => {
  const limpio = (valor ?? "").trim();
  return limpio === "" ? null : limpio;
};

function camposDesde(proveedor: Proveedor): CamposEditables {
  return {
    nombre_comercial: proveedor.nombre_comercial,
    descripcion: proveedor.descripcion ?? "",
    horarios: proveedor.horarios ?? "",
    categorias: proveedor.categorias,
    whatsapp: proveedor.whatsapp ?? "",
    telefono: proveedor.telefono ?? "",
    email: proveedor.email ?? "",
    web: proveedor.web ?? "",
    instagram: proveedor.instagram ?? "",
    facebook: proveedor.facebook ?? "",
    template_key: proveedor.template_key ?? "professional",
    provincia: proveedor.provincia ?? "",
    localidad: proveedor.localidad ?? "",
    direccion: proveedor.direccion ?? "",
    ubicacion_referencia: proveedor.ubicacion_referencia ?? "",
    google_maps_url: proveedor.google_maps_url ?? ""
  };
}

// El PUT espera el proveedor completo: se parte de lo guardado y se pisan los campos editados.
function guardarProveedor(proveedor: Proveedor, campos: CamposEditables) {
  const payload = {
    nombre_comercial: campos.nombre_comercial.trim(),
    slug: proveedor.slug,
    cuit: proveedor.cuit ?? null,
    descripcion: vacioANull(campos.descripcion),
    categorias: campos.categorias,
    pais: proveedor.pais,
    provincia: campos.provincia.trim(),
    localidad: campos.localidad.trim(),
    direccion: campos.direccion.trim(),
    google_maps_url: vacioANull(campos.google_maps_url),
    google_place_id: proveedor.google_place_id ?? null,
    ubicacion_referencia: vacioANull(campos.ubicacion_referencia),
    latitud: proveedor.latitud ?? null,
    longitud: proveedor.longitud ?? null,
    whatsapp: vacioANull(campos.whatsapp),
    telefono: vacioANull(campos.telefono),
    email: campos.email.trim(),
    web: vacioANull(campos.web),
    instagram: vacioANull(campos.instagram),
    facebook: vacioANull(campos.facebook),
    logo_url: proveedor.logo_url ?? null,
    portada_url: proveedor.portada_url ?? null,
    horarios: vacioANull(campos.horarios),
    template_key: campos.template_key,
    plan: proveedor.plan
  };
  return api.put<Proveedor>(`/proveedores/${proveedor.slug}`, payload).then((r) => r.data);
}

export function mensajeDeError(error: unknown) {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 401) return "Tu sesion vencio. Volve a ingresar.";
    if (error.response?.status === 403) return "No administras este proveedor.";
    const detalle = error.response?.data?.detail;
    if (Array.isArray(detalle) && detalle.length) {
      return detalle
        .map((item) => {
          const campo = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "";
          const texto = String(item.msg ?? "Dato invalido").replace(/^Value error, /, "");
          return campo && campo !== "body" ? `${campo}: ${texto}` : texto;
        })
        .join(" · ");
    }
    if (typeof detalle === "string") return detalle;
    if (!error.response) return "No se pudo conectar con el backend.";
  }
  return "No se pudo guardar. Revisa los datos.";
}

export function urlMapaEmbebido(datos: {
  latitud?: number | null;
  longitud?: number | null;
  direccion?: string | null;
  localidad?: string | null;
  provincia?: string | null;
  pais?: string | null;
}) {
  const consulta =
    datos.latitud != null && datos.longitud != null
      ? `${datos.latitud},${datos.longitud}`
      : [datos.direccion, datos.localidad, datos.provincia, datos.pais].filter(Boolean).join(", ");
  if (!consulta) return null;
  // encodeURIComponent: escapa la consulta para usarla dentro de una URL
  return `https://maps.google.com/maps?q=${encodeURIComponent(consulta)}&z=16&output=embed`;
}

function useFormularioEdicion({ proveedor, alGuardar }: VentanaEdicionProps) {
  const [campos, setCampos] = useState<CamposEditables>(() => camposDesde(proveedor));
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cambiar = (clave: keyof CamposEditables, valor: string | string[]) => {
    setCampos((actual) => ({ ...actual, [clave]: valor }));
    setError(null);
  };

  const enviar = (evento: FormEvent<HTMLFormElement>, validar: () => string | null) => {
    evento.preventDefault();
    const problema = validar();
    if (problema) {
      setError(problema);
      return;
    }
    setGuardando(true);
    guardarProveedor(proveedor, campos)
      .then(alGuardar)
      .catch((err) => setError(mensajeDeError(err)))
      .finally(() => setGuardando(false));
  };

  return { campos, cambiar, enviar, guardando, error };
}

function PieFormulario({ guardando, error, alCerrar }: { guardando: boolean; error: string | null; alCerrar: () => void }) {
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

export function VentanaDatos(props: VentanaEdicionProps) {
  const { campos, cambiar, enviar, guardando, error } = useFormularioEdicion(props);

  const validar = () => {
    if (campos.nombre_comercial.trim().length < 2) return "Carga un nombre comercial.";
    if (campos.categorias.length === 0) return "Selecciona al menos una categoria.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(campos.email.trim())) return "Carga un email valido.";
    if (campos.web.trim() && !/^https?:\/\//.test(campos.web.trim())) {
      return "La web debe empezar con http:// o https://";
    }
    return null;
  };

  const alternarCategoria = (slug: string) =>
    cambiar(
      "categorias",
      campos.categorias.includes(slug)
        ? campos.categorias.filter((item) => item !== slug)
        : [...campos.categorias, slug]
    );

  return (
    <Ventana titulo="Datos del negocio" alCerrar={props.alCerrar}>
      <form className="ventana-formulario" onSubmit={(e) => enviar(e, validar)} noValidate>
        <label className="wide">
          Nombre comercial
          <input value={campos.nombre_comercial} onChange={(e) => cambiar("nombre_comercial", e.target.value)} />
        </label>
        <label className="wide">
          Descripcion
          <textarea value={campos.descripcion} onChange={(e) => cambiar("descripcion", e.target.value)} />
        </label>
        <label className="wide">
          Horarios
          <input
            value={campos.horarios}
            placeholder="Lunes a sabado de 9 a 18"
            onChange={(e) => cambiar("horarios", e.target.value)}
          />
        </label>
        <div className="wide">
          <div className="field-heading">Categorias</div>
          <div className="category-grid">
            {categoryOptions.map((categoria) => (
              <button
                className={campos.categorias.includes(categoria.slug) ? "category-option selected" : "category-option"}
                key={categoria.slug}
                type="button"
                onClick={() => alternarCategoria(categoria.slug)}
              >
                {categoria.label}
              </button>
            ))}
          </div>
        </div>
        <label>
          Email
          <input type="email" value={campos.email} onChange={(e) => cambiar("email", e.target.value)} />
        </label>
        <label>
          WhatsApp
          <input
            inputMode="tel"
            value={campos.whatsapp}
            placeholder="5492966123456"
            onChange={(e) => cambiar("whatsapp", e.target.value)}
          />
        </label>
        <label>
          Telefono
          <input inputMode="tel" value={campos.telefono} onChange={(e) => cambiar("telefono", e.target.value)} />
        </label>
        <label>
          Instagram
          <input value={campos.instagram} placeholder="@minegocio" onChange={(e) => cambiar("instagram", e.target.value)} />
        </label>
        <label>
          Facebook
          <input value={campos.facebook} onChange={(e) => cambiar("facebook", e.target.value)} />
        </label>
        <label>
          Web
          <input value={campos.web} placeholder="https://..." onChange={(e) => cambiar("web", e.target.value)} />
        </label>
        <label className="wide">
          Estilo de la pagina
          <select value={campos.template_key} onChange={(e) => cambiar("template_key", e.target.value)}>
            {Object.entries(providerTemplates).map(([clave, template]) => (
              <option key={clave} value={clave}>
                {template.label}
              </option>
            ))}
          </select>
        </label>
        <PieFormulario guardando={guardando} error={error} alCerrar={props.alCerrar} />
      </form>
    </Ventana>
  );
}

export function VentanaUbicacion(props: VentanaEdicionProps) {
  const { campos, cambiar, enviar, guardando, error } = useFormularioEdicion(props);

  const validar = () => {
    if (!campos.provincia.trim() || !campos.localidad.trim() || !campos.direccion.trim()) {
      return "Provincia, localidad y direccion son obligatorias.";
    }
    const enlace = campos.google_maps_url.trim();
    if (enlace) {
      try {
        const host = new URL(enlace).hostname;
        if (!host.includes("google.") && host !== "maps.app.goo.gl") return "Debe ser un enlace de Google Maps.";
      } catch {
        return "Debe ser un enlace de Google Maps.";
      }
    }
    return null;
  };

  const direccionCompleta = [campos.direccion, campos.localidad, campos.provincia, props.proveedor.pais]
    .filter(Boolean)
    .join(", ");
  const vistaPrevia = urlMapaEmbebido({
    direccion: campos.direccion,
    localidad: campos.localidad,
    provincia: campos.provincia,
    pais: props.proveedor.pais
  });

  return (
    <Ventana titulo="Ubicacion" alCerrar={props.alCerrar}>
      <form className="ventana-formulario" onSubmit={(e) => enviar(e, validar)} noValidate>
        <label>
          Provincia
          <input value={campos.provincia} onChange={(e) => cambiar("provincia", e.target.value)} />
        </label>
        <label>
          Localidad
          <input value={campos.localidad} onChange={(e) => cambiar("localidad", e.target.value)} />
        </label>
        <label className="wide">
          Direccion
          <input value={campos.direccion} onChange={(e) => cambiar("direccion", e.target.value)} />
        </label>
        <label className="wide">
          Referencia
          <input
            value={campos.ubicacion_referencia}
            placeholder="Frente a la plaza principal"
            onChange={(e) => cambiar("ubicacion_referencia", e.target.value)}
          />
        </label>
        {vistaPrevia && (
          <iframe className="mapa-embebido wide" src={vistaPrevia} title="Vista previa del mapa" loading="lazy" />
        )}
        <label className="wide">
          Enlace de Google Maps (opcional, marca el punto exacto)
          <input
            value={campos.google_maps_url}
            placeholder="https://maps.app.goo.gl/..."
            onChange={(e) => cambiar("google_maps_url", e.target.value)}
          />
        </label>
        <a
          className="secondary-link wide"
          href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(direccionCompleta)}`}
          target="_blank"
          rel="noreferrer"
        >
          <MapPin size={18} aria-hidden="true" />
          Buscar en Google Maps y copiar el enlace "Compartir"
        </a>
        <PieFormulario guardando={guardando} error={error} alCerrar={props.alCerrar} />
      </form>
    </Ventana>
  );
}
