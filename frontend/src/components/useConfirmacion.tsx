import { useCallback, useEffect, useRef, useState } from "react";
import { Ventana } from "./Ventana";

type Pregunta = { titulo: string; mensaje: string; aceptar: string };

// Los cierres por Escape, fondo o cruz equivalen siempre a cancelar.
export function useConfirmacion() {
  const [pregunta, setPregunta] = useState<Pregunta | null>(null);
  const resolver = useRef<((valor: boolean) => void) | null>(null);
  const confirmar = useCallback((mensaje: string, titulo = "Confirmar accion", aceptar = "Confirmar") => {
    resolver.current?.(false);
    setPregunta({ titulo, mensaje, aceptar });
    return new Promise<boolean>(resolve => { resolver.current = resolve; });
  }, []);
  const responder = useCallback((valor: boolean) => {
    const pendiente = resolver.current;
    resolver.current = null;
    setPregunta(null);
    pendiente?.(valor);
  }, []);
  useEffect(() => () => { resolver.current?.(false); resolver.current = null; }, []);
  const ventanaConfirmacion = pregunta && <Ventana titulo={pregunta.titulo} alCerrar={() => responder(false)}>
    <p style={{ whiteSpace: "pre-line" }}>{pregunta.mensaje}</p>
    <div className="form-actions">
      <button autoFocus className="secondary-button" type="button" onClick={() => responder(false)}>Cancelar</button>
      <button className="action-button" type="button" onClick={() => responder(true)}>{pregunta.aceptar}</button>
    </div>
  </Ventana>;
  return { confirmar, ventanaConfirmacion };
}
