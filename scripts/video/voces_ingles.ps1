# Voces en inglés de las cinemáticas de TERRA 2045 (ADR-050) con Piper, un motor de voz neuronal libre que corre sin
# conexión. Windows de este equipo solo trae voces en español, y agregar voces en inglés instala paquetes en C:.
# Todo queda en .herramientas\piper (D:). Voces de Piper (rhasspy/piper-voices, MIT) entrenadas con datos de dominio
# público según su ficha: john (narrador), ljspeech (Nikol y radio), bryce (Andrés), kristin (viajero); Mario y Killa
# usan kristin y ljspeech con el tono subido al montar (render.py).
#
#   powershell -ExecutionPolicy Bypass -File scripts\video\voces_ingles.ps1

param([string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path)
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"
$tools = Join-Path $Root ".herramientas"
$piperDir = Join-Path $tools "piper"
$voiceDir = Join-Path $tools "piper-voices"
$tmp = Join-Path $tools "tmp"
New-Item -ItemType Directory -Force -Path $piperDir, $voiceDir, $tmp | Out-Null
$exe = Join-Path $piperDir "piper\piper.exe"
if (-not (Test-Path $exe)) {
  $zip = Join-Path $tools "piper.zip"
  Invoke-WebRequest "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip" -OutFile $zip
  Expand-Archive $zip -DestinationPath $piperDir -Force
  Remove-Item $zip
}
$voices = @{ john = "john/medium/en_US-john-medium"; ljspeech = "ljspeech/high/en_US-ljspeech-high"; bryce = "bryce/medium/en_US-bryce-medium"; kristin = "kristin/medium/en_US-kristin-medium" }
foreach ($name in $voices.Keys) {
  foreach ($ext in @(".onnx", ".onnx.json")) {
    $file = Join-Path $voiceDir ((Split-Path $voices[$name] -Leaf) + $ext)
    if (-not (Test-Path $file)) { Invoke-WebRequest ("https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/" + $voices[$name] + $ext) -OutFile $file }
  }
}
$roles = @{ narrador = "john"; nikol = "ljspeech"; radio = "ljspeech"; andres = "bryce"; viajero = "kristin"; mario = "ljspeech"; killa = "kristin" }
$guion = Get-Content (Join-Path $Root "scripts\video\guion.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$out = Join-Path $Root "videos\voz\en"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$report = @()
foreach ($line in $guion.lines) {
  $voice = $roles[$line.who]; if (-not $voice) { $voice = "ljspeech" }
  $model = Join-Path $voiceDir ((Split-Path $voices[$voice] -Leaf) + ".onnx")
  $text = $line.en -replace [char]0x2026, "..." -replace [char]0x2019, "'" -replace [char]0x201C, '"' -replace [char]0x201D, '"'
  $textFile = Join-Path $tmp "linea.txt"
  [IO.File]::WriteAllText($textFile, $text, (New-Object System.Text.UTF8Encoding($false)))
  $wav = Join-Path $out "$($line.id).wav"
  $piperArgs = @("--model", "`"$model`"", "--length_scale", "1.06", "--sentence_silence", "0.25", "--output_file", "`"$wav`"")
  Start-Process -FilePath $exe -ArgumentList $piperArgs -RedirectStandardInput $textFile -RedirectStandardError (Join-Path $tmp "piper.err") -NoNewWindow -Wait
  $report += [pscustomobject]@{ id = $line.id; lang = "en"; who = $line.who; voice = "piper " + $voice }
  Write-Host "  $($line.id) ($($line.who), $voice)"
}
$report | ConvertTo-Json | Set-Content -Path (Join-Path $Root "videos\voz\voces_en.json") -Encoding UTF8
Write-Host ("Listo: " + $report.Count + " voces en ingles en " + $out) -ForegroundColor Green
