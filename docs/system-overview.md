# 智慧医保临床实时质控系统 — 系统概览

> 本文概述系统背景、目标、总体架构与技术栈，帮助新成员快速了解项目。

## 目录
- 背景与目标
- 系统架构概述
- 技术栈说明
- 部署与运行（概览）
- 安全与权限（概览）
- 术语表

## 背景与目标
- 背景：医保场景下需要对处方/用药等行为进行实时合规质控（性别/年龄/儿童专用/保险类型/诊断/剂型/给药途径/适应症等）。
- 目标：
  - 高效管理数千条规则（目前已导入并展示 1173 条）。
  - 提供友好的前端管理界面：规则列表/筛选/搜索/分页/启停/版本与详情预览。
  - 提供标准化 API：认证、分页查询、筛选与搜索，支持后续系统集成。
  - 支持规则生命周期管理与版本管理，便于审计与回溯。

## 系统架构概述
```
Monorepo（health-qc-monorepo）
├── apps
│   ├── yibao-web        # 前端应用（Vue 3 + Vite + Ant Design Vue + Tailwind）
│   └── medqc-web        # MedQC 后端（FastAPI）
├── packages             # 共享包（schemas / ui-qc / web-utils 等）
├── infra                # 基础设施（Supabase/Edge Functions、PDF服务等）
├── docs                 # 项目文档
└── scripts              # 启动脚本/健康检查/集成脚本等
```

- 数据流：
  1) 前端 apps/yibao-web 通过 ApiService 调用后端 `/api/*` 接口。
  2) 后端服务负责认证、规则数据查询（分页/筛选/搜索）与管理。
  3) 持久化使用 Supabase（Postgres）表：`yibao_rules`、`yibao_rule_conditions`、`yibao_rule_actions`、`yibao_rule_triggers` 等。

- 关键页面：规则列表页面（RulesList.vue）
  - 列：规则编号/规则信息（名称+描述）/类型（中文标签）/严重级别/状态/版本/更新时间/操作
  - 快速筛选：规则类型、严重级别、启用状态；查询与重置按钮同列靠右
  - 分页：支持每页 10/15/20/30/50/100，显示“第 X-Y 条，共 N 条规则”

## 技术栈说明
- 前端：
  - Vue 3（Composition API）、Vite、TypeScript
  - Ant Design Vue（表格、表单、选择器、Tag、Switch、Drawer、Modal 等）
  - Tailwind CSS（辅助布局与视觉优化）
- 后端：
  - FastAPI（apps/medqc-web/backend，参考 scripts/start_backend.sh）
  - 规则相关服务对外暴露 RESTful API（`/api/rules` 等）
- 数据层：
  - Supabase（PostgreSQL）
  - 表：`yibao_rules`、`yibao_rule_conditions`、`yibao_rule_actions`、`yibao_rule_triggers`
- 认证：
  - JWT（`/api/auth/login` 获取 access_token / refresh_token；`/api/auth/refresh` 刷新）
  - 前端在 ApiService 中透传 Authorization: Bearer <token>

## 部署与运行（概览）
- 后端（FastAPI，仅供参考）：
  - `scripts/start_backend.sh` 会创建/激活虚拟环境并启动 Uvicorn（默认 8001）。
- 前端（开发）：
  - 在 monorepo 根执行 `pnpm -w dev` 或进入 `apps/yibao-web` 执行 `npm run dev`。
- 环境变量：
  - 前端通过 `VITE_API_BASE_URL` 指定 API 基础路径（默认同源）。

## 安全与权限（概览）
- 401：未认证或 token 过期，前端会重定向到登录。
- 403：已登录但权限不足，前端会提示“没有权限访问该资源”。
- 前端在请求拦截器中注入 Authorization 头，响应拦截器处理 401 自动刷新（若存在 refresh_token）。

## 术语表
- 规则：用于限制或提示的业务逻辑单元。
- 严重级别：信息（info）/警告（warn）/阻断（block）。
- 启用状态：是否在运行时生效。

