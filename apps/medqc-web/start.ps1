# 一键启动前后端开发服务器（含 esbuild EPERM 防护）
# 用法：在 PowerShell 中执行  .\start.ps1

$root = "d:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web"

function Resolve-EsbuildBinary([string]$projectRoot) {
    try {
        $searchRoots = @(
            $projectRoot,
            (Split-Path -Parent $projectRoot),
            (Split-Path -Parent (Split-Path -Parent $projectRoot))
        ) | Select-Object -Unique

        $hostCandidates = @()
        foreach ($sr in $searchRoots) {
            $hostPattern = Join-Path $sr "node_modules\.pnpm\esbuild@*\node_modules\esbuild\package.json"
            $hostCandidates += Get-ChildItem -Path $hostPattern -ErrorAction SilentlyContinue
        }
        if (-not $hostCandidates -or $hostCandidates.Count -eq 0) { return $null }

        $hostPkg = $hostCandidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $hostVersion = (Get-Content $hostPkg.FullName -Raw | ConvertFrom-Json).version
        if (-not $hostVersion) { return $null }

        $candidateList = @()
        foreach ($sr in $searchRoots) {
            $candidatePattern = Join-Path $sr "node_modules\.pnpm\@esbuild+win32-x64@$hostVersion\node_modules\@esbuild\win32-x64\esbuild.exe"
            $candidateList += Get-ChildItem -Path $candidatePattern -ErrorAction SilentlyContinue
        }
        $candidate = $candidateList | Select-Object -First 1
        if (-not $candidate) { return $null }

        # 使用版本化文件名，避免“同名文件被占用”导致 Copy-Item 失败
        $safeVersion = ($hostVersion -replace "[^0-9A-Za-z\.-]", "_")
        $localTmpDir = Join-Path $projectRoot ".tmp"
        if (-not (Test-Path -LiteralPath $localTmpDir)) {
            New-Item -ItemType Directory -Path $localTmpDir -Force | Out-Null
        }
        $tempEsbuild = Join-Path $localTmpDir ("esbuild-dev-" + $safeVersion + ".exe")
        try {
            Copy-Item -Path $candidate.FullName -Destination $tempEsbuild -Force -ErrorAction Stop
        } catch {
            # 若被占用但文件已存在，可直接复用
            if (-not (Test-Path -LiteralPath $tempEsbuild)) {
                throw
            }
        }
        return $tempEsbuild
    } catch {
        Write-Warning "  准备 esbuild 二进制失败: $($_.Exception.Message)"
        return $null
    }
}

Write-Host "===== 清理旧进程 =====" -ForegroundColor Cyan
@(3000, 8001) | ForEach-Object {
    $port = $_
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "  killed port $port (pid $($conn.OwningProcess))"
    }
}
Start-Sleep 1

Write-Host "`n===== 启动后端 (uvicorn :8001) =====" -ForegroundColor Green
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; python -m uvicorn app.main:app --reload --port 8001 --host 0.0.0.0" -WindowStyle Normal

Write-Host "===== 启动前端 (vite :3000) =====" -ForegroundColor Green
$esbuildBinary = Resolve-EsbuildBinary $root
if ($esbuildBinary) {
    Write-Host "  使用 esbuild 替身: $esbuildBinary"
    $frontendCmd = "cd '$root'; `$env:ESBUILD_BINARY_PATH='$esbuildBinary'; npm run dev"
} else {
    Write-Warning "  未找到 esbuild 替身，按默认方式启动"
    $frontendCmd = "cd '$root'; npm run dev"
}
Start-Process pwsh -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal

Start-Sleep 3
Write-Host "`n===== 就绪 =====" -ForegroundColor Yellow
Write-Host "  前端: http://127.0.0.1:3000/"
Write-Host "  后端: http://127.0.0.1:8001/docs"
Write-Host "  按 Ctrl+C 关闭本窗口（前后端在各自窗口运行）"
