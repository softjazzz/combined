param(
    [Parameter(Mandatory = $true)][string]$BackendPath,
    [string]$Samples = 'C17,C18,C22',
    [string]$Tables = 'inpat_drug_order,inpat_nondrug_order,bloodtrans_record,discharge_record',
    [string]$BackupDir = 'D:\medqc\backups',
    [string]$OutputDir = 'D:\medqc\dual-source-acceptance-reports',
    [string]$PythonPath = '',
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$entry = Join-Path $PSScriptRoot 'backend\scripts\sync_dual_source_cases.py'
if (-not (Test-Path -LiteralPath $entry)) {
    $entry = Join-Path $PSScriptRoot '..\backend\scripts\sync_dual_source_cases.py'
}
$scope = Join-Path (Split-Path -Parent $entry) 'dual-source-acceptance-scope-private.json'
$arguments = @('-X', 'utf8', $entry, '--backend', $BackendPath, '--scope', $scope,
    '--samples', $Samples, '--tables', $Tables, '--backup-dir', $BackupDir, '--output-dir', $OutputDir)
if ($Apply) {
    Write-Host 'APPLY: backup first, insert confirmed records and fill empty fields; preserve conflicts. Refresh bundles. No QC/model calls.'
    $arguments += '--apply'
} else {
    Write-Host 'PREVIEW ONLY: no database writes, no bundle refresh, no QC/model calls.'
}
if ($PythonPath) { & $PythonPath @arguments } else { & py -3.10 @arguments }
if ($LASTEXITCODE -ne 0) {
    throw 'Acceptance did not finish. Check data_committed and phase; do not blindly repeat. Send only safe error events.'
}
