param(
    [string]$BackendPath = 'D:\medqc\medqc-web-customer-R26.4\backend',
    [string]$OutputDir = 'D:\medqc\orders27-reports'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$scriptPath = Join-Path $PSScriptRoot 'preview_orders27.py'
$scopePath = Join-Path $PSScriptRoot 'cases27-private.json'
foreach ($path in @($BackendPath, $scriptPath, $scopePath, (Join-Path $PSScriptRoot 'preview_order_time_fill.py'))) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing path: $path" }
}
$previousEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING = 'utf-8'
    Write-Host 'Read-only preview: 27 cases, drug and nondrug orders. No database writes, deployment, or model calls.'
    & py -3.10 $scriptPath --backend $BackendPath --scope $scopePath --output-dir $OutputDir
    if ($LASTEXITCODE -ne 0) { throw 'Preview incomplete. Send the error event; do not use partial reports as complete.' }
    Write-Host 'Complete. Send back the report ZIP shown in the done event. Nothing was changed in the databases.' -ForegroundColor Green
}
finally { $env:PYTHONIOENCODING = $previousEncoding }
