param(
    [Parameter(Mandatory = $true)][string]$BackendPath,
    [string]$OutputDir = 'D:\medqc\exports-dual-source27',
    [string]$PythonPath = ''
)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$entry = Join-Path $PSScriptRoot 'backend\scripts\export_dual_source27.py'
if (-not (Test-Path -LiteralPath $entry)) {
    $entry = Join-Path $PSScriptRoot '..\backend\scripts\export_dual_source27.py'
}
Write-Host 'Read-only export: local backup first, then full dual-source rows and reviewed candidates. No database writes or model calls.'
$arguments = @($entry, '--backend', $BackendPath, '--output-dir', $OutputDir)
if ($PythonPath) { & $PythonPath @arguments } else { & py -3.10 @arguments }
if ($LASTEXITCODE -ne 0) { throw 'Export incomplete. Do not use a .partial archive. Send only the safe error event.' }
