# LX0609 66条已定义规则可解释收敛 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将待确认9条以外的66条LX0609规则全部做到可执行、可解释、可定位、可验收；每条合规结果说明为什么合规，每条数据不足结果明确缺少什么资料以及该缺口为什么阻止判断。

**Architecture:** 保持 `Bundle / Evidence Snapshot → Native → RuleDecision → CanonicalQcResultEnvelope → 保存 → 单一结果 API → 前端只渲染` 不变。复用现有 `findings`、`evidence`、`suggestion`、`reason_code`、`criterion_results`、`evidence_items` 和 `customer_display_facts`，不新增第二套结果DTO；通过规则合同声明判定子项，由各Native执行器提交实际事实和缺失事实，统一 renderer 只做受控文案投影，不重新判定状态。

**Tech Stack:** Python 3、dataclass、FastAPI、PostgreSQL、现有 EvidenceSnapshot / RuleDecision / CanonicalQcResultEnvelope、pytest；前端继续使用现有 Vue 3 结果渲染链，不承担规则解释。

---

## 1. 范围和完成定义

### 1.1 本阶段66条

排除以下9条待确认规则：

```text
LX0609-010、017、023、024、028、049、056、059、075
```

本阶段纳入：

| 规则族                   |   数量 | 规则ID                                       |
| ------------------------ | -----: | -------------------------------------------- |
| 基础时限                 |      5 | 001、002、004、005、006                      |
| 查房病程                 |      5 | 007、008、009、016、018                      |
| 检查检验                 |      4 | 011、012、014、015                           |
| 会诊质量                 |      3 | 020、021、022                                |
| 手术麻醉                 |     14 | 003、025、029～040                           |
| 输血                     |      8 | 041～048                                     |
| 肿瘤病理                 |      4 | 013、019、026、027                           |
| 死亡、出院与连续医疗记录 |     23 | 050～055、057、058、060～074（不含056、059） |
| **合计**                 | **66** | 无重复、无缺号误算                           |

### 1.2 LX0609-009的特殊边界

009虽然属于上述66条，但当前只完成“病危医嘱有效期间每天至少有1次查房病程”的确定子判定。

“病情变化时应及时记录病程”继续保持暂停，不自行定义病情变化事件。结果和验收报告必须显示：

- 已执行子项：病危期间每日覆盖；
- 暂缓子项：病情变化事件响应；
- 不得以每日覆盖通过宣称009所有潜在子项均已验证。

### 1.3 一条规则何时算完成

每条规则必须同时满足：

1. 有唯一执行器，且每次任务 exactly-once 输出。
2. 有明确的适用性触发事实和排除事实。
3. 有完成判断所需的数据来源、字段、时间和关联条件。
4. `compliant` 返回实际满足了什么条件，而不是只写“符合质控要求”。
5. `non_compliant` 返回违反了什么条件、实际值、标准值和差异。
6. `data_gap` 返回缺失资料的具体中文名称、已经取得的资料、缺口造成的影响和补充建议。
7. `not_applicable` 返回未触发规则的确定事实，不能以数据源缺失代替不适用。
8. 至少有合规、不合规以及适用性/数据不足的受控样本。
9. 关键事实有可定位的 `evidence_items`；纯存在性缺失应列出已核对的来源。
10. 保存的 Envelope 与单一结果 API 回读逐字段一致。

## 2. 统一解释合同

### 2.1 不改变对外Envelope结构

继续使用现有字段：

```json
{
  "status": "compliant | non_compliant | not_applicable | data_gap | technical_error | uncertain",
  "findings": "客户首先看到的一句话结论",
  "evidence": "支持结论或说明缺口影响的简明事实",
  "suggestion": "客户下一步动作",
  "reason_code": "受控原因码",
  "criterion_results": [],
  "evidence_items": [],
  "customer_display_facts": {}
}
```

不新增 `explanation_v2`、`gap_engine` 或前端状态解释器。数据库和API继续原样保存、原样返回该 Envelope。

### 2.2 合规结果合同

合规结果至少回答“核对了什么”和“为什么满足”。

按规则类型输出：

