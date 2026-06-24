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
Invoke-WebRequest http://127.0.0.1:3000/@vite/client -UseBasicParsing
netstat -ano -p tcp | Select-String ':3000|:8001'
```

判定规则：

- `3000/8001` 都返回 `200`，且 `3000/@vite/client` 也返回 `200`：当前是 `dev`，优先排查浏览器缓存/插件。
- `3000/8001` 都返回 `200`，但 `3000/@vite/client` 不通：当前不是 `dev`，大概率是 `dist` 或 `preview`。
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

若怀疑依赖优化缓存损坏，直接用强制恢复命令：

```powershell
npm run dev:force
```

说明：

- `npm run cache:clean` 会清掉 `node_modules/.vite` 和 `.tmp/vite-cache`
- `npm run dev:force` 会在清缓存后用 `vite --force` 重建依赖优化结果

如果项目物理路径包含中文目录，例如 `D:\大模型项目\...`，Vite dev 可能出现：

- `index.html` 能返回
- 但 `/src/main.ts`、`/@vite/client`、静态资源正文请求超时

这类问题在本仓库已复现，当前最稳妥的解决方式不是 `subst`，而是把仓库实际放到纯 ASCII 路径，例如：

```powershell
D:\lx0222\health-qc-monorepo
```

再从该路径运行：

```powershell
cd D:\lx0222\health-qc-monorepo\apps\medqc-web
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
- 前端：`dist` 模式（稳定模式）
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

# 前端改为 preview 模式
powershell -ExecutionPolicy Bypass -File .\start-all.ps1 -FrontendMode preview

# 跳过端口清理
powershell -ExecutionPolicy Bypass -File .\start-all.ps1 -NoKill
```

## 10. 如何确认当前到底是 dev / preview / dist

直接执行：

```powershell
Invoke-WebRequest http://127.0.0.1:3000/@vite/client -UseBasicParsing
Get-ChildItem .tmp\frontend-*-3000.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1 Name,LastWriteTime
```

判定规则：

- `@vite/client` 返回 `200`：当前是 `dev`
- `@vite/client` 不通，但根路径 `/` 正常：当前是 `preview` 或 `dist`
- 最近日志文件名是 `frontend-dev-3000.log` / `frontend-preview-3000.log` / `frontend-dist-3000.log`，可作为辅助确认

注意：

- `dev` 依赖 Vite HMR 和 `/@vite/client`
- `preview`/`dist` 只验证静态资源能否打开，不代表热更新可用
- 如果你指定了 `-FrontendMode dev`，脚本现在会按 `@vite/client` 做健康检查，不再把 `dist` 误判成 `dev`

## 11. `spawn EPERM` 最短修复路径（管理员 PowerShell）

适用症状：

- `npm run dev` 很快出现 `vite ready`
- 随后马上出现 `Pre-transform error: spawn EPERM`
- 触发文件通常是 `src/main.ts`、`src/router/index.ts`、`src/App.vue`

这类故障不是前端业务代码慢，而是 Windows 上 `node.exe -> child_process.spawn(...)` 被系统策略或安全软件拦截。

### 11.1 先做最小复现

在项目目录执行：

```powershell
@'
const cp = require('child_process');
const r = cp.spawnSync('cmd', ['/c', 'echo ok'], { encoding: 'utf8' });
console.log('status=', r.status, 'error=', r.error && r.error.code, 'stdout=', (r.stdout || '').trim(), 'stderr=', (r.stderr || '').trim());
'@ | node -
```

若输出里出现 `error= EPERM`，说明不是 Vite 本身故障，而是 Node 子进程执行被拦。

### 11.2 管理员窗口确认 Defender 排除项

```powershell
Add-MpPreference -ExclusionProcess "node.exe"
Add-MpPreference -ExclusionProcess "esbuild.exe"
Add-MpPreference -ExclusionPath "D:\大模型项目\lx0222\health-qc-monorepo"
```

说明：

- 这一步要在“管理员身份”的 PowerShell 里执行
- 如果已经配过，重复执行问题不大

### 11.3 管理员窗口重启前端进程

```powershell
taskkill /IM node.exe /F
```

然后回到项目目录：

```powershell
cd D:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web
powershell -ExecutionPolicy Bypass -File .\start-all.ps1 -FrontendMode dev
```

### 11.4 再次验证 Node 子进程是否恢复

```powershell
@'
const cp = require('child_process');
const r = cp.spawnSync('cmd', ['/c', 'echo ok'], { encoding: 'utf8' });
console.log('status=', r.status, 'error=', r.error && r.error.code, 'stdout=', (r.stdout || '').trim(), 'stderr=', (r.stderr || '').trim());
'@ | node -
```

预期结果：

- `status= 0`
- `error= null` 或空
- `stdout= ok`

### 11.5 验证 dev 是否真的起来

```powershell
Invoke-WebRequest http://127.0.0.1:3000/@vite/client -UseBasicParsing
```

判定标准：

- `Content-Type` 是 `text/javascript` 或类似 JS 模块类型：`dev` 正常
- 返回 `text/html`：当前不是 `dev`
- 超时/拒绝连接：`dev` 没起来，继续看 `.tmp\frontend-dev-3000.err.log`

### 11.6 如果仍然 `EPERM`

优先级顺序：

1. 必须在管理员 PowerShell 里重新执行第 11.2 节和第 11.3 节
2. 关闭或排除第三方安全软件/EDR，不只看 Defender
3. 不要在被策略托管的终端宿主里跑 Node 子进程
4. 用 `3001 dev` 作为临时热更新端口，`3000` 保留给 `dist/preview`
