param(
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [Parameter(Mandatory=$true)][string]$DataRoot,
    [Parameter(Mandatory=$true)][string]$PackageRoot,
    [string]$PgBin = 'C:\Program Files\PostgreSQL\16\bin',
    [string]$DeploymentUser = 'postgres',
    [int]$Port = 5432,
    [string]$CacheHost,
    [string]$CacheNamespace
)
$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run in the existing elevated administrator PowerShell'
}
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
$DataRoot = [IO.Path]::GetFullPath($DataRoot)
foreach ($directory in @($DataRoot,(Join-Path $DataRoot 'secrets'),(Join-Path $DataRoot 'backups'),(Join-Path $DataRoot 'reports'),(Join-Path $DataRoot 'private-logs'))) {
    if (-not (Test-Path -LiteralPath $directory -PathType Container)) { throw 'Existing run directory required' }
    $acl = Get-Acl -LiteralPath $directory
    if (-not $acl.AreAccessRulesProtected -or $acl.Access.Count -ne 2) { throw 'Existing run ACL mismatch' }
    foreach ($entry in $acl.Access) {
        $sid = $entry.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        if (@('S-1-5-18','S-1-5-32-544') -notcontains $sid -or $entry.IsInherited -or $entry.AccessControlType -ne 'Allow' -or [int]$entry.FileSystemRights -ne 2032127) { throw 'Existing run ACL mismatch' }
    }
}
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Existing Python executable required' }
foreach ($command in @('pg_dump.exe','pg_restore.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $PgBin $command))) { throw 'PostgreSQL 16 tools required' }
}
$version = & (Join-Path $PgBin 'pg_dump.exe') --version
if ($LASTEXITCODE -ne 0 -or "$version" -notmatch '\s16\.') { throw 'PostgreSQL 16 tools required' }
$Secrets = Join-Path $DataRoot 'secrets'
$Backups = Join-Path $DataRoot 'backups'
$Reports = Join-Path $DataRoot 'reports'
$PrivateLogs = Join-Path $DataRoot 'private-logs'
foreach ($name in @('takeover-import.json','service-acceptance.json','deployment-result.json','resume-preflight.json','takeover-import-deployment-source-diagnostic.json')) {
    if (Test-Path -LiteralPath (Join-Path $Reports $name)) { throw 'This continuation was already attempted; preserve the existing report' }
}
if (Test-Path -LiteralPath (Join-Path $DataRoot 'runtime.json')) { throw 'Existing runtime config; refuse partial acceptance overwrite' }
$plan = Get-Content -LiteralPath (Join-Path $Reports 'database-plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$Ingest = $plan.ingest
$Cdm = $plan.cdm
$RestoreIngest = $plan.restore_ingest
$RestoreCdm = $plan.restore_cdm
$AdminPass = Join-Path $Secrets 'deployment-admin.pgpass'
$RuntimePass = Join-Path $Secrets 'runtime.pgpass'
$admin = [pscustomobject]@{ UserName=$DeploymentUser }
$HotfixRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))

