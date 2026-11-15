// Paso 3 de cada misión: decidir con recursos limitados (ADR-050). Funciones y textos puros, sin React.
//
// Es una SIMULACIÓN del juego y se declara en pantalla: los efectos (personas, naturaleza, comunidad) son una regla de
// juego para pensar en beneficios y límites, no una medición ni un modelo de la plataforma. No hay una única respuesta
// correcta: se valora que el plan sea equilibrado, que use los recursos y que sume a la comunidad.
// Las medidas son recomendaciones generales de gestión del riesgo y de adaptación; no traen cifras.

import type { Mission } from "./game-types";

export type Axis = "personas" | "naturaleza" | "comunidad";
export const AXES: { id: Axis; label: string }[] = [
  { id: "personas", label: "Protege a las personas" },
  { id: "naturaleza", label: "Cuida agua, suelo y ecosistemas" },
  { id: "comunidad", label: "Suma a la comunidad" },
];

export interface Measure {
  id: string;
  text: string;
  /** Fichas de recurso que cuesta. */
  cost: number;
  effects: Partial<Record<Axis, number>>;
  benefit: string;
  limit: string;
}

export interface DecisionSet {
  key: string;
  title: string;
  situation: string;
  /** Lo que dice la indiferencia, el antagonista del juego: desinformación, desinterés y falta de cooperación. */
  indifference: string;
  budget: number;
  measures: Measure[];
}

export const DECISION_NOTICE = "Simulación del juego: los efectos son una regla para pensar en beneficios y límites, no una medición.";
const BUDGET = 4;

