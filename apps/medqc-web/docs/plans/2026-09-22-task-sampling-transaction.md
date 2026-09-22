# 抽样原子保存 Implementation Plan

**Goal:** 抽样关联与任务状态全部成功或全部回滚；重复请求读取已经保存的结果，不重复抽样或插入。

**Architecture:** 复用 `database.connection.SessionLocal`，用单个同步事务职责保存抽样结果，由路由在线程池调用一次。事务持有任务行锁，重验任务状态/场景/抽样配置；不修改 24 个路由共享的兼容适配器，不新增事务框架。场景候选尚未接通，上一批 409 保护继续保留。

**Tech Stack:** FastAPI / SQLAlchemy / PostgreSQL / anyio / pytest，隔离内存 SQLite 验证事务回滚，PostgreSQL 编译验证行锁语句。

## 基线与根因

- 基线 `e61da15a4`，开工工作区干净。上一 Goal 轮次是 progress：提交场景合同、测试和验收证据，但未执行迁移。
- 主代理亲自读取 `tasks.py` 抽样入口和 `supabase_client.py`：先插入关联，后更新状态，两次 `_exec_*` 独立 commit；第二步失败会残留关联。
- `async_execute` 在 execute_async 异常后再次 execute，不适合包裹有不确定提交结果的事务保存。新保存操作不得走此重试层；兼容适配器本批不改。
- `TaskUpdateRequest` 可改 status，故不能仅凭路由先前读到的 draft 保存；抽样配置也需要在行锁内重新对比，不能覆盖并发更改。
- 本批不处理任务分配、执行规则、归档事实补齐、历史数据修复或数据库迁移。另一个 Sol / medium 子代理仅调查病历 ID 与场景候选权威读取链，为后续任务提供证据。

## 固定合同

1. 仅 draft 可新保存；sampling 返回同一批已持久化的关联结果，包括零条，不重新读取候选。assigned/in_progress/completed/cancelled 或未知状态拒绝 409。
2. 用任务行 `FOR UPDATE` 串行化同一任务的两次保存。并发第二请求在拿到锁后，若已 sampling，返回首次结果而非自己随机得到的候选。
3. scene 非 NULL 继续明确拒绝，不能绕过上一批场景未接通保护；初始路由和持锁后状态变更都需要覆盖。
4. 草稿若已有遗留关联拒绝，不删除、不自动修复；已 sampling 若实际关联数量与 total_records 不同，也拒绝。
5. 新保存对比 scene、date_range、department_filter、record_ids、sampling_method、sampling_config；TEXT JSON 与已解码结构先按结构归一，不引入 digest 或名称推测。
6. 候选 ID 非空字符串且不重复。关联插入和任务更新使用同一事务并核对受影响行数，任意插入/更新/提交失败回滚；不自动重试写操作。
7. HTTP 合同保持 `{task_id, sampled_count, records:前20条}`。不存在 404、状态/配置冲突 409、数据库故障固定 503；不泄露底层 SQL。失败不能返回成功计数。

## 分工与步骤

### 保存职责（scene_backend_review，Sol medium）

文件：新 `backend/app/services/task_sampling_persistence.py`、新 `backend/tests/unit/test_task_sampling_persistence.py`。

1. 先增加事务成功、插入失败、更新失败、提交失败、重复请求、零条、超过20条返回、遗留关联、配置漂移等反例。
2. 新模块承载完整的原子保存职责，不做逐函数拆片。轻量 SQLAlchemy table/column + SELECT *，避免反射整库，也不要求未执行的 scene 迁移才能读取旧任务。
3. 独立内存测试表与 Session 工厂，禁止使用业务库 Session 或 Base.metadata 创建真实表。
4. 编译 PostgreSQL SELECT 断言 FOR UPDATE；真实 PostgreSQL 并发和故障注入写验收仍需授权，SQLite 不作为行锁并发证明。

### 路由与验收（主代理）

文件：`backend/app/routers/tasks.py` 抽样入口、`backend/tests/unit/test_task_sampling_safety.py`、本文、滚动计划与 PRD。

