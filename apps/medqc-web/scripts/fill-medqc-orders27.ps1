param(
    [string]$BackendPath = 'D:\medqc\medqc-web-customer-R26.4\backend',
    [string]$BackupDir = 'D:\medqc\backups',
    [string]$OutputDir = 'D:\medqc\orders27-reports',
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
if (-not $Apply) { throw 'Explicit -Apply is required. No database changes were made.' }
foreach ($file in @('fill_orders27.py','preview_orders27.py','preview_order_time_fill.py','cases27-private.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $file))) { throw "Missing file: $file" }
}
if (-not (Test-Path -LiteralPath $BackendPath)) { throw 'Backend directory not found.' }
$previousEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING = 'utf-8'
    Write-Host '27 cases: backup first, fill confirmed existing orders only. No inserts, deletes, or model calls.'
    & py -3.10 (Join-Path $PSScriptRoot 'fill_orders27.py') `
        --backend $BackendPath --scope (Join-Path $PSScriptRoot 'cases27-private.json') `
        --backup-dir $BackupDir --output-dir $OutputDir --apply
    if ($LASTEXITCODE -ne 0) { throw 'Fill did not finish. Check error phase and data_committed; keep the private backup local.' }
    Write-Host 'Complete. Share the final done output, not the private backup.' -ForegroundColor Green
}
finally { $env:PYTHONIOENCODING = $previousEncoding }
