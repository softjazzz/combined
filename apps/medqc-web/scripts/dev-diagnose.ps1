param(
  [int]$FrontendPort = 3000,
  [int]$BackendPort = 8001
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

function Write-Section([string]$title) {
  Write-Host ""
  Write-Host "=== $title ===" -ForegroundColor Cyan
}

function Write-KeyValue([string]$k, [string]$v) {
  Write-Host ("{0,-28} {1}" -f $k, $v)
}

function Test-TcpPort([int]$port) {
  $listening = netstat -ano -p tcp | Select-String "LISTENING" | Select-String ":$port\s"
  return ($null -ne $listening)
}

function Get-PortListeners([int]$port) {
  $raw = netstat -ano -p tcp | Select-String "LISTENING" | Select-String ":$port\s"
  if (-not $raw) { return @() }
  $rows = @()
  foreach ($line in $raw) {
    $parts = ($line.ToString() -split "\s+") | Where-Object { $_ -ne "" }
    if ($parts.Length -ge 5) {
      $rows += [pscustomobject]@{
        Proto = $parts[0]
        Local = $parts[1]
        PID = $parts[-1]
      }
    }
  }
  return $rows
}

function Test-Http([string]$url, [int]$timeoutSec = 4) {
  try {
    $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec
    return [pscustomobject]@{
      Ok = $true
      Status = [string]$resp.StatusCode
      Error = ""
    }
  } catch {
    $status = ""
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      $status = [string]$_.Exception.Response.StatusCode.value__
    }
    return [pscustomobject]@{
      Ok = $false
      Status = $status
      Error = $_.Exception.Message
    }
  }
}

function Get-ProxyOverride {
  $key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
  try {
    $val = Get-ItemProperty -Path $key -Name ProxyOverride -ErrorAction Stop
    return [string]$val.ProxyOverride
  } catch {
    return ""
  }
}

function Test-NodeSpawn([string]$command, [string[]]$commandArgs) {
  $safeArgs = @()
  if ($commandArgs) { $safeArgs = $commandArgs }
  $argsJson = ($safeArgs | ConvertTo-Json -Compress)
  $argsBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($argsJson))
  $nodeScript = @"
const cp = require('node:child_process');
const cmd = process.argv[2];
const argsJson = Buffer.from(process.argv[3] || '', 'base64').toString('utf8');
let args = [];
try {
  args = JSON.parse(argsJson);
  if (!Array.isArray(args)) {
    if (args === null || typeof args === 'undefined') {
      args = [];
    } else {
      args = [String(args)];
    }
  }
} catch {
  console.log(JSON.stringify({
    ok: false,
    status: null,
    stdout: '',
    stderr: '',
    error: { code: 'ARGS_PARSE', detail: argsJson }
  }));
  process.exit(0);
}
const r = cp.spawnSync(cmd, args, { encoding: 'utf8' });
const out = {
  ok: !r.error,
  status: r.status,
  stdout: (r.stdout || '').trim(),
  stderr: (r.stderr || '').trim(),
  error: r.error ? {
    code: r.error.code || '',
    errno: r.error.errno || '',
    syscall: r.error.syscall || '',
    path: r.error.path || ''
  } : null
};
console.log(JSON.stringify(out));
"@
  try {
    $tmpNodeScript = Join-Path $env:TEMP "node-spawn-check.js"
    Set-Content -Path $tmpNodeScript -Value $nodeScript -Encoding Ascii
    $raw = & node $tmpNodeScript $command $argsBase64 2>&1
    if (-not $raw) {
      return [pscustomobject]@{ Ok = $false; Detail = "node returned empty" }
    }
    $jsonLine = ($raw | Where-Object { $_ -match "^\s*\{" } | Select-Object -Last 1)
    if (-not $jsonLine) {
      return [pscustomobject]@{ Ok = $false; Detail = (($raw | Out-String).Trim()) }
    }
    $obj = $jsonLine | ConvertFrom-Json
    return [pscustomobject]@{ Ok = [bool]$obj.ok; Detail = ($obj | ConvertTo-Json -Compress) }
  } catch {
    return [pscustomobject]@{ Ok = $false; Detail = $_.Exception.Message }
  } finally {
    try {
      if ($tmpNodeScript -and (Test-Path $tmpNodeScript)) {
        Remove-Item -Path $tmpNodeScript -Force -ErrorAction SilentlyContinue
      }
    } catch {}
  }
}

Write-Host "Dev diagnose start: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Yellow
Write-KeyValue "Workspace" $root

Write-Section "Versions and Env"
$nodeVer = ""
try { $nodeVer = (node -v) } catch { $nodeVer = "Unavailable: $($_.Exception.Message)" }
$npmVer = ""
try { $npmVer = (npm -v) } catch { $npmVer = "Unavailable: $($_.Exception.Message)" }
Write-KeyValue "Node" $nodeVer
Write-KeyValue "NPM" $npmVer
Write-KeyValue "ComSpec" ([string]$env:ComSpec)
Write-KeyValue "HTTP_PROXY" ([string]$env:HTTP_PROXY)
Write-KeyValue "HTTPS_PROXY" ([string]$env:HTTPS_PROXY)
Write-KeyValue "ALL_PROXY" ([string]$env:ALL_PROXY)
Write-KeyValue "NO_PROXY" ([string]$env:NO_PROXY)

