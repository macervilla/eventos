import "leaflet/dist/leaflet.css";

import L from "leaflet";
import iconoMarcador2x from "leaflet/dist/images/marker-icon-2x.png";
import iconoMarcador from "leaflet/dist/images/marker-icon.png";
import sombraMarcador from "leaflet/dist/images/marker-shadow.png";
import { useEffect, useRef } from "react";

// Con Vite hay que indicar las imagenes del marcador explicitamente.
const icono = L.icon({
  iconUrl: iconoMarcador,
  iconRetinaUrl: iconoMarcador2x,
  shadowUrl: sombraMarcador,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});

const CENTRO_ARGENTINA: L.LatLngTuple = [-38.4, -63.6];

type MapaUbicacionProps = {
  latitud: number | null;
  longitud: number | null;
  alCambiar: (latitud: number, longitud: number) => void;
};

/** Mapa de OpenStreetMap con un marcador que se arrastra o se ubica con un clic. */
export function MapaUbicacion({ latitud, longitud, alCambiar }: MapaUbicacionProps) {
  const contenedor = useRef<HTMLDivElement>(null);
  const mapa = useRef<L.Map | null>(null);
  const marcador = useRef<L.Marker | null>(null);
  const alCambiarActual = useRef(alCambiar);
  alCambiarActual.current = alCambiar;

  useEffect(() => {
    if (!contenedor.current || mapa.current) return;
    const nuevoMapa = L.map(contenedor.current).setView(CENTRO_ARGENTINA, 4);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 19
    }).addTo(nuevoMapa);
    nuevoMapa.on("click", (evento: L.LeafletMouseEvent) =>
      alCambiarActual.current(evento.latlng.lat, evento.latlng.lng)
    );
    mapa.current = nuevoMapa;
    // Dentro de una ventana emergente el tamano final se conoce despues de abrir:
    // invalidateSize recalcula el area visible del mapa.
    const temporizador = window.setTimeout(() => nuevoMapa.invalidateSize(), 150);
    return () => {
      window.clearTimeout(temporizador);
      nuevoMapa.remove();
      mapa.current = null;
      marcador.current = null;
    };
  }, []);

  useEffect(() => {
    const instancia = mapa.current;
    if (!instancia) return;
    if (latitud === null || longitud === null) {
      marcador.current?.remove();
      marcador.current = null;
      return;
    }
    const posicion: L.LatLngTuple = [latitud, longitud];
    if (!marcador.current) {
      marcador.current = L.marker(posicion, { draggable: true, icon: icono }).addTo(instancia);
      marcador.current.on("dragend", () => {
        const punto = marcador.current!.getLatLng();
        alCambiarActual.current(punto.lat, punto.lng);
      });
      instancia.setView(posicion, Math.max(instancia.getZoom(), 16));
    } else {
      marcador.current.setLatLng(posicion);
      // panTo: desplaza el mapa suavemente si el punto quedo fuera de la vista
      if (!instancia.getBounds().contains(posicion)) instancia.panTo(posicion);
    }
  }, [latitud, longitud]);

  return <div className="mapa-interactivo" ref={contenedor} />;
}
