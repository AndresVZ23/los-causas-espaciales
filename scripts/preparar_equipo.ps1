# Prepara este equipo para TERRA 2045 (ADR-050) sin instalar nada en C: todo queda dentro del repositorio, en D:.
#
#   Doble clic en PREPARAR.bat (en la raíz del repositorio), o:
#   powershell -ExecutionPolicy Bypass -File scripts\preparar_equipo.ps1
#
# Qué hace, en orden (cada paso escribe su registro en .herramientas\registros\):
#   1. Descarga uv (astral-sh, GitHub oficial) en .herramientas\uv. uv instala Python 3.12 en .herramientas\python
#      y crea el entorno .venv con backend\requirements.txt. Cachés de uv, pip y npm, y temporales: en .herramientas.
#   2. Descarga para los videos: NASA Blue Marble y Black Marble (GIBS, dominio público) y la música de Kevin MacLeod
#      (incompetech.com, CC BY 4.0) en videos\assets y videos\musica.
#   3. Genera las voces sintéticas de los videos con las voces de Windows (scripts\video\voces.ps1).
#   4. Instala las dependencias del frontend (frontend\node_modules) con la caché de npm en .herramientas.
#   5. Enciende la API (puerto 8000) en otra ventana, construye la misión de Lima y su terreno, y corre la puerta común
#      (pytest, build, audit) y la comprobación del juego (game_logic.cjs).
#   6. Enciende la web en modo desarrollo (puerto 3100) en otra ventana.
# Requiere Node.js (ya instalado en este equipo) e internet. No usa Docker.

$ErrorActionPreference = "Continue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Tools = Join-Path $Root ".herramientas"
$Logs = Join-Path $Tools "registros"
New-Item -ItemType Directory -Force -Path $Tools, $Logs, (Join-Path $Tools "tmp") | Out-Null
Set-Location $Root

# Todo lo que estas herramientas guardan va a D:, dentro del repositorio.
$env:UV_CACHE_DIR = Join-Path $Tools "uv-cache"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Tools "python"
$env:UV_TOOL_DIR = Join-Path $Tools "uv-tools"
$env:PIP_CACHE_DIR = Join-Path $Tools "pip-cache"
$env:npm_config_cache = Join-Path $Tools "npm-cache"
$env:TEMP = Join-Path $Tools "tmp"
$env:TMP = $env:TEMP
$env:PYTHONUTF8 = "1"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"

function Step($name) { Write-Host ""; Write-Host "=== $name ===" -ForegroundColor Cyan }
function Log($name) { Join-Path $Logs "$name.txt" }

# --- 1. Python 3.12 y el entorno del backend, con uv -------------------------------------------------------------
Step "1/6 · Python y backend (en $Tools)"
$uv = Join-Path $Tools "uv\uv.exe"
if (-not (Test-Path $uv)) {
  $zip = Join-Path $Tools "uv.zip"
  Invoke-WebRequest "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" -OutFile $zip
  Expand-Archive $zip -DestinationPath (Join-Path $Tools "uv") -Force
  Remove-Item $zip
}
& $uv venv .venv --python 3.12 --allow-existing *>&1 | Tee-Object (Log "1-python")
& $uv pip install -r backend\requirements.txt --python .venv\Scripts\python.exe *>&1 | Tee-Object -Append (Log "1-python")
$py = Join-Path $Root ".venv\Scripts\python.exe"

# --- 2. Imágenes de NASA y música para los videos ----------------------------------------------------------------
Step "2/6 · Imágenes de NASA y música"
$assets = Join-Path $Root "videos\assets"; $music = Join-Path $Root "videos\musica"
New-Item -ItemType Directory -Force -Path $assets, $music | Out-Null
$gibs = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&CRS=EPSG:4326&BBOX=-90,-180,90,180&WIDTH=4096&HEIGHT=2048"
$images = @{ "bluemarble.jpg" = "$gibs&LAYERS=BlueMarble_NextGeneration&FORMAT=image/jpeg"; "blackmarble.jpg" = "$gibs&LAYERS=VIIRS_Black_Marble&FORMAT=image/jpeg" }
foreach ($name in $images.Keys) {
  $target = Join-Path $assets $name
  if (-not (Test-Path $target)) { try { Invoke-WebRequest $images[$name] -OutFile $target; Write-Host "  $name" } catch { Write-Host "  no se pudo bajar $name : $_" } }
}
$guion = Get-Content (Join-Path $Root "scripts\video\guion.json") -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($title in $guion.music) {
  $target = Join-Path $music "$title.mp3"
  if (-not (Test-Path $target)) { try { Invoke-WebRequest ("https://incompetech.com/music/royalty-free/mp3-royaltyfree/" + [Uri]::EscapeDataString($title) + ".mp3") -OutFile $target; Write-Host "  $title" } catch { Write-Host "  no se pudo bajar $title : $_" } }
}
Get-ChildItem $assets, $music | Select-Object Name, Length | Format-Table | Out-String | Set-Content (Log "2-recursos")

# --- 3. Voces sintéticas -----------------------------------------------------------------------------------------
Step "3/6 · Voces sintéticas de Windows"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\video\voces.ps1") -Root $Root *>&1 | Tee-Object (Log "3-voces")

# --- 4. Frontend -------------------------------------------------------------------------------------------------
Step "4/6 · Dependencias del frontend"
Push-Location frontend
& npm.cmd install *>&1 | Tee-Object (Log "4-npm")
Pop-Location

# --- 5. API, misión de Lima y puerta común -----------------------------------------------------------------------
Step "5/6 · API, misión de Lima y comprobaciones"
$api = Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--port", "8000" -WorkingDirectory $Root -PassThru -WindowStyle Minimized
$ready = $false
foreach ($i in 1..60) { Start-Sleep 2; try { Invoke-WebRequest "http://localhost:8000/docs" -UseBasicParsing -TimeoutSec 3 | Out-Null; $ready = $true; break } catch {} }
if ($ready) {
  & $py scripts\missions\build_missions.py lima *>&1 | Tee-Object (Log "5-lima")
  & $py scripts\missions\build_terrain.py lima *>&1 | Tee-Object -Append (Log "5-lima")
} else { "La API no respondió en el puerto 8000." | Tee-Object (Log "5-lima") }
& $py -m pytest backend\tests -q *>&1 | Tee-Object (Log "5-pytest")
Push-Location frontend
& npm.cmd run build *>&1 | Tee-Object (Log "5-build")
& npm.cmd audit --omit=dev *>&1 | Tee-Object (Log "5-audit")
Pop-Location
& node scripts\qa\game_logic.cjs *>&1 | Tee-Object (Log "5-game-logic")

# --- 6. Web en modo desarrollo -----------------------------------------------------------------------------------
Step "6/6 · Web en http://localhost:3100"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$Root\frontend`" && set npm_config_cache=$($env:npm_config_cache) && npm.cmd run dev" -WorkingDirectory (Join-Path $Root "frontend")
"Terminado: $(Get-Date -Format s)" | Tee-Object (Log "listo")
Write-Host ""
Write-Host "Listo. Quedan abiertas la API (puerto 8000) y la web (puerto 3100). Avísale a Claude." -ForegroundColor Green
