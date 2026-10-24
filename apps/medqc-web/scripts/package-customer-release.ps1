# Windows PowerShell 5.1 decodes BOM-less scripts as ANSI; keep this file ASCII-only.
param(
  [string]$OutputRoot = "D:\LLM\LX888\release",
  [switch]$SkipBuild,
  [string]$InventoryPath = "",
  [switch]$AllowDirty,
  [int]$BundledActivationMonths = 3,
  [string]$BundledActivationCustomer = ("MedQC " + [string]::Concat([char[]]@(0x5BA2, 0x6237, 0x8BD5, 0x7528, 0x6388, 0x6743))),
  [string]$ActivationPrivateKeyPath = "",
  [switch]$SkipBundledActivation
)

$ErrorActionPreference = "Stop"

if ($SkipBuild) {
  throw "-SkipBuild is not supported: customer packages must rebuild frontend JavaScript with the current build identity. Run again without -SkipBuild (also required with -AllowDirty)."
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $projectRoot)
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$releaseName = if ($AllowDirty) {
  "NON-RELEASABLE-medqc-web-customer-$stamp"
} else {
  "medqc-web-customer-$stamp"
}
$releaseDir = Join-Path $OutputRoot $releaseName
$backendDir = Join-Path $releaseDir "backend"
$frontendDir = Join-Path $releaseDir "frontend"
$toolsDir = Join-Path $releaseDir "tools"
$docsDir = Join-Path $releaseDir "docs"
$bundledActivationSummary = "disabled by -SkipBundledActivation"
$bundledActivationNote = "- This package contains no bundled activation; activate manually in System Settings."

if (-not $SkipBundledActivation) {
  if ($BundledActivationMonths -lt 1 -or $BundledActivationMonths -gt 24) {
    throw "BundledActivationMonths must be between 1 and 24."
  }
  if ([string]::IsNullOrWhiteSpace($BundledActivationCustomer)) {
    throw "BundledActivationCustomer must not be empty."
  }
  if ([string]::IsNullOrWhiteSpace($ActivationPrivateKeyPath)) {
    $ActivationPrivateKeyPath = Join-Path $repoRoot "secrets\medqc-offline-activation-private.pem"
  }
  if (-not (Test-Path -LiteralPath $ActivationPrivateKeyPath -PathType Leaf)) {
    throw "Bundled activation requires the issuer private key. Use -ActivationPrivateKeyPath or explicitly pass -SkipBundledActivation."
  }
}

function Write-Step([string]$message) {
  Write-Host "[package] $message" -ForegroundColor Cyan
}

function Test-NameMatch([string]$name, [string[]]$patterns) {
  foreach ($pattern in $patterns) {
    if ($name -like $pattern) {
      return $true
    }
  }
  return $false
}

function Copy-TreeExclude(
  [string]$source,
  [string]$destination,
  [string[]]$excludeDirs,
  [string[]]$excludeFiles,
  [string[]]$excludeDirPatterns = @(),
  [string[]]$excludeFilePatterns = @()
) {
  Get-ChildItem -LiteralPath $source -Force | ForEach-Object {
    $name = $_.Name
    if ($_.PSIsContainer) {
      # Diagnostics may contain clinical text; exclude runtime data, keep services/qc_diagnostics source.
      if ($_.FullName -match '[\\/]storage[\\/]qc_diagnostics$') {
        return
      }
      if (($excludeDirs -contains $name) -or (Test-NameMatch -name $name -patterns $excludeDirPatterns)) {
        return
      }
      $target = Join-Path $destination $name
      New-Item -ItemType Directory -Force -Path $target | Out-Null
      Copy-TreeExclude `
        -source $_.FullName `
        -destination $target `
        -excludeDirs $excludeDirs `
        -excludeFiles $excludeFiles `
        -excludeDirPatterns $excludeDirPatterns `
        -excludeFilePatterns $excludeFilePatterns
      return
    }
    if (($excludeFiles -contains $name) -or (Test-NameMatch -name $name -patterns $excludeFilePatterns)) {
      return
    }
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $destination $name) -Force
  }
}

