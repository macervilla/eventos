import { ChevronDown } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

export function MenuDesplegable({ etiqueta, icono, children, className = "" }: {
  etiqueta: string; icono?: ReactNode; children: ReactNode; className?: string;
}) {
  const [abierto, setAbierto] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const id = useId();
  const location = useLocation();
  useEffect(() => { setAbierto(false); }, [location.pathname, location.search]);
  useEffect(() => {
    const otroMenu = (e: Event) => { if ((e as CustomEvent).detail !== id) setAbierto(false); };
    window.addEventListener("eventos:abrir-menu", otroMenu);
    return () => window.removeEventListener("eventos:abrir-menu", otroMenu);
  }, [id]);
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: PointerEvent) => { if (!raiz.current?.contains(e.target as Node)) setAbierto(false); };
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setAbierto(false); boton.current?.focus(); }
    };
    document.addEventListener("pointerdown", fuera);
    document.addEventListener("keydown", tecla);
    return () => { document.removeEventListener("pointerdown", fuera); document.removeEventListener("keydown", tecla); };
  }, [abierto]);
  return <div ref={raiz} className={`menu-desplegable ${className}`} onBlur={e => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setAbierto(false);
  }}>
    <button ref={boton} className="barra-control" type="button" aria-expanded={abierto} aria-controls={id}
      onClick={() => {
        if (!abierto) window.dispatchEvent(new CustomEvent("eventos:abrir-menu", { detail: id }));
        setAbierto(!abierto);
      }}>{icono}{etiqueta}<ChevronDown size={16} aria-hidden="true" /></button>
    {abierto && <div id={id} className="menu-desplegable-panel" onClick={e => {
      if ((e.target as HTMLElement).closest("a,button")) setAbierto(false);
    }}>{children}</div>}
  </div>;
}
