param(
  [string]$OutputRoot = "D:\LLM\LX888\release",
  [switch]$SkipBuild,
  [string]$InventoryPath = "",
  [switch]$AllowDirty
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
    $_.Name -eq "coverage.xml"
  }
  if ($forbiddenFiles.Count -gt 0) {
    $sample = ($forbiddenFiles | Select-Object -First 10 | ForEach-Object { $_.FullName }) -join "`n"
    throw "Forbidden release files found:`n$sample"
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

Write-Step "Copy backend source (exclude ICD vector index and development directories)"
Copy-TreeExclude `
  -source (Join-Path $projectRoot "backend") `
  -destination $backendDir `
  -excludeDirs @(
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
  ) `
  -excludeFiles @(
    ".coverage",
    ".env",
    "coverage.xml",
    "build_icd_vector_index.py",
    "icd_vector_retrieval_demo.py"
  ) `
  -excludeDirPatterns @("tmp*", "__pycache__") `
  -excludeFilePatterns @(
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
  "",
  "## Directory layout",
  "- frontend/dist: frontend static assets",
  "- backend: backend source code",
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
  "- Frontend is built in customer mode and does not hardcode the public API domain."
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
