"""Guion de las cinemáticas de TERRA 2045 (ADR-050): tráiler, prólogo, viaje temporal, regreso a 2045 y los tres finales.

Fuente única de los textos: de aquí salen las voces (scripts/video/voces_edge.py con las voces neuronales de Microsoft Edge; respaldo: voces.ps1 con Windows y voces_ingles.ps1 con Piper), los
subtítulos en español e inglés y el montaje (scripts/video/render.py). Escribe scripts/video/guion.json.

    python scripts/video/guion.py

Reglas: es ficción declarada (como story.ts); las únicas cifras medidas son las del plano de datos del tráiler, que se
leen de backend/data/missions/missions.json al montar, nunca se escriben a mano. La historia no atribuye hechos futuros
a lugares reales: los finales hablan de «los pueblos de las quebradas» o «las ciudades junto al río».
Personajes: narrador, la doctora Nikol (científica, Proyecto Génesis), Andrés (amigo del viajero en la colonia), Mario
(hermano menor del viajero, nacido en la Luna), el viajero (quien juega) y Killa (la niña del cuaderno, 2026).
"""

import json
from pathlib import Path

OUT = Path(__file__).with_name("guion.json")

# Cada plano: escena visual (la dibuja render.py), líneas de voz y un tiempo mínimo en pantalla.
# Línea: (id, quién, español, inglés). «pausa» agrega silencio después de la línea, en segundos.

