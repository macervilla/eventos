import { CSSProperties, useEffect } from "react";

type Tipografia = {
  label: string;
  titulo: string;
  texto: string;
  // Algunas fuentes solo existen en peso normal: forzar negrita las deforma
  pesoTitulo: string;
  // Familias a pedir a Google Fonts (vacio = fuente del sistema, no se descarga nada)
  google: string[];
};

export const tipografias = {
  sistema: {
    label: "Estandar",
    titulo: "inherit",
    texto: "inherit",
    pesoTitulo: "inherit",
    google: []
  },
  elegante: {
    label: "Elegante",
    titulo: "'Playfair Display', serif",
    texto: "'Lato', sans-serif",
    pesoTitulo: "700",
    google: ["Playfair+Display:wght@700", "Lato:wght@400;700"]
  },
  romantica: {
    label: "Romantica",
    titulo: "'Great Vibes', cursive",
    texto: "'Lora', serif",
    pesoTitulo: "400",
    google: ["Great+Vibes", "Lora:wght@400;700"]
  },
  moderna: {
    label: "Moderna",
    titulo: "'Montserrat', sans-serif",
    texto: "'Montserrat', sans-serif",
    pesoTitulo: "800",
    google: ["Montserrat:wght@400;600;800"]
  },
  divertida: {
    label: "Divertida",
    titulo: "'Fredoka', sans-serif",
    texto: "'Nunito', sans-serif",
    pesoTitulo: "600",
    google: ["Fredoka:wght@600", "Nunito:wght@400;700"]
  },
  clasica: {
    label: "Clasica",
    titulo: "'Cormorant Garamond', serif",
    texto: "'EB Garamond', serif",
    pesoTitulo: "700",
    google: ["Cormorant+Garamond:wght@700", "EB+Garamond:wght@400;600"]
  },
  fiesta: {
    label: "Fiesta",
    titulo: "'Pacifico', cursive",
    texto: "'Poppins', sans-serif",
    pesoTitulo: "400",
    google: ["Pacifico", "Poppins:wght@400;600"]
  },
  impacto: {
    label: "Impacto",
    titulo: "'Bebas Neue', sans-serif",
    texto: "'Roboto', sans-serif",
    pesoTitulo: "400",
    google: ["Bebas+Neue", "Roboto:wght@400;700"]
  }
} satisfies Record<string, Tipografia>;

export type TipografiaKey = keyof typeof tipografias;

export function obtenerTipografia(clave: string | null | undefined): Tipografia {
  return tipografias[(clave ?? "sistema") as TipografiaKey] ?? tipografias.sistema;
}

/** Variables CSS que usa la pagina (.con-tipografia) para titulos y textos. */
export function estiloTipografia(clave: string | null | undefined) {
  const tipografia = obtenerTipografia(clave);
  return {
    "--fuente-titulo": tipografia.titulo,
    "--fuente-texto": tipografia.texto,
    "--peso-titulo": tipografia.pesoTitulo
  } as CSSProperties;
}

/** Inserta (una sola vez) el <link> de Google Fonts con las familias pedidas. */
export function useFuentesGoogle(claves: string[]) {
  const familias = Array.from(new Set(claves.flatMap((clave) => obtenerTipografia(clave).google)));
  const firma = familias.join("|");

  useEffect(() => {
    if (!firma) return;
    const id = `fuentes-${firma}`;
    // getElementById: evita agregar el mismo <link> varias veces
    if (document.getElementById(id)) return;
    const enlace = document.createElement("link");
    enlace.id = id;
    enlace.rel = "stylesheet";
    enlace.href = `https://fonts.googleapis.com/css2?${firma
      .split("|")
      .map((familia) => `family=${familia}`)
      .join("&")}&display=swap`;
    document.head.appendChild(enlace);
  }, [firma]);
}
