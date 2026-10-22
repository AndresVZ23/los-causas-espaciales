import type { NasaQuestion } from "./types";

const STATUS: Record<NasaQuestion["status"], string> = { RESPONDIDA: "Respondida", PARCIAL: "Respondida con salvedades", EVIDENCIA_INSUFICIENTE: "Evidencia insuficiente" };

type Props = { questions: NasaQuestion[]; onGoToStage: (step: number) => void };

export default function NasaQuestions({ questions, onGoToStage }: Props) {
  if (!questions.length) return null;
  return (
    <section className="questionsPanel" aria-labelledby="questions-title">
      <div className="questionsHead">
        <h3 id="questions-title">Las preguntas del reto NASA</h3>
        <p><span lang="en">Be An Earth System Trend Detective!</span> · cuatro preguntas del reto y una quinta del producto, respondidas solo con resultados calculados.</p>
      </div>
      <ol>
        {questions.map((question, index) => (
          <li key={question.key} id={`pregunta-${question.key}`} className={`question ${question.key === "so_what" ? "productQuestion" : ""}`} tabIndex={-1}>
            <span className="questionIndex" aria-hidden="true">{index + 1}</span>
            <div className="questionBody">
              {question.key === "so_what" && <span className="questionKicker">Quinta pregunta · Los Causas Espaciales</span>}
              <h4>{question.question_es}<small lang="en">{question.question}</small></h4>
              <p>{question.answer}</p>
              {question.evidence.length > 0 && (
                <details>
                  <summary>Evidencia y método ({question.evidence.length})</summary>
                  <ul>{question.evidence.map((item) => <li key={item}>{item}</li>)}</ul>
                </details>
              )}
            </div>
            <div className="questionMeta">
              <span className={`questionStatus status-${question.status.toLowerCase()}`}><i aria-hidden="true" />{STATUS[question.status]}</span>
              <span className="questionProvenance">{question.provenance.join(" · ")}</span>
              <span className="questionStages">
                {question.stage_steps.map((step) => <button key={step} type="button" onClick={() => onGoToStage(step)}>Etapa {step}</button>)}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
