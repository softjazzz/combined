# 临床申诉审核动作安全 Implementation Plan

**Goal:** 审核申诉必须由具备质控结果 REVIEW 权限的用户执行，且状态变更与审核历史同事务；审核与撤回不能互相覆盖已终结申诉。

**Architecture:** 保留现有审核/撤回端点，路由只做身份权限、脱敏校验、错误映射与响应；单一服务在事务中固定 `qc` schema 并锁定申诉行，审核同时写历史和主状态，撤回共用该锁与状态合同。本批不接首页待办或前端旧模拟申诉页。

## 根因与真实证据

- 当前 `appeals.py` 审核路由没有角色权限检查，除 withdrawn 外允许已终态再次审核；先调用适配器插历史，再独立更新主表。第二次写失败会留下无法对齐的审核历史，重复请求可改写终结结论。
- 主 Agent 只读核查 `qc.qc_appeals` 5 条：`pending=2 / accepted=2 / rejected=1`，审核人 5 条均空。`accepted` 是历史状态漂移，不得当成可审核 `pending`；不回填或改写历史。
- `ResourceType.QC_RESULTS` 已配置 `REVIEW`：admin 和 qc_manager 允许，医生与质控专员没有。路由可复用现有 `require_permission`，不新增角色硬编码。
- 活跃 V5 首页只显示任务待办；旧 `/dashboard` 重定向，旧 `AppealList.vue` 使用模拟权限/用户 ID，前后端 DTO 也漂移。本批只先关闭审核动作风险，不能称“临床申诉待办”交付。

## 固定合同与失败语义

1. 只有 `pending/reviewing` 可审核；`approve -> approved`、`reject -> rejected`，`request_info/forward -> reviewing`。任何其他状态（含历史 `accepted`）返回 409，不插历史、不改主表。不存在返回 404。
2. 无 REVIEW 权限返回 403；缺失登录身份按现有权限装饰器 401。数据库/会话不可用返回 503，不能报告成功；响应和日志不输出 SQL 参数、申诉理由或患者数据。
3. 对同一申诉加行锁，主状态与审核历史一次提交；撤回由申诉人在同一锁下执行，任一写失败必须回滚。SQLite 隔离测试只验证顺序状态与事务行为，不能代表 PostgreSQL 并发锁验收。真实业务库不写入。
4. 不修改创建、更新、列表或历史 `accepted` 数据。共享池还是个人队列、人工缺陷来源和病历审核状态机均待业务确认，另立闭环。

## 分工与验收

- Sol / medium 实现代理仅拥有新 `backend/app/services/appeal_review_service.py` 与 `backend/tests/unit/test_appeal_review_transaction.py`，实现单事务服务和回滚/终态反例，不暂存、不提交。
- 主 Agent 拥有 `backend/app/routers/appeals.py`、HTTP 权限/错误语义测试和本文/滚动计划/PRD，独立审查关键 diff、状态映射、数据库调用量及真实只读数据。
- 先跑新服务/路由聚焦测试与相邻申诉测试，再执行 Ruff、编译、编码及适用前端门禁；隔离验证完成后中文提交。数据库写入和真实并发验收仍待授权。

## 验证与边界

- 主 Agent 只读核对实际 `qc.qc_appeal_reviews.metadata` 为 JSONB，审核时间列为带时区时间戳；ORM 使用 PostgreSQL JSONB / SQLite JSON，相关写入使用明确的 UTC 时间。服务在 PostgreSQL 事务内把搜索路径限定为 `qc`，避免默认 `public` 同名表抢先命中。未修改生产数据。
- 独立审查发现旧撤回端点的先读后写可覆盖审核终态、默认搜索路径可能写错表、FastAPI 自动校验会在权限前返回带原文的 422；主 Agent 已按调用链逐项收敛并补反例。复核又发现手工校验令 OpenAPI 请求体消失，现从原 DTO 恢复两端点的请求 schema。
- HTTP 与事务隔离测试 28 条通过，覆盖权限先于审核正文校验、缺失身份、状态冲突、历史 `accepted`、撤回/审核顺序保护、OpenAPI 请求合同、原子回滚和错误信息脱敏；相关文件 Ruff 与 Python 编译通过。SQLite 测试不能证明 PostgreSQL 的行锁竞争或真实提交流程。
- 本批仅加固已有审核/撤回动作。首页临床申诉待办、共享池/个人队列归属、旧申诉列表 DTO 和创建/更新接口仍未交付或修复；不将本批标为 PRD 待办完成。
- 复核确认相邻 `PUT /api/v1/appeals/{id}` 仍先读 `pending` 再按 id 无条件更新；若与审核并发，理由/证据可能在终态后变化。它不会覆盖审核状态或历史，但违反更新权限的并发语义，列入下一独立小闭环，不在本批顺带扩展。
- 提交前门禁：编码检查通过；前端 lint 为 0 errors / 953 warnings，类型检查通过；全量单测 `1156 passed / 3 failed`，失败均在本批未修改的 `SingleRecordQcResultPanel.spec.ts` 与 `QcRecordReviewPreview.spec.ts`，与前序独立复现的基线一致。Python 聚焦 28 条及 Ruff/编译通过。

## 状态

审核/撤回动作代码与隔离测试、独立复核已完成，待提交；Goal 保持 active。
