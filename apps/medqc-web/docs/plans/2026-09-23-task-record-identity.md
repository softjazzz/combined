# 任务病例三坐标 Implementation Plan

**Goal:** 为任务病历关联建立可区分跨机构、跨患者同次就诊号的三坐标持久化合同，保留历史任务读取，不把结构就绪误报为场景质控已贯通。

**Architecture:** `qc_task_records` 新增可空的 `institute_id/patient_id/visit_id`；旧行保持三列全 NULL，新行必须三列完整。旧模式按 `(task_id, record_id)` 唯一，新模式按 `(task_id, institute_id, patient_id, visit_id)` 唯一，取消会阻止合法新病例的旧全局唯一索引。病例身份权威仍由现有 `CaseRef` 表示，不能把 JSON 复合键写进 `record_id`。

**Tech Stack:** Alembic、PostgreSQL、SQLAlchemy、pytest；本批只交付迁移代码，不执行生产/本机业务库迁移。

## 业务证据与取舍

- 真实任务详情和抽样保存只持有单个 `record_id`；`re_analyze_task` 也只把该值交给演示 `QCService.evaluate`。这条链不能唯一表示 `(institute_id, patient_id, visit_id)`，迁移单独完成不等于真实执行已可用。
- 主 Agent 在 `transaction_read_only=on` 的本机库核对：revision `20260915_000044`；`qc.qc_task_records` 35 行、`public` 同名表 0 行；两表均无三坐标。实际 `qc` 的 `task_id/record_id` 可空且无旧全局唯一索引，`public` 两列非空且有旧全局唯一索引；当前两表非法空值与旧键重复组均为 0。
- 方案 A：三坐标序列化进旧 `record_id`，无需迁移但会碰到 `VARCHAR(100)`、旧唯一键及消费者把它当就诊号的问题，拒绝。方案 B：只加三列而保留旧全局唯一，跨机构同 `visit_id` 仍会冲突，拒绝。选择分模式部分唯一索引与 all-or-none CHECK。
- 不自动回填历史 35 行，也不从 `record_id` 猜测机构、患者；若旧数据在迁移时出现空值或重复，迁移失败并要求人工核对，不删除或修复数据。
- revision46 超过 200 行，因为同一 Alembic 修订必须闭合双 schema 探测、旧数据预检、约束/索引替换与安全降级；这些步骤共用一次 DDL 事务和同一版本号，拆到既有迁移或碎片模块会使升级/降级边界难以审计。没有改变其他模块行为。

## 固定合同与失败语义

1. revision 46 依赖 revision 45；仅对存在的 `qc/public.qc_task_records` 生效。先检查旧 `task_id/record_id` 非 NULL、ASCII 空白后非空、无重复，再以 CHECK 加强非空约束，保留部署前的物理 nullable 属性。预检失败必须报可定位错误，不以数据库写入修正历史。
2. 三坐标三列同时 NULL 表示历史未知；新关联必须全部非 NULL 且去空白后非空。部分填写、空串、同任务相同三坐标均失败。`record_id` 继续承载兼容展示值，不承担新病例唯一身份。
3. 旧全局 `(task_id, record_id)` 唯一索引若存在则替换为历史模式部分唯一；新模式部分唯一以三坐标为准。保留既有主键、外键、普通查询索引、scene/record_type。迁移降级不能静默删除病例数据；若现代关联无法安全映射回旧唯一合同，必须明确拒绝降级。
4. 迁移未执行之前，应用不得写三坐标列；新场景抽样仍 409。`qc_tasks` 目前只有旧 `record_ids` 文本配置列；下一小批必须另定并持久化 `record_refs` 配置列，不能把三坐标字典塞回旧字段，也不能从旧 `record_id` 反推三坐标。

## 实施与验收

### Task 1: 迁移与 ORM 一致性

**文件：** `backend/alembic/versions/20260923_000046_task_record_case_identity.py`、`backend/app/database/models/qc.py`、`backend/tests/unit/test_task_record_identity_migration.py`。

