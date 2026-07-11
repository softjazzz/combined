# LX0609 客户专项混合执行包纵向切片计划

## 1. 计划状态与边界

- 基线：`fead03b8a2772e4ffafcd1515a28e60caa445cf3`，该 checkpoint 仅保存开发现场，不代表业务验收。
- 架构依据：`docs/architecture/ADR-LX0609-001-customer-hybrid-execution-package.md`，当前状态为 Proposed。
- 本文只定义后续任务门禁，不授权在本任务中修改生产代码、测试代码或实验脚本。
- 本阶段不跑新 A/B、不调整 prompt、不修改生产代码；只提交本计划和 ADR。
- 每个阶段必须由独立 `TASK_ASSIGN` 明确文件白名单。下列白名单是建议上限，不得跨阶段自动继承。

## 2. 现有 Golden 资产审计

### 2.1 资产事实

| 资产                                          | 当前事实                                                                | 可否作为 gold      |
| --------------------------------------------- | ----------------------------------------------------------------------- | ------------------ |
| `泸县0609真实样本GoldenSet标注表.csv`         | 28 行；`human_status=pending` 28 行；25 行待系统运行，3 行为 sample gap | 否                 |
| `泸县0609真实样本GoldenSet系统人工对比表.csv` | 28 行；人工、匹配和证据状态全部 pending                                 | 否                 |
| `luxian_0609_golden_review_queue.csv`         | 81 行，全部 pending                                                     | 否                 |
| `luxian_0609_golden_review_queue_merged.csv`  | 178 行，全部 pending                                                    | 否                 |
| 复核队列质量报告                              | accepted 规则数为 0                                                     | 否                 |
| 真实样本候选报告                              | 28 个候选框架；检查检验、输血、肿瘤病理/化疗仍有真实样本缺口            | 仅候选             |
| 合成样本                                      | 可用于机制回归                                                          | 不可用于真实准确率 |
| `full_text` 结果                              | 可作 shadow baseline 和差异参照                                         | 不得当作人工 gold  |

### 2.2 状态定义

- **candidate**：由样本池、规则映射或历史问题发现的候选，尚未完成业务结论。
- **pending**：等待系统运行、人工标注、证据确认或复核决定；不得进入准确率分母。
- **accepted**：业务质控人员明确确认 case type、期望状态、证据要求和备注后，才是 Golden。
- **rejected**：不适合作为该规则 Golden，必须保留拒绝原因，不得混入 accepted。

### 2.3 Golden 进入门槛

每条规则至少准备并接受以下种子类型，缺一类时不得宣称该规则完成验收：

1. 确定不合规；
2. 确定合规；
3. 不适用；
4. 数据缺口或边界样本；
5. 对存在父子关系的规则，至少一组父缺失、父存在子缺陷和父状态异常样本。

Golden 文件可包含受控内部记录引用，但评审摘要、trace 和提交文档不得复制患者姓名、完整病历或身份信息。

## 3. 跨阶段兼容契约

所有阶段都必须保留：

- `selected_rule_ids` 是调用方选择的客户 `LX0609-*` ID，非空时结果不得补回未选择质控点。
- `scoped_customer_rule_ids` 是任务持久化和客户展示范围，父子任务必须保持同一客户语义。
- `record_rule_map` 是病历到允许执行的底层规则 ID 映射，planner 不得将其扩大成全量规则。
- `customer_rule_count` 与 `execution_rule_count` 分开统计；gate-only 客户点仍必须保留客户结果语义。
- scope 兼容检查覆盖：单病历、多病历、只选 gate-only 点、family 父子任务、重跑历史任务和结果抽屉。

任何阶段发现未选规则被执行或展示、record scope 被扩大、计数混淆，立即回滚该阶段。

## 4. 阶段 0：实验 telemetry 修复

### 入口条件

- ADR 通过架构评审但仍可保持 Proposed。
- 明确现有 A/B 仅为实验基线，不重新解释为准确率。
- 获得独立任务授权，可修改实验 runner；本任务不执行。

### 建议文件白名单

- `tmp-lx0609-ab-test/run_lx0609_fact_gate_ab.py`
- 对应 runner 的独立测试文件（新建时由该阶段 TASK_ASSIGN 指定精确路径）

禁止修改生产服务和 prompt。

### 工作内容

- 把 token 分为 gate、事实抽取、语义评价和 fallback，避免累计值被重复归属到每个规则。
- 记录实际 LLM 调用数、每调用 token/耗时、病历数、规则数、语义子族数和 unattributed token。
- 为每个结果记录 `context_mode`、版本集合、planner reason 和 fallback reason。
- 输出汇总时同时给出总量与按病历/子族分布，禁止用单规则累计值相加推导总 token。

