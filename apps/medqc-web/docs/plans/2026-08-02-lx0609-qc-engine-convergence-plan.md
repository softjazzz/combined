# LX0609 质控引擎收敛 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不重写质控引擎、不改变 Canonical Envelope 对外合同的前提下，将 LX0609 的 75 条质控规则收敛为可定位、可验证、可逐族替换的单一路由，使后续修复单个质控点时能够快速判断问题发生在资料、关联、适用性、判定还是交付环节。

**Architecture:** 保留已经稳定的 `Bundle / Snapshot → Native → CanonicalQcResultEnvelope → 保存 → 单一结果 API → 前端渲染` 对外交付链，只治理 Native 内部。先用一份机器可校验的 Runtime Manifest 统一规则、执行器、数据源和适用性元数据；再将引擎内部固定为 `Source Observation → Domain Fact → Event Association → Applicability → Decision → Envelope` 六段合同，以手术规则族作为试点，逐族迁移并逐族删除兼容路径。

**Tech Stack:** Python 3、FastAPI、SQLAlchemy、PostgreSQL、Pytest、现有 Luxian0609 EvidenceSnapshot、RuleDecision、FamilyExecutionEnvelope、CanonicalQcResultEnvelope；前端仅在需要展示运行清单时使用 Vue 3、TypeScript、Vitest。

---

## 1. 决策摘要

### 1.1 本轮要解决的问题

当前 75 条规则已经全部注册，但“注册完成”不等于“运行链路清晰”。修复一个规则时仍可能依次遇到：

1. 规则没有被正确派发到预期执行器。
2. 数据已经进入 Bundle，但没有进入该执行器使用的 Snapshot 或 Material Store。
3. 数据存在，但文书、医嘱、手术、检验事件没有正确关联。
4. 关联完成，但适用性门控把病例错误判为不适用或数据不足。
5. 判定已经产生，但 Typed Decision 绑定或兼容结果替换丢失了结果。
6. 规范结果正确，但证据和客户可读事实没有进入 Envelope。
7. 批量任务的旧投影仍用 `not_executed` 等占位语义误导用户。

本计划的目标是让上述七个检查点各自有唯一合同、唯一日志和聚焦测试，避免在一个巨型执行函数里反复排查。

### 1.2 明确不做

- 不重写 75 条医学规则。
- 不新建第二套“智能质控中台”或 Evidence Graph。
- 不修改数据库 Envelope 的客户结果结构，除非发现已批准合同无法表达的字段。
- 不让前端重新解释状态、适用性或证据充分性。
- 不引入新的全局 Store、消息总线或工作流引擎。
- 不一次删除所有 feature flag、legacy adapter 和兼容执行器。
- 不为了降低文件行数进行无业务收益的机械拆分。
- 不在本轮解决尚待客户定义的 8 条临时口径；只保证它们显式标注并按批准的临时口径验收。
- 不在每个微小补丁后执行完整类型检查和全量测试。

### 1.3 不可破坏的不变量

```text
医院资料 / 合成验证资料
  ↓
Bundle / Evidence Snapshot（只作为输入）
  ↓
Native 规则内部执行
  ↓
CanonicalQcResultEnvelope
  ↓ 原样保存
数据库 Envelope
  ↓ 原样读取
单一结果 API
  ↓
前端只渲染
```

实施过程中必须保持：

1. 一个病例、一个规则、一个权威结果槽位。
2. `technical_error` 不得降级成 `data_insufficient`、`not_applicable` 或 `compliant`。
3. 没有适用性证据时不得判定不适用。
4. 数据源未接入、记录不存在、正文被截断、字段为空、关联失败必须是不同缺口原因。
5. 规范状态只能由 Decision 层产生；聚合器、保存层、API 和前端不得改判。
6. LLM 只能提取受控事实，不能直接越过 Applicability 和 Python 校验写入最终状态。
7. 正式67条规则与临时8条规则必须在结果、运行清单和验收报告中可区分。

## 2. 当前基线与技术债证据

### 2.1 已经稳定的部分

- 规则总数为 75，当前全部具有执行器映射。
- 规则分布在 11 个执行器族中，而不是继续停留在最初49条规则。
- 对外 Canonical Envelope 保存和单一结果 API 已建立。
- Runtime Shadow、LLM trigger gate 当前默认关闭。
- 手术/操作及手术分级已经开始使用显式目录和院内优先口径。

### 2.2 尚未收敛的部分

`backend/app/services/luxian_0609/execution.py` 中的 `prepare_luxian_0609_execution` 同时承担：

