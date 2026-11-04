import axios from "axios";
import { useEffect, useId, useRef, useState } from "react";

import { api } from "../api/client";

export type GeografiaValor = {
  localidad: string; provincia: string; pais: string;
  geoname_id?: number | null; codigo_pais?: string | null;
  latitud?: number | null; longitud?: number | null;
};
type Localidad = GeografiaValor & { geoname_id: number; codigo_pais: string; latitud: number; longitud: number };

export function LocalidadAutocomplete({ valor, alCambiar, compacto = false, preservarPin = false }: {
  valor: GeografiaValor; alCambiar: (valor: GeografiaValor) => void; compacto?: boolean; preservarPin?: boolean;
}) {
  const id = useId();
  const [manual, setManual] = useState(false);
  const [abierto, setAbierto] = useState(false);
  const [resultados, setResultados] = useState<Localidad[]>([]);
  const [activo, setActivo] = useState(-1);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [consultado, setConsultado] = useState(false);
  const secuencia = useRef(0);
  const contenedor = useRef<HTMLDivElement>(null);
  const centroAnterior = useRef<{ latitud: number; longitud: number } | null>(null);

  useEffect(() => {
    const numero = ++secuencia.current;
    const controller = new AbortController();
    setResultados([]); setActivo(-1); setError(""); setConsultado(false); setCargando(false);
    const q = valor.localidad.trim();
    if (manual || !abierto || valor.geoname_id || q.length < 3) return () => controller.abort();
    setCargando(true);
    const timer = window.setTimeout(() => {
      api.get<{ resultados: Localidad[] }>("/geografia/localidades", { params: { q, limit: 10 }, signal: controller.signal })
        .then(({ data }) => { if (numero === secuencia.current && !controller.signal.aborted) { setResultados(data.resultados); setConsultado(true); } })
        .catch(err => { if (!axios.isCancel(err) && numero === secuencia.current && !controller.signal.aborted) setError("No se pudo consultar el catalogo. Podes usar la carga manual."); })
        .finally(() => { if (numero === secuencia.current && !controller.signal.aborted) setCargando(false); });
    }, 300);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [valor.localidad, valor.geoname_id, abierto, manual]);

  const elegir = (lugar: Localidad) => {
    ++secuencia.current;
    const eraCentro = centroAnterior.current?.latitud === valor.latitud && centroAnterior.current?.longitud === valor.longitud;
    const conservar = preservarPin && !eraCentro && valor.latitud != null && valor.longitud != null;
    alCambiar({ ...lugar, ...(conservar ? { latitud: valor.latitud, longitud: valor.longitud } : {}) });
    centroAnterior.current = { latitud: lugar.latitud, longitud: lugar.longitud };
    setResultados([]); setAbierto(false); setCargando(false); setError("");
  };
  const mostrar = abierto && !manual && resultados.length > 0;
  return <div className={`geo-selector${compacto ? " geo-compacto" : ""}`} ref={contenedor}
    onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setAbierto(false); }}>
    <div className="geo-combobox">
      <label htmlFor={id}>Localidad</label>
      <input id={id} role="combobox" autoComplete="off" aria-autocomplete="list" aria-expanded={mostrar}
        aria-controls={`${id}-lista`} aria-activedescendant={mostrar && activo >= 0 ? `${id}-${activo}` : undefined}
        aria-describedby={`${id}-ayuda`} value={valor.localidad} placeholder="Escribi al menos 3 caracteres"
        onFocus={() => setAbierto(true)}
        onChange={e => { alCambiar({ ...valor, localidad: e.target.value, geoname_id: null, codigo_pais: null,
          ...(!preservarPin ? { latitud: null, longitud: null } : {}) }); setAbierto(true); }}
        onKeyDown={e => {
          if (e.key === "Escape") { e.preventDefault(); setAbierto(false); }
          if (!mostrar) return;
          if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); setActivo(i => i < 0 ? (e.key === "ArrowDown" ? 0 : resultados.length - 1) : (i + (e.key === "ArrowDown" ? 1 : -1) + resultados.length) % resultados.length); }
          if (e.key === "Enter") { e.preventDefault(); if (activo >= 0) elegir(resultados[activo]); }
        }} />
      {mostrar && <ul id={`${id}-lista`} role="listbox" className="geo-sugerencias" aria-label="Localidades encontradas">
        {resultados.map((r, i) => <li id={`${id}-${i}`} key={r.geoname_id} role="option" aria-selected={i === activo}
          className={i === activo ? "activo" : ""} onMouseDown={e => e.preventDefault()} onClick={() => elegir(r)}>
          <strong>{r.localidad}</strong><span>{[r.provincia, r.pais].filter(Boolean).join(", ")}</span>
        </li>)}
      </ul>}
    </div>
    {!compacto && <div className="geo-contexto">
      <label>Provincia / estado<input value={valor.provincia} readOnly={!manual} onChange={e => alCambiar({ ...valor, provincia: e.target.value, geoname_id: null, codigo_pais: null })} /></label>
      <label>Pais<input value={valor.pais} readOnly={!manual} onChange={e => alCambiar({ ...valor, pais: e.target.value, geoname_id: null, codigo_pais: null })} /></label>
    </div>}
    <p id={`${id}-ayuda`} className="geo-ayuda" role="status">
      {cargando ? "Buscando localidades..." : error || (valor.geoname_id ? [valor.localidad, valor.provincia, valor.pais].filter(Boolean).join(", ") :
        manual ? "Carga manual: esta localidad se guarda sin identificador GeoNames." :
        consultado && !resultados.length ? "No hay coincidencias. Proba otro nombre o usa la carga manual." : "Elegi una coincidencia del catalogo o habilita la carga manual.")}
    </p>
    <div className="geo-pie"><button className="geo-manual" type="button" onClick={() => {
      setManual(!manual); setAbierto(false); setError("");
      if (!manual) alCambiar({ ...valor, geoname_id: null, codigo_pais: null });
    }}>{manual ? "Volver a buscar en el catalogo" : "Ingresar localidad manualmente"}</button>
      <a href="https://www.geonames.org/" target="_blank" rel="noreferrer">GeoNames · CC BY 4.0</a></div>
  </div>;
}
