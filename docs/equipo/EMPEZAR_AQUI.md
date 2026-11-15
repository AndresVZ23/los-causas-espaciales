# Empezar aquí

Guía para el equipo de **Los Causas Espaciales** (NASA Space Apps 2026, sede Moquegua). Léela antes de tu primer cambio. El estado de cada pieza, lo que falta y lo que se puede agregar están en la **red del proyecto**: abre `docs/equipo/pipeline.html` con doble clic después de clonar. GitHub no muestra HTML, así que hay que abrirlo desde tu copia.

**Entrega final: domingo 15 de noviembre de 2026, 23:59.**

## Qué es

Una plataforma web que convierte datos satelitales de NASA en decisiones de inversión en infraestructura. El usuario elige un sitio, un distrito o dibuja su proyecto. La plataforma:

- mide qué cambió en el clima y el territorio desde 2001;
- prueba si el cambio es estadísticamente significativo;
- **comprueba cada dato con una segunda fuente independiente**;
- termina en un puntaje, un VAN con sensibilidad y un PDF ejecutivo.

Responde al reto «Be An Earth System Trend Detective!». Nuestra diferencia es la confianza: cuando dos fuentes no coinciden, el informe lo dice.

Funciona en cualquier lugar del mundo con las fuentes globales; el detalle oficial (territorios, riesgo, patrimonio) existe solo para el Perú. El botón «Alertas en el mundo» del mapa muestra los eventos con alerta de GDACS y permite analizarlos con un clic. En ese mismo panel, «Zonas para recorrer» abre una maqueta en bloques de dos lugares reales (Moquegua y el volcán Taal) que se recorre a pie, con lo que la plataforma sabe de cada uno; también se entra directo por `http://localhost:3100/zona/moquegua` y `/zona/taal`.

| Módulo | Estado | Qué hace |
|---|---|---|
| 1 · Clima | Funcional | Tendencias NASA POWER cruzadas con ERA5; extremos de lluvia con IMERG y CHIRPS. |
| 2 · Energía | Solar, eólica e hidroeléctrica funcionales | Solar: irradiancia CERES contra ERA5. Eólica: viento horario NASA con el nivel del Global Wind Atlas. Hidroeléctrica de pasada: caudal GloFAS contra GEOGLOWS y salto NASADEM contra Copernicus. Eólica e hidro validadas contra la producción real del COES. |
| 3 · Amenazas | Funcional | Lluvia extrema, CENEPRED frente a los deslizamientos de NASA, ANA e INGEMMET. |
| 4 · Ambiente | Funcional | Vegetación MODIS frente a ESA WorldCover; agua, ecosistemas y áreas protegidas. |
| 5 · Territorio | Patrimonio funcional | Patrimonio del Ministerio de Cultura. **Comunidades y conflictos pendientes.** |
| 6 · Infraestructura | Piloto vial funcional | Corredor por tramos: lluvia, capas oficiales y VAN de mitigación. |
| 7 · Inversión | Piloto inmobiliario funcional | Terrenos o territorios IGN: lluvia, relieve, capas y VAN. |

## TERRA 2045 en la portada (14-nov)

Desde ADR-050 la portada (`http://localhost:3100`) es el juego TERRA 2045 y la consola técnica está en `http://localhost:3100/plataforma`. En Windows, sin Docker y sin instalar nada en C:, basta un doble clic en `PREPARAR.bat`: deja Python 3.12, `.venv`, las dependencias del frontend y sus cachés dentro de `.herramientas/`, baja los recursos de los videos, genera las voces, construye la misión de Lima, corre la puerta común y enciende la API y la web.

Las cinemáticas (prólogo, viaje, regreso a 2045, tres finales y tráiler) se ven como video dentro del juego desde `frontend/public/cine/` (`<video>_<es|en>.mp4` y `.vtt`). Para rehacerlas: `VOCES.bat` (voces neuronales de Microsoft Edge con `scripts/video/voces_edge.py`; necesita internet), luego `python scripts/video/render.py` (necesita Chrome, ffmpeg con libass y rubberband) y copiar `videos/web/*` a `frontend/public/cine/`. Sin esos archivos el juego muestra la historia en texto. Las voces de Edge (`videos/voz/*.mp3`), la música, las texturas, las grabaciones del juego que usa el tráiler (`videos/captura/`) y los videos finales (`videos/*.mp4`) vienen en el repositorio, así que `render.py` funciona sin volver a generar voces; `VOCES.bat` solo hace falta si cambia una línea del guion. Antes de subir cambios, `VERIFICAR.bat` corre la puerta común (pytest, tipos, build, audit y la comprobación del juego) y deja los resultados en `.herramientas/registros/`.

