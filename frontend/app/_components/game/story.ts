// La historia del modo jugador: un futuro perdido (2031), un salto de cinco años atrás y un cuaderno que cambia.
//
// Es FICCIÓN y se declara como tal en pantalla: no es un pronóstico ni un dato. Por eso aquí no hay ninguna cifra medida
// ni ningún hecho atribuido a un lugar real: solo años de la historia (2031, 2026), la edad de un personaje y el año en
// que empiezan las series (2001). Las cifras de cada misión siguen saliendo de la plataforma (mission-logic.ts).
// La idea que sostiene la historia es la misma del producto: los datos estaban; faltó leerlos a tiempo, comprobarlos
// con una segunda fuente, decir lo que no se sabe y salir a avisar. El final bueno no detiene la lluvia: detiene el silencio.
// Mensaje de cierre (pedido de Christian, 14-nov): el héroe no lo salvó todo; la gente tomó conciencia y cambió la
// situación. Quien juega no tiene nave, pero con Los Causas Espaciales sí tiene el conocimiento para hacer el cambio.

import type { Mission } from "./game-types";

/** Lugares que hay que avisar a tiempo para que cambie la última hoja del cuaderno. */
export const STORY_GOAL = 3;
export const STORY_NOTICE = "Esto es una historia, no un pronóstico. Las cifras de cada misión sí son datos reales.";

export type Outcome = "salvado" | "perdido";

export interface StorySlide {
  /** Rótulo corto sobre el texto (el año). */
  kicker?: string;
  lines: string[];
  /** Hoja del cuaderno: se dibuja como papel escrito a mano. */
  letter?: string[];
}

const KILLA_LOST = [
  "Para quien encuentre esto:",
  "Me llamo Killa y tengo nueve años.",
  "Mi abuela dice que antes el río avisaba. Esa noche no avisó nadie.",
  "Después, en la radio, dijeron que los satélites lo estaban viendo desde hacía años.",
  "No entiendo. Si lo estaban viendo, ¿por qué nadie vino a decirnos?",
  "Si encuentras mi cuaderno, guárdalo, por favor. Lo necesito para el lunes.",
];

const KILLA_SAVED = [
  "Para quien encuentre esto:",
  "Me llamo Killa y tengo nueve años.",
  "Hoy el río creció. Sonó la sirena y subimos todos al cerro, como en los ensayos.",
  "Mi abuela dice que antes el río avisaba. Ahora avisamos nosotros.",
  "Ya no hace falta que guardes mi cuaderno. Lo llevo yo.",
  "El lunes hay clases.",
];

/** Prólogo: lo que el héroe encuentra en 2031, antes de saltar. */
export const PROLOGUE: StorySlide[] = [
  { kicker: "Año 2031", lines: ["Llegas tarde.", "Otra vez."] },
  { lines: ["El río se llevó la calle por donde ibas a entrar.", "En lo que fue la plaza quedan un zapato, una puerta sin casa y una mochila de colegio."] },
  { lines: ["Dentro de la mochila hay un cuaderno. En la última hoja, con letra de niña:"], letter: KILLA_LOST },
  { lines: ["Preguntaste por Killa en todos los albergues. Nadie supo decirte.", "El cuaderno tiene más hojas. Cada una la escribió alguien de un lugar al que también llegaste tarde."] },
  { lines: ["No faltaron datos.", "Estaban ahí desde 2001, en las mismas series que vas a leer.", "Faltó quien las leyera a tiempo, las comprobara con una segunda fuente y saliera a avisar."] },
  { kicker: "Un solo salto", lines: ["Tu nave puede volver cinco años atrás. Noviembre de 2026.", "Nada de esto ha pasado todavía.", "Guardas el cuaderno. Sus hojas siguen escritas."] },
];

/** Hoja de un lugar, tal como está escrita en 2031 si nadie avisa. Una por tipo de peligro del lugar. */
const LOST_PAGE: Record<string, string[]> = {
  huaico: ["Esa noche la quebrada sonó como un camión.", "Mi papá dijo que eran piedras.", "No sabíamos por dónde subir. Nadie nos había dicho por dónde."],
  inundacion: ["El agua entró por la cocina.", "Mi mamá puso mis cuadernos sobre el ropero para que no se mojaran.", "Yo le dije que primero subiéramos nosotros."],
  calor: ["Ese verano el abuelo dejó de salir a la puerta.", "Decía que el calor ya no era como antes.", "Nadie nos dijo que había que cuidarlo distinto."],
  erupcion: ["La ceniza cayó como nieve gris.", "Mi hermano quería jugar con ella.", "No sabíamos hacia dónde había que caminar."],
  avalancha: ["La montaña crujió de noche.", "En el pueblo siempre decían que alguien iba a avisar.", "Esa vez no hubo quién."],
  ninguno: ["Aquí medimos todos los días y mandamos los números.", "Nunca supe si alguien los leía.", "Un día dejaron de preguntarnos por lo que todavía no sabíamos medir."],
};