| 类型      | 必须包含的事实                         | 示例                                               |
| --------- | -------------------------------------- | -------------------------------------------------- |
| 时限      | 起算时间、完成时间、实际间隔、规定时限 | “首次病程于入院后2.1小时完成，未超过8小时。”       |
| 存在性    | 触发事件、目标文书名称、文书时间       | “已确认实施手术，并找到对应术前小结。”             |
| 频次/覆盖 | 适用期间、应记录日期、实际覆盖情况     | “病危期间共3个自然日，3日均有查房病程。”           |
| 完整性    | 已核对字段及均已填写的结论             | “输血病程已记录成分、输血量、过程观察和输注效果。” |
| 一致性    | 被比较对象和一致的关键字段             | “手术、麻醉及术后首次病程中的红细胞2U记录一致。”   |
| 语义要求  | 被核对文书、满足的最低内容             | “会诊申请已说明当前病情、会诊理由和明确目的。”     |

禁止使用无法由事实支持的模板，例如“已全面核对”“内容完整”或“均符合要求”。

### 2.3 数据不足结果合同

每个数据不足结果必须返回四项信息：

1. **具体缺什么：** 例如“CT报告时间”“麻醉医师签名”“输血成分和输血量”，不得只写“相关资料”。
2. **已经有什么：** 例如“已读取到麻醉同意书，但签名字段为空”。
3. **为什么无法判断：** 例如“没有报告时间，无法计算报告后24小时窗口”。
4. **客户怎么补：** 指向应同步的数据表、文书或字段，不暴露内部表名和异常堆栈。

缺口原因继续使用并完善现有受控枚举：

| 原因码                       | 客户语义                         | 不得混淆为             |
| ---------------------------- | -------------------------------- | ---------------------- |
| `source_unavailable`         | 系统尚未接入所需资料来源         | 当前病例确实没有该记录 |
| `source_empty`               | 来源可读取，但本病例未返回记录   | 目标文书确定缺失       |
| `source_truncated`           | 只取得部分内容                   | 字段填写不完整         |
| `required_field_missing`     | 找到记录，但关键字段为空         | 数据源未接入           |
| `authoritative_time_missing` | 缺可靠起算或完成时间             | 一般字段缺失           |
| `association_failed`         | 资料存在，但无法确认属于同一事件 | 资料不存在             |

关键判定边界：

- 数据源完整、触发事实明确、目标文书确定不存在：存在性规则应判不合规，不是数据不足。
- 数据源未接入或读取失败：不得据此判目标文书不存在。
- 多次手术、会诊、检查、输血无法正确配对：返回 `association_failed`，不得取时间最近的一条强行判断。
- SQL错误、超时、模型异常属于 `technical_error`，不得包装成数据不足。

### 2.4 结构化子项合同

扩展现有 `RuleCriterionContract` / `CriterionResult`，不另建并行模型。每条已定义规则声明最小判定子项：

```python
RuleCriterionContract(
    criterion_id="completion_interval",
    label="完成时限",
    kind="timeliness",
    source_fact="first_course_record.completed_at",
    operator="lte",
    expected=8,
    unit="hour",
)
```

执行器只提交受控值：

```python
CriterionResult(
    criterion_id="completion_interval",
    status=CriterionStatus.PASSED,
    reason_code="requirement_satisfied",
    actual_value="2.08",
    expected_value="8",
    operator="lte",
    unit="hour",
    fact_refs=(...),
)
```

本阶段允许的最小 `kind`：

```text
presence、timeliness、coverage、completeness、consistency、text_length、semantic_relation
```

`CriterionResult` 不改变 reducer 的状态权威，只承担解释。Binding 必须校验：

- 合规结果不能包含 required criterion 的 `failed`。
- 不合规结果至少包含一个 `failed`。
- 数据不足至少包含一个 `unknown`，并能映射到具体中文资料名称。
- 子项引用只能来自本次 Snapshot。
- 文案标签来自可信规则合同，不能由模型自由生成。

## 3. 实施顺序

### Task 0：冻结66条范围并修正规则阶段状态

**Files:**

