# LX0609 质控点修复与真实验证长期任务实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不重写质控引擎、不伪造缺失资料的前提下，逐条修复并验证 LX0609 客户质控点，使每个可交付结论都能从源库、本地 CDM、Bundle、Canonical 结果一直追溯到前端证据定位。

**Architecture:** 规则执行器是唯一判定所有者；沿用现有 EvidenceReadSession→Snapshot/MaterialStore→Native→Decision→Canonical 链，证据快照只负责提供冻结资料；Renderer 只生成客户文案；Aggregator/Finalizer 只做状态合同校验和装配。每个规则或低耦合规则族单独形成“真实问题 → 最小修复 → 聚焦测试 → 真实病例复核 → 提交”的闭环。资料或业务口径不足时保持 `data_gap`/`not_executed`，不以关键词、历史任务或备用字段猜测结论。

**Tech Stack:** Python 3.10、FastAPI、SQLAlchemy、PostgreSQL、Pytest、Vue 3、TypeScript、Vitest。

---

## 一、当前基线（开始任务前先复核）

1. 目录仍有 75 条 LX0609 规则，但客户运行合同固定为 70 条：排除客户没有资料的 `033/034/035/041/042`；`025/059` 保持 `not_executed`，`049` 保持暂停。`phase_scope`、实现状态和真实验收状态是不同维度，不能用目录数量代替客户运行数量。
2. 历史任务结果不能作为修复后的验收依据。每次验收必须记录本次任务的代码 SHA、Alembic head、运行规则集合和 Canonical/API 版本；同一病历的新任务不得被旧任务或当前规则目录重新解释。
3. 本机本地库连接正常，但远端源库 PostgreSQL 握手被关闭，`remote_connected=false`、同步状态为 `never`。因此本地缺失资料只能证明“当前本地链路没有资料”，不能证明源库没有资料。
4. 已观察到的高风险问题集中在：评价时点、逐事件业务键关联、来源缺失与不适用混淆、技术错误伪装成数据不足、Canonical/API 结果数量不一致、证据定位失效，以及 Bundle 更新时间落后于最近同步。
5. 已有审计可复现的优先误判包括 `010/020/023/061/064`；它们先作为第一轮闭环对象，不因单元测试通过而视为已关闭。

### 不变式

- 同一病历、同一规则、同一任务只能有一个最新 Canonical 结论；历史任务不覆盖新任务。
- 每个确定问题必须有可解析的证据引用；证据引用必须能定位到真实文书 ID 和字段。
- `technical_error`、来源不可达、关联不确定、尚未成熟不能被降级为确定问题或合规。
- API、页面、HTML、Excel 的状态、原因码、事实和证据必须来自同一 Canonical Envelope。
- 规则总数、执行规则数、结果数和未执行数必须可解释且相互一致。

### 唯一验收台账（机器可验收）

每条规则只保留一行台账，至少包含以下字段：

`rule_id`、`definition_phase`、`implementation_status`、`source_readiness`、`golden_gate_state`、适用性输入、权威时间、来源表/字段、事件业务键、预期状态与 `reason_code`、证据 `source_ref/document_id/field_path`、fixture/真实病例标签、测试节点、commit SHA、运行 manifest hash、源库/CDM/Bundle 对账状态、UI 定位状态、`last_verified_at`、阻断原因和下一门禁。

其中状态必须使用受控枚举：`code_fixed`、`local_verified`、`real_data_blocked`、`not_executed`、`accepted`。`phase_1_target` 或“代码存在”不得直接写成 `accepted`；缺少源库、资料或院方口径时只能进入 `real_data_blocked`。

## 二、任务边界

### 可以先在本机完成的代码闭环

- 时限成熟门和时间冲突：`001/002/003/005/006/007/008/009/051/061/074`（已修过的规则先回归，不重复重写）。
- 确定性误判防护：`050/052/053/055/058` 的状态守卫、事实冲突和有限重试；`064` 按真实反例单独回归。
- 模型输出严格解析：`010/012/015/019/020/023/026` 的受控枚举、单次重试和失败语义。
- 结果投影的一致性、旧任务隔离和证据定位合同。

### 必须等待客户源数据或业务口径的项目

