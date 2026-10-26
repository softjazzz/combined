param(
    [ValidateSet('Upgrade','Install','Restart','Materials','PreviewMaterials','ApplyMaterials','PreviewRecovery','ApplyRecovery','Closeout')]
    [string]$Mode = 'Materials',
    [string]$BackendPath = 'D:\medqc\medqc-web-customer-R26.5\backend',
    [string]$OutputDir = 'D:\medqc\p0-closeout-reports',
    [string]$BackupDir = 'D:\medqc\backups',
    [string]$RecordingDir = 'D:\medqc\c18-diagnostic-reports',
    [string]$JobId = 'c4f16093-246a-455f-8124-438d9b3511e6',
    [string]$PgBin = 'C:\Program Files\PostgreSQL\16\bin'
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if (-not (Test-Path -LiteralPath (Join-Path $BackendPath '.env'))) { throw 'Backend .env does not exist.' }
if ($Mode -eq 'Closeout') {
    & py -3.10 -u (Join-Path $PSScriptRoot 'check_p0_restart_safety.py') --backend $BackendPath
    if ($LASTEXITCODE -ne 0) { throw 'An active QC task or database error prevents closeout. Nothing was changed.' }
    foreach ($step in @('Upgrade','Install','Restart','ApplyMaterials')) {
        & $PSCommandPath -Mode $step -BackendPath $BackendPath -OutputDir $OutputDir -BackupDir $BackupDir -RecordingDir $RecordingDir -JobId $JobId -PgBin $PgBin
    }
    $materialGaps = $false
    try { & $PSCommandPath -Mode 'Materials' -BackendPath $BackendPath -OutputDir $OutputDir }
    catch { $materialGaps = $true; Write-Host 'Material gaps were recorded. Recovery still requires verified material chains for each failed case.' }
    foreach ($step in @('PreviewRecovery','ApplyRecovery')) {
        & $PSCommandPath -Mode $step -BackendPath $BackendPath -OutputDir $OutputDir -BackupDir $BackupDir -RecordingDir $RecordingDir -JobId $JobId
    }
    if ($materialGaps) { throw 'Failed-pair recovery finished, but global material gaps remain. Keep the material report.' }
    return
}
if ($Mode -eq 'Upgrade') {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'upgrade-medqc-pg-053.ps1') -BackendPath $BackendPath -BackupDir $BackupDir -PgBin $PgBin
    if ($LASTEXITCODE -ne 0) { throw 'Database upgrade stopped.' }
    return
}
if ($Mode -eq 'Restart') {
    # 只重启8001后端，保留PG及前端；验收模式禁止启动旧质控队列。
    & py -3.10 -u (Join-Path $PSScriptRoot 'check_p0_restart_safety.py') --backend $BackendPath
    if ($LASTEXITCODE -ne 0) { throw 'An active QC task or database error prevents safe restart. Backend was not stopped.' }
    $null = New-Item -ItemType Directory -Path $OutputDir -Force
    $owners = @(Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($ownerId in $owners) { Stop-Process -Id $ownerId -ErrorAction Stop }
    $env:MEDQC_STARTUP_MODE = 'acceptance'
    $env:PRODUCT_ACTIVATION_REQUIRED = 'true'
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fffffff'
    $outLog = Join-Path $OutputDir ('p0-backend-' + $stamp + '-out-private.log')
    $errLog = Join-Path $OutputDir ('p0-backend-' + $stamp + '-err-private.log')
    $pythonLauncher = (Get-Command py -ErrorAction Stop).Source
    $process = Start-Process -FilePath $pythonLauncher -ArgumentList @('-3.10','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001') -WorkingDirectory $BackendPath -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $runtime = Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/runtime-build' -TimeoutSec 2
            if ($runtime.p0_acceptance.loaded_equals_disk -eq $true -and $runtime.p0_acceptance.recovery_supported -eq $true) {
                Write-Host ('P0_BACKEND_LOADED=True PID=' + $runtime.pid)
                return
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    throw ('Patched backend not ready. Check private log: ' + $errLog)
}
$arguments = @('--backend', $BackendPath)
switch ($Mode) {
    'Install' {
        $script = 'install_p0_chain_fix.py'
        $arguments += @('--backup-dir', $BackupDir)
    }
    'Materials' {
        $script = 'verify_p0_material_chain.py'
        $arguments += @('--output-dir', $OutputDir)
    }
    { $_ -in 'PreviewMaterials','ApplyMaterials' } {
        $script = 'repair_p0_materials.py'
        $arguments += @('--backup-dir', $BackupDir, '--output-dir', $OutputDir)
        if ($Mode -eq 'ApplyMaterials') { $arguments += '--apply' }
    }
    { $_ -in 'PreviewRecovery','ApplyRecovery' } {
        $script = 'recover_p0_failed_results.py'
        $arguments += @('--output-dir', $OutputDir, '--recordings', $RecordingDir, '--job', $JobId)
        if ($Mode -eq 'ApplyRecovery') { $arguments += '--apply' }
    }
}
Write-Host ('P0 mode: ' + $Mode + '. No real model calls. Original successful QC results are protected.')
& py -3.10 -u (Join-Path $PSScriptRoot $script) @arguments
if ($LASTEXITCODE -ne 0) {
    throw 'P0 check stopped or found gaps. Keep the report; do not restart a full QC batch.'
}
