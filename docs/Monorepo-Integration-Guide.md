# Health QC Monorepo 集成说明（Yibao + MedQC）

本指南记录将医保质控（Yibao）与病案质控（MedQC）整合进单一 Monorepo（pnpm workspaces）的落地情况、运行方法和后续开发要点，便于后续成员或模型快速继续开发。

---

## 1) 目录结构

```
health-qc-monorepo/
├─ apps/
│  ├─ medqc-web/                # MedQC 前后端（Vue3 + Vite + FastAPI）
│  ├─ yibao-web/                # Yibao 前端占位（后续接入）
│  └─ edge-functions/           # 公共/示例 Edge Functions 源码
├─ packages/
│  ├─ web-utils/                # 前端复用工具（Supabase client、ApiWrapper 等）
│  ├─ rule-engine/              # 规则引擎（Deno/Node 适配；用于医保/病案通用规则）
│  ├─ ui-qc/                    # 共享 QC UI 组件库
│  ├─ supabase-kit/             # Edge Functions 辅助（CORS/auth/errors）
│  └─ schemas/                  # 共享 TS 类型（DB/OpenAPI）
├─ infra/
│  └─ supabase/                 # 统一数据库迁移（yibao_*、medical_*、llm_*）
├─ pnpm-workspace.yaml          # 工作区定义（apps/*, packages/*）
├─ package.json                 # 根脚本（dev/build/lint/type-check）
└─ README.md                    # 简要说明与文档入口
```

关键点：
- 两个业务应用共享一套 workspace 与复用包，减少重复实现。
- 共享包通过 pnpm workspace 软链接到各 app，统一版本与升级。
- 原目录 `/home/ubuntu/MedQC0904` 未改动；本仓库为迁移副本，不影响旧代码。

---

## 2) 技术与运行时

- 前端：Vue 3 + TypeScript + Vite + Pinia + Ant Design Vue
- 后端：FastAPI (Python 3.10+)
- 数据层：Supabase（PostgreSQL + PostgREST + Edge Functions）
- 包管理：pnpm workspaces

---

## 3) 安装与环境

根目录安装：

```bash
cd /home/ubuntu/health-qc-monorepo
pnpm install
```

MedQC 后端（可选，本地运行后端）：

```bash
cd apps/medqc-web/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4) 启动与代理

### 4.1 前端（端口 3000）

```bash
cd /home/ubuntu/health-qc-monorepo
pnpm -r dev
# 或仅启动 medqc-web：
pnpm --filter "./apps/medqc-web" dev -- --host 0.0.0.0 --port 3000
```

Vite 开发代理（`apps/medqc-web/vite.config.ts`）：
- 所有以 `/api` 开头的请求代理到 `http://localhost:8001`（FastAPI）。
- 前端请一律使用相对路径（如 `/api/...`），避免硬编码 `http://localhost:8001` 或外网 IP，统一走代理以避免跨域与直连失败。

前端环境（`apps/medqc-web/.env` 建议）：

```
VITE_SUPABASE_URL=<your_supabase_url>
VITE_SUPABASE_ANON_KEY=<your_anon_key>
VITE_API_BASE_URL=
```

说明：`VITE_API_BASE_URL` 留空时，代码应走相对路径，经由 Vite 代理到 8001。

### 4.2 后端（端口 8001）

