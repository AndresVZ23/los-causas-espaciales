"use client";

import { useState } from "react";
import { formatMillions, formatNumber, formatPercent } from "./format";
import type { SensitivityBar, SubjectSensitivity } from "./types";

// Par divergente validado con el validador de dataviz sobre la superficie oscura (#141618): CVD ΔE 11.2.
const UNFAVORABLE = "#c8743e";
const FAVORABLE = "#1f9e8e";

function factorValue(value: number, unit: string) {
  if (unit === "fracción") return formatPercent(value);
  if (unit === "USD") return formatMillions(value);
  if (unit === "USD/año") return `${formatMillions(value)}/año`;
  if (!unit) return formatNumber(value, 2);
  return `${formatNumber(value, 2)} ${unit}`;
}

function scale(bars: SensitivityBar[], base: number) {
  // El eje siempre incluye VAN = 0: es el umbral de la decisión.
  const values = bars.flatMap((bar) => [bar.npv_at_low, bar.npv_at_high]).concat(base, 0);
  const lo = Math.min(...values), hi = Math.max(...values);
  const pad = (hi - lo) * 0.04 || 1;
  return (value: number) => ((value - (lo - pad)) / (hi - lo + 2 * pad)) * 100;
}

function Tornado({ item }: { item: SubjectSensitivity }) {
  const x = scale(item.tornado, item.base_npv);
  const base = x(item.base_npv), zero = x(0);
  return (
    <div className="tornado" role="list" aria-label={`Sensibilidad del VAN en ${item.subject}`}>
      <div className="tornadoAxis" aria-hidden="true">
        <span style={{ left: `${zero}%` }} className="zeroTick">VAN 0</span>
        <span style={{ left: `${base}%` }} className="baseTick">Base {formatMillions(item.base_npv)}</span>
      </div>
      {item.tornado.map((bar) => {
        const low = x(bar.npv_at_low), high = x(bar.npv_at_high);
        const summary = `${bar.label}: ${factorValue(bar.low_value, bar.unit)} da ${formatMillions(bar.npv_at_low)}; ${factorValue(bar.high_value, bar.unit)} da ${formatMillions(bar.npv_at_high)}.`;
        return (
          <div className="tornadoRow" role="listitem" tabIndex={0} key={bar.key} aria-label={summary}>
            <div className="tornadoLabel">
              <b>{bar.label}</b>
              <small>{factorValue(bar.low_value, bar.unit)} → {factorValue(bar.high_value, bar.unit)}</small>
            </div>
            <div className="tornadoTrack" aria-hidden="true">
              <i className="zeroLine" style={{ left: `${zero}%` }} />
              <i className="baseLine" style={{ left: `${base}%` }} />
              <span className="bar" style={{ left: `${Math.min(low, base)}%`, width: `${Math.abs(base - low)}%`, background: UNFAVORABLE }} />
              <span className="bar" style={{ left: `${Math.min(high, base)}%`, width: `${Math.abs(high - base)}%`, background: FAVORABLE }} />
            </div>
            <div className="tornadoValues"><span>{formatMillions(bar.npv_at_low)}</span><span>{formatMillions(bar.npv_at_high)}</span></div>
            <div className="tornadoTip" role="tooltip">
              <b>{bar.label}</b>
              <span><i style={{ background: UNFAVORABLE }} />Desfavorable {factorValue(bar.low_value, bar.unit)} · VAN {formatMillions(bar.npv_at_low)}</span>
              <span><i style={{ background: FAVORABLE }} />Favorable {factorValue(bar.high_value, bar.unit)} · VAN {formatMillions(bar.npv_at_high)}</span>
              <small>{bar.provenance} · {bar.basis}</small>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function SensitivityPanel({ items, stale }: { items: SubjectSensitivity[]; stale: boolean }) {
  const [active, setActive] = useState(0);
  const item = items[Math.min(active, items.length - 1)];
  const scenarioKeys = items[0].scenarios.map((scenario) => scenario.key);
  // El origen de cada rango lo declara su barra; aquí solo se dice si alguno viene de datos (años observados o una
  // segunda fuente) o si, como en vial e inmobiliario, todos son supuestos.
  const measured = items.some((subject) => subject.tornado.some((bar) => bar.provenance !== "USER_ASSUMPTION"));
  return (
    <section className="sensitivityPanel" aria-labelledby="sensibilidad-title">
      <div className="panelHeader">
        <div>
          <h3 id="sensibilidad-title">Escenarios y sensibilidad del VAN</h3>
          <p>Un factor a la vez en el tornado; juntos en los escenarios. {measured
            ? "Los rangos medidos salen de los años observados o de la segunda fuente; los demás son supuestos editables."
            : "Todos los rangos son supuestos editables."}</p>
        </div>
        <span>{item.currency} · MODEL_ESTIMATE</span>
      </div>
      {stale && <p className="sensitivityStale" role="status">Los supuestos cambiaron: vuelva a ejecutar el análisis para actualizar los escenarios.</p>}
      <div className="sensitivityGrid">
        <div>
          <table className="scenarioTable">
            <thead><tr><th scope="col">Escenario</th>{items.map((subject) => <th scope="col" key={subject.subject}>{subject.subject}</th>)}</tr></thead>
            <tbody>
              {scenarioKeys.map((key) => (
                <tr key={key} className={key === "adverso" ? "adverse" : undefined}>
                  <th scope="row">{items[0].scenarios.find((scenario) => scenario.key === key)?.label}</th>
                  {items.map((subject) => {
                    const npv = subject.scenarios.find((scenario) => scenario.key === key)?.npv ?? 0;
                    return <td key={subject.subject} className={npv >= 0 ? "positive" : "negative"}>{formatMillions(npv)}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="scenarioChanges">
            {item.scenarios.filter((scenario) => scenario.key !== "base").map((scenario) => (
              <p key={scenario.key}><span>{scenario.label} · {item.subject}</span>{scenario.changes.join(" · ")}</p>
            ))}
          </div>
          <div className="breakEvens">
            <h4>Puntos de equilibrio · {item.subject}</h4>
            {item.break_evens.map((even) => (
              <p key={even.key}>
                <b>{even.label}</b>
                <strong>{even.break_even_value == null ? "Sin cruce" : factorValue(even.break_even_value, even.unit)}</strong>
                <small>{even.note}</small>
              </p>
            ))}
          </div>
        </div>
        <div>
          <div className="tornadoHead">
            <div role="group" aria-label="Sujeto del tornado">
              {items.map((subject, index) => (
                <button key={subject.subject} className={index === active ? "active" : ""} aria-pressed={index === active} onClick={() => setActive(index)}>{subject.subject}</button>
              ))}
            </div>
            <p className="tornadoKey"><span><i style={{ background: UNFAVORABLE }} />Desfavorable</span><span><i style={{ background: FAVORABLE }} />Favorable</span></p>
          </div>
          <Tornado item={item} />
        </div>
      </div>
    </section>
  );
}
