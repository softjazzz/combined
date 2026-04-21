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
  Write-Step "以 customer 模式构建前端 dist"
  Push-Location $projectRoot
  try {
    npx vite build --mode customer --config vite.config.mjs --configLoader native
  }
  finally {
    Pop-Location
  }
}

Write-Step "准备发布目录 $releaseDir"
if (Test-Path -LiteralPath $releaseDir) {
  Remove-Item -LiteralPath $releaseDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $releaseDir, $backendDir, $frontendDir, $toolsDir | Out-Null

Write-Step "复制前端构建产物"
Copy-Item -LiteralPath (Join-Path $projectRoot "dist") -Destination (Join-Path $frontendDir "dist") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "package.json") -Destination (Join-Path $frontendDir "package.json") -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\serve_dist_spa.py") -Destination (Join-Path $toolsDir "serve_dist_spa.py") -Force

Write-Step "复制后端源码（排除 ICD 向量索引和开发目录）"
Copy-TreeExclude `
  -source (Join-Path $projectRoot "backend") `
  -destination $backendDir `
  -excludeDirs @("__pycache__", ".pytest_cache", ".mypy_cache", "htmlcov", ".ruff_cache", ".venv", "venv", "logs", "release-gate-artifacts") `
  -excludeFiles @(".coverage", "dev-backend.log", "dev-backend.err.log", "uvicorn.err.log", "uvicorn.out.log")

if (Test-Path -LiteralPath (Join-Path $backendDir "data\vector")) {
  Remove-Item -LiteralPath (Join-Path $backendDir "data\vector") -Recurse -Force
}
if (Test-Path -LiteralPath (Join-Path $backendDir "data\manual_qc_runs")) {
  Remove-Item -LiteralPath (Join-Path $backendDir "data\manual_qc_runs") -Recurse -Force
}

Write-Step "写入部署说明"
$readme = @"
# Customer deployment package

Generated at: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## Directory layout
- frontend/dist: frontend static assets
- backend: backend source code

## Excluded from this package
- backend/data/vector
- backend/data/manual_qc_runs
- cache, test, virtual environment, and log directories

## Notes
- This package does not include the ICD semantic vector index.
- Frontend is built in customer mode and does not hardcode the public API domain.
- If ICD semantic retrieval is needed later, build it in the customer environment:
  - apps/medqc-web/backend/scripts/build_icd_vector_index.py
"@
$readme | Set-Content -LiteralPath (Join-Path $releaseDir "README-deployment.txt") -Encoding UTF8

Write-Step "打包完成"
Write-Host $releaseDir
