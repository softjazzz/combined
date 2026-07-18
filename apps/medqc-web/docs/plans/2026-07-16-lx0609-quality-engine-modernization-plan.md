# LX0609 质控引擎渐进升级 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不一次性重写49个质控点的前提下，把当前“多规则族各自查库、各自判状态”的实现升级为共享不可变证据快照、统一事实契约、统一状态机、可隔离执行和真实 Golden 门禁的 LX0609 独立质控引擎。

**Architecture:** 采用短期旁路、按族直切的渐进替换方式。先让现有49点共享 `EvidenceSnapshot` 与统一执行信封，不改变客户结果；随后把 Python 确定性判断和 LLM 语义事实统一收口到 `RuleDecision`，由唯一 reducer 生成最终状态。旧映射与旧聚合器只保留在冻结的 rollback adapter 中，达到逐族验收门后退出正式主链。

**Tech Stack:** Python 3、FastAPI、SQLAlchemy、Pydantic/settings、pytest、现有 running/final bundle、LX0609 customer rule package、现有 LLM client。

---

## 1. 当前基线与约束

### 1.1 已确认事实

- 当前清单包含49个客户规则，执行分区为8个 `native_sync`、41个 `native_async`，正常开关下兼容执行规则数为0。
- 49点仍按10个 executor batch 调度：基础时限、手术门控、病程质量、检查检验、肿瘤病理、会诊、手术存在性、手术文书、MDT、输血。
- `029/030/032` 已采用 planner/manifest/fact/gate/finding/aggregator 纵向链；其余规则族仍主要使用各自的证据投影、Python/LLM逻辑和结果构造。
- 当前 evidence builder、bundle assembly 和部分规则族会分别读取源数据；source empty、unavailable、error 在部分边界仍会被压缩为空列表。
- 当前正式 Golden 工件没有 accepted 样本；固定10例×49点只能作为范围、形状、性能和回归冒烟，不作为总体准确率证明。

### 1.2 计划原则

1. 不一次性改写49条临床规则。
2. 不建立长期并存的第二套完整 LLM 引擎。
3. 旁路阶段不改变客户状态、不增加无触发病例的模型调用。
4. 确定性规则优先直切；语义规则必须先有适用性门控和人工 Golden。
5. LLM只输出受约束的语义事实或判断要素，不直接拥有最终客户状态。
6. 任何规则无法证明缺陷时不得输出确定 `non_compliant`。
7. 每一阶段独立 commit、独立开关、独立回滚，不跨阶段顺手重构。
8. 每次人工发现可复现问题，必须沉淀为机器契约、Golden 病例或自动门禁；同类问题不得依赖 Agent 下次重新理解。

## 2. 目标组件与核心契约

### 2.1 新的深模块入口

正式目标入口：

```python
async def evaluate_luxian_0609(
    request: Luxian0609EvaluationRequest,
) -> Luxian0609EvaluationReport:
    ...
```

`Luxian0609EvaluationRequest` 只接受客户 `LX0609-*` ID、三坐标、scene、策略版本和 deadline；不得接受旧 `SC/LX/CL/LXE` ID。

### 2.2 统一证据快照

Create: `backend/app/services/luxian_0609/evidence_snapshot.py`

```python
class SourceQueryState(str, Enum):
    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"

class SourceCompleteness(str, Enum):
    COMPLETE = "complete"
    TRUNCATED = "truncated"
    UNPROVEN = "unproven"

@dataclass(frozen=True)
class SourceObservation:
    source_key: str
    query_state: SourceQueryState
    completeness: SourceCompleteness
    record_count: int
    query_version: str
    snapshot_ref: str
    error_code: str = ""

@dataclass(frozen=True)
class Luxian0609EvidenceSnapshot:
    snapshot_hash: str
    visit_ref: str
    observations: tuple[SourceObservation, ...]
    facts: tuple[FactV2, ...]
    document_refs: tuple[str, ...]
```

约束：

- 只允许使用 `institute_id + patient_id + visit_id` 精确绑定；缺少绑定能力时为 `UNAVAILABLE`，禁止退化为仅 `visit_id`。
- 一次评估只构造一次 snapshot；所有规则结果必须引用同一个 `snapshot_hash`。
- raw query error 不回显；错误只通过固定 `error_code` 表达。
- `LIMIT` 截断必须显式为 `TRUNCATED`，不得伪装完整来源。
- snapshot 构造完成后，规则族不得再直接查库。