- 规则选择；
- package plan；
- feature flag 组合；
- 数据源预取；
- Snapshot 构建；
- 旧执行器注册；
- 统一引擎调用；
- Typed Decision 选择；
- 原始结果过滤和替换；
- 兼容执行路径；
- 技术异常降级。

CodeGraph 当前识别到该入口约130个下游调用/引用关系，且直接覆盖测试不足。这是最高风险的维护热点。

迁移期结构仍包括：

- `LEGACY_NATIVE_EXECUTION_ORDER`
- `LEGACY_EXECUTOR_MATERIAL_SOURCE_KEYS`
- `LEGACY_RULE_MATERIAL_SOURCE_KEYS`
- `build_luxian_0609_legacy_executor_registry`
- `compatibility_rule_ids`
- `compatibility_execution_rule_ids`
- `legacy_fact_adapter.py`
- 部分执行器内部的 `legacy_selected`、`legacy_documents` 和旧证据回退

主要执行器体量：

| 文件                                    | 约行数 | 风险                                   |
| --------------------------------------- | -----: | -------------------------------------- |
| `native_course_quality_execution.py`    |  3,134 | 读取、关联、相似度、适用性和判定混合   |
| `native_consultation_execution.py`      |  2,387 | 历史与当前会诊语义边界复杂             |
| `native_surgery_gate_execution.py`      |  1,845 | 手术门控、目录、文书和语义判定交织     |
| `native_extended_document_execution.py` |  1,558 | 新增规则集中进入单文件                 |
| `source_evidence_reader.py`             |  1,394 | 多数据源读取与缺口语义集中             |
| `native_exam_lab_execution.py`          |  1,384 | 检查、检验、报告和病程关联混合         |
| `native_transfusion_execution.py`       |  1,382 | 输血触发、九项检查、文书和收费关联混合 |
| `native_surgery_document_execution.py`  |  1,374 | 手术文书存在性、完整性和签名判定混合   |
| `native_basic_timeliness.py`            |  1,276 | 多种时间锚点和文书角色判断混合         |
| `execution.py`                          |  1,125 | 顶层调度职责过多                       |

文件大不是独立缺陷；真正的问题是上述文件同时拥有多个阶段的判定权，导致无法单独替换或验证。

### 2.3 风险等级

| 风险 | 说明                                         | 本轮处理方式                                      |
| ---- | -------------------------------------------- | ------------------------------------------------- |
| P0   | 状态被重解释、结果丢失、规则未执行却显示完成 | 立即建立运行不变量和交付审计                      |
| P1   | 数据存在但关联失败、门控误判、证据错配       | 以规则族为单位收敛 Fact/Association/Applicability |
| P1   | 同一规则存在多路派发或功能开关组合           | 建立 Runtime Manifest 并收敛路由                  |
| P2   | 执行器巨型且职责混合                         | 迁移规则族时按阶段抽离，不单独全面拆文件          |
| P2   | 串行执行导致验证慢                           | 正确性稳定后增加受控并发                          |
| P3   | 命名、注释和未启用旧文件                     | 仅在调用方归零并验收后删除                        |

## 3. 目标架构

### 3.1 规则运行清单成为唯一事实来源

每条规则必须存在一个机器可读取的 `RuntimeRuleContract`：

```python
@dataclass(frozen=True)
class RuntimeRuleContract:
    rule_id: str
    definition_version: str
    phase_status: Literal["formal", "temporary"]
    executor_key: str
    source_keys: tuple[str, ...]
    fact_types: tuple[str, ...]
    association_contract: str | None
    applicability_contract: str
    decision_contract: str
    evidence_contract: str
    llm_policy: Literal["forbidden", "fact_extraction_only"]
```

该合同不保存运行数据，只声明执行边界。以下内容必须由它派生或校验：

- 规则到执行器映射；
- 执行器的数据源预取集合；
- 正式/临时规则计数；
- 允许的 LLM 使用方式；
- 前端可查看的规则运行说明；
- 75条规则验收矩阵骨架。

### 3.2 规则族内部固定六段

```text
Source Observation
  数据源是否接入、读取是否成功、是否截断、返回多少条
        ↓
Domain Fact
  标准化时间、文书角色、人员签名、医嘱、报告、手术、输血等事实
        ↓
Event Association
  报告属于哪次检查、文书属于哪次手术、输血记录属于哪次输注
        ↓
Applicability
  是否适用；不适用必须携带已确认的排除事实
        ↓
Decision
  只基于上述受控事实产生规范状态和判定事实
        ↓
Envelope Projection
  只投影，不改判；返回客户摘要、结构化事实和安全证据引用
```

