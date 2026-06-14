# 泸县0609质控点正式上线 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将“泸县0609质控点验证 v1”从演示规则包升级为可在 `/workstation-v4/customer-sample-validation` 正式运行、可复核、可度量准确性的客户专项质控集。

**Architecture:** 以 49 条客户质控点为唯一范围，建立“规则定义 -> 数据依赖 -> 执行器 -> 证据链 -> golden cases -> 批量评估 -> 页面闭环”的上线链路。每条规则必须有明确适用条件、触发条件、排除条件、证据来源、输出字段和至少一组可复核样本；不能实现的规则必须以数据缺口标记，不允许伪装成已实现。

**Tech Stack:** Python/FastAPI 后端、Vue 3/TypeScript 前端、现有 Sichuan QC workspace batch job、阿里云百炼 `qwen3.5-35b-a3b` 作为 LLM 语义判断模型、JSON/CSV/Markdown 作为规则目录和验收工件。

---

## Definition of Done

本长程任务完成时，必须同时满足：

- `docs/0602/luxian_0609_formal_rule_catalog.json` 中 49 条规则均有稳定 `qc_point_id`、规则名称、客户原文、适用文书、数据依赖、执行策略、证据字段、上线状态。
- `/workstation-v4/customer-sample-validation` 可选择并运行 `luxian_0609_qc_v1`，并且结果能按泸县0609规则包展示。
- 每条规则至少有以下结论之一：
  - `formal_ready`：已有可执行规则、证据链、golden cases、准确性门禁通过。
  - `ready_with_data_gap`：规则逻辑已完成，但当前样本池缺少必要文书或结构化数据，页面和报告能明确说明无法判定原因。
  - `blocked_by_source`：客户质控点依赖当前系统完全没有的数据源，已在执行依赖矩阵和页面中明确标注。
- 所有可执行规则不得只返回“有没有字段”的浅层结果，必须输出能让客户复核的证据：文书类型、记录时间、命中文本摘要、比较对象、判断理由、建议动作。
- 批量评估脚本能输出规则级准确性报表，至少包含 TP/FP/TN/FN/Unknown、precision、recall、样本覆盖度、待人工复核数。
- 不把 `raw_response`、完整病历正文、prompt、embedding、internal_data 暴露给前端或验收文档。

---

## Next Long-Running Goal: P0 可上线验证闭环

**目标：** 先不追求 49 条一次性全部完美上线，优先把 `luxian_0609_qc_v1` 中 P0/可执行基础较好的规则做成“能正式对客户样本池跑、能复核、能计算准确性”的闭环。完成后，客户样本验证页面应能稳定选择“泸县0609质控点验证 v1”，并对已上线规则输出可信质控结论；其余规则必须明确显示为待补规则、数据缺口或需人工复核，不能混入已上线命中率。

**当前基线（2026-06-10）：**

- 规则目录：49 条，目录结构检查通过。
- 发布闸门：`release_ready=false`。
- 阻塞项：`implementation_ready`、`golden_cases_ready`、`review_completed`、`candidate_coverage`、`accuracy_evaluation`、`customer_sample_page_verified`。
- 候选样本：178 条待复核，全部仍为 `pending`。
- golden cases：尚未导入 accepted 样本，49 条规则均缺 positive / negative / boundary 的完整组合。
- 已修正准确性风险：`LX0609-001`、`LX0609-002`、`LX0609-016` 已从 formal-ready 降级为数据缺口；当前样本池缺入院时间或首次病程正文，不能正式计算阳性/阴性准确率。
- 当前真正 formal-ready 规则：`LX0609-017`、`LX0609-021`、`LX0609-032`；三条均已具备 positive / negative / boundary 三类候选，下一步是人工复核为 accepted 后导入 golden cases。
- 已新增 formal-ready 最小复核包：`docs/0602/luxian_0609_formal_ready_min_review_sheet.csv`，覆盖 3 条规则 x 3 类样本共 9 行，质量检查 `error_count=0`。这是导入第一批 golden cases 的最短路径。

