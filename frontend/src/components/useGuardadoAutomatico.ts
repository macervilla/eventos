import { useCallback, useEffect, useRef, useState } from "react";

/** Conserva el ultimo cambio y serializa las escrituras para evitar respuestas fuera de orden. */
export function useGuardadoAutomatico<T>(guardar: (valor: T) => Promise<unknown>, demora = 350) {
  const [estado, setEstado] = useState<"guardado" | "pendiente" | "guardando" | "error">("guardado");
  const persistir = useRef(guardar);
  persistir.current = guardar;
  const pendiente = useRef<{ valor: T } | null>(null);
  const enCurso = useRef<Promise<boolean> | null>(null);
  const temporizador = useRef<ReturnType<typeof setTimeout>>();
  const montado = useRef(true);

  const guardarAhora = useCallback((): Promise<boolean> => {
    clearTimeout(temporizador.current);
    if (enCurso.current) return enCurso.current;
    const procesar = async () => {
      while (pendiente.current) {
        const cambio = pendiente.current;
        pendiente.current = null;
        if (montado.current) setEstado("guardando");
        try {
          await persistir.current(cambio.valor);
        } catch {
          // Mantener el cambio mas reciente para reintentar sin perder la edicion.
          pendiente.current ??= cambio;
          if (montado.current) setEstado("error");
          return false;
        }
      }
      if (montado.current) setEstado("guardado");
      return true;
    };
    enCurso.current = procesar().finally(() => { enCurso.current = null; });
    return enCurso.current;
  }, []);

  const programar = useCallback((valor: T) => {
    pendiente.current = { valor };
    if (montado.current) setEstado("pendiente");
    clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => { void guardarAhora(); }, demora);
  }, [demora, guardarAhora]);

  useEffect(() => {
    montado.current = true;
    const alOcultar = () => { if (document.visibilityState === "hidden") void guardarAhora(); };
    document.addEventListener("visibilitychange", alOcultar);
    return () => {
      montado.current = false;
      clearTimeout(temporizador.current);
      document.removeEventListener("visibilitychange", alOcultar);
      if (pendiente.current) void guardarAhora();
    };
  }, [guardarAhora]);

  return { estado, programar, guardarAhora };
}

export function mensajeGuardado(estado: "guardado" | "pendiente" | "guardando" | "error") {
  if (estado === "error") return "No se pudieron guardar los cambios. Usa Guardar para reintentar.";
  return estado === "guardado" ? "Cambios guardados" : "Guardando cambios...";
}
