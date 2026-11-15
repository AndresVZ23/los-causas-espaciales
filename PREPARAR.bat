@echo off
rem Prepara este equipo para TERRA 2045: Python, dependencias, voces, recursos de video y la web. Todo queda en esta carpeta (D:).
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\preparar_equipo.ps1"
pause
