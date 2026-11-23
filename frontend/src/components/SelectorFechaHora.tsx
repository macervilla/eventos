const HORAS = Array.from({ length: 24 }, (_, hora) => String(hora).padStart(2, "0"));
const MINUTOS = ["00", "15", "30", "45"];

export function SelectorFechaHora({ valor, alCambiar }: {
  valor: string;
  alCambiar: (valor: string) => void;
}) {
  const [fecha = "", tiempo = "00:00"] = valor.split("T");
  const [hora = "00", minutos = "00"] = tiempo.split(":");

  return (
    <div className="selector-fecha-hora" role="group" aria-label="Fecha y hora">
      <label>
        Fecha
        <input type="date" value={fecha} onChange={e => alCambiar(e.target.value ? `${e.target.value}T${hora}:${minutos}` : "")} />
      </label>
      <label>
        Hora
        <select value={hora} disabled={!fecha} onChange={e => alCambiar(`${fecha}T${e.target.value}:${MINUTOS.includes(minutos) ? minutos : "00"}`)}>
          {HORAS.map(h => <option key={h} value={h}>{h}</option>)}
        </select>
      </label>
      <label>
        Minutos
        <select value={minutos} disabled={!fecha} onChange={e => alCambiar(`${fecha}T${hora}:${e.target.value}`)}>
          {!MINUTOS.includes(minutos) && <option value={minutos} disabled>{minutos} (actual)</option>}
          {MINUTOS.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </label>
    </div>
  );
}
