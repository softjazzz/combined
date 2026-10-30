param(
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [Parameter(Mandatory=$true)][string]$DataRoot,
    [string]$PackageRoot = (Join-Path $PSScriptRoot '..\..'),
    [string]$PgBin = 'C:\Program Files\PostgreSQL\16\bin',
    [int]$Port = 5432,
    [string]$Stamp = (Get-Date -Format 'yyyyMMddHHmmss'),
    [string]$ExistingRuntimePasswordFile,
    [string]$CacheHost,
    [string]$CacheNamespace,
    [switch]$SkipLiveSourceCheck
)
$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this deployment script in an elevated administrator PowerShell'
}
if ($Stamp -notmatch '^[0-9]{14}$') { throw 'Invalid deployment stamp' }
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
$DataRoot = [IO.Path]::GetFullPath($DataRoot)
if ($DataRoot -notmatch '^[A-Za-z]:\\' -or $DataRoot.StartsWith($PackageRoot.TrimEnd('\') + '\',[StringComparison]::OrdinalIgnoreCase)) {
    throw 'DataRoot must be a local directory outside the frozen package'
}
if (Test-Path -LiteralPath $DataRoot) { throw 'DataRoot already exists; no overwrite is allowed' }
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Existing Python executable required' }
foreach ($command in @('createdb.exe','pg_dump.exe','pg_restore.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $PgBin $command))) { throw 'PostgreSQL tools missing' }
}
$version = & (Join-Path $PgBin 'pg_dump.exe') --version
if ($LASTEXITCODE -ne 0 -or "$version" -notmatch '\s16\.') { throw 'PostgreSQL 16 client tools required' }

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
function Escape-PgPass([string]$Text) {
    if ($Text.Contains("`r") -or $Text.Contains("`n")) { throw 'Multiline credentials are not supported' }
    return $Text.Replace('\','\\').Replace(':','\:')
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

New-Item -ItemType Directory -Path $DataRoot | Out-Null
Protect-Path $DataRoot $true
$Secrets = Join-Path $DataRoot 'secrets'
$Backups = Join-Path $DataRoot 'backups'
$Reports = Join-Path $DataRoot 'reports'
$PrivateLogs = Join-Path $DataRoot 'private-logs'
foreach ($path in @($Secrets,$Backups,$Reports,$PrivateLogs)) {
    New-Item -ItemType Directory -Path $path | Out-Null
    Protect-Path $path $true
}
$Ingest = 'medqc_ingest_takeover_' + $Stamp
$Cdm = 'medqc_cdm_takeover_' + $Stamp
$RestoreIngest = 'medqc_restore_takeover_' + $Stamp
$nextStamp = [datetime]::ParseExact($Stamp,'yyyyMMddHHmmss',[Globalization.CultureInfo]::InvariantCulture).AddSeconds(1).ToString('yyyyMMddHHmmss')
$RestoreCdm = 'medqc_restore_takeover_' + $nextStamp
$SourceDatabase = 'medqc_bundle_time_clone_20261029180906'
Write-ProtectedText (Join-Path $Reports 'database-plan.json') (@{
    ingest=$Ingest; cdm=$Cdm; restore_ingest=$RestoreIngest; restore_cdm=$RestoreCdm;
    source=$SourceDatabase; state='prepared'; source_writes=$false
} | ConvertTo-Json)

$admin = Get-Credential -UserName 'postgres' -Message 'Deployment administrator; used only for new databases and backups'
$runtimePassword = $null
if ($ExistingRuntimePasswordFile) {
    $oldAcl = Get-Acl -LiteralPath $ExistingRuntimePasswordFile
    if (-not $oldAcl.AreAccessRulesProtected -or $oldAcl.Access.Count -ne 2) { throw 'Existing runtime secret ACL is not protected' }
    foreach ($entry in $oldAcl.Access) {
        $sid = $entry.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        if (@('S-1-5-18','S-1-5-32-544') -notcontains $sid -or $entry.IsInherited -or
            $entry.AccessControlType -ne 'Allow' -or [int]$entry.FileSystemRights -ne 2032127) {
            throw 'Existing runtime secret ACL is not allowed'
        }
    }
    $runtimePassword = [IO.File]::ReadAllText($ExistingRuntimePasswordFile).Trim()
} else {
    $runtime = Get-Credential -UserName 'medqc_sync' -Message 'Existing medqc_sync password; this script will not change it'
    if ($runtime.UserName -ne 'medqc_sync') { throw 'This acceptance setup expects the existing medqc_sync login' }
    $runtimePassword = $runtime.GetNetworkCredential().Password
}
$AdminPass = Join-Path $Secrets 'deployment-admin.pgpass'
$RuntimePass = Join-Path $Secrets 'runtime.pgpass'
Write-ProtectedText $AdminPass ("127.0.0.1:${Port}:*:" + (Escape-PgPass $admin.UserName) + ':' + (Escape-PgPass $admin.GetNetworkCredential().Password) + "`n")
Write-ProtectedText $RuntimePass ("127.0.0.1:${Port}:*:medqc_sync:" + (Escape-PgPass $runtimePassword) + "`n")
$runtimePassword = $null
$savedEnv = @{}
foreach ($name in @('PGPASSFILE','PGPASSWORD','PYTHONPATH','PYTHONIOENCODING','MEDQC_PG_DRIVER')) {
    $savedEnv[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
}
try {
    $env:PGPASSFILE = $AdminPass
    $env:PGPASSWORD = $null
    $env:PYTHONPATH = Join-Path $PackageRoot 'src'
    $env:PYTHONIOENCODING = 'utf-8'
    # 使用客户机已有驱动，不联网、不安装依赖。
    & $PythonPath -c 'import psycopg2'
    if ($LASTEXITCODE -eq 0) { $env:MEDQC_PG_DRIVER = 'psycopg2' }
    else {
        & $PythonPath -c 'import psycopg'
        if ($LASTEXITCODE -ne 0) { throw 'No supported existing PostgreSQL driver' }
        $env:MEDQC_PG_DRIVER = 'psycopg'
    }
    Invoke-Checked $PythonPath @('-c','import sys,struct; assert sys.version_info[:2]==(3,10) and struct.calcsize(chr(80))==8')
    $pgArgs = @('--host','127.0.0.1','--port',[string]$Port,'--username',$admin.UserName,'--no-password')
    $sourceBackup = Join-Path $Backups 'source-before-takeover.dump'
    New-ProtectedFile $sourceBackup
    Invoke-Checked (Join-Path $PgBin 'pg_dump.exe') ($pgArgs + @('--format=custom','--file',$sourceBackup,$SourceDatabase))
    Invoke-Checked (Join-Path $PgBin 'pg_restore.exe') @('--list',$sourceBackup)
    foreach ($database in @($Ingest,$Cdm,$RestoreIngest,$RestoreCdm)) {
        Invoke-Checked (Join-Path $PgBin 'createdb.exe') ($pgArgs + @('--template','template0','--encoding','UTF8','--owner','medqc_owner',$database))
    }
    Run-Tool 'run_takeover.py' @('init','--database',$Ingest,'--user',$admin.UserName,'--passfile',$AdminPass,'--port',[string]$Port)
    Invoke-Checked (Join-Path $PgBin 'pg_restore.exe') ($pgArgs + @('--dbname',$Cdm,'--no-owner','--no-acl','--role','medqc_owner','--exit-on-error',$sourceBackup))
    Run-Tool 'run_takeover.py' @('grant-cdm','--database',$Cdm,'--user',$admin.UserName,'--passfile',$AdminPass,'--port',[string]$Port)
    Run-Tool 'run_takeover.py' @('import','--database',$Ingest,'--user',$admin.UserName,'--passfile',$AdminPass,'--source-passfile',$RuntimePass,'--port',[string]$Port,'--output',(Join-Path $Reports 'takeover-import.json'))
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
    if (-not $SkipLiveSourceCheck) {
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
    }
    $runtimeConfig = Join-Path $DataRoot 'runtime.json'
    Write-ProtectedText $runtimeConfig ($config | ConvertTo-Json)
    if (-not $SkipLiveSourceCheck) {
        Run-Tool 'run_configured_daily.py' @('--config',$runtimeConfig,'--dry-date','2026-10-28')
        Run-Tool 'run_configured_daily.py' @('--config',$runtimeConfig,'--start','2026-10-28','--end','2026-10-28','--replay')
        Run-Tool 'accept_takeover.py' @('publish-check','--ingest-db',$Ingest,'--cdm-db',$Cdm,'--user','medqc_sync','--passfile',$RuntimePass,'--port',[string]$Port,'--output',(Join-Path $Reports 'live-publish-check.json'))
    }
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
    [xml]$task = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'medqc-ingest-daily.example.xml') -Raw -Encoding UTF8
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
    [xml]$weekly = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'medqc-ingest-weekly.example.xml') -Raw -Encoding UTF8
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
        backup_restore=$true; cache_accessed=(-not $SkipLiveSourceCheck); scheduled_task_registered=$false;
        business_database_accessed=$false; contains_phi=$false; contains_raw_values=$false
        postgres_service_modified=$false; scheduled_task_xml_created=$true
    } | ConvertTo-Json)
    Write-Host 'TAKEOVER_ACCEPTANCE_PASS. Reports are local; do not export secrets, backups or private logs.'
} finally {
    foreach ($name in $savedEnv.Keys) { [Environment]::SetEnvironmentVariable($name,$savedEnv[$name],'Process') }
    $admin = $null
    $runtime = $null
}
