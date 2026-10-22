# Scripts de QA

Herramientas de verificación de Claude Code. Las evidencias que generan (capturas, PDF y respuestas) van a `.claude-qa/`, que git ignora.

Instalación única: `cd scripts\qa` y luego `npm.cmd install` (Playwright 1.61.1 usa el Chromium ya instalado en el equipo).

| Script | Qué verifica | Uso |
|---|---|---|
| `shots.cjs` | Capturas antes y después de ejecutar, a 1440/768/390 px; desborde horizontal y errores de consola | `node scripts\qa\shots.cjs .claude-qa\capturas\<corrida> .verdict` |
| `interact.cjs` | Cambio de variable (dominio Y), edición de supuestos y aviso de VAN desactualizado | `node scripts\qa\interact.cjs .claude-qa\capturas\<corrida>` |
| `pipeline.cjs` | Inspector de etapas, enlaces etapa ↔ pregunta NASA y exportación | `node scripts\qa\pipeline.cjs .claude-qa\capturas\<corrida>` |
| `pdf_e2e.cjs` | Descarga real del PDF ejecutivo a 1440 y 390 px y etapa 9 completada | `node scripts\qa\pdf_e2e.cjs .claude-qa\pdf` |
| `bench_power.py` | Tiempo de extracción NASA POWER (fría y con caché) y parseo | `.venv\Scripts\python.exe scripts\qa\bench_power.py` |
| `token_check.py` | Fechas del token Earthdata y lectura autenticada de 1 byte, sin imprimir el token | `.venv\Scripts\python.exe scripts\qa\token_check.py` |
| `hr_real.py` | Contraste de Hamed–Rao con `pymannkendall` sobre una respuesta real (requiere instalar esa librería aparte) | `python scripts\qa\hr_real.py .claude-qa\datos\screening.json` |

Variable `QA_BASE_URL`: URL de la consola (por defecto `http://localhost:3100`).
