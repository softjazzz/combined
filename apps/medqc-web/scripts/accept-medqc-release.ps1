# ASCII only for Windows PowerShell 5.1.
param(
    [ValidateSet('Verify','PreviewMaterials','ApplyMaterials','PreviewRecovery','ApplyRecovery')]
    [string]$Mode = 'Verify',
    [string]$BackendPath = '',
    [string]$OutputDir = 'D:\medqc\release-acceptance-reports',
    [string]$BackupDir = 'D:\medqc\backups',
    [string]$RecordingDir = 'D:\medqc',
    [string]$JobId = 'c4f16093-246a-455f-8124-438d9b3511e6'
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if ([string]::IsNullOrWhiteSpace($BackendPath)) {
    $BackendPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'backend'
}
$BackendPath = (Resolve-Path -LiteralPath $BackendPath).Path
$declarationPath = Join-Path $BackendPath 'app\data\runtime_build.json'
if (-not (Test-Path -LiteralPath $declarationPath)) { throw 'Formal release build identity is missing.' }
$disk = Get-Content -LiteralPath $declarationPath -Raw -Encoding UTF8 | ConvertFrom-Json
$runtime = Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/runtime-build' -TimeoutSec 10
if ($runtime.available -ne $true -or $runtime.build_id -cne $disk.build_id -or $runtime.git_commit -cne $disk.git_commit) {
    throw 'Running backend does not match this release. Start the new release first; nothing was changed.'
}
if ($runtime.p0_acceptance.loaded_equals_disk -ne $true -or $runtime.p0_acceptance.recovery_supported -ne $true) {
    throw 'Loaded P0 implementation does not match disk; nothing was changed.'
}
Write-Host ('RUNNING_RELEASE_VERIFIED: ' + $runtime.build_id + ' / ' + $runtime.git_commit)
$arguments = @('--backend', $BackendPath, '--output-dir', $OutputDir)
switch ($Mode) {
    'Verify' { $script = 'verify_p0_material_chain.py' }
    { $_ -in 'PreviewMaterials','ApplyMaterials' } {
        $script = 'repair_p0_materials.py'
        $arguments += @('--backup-dir', $BackupDir)
        if ($Mode -eq 'ApplyMaterials') { $arguments += '--apply' }
    }
    { $_ -in 'PreviewRecovery','ApplyRecovery' } {
        $script = 'recover_p0_failed_results.py'
        $arguments += @('--recordings', $RecordingDir, '--job', $JobId)
        if ($Mode -eq 'ApplyRecovery') { $arguments += '--apply' }
    }
}
Write-Host ('Acceptance mode: ' + $Mode + '. No real model calls, source writes, or full-batch QC rerun.')
& py -3.10 -u (Join-Path $PSScriptRoot $script) @arguments
if ($LASTEXITCODE -ne 0) { throw 'Acceptance incomplete. Keep the report and check data_committed before repeating a write.' }
