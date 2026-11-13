// Reglas de las misiones: funciones puras que convierten el análisis real de un lugar en preguntas y retos.
// Nada aquí inventa una cifra: cada texto con números sale de la tendencia que devolvió la plataforma.

import type { Mission, MissionTrend } from "./game-types";

export interface Option {
  id: string;
  text: string;
  correct: boolean;
  feedback: string;
}

export interface Challenge {
  id: string;
  kind: "calor" | "frio" | "agua" | "lluvia" | "sol" | "pista_falsa" | "detective";
  title: string;
  situation: string;
  options: Option[];
  badge: string;
}

const fmt = (value: number, digits = 1) => value.toLocaleString("es-PE", { minimumFractionDigits: digits, maximumFractionDigits: digits });

const pText = (p: number | null) => (p == null ? "sin dato" : p < 0.001 ? "< 0,001" : fmt(p, 3));

/** Cambio por década en las unidades de la variable, con signo. */
export function perDecade(trend: MissionTrend | null): number | null {
  return trend?.slope_per_year == null ? null : trend.slope_per_year * 10;
}

/** Cambio por década como porcentaje del promedio; solo para variables de razón (lluvia, sol), nunca para °C. */
export function percentPerDecade(trend: MissionTrend | null): number | null {
  const decade = perDecade(trend);
  if (decade == null || !trend?.mean) return null;
  return (decade / trend.mean) * 100;
}

export function temperatureSentence(mission: Mission): string {
  const trend = mission.temperature;
  if (!trend) return "La plataforma no pudo leer la temperatura de este lugar: es una brecha, no un «sin cambio».";
  const decade = perDecade(trend);
  if (!trend.significant || decade == null) {
    return `No hay evidencia estadística suficiente de que la temperatura cambie desde 2001 (${trend.valid_years ?? "?"} años). No significa que no cambie: significa que estos datos no alcanzan para afirmarlo.`;
  }
  const verb = decade > 0 ? "sube" : "baja";
  return `La temperatura media ${verb} ${fmt(Math.abs(decade), 2)} °C por década desde 2001, con evidencia estadística (p ajustado ${pText(trend.p_value_adjusted)}).`;
}

export function secondSourceSentence(trend: MissionTrend | null): string | null {
  const check = trend?.second_source;
  if (!check) return null;
  const who = check.source.split(" (")[0];
  const when = check.period ? ` en ${check.period}` : "";
  switch (check.agreement) {
    case "coincide": return `${who} confirma la tendencia${when}.`;
    case "sin_tendencia": return `${who} no ve una tendencia significativa${when}: es una pista por confirmar.`;
    case "difiere": return `${who} ve otra cosa${when}: las fuentes no coinciden.`;
    case "solo_contraste": return `${who} solo sirve aquí para comparar el nivel, no la tendencia.`;
    default: return `${who} se consultó${when}; su resultado: ${check.agreement ?? "sin dato"}.`;
  }
}

/** Primer paso de toda misión: leer la tendencia de temperatura como un detective. */
export function detectiveQuestion(mission: Mission): Challenge {
  const answer = mission.heat;
  const options: Option[] = [
    { id: "sube", text: "Se está calentando", correct: answer === "calienta", feedback: "" },
    { id: "baja", text: "Se está enfriando", correct: answer === "enfria", feedback: "" },
    { id: "nada", text: "Los datos no alcanzan para afirmarlo", correct: answer === "sin_evidencia", feedback: "" },
  ];
  const explanation = [temperatureSentence(mission), secondSourceSentence(mission.temperature)].filter(Boolean).join(" ");
  options.forEach((option) => { option.feedback = (option.correct ? "¡Bien leído! " : "No es lo que dicen los datos. ") + explanation; });
  return {
    id: "detective",
    kind: "detective",
    title: "Paso 1 · Lee la pista",
    situation: `Mira la línea de temperatura de ${mission.name} desde 2001. ¿Qué está pasando?`,
    options,
    badge: "Detective de tendencias",
  };
}

