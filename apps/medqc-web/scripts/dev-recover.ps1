param(
  [switch]$FrontendOnly,
  [switch]$BackendOnly,
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8001,
  [string]$PythonExe = "C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\python.exe"
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$tmpDir = Join-Path $root ".tmp"
$frontendLog = Join-Path $tmpDir "vite-dev.log"
$backendLog = Join-Path $tmpDir "uvicorn-8001.log"

function Write-Step($msg) {
  Write-Host "==> $msg" -ForegroundColor Cyan
}

function Get-PortPids([int]$port) {
  $lines = netstat -ano -p tcp | Select-String "^\s*TCP\s+"
  $pidList = @()
  foreach ($line in $lines) {
    $parts = ($line.ToString() -split "\s+") | Where-Object { $_ -ne "" }
    if ($parts.Length -ge 5) {
      $localEndpoint = $parts[1]
      if ($localEndpoint -notmatch ":$port$") {
        continue
      }
      $portPid = $parts[-1]
      if ($portPid -match "^\d+$" -and $portPid -ne "0") {
        $pidList += [int]$portPid
      }
    }
  }
  return $pidList | Sort-Object -Unique
}

function Stop-PortProcess([int]$port) {
  $portPids = Get-PortPids $port
  if (-not $portPids -or $portPids.Count -eq 0) {
    Write-Host "  port ${port}: no process"
    return
  }
  foreach ($portPid in $portPids) {
    Write-Host "  kill pid=$portPid on port $port"
    try {
      taskkill /PID $portPid /F | Out-Null
    } catch {
      Write-Warning "  failed to kill pid=$portPid : $($_.Exception.Message)"
    }
  }
}

function Stop-FrontendNodeProcesses([string]$projectRoot, [int]$port) {
  Stop-PortProcess $port
  try {
    $escapedRoot = [Regex]::Escape($projectRoot)
    $nodeProcs = Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
      Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match "vite" -and
        $_.CommandLine -match $escapedRoot
      }
    foreach ($proc in $nodeProcs) {
      Write-Host "  kill stale vite pid=$($proc.ProcessId)"
      try {
        taskkill /PID $proc.ProcessId /F | Out-Null
      } catch {
        Write-Warning "  failed to kill stale vite pid=$($proc.ProcessId): $($_.Exception.Message)"
      }
    }
  } catch {
    Write-Warning "  scan stale vite process failed: $($_.Exception.Message)"
  }
}

