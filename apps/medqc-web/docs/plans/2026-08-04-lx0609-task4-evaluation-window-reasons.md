# LX0609 Task 4：评价终点与观察窗口原因收敛 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改变 Task 3 三态策略和检查检验临床判定口径的前提下，准确区分“评价终点缺失”“权威时间冲突”“24小时窗口未成熟”，并向客户返回对应的原因、解释和处理建议。

**Architecture:** `EvidenceSnapshot/MaterialStore` 继续是 Native 规则唯一权威资料链。逐病例快照只产生 Provider 控制策略和受控失败原因；Provider 负责生成唯一的 `evaluation_context.horizon`，检查检验投影不得再直接把原始出院记录解释为评价终点。Native 执行器用一个局部受控枚举计算窗口状态，Decision、Renderer、Finalizer只搬运同一个原因码，不增加第二证据源或 LLM 调用。

**Tech Stack:** Python 3.10、FastAPI、dataclass/Enum、LX0609 EvidenceSnapshot/MaterialStore、RuleDecision、Canonical Result、pytest。

---

## 1. 当前基线与问题证据

### 1.1 Task 3 已冻结的合同

当前逐病例评价策略只有三个合法值：

```text
frozen_task_date
authoritative_discharge
disabled
```

- running → `frozen_task_date`；
- final且resolved → `authoritative_discharge`；
- missing/conflict/unknown → `disabled`；
- 无逐病例快照的升级前排队任务继续走兼容路径；
- `disabled` 时 Provider 不生成 `evaluation_context.horizon`。

Task 4 不得修改这三个值，也不得恢复“final缺出院时间时用当天日期兜底”。

### 1.2 当前原因被压缩

`native_exam_lab_execution.py` 中 `post_horizon_mature()` 当前返回 `bool | None`：

```text
True  → 窗口成熟
False → 窗口未成熟
None  → 时间缺失或时间冲突
```

随后 `False/None` 均被压成：

```text
horizon_not_mature_or_missing
    ↓ _decision_from_outcome()
required_field_missing
```

因此客户无法知道是缺少评价截止时间、时间冲突，还是24小时尚未届满。

### 1.3 必须先修的绕过路径

`exam_lab_fact_extraction.py` 当前同时读取：

- `evaluation_context.horizon`；
- `inpat_registration.discharge_horizon`。

即使 Task 3 策略为 `disabled`、Provider 未生成评价终点，投影仍可能从原始出院来源形成 `precise_horizon`。这会绕过三态策略。

Task 4 必须先锁定：

> LX0609-011/012/014/015 只能消费 Provider 生成的 `evaluation_context.horizon`；原始出院资料只由 Provider 用来构造该受控终点，规则执行器不得再次解释。

## 2. 本轮业务合同

### 2.1 规则范围

本轮只处理共享24小时报告后观察窗口的规则：

```text
LX0609-011
LX0609-012
LX0609-014
LX0609-015
```

LX0609-020/023 的会诊执行窗口留在 Task 5，不在本轮顺手修改。

### 2.2 窗口状态

执行器内部使用唯一局部枚举：

```python
class EvaluationWindowState(str, Enum):
    MATURE = "mature"
    NOT_MATURE = "not_mature"
    MISSING = "missing"
    CONFLICT = "conflict"
```

映射合同：

| 窗口状态                      | Canonical状态   | reason code                    | 客户含义                                   |
| ----------------------------- | --------------- | ------------------------------ | ------------------------------------------ |
| `mature`且未找到规定记录/分析 | `non_compliant` | `requirement_violated`         | 24小时已届满，缺陷成立                     |
| `not_mature`                  | `data_gap`      | `evaluation_window_not_mature` | 截至评价日期尚未满24小时，本次暂不判定缺陷 |
| `missing`                     | `data_gap`      | `authoritative_time_missing`   | 缺少评价截止日期或有效出院时间             |
| `conflict`                    | `data_gap`      | `authoritative_time_conflict`  | 当前住院的入院、出院或评价时间存在冲突     |

已有合规、阳性识别、报告关联和病程语义事实不变。

### 2.3 时间精度