- Modify: `backend/app/data/luxian_0609_phase_scope_v1.json`
- Modify: `backend/app/data/luxian_0609_rule_contracts_v1.json`
- Modify: `backend/app/data/luxian_0609_phase1_rule_contracts_extension_v1.json`
- Test: `backend/tests/unit/test_luxian_0609_phase_scope.py`
- Test: `backend/tests/unit/test_luxian_0609_rule_contracts.py`
- Test: `backend/tests/unit/test_luxian_0609_full_regression_scope.py`

**Steps:**

1. 写失败测试，要求阶段状态与业务标准基线一致。
2. 将012、021、022、026、037、042、043、044、046、048从 `pending_definition` 升为已定义目标。
3. 将018从部分定义升为已定义目标。
4. 将056、059、075从当前目标降为 `pending_definition`。
5. 保留009为部分定义，并固定 active/pending 子项。
6. 断言最终为：65条完整定义、1条部分定义、9条待确认。
7. 运行聚焦测试并提交。

**Run:**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_phase_scope.py backend/tests/unit/test_luxian_0609_rule_contracts.py backend/tests/unit/test_luxian_0609_full_regression_scope.py -q
```

**Commit:** `配置：对齐LX0609业务标准阶段范围`

### Task 1：建立统一的合规与数据缺口解释合同

**Files:**

- Modify: `backend/app/services/luxian_0609/rule_contracts.py`
- Modify: `backend/app/services/luxian_0609/decision_model.py`
- Modify: `backend/app/services/luxian_0609/decision_binding.py`
- Modify: `backend/app/services/luxian_0609/source_gap_contract.py`
- Modify: `backend/app/services/luxian_0609/customer_renderer.py`
- Test: `backend/tests/unit/test_luxian_0609_rule_contracts.py`
- Test: `backend/tests/unit/test_luxian_0609_decision_binding.py`
- Test: `backend/tests/unit/test_luxian_0609_customer_renderer.py`
- Test: `backend/tests/unit/test_luxian_0609_source_observation.py`

**Steps:**

1. 为新的 criterion kind、operator、unit 写失败测试。
2. 为规则合同增加受控 `label`，拒绝空标签、重复子项和未知类型。
3. 扩展 `CriterionResult` 的受控标量和单位，但不允许任意对象或模型原文。
4. 在 binding 中增加终态与 criterion 一致性检查，矛盾时 fail-closed 为合同错误。
5. 让 renderer 根据可信合同和 criterion 生成合规短句。
6. 让 renderer 根据 `unknown` criterion 生成“缺什么、已有何物、影响什么”的数据不足说明。
7. 保留现有规则专用展示事实；不得在 renderer 重新查库或计算状态。
8. 运行聚焦测试并提交。

**Run:**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_rule_contracts.py backend/tests/unit/test_luxian_0609_decision_binding.py backend/tests/unit/test_luxian_0609_customer_renderer.py backend/tests/unit/test_luxian_0609_source_observation.py -q
```

**Commit:** `重构：统一LX0609结果解释与资料缺口合同`

### Task 2：基础时限与查房病程10条

**Rules:** 001、002、004～009、016、018。

**Files:**

- Modify: `backend/app/services/luxian_0609/basic_timeliness_facts.py`
- Modify: `backend/app/services/luxian_0609/native_basic_timeliness.py`
- Modify: `backend/app/services/luxian_0609/native_course_quality_execution.py`
- Modify: 两份规则合同JSON中的对应规则
- Test: `backend/tests/unit/test_luxian_0609_native_basic_timeliness.py`
- Test: `backend/tests/unit/test_luxian_0609_native_course_quality_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_basic_timeliness_fact_contract.py`

**Steps:**

1. 为每条规则补合规、不合规、缺权威时间、缺目标文书、门控不适用测试。
2. 时限规则输出起算时间、完成时间、实际间隔、规定时限及超出/剩余时间。
3. 007～009输出严重程度医嘱期间、应覆盖日期和实际记录日期。
4. 009明确展示只执行“每日覆盖”，不宣称完成病情变化子项。
5. 016输出比较文书、比较段落及“完全相同/未完全相同”的受控事实，不使用待确认的70%阈值。
6. 018同时输出主诉字数和诊断指向两个子项。
7. 聚焦测试通过后提交。