# Tráiler: abre en 2045 (motor propio) y, desde el salto a 2026, muestra el juego de verdad: capturas del navegador en
# videos/captura/ (planos «clip» y «pantalla», con la marca «Imágenes reales del juego»). Música: «Lightless Dawn» en
# 2045 y «Heroic Age» desde el salto, alineada para terminar con el título.
TRAILER = [
    {"scene": "negro_titulo", "hold": 1.5, "lines": [("t01", "narrador", "Año 2045. La humanidad perdió la Tierra.", "The year 2045. Humanity has lost the Earth.")]},
    {"scene": "tierra_desde_luna", "health": 0.0, "lines": [("t02", "narrador", "Los últimos supervivientes viven en una colonia en la Luna, mirando cómo muere el planeta que fue su hogar.", "The last survivors live in a colony on the Moon, watching the planet that was once their home die.")]},
    {"scene": "ventana", "who": ["mario", "andres"], "health": 0.0, "lines": [
        ("t03", "mario", "¿Crees que algún día podremos ir?", "Do you think we'll ever get to go there?"),
        ("t04", "andres", "No pasó de un día para otro. Todos pensaron que todavía había tiempo.", "It didn't happen overnight. Everyone thought there was still time.")]},
    {"scene": "genesis", "lines": [("t05", "nikol", "Podemos enviar a una persona al pasado. Solo una. Y solo una vez.", "We can send one person into the past. Only one. And only once.")]},
    {"scene": "tunel", "hold": 3.0, "lines": [("t06", "narrador", "Destino: 2026.", "Destination: 2026.")]},
    {"scene": "clip", "src": "globo.webm", "from": 0.2, "hold": 2.6, "fadeOut": 0.0, "lines": []},
    {"scene": "clip", "fadeIn": 0.0, "srcs": [
        {"src": "chamonix_llegada.webm", "from": 0.3, "dur": 2.5, "label": "Chamonix, Francia"},
        {"src": "huascaran_llegada.webm", "from": 0.2, "dur": 2.6, "label": "Huascarán, Perú"},
        {"src": "piura_llegada.webm", "from": 0.3, "label": "Piura, Perú"}],
     "lines": [("t07", "narrador", "Con datos reales de observación de la Tierra de la NASA, recorre lugares reales del Perú y de todo el mundo.", "With real NASA Earth observation data, travel to real places in Peru and around the world.")]},
    {"scene": "clip", "src": "llegada.webm", "from": 0.4, "hold": 4.2, "label": "Chosica, Perú", "lines": []},
    {"scene": "clip", "src": "vuelo.webm", "from": 2.0, "hold": 3.4, "label": "Chosica, Perú", "fadeOut": 0.0, "lines": []},
    {"scene": "clip", "src": "piura.webm", "from": 1.0, "hold": 3.4, "label": "Piura, Perú", "fadeIn": 0.0, "fadeOut": 0.0, "lines": []},
    {"scene": "clip", "src": "taal.webm", "from": 1.7, "hold": 3.2, "label": {'es': 'Volcán Taal, Filipinas', 'en': 'Taal Volcano, Philippines'}, "fadeIn": 0.0, "lines": []},
    {"scene": "clip", "fadeIn": 0.3, "srcs": [
        {"src": "huascaran.webm", "from": 3.0, "dur": 3.6, "label": "Huascarán, Perú"},
        {"src": "taal.webm", "from": 7.5, "label": {'es': 'Volcán Taal, Filipinas', 'en': 'Taal Volcano, Philippines'}}],
     "lines": [("t08", "narrador", "Lee los datos. Compruébalos con una segunda fuente. Y di en voz alta lo que todavía no se sabe.", "Read the data. Check it against a second source. And say out loud what is still unknown.")]},
    {"scene": "decision", "lines": [("t09", "narrador", "Decide con recursos limitados. No hay una única respuesta correcta.", "Decide with limited resources. There is no single right answer.")]},
    {"scene": "clip", "srcs": [
        {"src": "chosica.webm", "from": 10.3, "dur": 3.8, "label": "Chosica, Perú"},
        {"src": "piura.webm", "from": 0.0, "label": "Piura, Perú"}],
     "lines": [("t10", "nikol", "No tienes que salvar el planeta por tu cuenta. Tienes que conseguir que la gente quiera salvarlo contigo.", "You don't have to save the planet alone. You have to make people want to save it with you.")]},
    {"scene": "cuaderno_salvado", "hold": 4.0, "lines": []},
    {"scene": "planeta_cambia", "from": 0.0, "to": 1.0, "hold": 5.5, "lines": []},
    {"scene": "clip", "fadeIn": 0.0, "srcs": [
        {"src": "taal.webm", "from": 2.0, "dur": 1.3, "label": {'es': 'Volcán Taal, Filipinas', 'en': 'Taal Volcano, Philippines'}},
        {"src": "piura.webm", "from": 2.4, "dur": 1.3, "label": "Piura, Perú"},
        {"src": "vuelo.webm", "from": 3.6, "dur": 1.3, "label": "Chosica, Perú"},
        {"src": "huascaran_llegada.webm", "from": 1.6, "label": "Huascarán, Perú"}],
     "hold": 5.4, "lines": []},
    {"scene": "tierra_amanecer", "health": 1.0, "hold": 5.0, "lines": []},
    {"scene": "titulo", "hold": 3.0, "lines": [
        ("t12", "narrador", "TERRA 2045. El último viaje.", "TERRA 2045. The Last Journey."),
        ("t13", "narrador", "El futuro no está escrito. Pero cada decisión deja una huella.", "The future is not written. But every decision leaves a mark.")]},
]