- final：Provider 从当前住院权威出院时间生成 `horizon_datetime`和`horizon_date`；规则优先使用分钟级时间。
- running：冻结任务日期只有日期精度，不得补造00:00或23:59；仍按“严格晚于截止日期才可保守证明成熟”。
- disabled：不生成任何 horizon row；即使原始资料源存在出院时间，规则也不得形成评价终点。
- 兼容旧任务：保持当前行为，但必须通过显式 `policy=None` 分支，不能污染新任务三态合同：
  - 使用有效权威出院时间时，同时生成`horizon_datetime`和`horizon_date`，保持原有分钟级判断能力；
  - 只能回退任务日期时，仅生成`horizon_date`，继续使用日期级保守判断；
  - 必须增加24小时边界前、边界整点和边界后的兼容回归，禁止因为移除原始出院时间旁路而退化为数据不足。

### 2.4 客户解释

必须分别输出：

```text
authoritative_time_missing
发现：暂无法确认报告后24小时观察窗口是否已经结束。
原因：缺少评价截止日期或当前住院的有效出院时间。
建议：请确认住院状态及出院时间已正确同步后重新评估。
```

```text
authoritative_time_conflict
发现：当前住院时间存在冲突，暂无法计算报告后24小时窗口。
原因：入院、出院、报告或评价时间的先后关系不一致。
建议：请核对本次住院及对应检查检验事件的权威时间。
```

```text
evaluation_window_not_mature
发现：截至评价日期，报告出具后尚未满24小时。
原因：规定观察窗口尚未届满，本次暂不判定缺陷。
建议：待24小时窗口届满后重新评估，无需提示客户补录不存在的资料。
```

窗口未成熟不得显示“关键字段缺失”或“请补齐检查检验资料”。

## 3. 文件范围

### 生产代码

- Modify: `backend/app/services/luxian_0609/evaluation_horizon.py`
- Modify: `backend/app/routers/qc_sichuan.py`
- Modify: `backend/app/services/sichuan_qc_service.py`
- Modify: `backend/app/services/luxian_0609/execution.py`
- Modify: `backend/app/services/luxian_0609/evidence_snapshot_provider.py`
- Modify: `backend/app/services/luxian_0609/exam_lab_fact_extraction.py`
- Modify: `backend/app/services/luxian_0609/native_exam_lab_execution.py`
- Modify: `backend/app/services/luxian_0609/decision_model.py`
- Modify: `backend/app/services/luxian_0609/source_gap_contract.py`
- Modify: `backend/app/services/luxian_0609/customer_renderer.py`
- Modify: `backend/app/services/luxian_0609/canonical_result_finalizer.py`

这些文件中，前五个只允许增加受控失败原因的参数传递及 Provider 输出；不得修改 Scene、幂等身份或证据读取算法。

### 测试

- Modify: `backend/tests/unit/test_qc_sichuan_batch_throughput.py`
- Modify: `backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py`
- Modify: `backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py`
- Modify: `backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py`
- Modify: `backend/tests/unit/test_luxian_0609_decision_reducer.py`
- Modify: `backend/tests/unit/test_luxian_0609_customer_renderer.py`
- Modify: `backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py`

### 禁止修改

- Canonical状态终结流程和Envelope/API链路；
- 数据库结构或迁移；
- LLM Prompt、模型配置、调用次数和Token预算；
- 检查/检验阳性识别正则；
- 020～023会诊执行器；
- 手术规则及v3生成器；
- 前端。

若必须修改禁止文件，立即暂停并重新评审。

## 4. TDD执行步骤

### Task 4.1：锁定策略不得被原始出院资料绕过

**Step 1：写失败测试**

在真实 Provider + 检查检验投影链路构造：

```text
evaluation_horizon_policy=disabled
原始当前住院出院时间存在且有效
```

断言：

```python
assert materials.rows("evaluation_context.horizon") == ()
assert projection.precise_horizon is None
assert projection.horizon_date is None
```

Expected RED：当前投影仍可能从`inpat_registration.discharge_horizon`得到`precise_horizon`。

**Step 2：补Provider受控终点精度**