**Commit:** `修复：完成LX0609基础时限与病程解释闭环`

### Task 3：检查检验与肿瘤病理8条

**Rules:** 011～015（不含013在执行器归属上单列）、013、019、026、027；实际唯一ID为011、012、013、014、015、019、026、027。

**Files:**

- Modify: `backend/app/services/luxian_0609/exam_lab_fact_extraction.py`
- Modify: `backend/app/services/luxian_0609/native_exam_lab_execution.py`
- Modify: `backend/app/services/luxian_0609/native_tumor_pathology_execution.py`
- Modify: 两份规则合同JSON中的对应规则
- Test: `backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_tumor_pathology_execution.py`
- Test: `backend/tests/unit/test_document_assembly_exam_lab_master.py`
- Test: `backend/tests/unit/test_document_assembly_pathology.py`

**Steps:**

1. 以报告事件为单位写多报告关联失败测试，禁止按单个检验项目形成独立事件。
2. 011、012、014、015输出报告时间、响应病程时间、实际间隔和记录/分析内容子项。
3. 012只以报告结构字段或原文明示“阳性”触发。
4. 013、019必须先证明病理数据源完整；源缺失不得判不适用。
5. 026输出化疗医嘱与病程比较的药名、剂量、用法和时间子项。
6. 027输出恶性肿瘤触发事实及出院计划中已核对的治疗/随访内容。
7. 对每个数据不足场景明确缺报告时间、阳性结果、病程响应、取材记录或药名归一信息。
8. 聚焦测试通过后提交。

**Commit:** `修复：完成LX0609检查检验与肿瘤病理解释闭环`

### Task 4：会诊3条

**Rules:** 020、021、022。069留在扩展文书执行器批次，但复用同一会诊episode事实。

**Files:**

- Modify: `backend/app/services/luxian_0609/consultation_fact_contract.py`
- Modify: `backend/app/services/luxian_0609/consultation_020_relation_contract.py`
- Modify: `backend/app/services/luxian_0609/native_consultation_episode_execution.py`
- Modify: 两份规则合同JSON中的对应规则
- Test: `backend/tests/unit/test_luxian_0609_consultation_fact_contract.py`
- Test: `backend/tests/unit/test_luxian_0609_consultation_020_relation_contract.py`
- Test: `backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py`

**Steps:**

1. 固定申请、意见、执行记录的业务键优先关联。
2. 020输出对应会诊意见及执行记录的关联事实。
3. 021按病情诊疗、会诊理由、会诊目的、申请时间、申请医师逐项说明。
4. 022按临床特点、诊断依据、治疗意见、随访意见、科别、时间、签名逐项说明。
5. 多次会诊无法配对时返回 `association_failed` 并列出无法配对的记录。
6. LLM只提取最小受控内容子项，Python校验枚举并决定状态。
7. 聚焦测试通过后提交。

**Commit:** `修复：完成LX0609会诊规则解释闭环`

### Task 5：手术麻醉14条

**Rules:** 003、025、029～040。

**Files:**

- Modify: `backend/app/services/luxian_0609/surgery_applicability.py`
- Modify: `backend/app/services/luxian_0609/native_surgery_gate_execution.py`
- Modify: `backend/app/services/luxian_0609/native_surgery_document_execution.py`
- Modify: `backend/app/services/luxian_0609/native_mdt_execution.py`
- Modify: 两份规则合同JSON中的对应规则
- Test: `backend/tests/unit/test_luxian_0609_surgery_applicability.py`
- Test: `backend/tests/unit/test_luxian_0609_native_surgery_gate_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_surgery_document_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_mdt_execution.py`

**Steps:**

1. 先固定手术/非手术操作门控及手术分级事实，所有14条复用同一适用性结果。
2. 003输出手术结束时间、手术记录时间、实际间隔和24小时标准。
3. 029、030、032～034、036、038输出触发事件和找到/缺失的目标文书。
4. 025输出植入物每个必填字段的完整性。
5. 031输出术者、书写医师、签名医师及第一助手例外。
6. 035、037输出同意书或访视记录的具体缺项。
7. 039输出急诊抢救例外、术前讨论存在性及术者参加事实。
8. 040输出手术代码、院内优先分级、四级判定来源及多学科参与事实。
9. 多台手术无法绑定文书时返回 `association_failed`，不得跨手术借用文书。
10. 聚焦测试通过后提交。