/** Segundo paso: un reto de héroe según la señal más fuerte que detectó la plataforma. */
export function heroChallenge(mission: Mission): Challenge {
  const flagged = mission.flagged_extremes[0];
  if (flagged?.value != null) {
    const others = Object.entries(flagged.countercheck_values).filter(([, value]) => value != null)
      .map(([name, value]) => `${name.split(" (")[0]} ${fmt(value as number)} mm`).join(" y ");
    return {
      id: "pista-falsa", kind: "pista_falsa", title: "Paso 2 · La pista falsa",
      situation: `Un modelo marca ${fmt(flagged.value)} mm de lluvia en un solo día de ${flagged.year}, pero los satélites dicen ${others}. Te piden diseñar las defensas del lugar. ¿Qué haces?`,
      options: [
        { id: "a", text: `Diseñar todo para ${fmt(flagged.value)} mm`, correct: false, feedback: "Construirías para un valor que dos satélites no ven: gastarías de más y quizá en el lugar equivocado." },
        { id: "b", text: "Pedir el dato de una estación cercana antes de decidir", correct: true, feedback: "Eso hace un detective: cuando dos fuentes no coinciden, busca un tercer testigo antes de gastar." },
        { id: "c", text: "Ignorar la lluvia de este lugar", correct: false, feedback: "Un dato dudoso no vuelve cero el riesgo de lluvia; solo pide verificarlo." },
      ],
      badge: "Cazador de pistas falsas",
    };
  }
  const temp = mission.temperature;
  if (temp?.significant && temp.direction === "increasing") {
    return {
      id: "calor", kind: "calor", title: "Paso 2 · Bajar el calor",
      situation: `${mission.name} se calienta. La gente necesita refrescarse sin empeorar el problema. ¿Qué haces primero?`,
      options: [
        { id: "a", text: "Plantar árboles y dar sombra a calles, mercados y escuelas", correct: true, feedback: "La sombra y la vegetación bajan la temperatura que siente la gente y no emiten más gases." },
        { id: "b", text: "Poner aire acondicionado en todas partes con electricidad de carbón", correct: false, feedback: "Alivia hoy, pero quemar más carbón calienta más el planeta: es una mala adaptación." },
        { id: "c", text: "Talar el parque para construir más rápido", correct: false, feedback: "Quitar vegetación aumenta el calor de la ciudad." },
      ],
      badge: "Guardián del calor",
    };
  }
  const rain = mission.rain;
  const rainPct = percentPerDecade(rain);
  if (rain?.significant && rain.direction === "decreasing") {
    return {
      id: "agua", kind: "agua", title: "Paso 2 · Cuidar el agua",
      situation: `En ${mission.name} llueve menos (${fmt(Math.abs(rainPct ?? 0))} % menos por década). ¿Cómo ayudas?`,
      options: [
        { id: "a", text: "Cosechar agua de lluvia y regar por goteo", correct: true, feedback: "Guardar cada gota y regar solo la raíz rinde más con menos lluvia." },
        { id: "b", text: "Regar inundando los campos, como siempre", correct: false, feedback: "Con menos lluvia, el riego por inundación agota el agua más rápido." },
        { id: "c", text: "Perforar pozos sin medir cuánta agua queda", correct: false, feedback: "Sin medir, el agua subterránea también se acaba." },
      ],
      badge: "Guardián del agua",
    };
  }
  const extremeUp = mission.extremes.find((item) => item.significant && item.direction === "increasing");
  if ((rain?.significant && rain.direction === "increasing") || extremeUp) {
    const what = extremeUp ? extremeUp.label.toLowerCase() : "la lluvia";
    return {
      id: "lluvia", kind: "lluvia", title: "Paso 2 · Prepararse para la lluvia",
      situation: `En ${mission.name} aumenta ${what}. ¿Qué haces para proteger a la gente?`,
      options: [
        { id: "a", text: "Limpiar drenajes y no construir en los cauces de los ríos", correct: true, feedback: "Dejar paso al agua es la defensa más barata frente a lluvias más fuertes." },
        { id: "b", text: "Rellenar quebradas para hacer más casas", correct: false, feedback: "El agua vuelve a buscar su camino: esas casas quedan en peligro." },
        { id: "c", text: "Esperar a que pase", correct: false, feedback: "Si la tendencia es real, cada año el riesgo es mayor." },
      ],
      badge: "Guardián de la lluvia",
    };
  }
  const sun = mission.sun;
  if (sun?.significant && sun.direction === "decreasing") {
    return {
      id: "sol", kind: "sol", title: "Paso 2 · El sol que no llega",
      situation: `En ${mission.name} llega menos sol al suelo (${fmt(Math.abs(percentPerDecade(sun) ?? 0))} % menos por década). Una posible causa, por comprobar, es el humo y el polvo en el aire. ¿Qué haces?`,
      options: [
        { id: "a", text: "Medir la calidad del aire para saber qué tapa el sol", correct: true, feedback: "Primero se confirma la causa. Si es contaminación, limpiar el aire ayuda a la salud y a la energía solar." },
        { id: "b", text: "Llenar todo de paneles solares sin revisar", correct: false, feedback: "Con menos sol, los paneles rinden menos de lo esperado: hay que medir antes." },
        { id: "c", text: "Concluir que el clima se enfría", correct: false, feedback: "Menos sol en el suelo no es lo mismo que menos temperatura: son pistas distintas." },
      ],
      badge: "Detective del aire",
    };
  }
  if (temp?.significant && temp.direction === "decreasing") {
    return {
      id: "frio", kind: "frio", title: "Paso 2 · Un lugar que se enfría",
      situation: `Aquí la temperatura baja, al revés que en casi todo el planeta. ¿Qué haces con esa pista?`,
      options: [
        { id: "a", text: "Compararla con otra fuente y con estaciones antes de anunciarla", correct: true, feedback: "Una pista rara necesita más testigos. Así trabaja un detective." },
        { id: "b", text: "Decir que el calentamiento global no existe", correct: false, feedback: "Un punto no habla por todo el planeta: el clima cambia distinto en cada lugar." },
        { id: "c", text: "Ignorarla", correct: false, feedback: "Las pistas raras también enseñan; se verifican, no se esconden." },
      ],
      badge: "Detective de lo inesperado",
    };
  }
  return {
    id: "detective-final", kind: "detective", title: "Paso 2 · Cuando los datos no alcanzan",
    situation: `En ${mission.name} los datos no muestran una tendencia clara. Un periodista te pregunta si aquí «no pasa nada». ¿Qué respondes?`,
    options: [
      { id: "a", text: "«No pasa nada, aquí no hay cambio climático»", correct: false, feedback: "«No significativo» no prueba que no haya cambio: solo dice que la evidencia no alcanza." },
      { id: "b", text: "«La evidencia no alcanza: hacen falta estaciones de medición aquí»", correct: true, feedback: "Exacto. Más medición en tierra es lo que permitiría saberlo." },
      { id: "c", text: "«Seguro se calienta como todo el mundo»", correct: false, feedback: "Un detective no afirma lo que los datos no muestran." },
    ],
    badge: "Detective honesto",
  };
}

