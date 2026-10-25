param(
    [string]$BackendPath = 'D:\medqc\medqc-web-customer-R26.5\backend',
    [string]$OutputDir = 'D:\medqc\failure-inspection-reports'
)
$ErrorActionPreference = 'Stop'
$diagnosticScript = Join-Path $PSScriptRoot 'inspect_transfusion_failures_readonly.py'
if (-not (Test-Path -LiteralPath (Join-Path $BackendPath '.env') -PathType Leaf)) {
    throw 'Backend .env was not found. Check BackendPath.'
}
if (-not (Test-Path -LiteralPath $diagnosticScript -PathType Leaf)) {
    throw 'The inspection Python script was not found beside this PowerShell script.'
}
$null = New-Item -ItemType Directory -Path $OutputDir -Force
$reportPath = Join-Path $OutputDir (
    'transfusion-failures-existing-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fffffff') + '.jsonl'
)
Write-Host 'READ ONLY: existing job, results, diagnostic archives and logs. No model calls or retries.'
Write-Host ('Report: ' + $reportPath)
& py -3.10 -u $diagnosticScript --backend $BackendPath --output $reportPath
if ($LASTEXITCODE -ne 0) {
    throw ('Read-only inspection failed. Send the safe error event from: ' + $reportPath)
}
Write-Host ('Inspection finished. Report: ' + $reportPath)