const SETS: Record<string, Omit<DecisionSet, "key" | "budget">> = {
  huaico: {
    title: "Paso 3 · Decide antes de la temporada de lluvias",
    situation: "Las quebradas que bajan hacia el pueblo pueden activarse con lluvias fuertes en la sierra. Tienes recursos limitados. ¿En qué los inviertes?",
    indifference: "«Aquí siempre ha bajado agua y no ha pasado nada. ¿Para qué gastar?»",
    measures: [
      { id: "ruta", text: "Señalizar rutas de evacuación y hacer simulacros", cost: 1, effects: { personas: 2, comunidad: 2 }, benefit: "La gente sabe por dónde subir y lo ensaya.", limit: "No frena el huaico: solo prepara a las personas." },
      { id: "alerta", text: "Alerta temprana: pluviómetros arriba y sirena abajo", cost: 2, effects: { personas: 3, comunidad: 1 }, benefit: "Da minutos valiosos para salir.", limit: "Necesita mantenimiento y alguien que la vigile todo el año." },
      { id: "muros", text: "Muros y diques en la quebrada", cost: 2, effects: { personas: 2, naturaleza: -1 }, benefit: "Contiene parte del material que baja.", limit: "Caros; si se llenan de lodo fallan, y pueden dar una falsa seguridad." },
      { id: "reforestar", text: "Reforestar la parte alta de la cuenca", cost: 1, effects: { naturaleza: 3, personas: 1 }, benefit: "Las raíces sujetan el suelo y frenan la erosión.", limit: "Tarda años en hacer efecto." },
      { id: "reubicar", text: "Reubicar las casas que están en el cauce", cost: 2, effects: { personas: 3, comunidad: -1 }, benefit: "Saca a las familias del camino del huaico.", limit: "Socialmente difícil: sin acuerdo, la gente vuelve." },
      { id: "cauce", text: "Limpiar cauces y dejar de botar desmonte", cost: 1, effects: { personas: 1, naturaleza: 1, comunidad: 1 }, benefit: "El agua y el lodo encuentran su camino libre.", limit: "Hay que repetirlo cada año." },
    ],
  },
  inundacion: {
    title: "Paso 3 · Decide antes de que crezca el río",
    situation: "El río puede desbordarse y el agua entrar a las calles. Tienes recursos limitados. ¿En qué los inviertes?",
    indifference: "«El agua siempre se va sola. Ya veremos cuando llegue.»",
    measures: [
      { id: "alerta", text: "Alerta temprana conectada al pronóstico de lluvia", cost: 2, effects: { personas: 3, comunidad: 1 }, benefit: "Avisa con tiempo para salir.", limit: "Sirve solo si la gente confía y sabe qué hacer." },
      { id: "refugio", text: "Zonas altas de refugio y simulacros", cost: 1, effects: { personas: 2, comunidad: 2 }, benefit: "Cada familia sabe a dónde ir.", limit: "No evita los daños en las casas." },
      { id: "diques", text: "Defensas ribereñas y diques", cost: 2, effects: { personas: 2, naturaleza: -1 }, benefit: "Contiene crecidas moderadas.", limit: "Una crecida mayor los supera; encauzan el problema río abajo." },
      { id: "humedal", text: "Recuperar humedales y zonas que el río puede ocupar", cost: 2, effects: { naturaleza: 3, personas: 1 }, benefit: "Dan espacio al agua y la absorben como una esponja.", limit: "Necesita terreno libre y tiempo." },
      { id: "drenaje", text: "Limpiar canales y drenes de la ciudad", cost: 1, effects: { personas: 1, naturaleza: 1 }, benefit: "El agua de lluvia sale más rápido.", limit: "No alcanza si el río se desborda." },
      { id: "norma", text: "No construir más en zonas inundables", cost: 1, effects: { personas: 2, comunidad: -1 }, benefit: "Evita poner más casas en riesgo.", limit: "Genera conflicto si no se ofrece otra opción." },
    ],
  },
  calor: {
    title: "Paso 3 · Decide frente al calor y la sequía",
    situation: "El agua escasea y el calor aprieta. Tienes recursos limitados y no existe una única combinación correcta. ¿Cómo los distribuyes?",
    indifference: "«Siempre hubo veranos así. Que cada uno se las arregle.»",
    measures: [
      { id: "almacenar", text: "Infraestructura para almacenar agua", cost: 2, effects: { personas: 2, naturaleza: -1 }, benefit: "Guarda agua para los meses secos.", limit: "Si no llueve, no hay qué guardar; altera los ríos." },
      { id: "riego", text: "Sistemas de riego eficientes", cost: 1, effects: { naturaleza: 2, personas: 1 }, benefit: "Las chacras producen con menos agua.", limit: "Requiere capacitación y mantenimiento." },
      { id: "poblacion", text: "Priorizar el agua para la población", cost: 1, effects: { personas: 2, naturaleza: -1 }, benefit: "Nadie se queda sin agua para tomar.", limit: "La agricultura y los ecosistemas reciben menos." },
      { id: "fuentes", text: "Programa de conservación de fuentes de agua", cost: 2, effects: { naturaleza: 3, comunidad: 1 }, benefit: "Protege los manantiales y la recarga de agua.", limit: "Sus efectos se ven a largo plazo." },
      { id: "sombra", text: "Puntos de sombra e hidratación y visitas a adultos mayores", cost: 1, effects: { personas: 2, comunidad: 1 }, benefit: "Cuida a quienes más sufren el calor.", limit: "Alivia, pero no reduce el calor." },
      { id: "arboles", text: "Árboles y áreas verdes en la ciudad", cost: 1, effects: { naturaleza: 2, personas: 1 }, benefit: "Dan sombra y refrescan las calles.", limit: "Necesitan agua y años para crecer." },
    ],
  },
  erupcion: {
    title: "Paso 3 · Decide mientras el volcán está tranquilo",
    situation: "El volcán puede aumentar su actividad. Tienes recursos limitados. ¿En qué los inviertes?",
    indifference: "«Ese volcán lleva años humeando. No va a pasar nada.»",
    measures: [
      { id: "monitoreo", text: "Vigilancia del volcán: sismos, gases y satélites", cost: 2, effects: { personas: 3, comunidad: 1 }, benefit: "Detecta los cambios antes de una erupción.", limit: "Solo sirve si la alerta llega a la gente." },
      { id: "rutas", text: "Rutas de evacuación, puntos de encuentro y simulacros", cost: 1, effects: { personas: 2, comunidad: 2 }, benefit: "Todos saben hacia dónde caminar.", limit: "No protege casas ni cultivos." },
      { id: "mapa", text: "Mapa de peligro: no construir en los valles de los flujos", cost: 1, effects: { personas: 2, comunidad: -1 }, benefit: "Aleja a las familias del camino de los flujos.", limit: "Difícil de cumplir sin otra opción de vivienda." },
      { id: "ceniza", text: "Mascarillas y protección del agua frente a la ceniza", cost: 1, effects: { personas: 1, naturaleza: 1 }, benefit: "Cuida los pulmones y el agua para tomar.", limit: "Es una protección para pocos días." },
      { id: "chacras", text: "Plan para proteger cultivos y animales", cost: 1, effects: { naturaleza: 1, comunidad: 1 }, benefit: "La economía del pueblo resiste mejor.", limit: "No salva vidas por sí solo." },
      { id: "refugios", text: "Refugios reforzados", cost: 2, effects: { personas: 2 }, benefit: "Protegen de la caída de roca y ceniza.", limit: "Caros y para pocas personas." },
    ],
  },
  avalancha: {
    title: "Paso 3 · Decide antes de que la montaña cruja",
    situation: "El hielo y las lagunas de la montaña pueden desprenderse y bajar como un aluvión. Tienes recursos limitados. ¿En qué los inviertes?",
    indifference: "«En el pueblo siempre dicen que alguien va a avisar.»",
    measures: [
      { id: "lagunas", text: "Vigilar lagunas glaciares y laderas", cost: 2, effects: { personas: 3 }, benefit: "Detecta a tiempo una laguna peligrosa.", limit: "Necesita equipo y personal en altura." },
      { id: "sirena", text: "Sirena y simulacros en el pueblo", cost: 1, effects: { personas: 2, comunidad: 2 }, benefit: "La calle de arriba se vacía a tiempo.", limit: "No frena el aluvión." },
      { id: "zonas", text: "Mapa de zonas de peligro bajo la quebrada", cost: 1, effects: { personas: 2, comunidad: -1 }, benefit: "Nadie construye en el camino del aluvión.", limit: "Choca con quienes ya viven allí." },
      { id: "desague", text: "Obras para bajar el nivel de lagunas peligrosas", cost: 2, effects: { personas: 2, naturaleza: -1 }, benefit: "Reduce el agua que podría desprenderse.", limit: "Obras difíciles y caras en alta montaña." },
      { id: "escuelas", text: "Enseñar en las escuelas cómo cambia la montaña", cost: 1, effects: { comunidad: 2, personas: 1 }, benefit: "Los niños llevan el aviso a sus casas.", limit: "Sus efectos son a largo plazo." },
      { id: "queuna", text: "Reforestar laderas con árboles nativos", cost: 1, effects: { naturaleza: 2, personas: 1 }, benefit: "Sujetan el suelo de las laderas.", limit: "No detiene un aluvión grande." },
    ],
  },
  aire: {
    title: "Paso 3 · Decide para que la ciudad vuelva a respirar",
    situation: "En la escuela suspendieron actividades al aire libre. Tienes recursos limitados y ninguna medida resuelve todo sola. ¿Qué combinas?",
    indifference: "«El humo siempre ha estado ahí. Uno se acostumbra.»",
    measures: [
      { id: "movilidad", text: "Plan de movilidad: transporte público y ciclovías", cost: 2, effects: { personas: 2, naturaleza: 2 }, benefit: "Menos carros encendidos en las calles.", limit: "Tarda en construirse y la gente debe cambiar hábitos." },
      { id: "emisiones", text: "Control de emisiones de vehículos y fábricas", cost: 2, effects: { personas: 2, naturaleza: 1 }, benefit: "Ataca las fuentes más grandes de humo.", limit: "Necesita fiscalización constante." },
      { id: "verde", text: "Áreas verdes y árboles en los barrios", cost: 1, effects: { naturaleza: 2, personas: 1 }, benefit: "Más sombra y espacios para estar afuera.", limit: "Sus efectos sobre el aire son limitados." },
      { id: "vigilar", text: "Medir el aire y avisar en los días malos", cost: 1, effects: { personas: 2, comunidad: 1 }, benefit: "Las escuelas pueden organizarse cada día.", limit: "Avisa, pero no limpia el aire." },
      { id: "basura", text: "Campaña contra la quema de basura y para separar residuos", cost: 1, effects: { comunidad: 2, naturaleza: 1 }, benefit: "Los vecinos dejan de quemar y reciclan.", limit: "Depende de que la gente participe." },
      { id: "horarios", text: "Mover el recreo y el deporte a las horas con mejor aire", cost: 1, effects: { personas: 1, comunidad: 1 }, benefit: "Los niños respiran menos humo.", limit: "Se adapta al problema, no lo reduce." },
    ],
  },
  ninguno: {
    title: "Paso 3 · Decide qué medir primero",
    situation: "Aquí lo que más falta es saber. Tienes recursos limitados para investigar. ¿En qué los inviertes?",
    indifference: "«Si nadie lo mide, es que no importa.»",
    measures: [
      { id: "estacion", text: "Instalar una estación meteorológica", cost: 2, effects: { naturaleza: 2, personas: 1, comunidad: 1 }, benefit: "Datos medidos en tierra, no solo desde el espacio.", limit: "Hay que mantenerla en condiciones extremas." },
      { id: "hielo", text: "Medir el hielo en campo y compararlo con satélites", cost: 2, effects: { naturaleza: 3 }, benefit: "Una segunda fuente para lo que ven los satélites.", limit: "Campañas caras y cortas." },
      { id: "abiertos", text: "Compartir los datos abiertos con escuelas", cost: 1, effects: { comunidad: 2, naturaleza: 1 }, benefit: "Más personas aprenden a leerlos.", limit: "Compartir no reemplaza medir más." },
      { id: "cooperar", text: "Cooperación científica entre países", cost: 1, effects: { comunidad: 1, naturaleza: 1, personas: 1 }, benefit: "Se reparten costos y se comparan métodos.", limit: "Los acuerdos tardan." },
      { id: "residuos", text: "Reducir residuos y combustible en la base", cost: 1, effects: { naturaleza: 2 }, benefit: "Menos huella en un lugar frágil.", limit: "No aporta datos nuevos." },
      { id: "avisar", text: "Publicar en voz alta lo que todavía no se sabe", cost: 1, effects: { comunidad: 2, personas: 1 }, benefit: "Las brechas se ven y se pueden financiar.", limit: "Decir lo que falta no lo resuelve." },
    ],
  },
};