- `authoritative_discharge`生成一条受控 horizon row，同时保存：
  - `horizon_datetime`：权威出院时间，保留分钟/秒精度；
  - `horizon_date`：自然日期；
  - `basis=discharge_date`。
- `policy=None`且采用有效权威出院时间时，也生成相同的`horizon_datetime/horizon_date`；只有回退任务日期时才仅生成`horizon_date`。
- `frozen_task_date`只生成`horizon_date`，不补造`horizon_datetime`。
- `disabled`保持空行。

**Step 3：让投影只读受控终点**

`build_exam_lab_text_projection()`停止把`inpat_registration.discharge_horizon`解释为规则评价终点，只从`evaluation_context.horizon`读取`horizon_datetime/horizon_date`。

**Step 4：转绿并补正向合同**

增加：

- authoritative discharge使用分钟级终点；
- frozen date保持日期级保守判断；
- disabled即使源表有出院时间仍无终点。
- `policy=None`使用有效出院时间时，在24小时边界前1秒、整点和后1秒保持当前分钟级结果；回退任务日期时仍保持日期级保守结果。

Run：

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py -k "horizon or disabled or authoritative_discharge" -q
```

Expected：PASS。

### Task 4.2：把disabled的具体原因带入唯一证据链

**Step 1：写失败测试**

覆盖逐病例快照：

| resolution_status            | Provider策略 | 受控缺口原因                  |
| ---------------------------- | ------------ | ----------------------------- |
| `authoritative_time_missing` | `disabled`   | `authoritative_time_missing`  |
| `time_conflict`              | `disabled`   | `authoritative_time_conflict` |
| `scene_uncertain`            | `disabled`   | `authoritative_time_missing`  |

断言 worker → Service → Execution → Provider 后，`evaluation_context.horizon`的`SourceObservation.reason_code`保留对应原因；不得把完整逐病例快照交给执行器。

**Step 2：实现最小参数合同**

在`evaluation_horizon.py`增加纯函数：

```python
resolve_record_evaluation_horizon_unavailable_reason(snapshot) -> str | None
```

只允许返回：

```text
authoritative_time_missing
authoritative_time_conflict
None
```

沿Task 3现有参数链传递一个字符串原因。Provider验证：

- 只有`policy=disabled`允许非空缺口原因；
- resolved策略不得携带缺口原因；
- 非法值立即`ValueError`；
- 原因写入空的虚拟horizon SourceObservation，不生成临床事实或horizon row。

这属于任务输入控制元数据，经Provider写入EvidenceSnapshot后才允许规则消费，不构成第二证据源。

**Step 3：明确Observation进入Projection的唯一通道**

Native执行器必须从本次`EvidenceSnapshot.observations`中按唯一`source_key=\"evaluation_context.horizon\"`取得`reason_code`，再显式传给投影：

```python
build_exam_lab_text_projection(
    *,
    rows_by_source,
    horizon_unavailable_reason: str | None = None,
)
```

`ExamLabTextProjection`增加只读字段：

```python
horizon_unavailable_reason: str | None = None
```

约束：

- 参数只接受`authoritative_time_missing`、`authoritative_time_conflict`或`None`；
- 有有效horizon row时必须为`None`；
- 没有horizon row时保留Observation原因；
- 不允许用空虚拟row、Bundle字段或原始出院row传递原因；
- 该原因来自同一个EvidenceSnapshot，不构成第二证据源。

同时增加失败测试：Observation已有missing/conflict原因时，投影分别持有对应字段；无Observation原因时保持`None`。

**Step 4：转绿**

Run：

```powershell
python -m pytest backend/tests/unit/test_qc_sichuan_batch_throughput.py backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py -k "evaluation_horizon or unresolved or conflict" -q
```

Expected：PASS。

### Task 4.3：用受控枚举区分四种窗口状态

**Step 1：写表驱动失败测试**

先只用LX0609-012完成一次“Provider → Projection → Window State → RuleDecision”的完整红绿闭环；012转绿后，再将相同表驱动用例参数化复用到LX0609-011/014/015。不得四条规则同时改动后才首次运行测试。

每条规则最终分别覆盖：

