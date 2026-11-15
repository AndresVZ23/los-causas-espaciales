// La historia del modo jugador: TERRA 2045 · El último viaje (ADR-050, reemplaza la de 2031 de ADR-049).
//
// Año 2045. La humanidad vive en la colonia lunar New Horizon. El Proyecto Génesis, de la doctora Nikol, puede enviar a
// una sola persona al año 2026, con energía para tres regresos de emergencia. En el archivo de la evacuación hay un
// cuaderno de colegio, el de Killa, una niña de 2026: cada hoja la escribió alguien de un lugar al que nadie llegó a tiempo.
//
// Personajes: el viajero (nombre y figura los elige quien juega); la doctora Nikol, científica que dirige Génesis y guía
// por radio; Andrés, amigo del viajero en la colonia; Mario, su hermano menor, nacido en la Luna, que le da la foto de
// la Tierra verde; Christian, joven peruano de 2026 que acompaña las misiones del Perú; Killa, la niña del cuaderno.
// El antagonista no es una persona: es la indiferencia (desinformación, desinterés y falta de cooperación).
//
// Es FICCIÓN y se declara como tal en pantalla: no es un pronóstico ni un dato. Por eso aquí no hay ninguna cifra medida
// ni ningún hecho futuro atribuido a un lugar real: solo años de la historia (2045, 2026) y el año en que empiezan las
// series (2001). Las cifras de cada misión siguen saliendo de la plataforma (mission-logic.ts).
// Tesis: los datos estaban; faltó leerlos a tiempo, comprobarlos con una segunda fuente, decir lo que no se sabe y
// salir a avisar. El final bueno no detiene la lluvia: detiene el silencio. Y el héroe no lo salva todo: la gente cambia
// la situación. Quien juega no tiene una máquina del tiempo, pero sí el conocimiento para hacer el cambio.

import type { Mission } from "./game-types";
import { FUNDAMENTAL, MAX_RETURNS, TIERS, type Ending, type PlanetTier, type ReturnCause } from "./planet";

export const STORY_NOTICE = "Esto es una historia, no un pronóstico. Las cifras de cada misión sí son datos reales.";
export const STORY_TITLE = "TERRA 2045 · El último viaje";
export const STORY_TAGLINE = "El futuro no está escrito. Pero cada decisión deja una huella.";

export type Outcome = "salvado" | "perdido";