**本阶段验收门槛：**

1. P0 规则清单明确：从工作包中筛出 10-15 条最适合上线验证的 P0 规则，输出 `qc_point_id`、规则口径、执行器类型、数据源、当前样本覆盖。
2. 每条 P0 规则至少具备：
   - 1 个 positive golden case；
   - 1 个 negative golden case；
   - 1 个 boundary / data_quality_gap golden case；
   - 规则证据字段能支撑人工复核。
3. P0 规则执行结果必须能区分：
   - `non_compliant`
   - `compliant`
   - `not_applicable`
   - `data_quality_gap`
   - `uncertain`
4. P0 规则评估报告必须输出 TP/FP/TN/FN/Unknown、precision、recall、unknown_rate、data_gap_rate。
5. P0 上线闸门：
   - precision >= 0.90；
   - recall >= 0.85；
   - 无未解释的 `unsupported`；
   - 数据不足样本不得计入问题命中数；
   - LLM 规则 JSON 解析失败必须降级为 `uncertain`，不能直接判阳性。
6. 客户样本验证页面必须能看到：
   - 当前规则集；
   - P0 已上线规则数；
   - 待补规则数；
   - 数据缺口规则数；
   - 每条命中结果的证据摘要、文书定位、复核入口。

**推荐执行顺序：**

1. 修复候选发现误判：优先处理 `LX0609-002`、`LX0609-016`、`LX0609-021`、`LX0609-032` 这类已有 formal_ready 基础但样本类型不完整的规则。
2. 生成首轮人工复核工作表：只推送证据强、低歧义的候选，不自动接受。
3. 人工复核并导入 golden cases：只有 `review_status=accepted` 的样本才能进入 golden cases。
4. 实现/加固 P0 执行器：结构化时限规则优先，其次跨文书复制/一致性规则，最后 LLM 语义规则。
5. 跑批量评估和发布闸门：每次规则或样本变化后刷新 `luxian_0609_qc_eval.json` 和 `luxian_0609_release_gate.json`。
6. 页面闭环验收：用实际 batch job 在 `/workstation-v4/customer-sample-validation` 验证规则集选择、任务创建、结果分组、证据展示和导出。

**退出条件：** `run_luxian_0609_release_gate.py --write` 可以对 P0 范围输出 `p0_release_ready=true` 或等价的通过状态；若全量 49 条仍未 ready，报告必须清晰区分“P0 已上线验证”和“全量待补”。

---

## Phase 0: Baseline Lock

### Task 0.1: 固化当前规则范围

**Files:**

- Read: `D:\LLM\LX888\apps\medqc-web\docs\0602\质控点及规则.xlsx`
- Read: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_formal_rule_catalog.json`
- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-正式上线规则清单.md`

**Steps:**

1. 用脚本读取 Excel，确认客户质控点数量为 49。
2. 对照 `luxian_0609_formal_rule_catalog.json`，确认 49 条均有唯一 `LX0609-xxx`。
3. 生成或更新正式上线规则清单，字段包括：客户序号、`qc_point_id`、客户原文、规则名称、规则类型、当前状态、缺口说明。
4. 运行：
   ```powershell
   python scripts\qc\check_luxian_0609_catalog.py
   ```
5. Expected: `catalog_count=49` 且 `errors=0`。