export function missionSteps(mission: Mission): Challenge[] {
  return [detectiveQuestion(mission), heroChallenge(mission)];
}

/** Etiquetas flotantes sobre el lugar de la misión: solo cifras de la plataforma o «sin evidencia». */
export function missionTags(mission: Mission): string[] {
  const tag = (name: string, trend: MissionTrend | null, kind: "temp" | "ratio") => {
    if (!trend) return `${name}: sin dato`;
    const decade = perDecade(trend);
    if (!trend.significant || decade == null) return `${name}: sin evidencia`;
    if (kind === "temp") return `${name} ${decade > 0 ? "+" : "−"}${fmt(Math.abs(decade), 2)} °C/década`;
    const pct = percentPerDecade(trend) ?? 0;
    return `${name} ${pct > 0 ? "+" : "−"}${fmt(Math.abs(pct))} %/década`;
  };
  return [tag("Temperatura", mission.temperature, "temp"), tag("Lluvia", mission.rain, "ratio"), tag("Sol", mission.sun, "ratio")];
}

export interface Checkpoint {
  id: string;
  title: string;
  /** Nombre de juego de la misión y su ícono. */
  quest: string;
  icon: string;
  /** Lo que pregunta el vecino del pueblo antes de que el héroe le responda. */
  ask: string;
  /** Lo que el héroe le avisa a la gente, con la cifra de la plataforma. */
  message: string;
  tone: "alerta" | "calma" | "brecha";
  bearing: number;
}

/** Punto a una distancia y rumbo desde otro (esfera; basta para distancias de juego de pocos kilómetros). */
export function offset(lat: number, lon: number, bearingDeg: number, meters: number): [number, number] {
  const b = (bearingDeg * Math.PI) / 180;
  const dLat = (meters * Math.cos(b)) / 110_540;
  const dLon = (meters * Math.sin(b)) / (111_320 * Math.cos((lat * Math.PI) / 180));
  return [lon + dLon, lat + dLat];
}

export function metersBetween(a: [number, number], b: [number, number]): number {
  const dx = (a[0] - b[0]) * 111_320 * Math.cos((((a[1] + b[1]) / 2) * Math.PI) / 180);
  const dy = (a[1] - b[1]) * 110_540;
  return Math.hypot(dx, dy);
}

