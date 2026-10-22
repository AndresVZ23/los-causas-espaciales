---
name: Los Causas Espaciales
description: Consola técnica de inteligencia terrestre verificable para decisiones de inversión.
colors:
  mineral-cyan: "#38d9c3"
  night-ground: "#080c0d"
  instrument-surface: "#141618"
  raised-graphite: "#1f2226"
  control-graphite: "#202428"
  structural-border: "#2e3136"
  quiet-rule: "#25292d"
  cold-white: "#e8eaed"
  cool-muted: "#9aa4ae"
  cool-subtle: "#818b94"
  verified-green: "#75e59a"
  unavailable-red: "#ee7180"
  assumption-amber: "#f1c84b"
  cached-blue: "#74a0ff"
typography:
  display:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "clamp(25px, 3vw, 38px)"
    fontWeight: 520
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.2
  title:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "11px"
    fontWeight: 560
    lineHeight: 1.3
  data:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "10px"
    fontWeight: 500
    lineHeight: 1.35
rounded:
  structural: "2px"
  status-dot: "999px"
spacing:
  micro: "4px"
  xs: "7px"
  sm: "9px"
  md: "14px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.mineral-cyan}"
    textColor: "{colors.night-ground}"
    typography: "{typography.label}"
    rounded: "{rounded.structural}"
    height: "35px"
    padding: "0 16px"
  input:
    backgroundColor: "{colors.control-graphite}"
    textColor: "{colors.cold-white}"
    typography: "{typography.data}"
    rounded: "{rounded.structural}"
    height: "31px"
    padding: "0 8px"
  panel:
    backgroundColor: "{colors.instrument-surface}"
    textColor: "{colors.cold-white}"
    rounded: "{rounded.structural}"
    padding: "19px"
  provenance-cell:
    backgroundColor: "{colors.night-ground}"
    textColor: "{colors.cold-white}"
    typography: "{typography.data}"
    rounded: "{rounded.structural}"
    padding: "6px 7px"
---

# Design System: Los Causas Espaciales

## Overview

**Creative North Star: "Consola nocturna de inteligencia terrestre"**

El sistema es una mesa operativa densa y oscura para comparar ubicaciones, inspeccionar series y seguir una cadena de evidencia. Su autoridad proviene de la estructura: un masthead informativo, reglas finas, tipografía contenida, un mapa contextual verificable y estados explícitos. No intenta parecer una landing ni una cabina de ciencia ficción.

Las superficies son grafitos planos separados por tono y líneas de 1 px. El cian es una señal escasa para selección, foco, acción y adquisición; nunca se convierte en una atmósfera decorativa. No hay gradientes, vidrio, resplandor ni tarjetas redondeadas blandas.

**Key Characteristics:**

- Consola técnica oscura con densidad alta, jerarquía precisa y lectura prolongada.
- Public Sans para lenguaje y estructura; IBM Plex Mono para datos, códigos y procedencia.
- Mapa contextual NASA GIBS, configuración, serie anual y pipeline visibles desde el primer viewport de escritorio.
- Procedencia efectiva y brechas de datos expresadas como texto verificable, no solo color.
- Geometría casi cuadrada de 2 px, superficies planas y reglas estructurales de 1 px.

## Colors

La paleta usa negros verdosos y grafitos fríos como instrumento de trabajo; el cian mineral aparece con moderación y los otros colores quedan reservados para estados verificables.

### Primary

- **Cian mineral:** acción primaria, módulo o variable activa, foco visible, sitio principal y adquisición en curso.

### Secondary

- **Verde verificado:** fuente operativa, dato real y capacidad funcional.
- **Azul de caché:** observación recuperada desde una copia validada.

### Tertiary

- **Ámbar de supuesto:** supuestos editables, cautelas y capacidades todavía pendientes.
- **Rojo no disponible:** fuente ausente, brecha explícita o resultado negativo.

### Neutral

- **Suelo nocturno:** fondo global y contraste máximo detrás de la consola.
- **Superficie de instrumento:** paneles de resultado, controles contextuales y bloques de evidencia.
- **Grafito elevado y grafito de control:** estados interactivos y campos sin sugerir flotación.
- **Blanco frío, gris legible y gris secundario:** tres niveles estables de texto.
- **Borde estructural y regla silenciosa:** separadores de 1 px para la retícula, tablas y estados.

