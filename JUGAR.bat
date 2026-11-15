@echo off
rem Enciende TERRA 2045 en este equipo: la API (puerto 8000) y la web (puerto 3100), y abre el juego en el navegador.
rem La primera vez hay que correr PREPARAR.bat, que instala Python y las dependencias dentro de esta carpeta.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto falta
if not exist "frontend\node_modules" goto falta
set PYTHONUTF8=1
set npm_config_cache=%~dp0.herramientas\npm-cache

curl.exe -s -o nul http://localhost:8000/docs
if errorlevel 1 start "TERRA 2045 - API (8000)" /min /d "%~dp0" cmd /k .venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
curl.exe -s -o nul http://localhost:3100
if errorlevel 1 start "TERRA 2045 - Web (3100)" /min /d "%~dp0frontend" cmd /k npm.cmd run dev

echo Encendiendo TERRA 2045... la primera carga puede tardar un minuto.
set /a intentos=0
:esperar
set /a intentos+=1
if %intentos% gtr 90 goto abrir
timeout /t 2 /nobreak >nul
curl.exe -s -o nul http://localhost:3100
if errorlevel 1 goto esperar
:abrir
start "" http://localhost:3100
echo Listo: el juego esta en http://localhost:3100
echo Para apagarlo, cierra las ventanas "TERRA 2045 - API" y "TERRA 2045 - Web".
timeout /t 8 >nul
exit /b 0

:falta
echo Este equipo todavia no esta preparado: haz doble clic en PREPARAR.bat primero.
pause
exit /b 1
