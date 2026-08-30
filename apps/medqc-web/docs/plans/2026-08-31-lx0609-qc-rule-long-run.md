# LX0609 质控点修复与真实验证长期任务实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不重写质控引擎、不伪造缺失资料的前提下，逐条修复并验证 LX0609 客户质控点，使每个可交付结论都能从源库、本地 CDM、Bundle、Canonical 结果一直追溯到前端证据定位。

**Architecture:** 规则执行器是唯一判定所有者；沿用现有 EvidenceReadSession→Snapshot/MaterialStore→Native→Decision→Canonical 链，证据快照只负责提供冻结资料；Renderer 只生成客户文案；Aggregator/Finalizer 只做状态合同校验和装配。每个规则或低耦合规则族单独形成“真实问题 → 最小修复 → 聚焦测试 → 真实病例复核 → 提交”的闭环。资料或业务口径不足时保持 `data_gap`/`not_executed`，不以关键词、历史任务或备用字段猜测结论。

**Tech Stack:** Python 3.10、FastAPI、SQLAlchemy、PostgreSQL、Pytest、Vue 3、TypeScript、Vitest。

## 当前检查点（2026-08-31）

- 本次链路边界回归发现并修复 `qc_sichuan` 对已拆分批量 Worker 统计函数的兼容导出遗漏（提交 `ba816bd78`）。修复只恢复路由层导入，不增加判定或投影逻辑；主线服务 160 项通过，`pr-no-model` 质量门禁 2297 项通过、0 失败。另有 7 个指定链路文件 560 项通过，规则分流、状态归约和 Canonical 交付未发现重复执行。已有脱敏20例候选可用于 shadow 复测，但 `025` 跨运行状态不稳定、`020–023` 会诊 trace 未开启、`preproduction_api/runtime_shadow` 仍关闭，仍记为 `real_data_blocked`，不得宣称真实业务接受。
- 预生产门禁补充核查：对固定20例的 43 条纯程序规则使用 `llm_client=None`（明确零模型语义）时，20×43=860 条结果、0 technical error、0 LLM 调用、0 token，门禁通过。此前把无 `generate` 方法的 `object()` 当作客户端，恰好在 `LX0609-006` 的可选语义分支触发一次失败调用，形成 `llm_call_count=1/total_tokens=0`；这是诊断脚本客户端契约误用，不是生产链路新增第二判定链，不能通过放宽 token 合同掩盖。真实 LLM 失败仍保持发布阻断，需用有 usage 的客户端重新验收。
- 当前 HEAD 的完整 LX0609 单元回归重新执行：`4109 passed / 0 failed`，用时 52.30 秒；测试中主动注入的连接、模型解析和证据失败日志均被对应失败语义断言覆盖。该结果证明代码回归稳定，但不替代远端源库和真实金标验收。
- 代码回归：`backend/tests/unit` 下全部 `test_luxian_0609*.py` 共 4089 项通过，耗时 44.56 秒；测试中的连接失败/模型解析失败日志均已按既有失败语义断言，不代表本次回归失败。结果投影、复核、导出和统计聚焦回归另有 64 项通过（0.89 秒）。
- 已提交的最小修复：`c0cd52959`（023 非合规会诊证据保留末次异常文书）、`5c15cbee5`（061 多条出院记录取最新权威完成时间）。两项均已通过聚焦测试和全量 LX0609 回归。
- 已提交最小交付边界修复：`18a795b25`（客户结果投影/复核/HTML、CSV、XLSX 导出和工作台统计统一校验 75 条已知目录，过滤客户排除项，未知/缺失规则身份 fail-closed）。公开规则集随后由 `e30ac0e99` 明确投影四种范围：目录 75、客户交付 70、可执行 64、暂缓 6，同时保留旧 `rule_ids/rule_count=75` 兼容语义。本轮复核未发现可安全修改的确定性规则缺陷：`010/018/029/031/051/054/055/058/064/069/071/072/073/074`；这些规则仍需源库可达和真实金标才能从 `local_verified` 升为 `accepted`，不能以单测通过代替业务验收。
- 本轮新增提交 `ecef4ab02`：`010` 拒绝跨医嘱复用同一 `exam_id`，并在多事件共享病程时要求完整部位身份锚点；`018` 支持客户真实诊断名称内编号、严格复合诊断类型，且不让无序重复投影阻断已有有效候选。聚焦回归：检查检验执行/解析与课程质量共 352 项通过；仍需真实源库核对 `exam_id` 唯一性和诊断字段金标，状态暂记 `local_verified`/`real_data_blocked`，未宣称接受。
- 随后提交 `8483ab971`：`074` 单次诊断变更必须在带理由/依据的后续病程中明确引用本次变更后的诊断名称；不相关诊断的理由/依据不再被串作合规。074 专项 10 项、执行器整文件 218 项通过；真实源字段与多变更金标仍待客户验收。
- 本检查点新增提交 `faa054049`：`020/023` 为每条会诊建议保留意见文书与执行文书的逐条安全引用，并贯穿 Canonical、批任务快照、单病历/批量结果定位；`069` 对同一行同时出现且互相冲突的 `consultation_id/application_id` fail-closed 为 `data_gap/association_failed`；快照仅对 `recommendation_evidence` 放宽到 96 条，其余列表上限不变。后端聚焦回归 526 项通过，前端新增/相关回归 56 项通过，类型检查通过；代码状态为 `code_fixed`/`local_verified`，真实源库关联仍为 `real_data_blocked`，不能据此宣称 020/023/069 已业务接受。长期任务停止/证据保全门禁随后由 `8ab728cc2` 固化。
- 本检查点新增提交 `bfb853157`：`061` 对多条不同登记出院时间不再按返回顺序取第一条，而是稳定关闭为 `data_gap/authoritative_time_conflict`；冲突时间经白名单、排序去重后贯穿聚合器、Canonical 客户事实和文案，页面明确列出时间并要求核对住院登记。061/067/068 原生回归、结果聚合器、客户渲染器和 Canonical 相关回归共 973 项通过；`064` 当前没有脱离真实来源前提的确定性红测，保持 `real_data_blocked`。
- 本检查点新增提交 `ea0b81646`：`058` 仅在规则专用调用点把带时区的用药开始时间和专家支持文书时间归一到 `Asia/Shanghai` 后比较；无时区旧数据行为保持不变。新增“晚于用药”和“同一瞬时点”两条边界红测，058 专项 18 项、相关扩展回归 669 项通过。没有修改广泛复用的共享时间解析器，也没有新增结果层。
- 复杂度审计结论：从 `979d1a19c` 到当前版本，应用生产代码约新增 10,995 行、删除 2,395 行；`native_extended_document_execution.py`、`customer_renderer.py`、`native_consultation_episode_execution.py`、`luxian_0609_result_aggregator.py` 当前约 2,688/3,042/3,329/6,040 行，已越过预警线。CodeGraph 未发现第二个状态归约器或前端重新判定链，但继续在这些文件堆叠修复会增加回归风险。因此后续默认每个闭环新增不超过 150 行生产代码；超过 200 行、跨两个以上职责层或需要新 Resolver/Store/Registry 时必须先停下来单独评审，并且没有独立红测不得改公共层。`86913e33d` 已将 runtime manifest/audit 固化为 `75/70/64/6` 并校验 exact ID partition；合成病例入口和真实源库/API/UI 对账仍是独立发布门禁，不与规则逻辑修复混合。
- 本轮边界审查主动拒绝了两项会扩大隐性复杂度的实现：不把尚无专用模板的 `050–075` 规则强行塞进既有“查房病程/手术/输血”合成病例族，也不把批量结果中的普通 `field_path/evidence_excerpt` 自动提升为前端章节定位/原文展示权限。前者需要后端权威 `family/template` 合同，后者需要 Canonical/API 明确的授权摘录合同；在合同缺失前均保持 `real_data_blocked`，不以硬编码补齐表面覆盖率。文书级 `source_ref` 精确匹配链已通过 440 项后端和 11 项前端聚焦测试；字段级定位仍是发布门禁。
- `064` 独立复核未形成可代表生产来源的红测：批准来源字段只提供正式手术时间和 `record_content`，不提供计划/未完成状态或兼容 `content` 字段。064 专项 20 项、064–066 组合 33 项、扩展文书执行器全文件 221 项通过；因此本轮不改执行器，继续标记 `real_data_blocked`，等待真实来源反例而不是猜字段。
- 前端质量门禁：编码、lint、类型检查通过；完整前端单测仍有 7 个既有失败（文书展示旧断言、客户样本验证旧规则数断言、反馈 Hook 时序、冻结规则展示），已隔离为独立任务，未与本轮后端结果边界混合。
- 当前真实验收仍受远端源库连接阻断（`real_data_blocked`）。公开入口范围快照已由 `e30ac0e99` 的 40 项规则集测试覆盖；下一检查点是冻结规则投影和历史 Canonical 隔离，再进入有红测的规则闭环；若无红测，不修改公共引擎。