function Assert-NoReleaseForbiddenContent([string]$path) {
  $forbiddenPaths = @(
    "backend\.env",
    "backend\data\vector",
    "backend\data\manual_qc_runs",
    "backend\app\storage\qc_diagnostics",
    "backend\scripts\build_icd_vector_index.py"
  )
  foreach ($relative in $forbiddenPaths) {
    $candidate = Join-Path $path $relative
    if (Test-Path -LiteralPath $candidate) {
      throw "Forbidden release content found: $relative"
    }
  }

  $forbiddenFiles = Get-ChildItem -LiteralPath $path -Recurse -File -Force | Where-Object {
    $_.Name -like "*.pyc" -or
    $_.Name -like "*.pkl" -or
    $_.Name -like "*.log" -or
    $_.Name -like "*.out.log" -or
    $_.Name -like "*.err.log" -or
    $_.Name -eq ".coverage" -or
    $_.Name -eq "coverage.xml" -or
    $_.Name -eq "generate_medqc_activation_code.py" -or
    $_.Name -eq "product_activation_state.json" -or
    $_.Name -eq "activation.json" -or
    $_.Name -like ".activation-*.tmp"
  }
  if ($forbiddenFiles.Count -gt 0) {
    $sample = ($forbiddenFiles | Select-Object -First 10 | ForEach-Object { $_.FullName }) -join "`n"
    throw "Forbidden release files found:`n$sample"
  }

  $privateKeyFiles = @(
    Get-ChildItem -LiteralPath $path -Recurse -File -Force |
      Where-Object { $_.Extension -in @(".pem", ".key") } |
      Select-String -SimpleMatch "PRIVATE KEY" -List
  )
  if ($privateKeyFiles.Count -gt 0) {
    $sample = ($privateKeyFiles | Select-Object -First 10 | ForEach-Object { $_.Path }) -join "`n"
    throw "Private key material found in release package:`n$sample"
  }

  $backendRoot = Join-Path $path "backend"
  $allowedBackendRootEntries = @(
    ".env.example",
    "alembic",
    "alembic.ini",
    "app",
    "config",
    "data",
    "requirements.txt",
    "services",
    "start_dev_backend.ps1"
  )
  $unexpectedBackendRootEntries = Get-ChildItem -LiteralPath $backendRoot -Force | Where-Object {
    $_.Name -notin $allowedBackendRootEntries
  }
  if ($unexpectedBackendRootEntries.Count -gt 0) {
    $sample = ($unexpectedBackendRootEntries | Select-Object -First 10 | ForEach-Object { $_.Name }) -join "`n"
    throw "Unexpected backend root entries found in release package:`n$sample"
  }

  $frontendDist = Join-Path $path "frontend\dist"
  if (Test-Path -LiteralPath $frontendDist) {
    $forbiddenApiHits = @(
      Get-ChildItem -LiteralPath $frontendDist -Recurse -File -Force |
        Where-Object { $_.Extension -in @(".js", ".css", ".html", ".json") } |
        Select-String -SimpleMatch -Pattern @("api.medqc.com", "124.220.6.136") -List
    )
    if ($forbiddenApiHits.Count -gt 0) {
      $sample = ($forbiddenApiHits | Select-Object -First 10 | ForEach-Object { $_.Path }) -join "`n"
      throw "Forbidden public API domain found in customer frontend:`n$sample"
    }
  }
}