PROLOGO = [
    {"scene": "negro_radio", "hold": 0.6, "lines": [("p01", "radio", "Registro de la colonia New Horizon. Año 2045.", "New Horizon colony log. The year 2045.")]},
    {"scene": "tierra_desde_luna", "health": 0.0, "lines": [("p02", "narrador", "La humanidad lleva doce años viviendo fuera de la Tierra. En la colonia lunar New Horizon, los recursos alcanzan cada vez para menos.", "Humanity has lived off the Earth for twelve years. In the New Horizon lunar colony, resources stretch thinner every day.")]},
    {"scene": "ventana", "who": ["mario", "andres", "viajero"], "health": 0.0, "hold": 3.0, "lines": [
        ("p04", "mario", "¿Crees que algún día podremos ir?", "Do you think we'll ever get to go there?"),]},
    {"scene": "ventana_cerca", "who": ["viajero", "andres"], "health": 0.0, "lines": [
        ("p08", "viajero", "¿Cómo llegamos a esto?", "How did we end up like this?"),
        ("p09", "andres", "No ocurrió de un día para otro. Cada generación heredó un planeta un poco peor que el anterior. Y todos pensaron que todavía había tiempo para cambiarlo.", "It didn't happen overnight. Every generation inherited a planet a little worse than the one before. And everyone thought there was still time to change it.", 0.6)]},
    {"scene": "genesis", "lines": [
        ("p10", "narrador", "Esa noche, la doctora Nikol reúne a la colonia.", "That night, Doctor Nikol gathers the colony."),
        ("p11", "nikol", "Mi equipo logró activar el Proyecto Génesis. Puede enviar a un ser humano a través del tiempo. Pero necesita una cantidad de energía extraordinaria.", "My team has activated Project Genesis. It can send a human being through time. But it needs an extraordinary amount of energy."),]},
    {"scene": "genesis_cerca", "who": ["viajero", "nikol", "mario"], "lines": [
        ("p15", "mario", "¿Y si falla?", "And if it fails?"),
        ("p16", "nikol", "Génesis solo podrá devolverte a 2026 si el futuro mejora. Si no, no habrá otra oportunidad.", "Genesis can only send you back to 2026 if the future improves. If not, there will be no other chance.", 0.6)]},
    {"scene": "cuaderno", "lines": [
        ("p18", "killa", "Me llamo Killa y tengo nueve años. Mi abuela dice que antes el río avisaba. Esa noche no avisó nadie. Después, en la radio, dijeron que los satélites lo estaban viendo desde hacía años. Si lo estaban viendo, ¿por qué nadie vino a decirnos?", "My name is Killa and I'm nine years old. My grandma says the river used to warn us. That night, nobody warned us. Later, on the radio, they said the satellites had been watching for years. If they were watching, why didn't anyone come to tell us?", 0.8)]},
    {"scene": "satelites", "lines": [("p19", "narrador", "No faltaron datos. Estaban ahí desde 2001. Faltó quien los leyera a tiempo, los comprobara con una segunda fuente y saliera a avisar.", "Data was never missing. It had been there since 2001. What was missing was someone to read it in time, check it against a second source, and go out and warn people.")]},
    {"scene": "foto", "who": ["mario", "viajero"], "lines": [
        ("p21", "mario", "Toma. Es una foto de la Tierra cuando todavía era verde. Quiero que la mires cuando llegues. Para que recuerdes por qué vale la pena salvarla.", "Here. It's a photo of the Earth when it was still green. I want you to look at it when you get there. So you remember why it's worth saving.", 0.6)]},
    {"scene": "activacion", "lines": [
        ("p22", "nikol", "Destino temporal: año 2026. Misión: evitar el colapso ambiental.", "Temporal destination: the year 2026. Mission: prevent the environmental collapse."),
        ("p23", "nikol", "Recuerda: no tienes que salvar el planeta por tu cuenta. Tienes que conseguir que las personas quieran salvarlo contigo.", "Remember: you don't have to save the planet alone. You have to make people want to save it with you.", 0.8)]},
    {"scene": "titulo", "hold": 2.5, "lines": [("p24", "narrador", "El futuro no está escrito. Pero cada decisión deja una huella.", "The future is not written. But every decision leaves a mark.")]},
]

VIAJE = [
    {"scene": "activacion", "lines": [("v01", "nikol", "Génesis a plena potencia. Iniciando el salto.", "Genesis at full power. Starting the jump.")]},
    {"scene": "tunel", "hold": 8.0, "lines": []},
    {"scene": "llegada", "health": 0.75, "lines": [
        ("v02", "viajero", "¿Doctora? ¿Me escucha?", "Doctor? Can you hear me?"),
        ("v03", "radio", "¡Te recibimos! La señal es débil, pero estás ahí. ¿En qué año estás?", "We hear you! The signal is weak, but you're there. What year is it?"),
        ("v04", "viajero", "2026. Lo conseguimos.", "2026. We made it."),
        ("v05", "radio", "Escúchame. Tenemos los datos de observación de la Tierra. Investiga, identifica los riesgos y ayuda a la gente a decidir. Aquí empieza todo.", "Listen to me. We have the Earth observation data. Investigate, identify the risks and help people decide. This is where it all begins.", 1.0)]},
]