- `010/018/029/031/054/055/069/071/072/073` 的源字段、业务键和真实事件配对。
- `012/015/019/024/033–045/062/063/068/070` 的语义金标或院方口径。
- 远端源库不可连接时，只能做本地链路测试，不能宣称源库—本地库一致。

### 明确保持冻结

- `025/059` 在真实金标、性能和客户签收前保持 `not_executed`。
- 客户没有提供的同意书规则不重新加入客户运行范围。
- 不新增第二套 Bundle、结果表、通用规则基类或大于 2000 行的新文件。

## 三、分阶段执行

### Task 0：固化运行基线和验收账本

**Files:**

- Read/verify: `backend/scripts/audit_remote_cdm_schema.py`
- Read/verify: `backend/scripts/audit_single_visit_qc_execution_plan.py`
- Read/verify: `backend/scripts/audit_sample_source_coverage.py`
- Read/verify: `backend/scripts/build_luxian_0609_runtime_manifest.py`
- Test: `backend/tests/contract/test_luxian_0609_acceptance_matrix.py`
- Record: `docs/audits/` 下新增当日脱敏审计记录（不写患者姓名、正文和密钥）

**Steps:**

1. 记录后端 `/api/v1/health` 的 git SHA、前端进程模式、Alembic head 和数据库连接状态。
2. 读取当前规则目录、客户运行范围、冻结规则和排除规则，生成一张唯一范围表。
3. 对一个病例记录源表行数、文书 ID、权威时间、正文长度/哈希、本地 CDM、Bundle、Canonical/API 结果数量。
4. 生成脱敏的逐层摘要：记录键、文书 ID 集合和内容哈希、同步游标/时间、Bundle snapshot digest、Canonical envelope digest、API payload digest；证据引用必须能在对应 Bundle snapshot 中解析到唯一文书和字段。
5. 若远端 PostgreSQL 不可达，账本标记 `BLOCKED_SOURCE_CONNECTIVITY`，不得用本地空表替代源库结论。
6. 运行合同测试；范围表、版本、冻结状态或任一层摘要不一致时停止后续实现。

**验收：** 能明确回答“这次任务运行了哪个版本、哪些规则、哪些资料、哪个结果”，且旧任务不会混入新验收。

### Task 1：时限和事件成熟门闭环

**Files:**

- Modify only when a failing case proves the defect: `backend/app/services/luxian_0609/basic_timeliness_facts.py`
- Modify only when a failing case proves the defect: `backend/app/services/luxian_0609/course_quality/rule_007.py`
- Modify only when a failing case proves the defect: `backend/app/services/luxian_0609/course_quality/rules_008_009.py`
- Modify only when a failing case proves the defect: `backend/app/services/luxian_0609/extended_document/death_discussion.py`
- Modify only when a failing case proves the defect: `backend/app/services/luxian_0609/extended_document/discharge_documentation.py`
- Modify only when a failing case proves the defect: `backend/app/services/luxian_0609/extended_document/transfer_documentation.py`
- Test: `backend/tests/unit/test_luxian_0609_native_basic_timeliness.py`
- Test: `backend/tests/unit/test_luxian_0609_basic_timeliness_fact_contract.py`

**Steps:**

1. 为每个已复现的提前报错、过期仍 `data_gap`、负时长和跨历史事件误配写一个失败测试。
2. 实现最小评价时点/成熟门和时间冲突事实；不增加关键词分支。
3. 验证入院至首条、相邻记录、末条至评价时点三类区间均被覆盖。
4. 验证死亡、出院、转科、医师变更只读取本次就诊事件。
5. 运行聚焦测试并用一个已保存病例重新质控，比较修复前后状态、原因码和证据。
6. 单独提交本规则族；未通过真实病例复核时标记“代码完成、业务未验收”。

**验收：** 确定性时间规则在合成边界例上 100% 通过；任何时间冲突都显示两个时间、差值和“待核对”，不直接判合规/不合规。

### Task 2：检查检验、诊断和语义规则的确定性边界

**Files:**

