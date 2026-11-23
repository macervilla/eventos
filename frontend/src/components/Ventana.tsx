import { X } from "lucide-react";
import { ReactNode, useEffect, useRef } from "react";

type VentanaProps = {
  titulo: string;
  alCerrar: () => void;
  children: ReactNode;
};

export function Ventana({ titulo, alCerrar, children }: VentanaProps) {
  const referencia = useRef<HTMLElement>(null);
  useEffect(() => {
    const cerrarConEscape = (evento: KeyboardEvent) => {
      if (evento.key !== "Escape" || evento.defaultPrevented) return;
      const ventanas = document.querySelectorAll(".ventana[role='dialog']");
      if (ventanas[ventanas.length - 1] !== referencia.current) return;
      // Una vista previa o confirmacion anidada consume Escape sin cerrar su ventana de origen.
      evento.preventDefault();
      evento.stopImmediatePropagation();
      alCerrar();
    };
    // addEventListener: escucha teclas en toda la pagina mientras la ventana esta abierta
    window.addEventListener("keydown", cerrarConEscape);
    return () => window.removeEventListener("keydown", cerrarConEscape);
  }, [alCerrar]);

  return (
    <div className="ventana-fondo" onMouseDown={alCerrar}>
      <section
        ref={referencia}
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