```bash
cd /home/ubuntu/health-qc-monorepo/apps/medqc-web/backend
source .venv/bin/activate  # 如已创建
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

后端环境（`.env` 建议项）：

```
JWT_SECRET=dev_XXXX
ENV=development
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=<anon_key>
SUPABASE_SERVICE_ROLE_KEY=<service_role_key>  # 服务端优先使用
RECORDS_TABLE=medical_records_test            # 当前测试表
DOCUMENTS_TABLE=medical_documents_test        # 当前测试表
```

要点：
- `app/core/settings.py` 优先使用 `SUPABASE_SERVICE_ROLE_KEY`，无则回退 `SUPABASE_ANON_KEY`。
- `app/core/supabase_client.py` 与之保持一致。
- 表名用 `RECORDS_TABLE`、`DOCUMENTS_TABLE` 配置，需与 Supabase 实际一致（测试环境使用 *_test）。

---

## 5) 今日完成的关键改造

- Monorepo 搭建：`pnpm-workspace.yaml` 指定 `apps/*` 与 `packages/*`。
- 共享包：
  - `packages/web-utils`：抽取 Supabase 客户端、通用 `ApiWrapper`、简化错误处理。
  - `packages/rule-engine`：为医保规则评估（Yibao Edge Function）提供复用位点。
- MedQC 集成：
  - 前端：统一改用相对 `/api` 走代理；补齐缺失依赖与类型；为缺失模块创建最小占位（如 `src/lib/analytics-engine.ts`）。
  - 后端：设置管理统一（pydantic-settings）；Supabase 客户端优先 service role；修复 Supabase 响应取数方式一致性。
  - 代理：`vite.config.ts` 将 `/api` 代理至 `8001`，前端 API 统一走代理。
- 环境：
  - 前端 `.env` 留空 `VITE_API_BASE_URL` 强制走代理。
  - 后端 `.env` 指定 `RECORDS_TABLE=medical_records_test`、`DOCUMENTS_TABLE=medical_documents_test` 与现有数据一致。

---

## 6) 连通性与自检

- 通过前端代理验证 LLM 解析接口：

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST http://127.0.0.1:3000/api/llm/parse-text \
  -H "Content-Type: application/json" \
  --data '{"apiConfig":{"apiEndpoint":"https://dashscope.aliyuncs.com/compatible-mode/v1","apiKey":"test"},"requestBody":{"model":"qwen2.5-14b-instruct","messages":[{"role":"user","content":"hello"}]}}'
```

- 页面功能快速检查：
  1) 能登录（说明后端认证链路正常）；
  2) 病历列表显示 Supabase `medical_records_test` 数据；
  3) 详情页文档分类可用（表 `medical_documents_test`）；
  4) LLM 配置可保存（`/api/qc/llm/configs`）；
  5) LLM 解析经 `/api/llm/parse-text`，不出现直连 8001 的错误；
  6) 解析结果可经 `/api/medical-records` 写回数据库。

---

## 7) 后续开发建议

- 沉淀规则引擎：将 Yibao `evaluate-rule` Edge Function 核心提炼到 `packages/rule-engine`，两端共用；
- 全面清理硬编码地址：
  - grep `:8001`、`localhost:8001`、外网 IP，统一改相对路径 `/api/...`；
- 完整化共享包：
  - `web-utils`：错误处理、鉴权拦截、分页/过滤构建器；
  - `ui-qc`：常用质控组件（分类、结果展示、报告导出等）；
- 数据库迁移与一致性：
  - 将 MedQC 与 Yibao schema 融合至 `infra/supabase`，用分层命名（`yibao_*`、`medical_*`、`llm_*`）；
- 测试与类型：
  - E2E（Cypress/Playwright）、后端（pytest）；
  - 统一接口与类型输出到 `packages/schemas`。

---

## 8) 参考文件（关键入口）

- `apps/medqc-web/vite.config.ts`（代理设置）
- `apps/medqc-web/backend/app/core/settings.py`（环境/密钥优先级）
- `apps/medqc-web/backend/app/core/supabase_client.py`（Supabase 客户端）
- `apps/medqc-web/backend/app/routers/*`（主要 API）
- `packages/web-utils/src/lib/supabase-client.ts`（共享 Supabase 客户端）

---

维护者：协作助手（今日更新）

## Yibao 独立运行与规则引擎
- 前端端口：3001，顶层导航“医保规则质控”，独立登录与 Dashboard
- 规则引擎：已提供本地评估（@health-qc/rule-engine）与 Edge Function（infra/supabase/yibao/functions/evaluate-rule）
- 工具复用：@health-qc/web-utils（Supabase、ApiWrapper）、@health-qc/ui-qc（通用组件）

## 开发命令
- MedQC：`pnpm --filter "./apps/medqc-web" dev`
- Yibao：`pnpm --filter "./apps/yibao-web" dev`
- 同时启动：`pnpm dev:all`
