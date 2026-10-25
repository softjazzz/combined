param(
    [string]$BackendPath = 'D:\medqc\medqc-web-customer-R26.5\backend',
    [string]$BackupDir = 'D:\medqc\backups',
    [string]$PgBin = 'C:\Program Files\PostgreSQL\16\bin'
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
foreach ($requiredPath in @(
    (Join-Path $BackendPath '.env'),
    (Join-Path $BackendPath 'alembic.ini'),
    (Join-Path $BackendPath 'alembic\versions'),
    (Join-Path $PgBin 'pg_dump.exe'),
    (Join-Path $PgBin 'pg_restore.exe'),
    (Join-Path $PSScriptRoot 'upgrade_customer_pg_053.py')
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required path does not exist: $requiredPath"
    }
}

Write-Host 'Local PG only: full backup and archive verification, then upgrade to 053. No data fill, model or QC calls.'
py -3.10 (Join-Path $PSScriptRoot 'upgrade_customer_pg_053.py') `
    --backend $BackendPath --backup-dir $BackupDir --pg-bin $PgBin
if ($LASTEXITCODE -ne 0) {
    throw 'Upgrade did not finish verification. Keep the backup and report. Do not stamp or downgrade.'
}
