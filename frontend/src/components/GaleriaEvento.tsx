import { CSSProperties, useState } from "react";

export type ConfigGaleria = { modo: "grilla" | "carrusel"; filas: number; columnas: number };
type Imagen = { id: number; url: string };

export function GaleriaEvento({ imagenes, config, editando, alCambiar }: {
  imagenes: Imagen[]; config: ConfigGaleria; editando: boolean; alCambiar: (id: number) => void;
}) {
  const [pagina, setPagina] = useState(0);
  const [inicioToque, setInicioToque] = useState<number | null>(null);
  const capacidad = config.modo === "carrusel" ? 1 : config.filas * config.columnas;
  const paginas = Math.max(1, Math.ceil(imagenes.length / capacidad));
  const actual = Math.min(pagina, paginas - 1);
  const visibles = imagenes.slice(actual * capacidad, (actual + 1) * capacidad);
  const mover = (paso: number) => setPagina((actual + paso + paginas) % paginas);
  const carrusel = config.modo === "carrusel";

  if (!imagenes.length) return <p>Todavia no hay imagenes.</p>;
  return <div className={`galeria-presentacion ${carrusel ? "es-carrusel" : "es-grilla"}`}
    role="region" aria-label="Imagenes del evento" aria-roledescription={carrusel ? "carrusel" : undefined}
    tabIndex={0} onKeyDown={e => {
      if ((e.target as HTMLElement).closest("button")) return;
      if (e.key === "ArrowRight") { e.preventDefault(); mover(1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); mover(-1); }
    }}
    onTouchStart={e => setInicioToque(e.touches[0].clientX)}
    onTouchEnd={e => {
      if (inicioToque !== null) {
        const distancia = e.changedTouches[0].clientX - inicioToque;
        if (Math.abs(distancia) > 60) mover(distancia < 0 ? 1 : -1);
      }
      setInicioToque(null);
    }}>
    <div className="galeria-laminas" style={{ "--galeria-columnas": config.columnas, "--galeria-columnas-movil": Math.min(config.columnas, 2) } as CSSProperties}>
      {visibles.map((imagen, indice) => <figure key={imagen.id}>
        <img src={imagen.url} alt={`Imagen ${actual * capacidad + indice + 1} del evento`}
          loading="lazy" onDoubleClick={() => { if (editando) alCambiar(imagen.id); }} />
        {editando && <button className="secondary-button" type="button" onClick={() => alCambiar(imagen.id)}>Cambiar imagen</button>}
      </figure>)}
    </div>
    {paginas > 1 && <div className="galeria-navegacion">
      <button className="secondary-button" type="button" aria-label={carrusel ? "Imagen anterior" : "Pagina anterior de imagenes"} onClick={() => mover(-1)}>Anterior</button>
      <span aria-live="polite">{carrusel ? "Imagen" : "Pagina"} {actual + 1} de {paginas}</span>
      <button className="secondary-button" type="button" aria-label={carrusel ? "Imagen siguiente" : "Pagina siguiente de imagenes"} onClick={() => mover(1)}>Siguiente</button>
    </div>}
    {carrusel && paginas > 1 && <div className="galeria-indicadores" aria-label="Elegir imagen">
      {imagenes.map((imagen, indice) => <button key={imagen.id} type="button" aria-label={`Ver imagen ${indice + 1}`}
        aria-current={actual === indice ? "true" : undefined} onClick={() => setPagina(indice)} />)}
    </div>}
  </div>;
}
