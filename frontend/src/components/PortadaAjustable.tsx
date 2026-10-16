import { Check, Crosshair, Maximize, Minimize, X } from "lucide-react";
import { PointerEvent, useEffect, useRef, useState } from "react";

export type EncuadrePortada = {
  x: number;
  y: number;
  modo: "cubrir" | "completa";
};

const ENCUADRE_CENTRADO: EncuadrePortada = { x: 50, y: 50, modo: "cubrir" };

const limitar = (valor: number) => Math.min(100, Math.max(0, valor));

/**
 * Encuadre a usar cuando el administrador todavia no eligio uno:
 * las fotos verticales se muestran completas (con fondo desenfocado) para no cortarlas.
 */
function useEncuadreAutomatico(imagen: string, encuadre: EncuadrePortada | null | undefined) {
  const [automatico, setAutomatico] = useState<EncuadrePortada>(ENCUADRE_CENTRADO);

  useEffect(() => {
    if (encuadre) return;
    // new Image(): carga la imagen en memoria solo para leer su ancho y alto reales
    const prueba = new Image();
    prueba.onload = () =>
      setAutomatico(
        prueba.naturalHeight > prueba.naturalWidth
          ? { x: 50, y: 50, modo: "completa" }
          : ENCUADRE_CENTRADO
      );
    prueba.src = imagen;
  }, [imagen, encuadre]);

  return encuadre ?? automatico;
}

export function CapasPortada({
  imagen,
  encuadre
}: {
  imagen: string;
  encuadre: EncuadrePortada | null | undefined;
}) {
  const efectivo = useEncuadreAutomatico(imagen, encuadre);
  const url = `url("${imagen}")`;
  return (
    <div className="portada-capas" aria-hidden="true">
      {efectivo.modo === "completa" && (
        <div className="portada-capa portada-desenfocada" style={{ backgroundImage: url }} />
      )}
      <div
        className="portada-capa"
        style={{
          backgroundImage: url,
          backgroundSize: efectivo.modo === "completa" ? "contain" : "cover",
          backgroundPosition: `${efectivo.x}% ${efectivo.y}%`
        }}
      />
    </div>
  );
}

type EditorEncuadreProps = {
  encuadre: EncuadrePortada;
  guardando: boolean;
  alCambiar: (encuadre: EncuadrePortada) => void;
  alGuardar: () => void;
  alCancelar: () => void;
};

/** Capa sobre la portada: se arrastra la imagen para elegir que parte se ve. */
export function EditorEncuadre({ encuadre, guardando, alCambiar, alGuardar, alCancelar }: EditorEncuadreProps) {
  const inicio = useRef<{ px: number; py: number; encuadre: EncuadrePortada } | null>(null);

  const empezar = (e: PointerEvent<HTMLDivElement>) => {
    // setPointerCapture: sigue recibiendo el movimiento aunque el puntero salga del area
    e.currentTarget.setPointerCapture(e.pointerId);
    inicio.current = { px: e.clientX, py: e.clientY, encuadre };
  };

  const mover = (e: PointerEvent<HTMLDivElement>) => {
    if (!inicio.current) return;
    const area = e.currentTarget.getBoundingClientRect();
    // En "cubrir" mover la imagen a la derecha muestra su parte izquierda: el foco va al reves.
    const sentido = encuadre.modo === "cubrir" ? -1 : 1;
    const sensibilidad = 1.5;
    alCambiar({
      ...encuadre,
      x: limitar(inicio.current.encuadre.x + (sentido * (e.clientX - inicio.current.px) * 100 * sensibilidad) / area.width),
      y: limitar(inicio.current.encuadre.y + (sentido * (e.clientY - inicio.current.py) * 100 * sensibilidad) / area.height)
    });
  };

  const terminar = () => {
    inicio.current = null;
  };

  return (
    <>
      <div
        className="portada-editor-arrastre"
        onPointerDown={empezar}
        onPointerMove={mover}
        onPointerUp={terminar}
        onPointerCancel={terminar}
      />
      <div className="portada-editor-barra" role="toolbar" aria-label="Encuadre de la portada">
        <span>Arrastra la imagen para elegir que se ve</span>
        <div className="portada-editor-modos">
          <button
            className={encuadre.modo === "cubrir" ? "activo" : undefined}
            title="La imagen llena toda la portada (puede recortarse)"
            type="button"
            onClick={() => alCambiar({ ...encuadre, modo: "cubrir" })}
          >
            <Maximize size={16} aria-hidden="true" /> Llenar
          </button>
          <button
            className={encuadre.modo === "completa" ? "activo" : undefined}
            title="Se ve la imagen entera, con fondo desenfocado"
            type="button"
            onClick={() => alCambiar({ ...encuadre, modo: "completa" })}
          >
            <Minimize size={16} aria-hidden="true" /> Completa
          </button>
        </div>
        <button
          className="icono-boton"
          title="Centrar"
          type="button"
          onClick={() => alCambiar({ ...encuadre, x: 50, y: 50 })}
        >
          <Crosshair size={18} aria-hidden="true" />
        </button>
        <button className="icono-boton" title="Cancelar" type="button" onClick={alCancelar}>
          <X size={18} aria-hidden="true" />
        </button>
        <button className="action-button" disabled={guardando} type="button" onClick={alGuardar}>
          <Check size={18} aria-hidden="true" />
          {guardando ? "Guardando..." : "Guardar encuadre"}
        </button>
      </div>
    </>
  );
}

/** Estado del modo "ajustar encuadre" compartido por las paginas de proveedor y evento. */
export function useAjusteEncuadre(
  imagen: string,
  guardado: EncuadrePortada | null | undefined,
  guardar: (encuadre: EncuadrePortada) => Promise<unknown>,
  alError: (mensaje: string) => void
) {
  const [borrador, setBorrador] = useState<EncuadrePortada | null>(null);
  const [guardando, setGuardando] = useState(false);
  const efectivo = useEncuadreAutomatico(imagen, guardado);

  return {
    editando: borrador !== null,
    encuadreVisible: borrador ?? guardado,
    empezar: () => setBorrador({ ...efectivo }),
    editor: borrador && (
      <EditorEncuadre
        encuadre={borrador}
        guardando={guardando}
        alCambiar={setBorrador}
        alCancelar={() => setBorrador(null)}
        alGuardar={() => {
          setGuardando(true);
          guardar(borrador)
            .then(() => setBorrador(null))
            .catch(() => alError("No se pudo guardar el encuadre."))
            .finally(() => setGuardando(false));
        }}
      />
    )
  };
}
