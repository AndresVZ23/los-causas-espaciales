"use client";

import { useEffect, useState } from "react";
import { HEAT_LABEL, type Mission, type MissionTrend, type Role } from "./game-types";
import { missionSteps, percentPerDecade, perDecade, secondSourceSentence, temperatureSentence, type Checkpoint, type Option } from "./mission-logic";

const fmt = (value: number, digits = 1) => value.toLocaleString("es-PE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const dateOf = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("es-PE", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "sin fecha");

/** Línea anual de una variable, con la recta de Sen cuando la tendencia es significativa. */
function Sparkline({ trend, label }: { trend: MissionTrend; label: string }) {
  const points = trend.annual_series.filter((item): item is { year: number; value: number } => item.value != null);
  if (points.length < 3) return <p className="gameMuted">Sin serie suficiente para dibujar.</p>;
  const years = points.map((p) => p.year);
  const values = points.map((p) => p.value);
  const [x0, x1] = [Math.min(...years), Math.max(...years)];
  const [lo, hi] = [Math.min(...values), Math.max(...values)];
  const span = hi - lo || 1;
  const x = (year: number) => ((year - x0) / (x1 - x0 || 1)) * 280 + 10;
  const y = (value: number) => 70 - ((value - lo) / span) * 60;
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(p.year).toFixed(1)} ${y(p.value).toFixed(1)}`).join(" ");
  // Recta de Sen anclada en la mediana de la serie (la pendiente es la de la plataforma).
  const sorted = [...values].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  const midYear = (x0 + x1) / 2;
  const slope = trend.slope_per_year ?? 0;
  return (
    <figure className="gameSpark">
      <svg viewBox="0 0 300 80" role="img" aria-label={`${label}: ${points.length} años, de ${fmt(values[0])} a ${fmt(values[values.length - 1])} ${trend.unit ?? ""}`}>
        <path d={path} className="line" />
        {trend.significant && <path d={`M${x(x0)} ${y(median + slope * (x0 - midYear))} L${x(x1)} ${y(median + slope * (x1 - midYear))}`} className={`fit dir-${trend.direction}`} />}
      </svg>
      <figcaption><span>{x0}</span><span>{x1}</span></figcaption>
    </figure>
  );
}

function TrendRow({ title, trend, kind }: { title: string; trend: MissionTrend | null; kind: "temp" | "ratio" }) {
  if (!trend) return <div className="gameTrend"><b>{title}</b><p className="gameMuted">No disponible para este lugar (brecha declarada, no un cero).</p></div>;
  const decade = perDecade(trend);
  const pct = percentPerDecade(trend);
  const value = !trend.significant || decade == null ? "Sin evidencia suficiente"
    : kind === "temp" ? `${decade > 0 ? "+" : "−"}${fmt(Math.abs(decade), 2)} °C por década`
      : `${(pct ?? 0) > 0 ? "+" : "−"}${fmt(Math.abs(pct ?? 0))} % por década`;
  return (
    <div className={`gameTrend ${trend.significant ? `dir-${trend.direction}` : "dir-none"}`}>
      <b>{title}</b>
      <strong>{value}</strong>
      <small>{secondSourceSentence(trend) ?? "Sin segunda fuente para esta variable."}</small>
    </div>
  );
}

function Step({ title, situation, options, chosen, onChoose, locked }: {
  title: string; situation: string; options: Option[]; chosen: string | null; onChoose: (id: string) => void; locked: boolean;
}) {
  const picked = options.find((item) => item.id === chosen);
  return (
    <section className="gameStep">
      <h3>{title}</h3>
      <p>{situation}</p>
      <div className="gameOptions" role="group" aria-label={title}>
        {options.map((option) => (
          <button key={option.id} type="button" disabled={locked || chosen != null}
            className={chosen ? (option.correct ? "right" : option.id === chosen ? "wrong" : "") : ""}
            onClick={() => onChoose(option.id)}>{option.text}</button>
        ))}
      </div>
      {picked && <p className={`gameFeedback ${picked.correct ? "ok" : "ko"}`} role="status">{picked.feedback}</p>}
    </section>
  );
}

const VOICE = "Voz del pueblo";

export function MissionPanel({ mission, role, heroName, onComplete, onBack, done, checkpoints, visited }: {
  mission: Mission; role: Role; heroName: string; onComplete: (badges: string[]) => void; onBack: () => void; done: boolean;
  checkpoints: Checkpoint[]; visited: Set<string>;
}) {
  const steps = missionSteps(mission);
  const [answers, setAnswers] = useState<(string | null)[]>(steps.map(() => null));
  const spectator = role === "espectador";
  const current = answers.findIndex((item) => item == null);
  const finished = current === -1;
  const allWarned = checkpoints.length > 0 && checkpoints.every((item) => visited.has(item.id));
  const quizBadges = steps.filter((step, index) => step.options.find((option) => option.id === answers[index])?.correct).map((step) => step.badge);
  const earned = [...quizBadges, ...(allWarned ? [VOICE] : [])];
  const earnedKey = earned.join("|");

  const choose = (index: number, id: string) => setAnswers(answers.map((item, i) => (i === index ? id : item)));

  // Se guarda el progreso cuando termina el cuestionario o cuando avisa a todo el pueblo.
  useEffect(() => {
    if (spectator || (!finished && !allWarned)) return;
    onComplete(earnedKey ? earnedKey.split("|") : []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [earnedKey, finished, allWarned, spectator]);

  return (
    <aside className="gamePanel" aria-labelledby="mission-title">
      <button type="button" className="gameBack" onClick={onBack}>← Volver al globo</button>
      <p className="gameEyebrow">{mission.continent} · {mission.country}</p>
      <h2 id="mission-title">{mission.name}</h2>
      <p className={`gameHeat heat-${mission.heat}`}><i />{HEAT_LABEL[mission.heat]}</p>

      <div className="gameContext">
        <b>Contexto del lugar</b>
        <p>{mission.context}</p>
        <small>Texto de referencia del equipo, sin cifras; no es un dato medido por la plataforma.</small>
      </div>

      <section className="gameData" aria-label="Lo que miden los datos">
        <h3>Lo que miden los datos desde 2001</h3>
        {mission.temperature && <Sparkline trend={mission.temperature} label="Temperatura media anual" />}
        <TrendRow title="Temperatura" trend={mission.temperature} kind="temp" />
        <TrendRow title="Lluvia" trend={mission.rain} kind="ratio" />
        <TrendRow title="Sol que llega al suelo" trend={mission.sun} kind="ratio" />
        <p className="gameGap"><b>Lo que esta misión no mide:</b> {mission.not_measured} Es una brecha, no un «sin problema».</p>
      </section>

      {spectator ? (
        <section className="gameStep">
          <h3>Lo que leería un detective</h3>
          <p>{temperatureSentence(mission)} {secondSourceSentence(mission.temperature) ?? ""}</p>
          <ul className="gameWarnList">
            {checkpoints.map((item) => <li key={item.id} className="done"><b>{item.title}</b><span>{item.message}</span></li>)}
          </ul>
          <p className="gameMuted">Estás mirando como espectador. Para correr por el lugar y avisar al pueblo, entra como jugador.</p>
        </section>
      ) : (
        <>
          {steps.map((step, index) => (index <= (finished ? steps.length : current)) && (
            <Step key={step.id} title={step.title} situation={step.situation} options={step.options}
              chosen={answers[index]} onChoose={(id) => choose(index, id)} locked={index !== current} />
          ))}
          <section className="gameStep warn">
            <h3>Paso 3 · Avisa al pueblo</h3>
            <p>Corre por el lugar y llega a cada «!» para avisarle a la gente lo que dicen los datos.</p>
            <ul className="gameWarnList">
              {checkpoints.map((item) => (
                <li key={item.id} className={visited.has(item.id) ? "done" : ""}>
                  <b>{visited.has(item.id) ? "✓" : "!"} {item.title}</b>
                  {visited.has(item.id) ? <span>{item.message}</span> : <span className="gameMuted">Todavía no llegas aquí.</span>}
                </li>
              ))}
            </ul>
            {allWarned && <p className="gameFeedback ok" role="status">¡Avisaste a todo el pueblo! Ganaste: {VOICE}.</p>}
          </section>
          {finished && (
            <section className="gameReward" role="status">
              <h3>{earned.length ? `¡Misión cumplida, ${heroName}!` : `Misión terminada, ${heroName}`}</h3>
              <p>{earned.length ? `Ganaste: ${earned.join(" y ")}.` : "Esta vez no ganaste insignias; puedes volver a intentarlo."}</p>
              {!earned.length && <button type="button" onClick={() => setAnswers(steps.map(() => null))}>Intentar de nuevo</button>}
            </section>
          )}
          {done && !finished && <p className="gameMuted">Ya completaste esta misión antes; puedes repetirla.</p>}
        </>
      )}

      <footer className="gameSource">
        {mission.analysis.dataset ?? "NASA POWER"} {mission.analysis.version ?? ""} · {mission.analysis.provenance} · periodo {mission.analysis.period ?? "—"} · descargado {dateOf(mission.analysis.downloaded_at)}.
        Celda de grilla de unos 50 km: no reemplaza una estación en tierra.
      </footer>
    </aside>
  );
}
