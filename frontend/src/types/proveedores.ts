import type { EncuadrePortada } from "../components/PortadaAjustable";

export type Plan = "GRATIS" | "PREMIUM";

export interface CategoriaProveedor {
  id: number;
  nombre: string;
  slug: string;
}

export interface Proveedor {
  id: number;
  usuario_id: number;
  nombre_comercial: string;
  slug: string;
  cuit?: string | null;
  descripcion?: string | null;
  categorias: string[];
  categorias_detalle: CategoriaProveedor[];
  pais: string;
  localidad?: string | null;
  provincia?: string | null;
  direccion?: string | null;
  google_maps_url?: string | null;
  google_place_id?: string | null;
  ubicacion_referencia?: string | null;
  latitud?: number | null;
  longitud?: number | null;
  whatsapp?: string | null;
  telefono?: string | null;
  email?: string | null;
  web?: string | null;
  instagram?: string | null;
  facebook?: string | null;
  logo_url?: string | null;
  portada_url?: string | null;
  portada_encuadre?: EncuadrePortada | null;
  horarios?: string | null;
  template_key: string;
  plan: Plan;
  activo: boolean;
  distancia_km?: number | null;
}