export interface StorySlide {
  /** Rótulo corto sobre el texto (el año o el lugar). */
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

/** Prólogo: la colonia lunar en 2045, antes del viaje. Resume el video del prólogo. */
export const PROLOGUE: StorySlide[] = [
  { kicker: "Año 2045 · Colonia lunar New Horizon", lines: ["La humanidad lleva doce años viviendo fuera de la Tierra.", "Los recursos alcanzan cada vez para menos."] },
  { lines: ["Desde la ventana de observación, la Tierra ya no es azul.", "Tormentas, incendios y nubes de humo cubren regiones enteras.", "El planeta está muriendo."] },
  { lines: ["Mario, tu hermano menor, nació aquí. Nunca pisó la Tierra.", "—¿Crees que algún día podremos ir? —pregunta.", "Andrés no deja de mirar por la ventana: —Mi abuelo decía que antes se podía respirar aire limpio y beber agua de algunos ríos. Ese era nuestro hogar."] },
  { lines: ["—¿Cómo llegamos a esto? —preguntas.", "—No pasó de un día para otro —responde Andrés—. Cada generación heredó un planeta un poco peor que el anterior. Y todos pensaron que todavía había tiempo."] },
  { kicker: "Proyecto Génesis", lines: ["La doctora Nikol reúne a la colonia.", "—Tenemos registros satelitales y observaciones de la Tierra de décadas. Sabemos cuándo empezó a agravarse todo.", "—Génesis puede enviar a una persona al pasado. Solo hay energía para un viaje. No podemos mandar un ejército ni una máquina que lo arregle todo."] },
  { lines: ["En el archivo de la evacuación hay un cuaderno de colegio. Es de Killa, una niña de 2026. En la última hoja escribió:"], letter: KILLA_LOST },
  { lines: ["Cada hoja del cuaderno la escribió alguien de un lugar al que nadie llegó a tiempo.", "No faltaron datos: estaban ahí desde 2001.", "Faltó quien los leyera a tiempo, los comprobara con una segunda fuente y saliera a avisar."] },
  { lines: ["La doctora Nikol te elige por tu formación científica.", "Antes de partir, Mario te da una fotografía de la Tierra cuando todavía era verde.", "—Quiero que la mires cuando llegues. Para que recuerdes por qué vale la pena."] },
  { kicker: "Destino: 2026", lines: ["—Escucha bien —dice la doctora Nikol—. Si tu salud llega a cero, Génesis te traerá de vuelta. Tienes tres regresos, y solo podrás volver a 2026 si el futuro mejoró.", "—No tienes que salvar el planeta por tu cuenta. Tienes que conseguir que la gente quiera salvarlo contigo.", "Génesis se enciende."] },
];

/** Hoja de un lugar, tal como está escrita en el archivo de 2045 si nadie avisa. Una por tipo de peligro. */
const LOST_PAGE: Record<string, string[]> = {
  huaico: ["Esa noche la quebrada sonó como un camión.", "Mi papá dijo que eran piedras.", "No sabíamos por dónde subir. Nadie nos había dicho por dónde."],
  inundacion: ["El agua entró por la cocina.", "Mi mamá puso mis cuadernos sobre el ropero para que no se mojaran.", "Yo le dije que primero subiéramos nosotros."],
  calor: ["Ese verano el abuelo dejó de salir a la puerta.", "Decía que el calor ya no era como antes.", "Nadie nos dijo que había que cuidarlo distinto."],
  erupcion: ["La ceniza cayó como nieve gris.", "Mi hermano quería jugar con ella.", "No sabíamos hacia dónde había que caminar."],
  avalancha: ["La montaña crujió de noche.", "En el pueblo siempre decían que alguien iba a avisar.", "Esa vez no hubo quién."],
  aire: ["En el colegio ya casi no salíamos al patio.", "Decían que era por los carros y el humo.", "Nadie nos explicó qué tan grave era, ni qué podíamos hacer."],
  ninguno: ["Aquí medimos todos los días y mandamos los números.", "Nunca supe si alguien los leía.", "Un día dejaron de preguntarnos por lo que todavía no sabíamos medir."],
};

/** La misma hoja, reescrita, si el viajero leyó bien los datos, decidió con la gente y avisó a todo el pueblo. */
const SAVED_PAGE: Record<string, string[]> = {
  huaico: ["Hoy llovió fuerte y la quebrada sonó como un camión.", "Pero ya sabíamos por dónde subir. Lo ensayamos el día que vino alguien de lejos a contarnos lo que dicen los datos, y también lo que los datos no saben.", "Desde arriba vimos pasar el barro. Mi papá me apretó la mano.", "Estamos todos."],
  inundacion: ["Hoy el agua entró por la cocina.", "Pero mis cuadernos ya estaban arriba, y nosotros también.", "Mi mamá dice que no fue suerte: alguien vino a avisar antes, y le creímos.", "Mañana toca limpiar. Estamos todos."],
  calor: ["Este verano el abuelo se sienta bajo los árboles nuevos de la plaza.", "A las doce le llevamos agua, como nos enseñaron.", "Dice que el calor ya no es como antes. Y se ríe, porque ahora sabemos cuidarlo."],
  erupcion: ["Hoy cayó ceniza.", "Mi hermano quería jugar con ella y le dije que no: primero la mochila, después el camino que marcamos.", "En el punto de encuentro nos contaron uno por uno.", "Estamos todos."],
  avalancha: ["La montaña crujió de noche.", "Pero la sirena sonó antes, y la calle de arriba ya estaba vacía.", "En la mañana contamos las casas. Faltaban dos.", "No faltaba nadie."],
  aire: ["Hoy volvimos a jugar en el patio.", "En la puerta del colegio hay un cartel que dice cómo está el aire cada día.", "Los vecinos ya no queman basura, y el bus pasa más seguido.", "Todavía hay humo. Pero ahora sabemos cuándo cuidarnos, y qué pedir."],
  ninguno: ["Hoy llegó respuesta.", "Alguien leyó los números y preguntó por lo que todavía no medimos.", "Hacía años que nadie preguntaba eso.", "Mañana salimos a medir otra vez."],
};

export const pageKind = (mission: Mission) => (mission.hazard && LOST_PAGE[mission.hazard] ? mission.hazard : "ninguno");

/** Hoja del cuaderno de un lugar: la del archivo de 2045 si no se avisó, o la reescrita si el lugar quedó a salvo. */
export function missionPage(mission: Mission, saved: boolean): string[] {
  return (saved ? SAVED_PAGE : LOST_PAGE)[pageKind(mission)];
}

/**
 * Un lugar queda a salvo solo si el viajero leyó bien los datos (todas las respuestas), confirmó un plan con los
 * recursos y avisó a todo el pueblo. Con una respuesta equivocada la hoja no cambia (se puede reintentar).
 */
export function missionOutcome(allCorrect: boolean, finished: boolean, allWarned: boolean): Outcome | null {
  if (!finished) return null;
  if (!allCorrect) return "perdido";
  return allWarned ? "salvado" : null;
}

export function savedCount(story: Record<string, Outcome>): number {
  return Object.values(story).filter((value) => value === "salvado").length;
}

/** Transmisión de la doctora Nikol en el globo, según el avance. */
export function nikolMessage(saved: number, missing: { label: string }[], fundamentals: boolean): string {
  if (fundamentals) return "¡Lo lograste! Las misiones fundamentales están completas. Génesis tiene energía para el regreso final.";
  if (saved === 0) return "¿Me escuchas? La señal es débil, pero estás ahí. Tenemos los datos de observación de la Tierra. Investiga los lugares, identifica los riesgos y ayuda a la gente a decidir. No puedes solucionar algo que no entiendes.";
  const names = missing.map((item) => item.label.toLowerCase());
  const list = names.length > 1 ? `${names.slice(0, -1).join(", ")} y ${names[names.length - 1]}` : names[0];
  return `Los registros empiezan a moverse. Todavía nadie llega a tiempo a los lugares de ${list}. Recuerda: una ciudad no cambia solo porque una persona tenga una buena idea.`;
}

/** Transmisión corta de la doctora Nikol al llegar a un lugar fuera del Perú, según su peligro. Sin cifras. */
const NIKOL_BRIEF: Record<string, string> = {
  huaico: "Las quebradas de este lugar pueden activarse con lluvias fuertes. Lee los datos, decide con la gente y avisa por dónde subir.",
  inundacion: "Aquí el agua es el peligro. Mira cómo cambió la lluvia, decide con la gente y avisa antes de que crezca el río.",
  calor: "El calor y la falta de agua golpean este lugar. Lee la tendencia, reparte bien los recursos y cuida a los más expuestos.",
  erupcion: "El volcán está vigilado, pero la gente tiene que saber qué hacer. El calor no causa erupciones: no mezcles las causas.",
  avalancha: "La montaña cambia. Lee los datos con cuidado y prepara al pueblo para cuando suene la sirena.",
  aire: "El aire de esta ciudad preocupa. Mira lo que ven los satélites y lo que todavía no miden, y decide con la gente.",
  ninguno: "Aquí lo que más falta es saber. Lee lo que hay, di en voz alta lo que no se mide y decide qué investigar primero.",
};

export function nikolBrief(mission: Mission): string {
  return NIKOL_BRIEF[pageKind(mission)] ?? NIKOL_BRIEF.ninguno;
}

/** Lo que dice Christian, el joven de la comunidad, en las misiones del Perú. Conecta los datos con la vida diaria. */
const CHRISTIAN: Record<string, string> = {
  huaico: "Aquí todos conocen el sonido de la quebrada. Lo que nos falta es saber cuándo viene y por dónde subir. Si tú lees los datos, yo junto a los vecinos.",
  inundacion: "La gente todavía se acuerda de la última vez que el río se metió a las casas. Lo que necesitamos es que alguien nos explique qué dicen los datos ahora, no después.",
  avalancha: "Mi abuela habla de Yungay como si hubiera sido ayer. Las lagunas de arriba hay que vigilarlas, y el pueblo tiene que saber qué hacer si suena la sirena.",
  aire: "Antes jugábamos fútbol en el patio durante el recreo. Ahora casi siempre nos quedamos adentro. Dicen que son los carros, las fábricas y el humo, pero nadie nos explica qué tan grave es.",
  calor: "Con este calor, los que más sufren son los abuelos y las chacras. Si sabemos qué viene, podemos organizarnos.",
  erupcion: "Si el volcán despierta, cada familia tiene que saber hacia dónde caminar. Eso se ensaya antes, no el mismo día.",
  ninguno: "Que el Perú tenga una estación en la Antártida dice mucho: medir es la primera forma de cuidar.",
};

export function companionLine(mission: Mission): { who: string; text: string } | null {
  if (mission.country !== "Perú" && !mission.country.includes("peruana")) return null;
  return { who: "Christian, de la comunidad", text: CHRISTIAN[pageKind(mission)] ?? CHRISTIAN.ninguno };
}

const lowerList = (items: { label: string }[]) => {
  const names = items.map((item) => item.label.toLowerCase());
  return names.length > 1 ? `${names.slice(0, -1).join(", ")} y ${names[names.length - 1]}` : names[0] ?? "";
};

/** El regreso a 2045 que no es un final: el planeta según el avance y la energía para volver. */
export function returnSlides({ cause, used, tier, gained }: { cause: ReturnCause; used: number; tier: PlanetTier; gained: number }): StorySlide[] {
  const left = MAX_RETURNS - used;
  return [
    { kicker: `Año 2045 · Regreso ${used} de ${MAX_RETURNS}`, lines: cause === "emergencia"
      ? ["Tu salud llegó a cero.", "Génesis activó el protocolo de emergencia y te trajo de vuelta a la colonia."]
      : ["Pediste el regreso.", "Génesis te trae de vuelta a la colonia."] },
    { lines: ["Corres a la ventana de observación.", TIERS[tier].future, "Mario se acerca despacio. Andrés no dice nada."] },
    { lines: ["—Regresaste —dice la doctora Nikol—. Los registros cambiaron.", gained === 1 ? "—Un lugar más llegó a tiempo desde la última vez. No es suficiente, pero es algo." : "—Varios lugares más llegaron a tiempo desde la última vez. No es suficiente, pero es algo.", "—Génesis tiene energía para que vuelvas."] },
    { kicker: "Volver a 2026", lines: [left === 1 ? "Te queda un último regreso." : `Te quedan ${left} regresos.`, "Solo podrás usarlo si vuelves con el futuro mejor que hoy.", "Mario aprieta la fotografía contra tu mano. —Otra vez."] },
  ];
}

/** Resumen de un regreso que no es final, después de la cinemática «Regreso a 2045»: solo lo que cambia en la partida. */
export function returnSummary({ cause, used, tier, gained }: { cause: ReturnCause; used: number; tier: PlanetTier; gained: number }): StorySlide {
  const left = MAX_RETURNS - used;
  return { kicker: `Año 2045 · Regreso ${used} de ${MAX_RETURNS}`, lines: [
    cause === "emergencia" ? "Tu salud llegó a cero y Génesis te trajo de vuelta." : "Pediste el regreso y Génesis te trajo de vuelta.",
    `${gained === 1 ? "Un lugar más llegó" : `${gained} lugares más llegaron`} a tiempo desde la última vez. Estado del planeta: ${TIERS[tier].label}.`,
    TIERS[tier].future,
    left === 1 ? "Te queda un último regreso: solo podrás usarlo si vuelves con el futuro mejor que hoy." : `Te quedan ${left} regresos: solo podrás usarlos si vuelves con el futuro mejor que hoy.`,
  ] };
}

/** Resumen de la partida después de la cinemática de un final. */
export function finaleSummary(ending: Ending, saved: number, missing: { label: string }[]): StorySlide {
  const places = saved === 0 ? "ningún lugar" : saved === 1 ? "un lugar" : `${saved} lugares`;
  const title = ending === "bueno" ? "Final: un nuevo comienzo" : ending === "intermedio" ? "Final: un futuro a medias" : "Final: un futuro perdido";
  const lines = ending === "bueno"
    ? [`Llegaste a tiempo en ${places}, con al menos uno de cada peligro.`, "Tu parte fue llevar los datos. Lo demás lo hizo la gente que decidió con ellos."]
    : ending === "intermedio"
      ? [`Llegaste a tiempo en ${places}.`, `Faltó llegar a tiempo a los lugares de ${lowerList(missing)}.`, "Puedes empezar una nueva partida o seguir mirando los datos de la Tierra."]
      : [saved === 0 ? "No llegaste a tiempo a ningún lugar." : `Llegaste a tiempo en ${places}, pero desde tu último regreso ningún lugar más llegó a tiempo.`, "Puedes empezar una nueva partida."];
  return { kicker: title, lines: [...lines, ending === "bueno" ? CLOSING_GOOD.lines[3] : CLOSING_HARD.lines[1]] };
}

const CLOSING_GOOD: StorySlide = { kicker: "Hoy", lines: [
  "Tú no tienes una máquina para volver al pasado.",
  "No la necesitas. Todavía es hoy.",
  "Con Los Causas Espaciales tienes lo que le faltó a ese futuro: los datos de la Tierra, una segunda fuente que los comprueba y, dicho en voz alta, lo que aún no se sabe.",
  "El conocimiento ya es tuyo. El cambio empieza cuando sales a contarlo.",
] };
const CLOSING_HARD: StorySlide = { kicker: "Hoy", lines: [
  "En el juego puedes empezar de nuevo.",
  "Afuera no hay máquina del tiempo. Hay datos, y todavía es hoy.",
  "Con Los Causas Espaciales puedes leerlos antes de que sea tarde, comprobarlos con una segunda fuente y salir a contarlo.",
] };

/** Los tres finales. `saved` y `missing` solo se usan para nombrar lugares y peligros; no hay cifras medidas. */
export function finale(ending: Ending, saved: number, missing: { label: string }[]): { good: boolean; slides: StorySlide[] } {
  const places = (count: number) => (count === 1 ? "un lugar" : `${count} lugares`);
  if (ending === "bueno") {
    return {
      good: true,
      slides: [
        { kicker: "Año 2045 · El regreso final", lines: ["Génesis se activa por última vez.", "Abres los ojos en la colonia. Las alarmas no suenan."] },
        { lines: ["—¡No puede ser! ¡Volviste! —grita Mario.", "—Lo conseguimos —dices.", "—¿Y la Tierra?"] },
        { lines: ["Se acercan a la ventana.", "Los océanos vuelven a ser azules. Las regiones de bosque recuperaron su verde. La atmósfera se ve más limpia.", "—¿Ese… es nuestro planeta? —pregunta Andrés.", "—Sí. Nuestro hogar."] },
        { lines: ["—Los registros históricos cambiaron —dice la doctora Nikol—. Las comunidades se adaptaron, protegieron sus ecosistemas y redujeron los riesgos que amenazaban su futuro.", "No lo salvaste todo. Nadie puede. Hay casas que ya no están.", "Pero la gente está."] },
        { lines: ["El cuaderno de Killa sigue en el archivo. Abres la última hoja:"], letter: KILLA_SAVED },
        { lines: [`Llegaste a tiempo en ${places(saved)}, con al menos uno de cada peligro.`, "Tu parte fue llevar los datos. Lo demás lo hicieron ellos: ensayaron por dónde subir, dejaron libre el cauce, plantaron sombra y pidieron la estación que faltaba."] },
        { lines: ["—¿Entonces podemos ir? —pregunta Mario.", "—Esta vez sí.", "El planeta nunca necesitó héroes capaces de viajar en el tiempo. Necesitaba personas dispuestas a cambiar el presente."] },
        CLOSING_GOOD,
      ],
    };
  }
  if (ending === "intermedio") {
    return {
      good: false,
      slides: [
        { kicker: "Año 2045 · El último regreso", lines: ["Génesis ya no tiene energía para otro viaje.", "Vuelves a la colonia por última vez."] },
        { lines: ["Desde la ventana, la Tierra se ve distinta.", "Hay regiones que recuperaron su verde y mares que volvieron a ser azules.", "Y hay otras que siguen cubiertas de humo."] },
        { lines: ["—Sí sirvió —dice la doctora Nikol—. Los registros cambiaron en muchos lugares.", `—Pero nadie llegó a tiempo a los lugares de ${lowerList(missing)}. No fue suficiente para evitar el colapso en todas partes.`] },
        { lines: [`Llegaste a tiempo en ${places(saved)}. Esas hojas del cuaderno cambiaron.`, "La última, la de Killa, sigue igual:"], letter: KILLA_LOST },
        { lines: ["Andrés apoya la mano en el vidrio. —Algún día.", "Mario guarda la fotografía. —Algún día iremos.", "Cada decisión importa. Pero la recuperación necesita acciones sostenidas y colectivas, en todos los frentes."] },
        CLOSING_HARD,
      ],
    };
  }
  return {
    good: false,
    slides: [
      { kicker: "Año 2045", lines: ["Génesis te devuelve a la colonia.", "—¡Volviste! ¿Qué pasó? ¿Lo conseguimos? —pregunta Mario.", "Te quedas en silencio."] },
      { lines: ["—No… ¿verdad?", "—Lo intenté. Pero no fue suficiente.", "Desde tu último regreso, ningún lugar más llegó a tiempo. Génesis no tiene energía para volver."] },
      { lines: ["Suenan las alarmas.", "—¡Alerta! —grita Andrés—. ¡La atmósfera de la Tierra está en estado crítico!", "Por la ventana, el planeta se apaga bajo el humo y el fuego."] },
      { lines: ["—Era nuestro hogar… —dice Mario.", "Miras la fotografía de la Tierra verde.", "—Tuvimos tantas oportunidades…"] },
      { lines: ["El cuaderno de Killa sigue en el archivo. La última hoja dice lo mismo:"], letter: KILLA_LOST },
      { lines: ["El futuro que intentamos evitar se convirtió en nuestra última realidad.", saved === 0 ? "No llegaste a tiempo a ningún lugar." : `Llegaste a tiempo en ${places(saved)}, pero no bastó.`] },
      CLOSING_HARD,
    ],
  };
}

/** Texto corto de las reglas, para la colonia lunar antes de saltar. */
export function rulesText(): string {
  return `Misiones fundamentales: salva al menos un lugar de cada peligro (${FUNDAMENTAL.map((item) => item.label.toLowerCase()).join(", ")}). Un lugar queda a salvo si lees bien los datos, decides un plan con los recursos y avisas a todo el pueblo. Si tu salud llega a cero, o si lo pides, Génesis te trae de vuelta: tienes ${MAX_RETURNS} regresos, y solo podrás volver a 2026 si el futuro mejoró.`;
}
