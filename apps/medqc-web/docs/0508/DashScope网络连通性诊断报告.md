# DashScope 网络连通性诊断报告

## 结论

本轮没有运行正式质控，也没有读取或输出 API Key。

当前失败不是模型配置表 `user_llm_configs` 缺失导致的最终问题，也不是 DashScope 域名不可解析或 443 端口不可达。系统层网络可达；进一步定位正式后端当前可用解释器为 `C:\Python310\python.exe`，未发现项目内 `.venv`，也未发现正在运行的 Python/uvicorn 后端进程。

- DNS：`dashscope.aliyuncs.com` 可解析。
- TCP 443：`Test-NetConnection dashscope.aliyuncs.com -Port 443` 成功。
- PowerShell `Invoke-WebRequest`：能连到 DashScope，返回 HTTP `404 Not Found`，说明 HTTPS 请求已到达上游服务。
- `curl.exe` 经已批准的 PowerShell 7 前缀执行：能连到 DashScope，返回 HTTP `404 Not Found`。
- 普通 `python httpx`：第一次曾失败，`ConnectError: [WinError 10013] 以一种访问权限不允许的方式做了一个访问套接字的尝试。`
- 同一解释器 `C:\Python310\python.exe` 重新运行 minimal chat：HTTP `200`，`usage_total_tokens=28`。
- PowerShell 7 启动同一解释器运行 minimal chat：HTTP `200`，`usage_total_tokens=28`。
- 代理环境变量：仅存在 `NO_PROXY=localhost,127.0.0.1`；未发现 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`。

因此，前一轮 minimal chat 中的 `All connection attempts failed` 更符合“当次 Python 进程/沙箱/权限上下文出站连接失败”的瞬态或上下文问题，而不是 DashScope 服务不可用、模型不可用、endpoint 错误或 key 缺失。当前同一解释器 minimal chat 已通过，下一步才允许进入 `2122521` 单病历 c1/c3 门禁；仍不应直接重跑随机 10。

## 后端 Python 解释器定位

### 正在运行的后端进程

未发现正在运行的 Python/uvicorn/gunicorn 后端进程；当前进程列表中仅看到本次诊断命令自身的 PowerShell 进程。

### 当前可用 Python

命令：

```powershell
python -c "import sys; print(sys.executable); print(sys.prefix)"
```

结果：

- `sys.executable=C:\Python310\python.exe`
- `sys.prefix=C:\Python310`
- `base_prefix=C:\Python310`
- `site-packages=C:\Python310\lib\site-packages`

项目目录检查：

- `apps/medqc-web/.venv`：未发现。
- `apps/medqc-web/backend/.venv`：未发现。

## 诊断结果

### DNS

命令：

```powershell
Resolve-DnsName dashscope.aliyuncs.com
```

结果摘要：

- `dashscope.aliyuncs.com` 解析到 CNAME：`gtm-cn-rt54j1mlg03.dashscope.aliyuncs.com`
- A 记录包含：`8.140.217.18`、`8.152.159.24`、`39.96.198.249`、`39.96.213.166`
- AAAA 记录也存在。

### TCP 443

命令：

```powershell
Test-NetConnection dashscope.aliyuncs.com -Port 443
```

结果摘要：

- `TcpTestSucceeded=True`
- `RemotePort=443`
- 使用网络接口：`WLAN 2`

### PowerShell Invoke-WebRequest

命令：

```powershell
Invoke-WebRequest -Uri 'https://dashscope.aliyuncs.com/compatible-mode/v1' -Method Get
```

结果摘要：

- 请求到达上游。
- 返回 HTTP `404 Not Found`。
- 这属于路径未匹配或未授权前的服务响应，不是连接失败。

### curl.exe

命令：

```powershell
curl.exe -I --connect-timeout 20 --max-time 30 https://dashscope.aliyuncs.com/compatible-mode/v1
```

结果摘要：

- 普通 shell 下曾失败：`curl: (7) Failed to connect to dashscope.aliyuncs.com port 443`
- 通过已批准的 PowerShell 7 前缀执行后成功到达上游：
  - `HTTP/1.1 404 Not Found`
  - `server: istio-envoy`

该差异说明当前执行容器/沙箱与正常 PowerShell 7 网络权限不一致。

### Python httpx

命令：

```powershell
python -c "import httpx; httpx.get('https://dashscope.aliyuncs.com/compatible-mode/v1', timeout=20.0)"
```

第一次结果摘要：

```json
{
  "tool": "python-httpx",
  "url_host": "dashscope.aliyuncs.com",
  "success": false,
  "exception_type": "ConnectError",
  "error": "[WinError 10013] 以一种访问权限不允许的方式做了一个访问套接字的尝试。"
}
```

这和正式诊断脚本中 `ConnectError / All connection attempts failed` 的方向一致：该次 Python httpx 请求未进入 HTTP 响应阶段。

随后使用同一个解释器 `C:\Python310\python.exe` 读取后端 `.env` 配置并发起 DashScope compatible-mode minimal chat：

```json
{
  "runner": "current-shell-python",
  "python_executable": "C:\\Python310\\python.exe",
  "python_prefix": "C:\\Python310",
  "provider": "alibaba",
  "endpoint_host": "dashscope.aliyuncs.com",
  "model": "qwen3.6-35b-a3b",
  "key_present": true,
  "key_prefix_hash": "93fac017a605",
  "httpx_version": "0.25.2",
  "success": true,
  "http_status": 200,
  "has_choices": true,
  "usage_total_tokens": 28
}
```

PowerShell 7 启动同一解释器后也成功：

```json
{
  "python_executable": "C:\\Python310\\python.exe",
  "python_prefix": "C:\\Python310",
  "provider": "alibaba",
  "endpoint_host": "dashscope.aliyuncs.com",
  "model": "qwen3.6-35b-a3b",
  "key_present": true,
  "key_prefix_hash": "93fac017a605",
  "httpx_version": "0.25.2",
  "success": true,
  "http_status": 200,
  "has_choices": true,
  "usage_total_tokens": 28
}
```

### 代理环境变量

命令：

```powershell
Get-ChildItem Env: | Where-Object { $_.Name -match '^(HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|http_proxy|https_proxy|all_proxy|no_proxy)$' }
```

结果摘要：

- `NO_PROXY=localhost,127.0.0.1`
- 未发现 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`

