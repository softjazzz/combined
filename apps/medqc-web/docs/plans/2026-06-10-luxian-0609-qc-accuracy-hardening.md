# 泸县0609质控点准确性质控 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让“泸县0609质控点验证 v1”成为可在 `/workstation-v4/customer-sample-validation` 正式运行、逐条有效、可复核、可计算准确率的客户专项质控集。

**Architecture:** 以客户 49 条质控点为唯一上线范围，按“规则口径锁定 -> 数据依赖接入 -> 执行器实现 -> 证据链输出 -> golden cases -> 准确率评估 -> 页面验收 -> 发布闸门”推进。每条质控点必须明确是否可判定、为什么命中、引用了哪些文书或结构化数据；缺数据时返回 `data_quality_gap`，不得伪装为缺陷命中。

**Tech Stack:** Python/FastAPI 后端、Vue 3/TypeScript 前端、现有 Sichuan QC batch job、客户样本验证页、阿里云百炼 `qwen3.5-35b-a3b` 语义判断、JSON/CSV/Markdown 验收工件、pytest/npm 单测。

---

## 成功标准

本长程任务不是 UI 重绘，完成标准如下：

1. 49 条泸县0609质控点均有唯一 `LX0609-xxx`、客户原文、规则口径、适用文书、触发条件、排除条件、数据依赖、证据字段、上线状态。
2. 每条规则只能处于以下一种状态：
   - `formal_ready`: 可正式运行，golden cases 齐全，准确率达标。
   - `ready_with_data_gap`: 规则逻辑完成，但当前样本池缺关键数据，系统能返回“数据不足无法判定”。
   - `needs_evidence_hardening`: 可执行但证据链、边界条件或客户口径需补强。
   - `needs_cross_document`: 需跨文书 bundle 后才能准确判断。
   - `needs_data_linkage`: 需接入医嘱、检查、检验、输血、费用等结构化时间轴。
   - `needs_rule_implementation`: 当前没有可执行逻辑，需要新增规则。
   - `blocked_by_source`: 当前系统没有必要数据源，只能标注不可判定。
3. 每条 `formal_ready` 规则至少有 1 个阳性、1 个阴性、1 个边界/数据质量样本，并由人工复核为 `accepted` 后导入 golden cases。
4. 每条 `formal_ready` 规则输出统一结构：
   - `qc_point_id`
   - `rule_name`
   - `status`: `non_compliant` / `compliant` / `not_applicable` / `data_quality_gap` / `uncertain`
   - `evidence_documents`
   - `evidence_snippets`
   - `rule_basis`
   - `reasoning_summary`
   - `suggestion`
   - `risk_level`
5. 准确率门槛：
   - P0 规则 precision >= 0.90，recall >= 0.85。
   - 普通上线规则 precision >= 0.85，recall >= 0.80。
   - `data_quality_gap` 和 `uncertain` 不计入缺陷命中率，但必须统计占比。
6. `/workstation-v4/customer-sample-validation` 可以选择“泸县0609质控点验证 v1”，并展示规则集状态、命中证据、文书定位、复核结论、导出报告。
7. 发布闸门脚本输出 `release_ready=true` 或明确分阶段状态，例如 `p0_release_ready=true`、`full_release_ready=false`。

---

## 当前基线

截至 2026-06-10：

- 规则目录：49 条，目录结构检查通过。
- `formal_ready`: 3 条。
- `ready_with_data_gap`: 3 条。
- `needs_evidence_hardening`: 10 条。
- `needs_cross_document`: 14 条。
- `needs_data_linkage`: 15 条。
- `needs_rule_implementation`: 4 条。
- 候选样本：178 条，仍待人工复核。
- golden cases：仍缺 49 条规则的 positive / negative / boundary 完整组合。
- 当前真正接近正式验证的规则：`LX0609-017`、`LX0609-021`、`LX0609-032`。
- 已有最小复核包：`docs/0602/luxian_0609_formal_ready_min_review_sheet.csv`，3 条规则 x 3 类样本，共 9 行。

---

## Phase 1: 规则口径锁定

### Task 1.1: 固化 49 条规则目录

**Files:**

- Read: `D:\LLM\LX888\apps\medqc-web\docs\0602\质控点及规则.xlsx`
- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_formal_rule_catalog.json`
- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-正式上线规则清单.md`

**Steps:**

1. 读取 Excel，确认客户质控点数量为 49。
2. 确认每条规则有唯一 `LX0609-xxx`。
3. 为每条规则补齐：
   - 客户原文
   - 适用文书
   - 触发条件
   - 不触发条件
   - 边界条件
   - 数据依赖
   - 证据字段
   - 当前状态
4. 运行：
   ```powershell
   python scripts\qc\check_luxian_0609_catalog.py
   ```
5. Expected: `catalog_count=49`，`errors=0`。

### Task 1.2: 将规则分成 4 个执行批次

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-执行依赖矩阵.md`
- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-正式上线工作包.md`

