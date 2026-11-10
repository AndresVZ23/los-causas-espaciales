"use client";

import { useEffect, useState } from "react";
import { formatNumber, formatPercent, siteColor } from "./format";
import type { Criterion, Scorecard } from "./types";

const toPercent = (card: Scorecard) => Object.fromEntries(card.criteria.map((item) => [item.key, Math.round(item.weight * 1000) / 10]));

function valueText(value: number | null, unit: string) {
  if (value == null) return "Sin dato";
  if (unit === "fracción") return formatPercent(value);
  if (unit === "%") return `${formatNumber(value, 1)} %`;
  return `${formatNumber(value, 2)} ${unit}`;
}

function scaleText(criterion: Criterion) {
  return `0 = ${valueText(criterion.worst, criterion.unit)} · 100 = ${valueText(criterion.best, criterion.unit)}`;
}

export default function ScorecardPanel({ initial }: { initial: Scorecard }) {
  const [card, setCard] = useState(initial);
  const [weights, setWeights] = useState<Record<string, number>>(() => toPercent(initial));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Un análisis nuevo trae su propio puntaje y reinicia los pesos.
  useEffect(() => { setCard(initial); setWeights(toPercent(initial)); setError(""); }, [initial]);

  const total = Object.values(weights).reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0);
  // Los pesos se muestran con un decimal: seis redondeos pueden sumar 100.3 %. El backend renormaliza al recalcular.
  const balanced = Math.abs(total - 100) < 0.5;
  const edited = card.criteria.some((item) => Math.abs(item.weight * 100 - (weights[item.key] ?? 0)) > 0.05);

  async function recompute(next: Record<string, number>) {
    setBusy(true); setError("");
    try {
      const sum = Object.values(next).reduce((a, b) => a + b, 0);
      const body = {
        criteria: card.criteria.map((item) => ({ ...item, weight: next[item.key] / sum })),
        subjects: card.subjects.map((subject) => ({ subject: subject.subject, values: Object.fromEntries(subject.criteria.map((item) => [item.key, item.value])) })),
      };
      const response = await fetch("/api/scorecard", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "No se pudo recalcular el puntaje.");
      setCard({ ...(payload as Scorecard), notes: card.notes });
      setWeights(toPercent(payload as Scorecard));
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "No se pudo recalcular el puntaje.");
    } finally {
      setBusy(false);
    }
  }

  function normalize() {
    if (total <= 0) return;
    const next = Object.fromEntries(Object.entries(weights).map(([key, value]) => [key, (value / total) * 100]));
    recompute(next);
  }

  const fragile = card.weight_sensitivity.filter((item) => item.changes_leader);
  // El criterio de empate práctico lo decide el backend (`tie`, `margin`).
  const ranked = [...card.subjects].filter((item) => item.score != null).sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const gap = card.margin;
  const tie = card.tie;
  const labelOf = (key: string) => card.criteria.find((item) => item.key === key)?.label ?? key;

  return (
    <section className="scorecardPanel" aria-labelledby="puntaje-title">
      <div className="panelHeader">
        <div>
          <h3 id="puntaje-title">Puntaje multicriterio</h3>
          <p>Ordena prioridades de estudio con escalas y pesos a la vista; no es una recomendación de inversión.</p>
        </div>
        <span>MODEL_ESTIMATE · pesos USER_ASSUMPTION</span>
      </div>
      {ranked.length > 1 && (
        <p className={`scoreVerdict ${tie ? "tie" : ""}`} role="status">
          {tie
            ? `Empate práctico: ${formatNumber(gap ?? 0, 1)} punto(s) de diferencia; ${ranked[0].subject} queda primero en ${formatPercent(ranked[0].first_place_share, 0)} de las combinaciones de pesos. El puntaje no separa los sitios; decida con los criterios uno por uno.`
            : `${ranked[0].subject} lidera por ${formatNumber(gap ?? 0, 0)} puntos y queda primero en ${formatPercent(ranked[0].first_place_share, 0)} de las combinaciones de pesos.`}
        </p>
      )}
      <div className="scoreSummary">
        {card.subjects.map((subject, index) => (
          <article key={subject.subject} className={subject.subject === card.leader ? "leader" : undefined}>
            <p><i style={{ background: siteColor(index) }} aria-hidden="true" />{subject.subject}{subject.rank ? <span>{subject.rank}.º</span> : null}</p>
            <strong>{subject.score == null ? "N/D" : formatNumber(subject.score, 0)}<small>/100</small></strong>
            <small>Primero en {formatPercent(subject.first_place_share, 0)} de {card.stability_draws.toLocaleString("es-PE")} combinaciones de pesos · cobertura {formatPercent(subject.coverage, 0)}</small>
          </article>
        ))}
      </div>
      <div className="tableScroll">
        <table className="scoreTable">
          <thead>
            <tr><th scope="col">Criterio y escala</th><th scope="col">Peso</th>{card.subjects.map((subject) => <th scope="col" key={subject.subject}>{subject.subject}</th>)}</tr>
          </thead>
          <tbody>
            {card.criteria.map((criterion) => (
              <tr key={criterion.key}>
                <th scope="row">{criterion.label}<small>{scaleText(criterion)}</small><small title={criterion.basis}>{criterion.provenance} · {criterion.basis}</small></th>
                <td className="weightCell">
                  <label className="srOnly" htmlFor={`peso-${criterion.key}`}>Peso de {criterion.label} (%)</label>
                  <input id={`peso-${criterion.key}`} type="number" min={0} max={100} step={5} value={weights[criterion.key] ?? 0}
                         onChange={(event) => setWeights((current) => ({ ...current, [criterion.key]: Math.max(0, +event.target.value) }))} />
                  <span>%</span>
                </td>
                {card.subjects.map((subject) => {
                  const item = subject.criteria.find((entry) => entry.key === criterion.key);
                  return (
                    <td key={subject.subject} className="scoreCell">
                      <span>{valueText(item?.value ?? null, criterion.unit)}</span>
                      <i className="scoreBar" aria-hidden="true"><b style={{ width: `${item?.score ?? 0}%` }} /></i>
                      <small>{item?.score == null ? "fuera del cálculo" : `${formatNumber(item.score, 0)} pts · aporta ${formatNumber(item.contribution ?? 0, 1)}`}</small>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="weightBar">
        <p className={balanced ? undefined : "unbalanced"} role="status">Suma de pesos: {formatNumber(total, 1)} %{balanced ? "" : " · debe sumar 100 %"}</p>
        <div>
          <button onClick={() => { setWeights(toPercent(initial)); recompute(toPercent(initial)); }} disabled={busy}>Pesos por defecto</button>
          {!balanced && <button onClick={normalize} disabled={busy || total <= 0}>Llevar a 100 %</button>}
          <button className="primary" onClick={() => recompute(weights)} disabled={busy || !balanced || !edited}>{busy ? "Recalculando…" : "Recalcular"}</button>
        </div>
      </div>
      {error && <p className="errorMessage" role="alert">{error}</p>}
      <div className="scoreNotes">
        <p>{fragile.length
          ? `El primer lugar cambia si se lleva a la mitad o al 150 % el peso de: ${fragile.map((item) => labelOf(item.key).toLowerCase()).join(", ")}.`
          : "El primer lugar no cambia al llevar cualquier peso a la mitad o al 150 %."}</p>
        <p>{card.method}</p>
        {card.notes.map((note) => <p key={note}>{note}</p>)}
      </div>
    </section>
  );
}