**Commit:** `修复：完成LX0609手术麻醉规则解释闭环`

### Task 6：输血8条

**Rules:** 041～048。

**Files:**

- Modify: `backend/app/services/luxian_0609/native_transfusion_execution.py`
- Modify: `backend/app/services/luxian_0609/source_registry.py`
- Modify: 两份规则合同JSON中的对应规则
- Test: `backend/tests/unit/test_luxian_0609_native_transfusion_execution.py`
- Test: `backend/tests/unit/test_document_assembly_blood_application.py`

**Steps:**

1. 固定一次输血事件的申请、医嘱、输注、文书和检验关联键。
2. 041、045输出输血触发事实和目标文书存在性。
3. 042输出同意书患者信息、诊断、指征、成分、风险、替代方案、患者/代理人及医师签名、时间子项。
4. 043输出ABO、Rh、抗体筛查、乙肝五项、HCV、HIV、梅毒及检查早于输血的事实。
5. 044输出指征、实验室指标、既往输血/反应、患者状态、拟用成分、预期效果和医师签名。
6. 046输出原因、时间、成分、血型、输血量、过程观察、不良反应及处置、输注效果。
7. 047输出输血后24小时内的评价时间以及临床/实验室效果。
8. 048输出手术记录、麻醉记录和术后首次病程三方的成分、剂量比较矩阵。
9. 数据不足逐项列出缺失字段；三方资料存在但无法绑定时使用 `association_failed`。
10. 聚焦测试通过后提交。

**Commit:** `修复：完成LX0609输血规则解释闭环`

### Task 7：扩展文书23条

**Rules:** 050～055、057、058、060～074（不含056、059）。

**Files:**

- Modify: `backend/app/services/luxian_0609/native_extended_document_execution.py`
- Modify: `backend/app/services/luxian_0609/source_registry.py`
- Modify: `backend/app/services/luxian_0609/source_evidence_reader.py`
- Modify: `backend/app/data/luxian_0609_phase1_rule_contracts_extension_v1.json`
- Test: `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_source_evidence_reader.py`

**Steps:**

1. 按死亡、危急值、抗菌药、出院、术后、会诊时限、交接班、转科、诊断修正拆分测试组，不拆第二套执行入口。
2. 050、051、060先证明诊断不明确或死亡触发事实，再核对目标文书及时间。
3. 052、053使用PL/PH和报告时间，输出危急值项目、报告时间、处置时间及6小时窗口。
4. 054、055、057、058输出抗菌药物、使用动作、理由、评价时间、病原学检查及特殊级目录匹配事实。
5. 061～063输出出院时间、文书时间、带药字段及诊断比较事实。
6. 064～068输出手术时间、术后3日覆盖、医师级别、术后首次病程、出院前病程及上级医师意见。
7. 069复用会诊episode，输出申请时间、完成时间和实际间隔。
8. 070输出输血前九项逐项检查结果，并与043共享同一事实定义。
9. 071～073输出经治医师变更/转科触发、文书角色和完成时间。
10. 074输出诊断修正事件、修改理由和诊断依据子项。
11. 每组聚焦测试通过后才进入下一组，整个执行器完成后统一提交。

**Commit:** `修复：完成LX0609扩展文书规则解释闭环`

### Task 8：66条验收矩阵与合成病例闭环

**Files:**

- Modify: `backend/app/data/luxian_0609_acceptance_matrix.json`
- Modify: `backend/scripts/build_luxian_0609_acceptance_matrix.py`
- Modify: `backend/scripts/build_luxian_0609_0426_synthetic_v3.py`
- Test: `backend/tests/contract/test_luxian_0609_acceptance_matrix.py`
- Test: `backend/tests/unit/test_luxian_0609_0426_synthetic_v3.py`
- Test: `backend/tests/unit/test_luxian_0609_customer_renderer.py`

**Steps:**