Write-Step "Verify release source state"
if ([string]::IsNullOrWhiteSpace($InventoryPath)) {
  $inventoryCandidate = Get-ChildItem `
    -LiteralPath (Join-Path $projectRoot "docs\releases") `
    -Filter "change-inventory.json" `
    -File `
    -Recurse `
    -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1
  if ($null -eq $inventoryCandidate) {
    throw "Release inventory not found. Pass -InventoryPath explicitly."
  }
  $resolvedInventoryPath = $inventoryCandidate.FullName
} else {
  $candidate = if ([System.IO.Path]::IsPathRooted($InventoryPath)) {
    $InventoryPath
  } else {
    Join-Path $projectRoot $InventoryPath
  }
  $resolvedInventoryPath = (Resolve-Path -LiteralPath $candidate).Path
}

$sourceVerifyArgs = @(
  (Join-Path $projectRoot "scripts\verify_release_source.py"),
  "--repo",
  $projectRoot,
  "--inventory",
  $resolvedInventoryPath
)
if ($AllowDirty) {
  $sourceVerifyArgs += "--allow-dirty"
}
& python @sourceVerifyArgs
if ($LASTEXITCODE -ne 0) {
  throw "Release source verification failed."
}
$verifiedSourceCommit = & git -c "safe.directory=$($repoRoot.Replace('\', '/'))" -C $repoRoot rev-parse HEAD
if ($LASTEXITCODE -ne 0) {
  throw "Cannot freeze release source commit."
}
$verifiedSourceCommit = $verifiedSourceCommit.Trim()

if (-not $SkipBuild) {
  Write-Step "Build frontend dist in customer mode"
  $previousBuildId = $env:VITE_MEDQC_BUILD_ID
  $previousGitCommit = $env:VITE_MEDQC_GIT_COMMIT
  Push-Location $projectRoot
  try {
    $env:VITE_MEDQC_BUILD_ID = $releaseName
    $env:VITE_MEDQC_GIT_COMMIT = $verifiedSourceCommit
    npx vite build --mode customer --config vite.customer.config.mjs --configLoader native
    if ($LASTEXITCODE -ne 0) {
      throw "Customer frontend build failed; refusing to package stale artifacts."
    }
  }
  finally {
    $env:VITE_MEDQC_BUILD_ID = $previousBuildId
    $env:VITE_MEDQC_GIT_COMMIT = $previousGitCommit
    Pop-Location
  }
}

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "dist\index.html") -PathType Leaf)) {
  throw "Customer frontend dist/index.html is missing."
}
$frontendBuildInfoPath = Join-Path $projectRoot "dist\build-info.json"
if (-not (Test-Path -LiteralPath $frontendBuildInfoPath -PathType Leaf)) {
  throw "Customer frontend build-info.json is missing; refusing to package unmarked artifacts."
}
$frontendBuildInfo = Get-Content -LiteralPath $frontendBuildInfoPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($frontendBuildInfo.build_id -cne $releaseName -or $frontendBuildInfo.git_commit -cne $verifiedSourceCommit) {
  throw "Customer frontend build identity does not match this package; refusing to package stale artifacts."
}

Write-Step "Prepare release directory $releaseDir"
if (Test-Path -LiteralPath $releaseDir) {
  Remove-Item -LiteralPath $releaseDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $releaseDir, $backendDir, $frontendDir, $toolsDir, $docsDir | Out-Null

Write-Step "Copy frontend build artifacts"
Copy-Item -LiteralPath (Join-Path $projectRoot "dist") -Destination (Join-Path $frontendDir "dist") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\serve_dist_spa.py") -Destination (Join-Path $toolsDir "serve_dist_spa.py") -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\customer-db-preflight.ps1") -Destination (Join-Path $toolsDir "customer-db-preflight.ps1") -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\accept-medqc-release.ps1") -Destination (Join-Path $toolsDir "accept-medqc-release.ps1") -Force
foreach ($acceptanceScript in @('verify_p0_material_chain.py','repair_p0_materials.py','recover_p0_failed_results.py')) {
  Copy-Item -LiteralPath (Join-Path $projectRoot ("backend\scripts\" + $acceptanceScript)) -Destination (Join-Path $toolsDir $acceptanceScript) -Force
}
Write-Step "Remove frontend font files (use customer/system fonts)"
$distFontsDir = Join-Path $frontendDir "dist\fonts"
if (Test-Path -LiteralPath $distFontsDir) {
  Remove-Item -LiteralPath $distFontsDir -Recurse -Force
}

Write-Step "Copy backend runtime allowlist (exclude development scripts and artifacts)"
$backendSourceDir = Join-Path $projectRoot "backend"
$activationPublicKeySource = Join-Path $backendSourceDir "app\data\product_activation_public_key.pem"
if (-not (Test-Path -LiteralPath $activationPublicKeySource -PathType Leaf)) {
  throw "Required product activation public key is missing: product_activation_public_key.pem"
}
$backendRuntimeDirectories = @("alembic", "app", "config", "data")
$backendRuntimeFiles = @(
  ".env.example",
  "alembic.ini",
  "requirements.txt",
  "start_dev_backend.ps1"
)
$backendRuntimeServiceFiles = @("__init__.py", "pdf_parser.py")
$backendExcludeDirs = @(
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "htmlcov",
    ".ruff_cache",
    ".venv",
    "venv",
    "logs",
    ".runtime-logs",
    "release-gate-artifacts",
    "tests",
    "uploads",
    "manual_qc_runs",
    "sample_pool_uploads",
    "vector"
  )
$backendExcludeFiles = @(
    ".coverage",
    ".env",
    "coverage.xml",
    "runtime_build.json",
    "build_icd_vector_index.py",
    "icd_vector_retrieval_demo.py"
  )
$backendExcludeDirPatterns = @("tmp*", "__pycache__")
$backendExcludeFilePatterns = @(
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.out.log",
    "*.err.log",
    "*.pkl",
    "*.pickle",
    "*.db",
    "*.db-journal",
    "*.sqlite",
    "*.sqlite-journal",
    "*.sqlite3",
    "*.sqlite3-journal",
    "*.faiss",
    "*.index",
    "test_*.py",
    "tmp_*",
    "debug_*",
    "probe_*"
  )

foreach ($directoryName in $backendRuntimeDirectories) {
  $sourceDirectory = Join-Path $backendSourceDir $directoryName
  if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) {
    throw "Required backend runtime directory is missing: $directoryName"
  }
  $destinationDirectory = Join-Path $backendDir $directoryName
  New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
  Copy-TreeExclude `
    -source $sourceDirectory `
    -destination $destinationDirectory `
    -excludeDirs $backendExcludeDirs `
    -excludeFiles $backendExcludeFiles `
    -excludeDirPatterns $backendExcludeDirPatterns `
    -excludeFilePatterns $backendExcludeFilePatterns
}

foreach ($fileName in $backendRuntimeFiles) {
  $sourceFile = Join-Path $backendSourceDir $fileName
  if (-not (Test-Path -LiteralPath $sourceFile -PathType Leaf)) {
    throw "Required backend runtime file is missing: $fileName"
  }
  Copy-Item -LiteralPath $sourceFile -Destination (Join-Path $backendDir $fileName) -Force
}

$customerLauncherPath = Join-Path $backendDir "start_dev_backend.ps1"
$customerLauncherSource = Get-Content -LiteralPath $customerLauncherPath -Raw
# 客户包不得把开发默认密钥注入进程并遮蔽 .env。
$developmentSecretBlock = 'if (-not $env:JWT_SECRET) {' + "`n" + '    $env:JWT_SECRET = "dev-secret"' + "`n" + '}'
$customerLauncherSource = $customerLauncherSource.Replace("`r`n", "`n")
if (-not $customerLauncherSource.Contains($developmentSecretBlock)) {
  throw "Cannot locate development JWT fallback in launcher."
}
$customerLauncherSource = $customerLauncherSource.Replace($developmentSecretBlock, '')
$activationEnvironmentLine = '$env:PRODUCT_ACTIVATION_REQUIRED = "true"'
if (-not $customerLauncherSource.Contains($activationEnvironmentLine)) {
  $launcherMarker = '$ErrorActionPreference = "Stop"'
  if (-not $customerLauncherSource.Contains($launcherMarker)) {
    throw "Customer backend launcher is missing the expected initialization marker."
  }
  $customerLauncherSource = $customerLauncherSource.Replace(
    $launcherMarker,
    "$launcherMarker`n`n$activationEnvironmentLine"
  )
  [System.IO.File]::WriteAllText(
    $customerLauncherPath,
    $customerLauncherSource,
    (New-Object System.Text.UTF8Encoding($false))
  )
}

$activationPublicKeyTarget = Join-Path $backendDir "app\data\product_activation_public_key.pem"
if (-not (Test-Path -LiteralPath $activationPublicKeyTarget -PathType Leaf)) {
  throw "Customer package is missing product_activation_public_key.pem"
}

if (-not $SkipBundledActivation) {
  Write-Step "Issue default three-month bundled activation"
  $activationIssuerScript = Join-Path $projectRoot "scripts\generate_medqc_activation_code.py"
  if (-not (Test-Path -LiteralPath $activationIssuerScript -PathType Leaf)) {
    throw "Activation issuer script is missing."
  }
  $activationIssuedAt = [DateTimeOffset]::UtcNow
  $activationExpiresAt = $activationIssuedAt.AddMonths($BundledActivationMonths).ToString(
    "yyyy-MM-ddTHH:mm:ssZ",
    [System.Globalization.CultureInfo]::InvariantCulture
  )
  $activationSerial = "BUNDLED-$stamp"
  $activationBootstrapTarget = Join-Path $backendDir "app\data\product_activation_bootstrap.json"
  $activationIssuerArgs = @(
    $activationIssuerScript,
    "--private-key", $ActivationPrivateKeyPath,
    "--public-key", $activationPublicKeyTarget,
    "--customer", $BundledActivationCustomer,
    "--edition", "trial",
    "--serial", $activationSerial,
    "--expires-at", $activationExpiresAt,
    "--state-output", $activationBootstrapTarget
  )
  & python @activationIssuerArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to issue bundled product activation."
  }
  if (-not (Test-Path -LiteralPath $activationBootstrapTarget -PathType Leaf)) {
    throw "Bundled product activation state was not created."
  }
  $bundledActivationSummary = "enabled; expires at $activationExpiresAt; existing customer activation is never overwritten"
  $bundledActivationNote = "- A fresh installation receives the bundled three-month activation on first start. Existing activation state is never overwritten."
}

