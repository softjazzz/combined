param(
  [string]$OutputRoot = "D:\LLM\LX888\release",
  [switch]$SkipBuild,
  [string]$InventoryPath = "",
  [switch]$AllowDirty,
  [int]$BundledActivationMonths = 3,
  [string]$BundledActivationCustomer = "MedQC 客户试用授权",
  [string]$ActivationPrivateKeyPath = "",
  [switch]$SkipBundledActivation
)

$ErrorActionPreference = "Stop"

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
        Select-String -SimpleMatch "api.medqc.com" -List
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

if (-not $SkipBuild) {
  Write-Step "Build frontend dist in customer mode"
  Push-Location $projectRoot
  try {
    npx vite build --mode customer --config vite.config.mjs --configLoader native
  }
  finally {
    Pop-Location
  }
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
Write-Step "Slim frontend fonts (keep Source Han Sans SC Regular/Medium only)"
$distFontsDir = Join-Path $frontendDir "dist\fonts"
$sfProDir = Join-Path $distFontsDir "sf-pro"
if (Test-Path -LiteralPath $sfProDir) {
  Remove-Item -LiteralPath $sfProDir -Recurse -Force
}
$sourceHanDir = Join-Path $distFontsDir "source-han-sans-sc"
if (Test-Path -LiteralPath $sourceHanDir) {
  Get-ChildItem -LiteralPath $sourceHanDir -File | Where-Object {
    $_.Name -notin @("SourceHanSansSC-Regular.otf", "SourceHanSansSC-Medium.otf")
  } | Remove-Item -Force
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
  "- backend/start_dev_backend.ps1: customer backend launcher (default port 8001)",
  "- tools/customer-db-preflight.ps1: PostgreSQL and Alembic read-only preflight",
  "- docs/0418/QC/sheet2_exact_review_acceptance_package.json: runtime acceptance-package artifact",
  "",
  "## Excluded from this package",
  "- backend/data/vector",
  "- backend/data/manual_qc_runs",
  "- backend/data/sample_pool_uploads and local SQLite/demo DB files",
  "- backend/.env and local runtime secrets",
  "- backend/tests, cache, temporary scripts, runtime logs",
  "- frontend font files except Source Han Sans SC Regular/Medium",
  "- cache, virtual environment, and log directories",
  "",
  "## Notes",
  "- This package does not include the ICD semantic vector index.",
  "- This package does not include the ICD vector index builder script.",
  "- This package keeps only Source Han Sans SC Regular/Medium and removes SF Pro font files.",
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
  "6. Restart the backend and smoke-test the workstation, notifications, sample-pool list, and sample-pool upload endpoints.",
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

Write-Step "Create zip package"
$zipPath = "$releaseDir.zip"
if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -LiteralPath $releaseDir -DestinationPath $zipPath -Force

Write-Step "Package completed"
Write-Host $releaseDir
Write-Host $zipPath
