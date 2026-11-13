// El Niño Costero 2026 en el juego: cada dato sale de una fuente periodística u oficial, leída el 13-nov-2026,
// y se muestra con su medio, su fecha y su enlace. Es contexto de noticias, no un dato medido por la plataforma.
// Las cifras se copian como las escribe cada fuente. Solo se usan en las misiones del Perú, que es de lo que tratan.

export type NinoFact = {
  /** Frase corta para el noticiero, el aviso o el panel. */
  text: string;
  /** Medio que publica y, si corresponde, de quién es el dato. */
  source: string;
  /** Fecha tal como aparece en la página; null si la página no la muestra. */
  date: string | null;
  url: string;
};

export const NINO_CHECKED_AT = "2026-11-13";
export const NINO_COUNTRY = "Perú";

export const NINO_FACTS: NinoFact[] = [
  {
    text: "El ENFEN ratificó la alerta de El Niño Costero: se mantendrá en niveles extraordinarios en la región Niño 1+2 hasta febrero de 2027.",
    source: "Panamericana · Comunicado Oficial ENFEN N.° 19-2026",
    date: null,
    url: "https://panamericana.pe/nacionales/476700-enfen-pronostica-nino-costero-continuaria-fines-otono-2027",
  },
  {
    text: "Se esperan lluvias por encima de lo normal, de moderada a fuerte intensidad, entre noviembre de 2026 y el verano de 2027.",
    source: "Panamericana · Comunicado Oficial ENFEN N.° 19-2026",
    date: null,
    url: "https://panamericana.pe/nacionales/476700-enfen-pronostica-nino-costero-continuaria-fines-otono-2027",
  },
  {
    text: "La NOAA registró una anomalía de +5,4 °C en el mar de la región Niño 1+2.",
    source: "El Observador (datos de NOAA difundidos por MetSul)",
    date: "3 de noviembre de 2026",
    url: "https://www.elobservador.com.uy/el-nino-rompe-records-historicos-el-pacifico-se-calienta-como-nunca-y-provoca-inundaciones-sudamerica-n6062535",
  },
  {
    text: "Tumbes y Piura sufrieron lluvias intensas y deslizamientos; el río Tumbes alcanzó 1.021 metros cúbicos por segundo.",
    source: "El Observador",
    date: "3 de noviembre de 2026",
    url: "https://www.elobservador.com.uy/el-nino-rompe-records-historicos-el-pacifico-se-calienta-como-nunca-y-provoca-inundaciones-sudamerica-n6062535",
  },
  {
    text: "El Perú declaró por 60 días el estado de emergencia en 1.380 distritos, de los más de 1.800 que tiene el país.",
    source: "Primicias (AFP)",
    date: "3 de noviembre de 2026",
    url: "https://www.primicias.ec/internacional/peru-emergencia-fenomeno-nino-municipios-lluvias-inundaciones-136308/",
  },
  {
    text: "Más de 9,3 millones de habitantes, casi un tercio del país, están expuestos a un alto riesgo, según CENEPRED.",
    source: "Primicias (AFP)",
    date: "3 de noviembre de 2026",
    url: "https://www.primicias.ec/internacional/peru-emergencia-fenomeno-nino-municipios-lluvias-inundaciones-136308/",
  },
  {
    text: "25 puertos del litoral peruano cerraron por oleajes hasta el 6 de noviembre; las olas pueden llegar al doble o al triple de lo habitual.",
    source: "América Noticias",
    date: null,
    url: "https://www.americatv.com.pe/noticias/actualidad/cierran-25-puertos-oleajes-hasta-seis-noviembre-n524076",
  },
  {
    text: "La inflación de Lima Metropolitana llegó a 5,25 % en octubre, según el INEI, con efectos de El Niño Costero sobre la producción agrícola.",
    source: "Perú Retail (datos del INEI)",
    date: "3 de noviembre de 2026",
    url: "https://www.peru-retail.com/inflacion-en-peru-supera-el-5-por-primera-vez-en-mas-de-tres-anos-que-factores-presionaron-los-precios/",
  },
  {
    text: "En octubre el choclo subió 45,3 %, el bonito 26,9 % y la zanahoria 24,6 %; llega menos pescado por el oleaje anómalo y el mar caliente.",
    source: "Infomercado (datos del INEI)",
    date: "2 de noviembre",
    url: "https://infomercado.pe/inei-inflacion-en-lima-supera-el-5-por-el-nino-y-el-alza-de-combustibles/",
  },
  {
    text: "El Perú acordó con navieras rutas especiales de cabotaje por si El Niño corta carreteras: Matarani, Ilo, Callao, Chancay, Chimbote, Salaverry y Paita.",
    source: "MundoMarítimo",
    date: "4 de noviembre de 2026",
    url: "https://www.mundomaritimo.cl/noticias/editor/57702",
  },
  {
    text: "En el Congreso se propuso habilitar el cabotaje marítimo para llevar alimentos y medicamentos cuando las carreteras quedan bloqueadas.",
    source: "Congreso de la República",
    date: "21 de octubre de 2026",
    url: "https://comunicaciones.congreso.gob.pe/despacho-informa/norma-yarrow-propone-habilitar-el-cabotaje-maritimo-para-llevar-ayuda-urgente-a-las-zonas-afectadas-por-el-fenomeno-el-nino/",
  },
];

export function ninoCredit(fact: NinoFact): string {
  return fact.date ? `${fact.source}, ${fact.date}` : fact.source;
}

/** Conversaciones de la gente en el Perú: lo que dicen sale de las mismas fuentes. */
export const NINO_CHATS: string[][] = [
  ["¡Hola! ¿Cómo estás?", "¡Sí, todo bien! ¿Y tú?", "Bien. ¿Viste? Declararon emergencia en 1.380 distritos por El Niño.", "Sí… hay que tener lista la mochila de emergencia."],
  ["¡Hola, vecina! ¿Cómo estás?", "Todo bien, gracias. Aunque el choclo subió 45,3 % en octubre…", "¡Uf! Y dicen que llega menos pescado por el oleaje.", "Así es. Cuidémonos mucho estos meses."],
  ["¡Buenas! ¿Todo bien?", "¡Sí, todo bien! ¿Escuchaste? El ENFEN mantiene la alerta de El Niño Costero.", "Sí, hasta febrero de 2027, dicen.", "Entonces a prepararse. ¡Nos vemos!"],
];
export const PLAIN_CHATS: string[][] = [
  ["¡Hola! ¿Cómo estás?", "¡Sí, todo bien! ¿Y tú?", "Todo tranquilo, aquí paseando 😊", "¡Qué bueno! Nos vemos luego 👋"],
  ["¡Buenas! ¿Qué tal tu día?", "¡Muy bien! Voy al mercado.", "¡Qué bacán! Saludos a tu familia.", "¡Igualmente! Chau 👋"],
];
