param(
    [int]$Port = 8001,
    [switch]$Reload,
    [switch]$InstallActivationOnly
)

$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $env:TEMP "medqc-backend-logs"

function Install-BundledProductActivation {
    $bootstrapPath = Join-Path $backendRoot "app\data\product_activation_bootstrap.json"
    if (-not (Test-Path -LiteralPath $bootstrapPath -PathType Leaf)) {
        return $false
    }

    if ($env:PRODUCT_ACTIVATION_STATE_PATH) {
        $activationStatePath = $env:PRODUCT_ACTIVATION_STATE_PATH
        if (-not [System.IO.Path]::IsPathRooted($activationStatePath)) {
            $activationStatePath = Join-Path $backendRoot $activationStatePath
        }
    } elseif ($env:ProgramData) {
        $activationStatePath = Join-Path $env:ProgramData "MedQC\license\activation.json"
    } else {
        $activationStatePath = Join-Path $backendRoot "app\data\product_activation_state.json"
    }

    if (Test-Path -LiteralPath $activationStatePath -PathType Leaf) {
        Write-Host "Existing product activation state kept: $activationStatePath"
        return $false
    }

    try {
        $bootstrap = Get-Content -LiteralPath $bootstrapPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        throw "Bundled product activation state is not valid JSON."
    }
    if (-not $bootstrap.activation_code -or -not $bootstrap.payload) {
        throw "Bundled product activation state is incomplete."
    }

    $activationStateDirectory = Split-Path -Parent $activationStatePath
    New-Item -ItemType Directory -Path $activationStateDirectory -Force | Out-Null
    try {
        [System.IO.File]::Copy($bootstrapPath, $activationStatePath, $false)
    } catch [System.IO.IOException] {
        if (Test-Path -LiteralPath $activationStatePath -PathType Leaf) {
            Write-Host "Existing product activation state kept: $activationStatePath"
            return $false
        }
        throw
    }
    Write-Host "Bundled product activation installed: $activationStatePath"
    return $true
}

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
$activationInstalled = Install-BundledProductActivation
if ($InstallActivationOnly) {
    if (-not $activationInstalled) {
        Write-Host "No bundled product activation was installed."
    }
    exit 0
}

Write-Host "Starting backend on port $Port"
Write-Host "Log dir: $logDir"
if ($Reload) {
    Write-Host "Reload mode: ON (Windows 下仅建议在确实需要热重载时启用)"
} else {
    Write-Host "Reload mode: OFF (默认关闭，避免 uvicorn --reload 在 Windows 上卡死)"
}

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
    '--timeout-keep-alive', '5'
)

if ($Reload) {
    $uvicornArgs += @(
        '--reload',
        '--reload-dir', 'app',
        '--reload-exclude=*.log',
        '--reload-exclude=data/*',
        '--reload-exclude=downloads/*'
    )
}

& python @uvicornArgs