/** La misma hoja, reescrita, si el héroe leyó bien los datos y avisó a todo el pueblo. */
const SAVED_PAGE: Record<string, string[]> = {
  huaico: ["Hoy llovió fuerte y la quebrada sonó como un camión.", "Pero ya sabíamos por dónde subir. Lo ensayamos el día que vino alguien de lejos a contarnos lo que dicen los datos, y también lo que los datos no saben.", "Desde arriba vimos pasar el barro. Mi papá me apretó la mano.", "Estamos todos."],
  inundacion: ["Hoy el agua entró por la cocina.", "Pero mis cuadernos ya estaban arriba, y nosotros también.", "Mi mamá dice que no fue suerte: alguien vino a avisar antes, y le creímos.", "Mañana toca limpiar. Estamos todos."],
  calor: ["Este verano el abuelo se sienta bajo los árboles nuevos de la plaza.", "A las doce le llevamos agua, como nos enseñaron.", "Dice que el calor ya no es como antes. Y se ríe, porque ahora sabemos cuidarlo."],
  erupcion: ["Hoy cayó ceniza.", "Mi hermano quería jugar con ella y le dije que no: primero la mochila, después el camino que marcamos.", "En el punto de encuentro nos contaron uno por uno.", "Estamos todos."],
  avalancha: ["La montaña crujió de noche.", "Pero la sirena sonó antes, y la calle de arriba ya estaba vacía.", "En la mañana contamos las casas. Faltaban dos.", "No faltaba nadie."],
  ninguno: ["Hoy llegó respuesta.", "Alguien leyó los números y preguntó por lo que todavía no medimos.", "Hacía años que nadie preguntaba eso.", "Mañana salimos a medir otra vez."],
};

const kindOf = (mission: Mission) => (mission.hazard && LOST_PAGE[mission.hazard] ? mission.hazard : "ninguno");

/** Hoja del cuaderno de un lugar: la de 2031 si no se avisó, o la reescrita si el lugar quedó a salvo. */
export function missionPage(mission: Mission, saved: boolean): string[] {
  return (saved ? SAVED_PAGE : LOST_PAGE)[kindOf(mission)];
}

/** Un lugar queda a salvo solo si el héroe leyó bien los datos (todas las respuestas) y avisó a todo el pueblo. */
export function missionOutcome(allCorrect: boolean, finished: boolean, allWarned: boolean): Outcome | null {
  if (!finished) return null;
  if (!allCorrect) return "perdido";
  return allWarned ? "salvado" : null;
}

export function savedCount(story: Record<string, Outcome>): number {
  return Object.values(story).filter((value) => value === "salvado").length;
}

/** El regreso a 2031. Final bueno si se avisó a tiempo en al menos STORY_GOAL lugares; si no, el héroe puede volver a saltar. */
export function finale(saved: number): { good: boolean; slides: StorySlide[] } {
  const places = (count: number) => (count === 1 ? "1 lugar" : `${count} lugares`);
  if (saved >= STORY_GOAL) {
    return {
      good: true,
      slides: [
        { kicker: "Año 2031", lines: ["Vuelves al mismo lugar."] },
        { lines: ["El río creció igual. Las lluvias vinieron igual.", "No lo salvaste todo. Nadie puede.", "Hay casas que ya no están."] },
        { lines: ["Pero la gente está.", "Tú solo llegaste a tiempo con los datos. Lo demás lo hicieron ellos:", "ensayaron por dónde subir, dejaron libre el cauce, plantaron sombra y pidieron la estación que faltaba."] },
        { lines: ["En la plaza hay una mochila de colegio colgada de una banca. Su dueña juega cerca.", "Abres el cuaderno en la última hoja:"], letter: KILLA_SAVED },
        { lines: [`Avisaste a tiempo en ${places(saved)}.`, "El cuaderno todavía tiene hojas por cambiar."] },
        // El cierre le habla a quien juega: el poder del héroe no era la nave, era saber a tiempo. Eso sí existe.
        { kicker: "Hoy", lines: [
          "Tú no tienes una nave para volver cinco años atrás.",
          "No la necesitas. Todavía es hoy.",
          "Con Los Causas Espaciales tienes lo que le faltó a ese 2031: los datos de la Tierra, una segunda fuente que los comprueba y, dicho en voz alta, lo que aún no se sabe.",
          "El conocimiento ya es tuyo. El cambio empieza cuando sales a contarlo.",
        ] },
      ],
    };
  }
  return {
    good: false,
    slides: [
      { kicker: "Año 2031", lines: ["Llegas tarde.", "Otra vez."] },
      { lines: ["El zapato. La puerta sin casa. La mochila."] },
      { lines: ["El cuaderno está donde lo dejaste. La última hoja dice lo mismo:"], letter: KILLA_LOST },
      { lines: [saved === 0 ? "Todavía no avisaste a tiempo en ningún lugar." : `Avisaste a tiempo en ${places(saved)}.`, `Para cambiar esta hoja hacen falta ${STORY_GOAL}.`] },
      { lines: ["Pero tú ya conoces el camino de vuelta."] },
      { kicker: "Hoy", lines: ["En el juego puedes volver a saltar.", "Afuera no hay salto. Hay datos, y todavía es hoy.", "Con Los Causas Espaciales puedes leerlos antes de que sea tarde."] },
    ],
  };
}
