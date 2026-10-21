---
name: Los Causas Espaciales
description: Inteligencia terrestre verificable para decisiones de inversión.
colors:
  mineral-cyan: "#38d9c7"
  night-ground: "#0b0c0d"
  instrument-surface: "#141618"
  raised-graphite: "#1c1f22"
  control-graphite: "#202326"
  structural-border: "#303439"
  quiet-rule: "#25282c"
  cold-white: "#f0f3f5"
  cool-muted: "#a7b0b9"
  cool-subtle: "#7f8994"
  verified-green: "#74d99f"
  unavailable-red: "#f0717e"
  assumption-amber: "#e0b85b"
  cached-blue: "#82aaff"
typography:
  display:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "clamp(24px, 3vw, 38px)"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.2
  title:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "17px"
    fontWeight: 650
    lineHeight: 1.2
  body:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.3
  data:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.2
rounded:
  control: "6px"
  quiet: "7px"
  panel: "10px"
  pill: "999px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.mineral-cyan}"
    textColor: "{colors.night-ground}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "44px"
    padding: "0 16px"
  input:
    backgroundColor: "{colors.control-graphite}"
    textColor: "{colors.cold-white}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    height: "36px"
    padding: "7px 10px"
  panel:
    backgroundColor: "{colors.instrument-surface}"
    textColor: "{colors.cold-white}"
    rounded: "{rounded.panel}"
    padding: "22px"
  variable-chip:
    backgroundColor: "{colors.raised-graphite}"
    textColor: "{colors.cold-white}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "5px 8px"
---

# Design System: Los Causas Espaciales

## Overview

**Creative North Star: "Mesa nocturna de interpretación terrestre"**

El sistema se comporta como un instrumento de análisis que permanece abierto durante sesiones largas: oscuro, preciso y sobrio. El mapa y la evidencia mandan; la interfaz organiza una cadena verificable desde la selección hasta la exportación sin convertir el producto en una landing promocional.

La densidad es técnica, pero no críptica. Las superficies se distinguen por luz, los límites por reglas finas y el cian aparece con moderación para selección, foco y acción. La estética rechaza gradientes, vidrio, brillo neón, tarjetas decorativas y cualquier cifra de ejemplo que pueda confundirse con evidencia.

**Key Characteristics:**

- Mapa geoespacial dominante y controles compactos.
- Procedencia visible en cada estado de datos.
- Una sola voz cromática de selección.
- Numerales tabulares para coordenadas, métricas y códigos.
- Capacidad y brechas declaradas con igual jerarquía.

## Colors

La paleta combina grafitos minerales, blancos fríos y un cian escaso; verde, ámbar, rojo y azul se reservan para semántica de procedencia y estado.

### Primary

- **Cian mineral:** acción primaria, selección activa, foco y progreso en curso.

### Secondary

- **Verde verificado:** dato real y estado funcional.
- **Ámbar de supuesto:** supuestos del usuario, fuentes pendientes y cautelas.
- **Rojo no disponible:** ausencia declarada o resultado negativo.
- **Azul de caché:** observaciones reales recuperadas desde caché.

### Neutral

- **Suelo nocturno:** fondo global.
- **Superficie de instrumento:** paneles principales.
- **Grafito elevado y de control:** chips, campos y estados interactivos.
- **Blanco frío, gris legible y gris secundario:** jerarquía tipográfica.
- **Borde estructural y regla silenciosa:** separación sin construir una cuadrícula pesada.

### Named Rules

**The One Acquisition Line Rule.** El cian identifica selección, foco, acción o progreso; no rellena regiones decorativas.

**The Provenance Color Rule.** Los colores semánticos significan origen o estado verificable, nunca decoración.

## Typography

**Display Font:** Public Sans (con fallback sans-serif)  
**Body Font:** Public Sans (con fallback sans-serif)  
**Label/Mono Font:** IBM Plex Mono (con fallback monospace)

**Character:** Public Sans mantiene la interfaz clara y contemporánea; IBM Plex Mono aporta estabilidad visual a coordenadas, identificadores y resultados tabulares sin convertir todo el producto en una terminal.

### Hierarchy

- **Display** (700, `clamp(24px, 3vw, 38px)`, 1.2): títulos de secciones de evidencia.
- **Headline** (700, 20px, 1.2): encabezados de resultados y estados vacíos.
- **Title** (650, 17px, 1.2): títulos de panel.
- **Body** (400, 14px, 1.45): explicación y lectura continua.
- **Label** (600, 13px, 1.3): campos, módulos y acciones.
- **Data** (400, 12–13px, 1.2): códigos, coordenadas, unidades, métricas y ejes.