### 3.3 每层的失败语义

| 阶段                | 失败示例                     | 允许状态                                           |
| ------------------- | ---------------------------- | -------------------------------------------------- |
| Source Observation  | 数据库超时、SQL错误          | `technical_error`                                  |
| Source Observation  | 医院未接入收费表             | `data_insufficient` + `source_unavailable`         |
| Domain Fact         | 记录存在但缺权威报告时间     | `data_insufficient` + `authoritative_time_missing` |
| Event Association   | 有手术记录但无法绑定具体手术 | `data_insufficient` + `association_failed`         |
| Applicability       | 已确认无手术                 | `not_applicable` + 明确排除事实                    |
| Applicability       | 不知道是否实施手术           | `data_insufficient`，不得判不适用                  |
| Decision            | 已适用且超过时限             | `confirmed_issue` + 标准、实际值、差值             |
| Envelope Projection | 客户文案缺失                 | 保留内部状态并触发投影质量门，不得编造解释         |

## 4. 总体验收指标

### 4.1 正确性指标

1. 75条规则全部出现在 Runtime Manifest，ID无重复、无缺失。
2. 67条正式规则、8条临时规则计数固定且可自动校验。
3. 每个选中规则 exactly-once 输出；没有 `not_executed` 占位结果混入 Canonical Envelope。
4. 每条结果明确记录实际执行器和合同版本。
5. 每条 `not_applicable` 都包含适用性排除事实。
6. 每条 `data_insufficient` 都包含受控缺口类型、缺少的资料和客户可读说明。
7. 每条 `confirmed_issue` 和 `compliant` 都包含足以支持结论的简明事实。
8. 证据引用的规则ID、病例、文书和事实一致，不允许005/006一类证据指错文书。
9. Canonical Envelope 保存前后内容哈希一致；API不重新计算状态。

### 4.2 可维护性指标

1. 新增或调整规则路由只修改 Runtime Manifest 和对应规则族，不再修改顶层硬编码规则集合。
2. `prepare_luxian_0609_execution` 不再包含按规则ID拼接的 `typed_decision_rule_ids`。
3. 数据源依赖不再同时维护于规则合同、执行器常量和调度入口三个位置。
4. 每个规则族具有独立的 Fact、Association、Applicability 和 Decision 聚焦测试。
5. 出现错误时 trace 可在一次查看中回答：规则走了哪个执行器、读了哪些来源、建立了哪些关联、为什么适用、为什么产生该状态。

### 4.3 性能指标

1. 正确性阶段不得增加无触发病例的 LLM 调用。
2. 同一病历、同一事实抽取最多执行一次并在规则族内复用。
3. 手术规则族收敛后，相比基线数据库读取次数不增加，目标减少重复读取30%以上。
4. 完成全部规则族后再将确定性执行器并发从1调整到2；稳定后才评估4。
5. LLM并发单独限流，不得与确定性执行器共用无界并发。

## 5. 实施批次

### Task 0：冻结基线与建立停止条件

**目的：** 防止治理过程中把医学口径变化、数据修复和架构调整混在一起。

**Files:**

- Create: `docs/reports/2026-08-02-lx0609-engine-convergence-baseline.md`
- Create: `backend/scripts/audit_luxian_0609_runtime_manifest.py`
- Test: `backend/tests/unit/test_luxian_0609_runtime_manifest.py`
- Reference: `docs/plans/2026-07-31-qc-rule-defined-scope-development-task.md`

**步骤：**

1. 记录当前提交、工作区相关修改、后端启动配置和规则开关快照。
2. 导出75条规则的：规则ID、执行器、执行模式、数据源、正式/临时口径。
3. 记录病例208790、359787和合成验证集当前状态分布、执行耗时、数据库读取次数、LLM调用次数。
4. 固定 Envelope 保存与单一结果 API 的回读样本。
5. 新增只读审计脚本，不写数据库、不改变任务状态。
6. 运行现有 runtime manifest 聚焦测试并记录通过/失败，不在本任务修业务逻辑。