/** Clave del conjunto de decisiones: el peligro del lugar o «ninguno». */
export function decisionKey(mission: Mission): string {
  return mission.hazard && SETS[mission.hazard] ? mission.hazard : "ninguno";
}

export function decisionSet(mission: Mission): DecisionSet {
  const key = decisionKey(mission);
  return { key, budget: BUDGET, ...SETS[key] };
}

export function allDecisionSets(): DecisionSet[] {
  return Object.keys(SETS).map((key) => ({ key, budget: BUDGET, ...SETS[key] }));
}

export function spent(set: DecisionSet, chosen: string[]): number {
  return set.measures.filter((item) => chosen.includes(item.id)).reduce((sum, item) => sum + item.cost, 0);
}

/** ¿Se puede sumar esta medida sin pasarse del presupuesto? */
export function affordable(set: DecisionSet, chosen: string[], id: string): boolean {
  const measure = set.measures.find((item) => item.id === id);
  return !!measure && spent(set, chosen) + measure.cost <= set.budget;
}

export interface PlanResult {
  totals: Record<Axis, number>;
  used: number;
  /** Calidad del plan, de 0 a 4: suma puntos al estado del planeta. */
  quality: number;
  /** Plan débil: cuenta como mala decisión y cuesta salud. */
  weak: boolean;
  verdict: string;
  notes: string[];
}