### 测试矩阵

| 场景                 | 断言                                        |
| -------------------- | ------------------------------------------- |
| 无 LLM 的 fixture    | 调用数和 token 均为 0                       |
| 单次调用映射多个规则 | 总 token 只计一次，各规则仅引用 attribution |
| 调用失败             | 计入 technical error，不伪造 token          |
| fallback             | 原路径与 fallback 分段计量                  |
| 并发运行             | 总量等于唯一调用记录之和                    |

### 退出条件

- 固定 fixture 下 token 总量可重复，唯一调用记录求和与汇总一致。
- `unattributed_tokens` 为 0，或有明确可解释来源且不超过总 token 的 1%。
- 不包含患者姓名、完整正文、密钥或完整 prompt/response。

### 回滚条件

- token 仍出现按规则重复累计；调用记录无法与总量对账；telemetry 引入患者正文或密钥。

## 5. 阶段 1：Source Manifest + fact schema v2

### 入口条件

- 阶段 0 通过，telemetry 可作为后续性能证据。
- source query 的 `available/empty/unavailable/error` 由数据同步和查询负责人确认。
- 获得首批 accepted Golden 或明确只做 shadow、不得影响客户状态。

### 建议文件白名单

- `backend/app/services/luxian_0609/source_manifest.py`（新建）
- `backend/app/services/luxian_0609/fact_schema.py`（新建）
- `backend/app/services/luxian_0609/input_builder.py`
- `backend/app/services/luxian_0609_fact_extraction.py`
- `backend/tests/unit/test_luxian_0609_source_manifest.py`（新建）
- `backend/tests/unit/test_luxian_0609_fact_schema.py`（新建）
- `backend/tests/unit/test_luxian_0609_input_builder.py`
- `backend/tests/unit/test_luxian_0609_fact_extraction.py`

### 工作内容

- 将现有 input profile 升级为不改变主链路结果的 manifest/fact v2 shadow 产物。
- 建立来源状态、事实最小字段、脱敏短引用和版本化序列化；事实必须显式携带 `trigger_scope`、`current_visit_relevance`、`assertion/assertion_context`、`event_status`、`record_time/submit_time/update_time` 及各时间来源语义。
- 通用事实为主；规则专用 `extensions`/projection 必须版本化、引用 `derived_from_fact_ids` 且可重建，禁止承载最终状态或 AI 建议状态。
- 缓存键包含 snapshot、query、fact schema/extractor 版本，不使用患者姓名或完整正文。
- 旧 facts 只通过显式适配器进入 v2，不静默补默认状态。

### 测试矩阵

| 维度               | 场景                                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------------------- |
| source status      | available 有记录、empty 零记录、unavailable 缺表/未同步、error 查询异常                                 |
| schema             | 必填字段、非法置信度、稳定 fact_id、版本变化、短引用脱敏                                                |
| 本次住院关联性     | 同一关键词分别出现在本次住院、既往史、家族史和外部上下文；只有 current_visit + relevant 可直接触发 gate |
| assertion/negation | 肯定、否认史、既往史否认、家族史与 uncertain；否认命中不得转为肯定事实                                  |
| event status       | planned、ordered、performed、cancelled、unknown；计划和取消不得冒充已执行                               |
| 时间语义           | record_time、submit_time、update_time 不同、缺失、时区和精度；禁止静默互相代填                          |
| projection         | 通用事实派生规则 extension、版本变化、来源 fact 追溯、禁止写入最终/AI 建议状态                          |
| snapshot           | 同快照缓存命中、快照变化失效、规则包/事实/projection 版本变化失效                                       |
| 隐私               | 姓名、联系方式、完整正文、API key 不进入 trace/cache key                                                |
| 兼容               | shadow 开关关闭时现有结果字节级不受影响                                                                 |

### 退出条件

- 四种 source status 均有单测，`empty` 与 `unavailable` 不可互换。
- facts v2 可从固定输入稳定重建；本次住院/既往史/家族史、肯定/否认、计划/执行/取消和三类时间均能保持语义；版本变化会失效缓存。
- rule-specific projection 可追溯到通用 fact，且任何 facts/extension 中均不存在最终状态和 `ai_suggested_*`。
- shadow 不改变现有客户状态、scope 和调用数。

### 回滚条件

- manifest 无法区分缺表与零记录；facts 持久化泄露敏感信息；shadow 改变现有结果或扩大执行范围。

## 6. 阶段 2：首个程序化纵向切片 029/030/032

### 入口条件