## Ponerlo en marcha

Necesitas Git, Docker Desktop y, si quieres correrlo sin Docker, Python 3.12 y Node 22.

```powershell
git clone https://github.com/ChristianVenegas7/los-causas-espaciales.git
cd los-causas-espaciales
Copy-Item .env.example .env
docker compose -p los-causas-espaciales up -d --build
```

Luego abre estas direcciones:

- Aplicación: http://localhost:3100
- API y su documentación: http://localhost:8000/docs

Si te equivocas de puerto, ojo: el `3000` es de otro proyecto (MyFix), no lo uses.

**Credenciales.** La app funciona sin ellas: lo que no puede consultar lo declara como brecha.

- **`EARTHDATA_TOKEN`:** cada uno crea **su propio** token en https://urs.earthdata.nasa.gov (Profile → Generate Token). En ese mismo perfil autoriza la aplicación *LP DAAC*. Sin token, el relieve NASADEM queda en `METADATA_ONLY` y el sistema usa Copernicus como respaldo.
- **AppEEARS:** usa `EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD`. Es opcional.
- **Reglas:** nunca subas el `.env` (ya está en `.gitignore`) ni pegues un token en un chat, un commit o una captura.

**La primera consulta es lenta.** Cada fuente se descarga una vez y queda en caché (`backend/data/cache/`). La primera ejecución de un sitio nuevo puede tardar 1–2 minutos; las siguientes, segundos.

**CENEPRED saldrá «No disponible» en tu máquina, y no es un error tuyo.** Desde el 10 de noviembre su servicio exige un token. La aplicación muestra la última copia válida, con su fecha, solo donde ya se había consultado antes del cierre; esas copias están en la máquina de Christian (ADR-044).

**Sin Docker:**

```powershell
python --version  # debe responder 3.12.x; si abre Microsoft Store o no responde, instala Python 3.12 desde python.org y desactiva el alias de ejecución de Windows
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
# en otra terminal
cd frontend; npm.cmd install; npm.cmd run dev
```

**Puertos temporales para trabajar en paralelo.** El frontend lee la API desde `BACKEND_API_URL`; cambiar solo el puerto de Next deja sus rutas internas apuntando al 8000. Este ejemplo evita el stack compartido de 3100/8000 y también el 3000 de MyFix:

```powershell
# terminal 1, desde la raíz
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8311

# terminal 2, desde frontend
$env:BACKEND_API_URL = "http://127.0.0.1:8311"
$env:API_PUBLIC_URL = "http://127.0.0.1:8311"   # solo para el enlace «OpenAPI» del pie de página
npm.cmd run dev -- --hostname 127.0.0.1 --port 3411
```

Abre `http://127.0.0.1:3411` y `http://127.0.0.1:8311/docs`. Detén ambos procesos con `Ctrl+C` cuando termines. Los números 3411/8311 son ejemplos: usa dos puertos libres y conserva la misma relación en `BACKEND_API_URL`.

> **Red restringida:** durante `npm run dev` o `npm run build`, Next puede no descargar Public Sans e IBM Plex Mono desde Google Fonts. La aplicación continúa con sus fuentes de respaldo, pero el resultado visual no es idéntico. Registra el aviso y repite el QA visual con acceso a `fonts.googleapis.com` y `fonts.gstatic.com` antes de aprobar una entrega.

## Cómo trabajamos

1. **Una rama por persona y tema**, por ejemplo `abel/red-electrica`, `nikol/demo` o `mario/pitch`. Nunca se trabaja sobre `master`.
   ```powershell
   git switch master; git pull
   git switch -c abel/red-electrica
   # ... cambios ...
   git add <archivos>; git commit -m "feat(energia): distancia a la red eléctrica"
   git push -u origin abel/red-electrica
   ```
2. **Pull Request a `master`** en GitHub, con qué cambiaste, cómo lo probaste y capturas si hay pantalla.
3. **Christian revisa y fusiona** después de la puerta común: pruebas, build y QA. Nadie hace push directo a `master`.
4. Si tu cambio toca archivos que otro está editando (sobre todo `frontend/app/_components/workspace.tsx`), avísalo antes por el grupo.

