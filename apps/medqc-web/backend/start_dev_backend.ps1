param(
    [int]$Port = 8001,
    [switch]$Reload,
    [switch]$InstallActivationOnly
)

$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $backendRoot "logs"

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

function Test-PortInUse([int]$port) {
    $line = (netstat -ano | Select-String (":$port\s") | Select-String "LISTENING" | Select-Object -First 1).Line
    if (-not $line) { return $null }
    $portPid = ($line -split '\s+')[-1]
    return $portPid
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
    Write-Host "Reload mode: ON (use on Windows only when hot reload is required)"
} else {
    Write-Host "Reload mode: OFF (default on Windows to avoid uvicorn reload hangs)"
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

# 每次启动独立留档；使用 .NET API 构造并校验路径，避免客户机环境下
# Tee-Object 收到空 FilePath 后在应用启动前退出。
$logFileName = "backend-{0}-{1}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $PID
$logPath = [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($logDir, $logFileName))
if ([string]::IsNullOrWhiteSpace($logPath)) {
    throw "Backend log path is empty."
}
Write-Host "Backend log: $logPath"
$savedErrorActionPreference = $ErrorActionPreference
$backendExitCode = 1
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
$logWriter = New-Object System.IO.StreamWriter($logPath, $false, $utf8WithoutBom)
$logWriter.AutoFlush = $true
try {
    # Windows PowerShell 会把原生 stderr 包装成错误记录；不能因此中断日志管道。
    $ErrorActionPreference = "Continue"
    & python @uvicornArgs 2>&1 | ForEach-Object {
        $renderedLine = [string]$_
        Write-Output $renderedLine
        $logWriter.WriteLine($renderedLine)
    }
    $backendExitCode = $LASTEXITCODE
} finally {
    $logWriter.Dispose()
    $ErrorActionPreference = $savedErrorActionPreference
}
exit $backendExitCode
