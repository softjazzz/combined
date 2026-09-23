# 任务指定病例三坐标配置 Implementation Plan

**Goal:** 新任务可显式提交并保存完整 `record_refs` 选择意图；旧 `record_ids` 配置不被重新解释，场景抽样在候选来源完成前继续拒绝执行。

**Architecture:** revision47 在现存 qc/public `qc_tasks` 增加可空 JSONB `record_refs`，不回填历史。创建请求用独立严格 DTO 验证三坐标，禁止与旧 `record_ids` 混用或静默去重；仅在非空时写新列。后续抽样候选、关联保存和 workspace 执行使用同一组已保存三坐标，不能从旧 `record_id` 反推。

**Tech Stack:** Alembic、PostgreSQL JSONB、SQLAlchemy、Pydantic v2、FastAPI、pytest。

## 根因与证据

- 任务创建路由只写 `record_ids`，当前 `TaskCreateRequest` 也只有字符串列表；旧候选服务按 `medical_records.id` 查，任务关联保存只读 `id/record_id`。若把三坐标放进旧字段，写入、读取和唯一性所有者都会误当单 ID。
- 主 Agent 只读核查实际业务库 revision44：`qc.qc_tasks.record_ids` 是 JSONB，`public.qc_tasks.record_ids` 是 Text；两表均无 `record_refs`。qc 现有 11 个任务，5 个的旧 `record_ids` 非空。两种旧列型均保留，不修改或回填历史配置。
- 可选 Text JSON 沿用 ORM 声明，但会保留新字段跨 schema 的类型漂移；选择两表统一可空 JSONB。适配层现有 dict/list JSON 序列化可承载该值，ORM 在 PostgreSQL 映射 JSONB、SQLite 隔离测试映射 JSON。
- 新输入可复用 workspace 的三坐标语义，但不从其路由导入 DTO，以免任务模块依赖另一个路由。`CaseRef` 是业务身份，创建 DTO 只负责传输验证。

## 固定合同

1. `record_refs` 每项必须且仅能有非空、去首尾空白的 `institute_id/patient_id/visit_id`。同一请求重复三坐标、与非空 `record_ids` 混用、或非空 `record_refs` 缺少 `scene`，均返回 422，不创建任务；不自动去重、不把 `visit_id` 复制到 `record_id`。创建请求顶层未知字段也拒绝，避免错拼病例范围后静默创建空任务。
2. 旧请求不带或传空数组 `record_refs: []` 时创建 payload 不含新列，保持原兼容；显式 `null` 是非法类型并返回 422。新输入按原顺序保存 JSON 数组，插入返回值必须确认单行且 ID 匹配，响应才可读回相同三坐标。库不可用 503；插入失败保持既有固定错误，日志仅记录异常类型，不泄露 SQL 参数或病例坐标。
3. revision47 依赖46，仅给存在的 qc/public `qc_tasks` 添加可空 JSONB 列；历史全部 NULL。不建立无用途索引。若已有同名列但类型、可空性或默认值不符则失败关闭；降级按固定顺序锁住目标表后跨 schema 预检，任一表存在非 NULL `record_refs` 均拒绝，避免并发写入的任务范围事实被删。
4. 迁移45–47未经授权不执行；因此真实业务库的显式三坐标创建暂不可用。新场景抽样仍返回409，本批不把“保存创建意图”写成“任务病例已抽样”或“质控执行已接通”。

## 分工与验收

- Sol / medium 实现代理所有权：`backend/alembic/versions/20260923_000047_task_record_refs.py`、`backend/app/database/models/qc.py` 的 QCTask 字段、`backend/tests/unit/test_task_record_refs_migration.py`。写失败关闭与安全降级反例、双 schema 类型及历史 NULL 测试，不连接业务库、不执行迁移、不提交。
- 主 Agent 所有权：`backend/app/schemas/tasks.py`、`backend/app/routers/tasks.py`、`backend/tests/unit/test_task_record_refs_create.py`、本文/PRD/滚动计划；先写 malformed/mixed/duplicate/missing-scene 的422，以及新旧创建 payload 和错误语义，再最小实现。
- 独立审查代理只读核对 JSONB 适配边界、既有旧请求兼容、同名漂移、降级数据丢失和调用量。主 Agent 独立复跑聚焦/相邻 pytest、Ruff、编译、编码和适用前端门禁；真实数据库只读复核仍为 revision44，无患者原文产物。
- 完成本批后提交中文 commit；新主表字段、关联三坐标、场景候选、原子保存和真实 workspace 执行必须继续贯通，不以本批完成 PRD 三场景任务。

## 验收与剩余风险

- 独立 API 审查发现异常文本含患者三坐标、空插入响应误报成功、顶层字段错拼被忽略；独立迁移审查发现既有 JSONB 约束漂移与降级预检竞态。主 Agent 逐项复核并补反例，聚焦与相邻测试共 163 passed，Ruff/编译通过。
- 实际适配器使用 `INSERT ... RETURNING *`；只读 PostgreSQL 已确认其 JSON 序列化参数能解析为 JSONB 数组，但未执行真实 INSERT。旧客户端已确认的请求形状在测试中保持通过；未知顶层字段从忽略改为 422，仍有未登记客户端的兼容风险。
- 迁移45–47尚未执行，业务库仍为 revision44。真实 PostgreSQL DDL、并发降级、创建写入与门急诊正样本均未验收；场景候选、关联三坐标保存、详情和真实执行继续待办。Goal 继续 active。