### Task 0.2: 建立上线状态枚举

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_formal_rule_catalog.json`
- Modify: `D:\LLM\LX888\apps\medqc-web\scripts\qc\check_luxian_0609_catalog.py`

**Steps:**

1. 明确定义允许状态：
   - `formal_ready`
   - `needs_rule_implementation`
   - `needs_cross_document`
   - `needs_data_linkage`
   - `needs_evidence_hardening`
   - `ready_with_data_gap`
   - `blocked_by_source`
2. 校验脚本禁止出现未知状态。
3. 运行目录校验。
4. Expected: 无未知状态，无缺失规则。

---

## Phase 1: Rule Semantics and Dependency Matrix

### Task 1.1: 每条规则补齐执行语义

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-执行依赖矩阵.md`
- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_formal_rule_catalog.json`

**For each rule, define:**

- `applicability`: 什么病历/文书/场景适用。
- `positive_condition`: 什么情况判定为问题。
- `negative_condition`: 什么情况判定为合格。
- `boundary_condition`: 缺少文书、时间不明、数据冲突时如何处理。
- `evidence_required`: 必须回传哪些证据字段。
- `source_required`: 需要哪些文书或结构化表。

**Acceptance:**

- 49 条规则均有以上字段。
- 跨文书规则必须明确比较双方，例如“入院记录完成时间 vs 入院时间”。
- 数据联查规则必须明确需要的表，例如医嘱、费用、检查报告、手术麻醉、输血。

### Task 1.2: 把规则分成四类执行器

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-执行依赖矩阵.md`

**Categories:**

- `structured_time_rule`: 结构化时间/文书存在性/时限规则。
- `cross_document_rule`: 跨文书一致性和缺漏规则。
- `llm_semantic_rule`: 需要 LLM 判断语义是否充分、是否矛盾、是否存在分析说明。
- `data_linkage_rule`: 需要医嘱、费用、检查、检验、手术、麻醉、输血等结构化联查。

**Acceptance:**

- 49 条规则都有且只有一个主执行器类型。
- 每条规则可附加 `secondary_checker`，例如先结构化过滤再 LLM 复核。

---

## Phase 2: Golden Cases and Candidate Review

### Task 2.1: 构建候选样本覆盖矩阵

**Files:**

- Create: `D:\LLM\LX888\apps\medqc-web\scripts\qc\build_luxian_0609_candidate_coverage.py`
- Create/Update: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_candidate_coverage.json`
- Create/Update: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_candidate_coverage.csv`
- Create/Update: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-候选样本覆盖矩阵.md`

**Steps:**

1. 读取 `luxian_0609_formal_rule_catalog.json`。
2. 读取 `luxian_0609_golden_review_queue_merged.csv`。
3. 读取 `泸县0609质控点-golden-cases.json`。
4. 按 `qc_point_id` 聚合 `positive/negative/boundary` 候选数、已接收数、已拒绝数、数据不足数。
5. 输出缺失 case type 和下一步动作。
6. 运行：
   ```powershell
   python -m py_compile scripts\qc\build_luxian_0609_candidate_coverage.py
   python scripts\qc\build_luxian_0609_candidate_coverage.py --write
   ```

**Acceptance:**

- 49 条规则均出现在覆盖矩阵中。
- 不包含完整病历正文。
- 对没有候选的规则能明确说明缺什么样本。

### Task 2.2: 人工复核候选样本并导入 golden cases

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_golden_review_queue_merged.csv`
- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-golden-cases.json`
- Read/Run: `D:\LLM\LX888\apps\medqc-web\scripts\qc\import_luxian_0609_reviewed_cases.py`

**Steps:**

1. 人工将候选行标记为 `accepted` 或 `rejected`。
2. 每条 accepted 样本必须有 `expected_hit`、`expected_severity`、`evidence_expectation`。
3. 先 dry-run：
   ```powershell
   python scripts\qc\import_luxian_0609_reviewed_cases.py --input docs\0602\luxian_0609_golden_review_queue_merged.csv --dry-run
   ```
4. 确认无误后写入 golden cases。
5. 运行：
   ```powershell
   python scripts\qc\check_luxian_0609_golden_cases.py
   ```

**Acceptance:**

- `formal_ready` 候选规则至少具备 positive、negative、boundary 三类样本。
- 对当前样本池缺文书导致无法补齐的规则，状态转为 `ready_with_data_gap` 或 `blocked_by_source`，不能硬造样本。

---

## Phase 3: Rule Executor Implementation

### Task 3.1: 结构化时限规则执行器

**Files:**

- Modify/Create: `D:\LLM\LX888\apps\medqc-web\backend\app\services\qc\luxian_0609_executor.py`
- Test: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_luxian_0609_executor.py`