**Batch Definition:**

- Batch A: 单文书/存在性/时限规则，优先做成 formal-ready。
- Batch B: 同域多文书规则，例如多篇病程记录相似度。
- Batch C: 跨文书规则，例如手术记录 vs 安全核查、会诊记录 vs 病程执行。
- Batch D: 跨表联查规则，例如医嘱、检查、检验、输血、费用。

**Expected:** 每条规则都有 `implementation_batch`，且 Batch A/B 优先进入 P0。

---

## Phase 2: 数据上下文与执行器

### Task 2.1: 建立规则级上下文 bundle

**Files:**

- Create/Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\services\qc\luxian_0609_context.py`
- Test: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_luxian_0609_context.py`

**Requirements:**

- 输入 `visit_id`。
- 输出规则需要的文书和结构化片段。
- 支持以下文书域：
  - 入院记录
  - 首次病程
  - 日常病程
  - 上级查房
  - 抢救记录
  - 会诊记录
  - 手术记录
  - 术前小结/讨论
  - 手术安全核查
  - 麻醉记录/访视
  - 出院记录
  - 输血相关文书
- 支持以下结构化域：
  - 医嘱
  - 检查
  - 检验
  - 输血
  - 费用

**Expected:** 缺数据时返回 `data_quality_gap` 所需的缺口说明，不抛异常、不误判。

### Task 2.2: 实现确定性执行器

**Files:**

- Create/Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\services\qc\luxian_0609_executor.py`
- Test: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_luxian_0609_executor.py`

**Scope:**

- 文书存在性。
- 时间窗判断。
- 多文书相似度。
- 文书之间的存在性联动。

**Output Contract:**

```python
{
    "qc_point_id": "LX0609-032",
    "status": "non_compliant",
    "risk_level": "high",
    "evidence_documents": [],
    "evidence_snippets": [],
    "reasoning_summary": "",
    "suggestion": "",
    "data_gaps": [],
}
```

**Expected:** 不调用 LLM 也能覆盖 Batch A/B 的确定性规则。

### Task 2.3: 实现 LLM 语义判断执行器

**Files:**

- Create/Modify: `D:\LLM\LX888\apps\medqc-web\backend\app\services\qc\luxian_0609_llm_semantic.py`
- Test: `D:\LLM\LX888\apps\medqc-web\backend\tests\unit\test_luxian_0609_llm_semantic.py`

**Scope:**

- 会诊目的是否明确。
- 会诊意见是否明确。
- 主诉是否能导出第一诊断。
- 肿瘤治疗计划是否完整。
- 阳性检查/培养是否有分析。

**Rules:**

- 模型固定：`qwen3.5-35b-a3b`。
- 输入只传规则相关片段，不传全病历。
- 输出必须是 JSON schema。
- JSON 解析失败返回 `uncertain`。
- 不暴露 prompt、raw_response、完整病历正文。

**Expected:** 语义规则输出可复核证据，而不是一句“AI 判断”。

---

## Phase 3: Golden Cases 与准确率

### Task 3.1: 建立人工复核工作表

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\scripts\qc\build_luxian_0609_first_pass_review_sheet.py`
- Output: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_first_pass_review_sheet.csv`

**Steps:**

1. 每条规则挑选 positive / negative / boundary 候选。
2. 候选必须包含证据摘要。
3. 证据不足的候选不得进入复核表。
4. 运行：
   ```powershell
   python scripts\qc\build_luxian_0609_first_pass_review_sheet.py --write
   ```

**Expected:** 复核表覆盖所有可执行规则，不能自动标记 accepted。

### Task 3.2: 导入 accepted golden cases

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\scripts\qc\import_luxian_0609_reviewed_cases.py`
- Modify: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-golden-cases.json`

**Steps:**

1. 人工复核 CSV 中 `review_status=accepted` 的行。
2. 导入 golden cases。
3. 运行：
   ```powershell
   python scripts\qc\import_luxian_0609_reviewed_cases.py --review-csv docs\0602\luxian_0609_first_pass_review_sheet.csv --write --write-report
   python scripts\qc\check_luxian_0609_golden_cases.py
   ```

**Expected:** 每条上线规则至少有 positive / negative / boundary。

### Task 3.3: 评估规则准确率

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\scripts\qc\evaluate_luxian_0609_rules.py`
- Create/Modify: `D:\LLM\LX888\apps\medqc-web\scripts\qc\check_luxian_0609_formal_ready_predictions.py`
- Output: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_qc_eval.json`
- Output: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点评估报告.md`

**Metrics:**

- TP
- FP
- TN
- FN
- Unknown
- Data Gap
- precision
- recall
- unknown_rate
- data_gap_rate

**Expected:** 低于门槛的规则自动降级为 `needs_evidence_hardening` 或 `trial_only`。

### Task 3.4: 建立 formal-ready 最小预测门禁

**Files:**

- Create/Modify: `D:\LLM\LX888\apps\medqc-web\scripts\qc\predict_luxian_0609_formal_ready_cases.py`
- Create/Modify: `D:\LLM\LX888\apps\medqc-web\scripts\qc\check_luxian_0609_formal_ready_predictions.py`
- Output: `D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_formal_ready_min_predictions.json`
- Output: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-formal-ready最小预测质量报告.md`

