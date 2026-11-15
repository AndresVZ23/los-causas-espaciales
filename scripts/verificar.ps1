# Puerta común antes de subir cambios (CLAUDE.md, AGENTS.md): pytest, tipos, build, audit y la comprobación del juego.
# Lo lanza VERIFICAR.bat. Todo queda en D: (cachés y temporales en .herramientas). Los resultados quedan en
# .herramientas\registros\verificar-*.txt (UTF-8) y un resumen en verificar-resumen.txt.
$ErrorActionPreference = "Continue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Tools = Join-Path $Root ".herramientas"
$Logs = Join-Path $Tools "registros"
New-Item -ItemType Directory -Force -Path $Logs, (Join-Path $Tools "tmp") | Out-Null
Set-Location $Root
$env:PIP_CACHE_DIR = Join-Path $Tools "pip-cache"
$env:npm_config_cache = Join-Path $Tools "npm-cache"
$env:TEMP = Join-Path $Tools "tmp"
$env:TMP = $env:TEMP
$env:PYTHONUTF8 = "1"
$py = Join-Path $Root ".venv\Scripts\python.exe"
$summary = @()

function Run($name, [scriptblock]$block) {
  Write-Host ""; Write-Host "=== $name ===" -ForegroundColor Cyan
  $log = Join-Path $Logs "verificar-$name.txt"
  & $block *>&1 | Tee-Object -Variable out | Out-Host
  $out | Out-String | Set-Content -Path $log -Encoding UTF8
  $code = $LASTEXITCODE
  $script:summary += "$name : codigo $code"
}

Run "pytest" { & $py -m pytest backend\tests -q }
Push-Location frontend
Run "tipos" { & npx.cmd tsc --noEmit -p . }
Run "build" { & npm.cmd run build }
Run "audit" { & npm.cmd audit --omit=dev }
Pop-Location
Run "juego" { & node scripts\qa\game_logic.cjs }
$summary += "Terminado: $(Get-Date -Format s)"
$summary | Set-Content -Path (Join-Path $Logs "verificar-resumen.txt") -Encoding UTF8
Write-Host ""; $summary | ForEach-Object { Write-Host $_ }
