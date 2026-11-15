@echo off
rem Voces en ingles de los videos de TERRA 2045 con Piper. Todo queda en .herramientas (D:).
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\video\voces_ingles.ps1"
pause
