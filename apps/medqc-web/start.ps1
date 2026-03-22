# 一键启动前后端开发服务器
# 用法：在 PowerShell 中执行  .\start.ps1

$root = "d:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web"

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
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "cd '$root'; npm run dev" -WindowStyle Normal

Start-Sleep 3
Write-Host "`n===== 就绪 =====" -ForegroundColor Yellow
Write-Host "  前端: http://127.0.0.1:3000/"
Write-Host "  后端: http://127.0.0.1:8001/docs"
Write-Host "  按 Ctrl+C 关闭本窗口（前后端在各自窗口运行）"