- Modify: `backend/app/services/luxian_0609/course_quality/rule_018.py`
- Modify only for proven cases: `backend/app/services/luxian_0609/native_exam_lab_execution.py`
- Modify only for proven cases: `backend/app/services/luxian_0609/native_extended_document_execution.py`
- Modify only for proven cases: `backend/app/services/luxian_0609/native_treatment_order_consistency.py`
- Test: `backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_treatment_order_consistency.py`

**Steps:**

1. 为 `018` 明确诊断来源、诊断类型和排序字段；没有院方确认前不把 `diagnosis_id` 猜作顺序。
2. 为 `010/020/023/026` 写非法模型枚举、字段串位、多事件混配的失败测试。
3. 对模型解析失败最多重试一次；仍失败必须保留 `technical_error/model_invalid_output`。
4. 对 `052/053/055/058` 验证逐事件、逐药物和评价窗口，不允许单个关键词覆盖多条事件。
5. 对 `044` 明确输血申请单的指标/申请理由是否足以构成输血前评估；在院方口径未变前按现有受控事实执行，不用自由文本关键词扩大结论。
6. 对每个修复运行聚焦测试和最小真实病例回放，记录 LLM 调用次数、Token 和耗时。

**验收：** 模型失败不再伪装成资料不足；单次重试有上限；任何语义结论都有受控事实和来源引用。

### Task 3：手术、输血、会诊和交接的逐事件关联

**Files:**

- Modify only for proven association defects: `backend/app/services/luxian_0609/native_surgery_gate_execution.py`
- Modify only for proven association defects: `backend/app/services/luxian_0609/native_consultation_execution.py`
- Modify only for proven association defects: `backend/app/services/luxian_0609/native_extended_document_execution.py`
- Modify only for proven association defects: `backend/app/services/luxian_0609/native_treatment_order_consistency.py`
- Test: `backend/tests/unit/test_luxian_0609_native_surgery_gate_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_consultation_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_transfusion_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_physician_handoff.py`

**Steps:**

1. 先从源库/本地库确认可用业务键；没有业务键时只能返回关联不确定。
2. 对多台手术、多次输血、多次会诊、多次交接分别建立正例、负例和同名不同事件边界例。
3. `029/031` 必须逐台绑定术前小结、手术记录和签名；任意一份存在不能覆盖其他台次。
4. `044/054/055` 必须逐医嘱绑定指标/理由、权威开始时间和评价窗口；不能用一张申请单覆盖其他输血或用药事件。
5. `069/071/072/073` 必须逐次绑定申请、完成、变更或转科事件；历史记录不能跨事件匹配。
6. 运行聚焦测试，随后对客户授权病例做源库—本地库—Bundle—结果四层对账；同步未完成或 Bundle 未刷新时不得进入规则准确率结论。

**验收：** 不出现跨台、跨次、跨住院期配对；每个待核实结果明确列出缺失的业务键/时间/来源，而不是笼统写“完整文书缺失”。

### Task 4：Canonical、API 和前端证据交付一致性

**Files:**

- Modify only if an API/Envelope mismatch is reproduced: `backend/app/services/custom_qc_workspace_service.py`
- Modify only if an API/Envelope mismatch is reproduced: `backend/app/services/luxian_0609_result_aggregator.py`
- Modify only if an API/Envelope mismatch is reproduced: `backend/app/routers/qc_sichuan.py`
- Test: `backend/tests/unit/test_luxian_0609_canonical_result_delivery.py`
- Test: `backend/tests/unit/test_luxian_0609_record_result_read_model.py`
- Test: `backend/tests/unit/test_luxian_0609_result_persistence_contract.py`
- Frontend read/verify: `src/domain/customer-qc/result-normalizer.ts` and结果查看组件

**Steps:**

1. 写测试保证一个 Envelope 的状态计数、规则 ID、结果数在 API、导出和页面模型中一致。
2. 写测试保证历史任务不会被新规则目录重新解释，也不会把旧 `035` 混入新任务。
3. 写测试保证每条证据的 `source_ref/document_id/field_path` 能映射到文书列表和定位入口。
4. 对冻结规则的 `not_executed` 显示策略做明确选择：要么纳入计数，要么从执行范围和结果范围同时排除，不能出现 69/68/70 无解释差异。
5. 浏览器验证确定问题、待确认、资料待核实、不适用、技术错误五种状态，以及单病历和批量导出。
6. 验证取消/重跑、旧任务查询和新任务查询的隔离；409 或历史失败任务只能按历史状态展示，不能污染当前任务计数。