---

## 一、当前基线（开始任务前先复核）

1. 当前必须同时保留三种计数，不能混用：规则总目录/历史兼容基线 75 条；客户交付目录 70 条（排除客户明确没有资料的 `033/034/035/041/042`）；本轮实际可执行 64 条（70 条再扣除 `025/028/049/056/059/075` 六条冻结规则）。`phase_scope` 仍是 75 条、其中 69 条 `phase_1_target`；它是实现/依赖基线，不等于客户交付目录。五条同意书规则目前已在部分交付层过滤，但仍在 master、contract、inventory、runtime manifest 和部分合成/显式入口中注册，因此必须标为“范围合同漂移”，直到所有入口和测试统一。准生产 Golden/Benchmark 当前仍可能直接按这 69 条 `phase_1_target` 运行；在统一为客户交付 70、可执行 64、冻结 6 前，任何 Golden 通过都只能算内部诊断，不能算客户发布验收。
   当前已验证的交付层为：样本验证/API 客户目录 70 条、默认任务执行 64 条并另列 6 条冻结；仍需处理准生产入口和合成病例构造器的显式选择绕过，以及前端静态规则族残留。不得把“正常页面暂时不显示”当作范围已经统一。
2. 历史任务结果不能作为修复后的验收依据。每次验收必须记录本次任务的代码 SHA、Alembic head、运行规则集合和 Canonical/API 版本；同一病历的新任务不得被旧任务或当前规则目录重新解释。
3. 本机本地库连接正常，但远端源库 PostgreSQL 握手被关闭，`remote_connected=false`、同步状态为 `never`。因此本地缺失资料只能证明“当前本地链路没有资料”，不能证明源库没有资料。
4. 已观察到的高风险问题集中在：评价时点、逐事件业务键关联、来源缺失与不适用混淆、技术错误伪装成数据不足、Canonical/API 结果数量不一致、证据定位失效，以及 Bundle 更新时间落后于最近同步。
5. 已有审计可复现的优先误判包括 `010/020/023/061/064`；它们先作为第一轮闭环对象，不因单元测试通过而视为已关闭。当前跨层审计工具已提交（`656db48f5`），只证明来源/Bundle/Canonical 的可追溯性，不等于规则执行器或 API/UI 已验收。

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