**验证命令：**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_runtime_manifest.py backend/tests/unit/test_luxian_0609_executor_registry.py -q
python backend/scripts/audit_luxian_0609_runtime_manifest.py --format json
```

**验收：** 审计报告能证明75条规则的当前实际路由；不能读取的内容明确标注未知，不做推断。

**停止条件：** 如果当前分支仍有相同文件的未归属修改，先完成变更归属，不进入Task 1。

**Commit:** `文档：冻结LX0609质控引擎收敛基线`

---

### Task 1：建立唯一 Runtime Manifest

**目的：** 让规则路由、数据源依赖和验收元数据只有一个权威定义。

**Files:**

- Modify: `backend/app/services/luxian_0609/rule_contracts.py`
- Modify: `backend/app/services/luxian_0609/native_package.py`
- Modify: `backend/app/services/luxian_0609/executor_registry.py`
- Modify: `backend/app/services/luxian_0609/source_registry.py`
- Test: `backend/tests/unit/test_luxian_0609_rule_contracts.py`
- Test: `backend/tests/unit/test_luxian_0609_runtime_manifest.py`
- Test: `backend/tests/unit/test_luxian_0609_executor_registry.py`
- Create: `backend/tests/unit/test_luxian_0609_runtime_manifest_consistency.py`

**步骤：**

1. 先写失败测试，验证75条规则唯一、67/8分组正确、executor key均已注册。
2. 增加 `RuntimeRuleContract`，先适配现有合同，不改变执行行为。
3. 将 `LEGACY_RULE_MATERIAL_SOURCE_KEYS` 的规则级依赖迁入 Runtime Manifest。
4. 执行器级公共来源可保留，但必须由所辖规则依赖并集校验。
5. 让 `load_luxian_0609_dependency_inventory()` 从 Manifest 生成，不再维护第二份静态映射。
6. 增加一致性测试：规则引用的 source key 必须存在，formal/temporary必须显式。
7. 运行聚焦测试，比较迁移前后生成的执行计划完全相同。

**关键测试：**

```python
def test_runtime_manifest_covers_all_75_rules_once(): ...
def test_runtime_manifest_has_67_formal_and_8_temporary_rules(): ...
def test_every_rule_executor_is_registered(): ...
def test_every_source_key_exists_in_source_registry(): ...
def test_manifest_migration_does_not_change_execution_plan(): ...
```

**验收：** 只改变元数据的权威位置，不改变任何病例结果、模型输入和调用次数。

**停止条件：** 如果必须改变规则医学含义才能完成映射，将该规则标为合同缺口并单独进入Pending，不在本任务猜测。

**Commit:** `重构：建立LX0609唯一规则运行清单`

---

### Task 2：收敛顶层执行路由

**目的：** `execution.py` 只负责编排，不再按规则ID决定业务执行路径。

**Files:**

- Modify: `backend/app/services/luxian_0609/execution.py`
- Modify: `backend/app/services/luxian_0609/executor_registry.py`
- Modify: `backend/app/services/luxian_0609/planner.py`
- Modify: `backend/app/services/luxian_0609/rule_decision_settings.py`
- Test: `backend/tests/unit/test_luxian_0609_mainline_services.py`
- Test: `backend/tests/unit/test_luxian_0609_executor_registry.py`
- Create: `backend/tests/unit/test_luxian_0609_execution_routing.py`

**步骤：**

1. 为当前75条规则生成“选中规则→执行器→决策模式”的黄金快照测试。
2. 由 Runtime Manifest 计算 typed decision rules，移除 `execution.py` 中按功能开关拼接规则ID集合的逻辑。
3. 由 Manifest 的 source依赖并集生成预取列表。
4. 将 `build_luxian_0609_legacy_executor_registry` 重命名为中性名称前，先保证其只是薄适配器。
5. 保留旧feature flag作为整族回滚开关，不再让单条规则同时被多个开关决定。
6. 统一引擎成功时禁止再次运行旧family-by-family路径。
7. 统一引擎技术失败时返回明确技术错误，不静默改走会产生不同医学结论的旧链。
8. 用黄金快照证明收敛前后75条规则派发完全一致。

**关键测试：**

```python
def test_each_selected_rule_is_dispatched_exactly_once(): ...
def test_typed_decision_selection_comes_from_manifest(): ...
def test_source_prefetch_is_manifest_derived(): ...
def test_unified_engine_failure_does_not_rerun_legacy_medical_logic(): ...
```

**验收：** 顶层入口仍输出相同 FamilyExecutionEnvelope，但不再拥有规则级路由知识。

**回滚：** 保留整族执行器开关一个发布周期；发现回归时回滚整族，不恢复单规则多重路由。

**Commit:** `重构：收敛LX0609质控执行路由`

---

### Task 3：统一 Source Observation 与缺口语义

**目的：** 先解决“源库没数据、同步丢失、Bundle丢失、字段为空、关联失败都叫数据不足”的问题。

**Files:**

- Modify: `backend/app/services/luxian_0609/source_evidence_reader.py`
- Modify: `backend/app/services/luxian_0609/source_registry.py`
- Modify: `backend/app/services/luxian_0609/evidence_snapshot.py`
- Modify: `backend/app/services/luxian_0609/evidence_materials.py`
- Modify: `backend/app/services/luxian_0609/fact_schema.py`
- Test: `backend/tests/unit/test_luxian_0609_source_evidence_reader.py`
- Test: `backend/tests/unit/test_luxian_0609_evidence_snapshot.py`
- Create: `backend/tests/unit/test_luxian_0609_source_observation.py`

**最小合同：**

```python
@dataclass(frozen=True)
class SourceObservation:
    source_key: str
    capability: Literal["available", "unavailable"]
    read_state: Literal["ok", "empty", "truncated", "error"]
    row_count: int
    authoritative_time_available: bool | None
    error_code: str | None