REGRESO = [
    {"scene": "tunel", "hold": 5.0, "lines": [("r01", "narrador", "Génesis te trae de vuelta a 2045.", "Genesis brings you back to 2045.")]},
    {"scene": "colonia_calma", "health": 0.3, "lines": [
        ("r02", "mario", "¡Volviste! ¿Estás bien?", "You're back! Are you okay?"),
        ("r03", "viajero", "Estoy bien. ¿Cambió algo?", "I'm fine. Did anything change?", 0.6)]},
    {"scene": "ventana_revela", "who": ["mario", "andres", "viajero"], "from": 0.0, "to": 0.3, "lines": [
        ("r04", "andres", "Mira. El humo bajó en algunas regiones. Hay un poco más de azul.", "Look. The smoke has cleared in some regions. There's a little more blue.", 0.8)]},
    {"scene": "genesis_cerca", "who": ["viajero", "nikol"], "lines": [
        ("r05", "nikol", "Los registros cambiaron. Lo que hiciste allá está llegando hasta aquí.", "The records have changed. What you did back there is reaching us here."),
        ("r06", "nikol", "Génesis tiene energía para otro salto. Pero solo podrás volver si el futuro sigue mejorando.", "Genesis has energy for another jump. But you can only go back if the future keeps improving.", 0.6)]},
    {"scene": "activacion", "lines": [("r07", "nikol", "Prepárate. Todavía quedan lugares por salvar.", "Get ready. There are still places to save.", 1.0)]},
]

FINAL_BUENO = [
    {"scene": "activacion", "lines": [("b01", "narrador", "Año 2045. Génesis se activa por última vez.", "The year 2045. Genesis activates for the last time.")]},
    {"scene": "colonia_calma", "health": 1.0, "lines": [
        ("b02", "mario", "¡No puede ser! ¡Volviste!", "No way! You're back!"),
        ("b03", "viajero", "Lo conseguimos.", "We did it."),
        ("b04", "mario", "¿Y la Tierra?", "And the Earth?", 0.6)]},
    {"scene": "ventana_revela", "who": ["mario", "andres", "viajero"], "from": 0.15, "to": 1.0, "lines": [
        ("b05", "narrador", "Se acercan a la ventana. Los océanos vuelven a ser azules. Las regiones de bosque recuperaron su verde. La atmósfera se ve más limpia.", "They move closer to the window. The oceans are blue again. The forests have regained their green. The atmosphere looks cleaner."),
        ("b06", "andres", "¿Ese… es nuestro planeta?", "Is that… our planet?"),
        ("b07", "viajero", "Sí. Nuestro hogar.", "Yes. Our home.", 0.8)]},
    {"scene": "planeta_cambia", "from": 0.3, "to": 1.0, "hold": 9.0, "lines": []},
    {"scene": "tierra_desde_luna", "health": 1.0, "lines": [("b08", "nikol", "Los registros históricos cambiaron. Las comunidades lograron adaptarse, proteger sus ecosistemas y reducir los riesgos que amenazaban su futuro.", "The historical records have changed. Communities managed to adapt, protect their ecosystems and reduce the risks that threatened their future.")]},
    {"scene": "montaje_lugares", "health": 1.0, "places": ["chosica", "piura", "huascaran", "mocoa"], "hold": 22.0, "lines": [("b09", "narrador", "En los pueblos de las quebradas ensayaron por dónde subir. En las ciudades junto al río dejaron libre el cauce. En las escuelas, los niños volvieron al patio. En la montaña, la sirena sonó a tiempo.", "In the ravine towns, people rehearsed which way to climb. In the river cities, they kept the riverbed clear. In the schools, children went back to the playground. In the mountains, the siren sounded in time.")]},
    {"scene": "cuaderno_salvado", "lines": [("b10", "killa", "Hoy el río creció. Sonó la sirena y subimos todos al cerro, como en los ensayos. Mi abuela dice que antes el río avisaba. Ahora avisamos nosotros. El lunes hay clases.", "Today the river rose. The siren sounded and we all climbed the hill, just like we practiced. My grandma says the river used to warn us. Now we warn each other. There's school on Monday.", 0.8)]},
    {"scene": "tierra_amanecer", "health": 1.0, "hold": 13.0, "lines": [("b11", "narrador", "No lo salvaste todo. Nadie puede. Hay casas que ya no están. Pero la gente está.", "You didn't save everything. Nobody can. Some houses are gone. But the people are still here.", 0.6)]},
    {"scene": "ventana", "who": ["mario", "viajero"], "health": 1.0, "lines": [
        ("b12", "mario", "¿Entonces podemos ir?", "So can we go?"),
        ("b13", "viajero", "Esta vez sí.", "This time, yes.", 1.0)]},
    {"scene": "tierra_orbita", "health": 1.0, "lines": [
        ("b14", "narrador", "El planeta nunca necesitó héroes capaces de viajar en el tiempo. Necesitaba personas dispuestas a cambiar el presente.", "The planet never needed heroes who could travel through time. It needed people willing to change the present.", 1.0),
        ("b15", "narrador", "Tú no tienes una máquina para volver al pasado. No la necesitas. Todavía es hoy.", "You don't have a machine to go back in time. You don't need one. It's still today."),
        ("b16", "narrador", "Los datos de la Tierra ya existen: satélites que miran el planeta cada día, una segunda fuente que los comprueba y, dicho en voz alta, lo que aún no se sabe. El cambio empieza cuando sales a contarlo.", "The Earth's data already exists: satellites watching the planet every day, a second source to check them and, said out loud, what is still unknown. Change begins when you go out and share it.", 1.0)]},
    {"scene": "satelites", "hold": 9.0, "lines": []},
    {"scene": "titulo", "hold": 2.0, "lines": [("b17", "narrador", "TERRA 2045. Un proyecto de Los Causas Espaciales para el NASA Space Apps Challenge 2026.", "TERRA 2045. A Los Causas Espaciales project for the NASA Space Apps Challenge 2026.")]},
    {"scene": "creditos", "hold": 52.0, "lines": []},
]

