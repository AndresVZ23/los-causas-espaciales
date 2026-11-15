"use client";

// Paso 3 de la misión: decidir con recursos limitados (decisions.ts). Se eligen medidas hasta gastar el presupuesto y
// se confirma el plan; entonces se ven sus beneficios, sus límites y su efecto simulado en tres ejes.

import { useState } from "react";
import { AXES, DECISION_NOTICE, affordable, evaluatePlan, spent, type DecisionSet, type PlanResult } from "./decisions";

export function DecisionStep({ set, locked, onConfirm }: {
  set: DecisionSet;
  /** Bloqueado hasta terminar los pasos anteriores. */
  locked: boolean;
  onConfirm: (result: PlanResult, chosen: string[]) => void;
}) {
  const [chosen, setChosen] = useState<string[]>([]);
  const [result, setResult] = useState<PlanResult | null>(null);
  const used = spent(set, chosen);
  const toggle = (id: string) => {
    if (result) return;
    setChosen((current) => (current.includes(id) ? current.filter((item) => item !== id) : affordable(set, current, id) ? [...current, id] : current));
  };
  const confirm = () => {
    const evaluated = evaluatePlan(set, chosen);
    setResult(evaluated);
    onConfirm(evaluated, chosen);
  };
  const retry = () => { setResult(null); setChosen([]); };
  const picked = set.measures.filter((item) => chosen.includes(item.id));

  return (
    <section className={`gameStep gameDecision${locked ? " isLocked" : ""}`} aria-labelledby={`decision-${set.key}`}>
      <h3 id={`decision-${set.key}`}>{set.title}</h3>
      <p>{set.situation}</p>
      <p className="gameIndifference"><b>La indiferencia dice:</b> {set.indifference}</p>
      <p className="gameBudget" aria-live="polite">
        Recursos: {Array.from({ length: set.budget }, (_, index) => <i key={index} className={index < used ? "on" : ""} aria-hidden />)}
        <span>{used} de {set.budget} usados</span>
      </p>
      <div className="gameMeasures" role="group" aria-label="Medidas para tu plan">
        {set.measures.map((item) => {
          const on = chosen.includes(item.id);
          const blocked = !on && !affordable(set, chosen, item.id);
          return (
            <button key={item.id} type="button" aria-pressed={on} disabled={locked || !!result || blocked} className={on ? "on" : ""} onClick={() => toggle(item.id)}>
              <span>{item.text}</span><small>{item.cost === 1 ? "1 recurso" : `${item.cost} recursos`}</small>
            </button>
          );
        })}
      </div>
      {!result && <button type="button" className="gameGo" disabled={locked || chosen.length === 0} onClick={confirm}>Confirmar el plan</button>}
      {result && (
        <div className={`gamePlan ${result.weak ? "ko" : "ok"}`} role="status">
          <p><b>{result.verdict}</b></p>
          <ul>{picked.map((item) => <li key={item.id}><b>{item.text}.</b> {item.benefit} <em>Límite: {item.limit}</em></li>)}</ul>
          <dl className="gameAxes">
            {AXES.map((axis) => (
              <div key={axis.id}><dt>{axis.label}</dt><dd><i style={{ width: `${Math.max(0, Math.min(100, (result.totals[axis.id] / 6) * 100))}%` }} className={result.totals[axis.id] < 0 ? "neg" : ""} /><span>{result.totals[axis.id] > 0 ? `+${result.totals[axis.id]}` : result.totals[axis.id]}</span></dd></div>
            ))}
          </dl>
          {result.notes.map((note) => <p key={note} className="gameMuted">{note}</p>)}
          {result.weak && <p className="gameMuted">Un plan débil es una mala decisión: te cuesta salud. Puedes armar otro.</p>}
          <button type="button" onClick={retry}>Armar otro plan</button>
        </div>
      )}
      <small className="gameMuted">{DECISION_NOTICE}</small>
    </section>
  );
}
