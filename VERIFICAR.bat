@echo off
rem Puerta comun antes de subir cambios: pytest, tipos, build, audit y comprobacion del juego. Todo en D:.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\verificar.ps1"
pause
