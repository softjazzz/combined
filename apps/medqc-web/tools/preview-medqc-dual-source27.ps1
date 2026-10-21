param(
    [Parameter(Mandatory = $true)][string]$BackendPath,
    [string]$OutputDir = 'D:\medqc\dual-source27-reports',
    [string]$PythonPath = '',
    [string]$CasesPath = '',
    [string]$Tables = '',
    [ValidateRange(5, 120)][int]$StatementTimeoutSeconds = 60,
    [switch]$LocalOnly
)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$entry = Join-Path $PSScriptRoot 'backend\scripts\preview_dual_source27.py'
if (-not (Test-Path -LiteralPath $entry)) {
    $entry = Join-Path $PSScriptRoot '..\backend\scripts\preview_dual_source27.py'
}
$cases = if ($CasesPath) { $CasesPath } else { Join-Path (Split-Path -Parent $entry) 'cases27-private.json' }
$arguments = @($entry, '--backend', $BackendPath, '--cases', $cases, '--output-dir', $OutputDir)
if ($Tables) { $arguments += @('--tables', $Tables) }
$arguments += @('--statement-timeout-seconds', [string]$StatementTimeoutSeconds)
if ($LocalOnly) { $arguments += '--local-only' }
Write-Host 'Read-only dual-source preview: 27 cases. No database writes, deployment, or model calls.'
if ($PythonPath) { & $PythonPath @arguments } else { & py -3.10 @arguments }
if ($LASTEXITCODE -eq 2) {
    Write-Warning 'Coverage is incomplete. The report distinguishes unavailable sources/tables from zero rows. Do not apply it.'
    exit 2
} elseif ($LASTEXITCODE -ne 0) {
    throw 'Preview failed. Send only the safe error event; never send credentials or medical text.'
}
