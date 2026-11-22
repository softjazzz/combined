# Agents 指南（历史资料）

> 本文记录早期医保质控项目的共享包和 Supabase 集成方案。现行开发与提交约定见 [仓库 AGENTS](../AGENTS.md) 和 [MedQC AGENTS](../apps/medqc-web/AGENTS.md)，应用启动见 [MedQC 本地启动](../apps/medqc-web/README.md#本地启动)。

目标
- 快速理解本仓库的单体多项目（Monorepo）结构与运行方式
- 在不影响 `apps/medqc-web` 的前提下，推进 `apps/yibao-web` 的开发
- 复用共享能力（工具层、UI 组件、规则引擎）并保持一致的最佳实践

仓库结构（关键部分）
- `apps/medqc-web/`: 已运行的病案质控前后端（前端 3000，后端 8001）
- `apps/yibao-web/`: 新建医保质控前端（开发端口 3001）
- `packages/web-utils/`: 工具层（Supabase 客户端、ApiWrapper、通用工具）
- `packages/ui-qc/`: 共享 UI 组件（示例：RecordCard）
- `packages/rule-engine/`: 规则引擎核心（由 Yibao Edge Function 迁移的核心逻辑）
- `infra/supabase/`: Supabase 的迁移与 Edge Functions（yibao、medqc 两套）
- `docs/Monorepo-Integration-Guide.md`: 已完成的单仓整合说明

运行与开发
- 前端（MedQC）：`pnpm --filter "./apps/medqc-web" dev -- --host 0.0.0.0 --port 3000`
- 前端（Yibao）：`pnpm --filter "./apps/yibao-web" dev -- --host 0.0.0.0 --port 3001`
- 后端（MedQC）：FastAPI，端口 `8001`，前端通过 Vite 代理 `/api` 访问

应用导航与信息架构（分应用）
- MedQC 导航建议：`病历`、`文档/解析`、`质控`、`LLM配置`、`统计/分析`、`设置`
- Yibao 导航建议：顶层即 `医保规则质控`，下设：`规则库`、`触发器`、`动作/消息模板`、`实时提醒沙箱`、`违规与审计`、`看板`、`设置`
- 说明：文案与结构在各 app 内配置；共享组件与权限 key 通用以复用

环境变量（前端）
在各自 app 目录下配置 `.env`：
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_API_BASE_URL`（留空，使用 Vite 代理）

共享工具层使用
- 从 `@health-qc/web-utils` 引入：
  - `supabase`：统一初始化的 Supabase 客户端
  - `query`、`buildQuery`：统一接口风格与错误返回
- 示例（Yibao）：`apps/yibao-web/src/lib/api.ts`

UI 复用
- 从 `@health-qc/ui-qc` 引入共享组件
- 示例组件：`RecordCard`
- 示例（Yibao）：`apps/yibao-web/src/views/Home.vue`

规则引擎接入
- 目标：对齐 `@health-qc/rule-engine` 的表达式与消息渲染
- 前端快速验证：在 `apps/yibao-web/src/lib/rules.ts` 接入客户端校验
- 服务端/Edge Function：可在 `infra/supabase/yibao/functions` 下实现/迁移

API 代理与调用约定
- 所有浏览器端 API 调用均应走相对路径 `/api/...`，由 Vite 代理转发到后端
- Supabase 直连仅限前端读取匿名权限允许的数据；写入/敏感操作走后端

数据库与表
- `yibao_*`：医保项目相关表（规则、触发器、任务等）
- `medical_*`：病案项目相关表（病历、文档）
- `llm_*`：LLM 配置与调用
- 注意确保 RLS 与权限配置与业务一致

代码规范与错误处理
- 统一使用 `ApiWrapper` 包装数据库交互
- 前端保留统一错误提示与日志入口（`web-utils` 的 error-handler）

开发建议
- 新增能力优先沉淀到 `packages/*`，应用里只做“装配”
- 避免硬编码后端地址，使用代理与环境变量
- 变更前检查 `apps/medqc-web` 的运行不受影响

快速任务路线图（Yibao）
1. 工具层：完善 env，统一数据访问（已起步）
2. UI：搭建“医保规则质控”导航与页面骨架，逐步复用 UI 组件
3. 规则引擎：接入本地校验，择机上云到 Edge Function