- `025/028/049/056/059/075` 在各自的真实资料、金标和客户签收前保持 `not_executed`/`pending_definition`；不得只冻结 `025/059/049` 而遗漏另外三条。
- 客户没有提供的同意书规则在范围合同完成同步前保持“范围漂移阻断”；不能只从页面隐藏，也不能在后端继续执行后宣称已移除。完成同步后，master/历史基线仍可保留 75 条，但客户交付快照必须明确记录 70/64/6 三种集合。
- 不新增第二套 Bundle、结果表、通用规则基类或大于 2000 行的新文件。

## 三、分阶段执行

### Task 0：固化运行基线和验收账本（每个版本只执行一次）

**Files:**

- Primary: `backend/scripts/audit_luxian_0609_case_rule_chain.py`
- Read/verify: `backend/scripts/build_luxian_0609_runtime_manifest.py`
- Auxiliary only when the customer source is reachable: `backend/scripts/audit_remote_cdm_schema.py`, `backend/scripts/audit_sample_source_coverage.py`
- Test: `backend/tests/contract/test_luxian_0609_acceptance_matrix.py`
- Record: `docs/audits/` 下新增当日脱敏审计记录（不写患者姓名、正文和密钥）

**Steps:**

1. 记录后端 `/api/v1/health` 的 git SHA、前端进程模式、Alembic head 和数据库连接状态；同时记录长驻进程是否已重启。`load_luxian_0609_phase_scope`、`get_luxian_0609_sample_validation_rule_set` 使用进程级缓存，规则范围/配置变更后必须清缓存或重启，并用健康接口和新任务确认实际加载的是新集合。
2. 读取当前 75 条目录、客户交付排除项、64 条可执行项和 6 条冻结项，生成一张同时列出 `catalog_count=75`、`customer_delivery_count=70`、`executable_count=64`、`withheld_count=6` 的唯一范围表；任何入口只返回其中一种未标注的“规则数”都阻断。
3. 对一个病例记录源表与 CDM 的文书 ID 集合、权威时间、正文长度/哈希，并核对 Bundle 中相同字段；只有这些 digest 均可比较时才允许进入 `ready`。
4. 生成脱敏的逐层摘要：记录键、文书 ID 集合和内容哈希、同步游标/时间、Bundle snapshot digest、Canonical envelope digest；API payload 和 UI 定位作为独立 smoke 工件，不得由行数或 Canonical digest 推断。证据引用必须能在对应 Bundle snapshot 中解析到唯一文书和字段。
5. 若远端 PostgreSQL 不可达，账本标记 `BLOCKED_SOURCE_CONNECTIVITY`，不得用本地空表替代源库结论。
6. 运行合同测试，并额外运行 Golden/Benchmark 的范围快照：默认客户验收必须明确得到 `customer_delivery_count=70`、`executable_count=64`、`withheld_count=6`，禁止以 69 条 phase target 代替。范围表、版本、冻结状态、文书 ID/内容 digest 或任一层摘要不一致时停止后续实现。`audit_single_visit_qc_execution_plan.py` 仅作诊断，不能作为严格阻断入口。

