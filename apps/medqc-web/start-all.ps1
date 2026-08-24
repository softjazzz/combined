param(
  [ValidateSet("dist", "preview", "dev")]
  [string]$FrontendMode = "dist",
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8001,
  [string]$FrontendHost = "0.0.0.0",
  [string]$BackendHost = "0.0.0.0",
  [string]$HealthCheckHost = "127.0.0.1",
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
$frontendApiTarget = "http://${HealthCheckHost}:$BackendPort"
$frontendModeExplicit = $PSBoundParameters.ContainsKey("FrontendMode")

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

function Test-HttpOk([string]$url, [int]$timeoutSec = 3) {
  try {
    $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec
    return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Test-ViteDevClient([int]$port, [int]$timeoutSec = 3) {
  $devClientUrl = "http://${HealthCheckHost}:$port/@vite/client"
  try {
    $resp = Invoke-WebRequest -Uri $devClientUrl -UseBasicParsing -TimeoutSec $timeoutSec
    if ($resp.StatusCode -lt 200 -or $resp.StatusCode -ge 500) {
      return $false
    }

    $contentType = ""
    if ($resp.Headers -and $resp.Headers["Content-Type"]) {
      $contentType = [string]$resp.Headers["Content-Type"]
    }

    $body = ""
    if ($null -ne $resp.Content) {
      $body = [string]$resp.Content
    }

    if ($contentType -match "text/html") {
      return $false
    }

    return ($body -match "createHotContext" -or $body -match "__HMR_PROTOCOL__" -or $body -match "WebSocket")
  } catch {
    return $false
  }
}

function Wait-FrontendHealthy([string]$mode, [int]$port, [int]$timeoutSec = 30) {
  $rootUrl = "http://${HealthCheckHost}:$port/"
  $deadline = (Get-Date).AddSeconds($timeoutSec)

  while ((Get-Date) -lt $deadline) {
    if ($mode -eq "dev") {
      if (Test-ViteDevClient $port 3) {
        return $true
      }
    } else {
      if (Test-HttpOk $rootUrl 3) {
        return $true
      }
    }
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

function Remove-FileIfPossible([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) {
    return
  }
  try {
    Remove-Item -LiteralPath $path -Force
  } catch {
    Write-Warning "  skip removing locked file: $path"
  }
}

function Start-NpmCommand([string[]]$arguments, [string]$workingDirectory, [string]$log, [string]$errLog) {
  $escaped = ($arguments | ForEach-Object {
    if ($_ -match '\s') {
      '"' + $_.Replace('"', '\"') + '"'
    } else {
      $_
    }
  }) -join ' '

  Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm.cmd $escaped" `
    -WorkingDirectory $workingDirectory `
    -RedirectStandardOutput $log `
    -RedirectStandardError $errLog | Out-Null
}

function Start-FrontendDistViaPython([string]$projectRoot, [int]$port, [string]$pythonExe, [string]$log, [string]$errLog, [string]$frontendHost, [string]$apiTarget) {
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
    -ArgumentList "scripts/serve_dist_spa.py --host $frontendHost --port $port --dir dist --api-target $apiTarget" `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $log `
    -RedirectStandardError $errLog | Out-Null

  if (Wait-HttpOk "http://${HealthCheckHost}:$port/" 20) {
    Write-Host "  frontend ok (dist-python): http://${frontendHost}:$port/" -ForegroundColor Green
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

$backendArgs = @("-m", "uvicorn", "app.main:app", "--host", "$BackendHost", "--port", "$BackendPort", "--timeout-keep-alive", "5")
if ($BackendReload) {
  $backendArgs += @("--reload", "--reload-dir", "app", "--reload-exclude=*.log", "--reload-exclude=data/*", "--reload-exclude=downloads/*")
}

if (-not (Wait-HttpOk "http://${HealthCheckHost}:$BackendPort/docs" 2)) {
  Remove-FileIfPossible $backendLog
  Remove-FileIfPossible $backendErrLog

  Start-Process -FilePath $PythonExe `
    -ArgumentList $backendArgs `
    -WorkingDirectory $backendRoot `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrLog | Out-Null
} else {
  Write-Host "  backend already running on $BackendPort, skip start"
}

if (-not (Wait-HttpOk "http://${HealthCheckHost}:$BackendPort/docs" 40)) {
  Write-Host "backend failed to become healthy: http://${HealthCheckHost}:$BackendPort/docs" -ForegroundColor Red
  Write-Host "check logs: $backendLog / $backendErrLog" -ForegroundColor Yellow
  exit 1
}
Write-Host "  backend ok: http://${BackendHost}:$BackendPort/docs" -ForegroundColor Green

Write-Step "Start frontend ($FrontendMode, $FrontendPort)"

if ($FrontendMode -eq "dist") {
  if (-not (Wait-FrontendHealthy $FrontendMode $FrontendPort 2)) {
    Remove-FileIfPossible $frontendLog
    Remove-FileIfPossible $frontendErrLog
    Start-FrontendDistViaPython $root $FrontendPort $PythonExe $frontendLog $frontendErrLog $FrontendHost $frontendApiTarget | Out-Null
  } else {
    Write-Host "  frontend already running on $FrontendPort (dist/python), skip start"
  }
} elseif ($FrontendMode -eq "preview") {
  $frontendArgs = @("run", "preview", "--", "--host", "$FrontendHost", "--port", "$FrontendPort", "--strictPort")
} else {
  $frontendArgs = @("run", "dev", "--", "--host", "$FrontendHost", "--port", "$FrontendPort", "--strictPort")
}

if ($FrontendMode -ne "dist") {
  $frontendRootAlive = Test-HttpOk "http://${HealthCheckHost}:$FrontendPort/" 2
  $frontendHealthy = Wait-FrontendHealthy $FrontendMode $FrontendPort 2

  if (-not $frontendHealthy -and $frontendRootAlive -and $NoKill) {
    Write-Host "frontend port $FrontendPort is occupied by a non-$FrontendMode server. rerun without -NoKill or change -FrontendPort." -ForegroundColor Red
    Write-Host "requested mode: $FrontendMode" -ForegroundColor Yellow
    exit 1
  }

  if (-not $frontendHealthy) {
    Remove-FileIfPossible $frontendLog
    Remove-FileIfPossible $frontendErrLog
    Start-NpmCommand -arguments $frontendArgs -workingDirectory $root -log $frontendLog -errLog $frontendErrLog
  } else {
    Write-Host "  frontend already running on $FrontendPort ($FrontendMode), skip start"
  }
}

if (-not (Wait-FrontendHealthy $FrontendMode $FrontendPort 40)) {
  $fallbackTriggered = $false
  if (-not $NoFrontendFallback -and $FrontendMode -eq "preview" -and -not $frontendModeExplicit) {
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
      $fallbackTriggered = Start-FrontendDistViaPython $root $FrontendPort $PythonExe $frontendLog $frontendErrLog $FrontendHost $frontendApiTarget
    }
  }
  if (-not $fallbackTriggered) {
    if ($FrontendMode -eq "dev") {
      Write-Host "frontend failed to become healthy: http://${HealthCheckHost}:$FrontendPort/@vite/client" -ForegroundColor Red
    } else {
      Write-Host "frontend failed to become healthy: http://${HealthCheckHost}:$FrontendPort/" -ForegroundColor Red
    }
    Write-Host "check log: $frontendLog" -ForegroundColor Yellow
    Write-Host "check err: $frontendErrLog" -ForegroundColor Yellow
    exit 1
  }
}
if ($FrontendMode -eq "dev") {
  Write-Host "  frontend ok (dev + HMR): http://${FrontendHost}:$FrontendPort/" -ForegroundColor Green
} elseif ($FrontendMode -eq "preview") {
  Write-Host "  frontend ok (preview): http://${FrontendHost}:$FrontendPort/" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
Write-Host "frontend log: $frontendLog"
Write-Host "frontend err: $frontendErrLog"
Write-Host "backend  log: $backendLog"
Write-Host "backend err: $backendErrLog"
