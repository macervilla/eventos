import { Filter, MapPin } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import {
  LocationSelector,
  readSavedLocation,
  saveQueryLocation
} from "../components/LocationSelector";
import { DEFAULT_LOCATION, QueryLocation } from "../types/location";
import { Plan, Proveedor } from "../types/proveedores";

const categorias: Array<{ value: string; label: string }> = [
  { value: "dj", label: "DJ" },
  { value: "salon", label: "Salones" },
  { value: "catering", label: "Catering" },
  { value: "fotografia", label: "Fotografía" },
  { value: "animacion", label: "Animación" },
  { value: "decoracion", label: "Decoración" }
];

export function ProveedoresPage() {
  const [queryLocation, setQueryLocation] = useState<QueryLocation | null>(() => readSavedLocation());
  const [categoria, setCategoria] = useState("");
  const [localidad, setLocalidad] = useState("");
  const [nombre, setNombre] = useState("");
  const [radioKm, setRadioKm] = useState("30");
  const [plan, setPlan] = useState<Plan | "">("");
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!queryLocation) {
      saveQueryLocation(DEFAULT_LOCATION);
      setQueryLocation(DEFAULT_LOCATION);
    }
  }, [queryLocation]);

  const params = useMemo(() => {
    const searchParams: Record<string, string | number> = {};
    if (categoria) searchParams.categoria = categoria;
    if (localidad.trim()) searchParams.localidad = localidad.trim();
    if (nombre.trim()) searchParams.nombre = nombre.trim();
    if (plan) searchParams.plan = plan;
    if (queryLocation?.latitud !== undefined && queryLocation.longitud !== undefined) {
      searchParams.lat = queryLocation.latitud;
      searchParams.lng = queryLocation.longitud;
      if (radioKm) searchParams.radio_km = radioKm;
    } else if (queryLocation?.localidad && !localidad.trim()) {
      searchParams.localidad = queryLocation.localidad;
    }
    return searchParams;
  }, [categoria, localidad, nombre, plan, queryLocation, radioKm]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    api
      .get<Proveedor[]>("/proveedores", { params, signal: controller.signal })
      .then((response) => setProveedores(response.data))
      .catch((requestError) => {
        if (requestError.name !== "CanceledError") {
          setError("No se pudieron cargar proveedores.");
        }
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [params]);

  return (
    <main className="providers-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Proveedores</p>
          <h1>Proveedores cerca tuyo</h1>
        </div>
        <LocationSelector value={queryLocation} onChange={setQueryLocation} />
      </header>

      <section className="category-strip" aria-label="Categorías principales">
        {categorias.map((item) => (
          <button
            className={categoria === item.value ? "category-chip active" : "category-chip"}
            key={item.value}
            type="button"
            onClick={() => setCategoria((current) => (current === item.value ? "" : item.value))}
          >
            {item.label}
          </button>
        ))}
      </section>

      <section className="filters" aria-label="Filtros de búsqueda">
        <div className="filters-title">
          <Filter size={18} aria-hidden="true" />
          <span>Filtros</span>
        </div>
        <label>
          Nombre
          <input
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
            placeholder="DJ Example"
          />
        </label>
        <label>
          Localidad
          <input
            value={localidad}
            onChange={(event) => setLocalidad(event.target.value)}
            placeholder={queryLocation?.localidad ?? "Río Gallegos"}
          />
        </label>
        <label>
          Distancia
          <select value={radioKm} onChange={(event) => setRadioKm(event.target.value)}>
            <option value="10">10 km</option>
            <option value="30">30 km</option>
            <option value="50">50 km</option>
            <option value="100">100 km</option>
          </select>
        </label>
        <label>
          Plan
          <select value={plan} onChange={(event) => setPlan(event.target.value as Plan | "")}>
            <option value="">Todos</option>
            <option value="GRATIS">Gratis</option>
            <option value="PREMIUM">Premium</option>
          </select>
        </label>
      </section>

      <section className="results" aria-live="polite">
        {loading && <div className="empty-state">Cargando proveedores...</div>}
        {error && <div className="empty-state error">{error}</div>}
        {!loading && !error && proveedores.length === 0 && (
          <div className="empty-state">Todavía no hay proveedores para esta búsqueda.</div>
        )}
        {!loading &&
          !error &&
          proveedores.map((proveedor) => (
            <Link
              aria-label={`Ver pagina de ${proveedor.nombre_comercial}`}
              className="provider-card provider-card-link"
              key={proveedor.id}
              to={`/p/${proveedor.slug}`}
            >
              <div>
                <h2>{proveedor.nombre_comercial}</h2>
                <p>{proveedor.descripcion ?? "Proveedor registrado para eventos."}</p>
                <div className="provider-meta">
                  {(proveedor.categorias_detalle.length > 0
                    ? proveedor.categorias_detalle.map((item) => item.nombre)
                    : proveedor.categorias
                  ).map((item) => <span key={item}>{item}</span>)}
                  <span>{proveedor.plan}</span>
                  {proveedor.localidad && <span>{proveedor.localidad}</span>}
                </div>
              </div>
              <div className="distance-badge">
                <MapPin size={16} aria-hidden="true" />
                {proveedor.distancia_km !== null && proveedor.distancia_km !== undefined
                  ? `${proveedor.distancia_km} km`
                  : "Sin distancia"}
              </div>
            </Link>
          ))}
      </section>
    </main>
  );
}
