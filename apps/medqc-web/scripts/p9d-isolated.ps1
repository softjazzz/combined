# PowerShell 5.1: ASCII only; never auto-connect production databases or models.
param(
  [ValidateSet('Verify','Probe','Run','Frontend','Backend','Migrate')][string]$Mode='Verify',
  [string]$Endpoint='http://127.0.0.1:18084/v1',
  [int]$FrontendPort=3109,
  [int]$BackendPort=8019,
  [switch]$AllowIsolatedDatabaseMigration
)
$ErrorActionPreference='Stop'
$packageRoot=Split-Path -Parent $PSScriptRoot
$python=Join-Path $packageRoot 'runtime\python.exe'
$backend=Join-Path $packageRoot 'backend'
$state=Join-Path $packageRoot 'isolated-state'
if(-not (Test-Path -LiteralPath $python -PathType Leaf)){throw 'Missing bundled runtime'}
if($Mode -in @('Verify','Probe','Run')){
  $command=@('-B',(Join-Path $backend 'scripts\p9d_isolated_smoke.py'),$Mode.ToLower(),
    '--handoff',(Join-Path $packageRoot 'provider-handoff'),'--state',$state,'--endpoint',$Endpoint)
  if($Mode -ne 'Verify'){
    if(-not $env:P9D_STRATA_API_KEY){throw 'Set P9D_STRATA_API_KEY explicitly first'}
    $command+='--live'
  }
  Push-Location $backend
  try{& $python @command; if($LASTEXITCODE -ne 0){throw 'Isolated check failed'}}finally{Pop-Location}
  exit
}
if($Mode -eq 'Frontend'){
  & $python -B (Join-Path $PSScriptRoot 'serve_dist_spa.py') --host 127.0.0.1 --port $FrontendPort `
    --dir (Join-Path $packageRoot 'frontend\dist') --api-target "http://127.0.0.1:$BackendPort"
  exit
}
# Full product UI is optional; require an explicitly NEW local test database.
if(-not $env:P9D_ISOLATED_DATABASE_URL){throw 'Set P9D_ISOLATED_DATABASE_URL to a NEW local p9d_* database'}
$uri=[Uri]$env:P9D_ISOLATED_DATABASE_URL
if($uri.Host -notin @('127.0.0.1','localhost') -or $uri.AbsolutePath -notmatch '^/p9d_[a-zA-Z0-9_]+$'){
  throw 'Only local, explicitly named p9d_* test databases are permitted'
}
if(Test-Path -LiteralPath (Join-Path $backend '.env')){throw 'No .env is permitted in isolated package'}
$env:DATABASE_URL=$env:P9D_ISOLATED_DATABASE_URL
$env:REMOTE_DB_URL=''
$env:DATA_SOURCE='pg'
$env:DB_SCHEMA_MODE='split'
$env:STRATA_HANDOFF_DIR=Join-Path $packageRoot 'provider-handoff'
$env:MEDQC_RESUME_QC_TASKS='false'
$env:HOMOLOGY_SYNC_ENABLED='false'
$env:MONGO_SYNC_ENABLED='false'
$env:SAMPLE_SYNC_INCREMENTAL_ENABLED='false'
$env:PRODUCT_ACTIVATION_REQUIRED='false'
$env:LLM_DISPATCH_MODE='direct'
$env:LLM_LOCAL_TOKEN_BUDGET_ENABLED='true'
$env:LX0609_TOKEN_SPLIT_ENABLED='true'
if(-not $env:JWT_SECRET){$env:JWT_SECRET=[Guid]::NewGuid().ToString('N')+[Guid]::NewGuid().ToString('N')}
Push-Location $backend
try{
  if($Mode -eq 'Migrate'){
    if(-not $AllowIsolatedDatabaseMigration){throw 'Explicit migration flag required for the NEW test database'}
    & $python -B -m alembic upgrade head
  }else{
    $env:MEDQC_STARTUP_MODE='acceptance'
    & $python -B -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort
  }
  if($LASTEXITCODE -ne 0){throw 'Isolated process failed'}
}finally{Pop-Location}