1. 抽样成功后仅调用保存函数一次，移除旧两次适配器写入；sampling 跳过候选读取。
2. HTTP 测试覆盖状态拒绝、重放、错误不重试、事务函数返回结果原样搬运；保留旧场景与数据源失败测试。
3. 只读对比旧适配器与新 SessionLocal 的 search_path、数据库和 qc_tasks/qc_task_records 实际表 OID，防止写错同名表；不输出凭据或患者原文。
4. 运行相关 pytest、编码、lint --no-fix、type-check、unit；主代理独立审查关键差异后提交。

## 验收状态

代码闭环已完成。业务数据库保持只读；迁移45、真实写流程及 PostgreSQL 并发验收均尚未授权。本批不能标记完整三场景抽样或 PRD 完成。

### 主代理验收与审查更正

- 最终相关后端 6 文件 **126 passed**，包含事务层 30 条和 HTTP 安全层 31 条；覆盖插入/更新异常、受影响行数为零、提交前异常、零条重放、超过 20 条首次与重放一致、配置漂移、旧表无 scene 列及状态反向变化。
- 主代理发现并补强两个边界：首次按候选顺序返回与重放按 UUID 排序会不一致，现统一读取持久化记录；路由先读 sampling、锁内已退回 draft 时不得把未读取的候选当零条保存，现返回冲突。
- 独立审查指出 Core insert 不会使用 ORM 的 `defect_count` Python 默认值，按模型建表时该非空字段缺失会失败。显式写入 0，测试表加入相同 NOT NULL 无默认值约束。主代理另建隔离表，移除该字段稳定失败且完整回滚，恢复修复后保存与重放一致。
- **证据更正**：上述问题不是已验证的本机业务库故障。本机只读查询证明 qc.qc_task_records.defect_count 实际允许 NULL 且有 server default 0，与模型新建表不同。修复解决模型约束兼容风险；不得把审查中的“生产表必然失败”作为真实库结论引用。
- 两套连接均为只读，实际任务表 OID 为 qc.qc_tasks=17085、qc.qc_task_records=17111，数据库与 search_path 一致。过程脚本在 `.tmp/0910-full-audit/`，不提交。
- `npm run type-check` 通过；`npm run lint -- --no-fix` 为 0 errors / 953 warnings。全量前端测试 130 文件通过 / 4 文件失败，1140 passed / 5 failed：3 条为前序已独立复现的既有质控组件断言，另 2 条路由超时；这两个路由文件单独复跑 5 条全部通过。本批无前端变更，不宣称全量门禁全绿。
- 本批无新增 LLM 调用；事务成功分支最多 5 条 SQL 操作（锁任务、数关联、插入、更新、读取前 20），重放 3 条，不包含入口读任务及候选查询。此为静态调用路径计数，不是数据库实测性能；真实并发锁等待和提交响应丢失仍需授权后的 PostgreSQL 验收。
- 提交前运行暂存文件编码与差异检查。继续采用按路径提交；跳过提交钩子的原因仅为根钩子会对整个文件执行 eslint/prettier 自动改写，适用检查手工执行，未关闭 CI 门禁。

### 后续场景链路边界

Sol / medium 子代理只读调查，主代理逐项复读以下关键路径，结论用于后续独立任务，本批不扩展实现：

- `backend/app/services/case_identity.py:8` 的权威身份为机构、患者、就诊三坐标；`as_key()` 输出 JSON 数组键。
- `backend/app/database/models/qc.py:190` 的任务关联仅有 `record_id VARCHAR(100)`，唯一键为任务和 record_id，未持久化三坐标。不能直接用可能超过 100 字符的复合键替代并声称兼容。
- `backend/app/routers/records.py:180` 将 record_id 当 visit_id 或 mr_no 查询，没有解析三坐标键；`tasks.py` 的重新质控入口仍调用 `QCService.evaluate({record_id})`，该服务是演示分析器，不能作为真实病例执行证据。
- `backend/app/routers/qc_sichuan.py:1946` 的正式 LX0609 批处理拒绝 record_ids，要求 record_refs；可复用结构化身份合同，但不得因此改动本批之外的规则执行器。
- 所以下一批必须先明确任务关联、详情和真实执行链的身份合同。新增身份列/唯一性迁移需单独设计和授权，不能只修改抽样过滤后放行场景保护。