### 2.3 统一规则决策

Create: `backend/app/services/luxian_0609/decision_model.py`

```python
class ApplicabilityState(str, Enum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"
    ERROR = "error"

class EvidenceState(str, Enum):
    SUFFICIENT = "sufficient"
    DATA_GAP = "data_gap"
    CONFLICT = "conflict"
    TECHNICAL_ERROR = "technical_error"

class QcDirection(str, Enum):
    SATISFIED = "satisfied"
    DEFECT = "defect"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class RuleDecision:
    rule_id: str
    snapshot_hash: str
    applicability: ApplicabilityState
    evidence_state: EvidenceState
    qc_direction: QcDirection
    reason_code: str
    fact_refs: tuple[str, ...]
    evaluator_version: str
    confidence: float | None = None
```

Create: `backend/app/services/luxian_0609/decision_reducer.py`

唯一 reducer 负责把正交维度映射为客户状态。禁止根据 findings/evidence/suggestion 中文文案猜状态。

### 2.4 统一执行信封

Create: `backend/app/services/luxian_0609/engine.py`

```python
@dataclass(frozen=True)
class FamilyExecutionContext:
    selected_rule_ids: tuple[str, ...]
    snapshot: Luxian0609EvidenceSnapshot
    deadline_at: datetime
    package_version: str
    model_id: str

class Luxian0609FamilyExecutor(Protocol):
    executor_key: str

    async def evaluate(
        self,
        context: FamilyExecutionContext,
    ) -> tuple[RuleDecision, ...]:
        ...
```

执行器必须返回所选规则 exactly-once、目录顺序一致的决策；缺失、重复或额外结果统一转换为该规则 `technical_error`，不得静默丢失。

## 3. 阶段总览

| 阶段 | 目标                      |  客户结果变化 | 模型调用变化 | 退出条件                           |
| ---- | ------------------------- | ------------: | -----------: | ---------------------------------- |
| 0    | 冻结基线与质量门          |            否 |           否 | 现状可重放、指标可对账             |
| 1    | EvidenceSnapshot 旁路     |            否 |           否 | 固定病例同一快照、四态正确         |
| 2    | 统一执行信封接管          |      原则上否 |           否 | 规则族隔离、exactly-once、超时可控 |
| 3    | 统一 RuleDecision/reducer | 小范围 canary |           否 | 禁止文本推状态、状态边界通过       |
| 4    | 确定性规则族直切          |            是 |         减少 | Python truth/真实病例通过          |
| 5    | 语义规则族直切            |            是 |         受控 | Golden、稳定性、成本通过           |
| 6    | 全49正式切换与旧链退役    |            是 |     预期下降 | 全门禁通过且回滚演练完成           |

### 3.1 横向主线：自动化基础设施

自动化基础设施不是独立的“最后优化阶段”，而是 Phase 0–6 的共同交付物。任何阶段只有同时交付业务改动和对应自动门禁，才允许退出。目标是让后续 Agent 只凭规则 ID 就能自动获得数据依赖、状态语义、Python/LLM 边界、受影响病例、验收命令和回滚条件，无须由协调者重复口头补充。

知识固化优先级固定为：

1. 可执行类型、机器契约和不可变值对象；
2. contract tests、truth table 和 accepted Golden；
3. CI、发布门和性能/隐私阻断；
4. 脚本、Skill、`AGENTS.md`、review 文档和任务模板。

文档只能解释决策，不能替代可执行约束。能够由测试或 CI 判断的规则，不得只写在提示词或评审说明中。

### 3.2 各阶段必须同步交付的自动化

