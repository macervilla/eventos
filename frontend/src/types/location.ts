export type LocationOrigin = "GEOLOCATION" | "MANUAL" | "EVENTO";

export interface QueryLocation {
  localidad?: string;
  provincia?: string;
  pais: string;
  latitud?: number;
  longitud?: number;
  origen: LocationOrigin;
}

export const DEFAULT_LOCATION: QueryLocation = {
  localidad: "Río Gallegos",
  provincia: "Santa Cruz",
  pais: "Argentina",
  latitud: -51.623,
  longitud: -69.2168,
  origen: "MANUAL"
};