### Named Rules

**The Numeric Instrument Rule.** La monoespaciada se usa solo cuando alinear cifras o distinguir códigos mejora la lectura.

## Layout

El escritorio usa un rail fijo de 206 px, una barra superior de 64 px y un banco de trabajo de tres columnas: configuración, mapa y lectura/procedencia. El mapa recibe la mayor fracción flexible. El pipeline ocupa el ancho del banco de trabajo como una secuencia continua de nueve pasos.

Entre 821 y 1180 px, controles y lectura se reorganizan sin perder el mapa. A 820 px o menos, el rail se convierte en drawer y aparece una barra inferior persistente con cuatro destinos y “Más”; el mapa, los controles, la procedencia y la evidencia se apilan. La separación base es 8/16/24/32 px y la densidad se reduce solo donde la interacción táctil exige 44 px mínimos.

## Elevation & Depth

La profundidad es tonal y plana por defecto. Las superficies en reposo no flotan: fondo, panel, control y borde crean la jerarquía. Las sombras se reservan para controles superpuestos sobre el mapa y paneles de evidencia que necesitan distinguirse del suelo durante el desplazamiento.

**The Flat-by-Default Rule.** Si un bloque puede separarse con tono o una regla de 1 px, no usa sombra.

## Shapes

Los controles usan esquinas discretas de 6–7 px; los paneles llegan a 10 px; los chips de variables son completamente redondos. Los estados activos se expresan mediante una línea cian de 1 px, no mediante cápsulas saturadas. La marca usa un rombo lineal que repite la geometría cartográfica de registro.

## Components

### Buttons

- **Shape:** control compacto de 6 px y altura mínima de 44 px.
- **Primary:** cian mineral con texto nocturno y peso 750.
- **Hover / Focus:** aclarado moderado y contorno de foco cian de 2 px.
- **Disabled:** grafito medio y texto atenuado; nunca parece una acción disponible.

### Chips

- **Style:** grafito elevado, texto frío, radio completo y 5 × 8 px de padding.
- **State:** describen variables; no simulan estados de procedencia.

### Cards / Containers

- **Corner Style:** 10 px para evidencia; paneles estructurales pueden permanecer cuadrados.
- **Background:** superficie de instrumento sobre suelo nocturno.
- **Shadow Strategy:** tonal por defecto; sombra suave solo cuando el bloque debe elevarse.
- **Border:** regla silenciosa o borde estructural de 1 px.
- **Internal Padding:** 16–22 px según densidad.

### Inputs / Fields

- **Style:** grafito de control, borde estructural, 6 px de radio y 36 px mínimos.
- **Focus:** borde cian más anillo de 1 px.
- **Error / Disabled:** rojo solo para error; grafito neutro para deshabilitado.

### Navigation

El rail mantiene icono y etiqueta, con una línea cian en el borde para el módulo activo. En móvil, cuatro módulos prioritarios y “Más” forman una barra inferior; el drawer completo administra foco, Escape, `inert` y `aria-hidden`.

### Provenance Row

Cada origen combina punto de color, nombre legible y código monoespaciado. La posición y el texto siguen siendo suficientes sin depender exclusivamente del color.

### Pipeline

Nueve etapas conectadas por una regla de 1 px muestran número, nombre y estado. Solo la ejecución activa anima la línea de adquisición; `prefers-reduced-motion` elimina ese movimiento.

## Do's and Don'ts

### Do:

- **Do** mantener mapa, evidencia y procedencia por encima de mensajes promocionales.
- **Do** usar Public Sans para lectura e IBM Plex Mono únicamente para datos instrumentales.
- **Do** declarar `DATA_UNAVAILABLE` cuando una capa o fuente aún no existe.
- **Do** mantener controles táctiles de al menos 44 px y foco visible.
- **Do** limpiar resultados de otro módulo antes de mostrar un estado pendiente.

### Don't:

- **Don't** usar gradientes, vidrio, glow neón ni paletas violeta/índigo de plantilla.
- **Don't** mostrar métricas, mapas o imágenes orbitales ficticias como evidencia.
- **Don't** usar tarjetas repetitivas como decoración ni píldoras rellenas para navegación.
- **Don't** codificar procedencia solo por color.
- **Don't** presentar el VAN condicionado como recomendación de inversión.