- 阶段 1 通过。
- `029/030/032` 分别具备至少一组 accepted 不合规、合规、不适用和数据缺口/边界样本；没有 accepted 时只能运行 shadow。
- 手术医嘱、术前小结、手术记录、手术安全核查表的 source manifest 口径已确认。
- 明确当前 `032` 风险：不得把“手术安全核查表缺失”和“核查表存在但核查项/签名不规范”混为同一规则。

### 建议文件白名单

- `backend/app/services/luxian_0609/planner.py`（新建）
- `backend/app/services/luxian_0609/execution.py`
- `backend/app/services/luxian_0609_programmatic_rules.py`
- `backend/app/services/luxian_0609_result_aggregator.py`
- `backend/app/services/luxian_0609_result_schema.py`
- `backend/app/routers/qc_sichuan.py`（只允许 planner 前移接线）
- `backend/tests/unit/test_luxian_0609_planner.py`（新建）
- `backend/tests/unit/test_luxian_0609_mainline_services.py`
- `backend/tests/unit/test_qc_sichuan_batch_throughput.py`
- `backend/tests/unit/test_qc_sample_pools_router.py`

### 决策表

| 规则             | Applicability                                     | Evaluation                                                       | 父子关系                                        |
| ---------------- | ------------------------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------- |
| 029 无术前小结   | 已确认本次手术/手术医嘱                           | 查询术前小结；empty 才可判缺失，unavailable 为 data gap          | 独立父级存在性规则                              |
| 030 无手术记录   | 已确认本次手术/手术医嘱                           | 查询手术记录；empty 才可判缺失，unavailable 为 data gap          | 031/032/033 的父前提之一                        |
| 032 无安全核查表 | 已确认本次手术；不得仅依赖 030 的手术记录是否存在 | 查询安全核查来源；empty 才可判缺失；表存在但填写不规范不属于 032 | 受 030 的适用性信息影响，但来源独立时可继续评价 |

### 测试矩阵

| 场景                         | 029                | 030             | 032                                                      |
| ---------------------------- | ------------------ | --------------- | -------------------------------------------------------- |
| 无本次手术事实且来源可靠     | not applicable     | not applicable  | not applicable                                           |
| 有手术医嘱，目标来源 empty   | non-compliant      | non-compliant   | 依独立核查来源判定                                       |
| 必要来源 unavailable         | data gap           | data gap        | data gap                                                 |
| source query error           | technical error    | technical error | technical error                                          |
| 目标文书存在                 | compliant          | compliant       | compliant，不检查签名规范                                |
| 只选择单个规则               | 只执行/展示所选点  | 同左            | 同左                                                     |
| record_rule_map 限定不同病历 | 不扩大病历规则范围 | 同左            | 同左                                                     |
| 父 030 缺失                  | 不受影响           | non-compliant   | 有独立手术事实和核查来源时继续，否则 suppressed/data gap |

另需断言：三条程序化切片底层 LLM 调用数为 0；planner 在 bundle 构建前完成；被抑制子规则不计入合规分母；029/030/032 的 completely-evidenced/programmatic 结果只能是 `compliant/non_compliant`，不能降级为 `ai_suggested_*`；`data_gap/technical_error` 不得经 aggregator 转换为 AI 建议。

### 退出条件

- accepted Golden 全部通过，pending 样本不进入准确率统计。
- scope 三字段、customer/execution count 和 family 父子任务契约无回归。
- 程序化切片 LLM 调用数/token 为 0，trace 能解释每个状态和抑制原因。
- 阶段 2 的确定性状态与 AI 建议状态边界测试全部通过，source unavailable/error 对 AI 建议具有硬阻断优先级。
- shadow 差异逐条完成归因，未出现 source unavailable 被判不合规。

### 回滚条件

- planner 位于底层 LLM 之后；未选规则被执行/展示；032 继续把填写不规范当作无表；父子抑制隐藏了来源独立且应展示的问题；出现隐私泄露。

## 7. 后续程序化切片

每组都复用阶段 2 的入口、scope、隐私和回滚门禁，并由独立任务给出精确白名单。

### 7.1 切片 A：033/034/038

- 033：手术知情同意书存在性。
- 034：麻醉知情同意书存在性，作为 035 的父规则。
- 038：麻醉记录单存在性，局麻除外。
- 当前 `038` 口径错位风险：不得把“出室评分未填写”等麻醉记录内容质量问题替代为“无麻醉记录单”；必须先判定是否非局麻，再查询麻醉记录单来源。
- 退出条件：034 缺失时 035 被抑制；038 的局麻适用性、记录单存在性和内容完整性三者分离。

### 7.2 切片 B：003/035/036/028

