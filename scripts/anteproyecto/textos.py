"""Textos del anteproyecto de la sede Moquegua (versión del 15-nov-2026, centrada en el videojuego TERRA 2045).

Fuente única para el PDF (hacer_pdf.py) y el PowerPoint (hacer_pptx.py). Cada sección es una lista de párrafos;
`True` lleva viñeta, como en la plantilla original. Caben 10 líneas por tarjeta: `hacer_pdf.py --medir` lo comprueba.

Todo lo que se afirma sale del repositorio: ADR-048 a ADR-050 (el juego: 57 misiones en los siete continentes, cinco
peligros, cuatro pasos por misión, modo espectador), docs/equipo/EMPEZAR_AQUI.md (plataforma y módulos),
docs/nasa-submission/DATA_SOURCES.md (fuentes) y AI_USE.md.
"""

OBJETIVOS = [
    (True, "Objetivo: convertir los datos de la NASA en un videojuego que enseñe a leer cómo cambia la Tierra: qué "
           "cambia, dónde, cuánto y si el cambio es significativo (reto «Be An Earth System Trend Detective!»)."),
    (True, "Alcance: 57 lugares reales de los siete continentes, con huaicos, inundaciones, olas de calor, erupciones "
           "y avalanchas. Se juega en el navegador y está pensado para escolares, universitarios, familias y "
           "autoridades."),
    (True, "Para qué ayuda: que la gente reconozca las señales antes del desastre, sepa qué hacer y avise a tiempo; "
           "y que quien decide una obra tenga la misma evidencia, comprobada con una segunda fuente."),
]

IDEA = [
    (False, "TERRA 2045 · El último viaje es un videojuego web en 3D. Año 2045: la humanidad perdió la Tierra porque "
            "no supo cuidarla. Tú viajas a 2026 para cambiar lo que viene. En cada misión llegas "
            "a un lugar real, lees su tendencia con datos de la NASA desde 2001, la compruebas con una segunda fuente, "
            "decides con recursos limitados y avisas al pueblo antes del huaico, la inundación o la avalancha. Cada "
            "lugar a salvo cura un poco la Tierra de 2045."),
    (False, "También se entra como Espectador, para consultar los mismos datos sin jugar. Detrás trabaja la plataforma "
            "Los Causas Espaciales, que lleva esa evidencia a decisiones de inversión con puntaje, VAN e informe en "
            "PDF. Nuestra ventaja es la confianza: si dos fuentes no coinciden, se dice."),
]

RECURSOS = [
    (True, "Prototipo jugable: 57 misiones, mundo 3D sobre relieve real, cinco tipos de desastre, tres finales y "
           "cinemáticas en español e inglés; modo espectador y plataforma."),
    (True, "Datos abiertos y sin costo de licencia: NASA (POWER, GPM IMERG, MODIS, GIBS, NASADEM y EONET), NASA "
           "SERVIR, Copernicus y Comisión Europea (ERA5, relieve), ESA WorldCover, GEOGLOWS y GDACS."),
    (True, "Capas oficiales del Perú: IGN, CENEPRED, ANA, SERNANP, MINAM, INGEMMET, Ministerio de Cultura y COES."),
    (True, "Tecnología: Next.js, MapLibre, three.js, Python (FastAPI) y Docker; más de 300 pruebas automáticas; "
           "desarrollo asistido por IA (Claude Code y Codex)."),
]

SECCIONES = {"Texto Objetivos": OBJETIVOS, "Texto Idea principal": IDEA, "Texto Recursos": RECURSOS}
