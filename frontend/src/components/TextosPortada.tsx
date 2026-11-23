import { useRef, useState, type PointerEvent } from "react";
import { createPortal } from "react-dom";
import { mensajeGuardado, useGuardadoAutomatico } from "./useGuardadoAutomatico";

export type BloqueTexto = { x: number; y: number; visible: boolean };
export type TextosPortada = Record<"fecha" | "titulo" | "lugar", BloqueTexto>;
const claves = ["fecha", "titulo", "lugar"] as const;
type Clave = typeof claves[number];
const nombres = { fecha: "Fecha", titulo: "Titulo", lugar: "Lugar" };
export type ColoresTextos = Record<Clave, string>;
export const COLORES_TEXTOS_INICIALES: ColoresTextos = { titulo: "#ffffff", fecha: "#ffffff", lugar: "#ffffff" };
const limitar = (n: number) => Math.max(0, Math.min(100, n));

export function TextosPortadaEvento({ textos, configuracion, editable, alGuardar, contenedorControles, colores = COLORES_TEXTOS_INICIALES, etiquetas = nombres, editarColores = false }: {
  etiquetas?: Record<Clave, string>;
  editarColores?: boolean;
  colores?: ColoresTextos;
  textos: Record<Clave, string>;
  configuracion?: TextosPortada | null;
  editable: boolean;
  alGuardar: (config: TextosPortada, colores: ColoresTextos) => Promise<void>;
  contenedorControles: HTMLDivElement | null;
}) {
  const legacy = useRef<HTMLDivElement>(null);
  const [borrador, setBorrador] = useState<TextosPortada | null>(null);
  const [coloresBorrador, setColoresBorrador] = useState(colores);
  const [seleccionado, setSeleccionado] = useState<Clave>("titulo");
  const borradorActual = useRef<TextosPortada | null>(null);
  const coloresActuales = useRef(colores);
  const guardado = useGuardadoAutomatico(async (valor: { config: TextosPortada; colores: ColoresTextos }) => {
    await alGuardar(valor.config, valor.colores);
  });
  const arrastre = useRef<{ clave: Clave; id: number; x: number; y: number; inicial: BloqueTexto; ancho: number; alto: number } | null>(null);
  const enEdicion = editable && borrador !== null;
  const config = enEdicion ? borrador : configuracion;
  const coloresVisibles = enEdicion ? coloresBorrador : colores;

  const empezar = () => {
    setColoresBorrador({ ...colores });
    coloresActuales.current = { ...colores };
    if (configuracion) { borradorActual.current = structuredClone(configuracion); setBorrador(borradorActual.current); return; }
    const caja = legacy.current!;
    const portada = caja.parentElement!.getBoundingClientRect();
    const inicial = {} as TextosPortada;
    claves.forEach(clave => {
      const rect = caja.querySelector(`[data-texto="${clave}"]`)!.getBoundingClientRect();
      inicial[clave] = {
        x: limitar((rect.left - portada.left) / Math.max(1, portada.width - rect.width) * 100),
        y: limitar((rect.top - portada.top) / Math.max(1, portada.height - rect.height) * 100), visible: true
      };
    });
    borradorActual.current = inicial;
    setBorrador(inicial);
  };
  const registrar = () => {
    if (borradorActual.current) guardado.programar({ config: borradorActual.current, colores: coloresActuales.current });
  };
  const cambiar = (clave: Clave, valor: Partial<BloqueTexto>, persistir = true) => {
    const actual = borradorActual.current;
    if (!actual) return;
    borradorActual.current = { ...actual, [clave]: { ...actual[clave], ...valor } };
    setBorrador(borradorActual.current);
    if (persistir) registrar();
  };
  const iniciarArrastre = (e: PointerEvent<HTMLDivElement>, clave: Clave) => {
    if (!enEdicion || e.button !== 0) return;
    e.preventDefault();
    setSeleccionado(clave);
    const rect = e.currentTarget.getBoundingClientRect();
    const portada = e.currentTarget.parentElement!.getBoundingClientRect();
    arrastre.current = { clave, id: e.pointerId, x: e.clientX, y: e.clientY, inicial: { ...borrador![clave] },
      ancho: Math.max(1, portada.width - rect.width), alto: Math.max(1, portada.height - rect.height) };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const mover = (e: PointerEvent<HTMLDivElement>) => {
    const a = arrastre.current;
    if (!a || a.id !== e.pointerId) return;
    cambiar(a.clave, { x: limitar(a.inicial.x + (e.clientX - a.x) / a.ancho * 100),
      y: limitar(a.inicial.y + (e.clientY - a.y) / a.alto * 100) }, false);
  };
  const terminar = (e: PointerEvent<HTMLDivElement>, cancelar = false) => {
    const a = arrastre.current;
    if (!a || a.id !== e.pointerId) return;
    if (cancelar) cambiar(a.clave, a.inicial, false);
    else { registrar(); void guardado.guardarAhora(); }
    arrastre.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  };
  const guardar = async () => {
    if (!borrador) return;
    registrar();
    await guardado.guardarAhora();
  };
  const contenido = (clave: Clave) => clave === "titulo" ? <h1>{textos[clave]}</h1>
    : <p className={clave === "fecha" ? "eyebrow" : undefined}>{textos[clave]}</p>;

  return <>
    {!config ? <div className="provider-cover-copy" ref={legacy}>
      {claves.map(clave => <div key={clave} data-texto={clave} style={{ color: coloresVisibles[clave] }}>{contenido(clave)}</div>)}
    </div> : claves.filter(clave => config[clave].visible).map(clave => {
      const bloque = config[clave];
      return <div key={clave} data-texto={clave}
        className={`texto-portada ${enEdicion ? "texto-portada-editable" : ""} ${enEdicion && seleccionado === clave ? "seleccionado" : ""}`}
        style={{ color: coloresVisibles[clave], left: `${bloque.x}%`, top: `${bloque.y}%`, transform: `translate(-${bloque.x}%, -${bloque.y}%)` }}
        tabIndex={enEdicion ? 0 : undefined}
        role={enEdicion ? "group" : undefined} aria-label={enEdicion ? `Mover ${etiquetas[clave]}` : undefined}
        onFocus={() => setSeleccionado(clave)} onPointerDown={e => iniciarArrastre(e, clave)}
        onPointerMove={mover} onPointerUp={e => terminar(e)} onPointerCancel={e => terminar(e, true)}
        onLostPointerCapture={() => { if (arrastre.current) { registrar(); void guardado.guardarAhora(); } arrastre.current = null; }}
        onKeyDown={e => {
          if (!enEdicion || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
          e.preventDefault();
          const paso = e.shiftKey ? 5 : 1;
          cambiar(clave, { x: limitar(bloque.x + (e.key === "ArrowRight" ? paso : e.key === "ArrowLeft" ? -paso : 0)),
            y: limitar(bloque.y + (e.key === "ArrowDown" ? paso : e.key === "ArrowUp" ? -paso : 0)) });
        }}>{contenido(clave)}</div>;
    })}
    {editable && contenedorControles && createPortal(<aside className="textos-portada-controles" aria-label="Textos de portada">
      {!enEdicion ? <button className="secondary-button" type="button" onClick={empezar}>{editarColores ? "Mover, ocultar o dar color a textos" : "Mover u ocultar textos"}</button> : <>
        <strong>Textos de portada</strong>
        <p>Arrastra cada texto. Tambien podes seleccionarlo y usar las flechas.</p>
        <p role={guardado.estado === "error" ? "alert" : "status"}>{mensajeGuardado(guardado.estado)}</p>
        {claves.map(clave => <label key={clave}><input type="checkbox" checked={borrador[clave].visible}
          onChange={e => cambiar(clave, { visible: e.target.checked })} /> Mostrar {etiquetas[clave].toLowerCase()}</label>)}
        {editarColores && <div className="textos-portada-colores">
          {claves.map(clave => <label key={clave}>Color de {etiquetas[clave].toLowerCase()}
            <input type="color" value={coloresBorrador[clave]}
              onChange={e => { coloresActuales.current = { ...coloresActuales.current, [clave]: e.target.value }; setColoresBorrador(coloresActuales.current); registrar(); }} />
          </label>)}
        </div>}
        <div className="textos-portada-acciones">
          <button className="action-button" type="button" disabled={guardado.estado === "guardando"} onClick={guardar}>Guardar</button>
          <button className="secondary-button" type="button" onClick={async () => { if (await guardado.guardarAhora()) setBorrador(null); }}>Cancelar</button>
        </div>
      </>}
    </aside>, contenedorControles)}
  </>;
}
