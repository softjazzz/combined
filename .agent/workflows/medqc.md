---
description: MedQC 病案质控系统项目规则和约定
---

# MedQC 项目规则

## 项目结构

- **前端**: `apps/medqc-web/src` (Vue 3 + TypeScript + Ant Design Vue)
- **后端**: `apps/medqc-web/backend` (Python FastAPI)
- **数据库**: Supabase (PostgreSQL)

## 技术栈约定

### 前端
- Vue 3 Composition API (`<script setup>`)
- TypeScript 严格模式
- Ant Design Vue 组件库
- Vite 构建工具
- API 客户端放在 `src/api/` 目录

### 后端
- FastAPI + Pydantic
- 服务层放在 `app/services/`
- 路由放在 `app/routers/`
- Schema 放在 `app/schemas/`
- 使用 `safe_post_json` 调用外部 LLM API（已配置 trust_env=False 绕过代理）

## LLM 配置

### 环境变量命名映射

| 标准名（.env 中使用） | 历史别名（代码兼容） | 说明 |
|---|---|---|
| `LLM_API_ENDPOINT` | `SICHUAN_API_ENDPOINT` | LLM API 端点 |
| `LLM_API_KEY` | `SICHUAN_API_KEY` | API 密钥 |
| `LLM_MODEL` | `SICHUAN_MODEL` | 模型名称 |
| `LLM_TIMEOUT_SECONDS` | `SICHUAN_TIMEOUT_SECONDS` | 超时时间 |
| `LLM_ENABLE_TRUNCATE` | `SICHUAN_ENABLE_TRUNCATE` | 是否截断 |
| `LLM_MAX_CONTENT_LENGTH` | `SICHUAN_MAX_CONTENT_LENGTH` | 最大内容长度 |

> [!IMPORTANT]
> `.env` 文件统一使用 `LLM_*` 前缀。`SICHUAN_*` 是历史别名，通过 `settings.py` 的 `AliasChoices` 映射。
> **排查时搜索 `LLM_` 前缀，不要搜 `SICHUAN_`！** `SichuanQCLLMClient` 类名是历史命名，实际读取 `settings.LLM_*`。

### 当前开发环境配置（`backend/.env`）

```
LLM_API_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=qwen-turbo
LLM_TIMEOUT_SECONDS=120
```

> [!CAUTION]
> **`.env` 文件必须位于 `backend/` 目录下**，且启动后端时**工作目录必须是 `backend/`**，
> 否则 Pydantic Settings 无法读取 `.env`，LLM API 将不可用。

### LLM 不工作排查清单

1. 查看 `.env` 中 `LLM_API_ENDPOINT` / `LLM_API_KEY` / `LLM_MODEL` 是否已配置
2. 检查启动日志中的 `LLM diagnostics at startup` 输出
3. 调用 `GET /api/v1/health` 查看 `llm_config` 字段
4. 若 `LLM_*` 与 `SICHUAN_*` 同时存在且值冲突，启动时会直接报错

## 常用命令

// turbo-all

### 启动开发服务

> [!IMPORTANT]
> 后端和前端的端口必须匹配。当前 `vite.config.ts` 中 `backendTarget` 指向 `http://localhost:8001`。
> **后端必须以 `backend/` 为工作目录启动**，确保 `.env` 能被正确加载。

#### Linux / macOS
```bash
# 前端 (端口 3000)
cd apps/medqc-web && npx vite --host 0.0.0.0 --port 3000

# 后端 (端口 8001)
cd apps/medqc-web/backend && JWT_SECRET=dev-secret uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

#### Windows PowerShell
```powershell
# 前端 (端口 3000)
cd d:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web
npx vite --port 3000 --host

# 后端 (端口 8001) ← 必须在 backend 目录下启动！
cd d:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\backend
$env:JWT_SECRET="dev-secret"; python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 后台启动服务 (nohup, Linux only)
```bash
# 前端后台启动 (端口 3000)
cd apps/medqc-web && nohup npx vite --host 0.0.0.0 --port 3000 > frontend.log 2>&1 &

# 后端后台启动 (端口 8001)
cd apps/medqc-web/backend && nohup uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload > backend.log 2>&1 &

# 检查服务状态
lsof -i :3000 -i :8001

# 停止服务
kill $(lsof -t -i :3000) 2>/dev/null
kill $(lsof -t -i :8001) 2>/dev/null
```

### 运行测试
```bash
# 后端单元测试
cd apps/medqc-web/backend && python3 -m pytest tests/unit/ -v
```

### 类型检查
```bash
# 前端
cd apps/medqc-web && npx vue-tsc --noEmit
```

## 核心模块

### 病案首页自动生成 (F1-F13)
- 服务: `frontpage_extraction_service.py`
- ICD 编码: `icd_coding_service.py`
- 画像分析: `diagnosis_surgery_profiling_service.py`
- API: `/api/v1/frontpage/*`

### DRG/DIP 模块
- 路由: `app/routers/drg.py`
- 前端: `src/views/drg/`

## 注意事项

1. **代理问题**: httpx 客户端已配置 `trust_env=False`，避免 SOCKS 代理导致 LLM 调用失败
2. **Demo 模式**: 部分页面支持无需登录访问，路径为 `/demo/*`
3. **权限控制**: 路由 meta 中的 `permission` 字段控制角色访问权限
