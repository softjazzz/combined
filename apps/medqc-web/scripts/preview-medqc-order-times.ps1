param(
    [string]$BackendPath = 'D:\medqc\medqc-web-customer-R26.4\backend',
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$pythonScript = Join-Path $PSScriptRoot 'preview_order_time_fill.py'
$scopeFile = Join-Path $PSScriptRoot 'order-time-scope-private.json'
foreach ($path in @($BackendPath, $pythonScript, $scopeFile)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing path: $path" }
}
if (-not $OutputPath) {
    $OutputPath = Join-Path $PSScriptRoot ("order-time-preview-{0}-private.jsonl" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
$previousEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING = 'utf-8'
    Write-Host 'Read-only preview: C17 and C22, two drug orders. No database writes or model calls.'
    & py -3.10 $pythonScript --backend $BackendPath --scope $scopeFile --output $OutputPath
    $code = $LASTEXITCODE
    Write-Host "Report: $OutputPath"
    if ($code -eq 2) {
        Write-Host 'Preview finished with missing columns or conflicts. Review the report before any fill.' -ForegroundColor Yellow
    }
    elseif ($code -ne 0) { throw 'Preview failed. Send back the error event; do not include credentials.' }
    else { Write-Host 'Preview complete. Nothing was written to the database.' -ForegroundColor Green }
}
finally { $env:PYTHONIOENCODING = $previousEncoding }
