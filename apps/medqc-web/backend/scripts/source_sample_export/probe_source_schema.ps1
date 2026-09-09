param(
    [Parameter(Mandatory=$true)][string]$Server,
    [int]$Port = 5432,
    [Parameter(Mandatory=$true)][string]$Database,
    [Parameter(Mandatory=$true)][string]$Username,
    [string[]]$Schemas = @(),
    [string]$OutputDir = 'D:\medqc\source_schema_probe',
    [string]$PythonExe = 'py',
    [ValidateSet('disable','allow','prefer','require','verify-ca','verify-full')]
    [string]$SslMode = 'prefer',
    [int]$StatementTimeoutSeconds = 60
)
$ErrorActionPreference = 'Stop'
$pythonArgs = @()
if ($PythonExe -eq 'py') { $pythonArgs += '-3.10' }
& $PythonExe @pythonArgs -c 'import sys, psycopg2; assert sys.version_info >= (3, 10)'
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.10+ and psycopg2 are required. Set -PythonExe to the backend Python executable.'
}
Write-Host 'Python/psycopg2 ready'
$probeArgs = @(
    (Join-Path $PSScriptRoot 'probe_source_schema.py'),
    '--host', $Server, '--port', "$Port", '--database', $Database,
    '--username', $Username, '--output', $OutputDir, '--sslmode', $SslMode,
    '--statement-timeout', "$StatementTimeoutSeconds",
    '--dictionary', (Join-Path $PSScriptRoot 'cdm_dictionary.json')
)
foreach ($schemaName in $Schemas) { $probeArgs += @('--schema', $schemaName) }
# Password is requested inside Python getpass; never pass it as an argument.
& $PythonExe @pythonArgs @probeArgs
$probeExitCode = $LASTEXITCODE
if ($probeExitCode -ne 0) {
    Write-Warning "Probe incomplete/failed (exit $probeExitCode). Return the output ZIP and manifest if present."
}
exit $probeExitCode
