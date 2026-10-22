import { formatDuration } from "./format";
import type { QuestionKey, Stage } from "./types";

export const QUESTION_LABELS: Record<QuestionKey, string> = {
  what: "¿Qué cambia?",
  where: "¿Dónde?",
  how_much: "¿Cuánto?",
  significant: "¿Es significativo?",
  so_what: "¿Qué significa para invertir?",
};

// Qué hace cada etapa antes de ejecutarla: el pipeline se explica solo, sin resultados inventados.
const STAGE_GUIDE: { name: string; does: string; answers: QuestionKey[] }[] = [
  { name: "Selección", does: "Valida las ubicaciones en WGS84 (EPSG:4326) y mide su separación geodésica.", answers: ["where"] },
  { name: "Configuración", does: "Fija sector, variables NASA POWER, período, α = 0.05 y supuestos financieros.", answers: [] },
  { name: "Extracción", does: "Consulta NASA POWER diario por sitio, con caché de 24 h y procedencia por serie.", answers: ["what"] },
  { name: "Análisis", does: "Medias anuales, Mann–Kendall, pendiente de Sen con IC 95 %, autocorrelación lag-1 y ajuste Benjamini–Hochberg.", answers: ["what", "how_much", "significant"] },
  { name: "Inteligencia territorial", does: "Localiza NASADEM en NASA CMR y declara las capas oficiales que siguen pendientes.", answers: ["where", "so_what"] },
  { name: "Evaluación", does: "Ordena los sitios por irradiancia histórica, sin score compuesto.", answers: ["so_what"] },
  { name: "Impacto económico", does: "Calcula energía y VAN con la irradiancia NASA y los supuestos del usuario.", answers: ["so_what"] },
  { name: "Resultados", does: "Reúne respuestas NASA, tendencias, cautelas y brechas de debida diligencia.", answers: [] },
  { name: "Exportación", does: "Genera el reporte JSON reproducible con identificador, período, supuestos y procedencia.", answers: [] },
];

export const STAGE_NAMES = STAGE_GUIDE.map((item) => item.name);

const STATUS_LABELS: Record<string, string> = { LISTO: "Listo", PENDIENTE: "Pendiente", COMPLETADO: "Completado", PARCIAL: "Parcial", EN_CURSO: "En curso", NO_DISPONIBLE: "No disponible", ERROR: "Error" };
export function stageStatusLabel(status: string) { return STATUS_LABELS[status] ?? status; }
function statusClass(status: string) { return status.toLowerCase().replaceAll("_", "-"); }

type Props = {
  stages: Stage[];
  running: boolean;
  hasResult: boolean;
  selectedStep: number;
  onSelect: (step: number) => void;
  onQuestion: (key: QuestionKey) => void;
};

export default function PipelinePanel({ stages, running, hasResult, selectedStep, onSelect, onQuestion }: Props) {
  const selected = stages.find((stage) => stage.step === selectedStep) ?? stages[0];
  const guide = STAGE_GUIDE[selected.step - 1];
  const answers = selected.answers ?? guide?.answers ?? [];
  const pendingCount = stages.filter((stage) => !["COMPLETADO", "LISTO"].includes(stage.status)).length;

  return (
    <section className={`pipelineStrip ${running ? "isRunning" : ""}`} aria-label="Pipeline de análisis">
      <div className="pipelineMain">
        <div className="pipelineLabel">
          <span>Pipeline de análisis · 9 etapas</span>
          <b aria-live="polite">{running ? "En curso" : hasResult ? (pendingCount ? `Completado · ${pendingCount} con salvedades` : "Completado") : "Preparado"}</b>
        </div>
        <div className="pipelineScroll">
          <ol>
            {stages.map((stage) => (
              <li key={stage.key} className={`${statusClass(running ? "EN_CURSO" : stage.status)} ${stage.step === selected.step ? "selected" : ""}`}>
                <button type="button" aria-pressed={stage.step === selected.step} aria-controls="stage-inspector" onClick={() => onSelect(stage.step)}>
                  <span className="stageDot" aria-hidden="true">{stage.step}</span>
                  <b>{stage.name}</b>
                  <small>{stageStatusLabel(running ? "EN_CURSO" : stage.status)}</small>
                </button>
              </li>
            ))}
          </ol>
        </div>
      </div>
      <div className="stageInspector" id="stage-inspector" aria-live="polite">
        <div className="inspectorHead">
          <span>{String(selected.step).padStart(2, "0")}</span>
          <h3>{selected.name}</h3>
          <em className={statusClass(selected.status)}>{stageStatusLabel(selected.status)}</em>
          {selected.duration_ms != null && <time>{formatDuration(selected.duration_ms)}</time>}
        </div>
        <p className="inspectorSummary">{hasResult ? selected.summary : guide?.does}</p>
        {hasResult && selected.evidence && selected.evidence.length > 0 && (
          <dl className="inspectorEvidence">
            {selected.evidence.map((item) => (
              <div key={item.label}>
                <dt>{item.label}</dt>
                <dd>{item.value}{item.provenance && <i className={`prov-${item.provenance.toLowerCase()}`} title={item.provenance} />}</dd>
              </div>
            ))}
          </dl>
        )}
        <div className="inspectorFoot">
          {hasResult && selected.provenance.length > 0 && <span className="inspectorProvenance">{selected.provenance.join(" · ")}</span>}
          {answers.length > 0 && (
            <span className="inspectorAnswers">
              Responde:
              {answers.map((key) => hasResult
                ? <button key={key} type="button" onClick={() => onQuestion(key)}>{QUESTION_LABELS[key]}</button>
                : <b key={key}>{QUESTION_LABELS[key]}</b>)}
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
