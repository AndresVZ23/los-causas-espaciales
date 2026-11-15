# Voces sintéticas de las cinemáticas de TERRA 2045 (ADR-050), con las voces de Windows instaladas en el equipo.
# Lee scripts/video/guion.json y escribe un WAV por línea en videos/voz/es/ y videos/voz/en/, más voces.json con la voz
# usada en cada una. Ejecutar con Windows PowerShell 5.1 (powershell.exe), no con PowerShell 7: usa WinRT.
#
#   powershell -ExecutionPolicy Bypass -File scripts\video\voces.ps1
#
# Primero intenta las voces modernas de Windows (OneCore, WinRT); si no están, usa System.Speech (SAPI).
# El tono de los niños (Mario y Killa) y el filtro de radio se aplican después, al montar (render.py), no aquí.

param([string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path)
$ErrorActionPreference = "Stop"
$guion = Get-Content (Join-Path $Root "scripts\video\guion.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$outRoot = Join-Path $Root "videos\voz"
New-Item -ItemType Directory -Force -Path (Join-Path $outRoot "es"), (Join-Path $outRoot "en") | Out-Null

# Quién habla con qué tipo de voz. Los niños usan una voz femenina que luego se sube de tono.
$roles = @{ narrador = @("male", 0); nikol = @("female", 0); radio = @("female", 0); andres = @("male", 1); viajero = @("female", 1); mario = @("female", 1); killa = @("female", 0) }

function Pick($list, $lang, $gender, $index) {
  $pool = @($list | Where-Object { $_.Lang -like "$lang*" -and $_.Gender -eq $gender })
  if ($pool.Count -eq 0) { $pool = @($list | Where-Object { $_.Lang -like "$lang*" }) }
  if ($pool.Count -eq 0) { return $null }
  # Español: primero las voces de Latinoamérica (es-MX), luego las demás.
  if ($lang -eq "es") { $pool = @($pool | Sort-Object { if ($_.Lang -like "es-MX*") { 0 } elseif ($_.Lang -like "es-US*") { 1 } else { 2 } }) }
  return $pool[[Math]::Min($index, $pool.Count - 1)]
}

$report = @()
$useWinRT = $true
try {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  $null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
  $null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]
  $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  function Await($operation, [Type]$type) { $task = $asTask.MakeGenericMethod($type).Invoke($null, @($operation)); $task.Wait(-1) | Out-Null; $task.Result }
  $synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
  $voices = @([Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | ForEach-Object { [pscustomobject]@{ Name = $_.DisplayName; Lang = $_.Language; Gender = $_.Gender.ToString().ToLower(); Ref = $_ } })
  if ($voices.Count -eq 0) { throw "sin voces OneCore" }
} catch {
  $useWinRT = $false
  Add-Type -AssemblyName System.Speech
  $sapi = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $voices = @($sapi.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { [pscustomobject]@{ Name = $_.VoiceInfo.Name; Lang = $_.VoiceInfo.Culture.Name; Gender = $_.VoiceInfo.Gender.ToString().ToLower(); Ref = $_.VoiceInfo } })
}
Write-Host ("Motor: " + $(if ($useWinRT) { "OneCore (WinRT)" } else { "System.Speech (SAPI)" }))
Write-Host ("Voces instaladas: " + (($voices | ForEach-Object { "$($_.Name) [$($_.Lang), $($_.Gender)]" }) -join "; "))

foreach ($line in $guion.lines) {
  foreach ($lang in @("es", "en")) {
    $role = $roles[$line.who]; if (-not $role) { $role = @("female", 0) }
    $voice = Pick $voices $lang $role[0] $role[1]
    if (-not $voice) { Write-Host "  sin voz para $lang"; continue }
    $text = if ($lang -eq "es") { $line.es } else { $line.en }
    $file = Join-Path $outRoot "$lang\$($line.id).wav"
    if ($useWinRT) {
      $synth.Voice = $voice.Ref
      $stream = Await ($synth.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
      $reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
      $size = [uint32]$stream.Size
      $null = Await ($reader.LoadAsync($size)) ([uint32])
      $bytes = New-Object byte[] $size
      $reader.ReadBytes($bytes)
      [IO.File]::WriteAllBytes($file, $bytes)
      $reader.Dispose(); $stream.Dispose()
    } else {
      $sapi.SelectVoice($voice.Name)
      $sapi.SetOutputToWaveFile($file)
      $sapi.Speak($text)
      $sapi.SetOutputToNull()
    }
    $report += [pscustomobject]@{ id = $line.id; lang = $lang; who = $line.who; voice = $voice.Name; voice_lang = $voice.Lang }
  }
  Write-Host "  $($line.id) ($($line.who))"
}
$report | ConvertTo-Json | Set-Content -Path (Join-Path $outRoot "voces.json") -Encoding UTF8
Write-Host ("Listo: " + $report.Count + " archivos en " + $outRoot)
