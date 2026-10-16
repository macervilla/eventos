import { Crosshair, MapPin, Search } from "lucide-react";
import { FormEvent, useState } from "react";

import { DEFAULT_LOCATION, QueryLocation } from "../types/location";

interface LocationSelectorProps {
  value: QueryLocation | null;
  onChange: (location: QueryLocation) => void;
}

const STORAGE_KEY = "eventos.queryLocation";

export function readSavedLocation(): QueryLocation | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as QueryLocation;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function saveQueryLocation(location: QueryLocation) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(location));
}

export function LocationSelector({ value, onChange }: LocationSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [localidad, setLocalidad] = useState(value?.localidad ?? "");
  const [provincia, setProvincia] = useState(value?.provincia ?? "");
  const [error, setError] = useState<string | null>(null);

  const label = value?.localidad
    ? `${value.localidad}${value.provincia ? `, ${value.provincia}` : ""}`
    : "Sin ubicación habitual";

  const persist = (location: QueryLocation) => {
    saveQueryLocation(location);
    onChange(location);
    setIsOpen(false);
    setError(null);
  };

  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      setError("Este navegador no permite obtener ubicación.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        persist({
          localidad: "Ubicación actual",
          provincia: undefined,
          pais: "Argentina",
          latitud: position.coords.latitude,
          longitud: position.coords.longitude,
          origen: "GEOLOCATION"
        });
      },
      () => {
        setError("No se habilitó la ubicación. Podés buscar por localidad.");
      },
      { enableHighAccuracy: false, maximumAge: 300000, timeout: 8000 }
    );
  };

  const submitManual = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    persist({
      ...DEFAULT_LOCATION,
      localidad: localidad.trim() || undefined,
      provincia: provincia.trim() || undefined,
      latitud: localidad.trim().toLowerCase() === "río gallegos" ? DEFAULT_LOCATION.latitud : undefined,
      longitud:
        localidad.trim().toLowerCase() === "río gallegos" ? DEFAULT_LOCATION.longitud : undefined,
      origen: "MANUAL"
    });
  };

  return (
    <section className="location-bar" aria-label="Ubicación de consulta">
      <div className="location-label">
        <MapPin size={20} aria-hidden="true" />
        <span>
          <strong>Ubicación actual de consulta:</strong> {label}
        </span>
      </div>
      <button className="secondary-button" type="button" onClick={() => setIsOpen((open) => !open)}>
        Cambiar ubicación
      </button>

      {isOpen && (
        <div className="location-panel">
          <button className="action-button" type="button" onClick={useCurrentLocation}>
            <Crosshair size={18} aria-hidden="true" />
            Usar mi ubicación actual
          </button>

          <form className="manual-location-form" onSubmit={submitManual}>
            <label>
              Localidad
              <input
                value={localidad}
                onChange={(event) => setLocalidad(event.target.value)}
                placeholder="Río Gallegos"
              />
            </label>
            <label>
              Provincia
              <input
                value={provincia}
                onChange={(event) => setProvincia(event.target.value)}
                placeholder="Santa Cruz"
              />
            </label>
            <button className="action-button" type="submit">
              <Search size={18} aria-hidden="true" />
              Guardar ubicación
            </button>
          </form>

          {error && <p className="form-error">{error}</p>}
        </div>
      )}
    </section>
  );
}