**验收：** 能明确回答“这次任务运行了哪个版本、哪些规则、哪些资料、哪个结果”，且旧任务不会混入新验收。

### 每轮最小闭环（避免长任务退化为反复跑全量）

除 Task 0 和 Task 5 外，每轮最多处理一个规则族或两个相互独立的缺陷，固定顺序为：

1. 保存基线 SHA、runtime manifest hash、Alembic head、job/root_job 和失败病例摘要。
2. 写一个能复现业务错误的红测，并先确认它确实失败。
3. 只在白名单文件中做最小修改；不顺手重构公共引擎或改变无关规则。
4. 跑聚焦测试（目标小于 2 分钟），再跑一个新任务的单病例 `case-rule-chain` 对账。
5. 必要时做一条 API/UI smoke（状态、reason、document_id、field_path 和定位入口），由主协调者审查 diff 和结果。
6. 单独提交中文 commit；台账只更新到 `code_fixed` 或 `local_verified`，真实资料不足则写 `real_data_blocked`。

同一规则没有通过本轮门禁，不得进入下一规则；已 `accepted` 的规则也必须在 runtime manifest 或数据链发生变化时重新验证。

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

- Modify only when a failing red test proves the defect: `backend/app/services/luxian_0609/course_quality/rule_018.py`
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
3. 确定性规则至少要有正例、负例和边界例各 1 个；语义规则发布门禁固定为每条规则至少 3 个正例、3 个负例和 1 个边界例，不能依赖 CLI 默认的 1/1。样本不足的规则只能标记 `real_data_blocked`，不参加总体通过率，但必须计入覆盖率报告。
4. 对确定性规则要求金标 100% 一致；语义规则每个差异必须人工复核并关闭高风险误判。`data_gap`、`not_applicable`、`evaluation_unknown` 和 `technical_error` 分别报告，并纳入“资料/状态覆盖”门禁；不能因只剩 definite 条目而自动通过。
5. 生成独立性能产物，记录固定硬件/并发/选择器下的 wall-clock、每病例/规则延迟 P50/P95、逻辑调用数、HTTP 尝试数、重试数和 Token；相对基线回退超过 20% 或超过绝对上限时标记 `performance_blocked`。
6. 运行前后端必要检查：`npm run check:encoding`、`npm run lint`、`npm run type-check`、`npm run test:unit`，以及后端 LX0609 全量测试。
7. 只有所有放行条件通过后才编译打包；发布包记录 git SHA、Alembic head、规则范围、冻结规则、源/CDM/Bundle digest、API/UI smoke 工件和对账报告。

**最终放行条件：**

- 没有未解释的 `technical_error`、状态冲突或孤立证据引用。
- 每个正式运行规则都有测试、至少一个可追溯金标和明确来源合同。
- 客户缺失资料或未确认口径的规则仍保持受控冻结状态，不被包装成“已完成”。
- 75 条总目录、70 条客户交付目录、64 条本轮可执行目录和 6 条冻结目录均有明确版本化快照；任务结果必须标注使用的是哪一集合，范围漂移或冻结规则泄漏即阻断。
- API 返回与 Canonical 逐字段一致，至少一条浏览器/UI smoke 能把每条确定问题证据定位到同一 `document_id/field_path`；缺少 API/UI 工件即 `release_blocked`。
- 源库不可达时发布门禁自动阻断，不允许仅凭本地空表宣称同步完整。