当前 minimal chat 在无 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` 的情况下已成功，因此代理不是必需条件。若后续正式链路仍出现 `WinError 10013` 或 `All connection attempts failed`，应优先检查运行该 Python 进程的权限上下文、Windows 防火墙/安全软件策略、进程启动方式和是否被沙箱限制，而不是先改模型配置。

## 对正式质控的影响

前一轮随机 10 报告中的：

- `provider_error=127`
- `technical_error_internal=441`
- `total_tokens=0`

不能作为质量结论。它们只说明 Python 正式质控进程无法完成 provider 调用。

当前 Python httpx minimal chat 已通过，但这只解除 provider/config 的第一层门禁。仍不应直接重跑随机 10；下一步应先运行 `2122521` 单病历 `pack_concurrency=1`，通过后再运行同病历 `pack_concurrency=3`。

## 建议下一步

1. 不要直接重跑随机 10。
2. 使用 `C:\Python310\python.exe` 运行正式 provider 门禁脚本中的 `2122521` 单病历 `pack_concurrency=1`。
3. `c1` 成功后再跑 `c3`。
4. 只有 `c1/c3` 均无 provider/timeout/parse/technical error，且 tokens > 0，才允许重跑随机 10。
5. 如果单病历仍失败，重点检查 Windows 防火墙/安全软件是否按进程或启动来源拦截 Python 出站连接。