| 阶段 | 自动化交付                                                                            | 自动阻断条件                                              |
| ---- | ------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| 0    | 49点机器契约、版本化 Golden ledger、统一质量门 CLI                                    | 规则契约缺字段；accepted truth 缺失却声称准确率通过       |
| 1    | source registry 编译检查、快照四态/完整性/身份 contract tests                         | 仅 `visit_id` 查询；来源异常被压为空；同一评估多 snapshot |
| 2    | executor registry 漂移检查、exact selected/output set/order 门禁、family 故障隔离测试 | 缺失/重复/额外结果；跨 family 影响；旧 ID 泄漏            |
| 3    | reducer 全状态真值表、客户 DTO 白名单、隐私 fuzz gate                                 | 中文文案改状态；unknown 折叠；正文/prompt/坐标泄漏        |
| 4    | 受影响规则自动选例、Python 确定性重复运行、零模型断言                                 | truth table 非100%；程序化路径产生模型调用                |
| 5    | LLM schema/stability/cost gate、灰区/硬负例回归                                       | 解析不完整；unknown 被折叠；状态稳定性或成本超预算        |
| 6    | 全49正式入口 E2E、rollback drill、旧链引用扫描                                        | 非49个结果；旧 orchestrator 仍被正式入口调用；回滚失败    |

### 3.3 全49机器可读规则契约

Create: `backend/app/data/luxian_0609_rule_contracts_v1.json`

Test: `backend/tests/unit/test_luxian_0609_rule_contracts.py`

每条规则至少声明：

- `rule_id`、`family_key`、`executor_key`、`contract_version`；
- 权威来源表、三坐标绑定、权威字段、权威时间和 source completeness 要求；
- positive、explicit-negative、unknown/data-gap 事实定义；
- applicability 和 QC truth table、允许终态、固定 reason codes；
- `python`、`regex`、`llm` 各自允许处理的边界；
- prompt/schema/model policy 版本，以及每病例最大调用数、token、P95预算；
- 客户 DTO 白名单、trace 白名单、accepted Golden 分层门槛；
- feature flag、rollback adapter 和 legacy ID 仅兼容声明。

契约编译测试必须验证“客户目录 → 规则契约 → executor registry → focused tests”一致；禁止一个规则无执行器、多个最终执行器、无 unknown/data-gap 语义或修改 prompt 后不升级版本。

### 3.4 单一自动质量门

Create: `backend/scripts/run_luxian_0609_quality_gate.py`

Test: `backend/tests/unit/test_luxian_0609_quality_gate.py`

统一命令：

```powershell
cd backend
python scripts/run_luxian_0609_quality_gate.py --changed
```

`--changed` 根据 git diff 和规则契约计算受影响规则族，并按固定顺序运行：

1. catalog/contract/registry 漂移检查；
2. 受影响族 focused truth table；
3. 受影响 accepted Golden；
4. 全49正式入口 scope/order/exactly-once 冒烟；
5. 客户结果隐私 fuzz；
6. LLM 调用、token、retry、parse error、P50/P95 与基线差异；
7. flag-off rollback 对比。

命令输出一个安全 JSON summary 和人类可读摘要，不写患者正文、三坐标或 raw response。失败必须返回非0退出码，并明确规则 ID、失败门、expected/actual 安全状态和复现命令。

### 3.5 CI 分层与运行成本

Modify: `../../.github/workflows/backend-quality-medqc.yml`

- PR 必跑：契约编译、focused tests、正式入口49点范围/顺序、状态 reducer、隐私 fuzz、零模型断言；目标10分钟内完成。
- 有脱敏 snapshot 的 PR 门：受影响 accepted Golden、确定性稳定性和性能预算。
- 夜间门：需要真实模型的语义 Golden、同输入3次稳定性、token/P95预算、source readiness 覆盖漂移。
- 发布门：全 accepted Golden、全49正式入口、rollback drill、legacy reference scan 全部通过。

模型或真实病例门因外部依赖无法运行时必须明确 `blocked`，不得记为通过；无 accepted Golden 的规则只能保持 shadow。

### 3.6 防止自动化本身失控

- 不为一次性问题创建永久脚本；同类问题至少出现两次，或属于准确性/隐私/状态/范围硬约束，才提升为通用门禁。
- 新脚本必须接入统一质量门或明确替代旧脚本；禁止继续形成互不调用的报告脚本堆。
- 自动化不得生成临床真值；人工双审确认后的状态和安全证据引用才能进入 accepted Golden。
- Agent、Skill 或文档不得绕过契约和 CI；它们只能帮助找到正确入口、解释失败和生成标准任务。
- 性能优化不得降低准确率门槛；模型调用减少只有在 accepted Golden 不退化时才算收益。