```

**步骤：**

1. 写五类来源测试：未接入、读取错误、空记录、字段缺失、截断。
2. 将读取异常与业务空数据分开，禁止宽泛异常吞成空列表。
3. Source Observation进入执行上下文，但不直接进入客户结果。
4. 由规则合同把 Observation映射成客户缺口原因。
5. 保留旧material访问接口一轮，内部转读新Observation，避免同时改所有执行器。
6. 对本机PG的检验、手术、麻醉、输血来源做只读核对。

**客户文案映射：**

| 内部原因                     | 客户说明                                             |
| ---------------------------- | ---------------------------------------------------- |
| `source_unavailable`         | 当前系统尚未接入核对所需的资料                       |
| `source_empty`               | 当前病历中未同步到核对所需的记录                     |
| `source_truncated`           | 当前资料内容不完整，暂时无法完成核对                 |
| `required_field_missing`     | 当前记录缺少完成核对所需的关键字段                   |
| `authoritative_time_missing` | 当前记录缺少可用于计算时限的权威时间                 |
| `association_failed`         | 已找到相关资料，但暂时无法确认它们属于同一次诊疗事件 |

**验收：** 技术错误数量不会因映射而减少；数据不足原因可以被客户理解并能指导补数。

**Commit:** `重构：统一质控资料观测与缺口语义`

---

### Task 4：手术规则族试点收敛

**目的：** 用客户问题最集中、关联最复杂的规则族验证六段架构是否真正降低修复成本。

**范围规则：** `003、024、025、028、029、030、031、032、033、034、035、036、037、038、039、040、064、065、066`。

**Files:**

- Modify: `backend/app/services/luxian_0609/native_surgery_gate_execution.py`
- Modify: `backend/app/services/luxian_0609/native_surgery_document_execution.py`
- Modify: `backend/app/services/luxian_0609/native_surgery_execution.py`
- Modify: `backend/app/services/luxian_0609/native_mdt_execution.py`
- Modify: `backend/app/services/luxian_0609/surgery_classification.py`
- Create: `backend/app/services/luxian_0609/surgery_facts.py`
- Create: `backend/app/services/luxian_0609/surgery_association.py`
- Create: `backend/app/services/luxian_0609/surgery_applicability.py`
- Test: corresponding `backend/tests/unit/test_luxian_0609_native_surgery_*.py`
- Create: `backend/tests/unit/test_luxian_0609_surgery_association.py`
- Create: `backend/tests/unit/test_luxian_0609_surgery_applicability.py`

**统一手术事实：**

```text
procedure_event_id
procedure_code / procedure_name
procedure_kind = surgery | non_surgical_operation | unknown
procedure_level
level_source = hospital_performance | national_catalog | unknown
ordered_at / started_at / ended_at
emergency_flag
surgeon / assistants
anesthesia_type
related_document_refs
```

**步骤：**

1. 先写李孝西无手术病例的门控回归，029/030/032等返回不适用并说明无手术事实。
2. 写冯丽平手术病例的事件关联回归，手术、麻醉、术前小结、安全核查表属于同一次手术。
3. 统一使用院内绩效等级优先、国家目录次之、条件四级按四级的已批准口径。
4. 抽取 `surgery_facts.py`，只负责标准化事实，不产生规则状态。
5. 抽取 `surgery_association.py`，使用事件ID、时间窗、术式和医嘱建立确定性关联。
6. 无法可靠关联时返回 `association_failed`，不得以“目标文书缺失”判不合规。
7. 抽取 `surgery_applicability.py`，统一回答是否手术、是否麻醉、是否四级、是否局麻、是否急诊抢救例外。
8. 逐条让19条规则消费统一事实；不同时修改规则标题和客户口径。
9. 每迁移一条，比较旧/新结果；差异必须分类为旧缺陷修复、批准口径变化或回归。
10. 19条全部通过后，删除本规则族内部已无调用方的legacy fallback。

**验收病例：**

- 无手术、非手术操作、普通手术、四级手术各至少一份。
- 有手术医嘱但取消、已有实际手术但医嘱缺失各至少一份。
- 有麻醉记录、局麻、非局麻、麻醉方式未知各至少一份。
- 文书存在但时间/签名缺失、文书确实不存在各至少一份。

**验收：**

- 19条规则只使用一个手术适用性结论。
- 036、037、038不会再出现“已实施麻醉”和“未实施麻醉”互相矛盾。
- 029、030、032不会把非手术操作当作手术触发。
- 040能说明是否四级、等级来源和多学科讨论事实。
- 规则结果均带正确文书证据，不再以出院记录替代手术证据。

**停止条件：** 如果试点必须引入新的全局事件图、通用规则DSL或重写Envelope才能继续，立即停止并复盘；说明方案范围已失控。

**Commit:** `重构：收敛LX0609手术规则事实与适用性`

---

### Task 5：建立75条规则验收矩阵

**目的：** 避免“单元测试绿色，但客户结果事实不完整”。

**Files:**

- Create: `backend/app/data/luxian_0609_acceptance_matrix.json`
- Create: `backend/scripts/run_luxian_0609_contract_acceptance.py`
- Create: `backend/tests/contract/test_luxian_0609_acceptance_matrix.py`
- Modify: existing v3 synthetic fixture generation scripts only where required
- Create: `docs/reports/luxian-0609-rule-acceptance-status.md`

**每条规则必须记录：**

```json
{
  "rule_id": "LX0609-002",
  "definition_status": "formal",
  "cases": {
    "compliant": "fixture-ref",
    "confirmed_issue": "fixture-ref",
    "not_applicable": "fixture-ref",
    "data_insufficient": "fixture-ref"
  },
  "required_facts": ["admission_time", "first_course_record_time"],
  "required_evidence": ["admission_record", "first_course_record"],
  "expected_executor": "basic_timeliness"
}
```

**步骤：**

1. 从 Runtime Manifest生成75条空矩阵骨架，禁止手工复制规则ID。
2. 将现有0426派生验证集v3和已批准合成病例绑定到矩阵。
3. 每条至少准备确定问题和合规案例；不适用和数据不足只在规则存在这些语义时强制。
4. 对时间规则增加阈值前、阈值点、阈值后边界。
5. 对语义规则固定最小输入和受控输出枚举。
6. 验证状态、事实、证据、执行器、LLM调用上限，不只验证状态。
7. 生成客户可读的覆盖报告，正式67条和临时8条分栏展示。

**验收：** 不再使用“38份病例数量”推断覆盖率；覆盖率只按规则×状态槽位计算。

**Commit:** `测试：建立LX0609七十五条规则验收矩阵`

---

### Task 6：按规则族逐批迁移

**目的：** 复用手术试点模式，避免全面并行重构。

**迁移顺序：**

| 批次 | 规则族         | 重点债务                                       | 进入条件                       |
| ---- | -------------- | ---------------------------------------------- | ------------------------------ |
| 6A   | 基础时限与病程 | 权威时间、医生职级、严重程度时间轴、复制相似度 | 手术试点通过且六段合同无需扩张 |
| 6B   | 检查检验与病理 | 报告聚合、阳性/危急值、报告与病程关联          | 检验Source Observation稳定     |
| 6C   | 会诊           | 申请、会诊、执行记录episode关联                | 020/023关联基线明确            |
| 6D   | 输血           | 输血事件、九项检查、文书和收费关联             | 输血数据源能力已审计           |
| 6E   | 抗菌药与肿瘤   | 药物字典、用药意图、病理/诊断/化疗关联         | 客户字典版本已进入配置         |
| 6F   | 扩展文书规则   | 死亡、出院、转科、交接班、有创操作             | 050–075验收fixture齐备         |

**每个规则族统一执行以下步骤：**

1. 写规则族现状报告：规则列表、数据源、重复读取、现有失败病例。
2. 写关联和适用性失败测试。
3. 抽取最小Fact模块，不修改状态。
4. 抽取Association模块，不引入通用图框架。
5. 抽取Applicability模块，统一门控事实。
6. 逐条迁移Decision，旧路径作为对照而不是并行生产结果。
7. 运行规则族验收矩阵。
8. 使用至少两份真实脱敏病例回读Envelope和API。
9. 删除该规则族无调用方的兼容代码和功能开关。
10. 独立提交，必要时可整族回滚。

**每族完成定义：**

- 规则派发 exactly-once。
- 适用性事实不矛盾。
- 数据不足原因明确。
- 合规和不合规均有简明事实。
- 证据可定位且不串文书。
- 同一事实不重复读取或重复调用LLM。
- 规则族聚焦测试与验收矩阵全部通过。

**Commit示例:** `重构：收敛LX0609检查检验规则关联链路`

---

### Task 7：删除已失效兼容路径

**目的：** 只有在规则族完成迁移后，才兑现技术债减少。

**Files:**

- Modify/Delete only files proven to have zero production callers
- Modify: `backend/app/services/luxian_0609/execution.py`
- Modify: `backend/app/services/luxian_0609/executor_registry.py`
- Modify: `backend/app/services/luxian_0609/native_package.py`
- Modify: `backend/app/services/luxian_0609/rule_decision_settings.py`
- Test: full LX0609 contract and integration suites

**步骤：**

1. 使用CodeGraph列出每个legacy符号的生产调用方、测试调用方和脚本调用方。
2. 迁移只读诊断脚本后，再删除其依赖的旧公共函数。
3. 删除已完成规则族的 `compatibility_rule_ids`。
4. 删除不再控制真实分支的feature flag。
5. 将注册表从迁移期命名改为正式命名。
6. 禁止用保留空函数、永真开关或注释掉代码伪装删除完成。
7. 同步CodeGraph并再次确认生产调用方为零。

**验收：**

- 当前结果只有一条生产执行路径。
- 旧批量任务仍能只读查看，但不会参与当前结果竞争。
- 任何删除都可以对应到已通过的规则族验收报告。

**Commit:** `清理：移除LX0609已失效兼容执行路径`

---

### Task 8：受控性能优化

**目的：** 缩短真实病例验证周期，但不以并发掩盖重复工作。

**Files:**

- Modify: `backend/app/services/luxian_0609/engine.py`
- Modify: `backend/app/services/luxian_0609/execution.py`
- Modify: runtime settings and focused tests
- Test: concurrency, repeatability and fault-injection tests

**步骤：**

1. 记录单病例各规则族耗时、数据库读取、LLM调用和token基线。
2. 先消除同源重复读取和同Fact重复抽取。
3. 将无共享可变状态的确定性执行器并发设置为2。
4. 连续运行同一病例10次，验证结果顺序和Envelope哈希稳定。
5. 注入一个规则族超时，验证其他规则结果保留且错误归属正确。
6. 若数据库连接池、LLM限流和稳定性允许，再评估并发4；不是默认目标。
7. 将并发度设为可配置但有安全上限，禁止客户环境无界配置。

**验收：**

- 结果准确性和稳定性不回归。
- 单病例P95耗时相较基线明显下降；目标至少20%。
- 数据库连接峰值不超过池容量的70%。
- LLM调用数不因并发增加。

**Commit:** `性能：优化LX0609质控规则族受控并发`

---

### Task 9：发布门禁与文档收口

**目的：** 把收敛成果变成后续开发必须遵守的门禁。

**Files:**

- Create: `docs/architecture/luxian-0609-engine-contract.md`
- Create/Modify: CI or local quality scripts, without disabling existing gates
- Modify: rule development template
- Create: final convergence report

**门禁：**

```text
Manifest完整性
  → 路由exactly-once
  → Source Observation语义
  → 规则族合同测试
  → 75条验收矩阵
  → Envelope持久化/回读一致性
  → 真实病例回归
  → 性能与故障注入