**Scope examples:**

- 入院记录 24 小时。
- 首次病程 8 小时。
- 术后记录 24 小时。
- 抢救记录 6 小时。
- 主治/高级职称查房时限。

**Acceptance:**

- 时限规则返回 `non_compliant/compliant/data_quality_gap/not_applicable`。
- 返回入院时间、记录时间、超时时长、文书 ID、证据摘要。
- 单测覆盖正例、反例、边界、缺时间。

### Task 3.2: 跨文书一致性执行器

**Files:**

- Modify/Create: `D:\LLM\LX888\apps\medqc-web\backend\app\services\qc\luxian_0609_cross_document.py`
- Test: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_luxian_0609_cross_document.py`

**Scope examples:**

- 查房记录复制粘贴。
- 主诉不能导出第一诊断。
- 术前讨论与手术等级/手术记录一致性。
- 输血知情同意与输血记录关联。

**Acceptance:**

- 不能只做关键词命中，必须输出比较对象和差异摘要。
- 重复/复制类规则需要相似度、重复片段、文书日期。
- 诊断推导类规则需要主诉摘要、首诊断、判断理由。

### Task 3.3: LLM 语义规则执行器

**Files:**

- Modify/Create: `D:\LLM\LX888\apps\medqc-web\backend\app\services\qc\luxian_0609_llm_semantic.py`
- Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\services\qc_llm_client.py`
- Test: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_luxian_0609_llm_semantic.py`

**Requirements:**

- 模型固定使用当前配置的阿里云百炼 `qwen3.5-35b-a3b`。
- Prompt 必须要求 JSON 输出。
- 输出必须可解析为：
  - `decision`
  - `confidence`
  - `reason`
  - `evidence_quotes`
  - `missing_information`
  - `suggestion`
- JSON 解析失败时返回 `uncertain`，不能直接判问题。

**Acceptance:**

- 单测使用 fake LLM client，不依赖网络。
- 实际联调脚本能抽样调用真实模型并记录耗时和解析成功率。
- 不向前端返回 prompt 或 raw_response。

### Task 3.4: 数据联查规则执行器

**Files:**

- Modify/Create: `D:\LLM\LX888\apps\medqc-web\backend\app\services\qc\luxian_0609_data_linkage.py`
- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-执行依赖矩阵.md`
- Test: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_luxian_0609_data_linkage.py`

**Scope examples:**

- CT/MRI 检查前记录、报告后记录、阳性结果分析。
- 细菌培养报告后 24 小时记录及阳性菌分析。
- 化疗记录与医嘱一致性。
- I/II 类切口抗菌药物预防使用时长。
- 输血医嘱与收费一致性。

**Acceptance:**

- 如果当前库没有对应表或字段，返回 `data_quality_gap`，并说明缺少的数据源。
- 如果有数据源，返回联查证据和判定结果。
- 不因为缺数据把规则误判为合格或不合格。

---

## Phase 4: Integration With Sample Validation

### Task 4.1: 后端规则集接入正式执行器

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\services\qc_rule_sets.py`
- Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\services\sample_validation_rule_sets.py`
- Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\routers\qc_sample_pools.py`
- Test: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_qc_sample_pools_router.py`

**Acceptance:**

- `luxian_0609_qc_v1` 在客户样本验证页面可选。
- 发起任务时使用泸县0609规则包，而不是 SC 内涵质控默认规则。
- 批量任务返回每条规则的 `qc_point_id`、规则名称、判定状态、证据摘要。

### Task 4.2: 前端结果展示闭环

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\CustomerSampleValidationView.vue`
- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\types.ts`
- Test: `D:\LLM\LX888\apps\medqc-web\tests\unit\views\workstation-v4\CustomerSampleValidationView.spec.ts`

**Acceptance:**

- 页面能选择 `泸县0609质控点验证 v1` 和 `SC 内涵质控全量 v1`。
- 结果表能显示：规则包、命中规则、证据状态、数据缺口、复核入口。
- 对 `data_quality_gap` 和 `uncertain` 使用独立视觉状态，不混入问题数。
- 用户能从样本病历进入病历详情和具体质控结果。

---

## Phase 5: Accuracy Evaluation Gate

### Task 5.1: 批量评估脚本标准化

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\scripts\qc\evaluate_luxian_0609_rules.py`
- Create/Update: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_qc_eval.json`
- Create/Update: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_qc_eval.csv`
- Create/Update: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点评估报告.md`

**Metrics:**

- rule_count
- executable_rule_count
- formal_ready_count
- TP/FP/TN/FN/Unknown
- precision
- recall
- unknown_rate
- data_gap_rate
- sample_coverage_rate

**Acceptance:**

- 脚本能读取 batch job JSON 和 golden cases。
- 规则级、样本级、总体级指标齐全。
- 没有 golden cases 的规则标记为 `not_ready`。

### Task 5.2: 设置上线门禁

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\scripts\qc\evaluate_luxian_0609_rules.py`
- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-上线准备度看板.md`

**Gate:**

- `formal_ready` 规则：precision >= 0.90，recall >= 0.85。
- `ready_with_data_gap` 规则：0 误判，且数据缺口说明完整。
- 所有规则：不得有未解释的 `unsupported`。
- LLM 规则：JSON 解析成功率 >= 0.95。

**Acceptance:**

- 运行脚本后可直接输出 `ready_for_customer_validation=true/false`。
- 未通过时列出阻塞规则和阻塞原因。

---

## Phase 6: Customer Demo and Operation Readiness

### Task 6.1: 客户样本验证演示脚本

**Files:**

- Create/Update: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-客户样本验证演示脚本.md`