### Named Rules

**The One Acquisition Line Rule.** El cian identifica selección, foco, acción o progreso; no rellena regiones decorativas.

**The Provenance Color Rule.** Verde, azul, cian, ámbar y rojo acompañan una etiqueta de procedencia o estado legible; el color nunca carga el significado por sí solo.

## Typography

**Display Font:** Public Sans (con fallback sans-serif)

**Body Font:** Public Sans (con fallback sans-serif)

**Label/Mono Font:** IBM Plex Mono (con fallback monospace)

**Character:** Public Sans conserva claridad y neutralidad comercial en una interfaz muy densa. IBM Plex Mono convierte fechas, coordenadas, unidades, estados del pipeline e identificadores en un registro estable sin hacer que toda la aplicación parezca una terminal.

### Hierarchy

- **Display** (520, `clamp(25px, 3vw, 38px)`, 1.2): encabezados de evidencia y cobertura bajo el banco operativo.
- **Headline** (600, 18px, 1.2): estados vacíos y hallazgos principales.
- **Title** (600, 14px, 1.3): títulos compactos de panel y bloques de resultado.
- **Body** (400, 14px, 1.4): explicación, limitaciones y lectura continua.
- **Label** (560, 11px, 1.3): navegación, acciones y controles.
- **Data** (500, 9–11px, 1.35): coordenadas, fechas, fuentes, unidades, códigos y registros de proceso; usa cifras tabulares cuando corresponda.

### Named Rules

**The Numeric Instrument Rule.** La monoespaciada se reserva para información que gana precisión al alinear cifras o distinguir códigos; no sustituye a la tipografía de lectura.

## Layout

En escritorio, un masthead de 150 px combina marca, contexto, fechas y la clave de procedencia. Debajo, una retícula de 190 px para el rail y dos columnas de trabajo distribuye el primer viewport en mapa NASA GIBS, configuración, serie temporal anual y pipeline de nueve etapas. El rail recorre las tres filas del banco; el mapa y la configuración ocupan 355 px, la serie 265 px y el pipeline 110 px.

El sistema responde en `1180px`, `900px` y `560px`. Bajo 1180 px compacta el rail a 174 px y el masthead a 146 px. A 900 px o menos, el masthead pasa a 72 px, el banco se apila, el rail se convierte en drawer y aparece una navegación inferior fija de 66 px. El mapa precede a la configuración; los detalles de contexto y procedencia se trasladan junto a los controles; luego siguen la serie y el pipeline horizontal desplazable. Bajo 560 px, los editores de ubicación, resultados y tablas ajustan sus columnas sin ocultar estados.

En móvil, entradas, resúmenes y acciones usan objetivos táctiles de al menos 44 px. El contenido reserva espacio para la navegación inferior y las áreas desplazables conservan el orden operativo.

## Elevation & Depth

La profundidad es tonal y plana. Suelo, superficie, control, borde y regla forman la jerarquía; paneles y secciones no flotan. Las sombras aparecen únicamente en controles nativos superpuestos al mapa o como oscurecimiento interior de la imagen cartográfica, nunca como glow ni como elevación decorativa.

### Named Rules

**The Flat-by-Default Rule.** Si un bloque puede separarse con un cambio tonal o una regla de 1 px, no usa sombra.

## Shapes

La geometría estructural es casi cuadrada: campos, botones, tooltips y paneles usan 2 px. Los grandes contenedores permanecen rectangulares y se unen mediante reglas de 1 px. Solo marcadores, puntos de estado y nodos del pipeline usan círculos; no hay cápsulas de navegación ni tarjetas con radios suaves de 6–10 px.

La selección se expresa con segmentos finos: 2 px en el borde del módulo activo y 1 px bajo una variable o sobre un destino móvil. El mapa conserva marcadores cartográficos reconocibles y un eje comparativo discontinuo.

## Components

### Buttons

