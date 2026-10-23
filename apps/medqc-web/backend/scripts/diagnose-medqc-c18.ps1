param(
    [string]$BackendPath = 'D:\medqc\medqc-web-customer-R26.5\backend',
    [string]$OutputDir = 'D:\medqc\c18-diagnostic-reports',
    [switch]$Run,
    [string]$ReplayFile = ''
)
$ErrorActionPreference = 'Stop'
$null = New-Item -ItemType Directory -Path $OutputDir -Force
$report = Join-Path $OutputDir ('c18-diagnostic-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fffffff') + '.jsonl')
$script = Join-Path $PSScriptRoot 'diagnose_transfusion_pair.py'
Write-Host ('Report: ' + $report)
if ($Run -and $ReplayFile) { throw 'Choose Run or ReplayFile, not both.' }
if ($ReplayFile) {
    Write-Host 'OFFLINE REPLAY: C18 / 07-01-02 ONLY. No real model calls, database READ ONLY, no result saving.'
    & py -3.10 -u $script --backend $BackendPath --output $report --replay-calls $ReplayFile
} elseif ($Run) {
    Write-Host 'C18 / 07-01-02 ONLY: real model calls, database READ ONLY, no result saving or task retry.'
    & py -3.10 -u $script --backend $BackendPath --output $report --run
} else {
    Write-Host 'PREFLIGHT ONLY: no model calls, no database writes, no task retry.'
    & py -3.10 -u $script --backend $BackendPath --output $report
}
if ($LASTEXITCODE -ne 0) {
    throw ('Diagnostic stopped. Send the safe JSONL report only: ' + $report)
}
Write-Host ('Finished. Send the JSONL report only; keep the -private directory on the customer machine: ' + $report)