**Puerta común antes del Pull Request.** Las pruebas no salen a internet, porque usan dobles de las fuentes.

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q      # el número crece; ninguna prueba puede fallar
cd frontend; npm.cmd run build; npm.cmd audit --omit=dev
```

## Reglas de oro

Están completas en [AGENTS.md](../../AGENTS.md). Las que no se negocian:

- **Solo datos reales.** Nunca inventes una cifra, una fuente ni un resultado. Si algo no se puede consultar, se declara como `DATA_UNAVAILABLE`.
- **Un faltante nunca es cero.** Cero intersecciones no significa «sin riesgo».
- **Toda cifra lleva su procedencia:** `REAL_DATA`, `CACHED_DATA`, `MODEL_ESTIMATE`, `USER_ASSUMPTION` o `DATA_UNAVAILABLE`.
- **Cada dato nuevo entra con una segunda fuente** que lo compruebe, y lo que aparece al cruzarlas se registra como descubrimiento.
- **Supuestos a la vista.** Precio, CAPEX, tasa, etc. son supuestos editables, nunca datos.
- **Todo en español.** Se dejan en inglés solo los nombres propios y los identificadores técnicos.

## Mapa del código

| Carpeta | Qué hay |
|---|---|
| `backend/app/connectors/` | Una carpeta por proveedor: `nasa/`, `jrc/` (ERA5), `esa/`, `copernicus/` (relieve y caudal GloFAS), `geoglows/`, `gwa/`, `gdacs/` (alertas del mundo), `openmeteo/` (buscador de lugares), `peru/`, `energy/` (COES). Cada conector usa caché y declara su procedencia. |
| `backend/app/sectors/` | Un archivo por módulo (`climate.py`, `solar.py`, `wind.py`, `hydro.py`, `road.py`, `real_estate.py`, `baseline*.py`). Arma el resultado completo. |
| `backend/app/orchestration/` | Piezas comunes: extracción, análisis, contrastes con segundas fuentes y `discoveries.py` (las reglas de los descubrimientos). |
| `backend/app/statistics/`, `finance/`, `scoring/` | Mann–Kendall, Sen y Benjamini–Hochberg; VAN y sensibilidad; puntaje multicriterio. |
| `backend/app/schemas/` | Contratos de datos. `screening.py` es el **contrato común C2** que comparten todos los módulos. |
| `backend/app/reports/` | PDF ejecutivo. |
| `backend/tests/` | Pruebas. `conftest.py` impide que salgan a internet. |
| `frontend/app/_components/` | La consola: `workspace.tsx` (pantalla principal) y un archivo `*-panels.tsx` por módulo. `zone/` es la maqueta en bloques (three.js, se carga solo al entrar). `game/` es el modo jugador de `/jugar`: las reglas de los textos están en `mission-logic.ts` y la historia en `story.ts`. |
| `backend/app/zones/`, `backend/data/zones/`, `scripts/zones/` | Zonas para recorrer: lector de relieve y cobertura, las dos zonas ya construidas y el guion que las arma con resultados reales de la API local. |
| `backend/app/missions/`, `backend/data/missions/`, `scripts/missions/` | Modo jugador: las 56 misiones con su análisis real y sus terrenos. Tras cambiar un texto o una fuente del guion: `python scripts/missions/build_missions.py --textos`. Para revisar los textos del juego sin navegador: `node scripts/qa/game_logic.cjs`. |
| `docs/architecture/DECISION_LOG.md` | Cada decisión importante (ADR-001 a ADR-049). Léela antes de cambiar un método. |
| `docs/nasa-submission/` | Materiales de la entrega: fuentes (`DATA_SOURCES.md`), metodología, arquitectura, pitch y escenarios de demo. |

## Receta: agregar una fuente de datos

Así se integraron ERA5, Copernicus, WorldCover, el Global Wind Atlas, GloFAS y GEOGLOWS.

1. **Verificar la fuente** contra su documentación oficial: producto, versión, unidad, resolución, licencia y cómo marca los faltantes. Hacer una consulta real de prueba.
2. **Conector** en `backend/app/connectors/<proveedor>/`, con timeout, reintentos limitados, caché (`RawPayloadCache`) y procedencia.
3. **Contraste:** qué dato existente comprueba la fuente o qué otra fuente la comprueba a ella, y la regla de «coinciden / difieren» en `orchestration/discoveries.py`.
4. **Pruebas** sin red en `backend/tests/`: caso nominal, faltante y error del proveedor.
5. **Documentar:** una ficha en `DATA_SOURCES.md` y un ADR en `DECISION_LOG.md` con el resultado real medido.

Las decisiones se escriben en español, con fecha, cifra medida y fuente.