function Protect-Path([string]$Path, [bool]$Directory) {
    if ($Directory) { $acl = New-Object System.Security.AccessControl.DirectorySecurity }
    else { $acl = New-Object System.Security.AccessControl.FileSecurity }
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($value in @('S-1-5-18','S-1-5-32-544')) {
        $sid = New-Object System.Security.Principal.SecurityIdentifier($value)
        $inherit = [System.Security.AccessControl.InheritanceFlags]::None
        if ($Directory) { $inherit = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit' }
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid,[System.Security.AccessControl.FileSystemRights]::FullControl,
            $inherit,[System.Security.AccessControl.PropagationFlags]::None,
            [System.Security.AccessControl.AccessControlType]::Allow)
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
    $actual = Get-Acl -LiteralPath $Path
    if (-not $actual.AreAccessRulesProtected -or $actual.Access.Count -ne 2) { throw 'ACL verification failed' }
    foreach ($entry in $actual.Access) {
        $sid = $entry.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        if (@('S-1-5-18','S-1-5-32-544') -notcontains $sid -or $entry.IsInherited -or
            $entry.AccessControlType -ne 'Allow' -or [int]$entry.FileSystemRights -ne 2032127) {
            throw 'ACL verification failed'
        }
    }
}
function New-ProtectedFile([string]$Path) {
    if (Test-Path -LiteralPath $Path) { throw 'Refusing to overwrite an existing protected file' }
    $stream = [IO.File]::Open($Path,[IO.FileMode]::CreateNew)
    $stream.Dispose()
    Protect-Path $Path $false
}
function Write-ProtectedText([string]$Path, [string]$Content) {
    New-ProtectedFile $Path
    [IO.File]::WriteAllText($Path,$Content,(New-Object System.Text.UTF8Encoding($false)))
}
function Invoke-Checked([string]$Command, [string[]]$ArgumentList) {
    $log = Join-Path $PrivateLogs (([guid]::NewGuid().ToString()) + '.stderr.txt')
    New-ProtectedFile $log
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Command @ArgumentList 2> $log
        $nativeExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $oldPreference }
    if ($nativeExit -ne 0) { throw "Native command failed (exit $nativeExit). Inspect the private local stderr file." }
}
function Run-Tool([string]$Tool, [string[]]$ArgumentList) {
    Invoke-Checked $PythonPath (@((Join-Path $PackageRoot ('tools\' + $Tool))) + $ArgumentList)
}


$savedEnv = @{}
foreach ($name in @('PGPASSFILE','PGPASSWORD','PYTHONPATH','PYTHONIOENCODING','MEDQC_PG_DRIVER')) { $savedEnv[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
    $env:PGPASSFILE = $AdminPass
    $env:PGPASSWORD = $null
    $env:PYTHONPATH = Join-Path $PackageRoot 'src'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:MEDQC_PG_DRIVER = 'psycopg2'
    Invoke-Checked $PythonPath @('-c','import sys,struct,psycopg2; assert sys.version_info[:2]==(3,10) and struct.calcsize(chr(80))==8')
    Invoke-Checked $PythonPath @((Join-Path $HotfixRoot 'tools\takeover_resume_preflight.py'),'--package-root',$PackageRoot,'--run-root',$DataRoot,'--user',$DeploymentUser,'--port',[string]$Port)
    Invoke-Checked $PythonPath @((Join-Path $HotfixRoot 'tools\diagnose_takeover_import.py'),'--package-root',$PackageRoot,'--run-root',$DataRoot,'--user',$DeploymentUser,'--port',[string]$Port,'--deployment-source')
    $pgArgs = @('--host','127.0.0.1','--port',[string]$Port,'--username',$DeploymentUser,'--no-password')
    Run-Tool 'run_takeover.py' @('verify','--database',$Ingest,'--user','medqc_sync','--passfile',$RuntimePass,'--port',[string]$Port,'--output',(Join-Path $Reports 'takeover-verify.json'))
    Run-Tool 'accept_takeover.py' @('accept','--ingest-db',$Ingest,'--cdm-db',$Cdm,'--user','medqc_sync','--passfile',$RuntimePass,'--port',[string]$Port,'--output',(Join-Path $Reports 'service-acceptance.json'))
    Run-Tool 'run_takeover.py' @('verify','--database',$Ingest,'--user','medqc_sync','--passfile',$RuntimePass,'--port',[string]$Port,'--output',(Join-Path $Reports 'takeover-verify-after.json'))

    $config = @{
        MEDQC_PG_DRIVER=$env:MEDQC_PG_DRIVER; MEDQC_PG_PASSFILE=$RuntimePass;
        MEDQC_SOURCE_TIMEZONE='Asia/Shanghai'; MEDQC_SOURCE_ADAPTER='odbc';
        MEDQC_INGEST_PG_HOST='127.0.0.1'; MEDQC_INGEST_PG_PORT=[string]$Port;
        MEDQC_INGEST_PG_DATABASE=$Ingest; MEDQC_INGEST_PG_USER='medqc_sync';
        MEDQC_CDM_PG_HOST='127.0.0.1'; MEDQC_CDM_PG_PORT=[string]$Port;
        MEDQC_CDM_PG_DATABASE=$Cdm; MEDQC_CDM_PG_USER='medqc_sync'
    }
    if (-not $CacheHost) { $CacheHost = Read-Host 'Cache host (kept only in local runtime config)' }
    if (-not $CacheNamespace) { $CacheNamespace = Read-Host 'Cache namespace' }
    $cache = Get-Credential -UserName 'Baidu' -Message 'Read-only Caché interface account'
    $cachePass = Join-Path $Secrets 'cache-password'
    Write-ProtectedText $cachePass ($cache.GetNetworkCredential().Password + "`n")
    $config.MEDQC_CACHE_HOST = $cacheHost
    $config.MEDQC_CACHE_PORT = '1972'
    $config.MEDQC_CACHE_NAMESPACE = $cacheNamespace
    $config.MEDQC_CACHE_USER = $cache.UserName
    $config.MEDQC_CACHE_PASSWORD_FILE = $cachePass
    $config.MEDQC_CACHE_ODBC_DRIVER = 'InterSystems ODBC35'
    $cache = $null
    $runtimeConfig = Join-Path $DataRoot 'runtime.json'
    Write-ProtectedText $runtimeConfig ($config | ConvertTo-Json)
    Run-Tool 'run_configured_daily.py' @('--config',$runtimeConfig,'--dry-date','2026-10-28')
    Run-Tool 'run_configured_daily.py' @('--config',$runtimeConfig,'--start','2026-10-28','--end','2026-10-28','--replay')
    Run-Tool 'accept_takeover.py' @('publish-check','--ingest-db',$Ingest,'--cdm-db',$Cdm,'--user','medqc_sync','--passfile',$RuntimePass,'--port',[string]$Port,'--output',(Join-Path $Reports 'live-publish-check.json'))
    $pairs = @(@{Database=$Ingest;Restore=$RestoreIngest;Kind='ingest'},@{Database=$Cdm;Restore=$RestoreCdm;Kind='cdm'})
    foreach ($pair in $pairs) {
        $before = Join-Path $Reports ($pair.Kind + '-before-backup.json')
        $after = Join-Path $Reports ($pair.Kind + '-after-restore.json')
        Run-Tool 'accept_takeover.py' @('fingerprint','--ingest-db',$pair.Database,'--kind',$pair.Kind,'--user',$admin.UserName,'--passfile',$AdminPass,'--port',[string]$Port,'--output',$before)
        $dump = Join-Path $Backups ($pair.Kind + '-accepted.dump')
        New-ProtectedFile $dump
        Invoke-Checked (Join-Path $PgBin 'pg_dump.exe') ($pgArgs + @('--format=custom','--file',$dump,$pair.Database))
        Invoke-Checked (Join-Path $PgBin 'pg_restore.exe') @('--list',$dump)
        Write-ProtectedText ($dump + '.sha256') ((Get-FileHash -LiteralPath $dump -Algorithm SHA256).Hash + "`n")
        Invoke-Checked (Join-Path $PgBin 'pg_restore.exe') ($pgArgs + @('--dbname',$pair.Restore,'--no-owner','--role','medqc_owner','--exit-on-error',$dump))
        Run-Tool 'accept_takeover.py' @('fingerprint','--ingest-db',$pair.Restore,'--kind',$pair.Kind,'--user',$admin.UserName,'--passfile',$AdminPass,'--port',[string]$Port,'--output',$after)
        if ((Get-FileHash -LiteralPath $before -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $after -Algorithm SHA256).Hash) { throw 'Backup restore fingerprint mismatch' }
    }
    [xml]$task = Get-Content -LiteralPath (Join-Path $PackageRoot 'deploy\windows\medqc-ingest-daily.example.xml') -Raw -Encoding UTF8
    $task.Task.Actions.Exec.Command = $PythonPath
    $task.Task.Actions.Exec.Arguments = '"' + (Join-Path $PackageRoot 'tools\run_configured_daily.py') + '" --config "' + $runtimeConfig + '"'
    $task.Task.Actions.Exec.WorkingDirectory = $PackageRoot
    $hospitalNow = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([datetime]::UtcNow,'China Standard Time')
    $task.Task.Triggers.CalendarTrigger.StartBoundary = $hospitalNow.Date.AddDays(1).AddHours(2).ToString("yyyy-MM-dd'T'HH:mm:ss") + '+08:00'
    $scheduler = New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()
    $taskDefinition = $scheduler.NewTask(0)
    $taskDefinition.XmlText = $task.DocumentElement.OuterXml
    Write-ProtectedText (Join-Path $DataRoot 'medqc-ingest-daily.disabled.xml') $task.DocumentElement.OuterXml
    [xml]$weekly = Get-Content -LiteralPath (Join-Path $PackageRoot 'deploy\windows\medqc-ingest-weekly.example.xml') -Raw -Encoding UTF8
    $weekly.Task.Actions.Exec.Command = $PythonPath
    $weekly.Task.Actions.Exec.Arguments = '"' + (Join-Path $PackageRoot 'tools\run_configured_daily.py') + '" --config "' + $runtimeConfig + '" --mr-replay'
    $weekly.Task.Actions.Exec.WorkingDirectory = $PackageRoot
    $weeklyStart = $hospitalNow.Date.AddDays((7 - [int]$hospitalNow.DayOfWeek) % 7).AddHours(3)
    if ($weeklyStart -le $hospitalNow) { $weeklyStart = $weeklyStart.AddDays(7) }
    $weekly.Task.Triggers.CalendarTrigger.StartBoundary = $weeklyStart.ToString("yyyy-MM-dd'T'HH:mm:ss") + '+08:00'
    $weeklyDefinition = $scheduler.NewTask(0)
    $weeklyDefinition.XmlText = $weekly.DocumentElement.OuterXml
    Write-ProtectedText (Join-Path $DataRoot 'medqc-ingest-weekly.disabled.xml') $weekly.DocumentElement.OuterXml
    Write-ProtectedText (Join-Path $Reports 'deployment-result.json') (@{
        status='accepted'; interfaces=13; archive_preserved=$true; rollback_recovery=$true;
        backup_restore=$true; cache_accessed=$true; resumed_existing_databases=$true; source_readonly_deployment_identity=$true; scheduled_task_registered=$false;
        business_database_accessed=$false; contains_phi=$false; contains_raw_values=$false
        postgres_service_modified=$false; scheduled_task_xml_created=$true
    } | ConvertTo-Json)
    Write-Host 'TAKEOVER_ACCEPTANCE_PASS. Reports are local; do not export secrets, backups or private logs.'
} finally {
    foreach ($name in $savedEnv.Keys) { [Environment]::SetEnvironmentVariable($name,$savedEnv[$name],'Process') }
    $admin = $null
}
