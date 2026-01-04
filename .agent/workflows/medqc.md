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

环境变量（在 `backend/.env` 中配置）:
```
SICHUAN_API_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1
SICHUAN_API_KEY=sk-xxx
SICHUAN_MODEL=qwen2.5-14b-instruct
```

## 常用命令

// turbo-all

### 启动开发服务
```bash
# 前端 (端口 3000)
cd apps/medqc-web && npm run dev -- --port 3000

# 后端 (端口 8000)
cd apps/medqc-web/backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
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
