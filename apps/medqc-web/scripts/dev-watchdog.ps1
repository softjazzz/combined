param(
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8001,
  [string]$PythonExe = "C:\Python310\python.exe",
  [int]$IntervalSec = 8,
  [int]$FailThreshold = 2
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$recoverScript = Join-Path $PSScriptRoot "dev-recover.ps1"

function Test-Endpoint([string]$url, [int]$timeoutSec = 8) {
  try {
    $res = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec
    return ($res.StatusCode -ge 200 -and $res.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Test-FrontendHealthy([int]$port) {
  $base = "http://127.0.0.1:$port"
  if (-not (Test-Endpoint "$base/" 8)) { return $false }
  if (-not (Test-Endpoint "$base/@vite/client" 8)) { return $false }
  if (-not (Test-Endpoint "$base/src/main.ts?t=$([DateTimeOffset]::Now.ToUnixTimeMilliseconds())" 20)) { return $false }
  return $true
}

if (-not (Test-Path -LiteralPath $recoverScript)) {
  throw "recover script not found: $recoverScript"
}

Write-Host "frontend watchdog: port=$FrontendPort interval=${IntervalSec}s threshold=$FailThreshold" -ForegroundColor Cyan
$failedCount = 0

while ($true) {
  $ok = Test-FrontendHealthy $FrontendPort
  if ($ok) {
    if ($failedCount -gt 0) {
      Write-Host "frontend healthy again, fail counter reset." -ForegroundColor Green
    }
    $failedCount = 0
  } else {
    $failedCount++
    Write-Warning "frontend health failed ($failedCount/$FailThreshold)"
    if ($failedCount -ge $FailThreshold) {
      Write-Host "auto-recover triggered: restarting frontend..." -ForegroundColor Yellow
      & powershell -ExecutionPolicy Bypass -File $recoverScript `
        -FrontendOnly `
        -FrontendPort $FrontendPort `
        -BackendPort $BackendPort `
        -PythonExe $PythonExe
      $failedCount = 0
    }
  }
  Start-Sleep -Seconds $IntervalSec
}