```

**验证命令：**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_runtime_manifest_consistency.py -q
python -m pytest backend/tests/contract/test_luxian_0609_acceptance_matrix.py -q
python -m pytest backend/tests/unit/test_luxian_0609_* backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py -q
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
```

完整前端检查只在修改共享DTO、API或最终提交时执行；纯后端规则族的小补丁只运行对应聚焦测试。

**完成定义：**

1. 75条规则路由来自唯一Manifest。
2. 67条正式规则和8条临时规则都有验收状态。
3. 所有生产规则族使用六段内部合同或有明确、限期的未迁移说明。
4. 当前客户链路没有兼容结果参与状态竞争。
5. 真实病例和合成病例均证明Envelope保存/API回读一致。
6. 技术异常、数据不足、不适用的失败语义互不混淆。
7. 后续新增规则有模板、测试槽位和运行清单校验。

**Commit:** `文档：固化LX0609质控引擎开发与发布门禁`

## 6. 执行节奏与检查点

### 6.1 推荐时间盒

| 里程碑 | 内容                      |                  预计投入 | 必须产出                 |
| ------ | ------------------------- | ------------------------: | ------------------------ |
| M0     | Task 0 基线               |                     0.5天 | 可重复审计报告           |
| M1     | Task 1 Manifest           |                     1–2天 | 75条唯一运行清单         |
| M2     | Task 2 路由收敛           |                     1–2天 | 顶层不再硬编码规则族选择 |
| M3     | Task 3 Source Observation |                     1–2天 | 六类缺口语义可区分       |
| M4     | Task 4 手术试点           |                     2–3天 | 19条手术规则族闭环       |
| M5     | Task 5 验收矩阵           | 2–3天，可与规则族填充交错 | 75条验收状态报告         |
| M6     | Task 6 其余规则族         |                 每族1–3天 | 每族独立验收和提交       |
| M7     | Task 7–9                  |                     2–3天 | 删除兼容路径、性能和门禁 |

