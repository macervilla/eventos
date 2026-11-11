import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type MenuSesionContextValue = {
  accionesEvento: ReactNode | null;
  actualizarAccionesEvento: (acciones: ReactNode | null) => void;
  alCerrarSesion: (() => void) | null;
  actualizarAlCerrarSesion: (accion: (() => void) | null) => void;
};

const MenuSesionContext = createContext<MenuSesionContextValue | null>(null);

export function MenuSesionProvider({ children }: { children: ReactNode }) {
  const [accionesEvento, actualizarAccionesEvento] = useState<ReactNode | null>(null);
  const [alCerrarSesion, actualizarAlCerrarSesion] = useState<(() => void) | null>(null);
  const establecerCierreSesion = useCallback((accion: (() => void) | null) => {
    actualizarAlCerrarSesion(() => accion);
  }, []);
  return <MenuSesionContext.Provider value={{ accionesEvento, actualizarAccionesEvento, alCerrarSesion, actualizarAlCerrarSesion: establecerCierreSesion }}>{children}</MenuSesionContext.Provider>;
}

export function useMenuSesion() {
  const context = useContext(MenuSesionContext);
  if (!context) throw new Error("useMenuSesion debe usarse dentro de MenuSesionProvider.");
  return context;
}
