# 本地前后端打不开排障 SOP（Windows）

适用场景：
- 前端 `127.0.0.1:3000` 打不开、白屏、超时
- 控制台出现 `spawn EPERM`、`Failed to scan for dependencies`、MIME 类型异常（例如 `crypto-js.js`）
- 后端接口偶发不可达

## 1. 快速判定：服务问题还是浏览器问题

在 PowerShell 执行：

```powershell
Invoke-WebRequest http://127.0.0.1:3000/ -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8001/docs -UseBasicParsing
netstat -ano -p tcp | Select-String ':3000|:8001'
```

判定规则：
- `3000/8001` 都返回 `200`：优先排查浏览器缓存/插件。
- `8001=200` 但 `3000` 超时/拒绝：前端进程异常。
- 两者都失败：先做第 2 节通用恢复。

## 2. 通用恢复（先清理再启动）

```powershell
cd D:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web
taskkill /IM node.exe /F
Remove-Item -Recurse -Force .tmp\vite-cache,node_modules\.vite -ErrorAction SilentlyContinue
```

说明：`taskkill` 提示“未找到进程”属于正常情况。

## 3. 先用稳定模式验证可访问（推荐）

```powershell
npm run preview -- --host 127.0.0.1 --port 3000 --strictPort
```

目标：先确认构建产物可访问，排除页面本身故障。

## 4. 开发模式启动（需要热更新时）

```powershell
npm run dev
```

若出现以下关键词，按第 5 节处理：
- `spawn EPERM`
- `Pre-transform error`
- `Failed to scan for dependencies`

## 5. 根因修复（管理员 PowerShell，一次性）

以管理员身份运行：

```powershell
Add-MpPreference -ExclusionProcess "node.exe"
Add-MpPreference -ExclusionProcess "esbuild.exe"
Add-MpPreference -ExclusionPath "D:\大模型项目\lx0222\health-qc-monorepo"
```

验证排除项是否生效：

```powershell
Get-MpPreference | Select-Object -ExpandProperty ExclusionProcess
Get-MpPreference | Select-Object -ExpandProperty ExclusionPath
```

预期至少包含：
- `node.exe`
- `esbuild.exe`
- `D:\大模型项目\lx0222\health-qc-monorepo`

## 6. 浏览器侧排障（服务已正常但页面仍打不开）

按顺序执行：
1. 无痕窗口打开 `http://127.0.0.1:3000`
2. 临时禁用扩展（尤其翻译/脚本注入类）
3. 清理 `127.0.0.1:3000` 站点缓存
4. 强刷 `Ctrl+Shift+R`

## 7. 日志采集（用于二线定位）

```powershell
Get-Content .tmp\vite-dev.log -Tail 120
```

重点关注关键词：
- `spawn EPERM`
- `vite:esbuild`
- `Failed to scan for dependencies`
- `Internal server error`

## 8. 一键恢复建议顺序（最常用）

1. 执行第 2 节清理。
2. 先跑 `preview` 验证可访问。
3. 再切 `dev`。
4. 若 `dev` 仍报 `spawn EPERM`，执行第 5 节管理员修复并重试。

## 9. 一键启动脚本（推荐）

项目已提供：
- `apps/medqc-web/start-all.ps1`

默认行为：
- 后端：`uvicorn` 无 `--reload`（稳定模式）
- 前端：`preview` 模式（稳定模式）
- 自动端口清理 + 健康检查（`3000` / `8001`）

用法：

```powershell
cd D:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web
powershell -ExecutionPolicy Bypass -File .\start-all.ps1
```

可选参数：

```powershell
# 前端改为 dev 模式
powershell -ExecutionPolicy Bypass -File .\start-all.ps1 -FrontendMode dev

# 跳过端口清理
powershell -ExecutionPolicy Bypass -File .\start-all.ps1 -NoKill
```
