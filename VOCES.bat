@echo off
rem Voces de los videos de TERRA 2045 con las voces neuronales de Microsoft Edge (necesita internet). Todo queda en esta carpeta (D:).
cd /d "%~dp0"
set "UV_CACHE_DIR=%~dp0.herramientas\uv-cache"
set "TEMP=%~dp0.herramientas\tmp"
set "TMP=%~dp0.herramientas\tmp"
if not exist "%TEMP%" mkdir "%TEMP%"
"%~dp0.herramientas\uv\uv.exe" pip install edge-tts --python "%~dp0.venv\Scripts\python.exe"
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\video\voces_edge.py"
echo.
echo Listo: voces en videos\voz\es y videos\voz\en
pause
