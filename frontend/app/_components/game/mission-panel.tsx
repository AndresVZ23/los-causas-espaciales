"use client";

import { useEffect, useState } from "react";
import { HEAT_LABEL, type Mission, type MissionTrend, type Role } from "./game-types";
import { flagNotes, heatSupportPhrase, heatUnconfirmed, missionSteps, percentPerDecade, perDecade, secondSourceSentence, temperatureSentence, type Checkpoint, type Option } from "./mission-logic";
import { companionLine, missionOutcome, missionPage, STORY_NOTICE, type Outcome } from "./story";
import { decisionSet, type PlanResult } from "./decisions";
import { DecisionStep } from "./decision-step";

/** Salud que cuesta una mala decisión (respuesta equivocada o plan débil). La aplica el mundo 3D (ADR-050). */
export const BAD_DECISION_DAMAGE = 20;

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
  // Sin pendiente no se dibuja la recta: una pendiente faltante no es una recta plana.
  const slope = trend.slope_per_year;
  return (
    <figure className="gameSpark">
      <svg viewBox="0 0 300 80" role="img" aria-label={`${label}: ${points.length} años, de ${fmt(values[0])} a ${fmt(values[values.length - 1])} ${trend.unit ?? ""}`}>
        <path d={path} className="line" />
        {trend.significant && slope != null && <path d={`M${x(x0)} ${y(median + slope * (x0 - midYear))} L${x(x1)} ${y(median + slope * (x1 - midYear))}`} className={`fit dir-${trend.direction}`} />}
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
      // Sin promedio no hay porcentaje: se dice el sentido y que falta el dato, nunca «0 %».
      : pct == null ? `${decade > 0 ? "Aumenta" : "Disminuye"} · sin dato de porcentaje`
        : `${pct > 0 ? "+" : "−"}${fmt(Math.abs(pct))} % por década`;
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

/** Aerosoles en la columna de aire (AOD a 550 nm, NASA POWER). Solo existe en las misiones de aire, como Lima. */
function AirRow({ mission }: { mission: Mission }) {
  const air = mission.air;
  if (!air) return <div className="gameTrend"><b>Aerosoles en el aire</b><p className="gameMuted">No disponible para este lugar (brecha declarada, no un cero).</p></div>;
  const decade = perDecade(air);
  const peak = air.annual_series.filter((item): item is { year: number; value: number } => item.value != null).sort((a, b) => b.value - a.value)[0];
  return (
    <div className={`gameTrend ${air.significant ? `dir-${air.direction}` : "dir-none"}`}>
      <b>Aerosoles en la columna de aire (AOD)</b>
      <strong>{!air.significant || decade == null ? "Sin evidencia suficiente de tendencia" : `${decade > 0 ? "+" : "−"}${fmt(Math.abs(decade), 3)} por década`}</strong>
      <small>Promedio desde 2001: {air.mean != null ? fmt(air.mean, 2) : "sin dato"}{peak ? ` · año más alto: ${peak.year} (${fmt(peak.value, 2)})` : ""}. Es toda la columna de aire sobre una celda de unos 100 km, no el aire que se respira en la calle. {air.note ?? ""}</small>
    </div>
  );
}

const VOICE = "Voz del pueblo";

export function MissionPanel({ mission, role, heroName, onComplete, onBack, done, checkpoints, visited, pageSaved = false, onOutcome, onPlan, onHurt, briefing }: {
  mission: Mission; role: Role; heroName: string; onComplete: (badges: string[]) => void; onBack: () => void; done: boolean;
  checkpoints: Checkpoint[]; visited: Set<string>;
  /** Historia: la hoja del cuaderno de este lugar ya cambió en una partida anterior. */
  pageSaved?: boolean;
  onOutcome?: (id: string, outcome: Outcome) => void;
  /** Plan confirmado en el paso 3, con su calidad (0 a 4). */
  onPlan?: (id: string, quality: number) => void;
  /** Mala decisión: cuánta salud cuesta. */
  onHurt?: (amount: number) => void;
  /** Transmisión de la doctora Nikol para este lugar (fuera del Perú, donde no está Christian). */
  briefing?: string;
}) {
  const steps = missionSteps(mission);
  const [answers, setAnswers] = useState<(string | null)[]>(steps.map(() => null));
  const spectator = role === "espectador";
  const current = answers.findIndex((item) => item == null);
  const allWarned = checkpoints.length > 0 && checkpoints.every((item) => visited.has(item.id));
  const quizBadges = steps.filter((step, index) => step.options.find((option) => option.id === answers[index])?.correct).map((step) => step.badge);
  const earned = [...quizBadges, ...(allWarned ? [VOICE] : [])];
  const earnedKey = earned.join("|");
  const support = heatSupportPhrase(mission);
  // Años atípicos de lluvia como dato neutro; primero los que la plataforma considera artefacto probable. Se muestran tres.
  const notes = flagNotes(mission).sort((a, b) => Number(b.artifact) - Number(a.artifact));

  const choose = (index: number, id: string) => {
    setAnswers(answers.map((item, i) => (i === index ? id : item)));
    // Leer mal los datos es una mala decisión: cuesta salud (la aplica el mundo 3D).
    if (!spectator && !steps[index].options.find((option) => option.id === id)?.correct) onHurt?.(BAD_DECISION_DAMAGE);
  };
  // Paso 3: el plan con recursos limitados. Cuenta como hecho al confirmarlo; un plan débil cuesta salud.
  const set = decisionSet(mission);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [planKey, setPlanKey] = useState(0);
  const confirmPlan = (result: PlanResult) => {
    setPlan(result);
    onPlan?.(mission.id, result.quality);
    if (result.weak) onHurt?.(BAD_DECISION_DAMAGE);
  };
  const quizDone = current === -1;
  const allCorrect = quizBadges.length === steps.length;
  // «finished»: leyó los datos (pasos 1 y 2) y confirmó un plan (paso 3). Con una respuesta equivocada se cierra antes:
  // la hoja no cambia y no hace falta decidir el plan para saberlo.
  const finished = quizDone && (!!plan || !allCorrect);
  const resetAll = () => { setAnswers(steps.map(() => null)); setPlan(null); setPlanKey((value) => value + 1); };
  const companion = companionLine(mission);

  // Se guarda el progreso cuando termina la misión o cuando avisa a todo el pueblo.
  // Sin insignias no se guarda nada: cero insignias no es una misión completada (las ya ganadas las conserva game.tsx).
  useEffect(() => {
    if (spectator || (!finished && !allWarned) || !earnedKey) return;
    onComplete(earnedKey.split("|"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [earnedKey, finished, allWarned, spectator]);

  // Historia: la hoja de este lugar cambia solo si el viajero leyó bien los datos, decidió un plan y avisó a todo el pueblo.
  const outcome = spectator ? null : missionOutcome(allCorrect, finished, allWarned);
  const saved = pageSaved || outcome === "salvado";
  useEffect(() => {
    if (outcome) onOutcome?.(mission.id, outcome);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outcome, mission.id]);
  const page = !spectator && (
    <section className={`gamePage ${saved ? "saved" : outcome === "perdido" ? "lost" : ""}`} aria-label="Hoja del cuaderno de este lugar">
      <h3>El cuaderno de Killa · hoja de {mission.name}</h3>
      <blockquote className="gameLetter still">{missionPage(mission, saved).map((line) => <p key={line}>{line}</p>)}</blockquote>
      {saved ? <p className="gamePageNote" role="status">La hoja cambió. Lo que venía, vino igual; esta vez alguien avisó a tiempo y la gente decidió qué hacer.</p>
        : outcome === "perdido" ? <><p className="gamePageNote" role="status">La hoja no cambió. Todavía estás en 2026: puedes volver a leer los datos.</p><button type="button" onClick={resetAll}>Intentar de nuevo</button></>
          : finished ? <p className="gamePageNote" role="status">Leíste bien los datos y tienes un plan, pero la hoja aún no cambia: aquí nadie lo sabe todavía. Llega a cada «!» para avisar.</p>
            : <p className="gamePageNote">Así está escrita en el archivo de 2045. Cambia si lees bien los datos, decides un plan con la gente y avisas a todo el pueblo.</p>}
      <small>{STORY_NOTICE}</small>
    </section>
  );
  // Quién habla al llegar: Christian en el Perú; fuera, la doctora Nikol por radio.
  const voice = companion ?? (briefing ? { who: "Dra. Nikol · transmisión desde 2045", text: briefing } : null);
  return (
    <aside className="gamePanel" aria-labelledby="mission-title">
      <button type="button" className="gameBack" onClick={onBack}>← Volver al globo</button>
      <p className="gameEyebrow">{mission.continent} · {mission.country}</p>
      <h2 id="mission-title">{mission.name}</h2>
      {/* «gamePanelHeat» y no «gameHeat»: ese nombre es también el velo de calor del mundo 3D, que la volvía una capa absoluta encima de la tarjeta «Temperatura». */}
      <p className={`gamePanelHeat heat-${mission.heat}${heatUnconfirmed(mission) ? " hollow" : ""}`}><i />{HEAT_LABEL[mission.heat]}{support && <small> · {support}</small>}</p>

      {!spectator && voice && (
        <div className="gameVoice" role="note">
          <b>{voice.who}</b>
          <p>{voice.text}</p>
        </div>
      )}

      <div className="gameContext">
        <b>Contexto del lugar</b>
        <p>{mission.context}</p>
        <small>Texto de referencia del equipo: no lo midió la plataforma y puede no coincidir con lo que miden los datos de abajo.</small>
        {mission.context_sources?.length ? (
          <small>Fuentes del contexto: {mission.context_sources.map((source, index) => (
            <span key={source.url}>{index > 0 && " · "}<a href={source.url} target="_blank" rel="noreferrer">{source.title} ↗</a></span>
          ))}</small>
        ) : <small>Sin fuente enlazada.</small>}
      </div>

      <section className="gameData" aria-label="Lo que miden los datos">
        <h3>Lo que miden los datos desde 2001</h3>
        {mission.temperature && <Sparkline trend={mission.temperature} label="Temperatura media anual" />}
        <TrendRow title="Temperatura" trend={mission.temperature} kind="temp" />
        <TrendRow title="Lluvia" trend={mission.rain} kind="ratio" />
        <TrendRow title="Sol que llega al suelo" trend={mission.sun} kind="ratio" />
        {mission.hazard === "aire" && <AirRow mission={mission} />}
        {notes.slice(0, 3).map((note) => (
          <div key={note.id} className="gameTrend dir-none"><b>{note.title}</b><strong>{note.value}</strong><small>{note.detail}</small></div>
        ))}
        {notes.length > 3 && <p className="gameMuted">Y {notes.length - 3} {notes.length - 3 === 1 ? "año atípico más" : "años atípicos más"} en este lugar, que no se listan aquí.</p>}
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
          {/* La hoja va antes de los pasos mientras se juega (lo que está en juego) y al final cuando ya se decidió. */}
          {!finished && page}
          {steps.map((step, index) => (index <= (quizDone ? steps.length : current)) && (
            <Step key={step.id} title={step.title} situation={step.situation} options={step.options}
              chosen={answers[index]} onChoose={(id) => choose(index, id)} locked={index !== current} />
          ))}
          {quizDone && allCorrect && <DecisionStep key={`${mission.id}-${planKey}`} set={set} locked={false} onConfirm={confirmPlan} />}
          <section className="gameStep warn">
            <h3>Paso 4 · Avisa al pueblo</h3>
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
              {/* Con una respuesta equivocada la hoja del lugar no cambia: se conservan las insignias, pero no se celebra. */}
              <h3>{earned.length && outcome !== "perdido" ? `¡Misión cumplida, ${heroName}!` : `Misión terminada, ${heroName}`}</h3>
              <p>{earned.length ? `Ganaste: ${earned.join(" y ")}.` : done ? "Esta vez no ganaste insignias; conservas las que ya tenías y puedes volver a intentarlo." : "Esta vez no ganaste insignias; puedes volver a intentarlo."}</p>
              {(!earned.length || outcome === "perdido") && <button type="button" onClick={resetAll}>Intentar de nuevo</button>}
            </section>
          )}
          {finished && page}
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