- 003：手术记录时限，依赖可靠的手术结束时间与记录时间。
- 035：麻醉知情同意书填写规范，仅在 034 确认文书存在时运行。
- 036：麻醉术前/术后访视存在性，局麻除外，作为 037 的父规则。
- 028：切口类别、预防性抗菌药物和停药时间的跨表程序计算。
- 退出条件：034->035、036->037 抑制正确；时间计算不交给 LLM；缺表与零记录分离。

### 7.3 切片 C：026

- 对齐恶性肿瘤化疗病程事实与医嘱的药物、剂量、方法和时间。
- 入口要求：肿瘤病理/化疗真实候选缺口已补齐，且存在 accepted 正、负、边界样本。
- 退出条件：结构化医嘱先行，语义只做实体/事件对齐；未获得肿瘤/化疗适用事实时不进入评价。

## 8. 语义子族 B2

语义子族 B2 必须在上述程序化切片完成后启动，不能与首切片并行生产化。

### 入口条件

- 程序化规则已移除存在性、时间窗和硬字段比较。
- 阶段 0 telemetry 能证明唯一调用数和 token。
- 每个目标语义子族已有 accepted Golden，且 prompt 调整另行授权。

### 建议执行方式

- planner 只把剩余高语义规则按“每病历 × 语义子族”分组。
- LLM 只返回语义 facts、证据引用、置信度和矛盾；aggregator 决定最终状态。
- aggregator 使用版本化 `confidence_policy_version`：来源充分且适用性确定时，达到建议阈值但未达到确定性阈值才生成 `ai_suggested_compliant/ai_suggested_non_compliant`；低于建议阈值或证据冲突进入 `evaluation_unknown` 和内部复核/fallback。
- `data_gap/technical_error`、关键来源 unavailable/error 和 applicability 未确定均硬阻断 AI 建议；AI 建议不计入确定缺陷，客户展示分别为“AI判断未发现问题”和“AI判断存在问题”。
- 先 shadow，后小流量灰度；`full_text` 只作 shadow 或明确灰区 fallback。

### 测试矩阵与退出条件

- 同病历同子族多个规则只产生一次 LLM 调用。
- gate 排除、程序化完成和 source unavailable 的规则调用数为 0。
- 覆盖低于建议阈值、建议阈值边界、确定性阈值边界、证据冲突、data gap、technical error；断言状态和客户展示映射均符合 ADR。
- 阈值只使用 accepted Golden 校准并保留独立验证集；阈值、证据要求、校准集版本和验证指标写入 `confidence_policy_version`。pending/full_text 不得参与阈值标注。
- 发布前每个语义子族的 accepted Golden 必须同时覆盖建议合规、建议不合规、低置信和冲突样本；样本不足只允许 shadow。不得以减少 `evaluation_unknown` 或提高覆盖率作为降阈值理由。
- 总 token 相对 full_text 至少下降 40%，wall time 至少下降 50%，不得高于 full_text token。
- accepted Golden 无新增确定性误报；AI 建议的方向性指标达到经架构评审批准的门槛，差异均有 fact、source、planner、阈值版本和 aggregator 归因。

### 回滚条件

- token 反增、状态差异无法归因、LLM 直接拥有最终/AI 建议状态、为减少复核而降低阈值、data gap/technical error 被转成 AI 建议、Golden 校准指标跌破门槛、完整病历进入 trace、technical error 超过 1%。

## 9. 发布与回滚总门禁

每阶段依次执行：

1. 单元测试与固定 fixture；
2. scoped API/任务契约测试；
3. accepted Golden shadow；
4. 性能与 token 对账；
5. 隐私扫描；
6. kill switch 演练；
7. 架构与业务双评审。

任何阶段都不得用以下方式“通过”：

- 把 `full_text` 输出标成 gold；
- 将 pending 候选计入准确率；
- 把 `unavailable` 当 `empty`；
- 把 `technical_error` 当 `data_gap`、合规或不合规；
- 通过扩大 `selected_rule_ids`、`record_rule_map` 或 `scoped_customer_rule_ids` 获得表面覆盖；
- 只观察最终状态而不核对实际 LLM 调用数和 token。

## 10. 当前文档任务验收

- 只允许变更：
  - `docs/architecture/ADR-LX0609-001-customer-hybrid-execution-package.md`
  - `docs/plans/2026-07-11-lx0609-hybrid-package-slice-plan.md`
- 不运行新 A/B、不调整 prompt、不修改生产/测试/实验代码。
- 对两个文件执行 `git diff --check`、UTF-8 无 BOM/LF 检查和隐私/密钥扫描。
- 精确 stage 两个文件，确认既有 `AGENTS.md` 未 stage，再以指定中文 message 提交；不 push。
