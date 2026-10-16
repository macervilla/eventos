import { X } from "lucide-react";
import { ReactNode, useEffect } from "react";

type VentanaProps = {
  titulo: string;
  alCerrar: () => void;
  children: ReactNode;
};

export function Ventana({ titulo, alCerrar, children }: VentanaProps) {
  useEffect(() => {
    const cerrarConEscape = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") alCerrar();
    };
    // addEventListener: escucha teclas en toda la pagina mientras la ventana esta abierta
    window.addEventListener("keydown", cerrarConEscape);
    return () => window.removeEventListener("keydown", cerrarConEscape);
  }, [alCerrar]);

  return (
    <div className="ventana-fondo" onMouseDown={alCerrar}>
      <section
        aria-label={titulo}
        aria-modal="true"
        className="ventana"
        role="dialog"
        onMouseDown={(evento) => evento.stopPropagation()}
      >
        <header className="ventana-encabezado">
          <h2>{titulo}</h2>
          <button aria-label="Cerrar" className="icono-boton" type="button" onClick={alCerrar}>
            <X size={20} aria-hidden="true" />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