FINAL_INTERMEDIO = [
    {"scene": "activacion_debil", "lines": [("i01", "narrador", "Año 2045. Génesis ya no tiene energía para otro viaje.", "The year 2045. Genesis has no energy left for another journey.")]},
    {"scene": "colonia_calma", "health": 0.5, "lines": [
        ("i02", "mario", "¿Lo lograste?", "Did you do it?"),
        ("i03", "viajero", "No lo sé. Mira.", "I don't know. Look.", 0.6)]},
    {"scene": "ventana_revela", "who": ["mario", "andres", "viajero"], "from": 0.1, "to": 0.5, "lines": [("i04", "narrador", "Desde la ventana, la Tierra se ve distinta. Hay regiones que recuperaron su verde y mares que volvieron a ser azules. Y hay otras que siguen cubiertas de humo.", "From the window, the Earth looks different. Some regions have regained their green and some seas are blue again. And others are still covered in smoke.", 0.6)]},
    {"scene": "planeta_cambia", "from": 0.1, "to": 0.5, "hold": 9.0, "lines": []},
    {"scene": "genesis_cerca", "who": ["viajero", "nikol"], "lines": [
        ("i05", "nikol", "Los registros cambiaron en muchos lugares. Pero no fue suficiente para evitar el colapso en todas partes.", "The records changed in many places. But it wasn't enough to prevent the collapse everywhere."),
        ("i06", "viajero", "¿Todo lo que hicimos no sirvió?", "Was everything we did for nothing?"),
        ("i07", "nikol", "Sí sirvió. Cada lugar que llegó a tiempo es una hoja que cambió. Pero la recuperación necesita acciones sostenidas y colectivas, en todos los frentes.", "It wasn't for nothing. Every place that was reached in time is a page that changed. But recovery needs sustained, collective action, on every front.", 0.6)]},
    {"scene": "montaje_mixto", "health": 0.5, "places": ["chosica", "huascaran", "piura", "mocoa"], "hold": 18.0, "lines": [("i08", "narrador", "Algunas hojas del cuaderno cambiaron. La última, la de Killa, sigue igual.", "Some pages of the notebook changed. The last one, Killa's, is still the same.")]},
    {"scene": "cuaderno", "lines": [("i09", "killa", "Mi abuela dice que antes el río avisaba. Esa noche no avisó nadie.", "My grandma says the river used to warn us. That night, nobody warned us.", 1.0)]},
    {"scene": "ventana", "who": ["andres", "mario"], "health": 0.5, "lines": [
        ("i10", "andres", "Algún día.", "Someday."),
        ("i11", "mario", "Algún día iremos.", "Someday we'll go.", 1.0)]},
    {"scene": "tierra_orbita", "health": 0.5, "hold": 10.0, "lines": []},
    {"scene": "tierra_desde_luna", "health": 0.5, "lines": [
        ("i12", "narrador", "Cada decisión importa. Pero ninguna basta sola.", "Every decision matters. But none is enough on its own.", 0.8),
        ("i13", "narrador", "En el juego, el último regreso ya pasó. Afuera no hay máquina del tiempo. Hay datos, y todavía es hoy.", "In the game, the last return is gone. Out here there is no time machine. There is data, and it's still today."),
        ("i14", "narrador", "Puedes leerlos antes de que sea tarde, comprobarlos con una segunda fuente y salir a contarlo.", "You can read it before it's too late, check it against a second source, and go out and share it.", 1.0)]},
    {"scene": "titulo", "hold": 2.0, "lines": [("i15", "narrador", "TERRA 2045. El futuro no está escrito. Pero cada decisión deja una huella.", "TERRA 2045. The future is not written. But every decision leaves a mark.")]},
    {"scene": "creditos", "hold": 52.0, "lines": []},
]

