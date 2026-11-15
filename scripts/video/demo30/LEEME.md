# Demo de 30 segundos (ADR-051)

El video que pide la entrega de NASA Space Apps 2026 como «Project Demo». Deja claros en menos de 30 segundos el problema, la necesidad y la solución, sin nombrarlos, con la historia del videojuego TERRA 2045 y la plataforma con los datos de la NASA a la vista. Sale en dos versiones con las mismas imágenes:

| Archivo | Para qué | Voz y textos |
|---|---|---|
| `videos/terra2045_demo30_en.mp4` | **La página oficial del proyecto** (jurado global) | Inglés |
| `videos/terra2045_demo30_es.mp4` | La sede Moquegua y presentaciones en español | Español, con subtítulos en inglés en pantalla |

Cada uno mide **885 cuadros a 30 por segundo: 29,5 s**, medio segundo menos que el límite, para que ningún reproductor lo muestre como 0:31. Junto a cada video queda su `.srt`.

## El mensaje: problema, necesidad y solución, sin nombrarlos

A Nikol le observaron el 15-nov que el video debía dejar claros el problema, la necesidad y la solución. Un corte con esas tres palabras en la voz y en pantalla no le gustó: pidió que se entiendan sin decirlas, con una pregunta, y que vuelva la plataforma con los datos a la vista. Quedó así:

- **El problema:** «Año 2045. La Tierra está en caos.»
- **La pregunta, que abre la necesidad:** «¿Y si pudieras volver a 2026 y cambiarlo?» «Las señales ya estaban en los datos de la NASA.»
- **La solución, en dos pasos:** la plataforma, que lee esas señales («qué cambia, dónde, cuánto y si es significativo»; «si dos fuentes no coinciden, lo decimos»), y el videojuego («enfrentas huaicos, inundaciones, erupciones y avalanchas, y avisas a tiempo»).

El año 2045 es la historia del juego, no un pronóstico; por eso esos planos llevan el rótulo «Cinemática».

## Reglas oficiales que cumple

Leídas el 15-nov-2026 en la [Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/) y la [Judging & Awards Guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/):

- **Duración:** «30-second or less»; lo que se pasa no entra al jurado global. `build.py` falla si el archivo no mide los cuadros que pide `guion.json` (885), si pasa de esa duración o si encuentra un cuadro negro suelto en medio de un plano.
- **Idioma:** inglés en la página y en lo enlazado. Un video hablado en otro idioma **debe** llevar subtítulos en inglés: la versión en español los lleva en pantalla.
- **Enlace:** público, sin contraseña ni registro (YouTube, Drive…). Subirlo es tarea del equipo.
- **Uso de IA** (la guía la llama «SI»): imágenes y videos con marca visible; audio declarado en texto y en metadatos; sin logotipos ni elementos de marca de NASA. El video lleva la marca todo el tiempo, los metadatos del archivo lo declaran y no usa ningún logotipo.
- **Menores:** ninguna imagen ni voz de menores de 18 años.
- **Plantilla del video:** quiénes somos · reto y motivo · nombre y lema · cómo funciona, con datos NASA y de agencias socias · el futuro. El equipo se presenta en el primer rótulo y en el cierre; el reto, en el plano de las cuatro preguntas y en el cierre.

## Qué se ve