1. 先写隔离反例：历史全 NULL 可保留；新模式同任务同 `visit_id` 不同机构/患者可共存；旧模式重复、现代三坐标重复、部分填写或空串均拒绝；预检在旧空值/重复时失败；分别覆盖 `qc` 无旧索引和 `public` 有旧索引。
2. 跑单文件 pytest 证明反例失败，再实现最小 Alembic 操作和 ORM 声明；不改任务路由、抽样服务、前端或真实数据库。
3. 跑聚焦 pytest、迁移静态检查及适用 Python 检查；主 Agent 核对 SQL/索引语义及真实只读 schema，独立审查关键 diff。确认新列不被当前旧保存链误写，保持场景 409。
4. 记录 revision 44/45/46 代码与实际库版本差异。未经明确授权，不运行 upgrade/downgrade，也不做真实写入/并发验收；不能以隔离测试替代后者。

### Task 2: 后续应用合同（本次不伪称完成）

**预期文件：** 后续任务主表 `record_refs` 迁移与模型、`backend/app/schemas/tasks.py`、`backend/app/routers/tasks.py`、`backend/app/services/task_sampling_service.py`、`backend/app/services/task_sampling_persistence.py` 及各自聚焦测试，前端 API/表单另批处理。

1. 新任务显式接收完整 `record_refs` 并保存在新字段，拒绝不完整身份与混用旧 `record_ids`；历史草稿继续原兼容合同。同一任务内不得混用旧/新身份模式。候选来源需先按门急诊、运行、终末分别验证，不从任务场景标签推定病例事实。
2. 抽样关联原子保存三列，重放返回相同三坐标；详情只搬运三列，不用 `CaseRef.from_mapping` 的 `record_id` 回退构造新身份；旧全 NULL 行显示“身份未确认”，不开放文书导航。
3. 重新质控必须改用已持久化三坐标送真实 workspace `record_refs` 链，且权限、状态回写、失败语义和调用量单独验收；当前演示 `QCService` 不能作为完成证据。

## 状态

Task 1 的代码与隔离验收已完成；Task 2 未开始。迁移45/46未执行，业务库仅只读核查。PRD 总目标继续 active。

## 主 Agent 验收与剩余风险

- 独立复核发现三处 P2：同名错误 CHECK 可能被跳过、升级改变 qc 旧列物理可空性而降级未还原、普通 `trim` 漏 tab/换行。已分别改为同名 CHECK 失败关闭、以包含 `IS NOT NULL` 的 CHECK 保留物理 nullable、显式 ASCII 空白字符集双参数 `trim`；增加真实 qc/public 双表拓扑的隔离测试。
- 主 Agent 独立执行迁移、场景和相邻任务回归，共 111 passed；Ruff 与 `alembic heads` 检查通过。纯 SELECT 的实际 PostgreSQL 连接确认 `transaction_read_only=on`，双参数 `trim` 对空格、tab、换行、回车、换页、纵向制表符及组合均返回空，revision 仍为 `20260915_000044`。
- migration46 仅为代码，实际库尚无三坐标列；没有运行真实 PostgreSQL DDL、升级/降级、行锁或并发写测试。隔离 SQLite 与 Alembic mock 不能替代生产等价验收。当前 `qc` 表 35 行既有数据保持不动，`public` 表 0 行；旧字段非法空值和重复组均为 0。
- 降级在存在任何新三坐标数据时明确拒绝；全 legacy 降级会恢复 revision45 ORM/Alembic 的旧全局唯一合同，因真实 qc revision44 物理上原本缺失该索引，降级后的物理索引可能比迁移前更严格。真实执行前须审阅演练并获授权。
- 新场景抽样继续 409，主表 `record_refs` 持久化、场景候选、原子保存与真实 workspace 执行仍未接通；此提交不能作为三场景任务或业务数据表已具备的验收结论。