$backendServicesSourceDir = Join-Path $backendSourceDir "services"
$backendServicesDestinationDir = Join-Path $backendDir "services"
New-Item -ItemType Directory -Force -Path $backendServicesDestinationDir | Out-Null
foreach ($fileName in $backendRuntimeServiceFiles) {
  $sourceFile = Join-Path $backendServicesSourceDir $fileName
  if (-not (Test-Path -LiteralPath $sourceFile -PathType Leaf)) {
    throw "Required backend runtime service file is missing: $fileName"
  }
  Copy-Item -LiteralPath $sourceFile -Destination (Join-Path $backendServicesDestinationDir $fileName) -Force
}

if (Test-Path -LiteralPath (Join-Path $backendDir "data\vector")) {
  Remove-Item -LiteralPath (Join-Path $backendDir "data\vector") -Recurse -Force
}
if (Test-Path -LiteralPath (Join-Path $backendDir "data\manual_qc_runs")) {
  Remove-Item -LiteralPath (Join-Path $backendDir "data\manual_qc_runs") -Recurse -Force
}

Write-Step "Copy runtime acceptance package artifacts"
$sheet2AcceptanceSource = Join-Path $projectRoot "docs\0418\QC\sheet2_exact_review_acceptance_package.json"
if (Test-Path -LiteralPath $sheet2AcceptanceSource) {
  $sheet2AcceptanceTargetDir = Join-Path $docsDir "0418\QC"
  New-Item -ItemType Directory -Force -Path $sheet2AcceptanceTargetDir | Out-Null
  Copy-Item -LiteralPath $sheet2AcceptanceSource -Destination $sheet2AcceptanceTargetDir -Force
}