**验收：** 页面不再展示“有结果但无文书”或无法定位的证据；所有计数与 Envelope 可逐项对账。

### Task 5：真实病例金标与发布门禁

**Files:**

- Use: `backend/scripts/audit_remote_cdm_schema.py`
- Use: `backend/scripts/audit_single_visit_qc_execution_plan.py`
- Use: `backend/scripts/build_luxian_0609_golden_ledger.py`
- Use: `backend/scripts/build_luxian_0609_real_golden_set.py`
- Test: `backend/tests/unit/test_luxian_0609_golden_gate.py`
- Test: `backend/tests/unit/test_luxian_0609_preproduction_benchmark20.py`
- Record: `docs/audits/` 脱敏金标和性能报告

**Steps:**

1. 先选 10 例做快速回归，覆盖在院/出院、手术/输血、死亡/非死亡、多次事件和资料缺失。
2. 快速回归无阻断后扩展到至少 20–30 例；每例记录适用性、状态、原因、关键事实、证据位置和建议。病例总数不能替代逐规则覆盖。
3. 确定性规则至少要有正例、负例或边界例各 1 个；语义规则至少要有 3 个正例、3 个负例和 1 个边界例。样本不足的规则只能标记 `real_data_blocked`，不参加总体通过率。
4. 对确定性规则要求金标 100% 一致；语义规则每个差异必须人工复核并关闭高风险误判。将 `data_gap`、`not_applicable`、`evaluation_unknown` 单独报告并计入覆盖率分母。
5. 生成独立性能产物，记录固定硬件/并发/选择器下的 wall-clock、每病例/规则延迟 P50/P95、逻辑调用数、HTTP 尝试数、重试数和 Token；相对基线回退超过 20% 或超过绝对上限时标记 `performance_blocked`。
6. 运行前后端必要检查：`npm run check:encoding`、`npm run lint`、`npm run type-check`、`npm run test:unit`，以及后端 LX0609 全量测试。
7. 只有所有放行条件通过后才编译打包；发布包记录 git SHA、Alembic head、规则范围、冻结规则和对账报告。

**最终放行条件：**

- 没有未解释的 `technical_error`、状态冲突或孤立证据引用。
- 每个正式运行规则都有测试、至少一个可追溯金标和明确来源合同。
- 客户缺失资料或未确认口径的规则仍保持受控冻结状态，不被包装成“已完成”。
- 源库不可达时发布门禁自动阻断，不允许仅凭本地空表宣称同步完整。

## 四、长期任务执行协议

每个子任务严格按以下顺序执行：

1. 主协调者先给出真实病例/调用链证据和文件白名单。
2. 实现者先写失败测试，再做最小实现；不得顺手改相邻规则。
3. 测试者独立检查状态、原因码、证据、调用次数、耗时和页面表现。
4. 主协调者亲自审查 diff 和真实结果，确认后单独提交中文 commit。
5. 每个闭环完成后暂停；下一规则必须有新的授权或继续指令。

### 阻断与恢复

- 源库连接失败：继续做代码/合成测试，但将真实验收标为阻断，不修改数据、不猜字段。
- 业务口径未确认：保持 `data_gap`/`not_executed`，列出需要院方确认的最小问题。
- 测试通过但真实病例不一致：以真实病例为准，回到对应规则闭环，不做公共引擎重构。
- 任何新方案需要新增通用层、巨型文件或第二套结果所有者时，立即暂停并重新评审。

## 五、第一轮实际顺序

1. 先完成 Task 0 基线账本。
2. 复核已修的 `001/051/074`，再按已知反例处理 `010/020/023/061/064`，同时记录修复前后状态、原因码和证据差异。
3. 处理 `055/058` 和 `044` 的确定性边界；模型非法输出最多一次受控重试，失败必须可见。
4. 处理 `018/029/031/054/069/071–073` 的字段/事件关联；源库不可达的部分只完成合同和本地回放。
5. 最后处理同步健康、Bundle 刷新、API 计数与证据定位，再进入 20–30 例金标和发布门禁。