时间盒不是承诺一次连续做完。M4结束必须做Go/No-Go评审：如果手术规则修复速度、事实一致性和测试可读性没有明显改善，不继续复制该架构到其他规则族。

### 6.2 每日收口原则

- 一天最多同时迁移一个规则族。
- 一个提交只包含一个可回滚业务闭环。
- 不允许“先改完所有文件，最后统一测试”。
- 每个闭环先跑聚焦测试；完整检查只在里程碑结束和提交前执行。
- 每次报告必须给出业务收益：修复了哪些误判、减少了多少重复读取、缩短了多少耗时。

## 7. 回滚策略

1. Runtime Manifest阶段只做等价迁移，可直接回滚提交。
2. 规则族迁移使用整族开关，回滚粒度是规则族，不是单条规则的多路拼接。
3. Canonical Envelope合同保持不变，因此后端内部回滚不要求前端回滚。
4. 新旧执行器对比只存在于测试/只读审计，不同时写入客户结果。
5. 数据库若无必要不新增迁移；如必须新增审计字段，使用向后兼容nullable字段并单独迁移。
6. 任何真实病例回归失败，停止后续规则族迁移，先恢复最近一个已验收里程碑。

## 8. 防止再次过度工程化的红线

出现下列任一情况必须暂停：

- 为迁移一个规则族提出新的通用规则语言或DSL。
- 引入全局事件图、向量检索或第二个事实存储。
- 需要同时修改前端状态映射和后端医学状态才能继续。
- 单个任务修改三个以上规则族。
- 没有真实病例或批准合成病例就宣布规则修复完成。
- 新抽象没有减少重复数据读取、重复门控或重复关联中的任何一项。
- 测试只断言状态，不断言判定事实和证据。
- 为了让测试通过而把异常统一降为数据不足。