## 4. Phase 0：冻结基线和修正测量口径

### Task 0.1：建立49点引擎符合性清单

**Files:**

- Create: `docs/plans/lx0609-engine-conformance-matrix.md`
- Test: `backend/tests/unit/test_luxian_0609_native_package.py`

**Steps:**

1. 写失败测试，断言49条规则均声明 `executor_key`、输入来源、是否程序化、是否允许LLM、结果契约版本。
2. 运行：`python -m pytest tests/unit/test_luxian_0609_native_package.py -q`；预期新增测试先失败。
3. 只补齐机器可读清单字段，不调整任何临床判断。
4. 再运行聚焦测试，预期通过。
5. 提交：`git commit -m "建立泸县0609引擎符合性清单"`。

### Task 0.2：修正 profile 和任务汇总口径

**Files:**

- Modify: `backend/app/services/qc_llm_client.py`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py`
- Test: `backend/tests/unit/test_qc_llm_client.py`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`

**Required behavior:**

- LLM内部 length retry 按两次 transport call 和两段 token 计量。
- 汇总拆分 `confirmed_compliant_count`、`ai_suggested_compliant_count`、`unresolved_count`。
- `confirmed_compliance_rate` 的分子分母只使用确定状态。
- 未知 status 不得默认成为 `non_compliant`，必须 fail closed 为 `technical_error`。

**Verification:**

```powershell
cd backend
python -m pytest tests/unit/test_qc_llm_client.py tests/unit/test_luxian_0609_result_aggregator.py -q
```

### Task 0.3：冻结准确率基线资产

**Files:**

- Modify: `docs/0602/泸县0609真实样本GoldenSet标注表.csv`
- Modify: `docs/0602/luxian_0609_golden_review_queue_merged.csv`
- Create: `docs/0602/泸县0609真实样本GoldenSet验收规则.md`

**Boundary:** 此任务只能录入人工确认状态和安全证据引用，不运行模型生成标签，不提交患者正文。

**Seed gate:**

- 每条规则至少拥有一个可用边界样本；缺少真实适用病例时明确记录 `sample_gap`。
- 确定性规则至少覆盖 compliant、non_compliant、not_applicable、data_gap 和时间/数量边界。
- 语义规则按规则族至少30个已人工判定的 applicable 样本；单规则每个实际输出方向至少5例，否则保持 shadow。

### Task 0.4：建立统一质量门骨架并接入 CI

**Files:**

- Create: `backend/scripts/run_luxian_0609_quality_gate.py`
- Create: `backend/tests/unit/test_luxian_0609_quality_gate.py`
- Modify: `../../.github/workflows/backend-quality-medqc.yml`

**Steps:**

1. 写失败测试，证明未知检查项、检查失败和外部依赖 blocked 都返回非0退出码，且摘要不包含患者标识或正文。
2. 实现只编排现有 catalog、scope、focused pytest 和 privacy 检查的最小 CLI；本阶段不复制临床判断。
3. 运行 `python scripts/run_luxian_0609_quality_gate.py --changed --no-model`，确认输出包含所选规则、执行门和安全计量。
4. 将无模型快速门接入 PR workflow；真实模型和真实 Golden 暂放夜间/手动受控门。
5. 提交：`git commit -m "建立泸县0609统一自动质量门"`。

## 5. Phase 1：EvidenceSnapshot 只读旁路

### Task 1.1：建立 source registry 和快照值对象

**Files:**

- Create: `backend/app/services/luxian_0609/evidence_snapshot.py`
- Create: `backend/app/services/luxian_0609/source_registry.py`
- Test: `backend/tests/unit/test_luxian_0609_evidence_snapshot.py`

**RED matrix:**

- available、empty、unavailable、error；
- complete、truncated、unproven；
- 三坐标缺失；
- 同输入稳定 fingerprint；
- snapshot/version变化导致 fingerprint 变化；
- raw正文、身份证、手机号、SQL、异常文本不得进入安全输出。

### Task 1.2：一次性读取被选规则所需来源

**Files:**

- Create: `backend/app/services/luxian_0609/evidence_snapshot_provider.py`
- Modify: `backend/app/services/luxian_0609/source_evidence_reader.py`
- Test: `backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py`

