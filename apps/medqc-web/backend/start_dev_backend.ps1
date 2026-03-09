param(
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $env:TEMP "medqc-backend-logs"

function Test-PortInUse([int]$p) {
    $line = (netstat -ano | Select-String (":$p\\s") | Select-String "LISTENING" | Select-Object -First 1).Line
    if (-not $line) { return $null }
    $pid = ($line -split "\\s+")[-1]
    return $pid
}

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

if (-not $env:JWT_SECRET) {
    $env:JWT_SECRET = "dev-secret"
}

$env:PYTHONIOENCODING = "utf-8"

Write-Host "Starting backend on port $Port"
Write-Host "Log dir: $logDir"

Set-Location $backendRoot

$pidInUse = Test-PortInUse $Port
if ($pidInUse) {
    $pname = $null
    try { $pname = (Get-Process -Id $pidInUse -ErrorAction Stop).ProcessName } catch { }
    $msg = "Port $Port is already in use by PID=$pidInUse"
    if ($pname) { $msg += " ($pname)" }
    throw $msg
}

$uvicornArgs = @(
    '-m', 'uvicorn', 'app.main:app',
    '--host', '0.0.0.0',
    '--port', "$Port",
    '--reload',
    '--reload-dir', 'app',
    '--reload-exclude=*.log',
    '--reload-exclude=data/*',
    '--reload-exclude=downloads/*'
)

& python @uvicornArgs