1. 为66条各准备至少一个合规和一个不合规样本。
2. 对存在资料依赖的规则补一个精确数据不足样本。
3. 对有门控的规则补一个不适用样本。
4. 每个合规样本断言 `findings` 不是“符合质控要求”单句，且包含至少一个病例实际事实。
5. 每个数据不足样本断言存在具体缺失项，且不出现“相关资料”“现有数据不足”等孤立泛化表述。
6. 每个确定结论断言至少有一个可定位证据或“已核对来源清单”。
7. 断言9条pending规则不会被66条验收任务误激活。
8. 运行66条矩阵并生成按规则族的通过报告。

**Run:**

```powershell
python -m pytest backend/tests/contract/test_luxian_0609_acceptance_matrix.py backend/tests/unit/test_luxian_0609_0426_synthetic_v3.py backend/tests/unit/test_luxian_0609_customer_renderer.py -q
```

**Commit:** `测试：补齐LX0609六十六条可解释验收矩阵`

### Task 9：真实病例、Envelope和单一API验收

**Files:**

- Test: `backend/tests/unit/test_luxian_0609_canonical_result_delivery.py`
- Test: `backend/tests/unit/test_luxian_0609_record_result_read_model.py`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`
- Create: `docs/reports/2026-08-xx-lx0609-66-rule-acceptance.md`

**Steps:**

1. 只读运行合成验证集，确认66条均真实执行，不存在 `not_executed` 占位。
2. 对208790、359787及至少一份非手术病例进行规则族抽样复核。
3. 逐条核对数据库保存 Envelope 与单一结果 API 返回的状态、事实、缺口和证据一致。
4. 统计每条规则的状态、解释完整度、证据定位率、LLM调用数和执行耗时。
5. 对真实病例中确实缺少源数据的规则保留 `data_gap`，但必须通过具体缺口文案验收。
6. 确认前端仅渲染API结果，不增加状态映射或业务推断。
7. 完成功能闭环后运行发布前检查并提交验收报告。

**Run:**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_canonical_result_delivery.py backend/tests/unit/test_luxian_0609_record_result_read_model.py backend/tests/unit/test_luxian_0609_result_aggregator.py -q
```

**Commit:** `测试：完成LX0609六十六条端到端验收`

## 4. 发布门禁

66条全部满足以下条件才可宣布本阶段完成：

| 指标               | 要求                                      |
| ------------------ | ----------------------------------------- |
| 规则执行覆盖       | 66/66真实执行，0条占位                    |
| 合规解释完整率     | 100%，必须包含实际事实                    |
| 数据不足具体率     | 100%，必须指出具体来源/字段/时间/关联缺口 |
| 不适用门控证据率   | 100%                                      |
| 确定结论证据定位率 | 100%，或存在明确的已核对来源清单          |
| 技术异常伪装率     | 0%                                        |
| Envelope/API一致率 | 100%                                      |
| Pending误执行      | 0条                                       |
| 新增无触发LLM调用  | 0次                                       |

任何一个规则族未通过时，只阻止该族进入发布基线，不回退已经通过的规则族，也不通过聚合器补文案掩盖问题。

## 5. 明确不做

- 不重写整个质控引擎。
- 不引入规则DSL、Evidence Graph或新的工作流引擎。
- 不改变数据库 Envelope 保存模型和单一结果API。
- 不让前端拼装“为什么合规”或推断缺失资料。
- 不为通过测试伪造证据定位。
- 不在本阶段自行决定9条pending规则。
- 不把真实源数据缺失强行改判为合规、不合规或不适用。
- 不在每个小补丁后运行全量前后端构建；每族先运行聚焦测试，阶段结束后再做发布级检查。

## 6. 执行顺序与停止点

严格按以下顺序执行：

```text
Task 0 范围对齐
  ↓
Task 1 统一解释合同
  ↓
Task 2～7 按规则族逐族完成
  ↓
Task 8 合成病例矩阵
  ↓
Task 9 真实病例与交付链验收
```

每个规则族形成独立提交。若某族必须修改 Envelope/API 或要求客户确认新口径，立即停止该族并记录阻塞，不扩大为全局架构改造。