**Required behavior:**

- 根据所选客户规则并集计算来源集合。
- 每个 source 一次有界参数化查询。
- 禁止 `visit_id` 单字段回退。
- 查询失败保留 `ERROR`，缺表/字段能力为 `UNAVAILABLE`，成功零行为 `EMPTY`。
- 不复用 `SELECT *` fallback。

### Task 1.3：在正式入口挂只读 sidecar

**Files:**

- Modify: `backend/app/services/sichuan_qc_service.py`
- Modify: `backend/app/services/luxian_0609/execution.py`
- Test: `backend/tests/unit/test_luxian_0609_mainline_services.py`

**Acceptance:**

- sidecar关闭时返回对象字节级兼容。
- sidecar开启时客户49点状态、顺序、token、模型调用数不变。
- 固定10例每例只产生一个 snapshot hash；49点全部引用它。
- 不向客户返回 evidence snapshot、正文、三坐标或内部错误。

**Real read-only check:**

```powershell
cd backend
python scripts/run_luxian_0609_fixed10_readonly.py --assert-49
```

若任何客户状态变化，立即关闭 sidecar 并停止下一阶段。

## 6. Phase 2：统一执行信封与故障隔离

### Task 2.1：注册表驱动调度，替换中央 if-chain

**Files:**

- Create: `backend/app/services/luxian_0609/engine.py`
- Create: `backend/app/services/luxian_0609/executor_registry.py`
- Modify: `backend/app/services/luxian_0609/execution.py`
- Test: `backend/tests/unit/test_luxian_0609_engine.py`

**Required behavior:**

- executor registry 从 `executor_key` 解析执行器，不在中央函数增加第11个分支。
- 每个 family 收到相同 snapshot，禁止自行查库。
- 支持 family deadline、cancellation 和异常隔离。
- independent family 可有界并发；存在显式依赖的 family 保持顺序。

### Task 2.2：统一 exactly-once 结果校验

**Files:**

- Create: `backend/app/services/luxian_0609/execution_contract.py`
- Modify: `backend/app/services/luxian_0609/engine.py`
- Test: `backend/tests/unit/test_luxian_0609_execution_contract.py`

**RED cases:** 缺一个结果、重复结果、额外ID、乱序、异常、超时、取消。

**GREEN behavior:** 仅受影响规则生成 `technical_error`；其他规则继续；最终仍返回所选客户ID的精确数量与顺序。

### Task 2.3：适配现有10个执行器，不改临床逻辑

**Files:**

- Modify: `backend/app/services/luxian_0609/native_package.py`
- Modify: `backend/app/services/luxian_0609/native_*execution.py`
- Test: 各现有 `test_luxian_0609_native_*execution.py`

每个 adapter 只做输入/输出契约适配；禁止在本阶段重写正则、prompt或状态规则。

## 7. Phase 3：统一状态机接管

### Task 3.1：实现 RuleDecision 与 reducer

**Files:**

- Create: `backend/app/services/luxian_0609/decision_model.py`
- Create: `backend/app/services/luxian_0609/decision_reducer.py`
- Test: `backend/tests/unit/test_luxian_0609_decision_reducer.py`

**Truth table:**

- applicability not_applicable → `not_applicable`；
- applicable + data_gap → `data_gap`；
- applicable + sufficient + defect → `non_compliant`；
- applicable + sufficient + satisfied → `compliant`；
- conflict/低置信 → `evaluation_unknown`；
- query/parse/timeout error → `technical_error`；
- unavailable/error 永远不得转为确定缺陷；
- 文案内容不得参与状态映射。

### Task 3.2：客户渲染与内部 trace 分离

**Files:**