FINAL_PERDEDOR = [
    {"scene": "activacion_debil", "hold": 6.0, "lines": [("l01", "narrador", "Año 2045. Génesis te devuelve a la colonia.", "The year 2045. Genesis brings you back to the colony.")]},
    {"scene": "colonia_calma", "health": 0.0, "lines": [
        ("l02", "mario", "¡Volviste! ¿Qué pasó? ¿Lo conseguimos?", "You're back! What happened? Did we do it?", 2.0),
        ("l03", "mario", "No… ¿verdad?", "No… right?"),
        ("l04", "viajero", "Lo intenté. Pero no fue suficiente.", "I tried. But it wasn't enough.", 0.6)]},
    {"scene": "genesis_cerca", "who": ["nikol", "viajero"], "lines": [("l05", "nikol", "Regresaste, pero los registros no cambiaron. Génesis ya no tiene energía para volver.", "You came back, but the records didn't change. Genesis has no energy left to go back.", 0.6)]},
    {"scene": "montaje_perdido", "places": ["chosica", "piura", "huascaran"], "hold": 15.0, "lines": []},
    {"scene": "alarma", "health": 0.0, "lines": [("l06", "andres", "¡Alerta! ¡La atmósfera de la Tierra está en estado crítico!", "Alert! The Earth's atmosphere is in a critical state!")]},
    {"scene": "colapso", "hold": 30.0, "lines": [("l07", "narrador", "Una cadena de catástrofes ambientales se desata sobre el planeta.", "A chain of environmental catastrophes is unleashed across the planet.")]},
    {"scene": "ventana_oscura", "who": ["mario", "viajero"], "lines": [
        ("l08", "mario", "Era nuestro hogar…", "It was our home…", 1.0),
        ("l09", "viajero", "Tuvimos tantas oportunidades…", "We had so many chances…", 1.2)]},
    {"scene": "cuaderno", "lines": [
        ("l10", "narrador", "El cuaderno de Killa sigue en el archivo. La última hoja dice lo mismo.", "Killa's notebook is still in the archive. The last page says the same thing."),
        ("l11", "killa", "Si lo estaban viendo, ¿por qué nadie vino a decirnos?", "If they were watching, why didn't anyone come to tell us?", 1.2)]},
    {"scene": "negro_titulo", "hold": 1.5, "lines": [("l12", "narrador", "El futuro que intentamos evitar se convirtió en nuestra última realidad.", "The future we tried to prevent became our last reality.", 2.0)]},
    {"scene": "tierra_hoy", "health": 0.75, "lines": [
        ("l13", "narrador", "Pero esto es una historia. Afuera, todavía es hoy. Los datos existen, y alguien tiene que leerlos a tiempo, comprobarlos y salir a avisar.", "But this is a story. Out here, it's still today. The data exists, and someone has to read it in time, check it, and go out and warn people.", 1.0),
        ("l14", "narrador", "El futuro no está escrito. Pero cada decisión deja una huella.", "The future is not written. But every decision leaves a mark.")]},
    {"scene": "titulo", "hold": 3.0, "lines": []},
    {"scene": "creditos", "hold": 52.0, "lines": []},
]

