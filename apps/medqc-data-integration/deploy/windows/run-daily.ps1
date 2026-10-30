param(
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [Parameter(Mandatory=$true)][string]$RuntimeConfig,
    [string]$InstallRoot = (Join-Path $PSScriptRoot '..\..'),
    [string]$StartDate,
    [string]$EndDate,
    [switch]$Replay
)
$ErrorActionPreference = 'Stop'
$allowed = @(
    'MEDQC_PG_DRIVER','MEDQC_PG_PASSFILE','MEDQC_CHUNK_SIZE','MEDQC_STALE_BATCH_MINUTES',
    'MEDQC_SOURCE_TIMEZONE','MEDQC_SOURCE_ADAPTER','MEDQC_CACHE_ODBC_DRIVER',
    'MEDQC_CACHE_HOST','MEDQC_CACHE_PORT','MEDQC_CACHE_NAMESPACE','MEDQC_CACHE_USER',
    'MEDQC_CACHE_PASSWORD_FILE','MEDQC_INGEST_PG_HOST','MEDQC_INGEST_PG_PORT',
    'MEDQC_INGEST_PG_DATABASE','MEDQC_INGEST_PG_USER','MEDQC_CDM_PG_HOST',
    'MEDQC_CDM_PG_PORT','MEDQC_CDM_PG_DATABASE','MEDQC_CDM_PG_USER'
)
$config = Get-Content -LiteralPath $RuntimeConfig -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($property in $config.PSObject.Properties) {
    if ($allowed -notcontains $property.Name) { throw 'Runtime config contains an unsupported key' }
}
if ($config.MEDQC_INGEST_PG_DATABASE -notmatch '^medqc_ingest_takeover_[0-9]{14}$' -or
    $config.MEDQC_CDM_PG_DATABASE -notmatch '^medqc_cdm_takeover_[0-9]{14}$') {
    throw 'Only independent takeover databases are allowed in this acceptance runner'
}
if ($config.MEDQC_INGEST_PG_HOST -ne '127.0.0.1' -or $config.MEDQC_CDM_PG_HOST -ne '127.0.0.1') {
    throw 'This acceptance runner requires local PostgreSQL'
}
$saved = @{}
foreach ($name in @($allowed + @('PYTHONPATH','PYTHONIOENCODING','PGPASSWORD'))) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$exitCode = 1
try {
    foreach ($property in $config.PSObject.Properties) {
        [Environment]::SetEnvironmentVariable($property.Name, [string]$property.Value, 'Process')
    }
    $env:PGPASSWORD = $null
    $env:PYTHONPATH = Join-Path ([IO.Path]::GetFullPath($InstallRoot)) 'src'
    $env:PYTHONIOENCODING = 'utf-8'
    $arguments = @('-m','medqc_ingest.cli','daily')
    if ($StartDate) { $arguments += @('--start',$StartDate) }
    if ($EndDate) { $arguments += @('--end',$EndDate) }
    if ($Replay) { $arguments += '--replay' }
    & $PythonPath @arguments
    $exitCode = $LASTEXITCODE
} finally {
    foreach ($name in $saved.Keys) {
        [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process')
    }
}
exit $exitCode
