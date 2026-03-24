param(
  [ValidateSet("dist", "preview", "dev")]
  [string]$FrontendMode = "dist",
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8001,
  [string]$PythonExe = "C:\Python310\python.exe",
  [switch]$BackendReload,
  [switch]$NoKill,
  [switch]$NoFrontendFallback
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backendRoot = Join-Path $root "backend"
$tmpDir = Join-Path $root ".tmp"
$frontendLog = Join-Path $tmpDir "frontend-$FrontendMode-$FrontendPort.log"
$frontendErrLog = Join-Path $tmpDir "frontend-$FrontendMode-$FrontendPort.err.log"
$backendLog = Join-Path $tmpDir "backend-$BackendPort.log"
$backendErrLog = Join-Path $tmpDir "backend-$BackendPort.err.log"

function Write-Step([string]$msg) {
  Write-Host "==> $msg" -ForegroundColor Cyan
}

function Get-PortPids([int]$port) {
  $lines = netstat -ano -p tcp | Select-String "^\s*TCP\s+"
  $pidList = @()
  foreach ($line in $lines) {
    $parts = ($line.ToString() -split "\s+") | Where-Object { $_ -ne "" }
    if ($parts.Length -ge 5) {
      $localEndpoint = $parts[1]
      if ($localEndpoint -notmatch ":$port$") { continue }
      $portPid = $parts[-1]
      if ($portPid -match "^\d+$" -and $portPid -ne "0") {
        $pidList += [int]$portPid
      }
    }
  }
  return $pidList | Sort-Object -Unique
}

function Stop-PortProcess([int]$port) {
  $pids = Get-PortPids $port
  if (-not $pids -or $pids.Count -eq 0) {
    Write-Host "  port ${port}: no process"
    return
  }
  foreach ($targetPid in $pids) {
    Write-Host "  kill pid=$targetPid on port $port"
    taskkill /PID $targetPid /F | Out-Null
  }
}

function Wait-HttpOk([string]$url, [int]$timeoutSec = 30) {
  $deadline = (Get-Date).AddSeconds($timeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
        return $true
      }
    } catch {}
    Start-Sleep -Milliseconds 700
  }
  return $false
}

function Resolve-PythonExecutable([string]$preferred) {
  if ($preferred -and (Test-Path -LiteralPath $preferred)) {
    return $preferred
  }
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    return $python.Source
  }
  return $null
}

function Start-FrontendDistViaPython([string]$projectRoot, [int]$port, [string]$pythonExe, [string]$log, [string]$errLog) {
  $entry = Join-Path $projectRoot "scripts\serve_dist_spa.py"
  $distIndex = Join-Path $projectRoot "dist\index.html"
  if (-not (Test-Path -LiteralPath $entry)) {
    Write-Warning "  dist fallback script missing: $entry"
    return $false
  }
  if (-not (Test-Path -LiteralPath $distIndex)) {
    Write-Warning "  dist/index.html missing. Please build once before fallback."
    return $false
  }
  $resolvedPython = Resolve-PythonExecutable $pythonExe
  if (-not $resolvedPython) {
    Write-Warning "  python executable not found for dist fallback."
    return $false
  }

  Start-Process -FilePath $resolvedPython `
    -ArgumentList "scripts/serve_dist_spa.py --host 127.0.0.1 --port $port --dir dist" `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $log `
    -RedirectStandardError $errLog | Out-Null

  if (Wait-HttpOk "http://127.0.0.1:$port/" 20) {
    Write-Host "  frontend ok (dist-python): http://127.0.0.1:$port/" -ForegroundColor Green
    return $true
  }
  return $false
}

if (-not (Test-Path -LiteralPath $tmpDir)) {
  New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
}

if (-not $NoKill) {
  Write-Step "Stop stale listeners"
  Stop-PortProcess $FrontendPort
  Stop-PortProcess $BackendPort
}

Write-Step "Start backend ($BackendPort)"
if (-not (Test-Path -LiteralPath $PythonExe)) {
  $resolvedPython = (Get-Command python -ErrorAction SilentlyContinue)
  if (-not $resolvedPython) {
    throw "Python executable not found. Set -PythonExe explicitly."
  }
  $PythonExe = $resolvedPython.Source
}

$backendArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort", "--timeout-keep-alive", "5")
if ($BackendReload) {
  $backendArgs += @("--reload", "--reload-dir", "app", "--reload-exclude=*.log", "--reload-exclude=data/*", "--reload-exclude=downloads/*")
}

if (-not (Wait-HttpOk "http://127.0.0.1:$BackendPort/docs" 2)) {
  if (Test-Path -LiteralPath $backendLog) { Remove-Item -LiteralPath $backendLog -Force }
  if (Test-Path -LiteralPath $backendErrLog) { Remove-Item -LiteralPath $backendErrLog -Force }

  Start-Process -FilePath $PythonExe `
    -ArgumentList $backendArgs `
    -WorkingDirectory $backendRoot `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrLog | Out-Null
} else {
  Write-Host "  backend already running on $BackendPort, skip start"
}