1. 精确终点等于24小时截止点 → `MATURE`；
2. 精确终点早1秒 → `NOT_MATURE`；
3. 日期终点等于截止日期 → `NOT_MATURE`；
4. 日期终点严格晚于截止日期 → `MATURE`；
5. 无终点且observation reason为missing → `MISSING`；
6. 无终点且observation reason为conflict → `CONFLICT`；
7. `event_time > precise_horizon` → `CONFLICT`；
8. `event_time.date() > horizon_date` → `CONFLICT`；
9. event与日期级终点为同一自然日、无法知道具体先后 → `NOT_MATURE`；
10. 精确终点恰好等于event后24小时 → `MATURE`。

先断言当前`bool | None`实现无法区分，确认RED。

**Step 2：实现局部枚举和纯函数**

在`native_exam_lab_execution.py`定义局部`EvaluationWindowState`和：

```python
resolve_evaluation_window_state(
    *,
    event_time: datetime,
    projection: ExamLabTextProjection,
) -> EvaluationWindowState
```

判定顺序固定为：

1. Projection携带`authoritative_time_conflict` → `CONFLICT`；
2. Projection携带`authoritative_time_missing`且没有终点 → `MISSING`；
3. 精确终点早于报告时间 → `CONFLICT`；
4. 日期终点严格早于报告日期 → `CONFLICT`；
5. 精确终点达到报告后24小时 → `MATURE`，否则`NOT_MATURE`；
6. 日期终点严格晚于截止日期 → `MATURE`；同日或截止日期当天 → `NOT_MATURE`；
7. 无终点且无更具体原因 → `MISSING`。

不得新建跨规则时间平台或公共状态机。

**Step 3：替换两个合并原因出口**

将`horizon_not_mature_or_missing`替换为三种精确原因：

```text
NOT_MATURE → evaluation_window_not_mature
MISSING    → authoritative_time_missing
CONFLICT   → authoritative_time_conflict
```

MATURE继续沿用当前`exam_lab_text_fact`内部结果，并在Decision层保持既有合规/不合规原因。

**Step 4：Decision保留原因码**

- 在`decision_model.py`的`data_gap`合法原因中加入：
  - `authoritative_time_conflict`；
  - `evaluation_window_not_mature`。
- `_decision_from_outcome()`对三个受控时间原因原样写入RuleDecision；其他检查检验缺口继续使用当前映射，不扩大原因码清理范围。
- LX0609-012完整闭环转绿后，才复用到011/014/015；复用只能增加规则参数，不得复制第二套窗口判断。

Run：

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py backend/tests/unit/test_luxian_0609_decision_reducer.py -q
```

Expected：PASS。

### Task 4.4：锁定客户解释与Canonical元数据

**Step 1：写失败测试**

对四条规则分别验证三种原因：

- Renderer的`findings/evidence/suggestion`；
- Finalizer的`reason_code/data_gap_details/customer_message`；
- `status=result_status=data_gap`；
- `is_compliant is None`。

特别断言：

```python
assert "关键字段缺失" not in rendered_text
assert "请补齐检查检验资料" not in not_mature_text
```

**Step 2：最小文案映射**

- `source_gap_contract.py`增加两个合法原因的受控基础文案；
- `customer_renderer.py`增加`(rule_id, reason_code)`优先映射；时间原因不得再拼接该规则的通用“报告/病程资料缺失”文案；
- `canonical_result_finalizer.py`只登记新原因的通用默认label、missing fields和customer message，并补齐缺失字段；不得按规则ID重新解释原因。
- Renderer负责四条规则的专属客户文案。Finalizer收到已有`customer_message/data_gap_details`时必须原样保留，不得覆盖；不得修改`status/result_status/reason_code/is_compliant`。

**Step 3：转绿**

Run：

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_customer_renderer.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py -q
```

Expected：PASS。

### Task 4.5：锁定020/023非回归

Provider的`evaluation_context.horizon`也被会诊执行规则消费。本轮不修改会诊执行器，但必须增加一条非回归测试：

- 相同会诊资料、相同horizon row，新增Observation reason字段前后，020/023状态和reason code不变；
- `disabled`且无horizon row时，020/023继续返回当前受控数据不足，不得因新原因字段变成确定不合规或技术异常；
- 不修改020/023 Prompt、关联逻辑或调用预算。