- **Shape:** rectángulos compactos de 2 px; la acción primaria mide 35 px en escritorio y al menos 44 px en móvil.
- **Primary:** fondo cian mineral, texto casi negro y peso alto; se reserva para ejecutar el análisis.
- **Hover / Focus:** cambio tonal corto, borde coherente y contorno global de foco cian de 2 px con offset de 2 px.
- **Disabled:** grafito neutro, texto atenuado y lenguaje explícito como “Módulo pendiente”.

### Cards / Containers

- **Corner Style:** 2 px en paneles de evidencia; las zonas mayores de la consola permanecen cuadradas.
- **Background:** capas planas de suelo nocturno, superficie de instrumento y grafito elevado.
- **Shadow Strategy:** ninguna en reposo; solo overlays cartográficos justifican sombra.
- **Border:** borde estructural o regla silenciosa de 1 px.
- **Internal Padding:** 14–19 px para paneles; 6–9 px para celdas densas.

### Inputs / Fields

- **Style:** fondo grafito de control, borde estructural, radio de 2 px y cifras tabulares.
- **Focus:** borde cian más un anillo contenido de 1 px; el foco global sigue visible por teclado.
- **Sizing:** 31–32 px en escritorio y 44 px en móvil.
- **Error / Disabled:** rojo solo para error comprobable; neutral atenuado para indisponibilidad.

### Navigation

El rail de 190 px usa icono, etiqueta y punto de disponibilidad. El módulo activo recibe un segmento cian de 2 px en el borde izquierdo; el hover cambia apenas el tono de la fila. En móvil, cuatro destinos prioritarios y “Más” forman la barra fija de 66 px; el destino activo usa icono cian y una regla superior de 1 px. El drawer gestiona foco, Escape, `inert` y `aria-hidden`.

### Provenance Ledger

La clave superior enumera `REAL_DATA`, `CACHED_DATA`, `MODEL_ESTIMATE`, `USER_ASSUMPTION` y `DATA_UNAVAILABLE` con punto, código y descripción. Tras una ejecución, la procedencia efectiva registra sitio, estado, dataset, versión, fecha de descarga y resolución espacial. En móvil aparece dentro de “Contexto de análisis”, junto a región, fuente y fechas; antes de una ejecución declara honestamente que no hay datos.

### NASA GIBS Map

Blue Marble de NASA EOSDIS GIBS funciona como basemap raster estático y contextual, con atribución visible. No se presenta como una observación analítica. El mapa añade dos marcadores, eje comparativo discontinuo, coordenadas WGS84 y controles discretos.

### Temporal Series

La gráfica anual usa retícula fina, ejes monoespaciados y líneas sin animación. Antes de ejecutar, conserva la retícula pero declara que la serie aún no está disponible; nunca rellena el espacio con datos ficticios.

### Pipeline & Acquisition

Nueve pasos numerados comparten una línea de 1 px y estados textuales. Durante la consulta, un segmento cian sólido de 1 px recorre el perímetro interior del mapa y el pipeline cambia a “EN CURSO”. Con `prefers-reduced-motion`, el segmento queda fijo en una posición de referencia y toda transición se reduce a 1 ms.

## Do's and Don'ts

### Do:

- **Do** mantener el mapa contextual, la configuración, la serie y el pipeline legibles desde el primer viewport de escritorio.
- **Do** mostrar procedencia efectiva con sitio, estado, dataset, versión, descarga y resolución cuando existan resultados.
- **Do** declarar `DATA_UNAVAILABLE`, “pendiente” o “aún no disponible” cuando falte una fuente o ejecución.
- **Do** conservar foco visible, semántica, navegación por teclado y objetivos táctiles móviles de al menos 44 px.
- **Do** usar Public Sans para lectura e IBM Plex Mono para datos instrumentales.

### Don't:

- **Don't** usar gradientes, vidrio, glow, sombras decorativas ni radios blandos de 6–10 px.
- **Don't** presentar el basemap NASA GIBS como evidencia analítica ni mostrar métricas o series ficticias.
- **Don't** codificar procedencia, disponibilidad o riesgo únicamente mediante color.
- **Don't** convertir una capacidad pendiente en una tarjeta promocional o un estado de éxito.
- **Don't** presentar el VAN condicionado como recomendación de inversión.
