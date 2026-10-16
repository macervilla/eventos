import { useEffect } from "react";

const TAMANIO_MAXIMO = 5 * 1024 * 1024;

/** Si la imagen supera el limite del backend (5 MB), se recomprime como JPEG. */
export async function prepararImagen(archivo: File): Promise<File> {
  if (archivo.size <= TAMANIO_MAXIMO) return archivo;
  // createImageBitmap: decodifica la imagen para poder redibujarla en un canvas
  const imagen = await createImageBitmap(archivo);
  const escala = Math.min(1, 2400 / Math.max(imagen.width, imagen.height));
  const lienzo = document.createElement("canvas");
  lienzo.width = Math.round(imagen.width * escala);
  lienzo.height = Math.round(imagen.height * escala);
  lienzo.getContext("2d")!.drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
  const blob = await new Promise<Blob | null>((resolver) =>
    // toBlob: exporta el canvas como archivo JPEG con calidad 0.85
    lienzo.toBlob(resolver, "image/jpeg", 0.85)
  );
  if (!blob) return archivo;
  return new File([blob], "portada.jpg", { type: "image/jpeg" });
}

function imagenDelPortapapeles(evento: ClipboardEvent): File | null {
  const items = Array.from(evento.clipboardData?.items ?? []);
  const item = items.find((elemento) => elemento.kind === "file" && elemento.type.startsWith("image/"));
  return item?.getAsFile() ?? null;
}

/** Lee una imagen del portapapeles a pedido (boton "Pegar imagen"). */
export async function leerImagenDelPortapapeles(): Promise<File | null> {
  // navigator.clipboard.read: pide al navegador el contenido del portapapeles (solicita permiso)
  const contenidos = await navigator.clipboard.read();
  for (const contenido of contenidos) {
    const tipo = contenido.types.find((t) => t.startsWith("image/"));
    if (tipo) {
      const blob = await contenido.getType(tipo);
      return new File([blob], `portada.${tipo.split("/")[1]}`, { type: tipo });
    }
  }
  return null;
}

/**
 * Escucha Ctrl+V en toda la pagina y entrega la imagen pegada.
 * Se ignora si se esta escribiendo en un campo, para no romper el pegado de texto.
 */
export function usePegarImagen(activo: boolean, alPegar: (archivo: File) => void) {
  useEffect(() => {
    if (!activo) return;
    const manejarPegado = (evento: ClipboardEvent) => {
      const destino = evento.target as HTMLElement | null;
      if (destino?.closest("input, textarea, select, [contenteditable='true'], .ventana")) return;
      const archivo = imagenDelPortapapeles(evento);
      if (!archivo) return;
      evento.preventDefault();
      alPegar(archivo);
    };
    window.addEventListener("paste", manejarPegado);
    return () => window.removeEventListener("paste", manejarPegado);
  }, [activo, alPegar]);
}