- Create: `backend/app/services/luxian_0609/customer_renderer.py`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py`
- Test: `backend/tests/unit/test_luxian_0609_customer_renderer.py`

客户 DTO 使用字段白名单；trace 独立保存。删除 native 正式路径中按中文 findings/evidence/suggestion 重新推导状态的能力。

## 8. Phase 4：确定性规则直切顺序

每组都执行：RED truth table → 最小实现 → 聚焦测试 → 真实受影响规则复核 → 固定10例×49冒烟 → commit。

### Wave 4A：基础时限与查房时间

- `001/002/004/005/006`
- `007/008/009`

要求：只使用权威时间字段和明确文书类型；缺权威时间为 `data_gap`，不从正文猜时间，不调用模型。

### Wave 4B：文书存在性与手术事实

- 已有样板：`029/030/032`
- 扩展：`003/033/034/036/038`

要求：performed fact、source readiness、document qualification 分离；EMPTY才允许形成缺失文书，UNAVAILABLE为data_gap，ERROR为technical_error。

### Wave 4C：结构化跨表计算

- `020/021/022/023`
- `028/031/039/040`
- 输血族中可由申请、记录、时间、数值、目的字段确定的子规则。

要求：跨表关联使用同一 snapshot；不得由表存在、泛关键词或费用条目推断临床事件。

> **2026-07-18 例外决策：LX0609-020 暂缓。** 020 继续使用兼容旧链，不作为当前
> Wave 4C 的迁移项，也不得随 021–023 一并声明完成。专用“会诊意见—执行记录”关系合同和
> 单次裁剪 LLM 原型虽通过聚焦测试，但关键真实病例闸门未通过：应为不合规的病例返回不确定，
> 应为合规的病例出现模型合同失败，仅复杂歧义病例符合人工结论。候选未接主链、未提交。
> 后续只有固定20例达到至少 18/20、两条不合规 2/2 命中、三条人工不确定不被强制折叠，
> 并通过新增盲测10例后，才允许重新启动020迁移。

## 9. Phase 5：语义规则接管

### 9.1 LLM统一输出契约

Create: `backend/app/services/luxian_0609/semantic_fact_extractor.py`

```json
{
  "facts": [
    {
      "fact_type": "controlled_code",
      "state": "present|absent|unknown|conflict",
      "source_refs": ["safe-ref"],
      "confidence": 0.0,
      "reason_code": "controlled-code"
    }
  ]
}
```

禁止模型输出客户最终状态。JSON schema 不完整、未知字段、ID缺失、模型异常均为 `evaluation_unknown/technical_error`，不得回退为不合规。

### 9.2 语义迁移顺序

1. `017` 复制病历：Python只筛强阳性/强阴性，灰区每病例最多一次裁剪LLM。
2. `013/019/026/027` 肿瘤病理。
3. `010/011/012/014/015` 检查检验；无显式触发事实时零模型。
4. `024/025` 手术恶性/植入物；没有受控正负事实时保持data_gap，不得靠泛词上线。
5. `035/037` 文书填写规范。
6. `041-049` 输血语义质量；共享一次事实投影，只有确需语义判断的规则调用模型。

### 9.3 模型门禁

- temperature 使用稳定配置；模型、prompt、schema、snapshot hash 全部进入执行指纹。
- 被 gate 排除或 Python 完成的规则调用数必须为0。
- 每病例每语义子族最多1次调用，除非单规则 Golden 明确证明合并调用导致状态漂移。
- 同输入连续3次 exact状态一致率≥98%，parse error=0。
- `ai_suggested_non_compliant` PPV≥95%；确定 `non_compliant` 只能来自完全证据或确定性计算。

## 10. Phase 6：全49切换、回滚演练和旧链退役

### Task 6.1：正式入口切换

**Files:**

- Modify: `backend/app/services/sichuan_qc_service.py`
- Modify: `backend/app/services/luxian_0609/customer_rule_package.py`
- Modify: `backend/app/services/luxian_0609/native_package.py`
- Modify: `backend/app/core/settings.py`
- Test: `backend/tests/unit/test_luxian_0609_mainline_services.py`

正式 LX0609 入口只接受客户ID，直接调用新 engine；旧通用 Sichuan orchestrator 不再参与正常 LX0609 执行。

### Task 6.2：冻结 rollback adapter

**Files:**

- Create: `backend/app/services/luxian_0609/legacy_rollback_adapter.py`
- Modify: `backend/app/services/luxian_0609/native_package.py`
- Test: `backend/tests/unit/test_luxian_0609_legacy_rollback_adapter.py`

将 `compatibility_rule_ids` 从 native registry 必填字段移出。旧映射只存在于 rollback adapter，禁止被新 engine 的事实、planner、结果和客户 metadata 读取。

### Task 6.3：移除旧聚合临床补丁

**Files:**

- Modify: `backend/app/services/luxian_0609_result_aggregator.py`
- Modify: `backend/app/services/luxian_0609_result_schema.py`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`