if (-not (Wait-HttpOk "http://127.0.0.1:$BackendPort/docs" 40)) {
  Write-Host "backend failed to become healthy: http://127.0.0.1:$BackendPort/docs" -ForegroundColor Red
  Write-Host "check logs: $backendLog / $backendErrLog" -ForegroundColor Yellow
  exit 1
}
Write-Host "  backend ok: http://127.0.0.1:$BackendPort/docs" -ForegroundColor Green

Write-Step "Start frontend ($FrontendMode, $FrontendPort)"
if (Test-Path -LiteralPath $frontendLog) { Remove-Item -LiteralPath $frontendLog -Force }
if (Test-Path -LiteralPath $frontendErrLog) { Remove-Item -LiteralPath $frontendErrLog -Force }

if ($FrontendMode -eq "dist") {
  if (-not (Wait-HttpOk "http://127.0.0.1:$FrontendPort/" 2)) {
    Start-FrontendDistViaPython $root $FrontendPort $PythonExe $frontendLog $frontendErrLog | Out-Null
  } else {
    Write-Host "  frontend already running on $FrontendPort, skip start"
  }
} elseif ($FrontendMode -eq "preview") {
  $frontendArgs = @("run", "preview", "--", "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort")
} else {
  $frontendArgs = @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort")
}

if ($FrontendMode -ne "dist") {
  if (-not (Wait-HttpOk "http://127.0.0.1:$FrontendPort/" 2)) {
    Start-Process -FilePath "npm.cmd" `
      -ArgumentList $frontendArgs `
      -WorkingDirectory $root `
      -RedirectStandardOutput $frontendLog `
      -RedirectStandardError $frontendErrLog | Out-Null
  } else {
    Write-Host "  frontend already running on $FrontendPort, skip start"
  }
}

if (-not (Wait-HttpOk "http://127.0.0.1:$FrontendPort/" 40)) {
  $fallbackTriggered = $false
  if (-not $NoFrontendFallback -and $FrontendMode -ne "dist") {
    $needFallback = $true
    try {
      if (Test-Path -LiteralPath $frontendErrLog) {
        $errText = Get-Content -Path $frontendErrLog -Raw -ErrorAction SilentlyContinue
        if ($errText -and ($errText -match "spawn EPERM" -or $errText -match "vite:esbuild")) {
          $needFallback = $true
        }
      }
    } catch {}
    if ($needFallback) {
      Write-Warning "frontend unstable. fallback to dist-python..."
      Stop-PortProcess $FrontendPort
      $fallbackTriggered = Start-FrontendDistViaPython $root $FrontendPort $PythonExe $frontendLog $frontendErrLog
    }
  }
  if (-not $fallbackTriggered) {
    Write-Host "frontend failed to become healthy: http://127.0.0.1:$FrontendPort/" -ForegroundColor Red
    Write-Host "check log: $frontendLog" -ForegroundColor Yellow
    Write-Host "check err: $frontendErrLog" -ForegroundColor Yellow
    exit 1
  }
}
if ($FrontendMode -ne "dist") {
  Write-Host "  frontend ok: http://127.0.0.1:$FrontendPort/" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
Write-Host "frontend log: $frontendLog"
Write-Host "frontend err: $frontendErrLog"
Write-Host "backend  log: $backendLog"
Write-Host "backend err: $backendErrLog"
