"use client";

import { useEffect, useState } from "react";
import type { AnyResult } from "./types";

type Exchange = { question: string; answer: string; mode: "gemini" | "reglas"; model: string | null; citations: string[]; notice: string | null };

const SUGGESTIONS: Record<string, string[]> = {
  solar: ["¿Cuál es el mejor sitio según el puntaje?", "¿Qué pasa con el VAN en el escenario adverso?", "¿Sube la temperatura?", "¿Qué brechas faltan cubrir?"],
  climate: ["¿Qué está cambiando?", "¿Hay más lluvias extremas?", "¿Cómo va la lluvia este año?", "¿Qué dice el contraste con IMERG?"],
};
const MAX_HISTORY = 6;

export default function AssistantPanel({ result }: { result: AnyResult }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<Exchange[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [geminiAvailable, setGeminiAvailable] = useState(false);
  // Cada análisis nuevo empieza su propia conversación: las respuestas solo valen para el análisis que las produjo.
  useEffect(() => { setHistory([]); setError(""); }, [result.analysis_id, result.sector]);
  useEffect(() => {
    fetch("/api/assistant").then((response) => response.json()).then((payload) => setGeminiAvailable(Boolean(payload.gemini_available))).catch(() => setGeminiAvailable(false));
  }, []);

  async function ask(text: string, useGemini = false) {
    const clean = text.trim();
    if (clean.length < 3 || busy) return;
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/assistant", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: clean, envelope: result, use_gemini: useGemini }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "El asistente no pudo responder.");
      setHistory((current) => [{ question: clean, ...payload } as Exchange, ...current].slice(0, MAX_HISTORY));
      setQuestion("");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "El asistente no pudo responder.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="assistantPanel" aria-labelledby="asistente-title">
      <div className="panelHeader">
        <div>
          <h3 id="asistente-title">Pregunte al análisis</h3>
          <p>Responde solo con los datos de este análisis y cita de dónde salen. No consulta otras fuentes ni da recomendaciones de inversión.</p>
        </div>
        <span>Reglas sin costo{geminiAvailable ? " · Gemini a pedido" : ""}</span>
      </div>
      <form className="assistantForm" onSubmit={(event) => { event.preventDefault(); ask(question); }}>
        <label className="srOnly" htmlFor="pregunta-asistente">Pregunta sobre el análisis</label>
        <input id="pregunta-asistente" value={question} maxLength={500} placeholder="Por ejemplo: ¿qué factor mueve más el VAN?" onChange={(event) => setQuestion(event.target.value)} />
        <button type="submit" disabled={busy || question.trim().length < 3}>{busy ? "Respondiendo…" : "Preguntar"}</button>
        {geminiAvailable && <button type="button" className="geminiAsk" onClick={() => ask(question, true)} disabled={busy || question.trim().length < 3}>Preguntar a Gemini</button>}
      </form>
      {geminiAvailable && <p className="assistantQuota">«Preguntar a Gemini» redacta con IA y gasta tu cuota gratuita de Google; «Preguntar» no gasta nada. Si Gemini cita una cifra que no está en el análisis, se descarta.</p>}
      <div className="assistantSuggestions" role="group" aria-label="Preguntas sugeridas">
        {(SUGGESTIONS[result.sector] ?? SUGGESTIONS.climate).map((item) => <button key={item} onClick={() => ask(item)} disabled={busy}>{item}</button>)}
      </div>
      {error && <p className="errorMessage" role="alert">{error}</p>}
      <div className="assistantLog" aria-live="polite">
        {history.map((item, index) => (
          <article key={`${item.question}-${index}`}>
            <p className="assistantQuestion">{item.question}</p>
            <p className="assistantAnswer">{item.answer}</p>
            <p className="assistantMeta">
              <span>{item.mode === "gemini" ? `Gemini · ${item.model}` : "Reglas"}</span>
              {item.citations.length > 0 && <span>Fuente en el análisis: {item.citations.join(" · ")}</span>}
            </p>
            {item.notice && <p className="assistantNotice">{item.notice}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}