/**
 * Valora un plan. No hay respuesta única: suma un punto por un plan con efecto amplio, otro si es muy completo, otro si
 * no deja ningún eje en contra y otro si suma a la comunidad. Dejar fichas sin usar resta: la indiferencia también decide.
 */
export function evaluatePlan(set: DecisionSet, chosen: string[]): PlanResult {
  const picked = set.measures.filter((item) => chosen.includes(item.id));
  const totals: Record<Axis, number> = { personas: 0, naturaleza: 0, comunidad: 0 };
  for (const item of picked) for (const axis of AXES) totals[axis.id] += item.effects[axis.id] ?? 0;
  const used = picked.reduce((sum, item) => sum + item.cost, 0);
  const sum = totals.personas + totals.naturaleza + totals.comunidad;
  const lowest = Math.min(totals.personas, totals.naturaleza, totals.comunidad);
  let quality = 0;
  if (sum >= 5) quality += 1;
  if (sum >= 7) quality += 1;
  if (lowest >= 1) quality += 1;
  if (totals.comunidad >= 2) quality += 1;
  const idle = set.budget - used;
  if (idle >= 2) quality = Math.max(0, quality - 1);
  const notes: string[] = [];
  if (idle >= 2) notes.push("Dejaste recursos sin usar. La indiferencia también es una decisión.");
  if (totals.comunidad < 1) notes.push("Sin la comunidad, el plan se queda en el papel: nadie lo cuida ni lo ensaya.");
  if (totals.naturaleza < 0) notes.push("Tu plan protege hoy, pero deja la naturaleza peor que antes.");
  if (totals.personas < 2) notes.push("Las personas siguen muy expuestas si el peligro llega pronto.");
  const verdict = quality >= 4 ? "Plan equilibrado: protege a la gente, cuida el entorno y suma a la comunidad."
    : quality === 3 ? "Buen plan, con algún punto débil."
      : quality === 2 ? "Plan posible, pero deja huecos importantes."
        : "Plan débil: la indiferencia gana terreno.";
  return { totals, used, quality, weak: quality <= 1, verdict, notes };
}
