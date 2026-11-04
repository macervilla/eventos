import { Building2, Home, LocateFixed, Search } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { Proveedor } from "../types/proveedores";
import { urlMapaEmbebido } from "./EdicionProveedor";
import { MapaUbicacion } from "./MapaUbicacion";
import { LocalidadAutocomplete } from "./LocalidadAutocomplete";

export type DatosLugar = {
  geoname_id?: number | null;
  codigo_pais?: string | null;
  lugar_tipo: "salon" | "domicilio";
  salon_slug: string;
  direccion: string;
  localidad: string;
  provincia: string;
  pais: string;
  latitud: number | null;
  longitud: number | null;
};

type ResultadoBusqueda = { latitud: number; longitud: number; nombre: string };

export const LUGAR_VACIO: DatosLugar = {
  lugar_tipo: "salon",
  salon_slug: "",
  direccion: "",
  localidad: "",
  provincia: "",
  pais: "Argentina",
  latitud: null,
  longitud: null
};

export function validarLugar(lugar: DatosLugar): string | null {
  if (lugar.lugar_tipo === "salon") return lugar.salon_slug ? null : "Elegi el salon del evento.";
  if (!lugar.direccion.trim() || !lugar.localidad.trim() || (!lugar.provincia.trim() && !lugar.geoname_id) || !lugar.pais.trim()) {
    return "Completa direccion, localidad, provincia y pais.";
  }
  return null;
}

/** Datos del lugar tal como los espera el backend. */
export function lugarParaGuardar(lugar: DatosLugar) {
  if (lugar.lugar_tipo === "salon") return { lugar_tipo: "salon", salon_slug: lugar.salon_slug };
  return {
    lugar_tipo: "domicilio",
    salon_slug: null,
    direccion: lugar.direccion.trim(),
    localidad: lugar.localidad.trim(),
    provincia: lugar.provincia.trim(),
    pais: lugar.pais.trim(),
    latitud: lugar.latitud,
    longitud: lugar.longitud,
    geoname_id: lugar.geoname_id ?? null,
    codigo_pais: lugar.codigo_pais ?? null
  };
}

type SelectorLugarProps = {
  valor: DatosLugar;
  alCambiar: (cambios: Partial<DatosLugar>) => void;
};

