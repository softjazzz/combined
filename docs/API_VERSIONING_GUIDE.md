# API 版本控制指南

## 📋 概述

本文档说明医疗质控系统的 API 版本控制策略和使用方法。

## 🎯 版本控制策略

### 当前版本

- **版本号**: v1
- **前缀**: `/api/v1`
- **状态**: 稳定版本

### 版本历史

| 版本 | 状态 | 发布日期 | 说明 |
|------|------|---------|------|
| v1 | ✅ 当前版本 | 2025-10-09 | 首个稳定版本 |
| legacy `/api` | ⚠️ 已废弃 | - | 向后兼容，自动重定向到 v1 |

## 🔗 API 端点

### v1 API 端点

所有 v1 API 端点都使用 `/api/v1` 前缀：

```
/api/v1/health              # 系统健康检查
/api/v1/auth/*              # 认证相关
/api/v1/records/*           # 病历记录
/api/v1/qc/*                # 质控规则
/api/v1/llm/*               # LLM 服务
/api/v1/reports/*           # 报告生成
/api/v1/semantic-rules/*    # 语义规则
...
```

### 完整端点列表

#### 系统 (System)
- `GET /api/v1/health` - 健康检查
- `GET /api/v1/stats` - 系统统计

#### 认证 (Auth)
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/logout` - 用户登出
- `POST /api/v1/auth/refresh` - 刷新 Token
- `GET /api/v1/auth/me` - 获取当前用户信息

#### 病历记录 (Records)
- `GET /api/v1/records` - 获取病历列表
- `POST /api/v1/records` - 创建病历记录
- `GET /api/v1/records/{id}` - 获取病历详情
- `PUT /api/v1/records/{id}` - 更新病历记录
- `DELETE /api/v1/records/{id}` - 删除病历记录

#### 质控 (QC)
- `GET /api/v1/qc/rules` - 获取质控规则列表
- `POST /api/v1/qc/rules` - 创建质控规则
- `GET /api/v1/qc/rules/{id}` - 获取规则详情
- `PUT /api/v1/qc/rules/{id}` - 更新质控规则
- `DELETE /api/v1/qc/rules/{id}` - 删除质控规则
- `POST /api/v1/qc/execute` - 执行质控检查

#### LLM 服务 (LLM)
- `GET /api/v1/llm/providers` - 获取 LLM 提供商列表
- `GET /api/v1/llm/models` - 获取模型列表
- `POST /api/v1/llm/chat` - LLM 对话
- `POST /api/v1/llm/complete` - LLM 补全

#### 报告 (Reports)
- `GET /api/v1/reports` - 获取报告列表
- `POST /api/v1/reports/generate` - 生成报告
- `GET /api/v1/reports/{id}` - 获取报告详情
- `GET /api/v1/reports/{id}/download` - 下载报告

#### 语义规则 (Semantic Rules)
- `GET /api/v1/semantic-rules` - 获取语义规则列表
- `POST /api/v1/semantic-rules` - 创建语义规则
- `GET /api/v1/semantic-rules/{id}` - 获取规则详情
- `PUT /api/v1/semantic-rules/{id}` - 更新语义规则
- `DELETE /api/v1/semantic-rules/{id}` - 删除语义规则

## 🔄 向后兼容

### 自动重定向

为了保证向后兼容性，系统会自动将旧的 `/api/*` 请求重定向到 `/api/v1/*`：

```
/api/health  →  /api/v1/health  (HTTP 307)
/api/auth/*  →  /api/v1/auth/*  (HTTP 307)
/api/qc/*    →  /api/v1/qc/*    (HTTP 307)
```

### 重定向机制

- **状态码**: `307 Temporary Redirect`
- **保持方法**: 重定向后保持原始 HTTP 方法（GET、POST 等）
- **日志记录**: 所有旧版本 API 调用都会被记录，便于监控迁移进度

### 响应头

所有 API 响应都包含版本信息：

```http
HTTP/1.1 200 OK
X-API-Version: v1
X-Trace-ID: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json
```

## 📖 使用示例

### cURL 示例

```bash
# 使用 v1 API（推荐）
curl https://api.example.com/api/v1/health

# 使用旧版 API（自动重定向）
curl https://api.example.com/api/health
```

### JavaScript/TypeScript 示例

```typescript
// 推荐：直接使用 v1 API
const response = await fetch('http://localhost:8001/api/v1/health')
const data = await response.json()

// 或使用环境变量
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
const API_VERSION = import.meta.env.VITE_API_VERSION || 'v1'
const endpoint = `${API_BASE_URL}/api/${API_VERSION}/health`
```

### Python 示例

```python
import requests

# 使用 v1 API
response = requests.get('http://localhost:8001/api/v1/health')
data = response.json()

# 检查 API 版本
api_version = response.headers.get('X-API-Version')
print(f"API Version: {api_version}")
```

## 🚀 迁移指南

### 前端迁移

#### 1. 更新 API 基础 URL

```typescript
// 旧版本
const API_BASE_URL = 'http://localhost:8001/api'

// 新版本
const API_BASE_URL = 'http://localhost:8001/api/v1'
```

#### 2. 使用环境变量

```typescript
// .env
VITE_API_BASE_URL=http://localhost:8001
VITE_API_VERSION=v1

// 代码中
const API_URL = `${import.meta.env.VITE_API_BASE_URL}/api/${import.meta.env.VITE_API_VERSION}`
```

#### 3. 创建统一的 API 客户端

```typescript
class ApiClient {
  private baseURL: string
  private version: string

  constructor() {
    this.baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'
    this.version = import.meta.env.VITE_API_VERSION || 'v1'
  }

  private getUrl(path: string): string {
    // 移除路径开头的 /api 或 /api/v1
    const cleanPath = path.replace(/^\/api(\/v\d+)?/, '')
    return `${this.baseURL}/api/${this.version}${cleanPath}`
  }

  async get(path: string) {
    const url = this.getUrl(path)
    const response = await fetch(url)
    return response.json()
  }

  async post(path: string, data: unknown) {
    const url = this.getUrl(path)
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    return response.json()
  }
}

// 使用
const api = new ApiClient()
const health = await api.get('/health')
```

### 后端迁移

#### 1. 路由定义

```python
# ✅ 正确：使用 /api/v1 前缀
router = APIRouter(prefix="/api/v1/qc", tags=["qc"])

# ❌ 错误：使用旧的 /api 前缀
router = APIRouter(prefix="/api/qc", tags=["qc"])
```

#### 2. 禁用向后兼容（可选）

如果确认所有客户端都已迁移，可以禁用自动重定向：

```python
# apps/medqc-web/backend/app/main.py

# 禁用旧版本重定向
app.add_middleware(APIVersionMiddleware, enable_legacy_redirect=False)
```

## 📊 监控与日志

### 监控旧版本 API 使用

系统会自动记录所有使用旧版本 API 的请求：

```log
2025-10-09 07:50:19 - app.access - WARNING - [trace-id-xxx] - Legacy API usage detected: /api/health → /api/v1/health
```

### 查询旧版本 API 使用情况

```bash
# 查看过去 24 小时内使用旧版本 API 的请求数
grep "Legacy API usage detected" /var/log/medqc/app.log | tail -100

# 统计使用最多的旧版本端点
grep "Legacy API usage detected" /var/log/medqc/app.log | \
  grep -oP '/api/\w+' | sort | uniq -c | sort -rn
```

## 🔮 未来版本计划

### v2 规划（未来）

当需要引入破坏性变更时，将发布 v2 版本：

```
/api/v2/*  # 新版本 API
/api/v1/*  # 继续支持 v1（至少 6 个月）
/api/*     # 重定向到 v2（或移除向后兼容）
```

### 版本生命周期

| 阶段 | 持续时间 | 说明 |
|------|---------|------|
| 预览版 | 1-3 个月 | 早期测试，可能有变更 |
| 稳定版 | 无限期 | 生产环境使用 |
| 维护版 | 6-12 个月 | 仅修复安全问题 |
| 废弃版 | - | 不再支持 |

## ✅ 最佳实践

### 客户端

1. ✅ **始终使用版本化的 API** (`/api/v1/*`)
2. ✅ **检查响应头中的 `X-API-Version`**
3. ✅ **处理重定向响应** (HTTP 307)
4. ✅ **使用环境变量管理 API 版本**
5. ❌ **不要硬编码 API 路径**

### 服务端

1. ✅ **新端点使用 `/api/v1` 前缀**
2. ✅ **保持向后兼容至少 6 个月**
3. ✅ **记录所有旧版本 API 使用**
4. ✅ **在响应头中添加版本信息**
5. ❌ **不要删除旧版本端点，直到确认无使用**

## 🔧 故障排查

### 404 Not Found

**症状**: 请求返回 404

**解决方案**:
1. 检查 API 路径是否包含 `/v1`
2. 确认端点是否存在（查看 `/docs`）
3. 检查 HTTP 方法是否正确

### 重定向循环

**症状**: 请求陷入重定向循环

**解决方案**:
1. 检查客户端是否正确处理 307 重定向
2. 确认没有手动添加重复的 `/api/v1` 前缀

### CORS 错误

**症状**: 浏览器显示 CORS 错误

**解决方案**:
1. 确认后端 `CORS_ORIGINS` 配置正确
2. 检查预检请求（OPTIONS）是否成功
3. 验证重定向后的 URL 是否在白名单中

## 📚 参考资料

- [REST API 版本控制最佳实践](https://restfulapi.net/versioning/)
- [语义化版本控制](https://semver.org/lang/zh-CN/)
- [FastAPI 路由文档](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

## 🎯 检查清单

在发布新版本前，请确保:

- [ ] 所有新端点使用 `/api/v1` 前缀
- [ ] 向后兼容中间件已启用
- [ ] 响应头包含 `X-API-Version`
- [ ] 旧版本 API 使用已记录
- [ ] 文档已更新（/docs）
- [ ] 前端代码已更新 API 路径
- [ ] 环境变量配置正确
- [ ] 所有测试通过

---

**文档维护**: P2-3 API 版本控制任务
**创建日期**: 2025-10-09
**最后更新**: 2025-10-09