## 四、长期任务执行协议

每个子任务严格按以下顺序执行：

1. 主协调者先给出真实病例/调用链证据和文件白名单。
2. 实现者先写失败测试，再做最小实现；不得顺手改相邻规则。
3. 测试者独立检查状态、原因码、证据、调用次数、耗时和页面表现。
4. 主协调者亲自审查 diff 和真实结果，确认后单独提交中文 commit。
5. 在当前 Goal 已批准的范围内，闭环完成后自动按台账 checkpoint 继续下一个规则；只有遇到新增资料权限、院方业务口径、数据库写入、发布打包或其他超出当前授权的动作才暂停并请求确认。这样既不会重复跑已验收规则，也不会把“长程”退化成一次性全量改动。

### 阻断与恢复

- 源库连接失败：继续做代码/合成测试，但将真实验收标为阻断，不修改数据、不猜字段。
- 业务口径未确认：保持 `data_gap`/`not_executed`，列出需要院方确认的最小问题。
- 测试通过但真实病例不一致：以真实病例为准，回到对应规则闭环，不做公共引擎重构。
- 每次真实验收必须创建新任务/新样本池，不覆盖客户历史结果；失败时保留诊断工件，回退只能回到上一个已验证 commit 和 manifest，并先确认 `alembic current` 后重启服务。规则目录或范围配置改变后，恢复前必须重新启动长驻后端（或显式清除上述缓存），再核对实际任务的范围快照，不能把旧进程结果当作新版本结果。
- 任何新方案需要新增通用层、巨型文件或第二套结果所有者时，立即暂停并重新评审。

### 长程运行的停止与证据保全

为避免长期任务在资料阻断或重复运行时无限循环，每次 checkpoint 还必须遵守以下最小门禁：

1. 每次运行生成不可变的 `run_id`、代码 SHA、Alembic head、runtime manifest hash、job/root_job、输入快照和产物路径；审计 JSON/Markdown 不覆盖已有文件。三方对账同时记录查询版本、筛选条件、时区/排序规则、归一化规则和源行主键，便于重放“源库→CDM”差异。
2. 远端源库或 LLM 失败只允许按本轮约定次数重试；同一阻断连续三次仍未改变时暂停当前 Goal，标记 `real_data_blocked` 并列出需要用户/院方提供的最小动作，不自动跳过阻断继续宣称完成。
3. 源库—CDM 对账必须输出逐行 `missing/duplicate/normalized/time_precision` 差异；只有缺行、重复业务键或未解释时间差为零时才进入 `ready`。空白、编码和时区标准化差异要在报告中显式列出，不能只比较总数或整体哈希。
4. Golden/UI 放行矩阵固定到“规则 × 适用性 × 状态 × 单病历/批量/导出/定位”维度：确定性规则至少正例、负例、边界各 1 个；语义规则至少 3/3/1；缺少 `data_gap`、`not_applicable`、`evaluation_unknown`、`technical_error` 的必要覆盖或任一定位工件时，保持 `real_data_blocked`。客户金标需记录口径版本和复核人/仲裁结果。
5. 脱敏审计产物在归档前执行一次自动 PII 扫描；未通过时只保留本地受控工件，不进入发布包。

## 五、第一轮实际顺序

1. 先完成 Task 0 基线账本，并先解决 75/70/64/6 的客户合同范围漂移（包括五条同意书规则的显式入口和合成样本入口）。
2. 复核已修的 `001/051/074`，再按已知反例一次只处理一个 `010/020/023/061/064`；当前 064 的空正文病程和混合手术来源、061 的多行/空正文策略先标业务口径或来源阻断，不得擅自猜测。
3. 处理 `055/058` 和 `044` 的确定性边界；模型非法输出最多一次受控重试，失败必须可见。
4. 处理 `018/029/031/054/069/071–073` 的字段/事件关联；源库不可达的部分只完成合同和本地回放。
5. 最后处理同步健康、Bundle 刷新、API 计数与证据定位，再进入 20–30 例金标和发布门禁；没有 API/UI smoke 和内容 digest 时不得发布。
