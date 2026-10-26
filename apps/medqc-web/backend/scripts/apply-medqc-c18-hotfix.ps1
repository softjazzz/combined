param(
    [string]$BackendPath = 'D:\medqc\medqc-web-customer-R26.5\backend',
    [string]$ReplayFile = 'D:\medqc\c18-diagnostic-reports\c18-diagnostic-20261023-183626-4894162-private\C18-calls-private.json',
    [string]$BackupDir = 'D:\medqc\backups',
    [string]$OutputDir = 'D:\medqc\c18-hotfix-reports'
)
$ErrorActionPreference = 'Stop'
Write-Host 'Backup one backend source file, install the C18 assessment fix, then replay two recorded responses.'
Write-Host 'No real model calls, database writes, result saving, service restart, or full-case QC.'
& py -3.10 -u (Join-Path $PSScriptRoot 'apply_c18_assessment_hotfix.py') `
    --backend $BackendPath --replay-file $ReplayFile --backup-dir $BackupDir --output-dir $OutputDir
if ($LASTEXITCODE -ne 0) { throw 'Hotfix stopped. Send the safe error output; do not rerun QC yet.' }