| Tiempo | Plano | Imagen | Qué es |
|---|---|---|---|
| 0,0–3,6 s | Luna, 2045 | El viajero mira la Tierra enferma. «La Tierra está en caos». Se ve la Luna, pero no se dice que vivimos allí: lo pidió Nikol | Cinemática en 3D hecha para el video |
| 3,6–6,6 s | El salto | La pregunta «¿Y si pudieras volver a 2026?» mientras el contador baja de 2045 a 2026 | Cinemática |
| 6,6–9,7 s | Las señales | «Las señales ya estaban en los datos»: la Tierra en 3D se convierte en el globo del modo espectador con «Mar más caliente» | Cinemática y **captura de la aplicación**: anomalía de temperatura del mar de NASA GIBS, dato del 14-nov-2026. «1.380 distritos en emergencia»: Primicias (AFP), 3-nov-2026, la fuente de `nino-2026.ts` |
| 9,7–15,9 s | La plataforma | Primero la vista general (mapa, lectura climática, serie anual de 2001 a 2025 y etapas del análisis); después «Las preguntas del reto NASA», con la cámara bajando con la pregunta que nombra la voz. El paso de una a otra sigue a la voz | **Capturas de la plataforma**, análisis de clima de Moquegua y Arequipa |
| 15,9–18,2 s | Segunda fuente | Fila «Artefacto probable» de «Descubrimientos al cruzar fuentes» | **Captura de la plataforma**: 300 mm frente a 12 y 17 mm (ADR-036) |
| 18,2–22,5 s | El videojuego | Huaico en Chosica, inundación en Piura, erupción del Taal y avalancha del Huascarán; cada uno con un paso de la misión | Animación sobre el **relieve real** de cada misión (Copernicus DEM GLO-30 y ESA WorldCover). Eventos simulados |
| 22,5–25,3 s | Para quién y por qué | La Tierra de 2045 sana. «Avisar a tiempo salva vidas» | Cinemática |
| 25,3–29,5 s | Cierre | Amanecer del tráiler con título, equipo, reto y créditos | Tramo del tráiler (ADR-050) |

**Qué es real y qué no.** Las capturas son la aplicación tal cual. Las cinemáticas son animación hecha para este video: se parecen al juego en la historia, los lugares y el relieve, pero se ven mejor que el juego de hoy. Por eso llevan en pantalla el rótulo «Cinemática» o «Animación sobre el relieve real · evento simulado». Ninguna cifra se escribe de memoria: sale de una captura o de una fuente citada en pantalla.

## Volver a armarlo

```bash
# una vez: voz libre de Piper en una carpeta local corta (espeak-ng no admite rutas de más de 160 caracteres)
python3 -m venv .herramientas/voz && .herramientas/voz/bin/pip install piper-tts
(mkdir -p .herramientas/piper-voces && cd .herramientas/piper-voces && ../voz/bin/python -m piper.download_voices es_MX-claude-high en_US-ljspeech-high)

# con la aplicación en marcha (localhost:3100 y su API): capturas de la interfaz
node scripts/video/demo30/tomas.cjs

# los dos videos (necesita ffmpeg, o `pip install imageio-ffmpeg`, y Playwright para Node; las cinemáticas usan la tarjeta gráfica)
python scripts/video/demo30/build.py --lang en
python scripts/video/demo30/build.py --lang es
```

- `guion.json`: los cortes (en cuadros), los tramos de la base, las frases de la voz en los dos idiomas y todos los textos en pantalla.
- `cine/cine.js`: las cinemáticas en 3D (three.js, el del frontend). Cada escena es una función del tiempo: `window.draw(escena, segundos)` dibuja siempre el mismo cuadro. `cine/cine_frames.cjs` saca los cuadros; `node scripts/video/demo30/cine/cine_frames.cjs prueba luna 1,3 <carpeta>` saca cuadros sueltos para revisar.
- `overlay.html`: la capa de arriba (textos, capturas con su cámara y resaltes) para un instante dado. Donde queda transparente se ve la base. Sobre las capturas de la plataforma pone una franja opaca arriba y otra abajo, para que ningún rótulo quede encima de otro texto. `frames.cjs` saca sus 900 cuadros.
- `build.py`: voces, línea de tiempo, base (cinemáticas y cierre), música con atenuación bajo la voz, unión, `.srt` y comprobación de la duración y de cuadros negros.