**Content:**

- 演示入口。
- 如何选择泸县0609规则集。
- 如何发起验证。
- 如何看命中问题、数据缺口、证据链。
- 如何解释未覆盖规则。
- 如何导出或截图复核材料。

**Acceptance:**

- 医院现场可以按文档逐步演示。
- 对未达成项有清晰话术，不夸大已实现能力。

### Task 6.2: 最终回归

**Commands:**

```powershell
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
python scripts\qc\check_luxian_0609_catalog.py
python scripts\qc\check_luxian_0609_golden_cases.py
python scripts\qc\evaluate_luxian_0609_rules.py --write
```

**Acceptance:**

- 前端基础检查通过。
- 规则目录检查通过。
- golden cases 检查通过，或仅剩明确 `ready_with_data_gap/blocked_by_source` 的规则。
- 评估脚本输出可用于上线判断。

---

## Workstream Ownership

建议用 5 个并行子 agent 执行，但每个子 agent 必须先读本计划和相关文档：

1. **规则语义 agent**：负责 49 条规则的语义、依赖矩阵、正式 catalog。
2. **样本与评估 agent**：负责候选样本覆盖、golden cases、评估脚本、准确性门禁。
3. **后端执行器 agent**：负责结构化、跨文书、LLM、数据联查执行器。
4. **前端闭环 agent**：负责客户样本验证页面规则集选择、结果展示、数据缺口呈现。
5. **验收文档 agent**：负责演示脚本、上线准备度看板、客户说明材料。

---

## Non-Goals

- 不重新设计所有 UI。
- 不把 49 条规则伪装成全部已实现。
- 不为了命中率把不适用规则强行判定为合格。
- 不直接暴露完整病历原文给前端或报告。
- 不在本任务中重做 SC 全量质控规则。
