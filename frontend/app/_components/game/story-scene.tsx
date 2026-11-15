"use client";

// Escena de la historia (prólogo de 2045, regresos y finales): texto a pantalla completa, una lámina a la vez.
// Cada línea aparece con una pausa para que se lea despacio; con «reducir movimiento» aparece todo de una vez.
// Se avanza con el botón (Enter o Espacio) y siempre se puede saltar.

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { STORY_NOTICE, type StorySlide } from "./story";

export function StoryScene({ slides, tone, label, doneLabel, onDone, onSkip, link }: {
  slides: StorySlide[]; tone: "perdido" | "salvado"; label: string; doneLabel: string; onDone: () => void; onSkip?: () => void;
  /** Enlace que acompaña al botón de la última lámina (en el final, la plataforma). */
  link?: { href: string; label: string };
}) {
  const [index, setIndex] = useState(0);
  const next = useRef<HTMLButtonElement>(null);
  const slide = slides[index];
  const last = index === slides.length - 1;
  // El foco entra a la escena y se queda en «Continuar»: así Enter o Espacio pasan la lámina sin usar el mouse.
  useEffect(() => { next.current?.focus(); }, [index]);
  // Escape salta la historia, igual que el botón.
  useEffect(() => {
    if (!onSkip) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onSkip(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onSkip]);

  const letterStart = slide.lines.length;
  return (
    <section className={`gameStory tone-${tone}`} role="dialog" aria-modal="true" aria-label={label}>
      {/* La clave por lámina reinicia la aparición escalonada de las líneas. */}
      <div className="gameStoryText" key={index} aria-live="polite">
        {slide.kicker && <p className="gameStoryKicker">{slide.kicker}</p>}
        {slide.lines.map((line, order) => <p key={line} className="gameStoryLine" style={{ animationDelay: `${0.25 + order * 1.1}s` }}>{line}</p>)}
        {slide.letter && (
          <blockquote className="gameLetter" style={{ animationDelay: `${0.25 + letterStart * 1.1}s` }}>
            {slide.letter.map((line, order) => <p key={line} style={{ animationDelay: `${0.9 + (letterStart + order) * 1.1}s` }}>{line}</p>)}
          </blockquote>
        )}
      </div>
      <div className="gameStoryActions">
        <button ref={next} type="button" className="gameGo" onClick={() => (last ? onDone() : setIndex(index + 1))}>{last ? doneLabel : "Continuar"}</button>
        {onSkip && !last && <button type="button" className="gameStorySkip" onClick={onSkip}>Saltar la historia</button>}
        {last && link && <Link href={link.href} className="gameStoryLink">{link.label}</Link>}
      </div>
      <p className="gameStoryNotice">{STORY_NOTICE} · {index + 1} de {slides.length}</p>
    </section>
  );
}
