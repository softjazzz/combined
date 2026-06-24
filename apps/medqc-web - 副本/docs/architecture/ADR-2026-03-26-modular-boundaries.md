# ADR-2026-03-26: MedQC Core Module Boundaries

## Status
Accepted

## Date
2026-03-26

## Context
P2 重构需要将 `auth/sync/drg/records` 从“路由承载业务逻辑”迁移到“路由薄层 + 应用服务层”。如果不建立明确边界和 owner，后续功能迭代会重新回到耦合状态，导致回归率升高、排障困难。

## Decision
1. 核心域采用统一分层：
   - Router: 协议层（鉴权、参数校验、响应壳）
   - Service: 业务规则与编排
   - Repository/Store: 数据访问与持久化细节
2. 核心域间依赖规则：
   - `auth` 只向外提供身份与权限能力，不依赖 `drg/records/sync` 业务模块。
   - `sync` 可依赖 `auth`（操作人上下文）和数据访问层，不依赖 `drg/records` 路由或页面语义。
   - `drg` 与 `records` 仅通过共享 schema/service 接口交互，不允许跨域直接引用对方 router。
3. 禁止模式：
   - Router 中写复杂业务分支或多数据源编排。
   - 跨域直接调用他域 router 方法。
   - 以前端参数格式驱动后端长期领域模型。

## Ownership
- auth: Backend Security Owner
- sync: Backend Data Owner
- drg: Backend DRG Owner
- records: Backend EMR Owner
- cross-cutting (observability/release gate): Tech Lead + SRE

## Enforcement
1. Code review 门禁：
   - 触碰 `backend/app/routers/{auth,sync,drg,medical_records}*` 必须至少 1 名后端 owner 审核。
2. Release gate：
   - 必须通过 `openapi_contract`、`auth_guard`、`metrics_catalog`。
3. 测试门禁：
   - 领域变更必须包含对应单测/契约测试更新。

## Consequences
- 正面：降低耦合与回归风险，提升并行开发效率。
- 代价：短期改造成本上升，需要补齐服务层与测试资产。

## Follow-ups
- 按域将超大 router 继续拆分，保持单文件核心逻辑 <= 500 行。
- 在 CI 中加入模块依赖扫描（后续任务）。
