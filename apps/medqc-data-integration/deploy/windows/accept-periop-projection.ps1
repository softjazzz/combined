param(
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [Parameter(Mandatory=$true)][string]$RunRoot,
    [string]$PackageRoot = (Join-Path $PSScriptRoot '..\..'),
    [string]$AdminPassfile = 'D:\medqc\service-takeover-run-20261030205035\secrets\deployment-admin.pgpass',
    [string]$RuntimePassfile = 'D:\medqc\service-takeover-run-20261030205035\secrets\runtime.pgpass',
    [string]$PgBin = 'C:\Program Files\PostgreSQL\16\bin',
    [string]$DeploymentUser = 'postgres',
    [int]$Port = 5432
)
$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Use the existing elevated administrator PowerShell'
}
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
$RunRoot = [IO.Path]::GetFullPath($RunRoot)
function Assert-Acl([string]$Path) {
    $actual = Get-Acl -LiteralPath $Path
    if (-not $actual.AreAccessRulesProtected -or $actual.Access.Count -ne 2) { throw 'ACL mismatch' }
    $seen = @()
    foreach ($entry in $actual.Access) {
        $sid = $entry.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
        if (@('S-1-5-18','S-1-5-32-544') -notcontains $sid -or $entry.IsInherited -or
            $entry.AccessControlType -ne 'Allow' -or [int]$entry.FileSystemRights -ne 2032127) { throw 'ACL mismatch' }
        $seen += $sid
    }
    if (($seen | Select-Object -Unique).Count -ne 2) { throw 'Missing ACL principal' }
}
function Protect-Path([string]$Path) {
    $directory = Test-Path -LiteralPath $Path -PathType Container
    if ($directory) { $acl = New-Object Security.AccessControl.DirectorySecurity }
    else { $acl = New-Object Security.AccessControl.FileSecurity }
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($value in @('S-1-5-18','S-1-5-32-544')) {
        $sid = New-Object Security.Principal.SecurityIdentifier($value)
        $inherit = [Security.AccessControl.InheritanceFlags]::None
        if ($directory) { $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit' }
        $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid,
            [Security.AccessControl.FileSystemRights]::FullControl,$inherit,
            [Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
    Assert-Acl $Path
}
foreach ($path in @($PythonPath,$AdminPassfile,$RuntimePassfile,(Join-Path $PgBin 'pg_dump.exe'),(Join-Path $PgBin 'pg_restore.exe'))) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Required existing executable or passfile missing' }
}
Assert-Acl $AdminPassfile
Assert-Acl $RuntimePassfile
$manifest = Get-Content -LiteralPath (Join-Path $PackageRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.package_kind -ne 'periop-projection-acceptance-v2') { throw 'Wrong acceptance package' }
$verified = 0
foreach ($line in (Get-Content -LiteralPath (Join-Path $PackageRoot 'CHECKSUMS.txt') -Encoding UTF8)) {
    $parts = $line -split '  ',2
    if ($parts.Count -ne 2 -or $parts[0] -notmatch '^[0-9a-f]{64}$') { throw 'Invalid checksum line' }
    $path = [IO.Path]::GetFullPath((Join-Path $PackageRoot $parts[1]))
    if (-not $path.StartsWith($PackageRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase) -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $parts[0]) { throw 'Checksum mismatch' }
    $verified++
}
if ($verified -ne $manifest.inventory_count) { throw 'Inventory count mismatch' }
if (Test-Path -LiteralPath $RunRoot) { throw 'New run directory required; preserve failed runs' }
$null = New-Item -ItemType Directory -Path $RunRoot
Protect-Path $RunRoot
$log = Join-Path $RunRoot 'python.private.stderr.txt'
$null = New-Item -ItemType File -Path $log
Protect-Path $log
function Run-Python([string[]]$ArgumentList) {
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $PythonPath @ArgumentList 2>> $log
        $exit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $oldPreference }
    if ($exit -ne 0) { throw 'Python failed; preserve databases/run directory and report controlled failure.json only' }
}
$saved = @{}
foreach ($name in @('PGPASSWORD','PGSERVICE','PGSERVICEFILE','PGOPTIONS','PYTHONPATH','PYTHONIOENCODING')) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
}
try {
    $env:PGPASSWORD = $null
    $env:PGSERVICE = $null
    $env:PGSERVICEFILE = $null
    $env:PGOPTIONS = $null
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONPATH = Join-Path $PackageRoot 'tools'
    Run-Python @('-c','import sys,struct,psycopg2,sqlalchemy,alembic,dotenv; assert sys.version_info[:2]==(3,10) and struct.calcsize(chr(80))==8')
    Run-Python @('-m','unittest','discover','-s',(Join-Path $PackageRoot 'tests'),'-p','test_periop*.py','-v')
    $version = & (Join-Path $PgBin 'pg_dump.exe') --version
    if ($LASTEXITCODE -ne 0 -or "$version" -notmatch '\s16\.') { throw 'PostgreSQL 16 tools required' }
    $version = & (Join-Path $PgBin 'pg_restore.exe') --version
    if ($LASTEXITCODE -ne 0 -or "$version" -notmatch '\s16\.') { throw 'PostgreSQL 16 tools required' }
    $stamp = Get-Date -Format yyyyMMddHHmmss
    Run-Python @((Join-Path $PackageRoot 'tools\accept_periop_projection.py'),
        '--target',('medqc_periop_cdm_acceptance_'+$stamp),
        '--restore',('medqc_periop_restore_'+$stamp),
        '--admin-passfile',$AdminPassfile,'--runtime-passfile',$RuntimePassfile,
        '--admin-user',$DeploymentUser,'--port',[string]$Port,'--pg-major','16',
        '--pg-bin',$PgBin,'--output',(Join-Path $RunRoot 'acceptance'))
} finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
    Get-ChildItem -LiteralPath $RunRoot -Force -Recurse | ForEach-Object { Protect-Path $_.FullName }
}
Write-Host 'DONE. Export only acceptance\reports. Keep dump and private logs on this PC.'
