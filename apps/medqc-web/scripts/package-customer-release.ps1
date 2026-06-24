param(
  [string]$OutputRoot = "D:\LLM\LX888\release",
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $projectRoot)
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$releaseDir = Join-Path $OutputRoot "medqc-web-customer-$stamp"
$backendDir = Join-Path $releaseDir "backend"
$frontendDir = Join-Path $releaseDir "frontend"
$toolsDir = Join-Path $releaseDir "tools"

function Write-Step([string]$message) {
  Write-Host "[package] $message" -ForegroundColor Cyan
}

function Copy-TreeExclude([string]$source, [string]$destination, [string[]]$excludeDirs, [string[]]$excludeFiles) {
  Get-ChildItem -LiteralPath $source -Force | ForEach-Object {
    $name = $_.Name
    if ($_.PSIsContainer) {
      if ($excludeDirs -contains $name) {
        return
      }
      $target = Join-Path $destination $name
      New-Item -ItemType Directory -Force -Path $target | Out-Null
      Copy-TreeExclude -source $_.FullName -destination $target -excludeDirs $excludeDirs -excludeFiles $excludeFiles
      return
    }
    if ($excludeFiles -contains $name) {
      return
    }
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $destination $name) -Force
  }
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
New-Item -ItemType Directory -Force -Path $releaseDir, $backendDir, $frontendDir, $toolsDir | Out-Null

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
  -excludeDirs @("__pycache__", ".pytest_cache", ".mypy_cache", "htmlcov", ".ruff_cache", ".venv", "venv", "logs", "release-gate-artifacts") `
  -excludeFiles @(".coverage", "dev-backend.log", "dev-backend.err.log", "uvicorn.err.log", "uvicorn.out.log", "build_icd_vector_index.py")

if (Test-Path -LiteralPath (Join-Path $backendDir "data\vector")) {
  Remove-Item -LiteralPath (Join-Path $backendDir "data\vector") -Recurse -Force
}
if (Test-Path -LiteralPath (Join-Path $backendDir "data\manual_qc_runs")) {
  Remove-Item -LiteralPath (Join-Path $backendDir "data\manual_qc_runs") -Recurse -Force
}

Write-Step "Write deployment README"
$generatedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$readmeLines = @(
  "# Customer deployment package",
  "",
  "Generated at: $generatedAt",
  "",
  "## Directory layout",
  "- frontend/dist: frontend static assets",
  "- backend: backend source code",
  "",
  "## Excluded from this package",
  "- backend/data/vector",
  "- backend/data/manual_qc_runs",
  "- frontend font files except Source Han Sans SC Regular/Medium",
  "- cache, test, virtual environment, and log directories",
  "",
  "## Notes",
  "- This package does not include the ICD semantic vector index.",
  "- This package does not include the ICD vector index builder script.",
  "- This package keeps only Source Han Sans SC Regular/Medium and removes SF Pro font files.",
  "- Frontend is built in customer mode and does not hardcode the public API domain."
)
$readme = $readmeLines -join "`n"
$readme | Set-Content -LiteralPath (Join-Path $releaseDir "README-deployment.txt") -Encoding UTF8
Write-Step "Package completed"
Write-Host $releaseDir