**Parpadeo al montar la capa (15-nov).** En dos puntos del video la capa de textos y capturas desaparecía uno o dos cuadros. La causa: el navegador guarda como PNG sin transparencia los cuadros totalmente opacos, y al cambiar de formato en mitad de la serie ffmpeg rehace el montaje y deja algún cuadro sin la capa. `frames.cjs` dibuja ahora una fila de más (1081 en vez de 1080), que queda siempre transparente; `build.py` la recorta, falla si algún cuadro sale sin transparencia y en su revisión del video final busca tramos de uno a tres cuadros más oscuros que sus vecinos. Un primer arreglo con `clip-path` en la página se descartó: volvía el dibujo tan lento que las capturas vencían el tiempo de espera.

**Cuadro negro en la llegada (15-nov).** La escena `llegada` salía negra justo en el segundo 1,0: un cuadro negro a los 9,4 s del video. `cine_frames.cjs` ahora reconoce un cuadro negro por el tamaño del JPEG y lo vuelve a dibujar 4 ms después; `build.py` revisa el video final y falla si queda alguno.
- `tomas.cjs`: vuelve a capturar la interfaz. El video usa cuatro de esas tomas (el globo con El Niño, la vista general de la plataforma, las preguntas del reto y la segunda fuente); las demás quedan de cortes anteriores.

Las posiciones de los resaltes están escritas en `overlay.html` para estas tomas: si cambia la interfaz, se revisan.

## Cómo se dibujan los desastres

Son reglas de la animación, no de la plataforma ni del juego, y no ubican ni pronostican ningún evento real:

- **Relieve:** el archivo de la misión (`backend/data/missions/terrain/<lugar>.json`), con una pasada de suavizado y exagerado entre 1,25 y 2,4 veces según la escena. El color sale de la cobertura de WorldCover; las casas son bloques sobre las celdas urbanas.
- **Huaico (Chosica):** entre 500 puntos altos, el camino cuesta abajo (siempre al vecino más bajo) que más desciende y termina junto a celdas urbanas.
- **Avalancha (Huascarán):** el mismo camino cuesta abajo desde la celda más alta.
- **Erupción (Taal):** sale de la celda más alta del recorte.
- **Inundación (Piura):** un plano de agua que sube del percentil 30 al 82 de la altura de las celdas urbanas.

## Voz, música y licencias

- **La voz no sale idéntica dos veces.** Piper cambia la duración de cada frase unas décimas en cada síntesis. `build.py` guarda las frases ya hechas en la carpeta de trabajo, corre el inicio de una frase si la anterior se alargó y falla si la última no cabe en los 30 s.
- **Voz:** [Piper](https://github.com/OHF-Voice/piper1-gpl) 1.8.0, sin internet. `es_MX-claude-high` (Apache-2.0) y `en_US-ljspeech-high` (datos LJ Speech, dominio público). No se usó la voz del sistema de macOS: su licencia solo permite uso personal, no publicarla. `--voz edge` usa las voces de Edge del tráiler (ADR-050), que envían el guion a ese servicio.
- **Música:** «Heroic Age», Kevin MacLeod (incompetech.com), CC BY 4.0, acreditada en el cierre. Se usa el tramo final de la pista para que el último acorde coincida con el final.
- **Imágenes de la Tierra y la Luna:** NASA Blue Marble y Black Marble (`videos/assets/`), dominio público. El viajero es el modelo `hombre.glb` del juego (Mixamo; su licencia sigue abierta, ADR-048).
- **Datos acreditados en el cierre:** NASA POWER (MERRA-2), NASA GIBS, GPM IMERG, ERA5, CHIRPS, Copernicus DEM y ESA WorldCover.

## Lo que falta revisar antes de publicar

- **Oír el video.** Se armó sin poder escucharlo: la mezcla está medida, pero la pronunciación la tiene que aprobar una persona. La voz en inglés es estadounidense.
- **Subirlo** a un enlace público y pegarlo en el formulario.
- La interfaz que se ve en las capturas está en español; los rótulos del video en inglés la explican.