**Steps:**

1. 基于 `docs\0602\luxian_0609_formal_ready_min_review_sheet.csv` 生成预测。
2. 校验 3 条 formal-ready 规则各有 positive / negative / boundary 预测。
3. 校验每条预测都有 `qc_point_id`、`case_id`、`visit_id`、`actual_hit`、`status`。
4. 校验命中结果必须有 `evidence_summary` 和 `matched_text`。
5. 运行：
   ```powershell
   python scripts\qc\predict_luxian_0609_formal_ready_cases.py --review-csv docs\0602\luxian_0609_formal_ready_min_review_sheet.csv --output docs\0602\luxian_0609_formal_ready_min_predictions.json --write
   python scripts\qc\check_luxian_0609_formal_ready_predictions.py --write
   ```

**Expected:** `formal_ready_rule_count=3`、`prediction_count=9`、`complete_rule_count=3`、`error_count=0`。该门禁只证明预测结构可用于后续评估，不代表人工准确率已经达标。

---

## Phase 4: 客户样本验证页面闭环

### Task 4.1: 规则集选择与状态展示

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\index.vue`
- Modify: `D:\LLM\LX888\apps\medqc-web\src\views\workstation-v4\customer-sample-validation\types.ts`
- Modify: `D:\LLM\LX888\apps\medqc-web\src\services\manual-case-sample-service.ts`

**Requirements:**

- 可选择：
  - `luxian_0609_qc_v1`
  - `sc_content_full_v1`
- 展示：
  - 已上线规则数
  - 待补规则数
  - 数据缺口规则数
  - 当前准确率
  - 最近评估时间

### Task 4.2: 结果按规则和病历双维度查看

**Requirements:**

- 按规则查看：看每条规则命中哪些病历。
- 按病历查看：看每份病历命中了哪些规则。
- 每条结果展示：
  - 质控点编号
  - 风险级别
  - 命中文书
  - 证据摘要
  - 建议处理
  - 复核状态

**Expected:** 客户可以现场点击一条问题，看到为什么判定为问题。

---

## Phase 5: 发布闸门

### Task 5.1: 建立正式上线闸门

**Files:**

- Modify: `D:\LLM\LX888\apps\medqc-web\scripts\qc\run_luxian_0609_release_gate.py`
- Output: `D:\LLM\LX888\apps\medqc-web\docs\0602\泸县0609质控点-正式版发布闸门报告.md`

**Gate Checks:**

- 49 条规则目录完整。
- 每条上线规则有执行器。
- 每条上线规则有 golden cases。
- 每条上线规则准确率达标。
- 页面能选择并运行规则集。
- 敏感字段未泄露。
- 未上线规则有明确状态和原因。

**Expected:**

```json
{
  "p0_release_ready": true,
  "full_release_ready": false,
  "failed_checks": []
}
```

### Task 5.2: 最终验证命令

Run:

```powershell
python scripts\qc\check_luxian_0609_catalog.py
python scripts\qc\check_luxian_0609_golden_cases.py
python scripts\qc\evaluate_luxian_0609_rules.py --write
python scripts\qc\run_luxian_0609_release_gate.py --write
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
```

Expected:

- 目录无错误。
- golden cases 覆盖上线规则。
- 准确率报告生成。
- 发布闸门通过 P0。
- 前端质量检查通过。

---

## 长程任务拆分建议

### Track A: 规则工程

目标：把 49 条规则逐条变成可执行定义。

交付物：

- 完整规则目录。
- 执行依赖矩阵。
- 规则状态看板。

### Track B: 样本与评估

目标：建立可计算准确率的 golden cases。

交付物：

- 人工复核工作表。
- golden cases。
- 评估报告。

### Track C: 执行器

目标：实现确定性、跨文书、跨表联查、LLM 语义四类执行器。

交付物：

- `luxian_0609_context.py`
- `luxian_0609_executor.py`
- `luxian_0609_llm_semantic.py`
- 单测与回归脚本。

### Track D: 页面闭环

目标：客户样本验证页可选择规则集、运行任务、查看证据、导出报告。

交付物：

- 规则集选择。
- 规则/病历双维结果视图。
- 证据定位。
- 导出报告。

---

## 第一阶段推荐目标

不要一上来承诺 49 条全部 formal-ready。第一阶段目标建议定义为：

**在客户样本验证页中，泸县0609规则集至少 10 条 P0 质控点达到 formal-ready，并通过 golden cases 准确率门槛；其余 39 条全部有明确待补原因和数据缺口说明。**

这能保证演示时既有真实有效的质控命中，又不会把尚未实现的跨表联查规则伪装成已上线。