Run：

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py -k "020 or 023 or horizon" -q
```

Expected：PASS。

### Task 4.6：组合回归和关键diff审查

只在上述小闭环全部完成后运行一次：

```powershell
python -m pytest backend/tests/unit/test_qc_sample_pools_router.py backend/tests/unit/test_qc_sichuan_batch_throughput.py backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py backend/tests/unit/test_luxian_0609_decision_reducer.py backend/tests/unit/test_luxian_0609_customer_renderer.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py -q
```

随后检查：

```powershell
git diff --check
npm run check:encoding
```

人工审查必须确认：

1. `disabled`没有原始出院时间旁路；
2. 三态策略值未变化；
3. missing/conflict/not_mature原因未被Reducer压回`required_field_missing`；
4. not_mature没有被渲染成资料缺失；
5. `policy=None`使用出院时间时未丢失分钟级精度；
6. 报告时间晚于评价终点被识别为冲突，同日日期精度不足保持未成熟；
7. 012/015阳性识别、正则、LLM调用次数均未变化；
8. 020/023状态、原因码和调用预算未回归；
9. Finalizer只补全缺失字段，没有按规则ID重新解释原因；
10. 未修改Task 5/6执行逻辑。

全部通过后形成一个独立提交：

```powershell
git add backend/app/services/luxian_0609/evaluation_horizon.py backend/app/routers/qc_sichuan.py backend/app/services/sichuan_qc_service.py backend/app/services/luxian_0609/execution.py backend/app/services/luxian_0609/evidence_snapshot_provider.py backend/app/services/luxian_0609/exam_lab_fact_extraction.py backend/app/services/luxian_0609/native_exam_lab_execution.py backend/app/services/luxian_0609/decision_model.py backend/app/services/luxian_0609/source_gap_contract.py backend/app/services/luxian_0609/customer_renderer.py backend/app/services/luxian_0609/canonical_result_finalizer.py backend/tests/unit/test_qc_sichuan_batch_throughput.py backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py backend/tests/unit/test_luxian_0609_decision_reducer.py backend/tests/unit/test_luxian_0609_customer_renderer.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py
git commit -m "修复：区分评价终点缺失与窗口未成熟"
```

## 5. 验收标准

Task 4正式完成必须同时满足：

1. Task 3三态策略及旧任务兼容行为不回归。
2. disabled即使源表存在有效出院时间，Provider和检查检验规则均不生成或推断评价终点。
3. authoritative discharge保留分钟级终点，running冻结日期保持保守日期语义。
4. policy=None采用有效出院时间时保持分钟级精度，24小时边界结果不回归。
5. Observation的missing/conflict原因通过显式参数进入Projection，不使用虚拟row或Bundle旁路。
6. 报告时间晚于终点形成conflict；同日日期精度不足形成not_mature。
7. missing/conflict/not_mature形成三个不同的RuleDecision reason code。
8. 四条检查检验规则对三种原因均返回`data_gap`且`is_compliant=None`。
9. 客户解释准确，不再用“关键字段缺失”覆盖时间原因。
10. 窗口未成熟不会提示客户补资料，只提示待窗口届满后复评。
11. Finalizer只做通用兜底补全，已有客户解释和状态字段原样保留。
12. 020/023现有状态、reason code和调用预算不回归。
13. 窗口成熟时现有合规/不合规逻辑不变。
14. 新增LLM调用为0，Prompt和模型配置diff为0。
15. Canonical、Envelope、API和前端合同不变。

## 6. 停止条件与剩余风险

出现以下任一情况立即暂停：

- 必须让Native执行器直接读取Bundle逐病例快照；
- 必须新增第二套评价时间资料源；
- 需要修改020/023会诊规则才能让本Task测试通过；
- reason code调整导致其他规则状态变化；
- 精确出院时间无法通过现有受控horizon source传递；
- 聚焦回归出现非既有失败且不能由本Task直接解释。

Task 4完成后必须暂停并汇报，不自动进入Task 5。历史主链5项既有失败继续单独记录，不得混入本Task回归结论。