Write-Step "Write deployment README"
Write-Step "Copy business agent runtime allowlist"
$agentRuntimeSource = Join-Path $projectRoot "agent-runtime"
$agentRuntimeTarget = Join-Path $releaseDir "agent-runtime"
New-Item -ItemType Directory -Force -Path $agentRuntimeTarget | Out-Null
$agentRuntimeFiles = @(
  "package.json", "package-lock.json", "server.mjs", "runtime.mjs",
  "model-adapter.mjs", "business-output.mjs"
)
foreach ($fileName in $agentRuntimeFiles) {
  $sourceFile = Join-Path $agentRuntimeSource $fileName
  if (-not (Test-Path -LiteralPath $sourceFile -PathType Leaf)) {
    throw "Required business agent runtime file is missing: $fileName"
  }
  Copy-Item -LiteralPath $sourceFile -Destination (Join-Path $agentRuntimeTarget $fileName) -Force
}
# The locked runtime dependency file:.. needs the unchanged parent manifest.
Copy-Item -LiteralPath (Join-Path $projectRoot "package.json") -Destination (Join-Path $releaseDir "package.json") -Force

$generatedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$readmeLines = @(
  "# Customer deployment package",
  "",
  "Generated at: $generatedAt",
  "Non-releasable development package: $($AllowDirty.IsPresent)",
  "Bundled product activation: $bundledActivationSummary",
  "",
  "## Directory layout",
  "- frontend/dist: frontend static assets",
  "- backend: backend source code",
  "- agent-runtime: business assistant Node source and locked dependencies (no installed dependencies or sessions)",
  "- backend/start_dev_backend.ps1: customer backend launcher (default port 8001)",
  "- tools/customer-db-preflight.ps1: PostgreSQL and Alembic read-only preflight",
  "- tools/accept-medqc-release.ps1: five material chains and original failed-pair acceptance; Verify is read-only, Apply modes are explicit and back up first",
  "- docs/0418/QC/sheet2_exact_review_acceptance_package.json: runtime acceptance-package artifact",
  "",
  "## Excluded from this package",
  "- backend/data/vector",
  "- backend/data/manual_qc_runs",
  "- backend/data/sample_pool_uploads and local SQLite/demo DB files",
  "- backend/.env and local runtime secrets",
  "- backend/tests, cache, temporary scripts, runtime logs",
  "- all frontend font files (the browser falls back to customer/system fonts)",
  "- cache, virtual environment, and log directories",
  "",
  "## Notes",
  "- This package does not include the ICD semantic vector index.",
  "- This package does not include the ICD vector index builder script.",
  "- This package excludes all frontend font files and uses customer/system font fallbacks.",
  "- Frontend is built in customer mode and does not hardcode the public API domain.",
  "- Start the backend from backend with: powershell -NoProfile -ExecutionPolicy Bypass -File .\start_dev_backend.ps1",
  "- The customer launcher enforces PRODUCT_ACTIVATION_REQUIRED=true; activate offline in System Settings > Product Activation.",
  $bundledActivationNote,
  "",
  "## Database deployment order",
  "1. Start PostgreSQL and confirm its configured port is listening. Opening /docs only proves the backend process is alive; it does not prove database health.",
  "2. Back up the customer database before changing application code or schema.",
  "3. Run the read-only preflight from the package root: powershell -NoProfile -ExecutionPolicy Bypass -File tools/customer-db-preflight.ps1",
  "4. Compare alembic current with alembic heads. The preflight never writes the database.",
  "5. After an authorized operator confirms the backup and version gap, run from backend: python -m alembic -c alembic.ini upgrade head",
  "6. Rule validation additionally requires qc.rule_validation_runs and qc.rule_validation_events. Alembic head alone is insufficient. An authorized administrator may create missing tables from backend using python -c `"from app.services.rule_validation import _tables; _tables()`". Existing tables with missing columns must be investigated, not silently repaired. Confirm application SELECT/INSERT/UPDATE privileges and rerun preflight.",
  "7. Restart the backend and smoke-test the workstation, notifications, sample-pool list, and sample-pool upload endpoints.",
  "",
  "## Business assistant setup (optional; required for assistant conversations)",
  "1. Install Node.js >=22.19 on the customer host. In agent-runtime run npm ci --ignore-scripts using package-lock.json. Offline hosts require dependencies prepared on a compatible OS/architecture; this source package does not bundle Node or npm dependencies.",
  "2. In backend/.env configure the existing model endpoint/key/model, MEDQC_AGENT_RUNTIME_KEY, MEDQC_AGENT_RUNTIME_URL=http://127.0.0.1:8013, and MEDQC_AGENT_BACKEND_URL=http://127.0.0.1:8001 (adjust to the actual backend port). Never use the isolated development callback 8003.",
  "3. Configure MEDQC_AGENT_ACCESS_FILE with approved account/case/department scopes. No authorization file or credentials are bundled. Keep MEDQC_AGENT_TASK_WRITE_ENABLED and MEDQC_AGENT_FEEDBACK_WRITE_ENABLED unset unless business writes are separately authorized.",
  "4. From agent-runtime start node server.mjs. It listens only on loopback 8013. Both services must use the same runtime key. Persist and restrict access to .tmp/0910-full-audit/business-agent-dsh-private and the Python session storage; do not overwrite them during upgrades.",
  "5. WeKnora is optional and not bundled. If configured, provide its URL/key and explicit allowed knowledge-base IDs. Without it, do not claim knowledge retrieval is available.",
  "6. Verify doctor and department-manager reads, document location, refresh and stop before customer acceptance. Feedback/action tables require migrations 45/46; writing remains disabled by default.",
  "",
  "## Core API smoke tests",
  "Use an authenticated browser session or an authorized API client. Expected result is not HTTP 500:",
  "- GET /api/medical-records/workstation",
  "- GET /api/v1/notifications?page_size=30",
  "- GET /api/v1/qc/sample-pools?page=1&page_size=50",
  "- POST /api/v1/qc/sample-pools/import-upload (use a valid customer template)"
)
$readme = $readmeLines -join "`n"
$readme | Set-Content -LiteralPath (Join-Path $releaseDir "README-deployment.txt") -Encoding UTF8

Write-Step "Verify forbidden content is absent"
Assert-NoReleaseForbiddenContent -path $releaseDir

if (-not $AllowDirty) {
  Write-Step "Freeze verified runtime build identity"
  & python @sourceVerifyArgs `
    --runtime-build-output (Join-Path $backendDir "app\data\runtime_build.json") `
    --build-id $releaseName `
    --expected-git-commit $verifiedSourceCommit
  if ($LASTEXITCODE -ne 0) {
    throw "Runtime build identity verification failed."
  }
}

Write-Step "Create zip package"
$zipPath = "$releaseDir.zip"
if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -LiteralPath $releaseDir -DestinationPath $zipPath -Force

Write-Step "Package completed"
Write-Host $releaseDir
Write-Host $zipPath
