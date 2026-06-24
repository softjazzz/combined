param(
  [switch]$FrontendOnly,
  [switch]$BackendOnly,
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8001,
  [string]$FrontendHost = "0.0.0.0",
  [string]$BackendHost = "0.0.0.0",
  [string]$HealthCheckHost = "127.0.0.1",
  [string]$PythonExe = "C:\Python310\python.exe",
  [switch]$WatchFrontend
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$recoverScript = Join-Path $root "scripts\dev-recover.ps1"
$watchdogScript = Join-Path $root "scripts\dev-watchdog.ps1"

if (-not (Test-Path -LiteralPath $recoverScript)) {
  throw "recover script not found: $recoverScript"
}

$recoverArgs = @(
  "-ExecutionPolicy", "Bypass",
  "-File", $recoverScript,
  "-FrontendPort", "$FrontendPort",
  "-BackendPort", "$BackendPort",
  "-FrontendHost", $FrontendHost,
  "-BackendHost", $BackendHost,
  "-HealthCheckHost", $HealthCheckHost,
  "-PythonExe", $PythonExe
)

if ($FrontendOnly) { $recoverArgs += "-FrontendOnly" }
if ($BackendOnly) { $recoverArgs += "-BackendOnly" }

Write-Host "===== Recover frontend/backend =====" -ForegroundColor Cyan
& powershell @recoverArgs

if ($WatchFrontend) {
  if (-not (Test-Path -LiteralPath $watchdogScript)) {
    throw "watchdog script not found: $watchdogScript"
  }
  Write-Host ""
  Write-Host "===== Start frontend watchdog =====" -ForegroundColor Cyan
  Start-Process -FilePath "powershell" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $watchdogScript,
    "-FrontendPort", "$FrontendPort",
    "-BackendPort", "$BackendPort",
    "-FrontendHost", $FrontendHost,
    "-BackendHost", $BackendHost,
    "-HealthCheckHost", $HealthCheckHost,
    "-PythonExe", $PythonExe
  ) -WorkingDirectory $root -WindowStyle Normal | Out-Null

  Write-Host "watchdog started: auto-recover frontend when health checks fail." -ForegroundColor Green
}