## 9. 第一阶段建议执行范围

立即执行到Task 4为止，然后评审，不直接承诺完成所有规则族：

```text
Task 0  冻结基线
Task 1  唯一Runtime Manifest
Task 2  顶层路由收敛
Task 3  Source Observation
Task 4  手术规则族试点
        ↓
Go / No-Go评审
```

Go的证据必须同时包括：

1. 修复一个手术质控点时能够在单一trace中定位到具体阶段。
2. 李孝西非手术病例不再触发手术专属规则。
3. 冯丽平手术文书能够关联到同一次手术。
4. 手术适用性在所有相关规则中一致。
5. 手术规则族的数据库重复读取下降。
6. 没有改变Envelope、API和前端结果合同。

若未满足，保留Manifest和Source Observation的确定收益，回滚手术族内部拆分，不继续扩大架构。

## 10. 最终预期效果

收敛后，处理一个质控点的标准流程应变为：

```text
查看规则Runtime Contract
  → 查看Source Observation
  → 查看Domain Fact
  → 查看Association
  → 查看Applicability
  → 查看Decision
  → 核对保存的Envelope与API
```

开发人员不再需要从顶层执行入口一路猜测功能开关、兼容执行器和结果替换逻辑。规则修复时间的主要部分将重新回到医学口径与真实数据本身，而不是消耗在寻找“代码到底走了哪条路”。