/** Puntos de «Avisa al pueblo»: uno por pista de la plataforma, y uno con lo que no se mide. */
export function missionCheckpoints(mission: Mission): Checkpoint[] {
  const where = mission.name.split(",")[0];
  const list: Checkpoint[] = [];
  const temp = mission.temperature;
  const decade = perDecade(temp);
  if (temp?.significant && decade != null && decade > 0) {
    list.push({ id: "temp", title: "Calor", quest: "Ola de calor", icon: "🔥", ask: "¡Héroe! ¿Por qué cada año hace más calor aquí?", tone: "alerta", bearing: 40,
      message: `¡Atención, ${where}! Aquí la temperatura sube ${fmt(decade, 2)} °C por década desde 2001. En los días de mucho calor: tomen agua, busquen sombra y cuiden a niños y abuelos.` });
  } else if (temp?.significant && decade != null) {
    list.push({ id: "temp", title: "Temperatura", quest: "Pista misteriosa", icon: "🕵️", ask: "Dicen que aquí se está enfriando… ¿es verdad?", tone: "calma", bearing: 40,
      message: `Aquí un modelo de NASA ve que la temperatura baja ${fmt(Math.abs(decade), 2)} °C por década. ${secondSourceSentence(temp) ?? ""} Es una pista por verificar, no una alarma.` });
  } else {
    list.push({ id: "temp", title: "Temperatura", quest: "Termómetro perdido", icon: "🌡️", ask: "¿Aquí se está calentando o no?", tone: "calma", bearing: 40,
      message: `Los datos no alcanzan para saber si ${where} se calienta. No significa que no cambie: hace falta una estación que lo mida aquí.` });
  }
  const flagged = mission.flagged_extremes[0];
  const rain = mission.rain;
  const extremeUp = mission.extremes.find((item) => item.significant && item.direction === "increasing");
  if (flagged?.value != null) {
    list.push({ id: "lluvia", title: "Lluvia", quest: "Pista falsa", icon: "🕵️", ask: "¡Oí que cayó una lluvia gigante! ¿Nos inundaremos?", tone: "calma", bearing: 160,
      message: `Un modelo marcó ${fmt(flagged.value)} mm de lluvia en un día de ${flagged.year}, pero los satélites no lo ven. No se alarmen: antes de decidir, que lo confirme una estación.` });
  } else if (rain?.significant && rain.direction === "decreasing") {
    list.push({ id: "lluvia", title: "Agua", quest: "Misión agua", icon: "💧", ask: "Mis plantas tienen sed… ¿qué le pasa a la lluvia?", tone: "alerta", bearing: 160,
      message: `¡Atención! En ${where} llueve ${fmt(Math.abs(percentPerDecade(rain) ?? 0))} % menos por década. Cuiden el agua: guarden la lluvia y rieguen por goteo.` });
  } else if (extremeUp || (rain?.significant && rain.direction === "increasing")) {
    list.push({ id: "lluvia", title: "Lluvias fuertes", quest: "Tormentas", icon: "⛈️", ask: "¡Las lluvias son cada vez más fuertes! ¿Qué hacemos?", tone: "alerta", bearing: 160,
      message: `¡Atención! En ${where} aumentan ${extremeUp ? extremeUp.label.toLowerCase() : "las lluvias"}. No construyan en los cauces, limpien los drenajes y tengan lista una ruta de evacuación.` });
  } else {
    list.push({ id: "lluvia", title: "Lluvia", quest: "Nube viajera", icon: "🌧️", ask: "¿Llueve más o menos que antes?", tone: "calma", bearing: 160,
      message: `La lluvia de ${where} no muestra un cambio claro desde 2001. Sigan midiendo: un año raro no es una tendencia.` });
  }
  const sun = mission.sun;
  if (sun?.significant && sun.direction === "decreasing") {
    list.push({ id: "sol", title: "Sol", quest: "El sol se esconde", icon: "☀️", ask: "Siento que el sol ya no brilla como antes… ¿por qué?", tone: "alerta", bearing: 280,
      message: `Aquí llega ${fmt(Math.abs(percentPerDecade(sun) ?? 0))} % menos sol al suelo por década. Puede ser humo o polvo en el aire: pidan medir la calidad del aire.` });
  }
  list.push({ id: "brecha", title: "Lo que no medimos", quest: "Zona sin datos", icon: "❓", ask: "¿Y tú sabes todo lo que pasa aquí?", tone: "brecha", bearing: list.length === 3 ? 220 : 280,
    message: `Esto no lo mide esta misión: ${mission.not_measured.replace(/\.$/, "")}. Pregunten a las autoridades locales; que no lo midamos no significa que no haya riesgo.` });
  return list;
}