删除正式 native 路径中的中文文案状态推导和规则专用临床 guard。旧逻辑在 rollback 模式冻结，不再新增补丁。

## 11. 全局验收门

### 11.1 准确性

- 按规则和状态分层统计，禁止只给49点总体准确率。
- 确定 `non_compliant` precision ≥95%。
- 已覆盖缺陷的 recall ≥90%。
- `not_applicable/data_gap` 原因准确率 ≥95%。
- 确定性 truth table 与 accepted Golden 必须100%一致。
- 样本不足的规则只能 shadow，不通过降低阈值追求覆盖。

### 11.2 稳定性

- technical error <1%，且不进入缺陷率和合规分母。
- Python同输入重复5次：状态、reason、fact refs、fingerprint 100%一致。
- LLM同输入重复3次：结构化解析100%，状态一致率≥98%。
- 一个family异常不得影响其他family；所选49点仍须返回49个安全状态。

### 11.3 性能

- 同一病例每个来源最多读取一次。
- 程序化规则模型调用/token为0。
- 相对当前固定集基线，wall p95目标下降50%，总token目标下降40%；准确性不得退化。
- profile 必须能对账 transport calls、retry、prompt/completion/total token、family耗时和unattributed token。

### 11.4 隐私和客户边界

- 客户结果、导出、repr中不得出现完整正文、prompt、raw response、SQL、异常栈、三坐标、旧映射ID。
- trace 只保留安全source/fact refs、版本、reason、耗时和token。
- 敏感扫描命中必须为0。

## 12. 每个规则族的固定验证流程

1. 先更新机器契约，质量门自动计算受影响规则和病例，禁止只靠任务描述限定范围。
2. 聚焦单测：只跑本族 truth table 和 contract tests。
3. 受影响真实病例：人工核对 evidence、applicability、state、reason；确认结果写回版本化 Golden ledger。
4. 固定10例×49：只验证范围、形状、无回归、性能，不冒充准确率。
5. 本族 accepted Golden：自动计算precision/recall/NA-DG原因准确率。
6. 同输入稳定性：Python 5次、LLM 3次；结果由质量门比较预算。
7. privacy/performance gate：客户 DTO、trace、调用次数、token、P95 必须通过。
8. flag-off rollback：与切换前客户结果和调用路径一致。
9. 独立测试Agent运行同一质量门证伪后才允许切下一族；不得使用另一套临时命令替代。

## 13. 停止条件

任一条件满足时停止当前wave，不扩大范围：

- 新增确定性误报或漏报；
- `unavailable/error` 被转换为不合规；
- 无触发病例产生模型调用；
- 规则缺失、重复、顺序变化或旧ID泄漏；
- 同输入稳定性低于门槛；
- wall time/token增加但没有准确率收益；
- 客户结果或trace出现敏感正文；
- 只能通过继续向聚合器增加规则专用补丁才能通过测试。

## 14. 总体完成定义

满足以下条件才称为“LX0609新质控引擎完成”，而不是仅完成原生ID迁移：

1. 49点全部消费同一不可变 EvidenceSnapshot。
2. 所有来源状态和完整性可追溯，规则族不再自行查库。
3. 所有规则都产出统一 RuleDecision，最终客户状态只有 reducer 能生成。
4. LLM不直接决定最终状态，且无触发/程序化路径零模型。
5. 正式入口不经过旧通用规则 orchestrator；旧映射只在冻结 rollback adapter。
6. 每条已发布规则满足其 accepted Golden 门禁；未满足的规则明确保持 shadow。
7. 全49 scope、性能、稳定性、隐私和回滚演练通过。
8. 全49规则拥有机器可读契约，且 catalog、executor、测试、prompt/策略版本无漂移。
9. PR、夜间和发布三层质量门已接入 CI；同类问题再次出现时能自动阻断，而不是依赖人工记忆。
10. 任一 Agent 在没有额外口头背景时，可从规则 ID 得到数据依赖、状态语义、执行边界、受影响 Golden、验证命令和回滚方法。