Write-Section "System Proxy"
$proxyOverride = Get-ProxyOverride
Write-KeyValue "ProxyOverride" $proxyOverride
if ($proxyOverride -match "localhost" -or $proxyOverride -match "127\.") {
  Write-KeyValue "localhost bypass" "yes"
} else {
  Write-KeyValue "localhost bypass" "no (recommend localhost;127.*;127.0.0.1;::1)"
}

Write-Section "Port Listening"
$fListening = Test-TcpPort $FrontendPort
$bListening = Test-TcpPort $BackendPort
Write-KeyValue "Frontend port $FrontendPort" ($(if ($fListening) { "LISTENING" } else { "NOT LISTENING" }))
Write-KeyValue "Backend port $BackendPort" ($(if ($bListening) { "LISTENING" } else { "NOT LISTENING" }))

if ($fListening) {
  $rows = Get-PortListeners $FrontendPort
  foreach ($r in $rows) {
    Write-KeyValue "Frontend PID" $r.PID
  }
}
if ($bListening) {
  $rows = Get-PortListeners $BackendPort
  foreach ($r in $rows) {
    Write-KeyValue "Backend PID" $r.PID
  }
}

Write-Section "HTTP Health"
$frontBase = Test-Http "http://127.0.0.1:$FrontendPort/"
$frontVite = Test-Http "http://127.0.0.1:$FrontendPort/@vite/client"
$backDocs = Test-Http "http://127.0.0.1:$BackendPort/docs"
Write-KeyValue "Frontend /" ($(if ($frontBase.Ok) { "OK $($frontBase.Status)" } else { "FAIL $($frontBase.Error)" }))
Write-KeyValue "Frontend /@vite/client" ($(if ($frontVite.Ok) { "OK $($frontVite.Status)" } else { "FAIL $($frontVite.Error)" }))
Write-KeyValue "Backend /docs" ($(if ($backDocs.Ok) { "OK $($backDocs.Status)" } else { "FAIL $($backDocs.Error)" }))

Write-Section "Node Spawn Check"
$spawnCmd = Test-NodeSpawn "cmd.exe" @("/c", "echo", "ok")
Write-KeyValue "spawn cmd.exe" ($(if ($spawnCmd.Ok) { "OK" } else { "FAIL" }))
Write-KeyValue "spawn detail" $spawnCmd.Detail

$spawnWhere = Test-NodeSpawn "where.exe" @("node")
Write-KeyValue "spawn where.exe" ($(if ($spawnWhere.Ok) { "OK" } else { "FAIL" }))
Write-KeyValue "where detail" $spawnWhere.Detail

Write-Section "esbuild Spawn Check"
$esbuildPath = Join-Path $root "..\..\node_modules\.pnpm\@esbuild+win32-x64@0.25.9\node_modules\@esbuild\win32-x64\esbuild.exe"
if (-not (Test-Path $esbuildPath)) {
  $esbuildPath = Join-Path $root "..\..\node_modules\.pnpm\@esbuild+win32-x64@0.21.5\node_modules\@esbuild\win32-x64\esbuild.exe"
}
if (Test-Path $esbuildPath) {
  Write-KeyValue "esbuild path" $esbuildPath
  $spawnEsbuild = Test-NodeSpawn $esbuildPath @("--version")
  Write-KeyValue "spawn esbuild" ($(if ($spawnEsbuild.Ok) { "OK" } else { "FAIL" }))
  Write-KeyValue "esbuild detail" $spawnEsbuild.Detail
} else {
  Write-KeyValue "esbuild path" "not found"
}

Write-Section "Conclusions"
$conclusions = @()
if (-not $spawnCmd.Ok -or -not $spawnWhere.Ok) {
  $conclusions += "Core issue: Node child process denied (EPERM). This is not proxy itself; check security software/policy blocking node.exe spawning."
}
if ($bListening -and $backDocs.Ok -and (-not $fListening -or -not $frontBase.Ok)) {
  $conclusions += "Backend is healthy but frontend is not; issue is in Vite/Node runtime."
}
if ($proxyOverride -notmatch "localhost" -and $proxyOverride -notmatch "127\.") {
  $conclusions += "System proxy bypass missing: add localhost/127.* into ProxyOverride."
}
if ($conclusions.Count -eq 0) {
  $conclusions += "No fatal issue detected. If browser still fails, check browser extensions/HMR cache/network filter driver."
}

$idx = 1
foreach ($c in $conclusions) {
  Write-Host ("{0}. {1}" -f $idx, $c) -ForegroundColor Green
  $idx++
}

Write-Host ""
Write-Host "Diagnose done." -ForegroundColor Yellow