export function SelectorLugar({ valor, alCambiar }: SelectorLugarProps) {
  const [salones, setSalones] = useState<Proveedor[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [resultados, setResultados] = useState<ResultadoBusqueda[]>([]);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Proveedor[]>("/proveedores", { params: { categoria: "salon" } })
      .then((response) => setSalones(response.data))
      .catch(() => setSalones([]));
  }, []);

  const elegido = salones.find((salon) => salon.slug === valor.salon_slug);
  const mapaSalon = elegido ? urlMapaEmbebido(elegido) : null;

  const ubicarDireccion = () => {
    const consulta = valor.localidad.trim();
    if (consulta.length < 3) {
      setAviso("Elegi o escribi una localidad para centrar el mapa.");
      return;
    }
    setBuscando(true);
    setAviso(null);
    setResultados([]);
    const peticion = valor.geoname_id
      ? api.get(`/geografia/localidades/${valor.geoname_id}`).then(r => [r.data])
      : api.get("/geografia/localidades", { params: { q: consulta, codigo_pais: valor.codigo_pais || undefined } }).then(r => r.data.resultados);
    peticion.then((localidades: Array<{ localidad: string; provincia: string; pais: string; latitud: number; longitud: number }>) => ({ data: localidades.map(r => ({
      latitud: r.latitud, longitud: r.longitud, nombre: [r.localidad, r.provincia, r.pais].filter(Boolean).join(", ")
    })) }))
      .then(({ data }) => {
        if (data.length === 0) {
          setAviso("No encontramos esa localidad. Ubica el punto haciendo clic en el mapa.");
          return;
        }
        if (data.length > 1) {
          setResultados(data);
          setAviso("Hay varias localidades. Elegi una para centrar el mapa.");
        } else {
          alCambiar({ latitud: data[0].latitud, longitud: data[0].longitud });
          setAviso("El mapa muestra el centro de la localidad. Ajusta el marcador a la direccion exacta.");
        }
      })
      .catch(() => setAviso("No se pudo consultar el mapa. Ubica el punto haciendo clic en el mapa."))
      .finally(() => setBuscando(false));
  };

  const usarUbicacionActual = () => {
    if (!navigator.geolocation) {
      setAviso("Este navegador no permite obtener la ubicacion.");
      return;
    }
    setAviso(null);
    // getCurrentPosition: pide permiso y devuelve la ubicacion del dispositivo
    navigator.geolocation.getCurrentPosition(
      (posicion) => alCambiar({ latitud: posicion.coords.latitude, longitud: posicion.coords.longitude }),
      () => setAviso("No se pudo obtener tu ubicacion. Revisa el permiso del navegador."),
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  return (
    <div className="selector-lugar wide">
      <div className="selector-lugar-tipos" role="radiogroup" aria-label="Tipo de lugar">
        <button
          aria-checked={valor.lugar_tipo === "salon"}
          className={valor.lugar_tipo === "salon" ? "activo" : undefined}
          role="radio"
          type="button"
          onClick={() => alCambiar({ lugar_tipo: "salon" })}
        >
          <Building2 size={18} aria-hidden="true" /> Salon registrado
        </button>
        <button
          aria-checked={valor.lugar_tipo === "domicilio"}
          className={valor.lugar_tipo === "domicilio" ? "activo" : undefined}
          role="radio"
          type="button"
          onClick={() => alCambiar({ lugar_tipo: "domicilio" })}
        >
          <Home size={18} aria-hidden="true" /> Mi casa
        </button>
      </div>

      {valor.lugar_tipo === "salon" ? (
        <>
          <label>
            Salon
            <select value={valor.salon_slug} onChange={(e) => alCambiar({ salon_slug: e.target.value })}>
              <option value="">Elegi un salon...</option>
              {salones.map((salon) => (
                <option key={salon.slug} value={salon.slug}>
                  {salon.nombre_comercial}
                  {salon.localidad ? ` — ${salon.localidad}` : ""}
                </option>
              ))}
            </select>
            {salones.length === 0 && (
              <span className="form-hint">Todavia no hay salones registrados. Podes elegir "Mi casa".</span>
            )}
          </label>
          {elegido && (
            <div className="salon-elegido">
              <Building2 size={20} aria-hidden="true" />
              <div>
                <strong>{elegido.nombre_comercial}</strong>
                <span>
                  {[elegido.direccion, elegido.localidad, elegido.provincia].filter(Boolean).join(", ")}
                </span>
              </div>
            </div>
          )}
          {mapaSalon && <iframe className="mapa-embebido" src={mapaSalon} title="Mapa del salon" loading="lazy" />}
        </>
      ) : (
        <>
          <div className="selector-lugar-campos">
            <label className="wide">
              Direccion
              <input
                value={valor.direccion}
                placeholder="Calle y numero"
                onChange={(e) => alCambiar({ direccion: e.target.value })}
              />
            </label>
            <LocalidadAutocomplete preservarPin valor={valor} alCambiar={geo => alCambiar({
              localidad: geo.localidad, provincia: geo.provincia, pais: geo.pais,
              geoname_id: geo.geoname_id, codigo_pais: geo.codigo_pais,
              latitud: geo.latitud ?? null, longitud: geo.longitud ?? null
            })} />
          </div>
          <div className="selector-lugar-acciones">
            <button className="secondary-button" type="button" onClick={ubicarDireccion} disabled={buscando}>
              <Search size={18} aria-hidden="true" />
              {buscando ? "Buscando..." : "Ubicar localidad en el mapa"}
            </button>
            <button className="secondary-button" type="button" onClick={usarUbicacionActual}>
              <LocateFixed size={18} aria-hidden="true" />
              Usar mi ubicacion actual
            </button>
          </div>
          {resultados.length > 1 && (
            <label>
              Encontramos varias coincidencias
              <select
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value === "") return;
                  const resultado = resultados[Number(e.target.value)];
                  alCambiar({ latitud: resultado.latitud, longitud: resultado.longitud });
                }}
              >
                <option value="" disabled>Elegi una localidad</option>
                {resultados.map((resultado, indice) => (
                  <option key={resultado.nombre} value={indice}>
                    {resultado.nombre}
                  </option>
                ))}
              </select>
            </label>
          )}
          {aviso && <p className="form-error">{aviso}</p>}
          <MapaUbicacion
            latitud={valor.latitud}
            longitud={valor.longitud}
            alCambiar={(latitud, longitud) => alCambiar({ latitud, longitud })}
          />
          <p className="form-hint">
            {valor.latitud !== null
              ? "Arrastra el marcador o hace clic en el mapa para ajustar el punto exacto."
              : "Hace clic en el mapa para fijar la ubicacion exacta (opcional)."}
          </p>
        </>
      )}
    </div>
  );
}