function Wait-HttpOk([string]$url, [int]$timeoutSec = 25) {
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

function Test-HttpEndpoint([string]$url, [int]$timeoutSec = 8) {
  try {
    $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec
    return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Test-FrontendHealth([int]$port) {
  $baseTargets = @(
    "http://127.0.0.1:$port/",
    "http://127.0.0.1:$port/@vite/client"
  )
  foreach ($target in $baseTargets) {
    if (-not (Test-HttpEndpoint $target 10)) {
      Write-Warning "  frontend health check failed: $target"
      return $false
    }
  }

  # 冷启动时模块转换较慢，给 src/main.ts 更长超时窗口
  $stamp = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
  $mainUrl = "http://127.0.0.1:$port/src/main.ts?t=$stamp"
  if (-not (Test-HttpEndpoint $mainUrl 45)) {
    Write-Warning "  frontend module warmup timeout: $mainUrl"
    return $false
  }

  return $true
}

function Get-ProcessCpuPercent([int]$processId, [int]$sampleSeconds = 3) {
  try {
    $p1 = Get-Process -Id $processId -ErrorAction Stop
    $cpu1 = [double]$p1.CPU
    Start-Sleep -Seconds $sampleSeconds
    $p2 = Get-Process -Id $processId -ErrorAction Stop
    $cpu2 = [double]$p2.CPU
    $deltaCpu = $cpu2 - $cpu1
    if ($deltaCpu -lt 0) { $deltaCpu = 0 }
    $cores = [Environment]::ProcessorCount
    if ($cores -le 0) { $cores = 1 }
    $percent = ($deltaCpu / ([double]$sampleSeconds * $cores)) * 100.0
    return [Math]::Round($percent, 1)
  } catch {
    return -1
  }
}

function Resolve-PythonExecutable([string]$preferred) {
  try {
    if ($preferred) {
      try {
        if (Test-Path -LiteralPath $preferred -ErrorAction Stop) {
          return $preferred
        }
      } catch {}
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
      return "py -3.10"
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
      return $python.Source
    }
  } catch {}
  return $null
}

function Resolve-EsbuildBinary([string]$projectRoot) {
  try {
    $searchRoots = @(
      $projectRoot,
      (Split-Path -Parent $projectRoot),
      (Split-Path -Parent (Split-Path -Parent $projectRoot))
    ) | Select-Object -Unique

    $hostCandidates = @()
    foreach ($sr in $searchRoots) {
      $hostPattern = Join-Path $sr "node_modules\.pnpm\esbuild@*\node_modules\esbuild\package.json"
      $hostCandidates += Get-ChildItem -Path $hostPattern -ErrorAction SilentlyContinue
    }
    if (-not $hostCandidates -or $hostCandidates.Count -eq 0) {
      return $null
    }
    $hostPkg = $hostCandidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $hostVersion = (Get-Content $hostPkg.FullName -Raw | ConvertFrom-Json).version
    if (-not $hostVersion) {
      return $null
    }

    $candidateList = @()
    foreach ($sr in $searchRoots) {
      $candidatePattern = Join-Path $sr "node_modules\.pnpm\@esbuild+win32-x64@$hostVersion\node_modules\@esbuild\win32-x64\esbuild.exe"
      $candidateList += Get-ChildItem -Path $candidatePattern -ErrorAction SilentlyContinue
    }
    $candidate = $candidateList | Select-Object -First 1
    if (-not $candidate) {
      return $null
    }

    $safeVersion = ($hostVersion -replace "[^0-9A-Za-z\.-]", "_")
    $localTmpDir = Join-Path $projectRoot ".tmp"
    if (-not (Test-Path -LiteralPath $localTmpDir)) {
      New-Item -ItemType Directory -Path $localTmpDir -Force | Out-Null
    }
    $tempEsbuild = Join-Path $localTmpDir ("esbuild-dev-" + $safeVersion + ".exe")
    try {
      Copy-Item -Path $candidate.FullName -Destination $tempEsbuild -Force -ErrorAction Stop
    } catch {
      if (-not (Test-Path -LiteralPath $tempEsbuild)) {
        throw
      }
    }
    return $tempEsbuild
  } catch {
    Write-Warning "  prepare esbuild binary failed: $($_.Exception.Message)"
    return $null
  }
}

if (-not (Test-Path $tmpDir)) {
  New-Item -ItemType Directory -Path $tmpDir | Out-Null
}

$runFrontend = $true
$runBackend = $true
if ($FrontendOnly) { $runBackend = $false }
if ($BackendOnly) { $runFrontend = $false }

if ($runFrontend) {
  Write-Step "Recover frontend :$FrontendPort"
  Stop-FrontendNodeProcesses $root $FrontendPort
  $esbuildBinary = Resolve-EsbuildBinary $root
  if ($esbuildBinary) {
    Write-Host "  use esbuild binary: $esbuildBinary"
  } else {
    Write-Warning "  esbuild binary not found, fallback to default"
  }

  if (Test-Path $frontendLog) {
    try {
      Remove-Item -Force $frontendLog -ErrorAction Stop
    } catch {
      $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
      $frontendLog = Join-Path $tmpDir "vite-dev-$stamp.log"
      Write-Host "  frontend log in use, switch to: $frontendLog"
    }
  }

  $frontendReady = $false
  for ($attempt = 1; $attempt -le 2; $attempt++) {
    Write-Host "  frontend boot attempt $attempt/2"
    $extraArgs = "--host=127.0.0.1 --port=$FrontendPort --strictPort"
    if ($attempt -eq 2) {
      $viteCache = Join-Path $root "node_modules\.vite"
      if (Test-Path $viteCache) {
        Write-Host "  retry mode: remove vite cache -> $viteCache"
        Remove-Item -Recurse -Force $viteCache
      }
      $extraArgs = "$extraArgs --force"
    }
    $esbuildEnv = ""
    if ($esbuildBinary) {
      $esbuildEnv = "set ESBUILD_BINARY_PATH=$esbuildBinary&& "
    }
    $frontendCmd = "set HTTP_PROXY=&& set HTTPS_PROXY=&& set ALL_PROXY=&& set NO_PROXY=localhost,127.0.0.1&& $esbuildEnv npm run dev -- $extraArgs > `"$frontendLog`" 2>&1"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $frontendCmd -WorkingDirectory $root | Out-Null

    if (-not (Wait-HttpOk "http://127.0.0.1:$FrontendPort" 35)) {
      Write-Warning "  frontend base url not ready in attempt $attempt"
    } elseif (Test-FrontendHealth $FrontendPort) {
      $frontendReady = $true
      break
    } else {
      $frontPid = Get-PortPids $FrontendPort | Select-Object -First 1
      if ($frontPid) {
        $cpu = Get-ProcessCpuPercent $frontPid 3
        if ($cpu -ge 0) {
          Write-Warning "  frontend pid=$frontPid unhealthy, cpu=$cpu%"
        } else {
          Write-Warning "  frontend pid=$frontPid unhealthy, cpu unknown"
        }
      } else {
        Write-Warning "  frontend unhealthy and no listening pid found"
      }
    }

    if ($attempt -lt 2) {
      Stop-FrontendNodeProcesses $root $FrontendPort
      Start-Sleep -Milliseconds 700
    }
  }

  if ($frontendReady) {
    Write-Host "  frontend ok: http://127.0.0.1:$FrontendPort" -ForegroundColor Green
  } else {
    Write-Warning "  frontend unstable. see log: $frontendLog"
  }
}

if ($runBackend) {
  Write-Step "Recover backend :$BackendPort"
  Stop-PortProcess $BackendPort

  $resolvedPython = Resolve-PythonExecutable $PythonExe
  if (-not $resolvedPython) {
    Write-Warning "  python not found. set -PythonExe or install py/python"
  } else {
    if (Test-Path $backendLog) {
      try {
        Remove-Item -Force $backendLog -ErrorAction Stop
      } catch {
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $backendLog = Join-Path $tmpDir "uvicorn-8001-$stamp.log"
        Write-Host "  backend log in use, switch to: $backendLog"
      }
    }

    $backendDir = Join-Path $root "backend"
    $arg = "-m uvicorn app.main:app --host 0.0.0.0 --port $BackendPort --reload"
    $backendErrLog = [System.IO.Path]::ChangeExtension($backendLog, ".err.log")
    if ($resolvedPython -like "py *") {
      $cmd = "$resolvedPython $arg > `"$backendLog`" 2> `"$backendErrLog`""
      Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -WorkingDirectory $backendDir | Out-Null
    } else {
      Start-Process -FilePath $resolvedPython -ArgumentList $arg -WorkingDirectory $backendDir -RedirectStandardOutput $backendLog -RedirectStandardError $backendErrLog | Out-Null
    }

    if (Wait-HttpOk "http://127.0.0.1:$BackendPort/docs" 35) {
      Write-Host "  backend ok: http://127.0.0.1:$BackendPort/docs" -ForegroundColor Green
    } else {
      Write-Warning "  backend not ready. see log: $backendLog"
    }
  }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
Write-Host "Frontend log: $frontendLog"
Write-Host "Backend  log: $backendLog"
