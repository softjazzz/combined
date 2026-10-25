param(
    [string]$BackendPath = 'D:\medqc\medqc-web-customer-R26.4\backend',
    [string]$BackupDir = 'D:\medqc\backups',
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
if (-not $Apply) { throw 'Explicit -Apply is required. No changes were made.' }
$scriptPath = Join-Path $PSScriptRoot 'fill_order_times.py'
$scopePath = Join-Path $PSScriptRoot 'order-time-scope-private.json'
$helperPath = Join-Path $PSScriptRoot 'preview_order_time_fill.py'
foreach ($path in @($BackendPath, $scriptPath, $scopePath, $helperPath)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing path: $path" }
}
$outputPath = Join-Path $PSScriptRoot ("order-time-fill-{0}-private.jsonl" -f (Get-Date -Format 'yyyyMMdd-HHmmssfff'))
$previousEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING = 'utf-8'
    Write-Host 'Backup first; add four nullable columns and fill only empty times in two drug orders.'
    & py -3.10 $scriptPath --backend $BackendPath --scope $scopePath `
        --backup-dir $BackupDir --output $outputPath --apply
    $code = $LASTEXITCODE
    Write-Host "Report: $outputPath"
    if ($code -ne 0) { throw 'Fill failed. Check error phase and data_committed in the report.' }
    Write-Host 'Fill committed and verified. Other order fields were preserved.' -ForegroundColor Green
}
finally { $env:PYTHONIOENCODING = $previousEncoding }