VIDEOS = {
    "trailer": {"title_es": "TERRA 2045 · Tráiler", "title_en": "TERRA 2045 · Trailer", "music": "Heroic Age", "max_s": 125, "shots": TRAILER,
                "music_cues": [{"track": "Lightless Dawn", "shot": 0}, {"track": "Heroic Age", "shot": 4, "align_end": True}]},
    "prologo": {"title_es": "TERRA 2045 · Prólogo", "title_en": "TERRA 2045 · Prologue", "music": "Lightless Dawn", "max_s": 120, "shots": PROLOGO},
    "viaje": {"title_es": "TERRA 2045 · El viaje", "title_en": "TERRA 2045 · The Jump", "music": "Space 1990", "max_s": 60, "shots": VIAJE},
    "regreso": {"title_es": "TERRA 2045 · Regreso a 2045", "title_en": "TERRA 2045 · Back to 2045", "music": "Impact Prelude", "max_s": 75, "shots": REGRESO},
    "final_bueno": {"title_es": "TERRA 2045 · Final: un nuevo comienzo", "title_en": "TERRA 2045 · Ending: A New Beginning", "music": "Eternal Hope", "max_s": 300, "shots": FINAL_BUENO},
    "final_intermedio": {"title_es": "TERRA 2045 · Final: un futuro a medias", "title_en": "TERRA 2045 · Ending: A Future Half-Saved", "music": "Bittersweet", "max_s": 300, "shots": FINAL_INTERMEDIO},
    "final_perdedor": {"title_es": "TERRA 2045 · Final: un futuro perdido", "title_en": "TERRA 2045 · Ending: A Lost Future", "music": "Anguish", "max_s": 300, "shots": FINAL_PERDEDOR},
}

# Música (Kevin MacLeod, incompetech.com, CC BY 4.0). La descarga scripts/video/preparar.ps1.
MUSIC = ["Heroic Age", "Lightless Dawn", "Space 1990", "Eternal Hope", "Bittersweet", "Anguish", "Impact Prelude"]


def lines() -> list[dict]:
    """Todas las líneas de voz, con su video y plano."""
    out = []
    for video, spec in VIDEOS.items():
        for index, shot in enumerate(spec["shots"]):
            for line in shot["lines"]:
                pid, who, es, en, *rest = line
                out.append({"id": pid, "video": video, "shot": index, "who": who, "es": es, "en": en, "pause": rest[0] if rest else 0.35})
    return out


def main() -> None:
    ids = [item["id"] for item in lines()]
    assert len(ids) == len(set(ids)), "ids de línea repetidos"
    videos = {key: {**spec, "shots": [{**shot, "lines": [line[0] for line in shot["lines"]]} for shot in spec["shots"]]} for key, spec in VIDEOS.items()}
    OUT.write_text(json.dumps({"videos": videos, "lines": lines(), "music": MUSIC}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(ids)} líneas en {OUT}")


if __name__ == "__main__":
    main()
