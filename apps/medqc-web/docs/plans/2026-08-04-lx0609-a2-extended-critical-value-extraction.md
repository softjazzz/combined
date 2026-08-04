# LX0609 A2：扩展文书危急值规则受控抽离 Implementation Plan

**Goal:** 在不改变 LX0609-052/053 质控口径、资料来源、结果合同和调用统计的前提下，将危急值判定从巨型 `native_extended_document_execution.py` 抽离为一个职责单一的深模块。

**Architecture:** 保留 `execute_luxian_0609_native_extended_document_rules()` 作为唯一公开入口和薄门面，继续从同一个 `EvidenceSnapshot/MaterialStore` 读取资料。新增的危急值模块只接收由入口投影出的受控输入，负责 PL/PH 触发、处置存在性、6 小时时限和展示事实；它不读取数据库、不接触 MaterialStore、不调用 LLM，也不生成 Canonical 结果。

**Tech Stack:** Python 3.10、pytest、现有 LX0609 `RuleDecision` / Reducer / Canonical Renderer 合同。

---

## 1. 背景与根因

当前文件：`backend/app/services/luxian_0609/native_extended_document_execution.py`

现状：

- 文件约 2,022 行。
- `execute_luxian_0609_native_extended_document_rules()` 约 1,382 行。
- 同一循环中混合 050～075 共 25 条规则，涵盖疑难病例、危急值、抗菌药、死亡、出院、术后、会诊、输血、交接班、转科和有创操作。
- LX0609-052/053 的资料来源和口径已经明确：`labtest_master`、`labtest_item_report`、`crisis_value_record`；`PL/PH` 为危急值标志；052 检查 6 小时内处置；053 检查是否存在处置记录。
- 这两条规则不调用 LLM，现有公开入口测试也较完整，适合作为 `extended_document` 的第一个真实内部 seam。

本次目标不是一次拆完巨型执行器，而是证明：

> 以后修改危急值触发、时限或展示事实，只需要修改一个危急值模块，不再进入 1,382 行主执行函数寻找分支。

---

## 2. 范围

### 2.1 本次包含

- LX0609-052：危急值报告后 6 小时内处置记录。
- LX0609-053：危急值报告后是否存在处置记录。
- 危急值 PL/PH 触发事实。
- 报告时间、处置时间和 6 小时间隔计算。
- 两条规则的 `final_state`、`reason_code` 和 `customer_display_facts`。
- 公开入口、Reducer、Canonical 的行为等价验证。

### 2.2 明确排除

- 不拆 050/051、054～075。
- 不调整危急值口径和 6 小时阈值。
- 不修改源表读取、SourceManifest、读取上限或 MaterialStore。
- 不新增或修改 LLM 调用、Prompt、Token 预算。
- 不修改 Decision 枚举、Canonical Finalizer、Envelope、API 或前端。
- 不建立通用规则平台、基类、注册表或新的依赖注入框架。
- 不顺手修复危急值以外的业务问题。
- 不以主文件必须下降到某个行数作为验收标准。

### 2.3 文件白名单

允许修改：

- Create: `backend/app/services/luxian_0609/extended_document_critical_value.py`
- Modify: `backend/app/services/luxian_0609/native_extended_document_execution.py`
- Modify: `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`

只运行、不修改：

- `backend/tests/unit/test_luxian_0609_customer_renderer.py`
- `backend/tests/unit/test_luxian_0609_result_aggregator.py`
- `backend/tests/unit/test_luxian_0609_executor_registry.py`
- `backend/tests/unit/test_luxian_0609_rule_contracts.py`
- `backend/tests/unit/test_luxian_0609_native_package.py`

任何实现若要求修改白名单以外的生产文件，立即停止 A2 并重新评审，不得自行扩范围。

---

## 3. 目标模块与 Interface

新增：`backend/app/services/luxian_0609/extended_document_critical_value.py`

建议最小 Interface：

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

CRITICAL_VALUE_RULE_IDS = ("LX0609-052", "LX0609-053")
CRITICAL_VALUE_SOURCE_KEYS = (
    "labtest_master",
    "labtest_item_report",
    "crisis_value_record",
)

@dataclass(frozen=True)
class CriticalValueItem:
    item_name: str
    # 与既有 _critical_rows() 相同的五个来源字段，按来源字段固定顺序保留。
    # 入口不得在此之前推导“是否危急值”。
    flag_values: tuple[str, ...]
    # 仅限当前资料行按既有 _material_text() 规则形成的受控文本投影。
    marker_text: str
    # 只用于原有 customer_display_facts 的标志展示，不参与提前门控。
    display_flag: str
    report_time: datetime | None

@dataclass(frozen=True)
class CriticalValueInput:
    lab_item_error: str | None
    crisis_error: str | None
    lab_report_count: int
    lab_detail_count: int
    items: tuple[CriticalValueItem, ...]
    disposition_times: tuple[datetime, ...]

@dataclass(frozen=True)
class CriticalValueOutcome:
    rule_id: str
    final_state: str
    reason_code: str
    display_facts: Mapping[str, object] | None = None

def evaluate_critical_value_rules(
    *,
    rule_ids: tuple[str, ...],
    inputs: CriticalValueInput,
) -> tuple[CriticalValueOutcome, ...]:
    ...
```

Interface 约束：

- 输入必须已经是当前 Evidence Session 内的受控投影。
- 模块不得导入 `native_extended_document_execution.py`。
- 模块不得导入或访问 MaterialStore、数据库、LLM、Reducer、Renderer、Aggregator。
- 输出顺序必须是“按 `CRITICAL_VALUE_RULE_IDS` 固定顺序过滤已选择规则”；
  不能跟随调用方传入顺序，也不能依赖集合顺序。
- 未支持的规则 ID 必须拒绝，不能静默忽略。
- 模块只返回 Outcome；入口继续使用现有 `_decision()` 生成 `RuleDecision`。
- 不增加新的状态或原因码。

职责分配：

```text
MaterialStore
    ↓ 原入口读取并投影时间/字段
CriticalValueInput
    ↓
extended_document_critical_value.py
    ↓
CriticalValueOutcome
    ↓ 原入口转换
RuleDecision + customer_display_facts
    ↓
Reducer → Canonical
```

---

## 4. 行为冻结表

抽离前后必须保持以下行为：

| 场景                           | 052            | 053            | 原因码                                               |
| ------------------------------ | -------------- | -------------- | ---------------------------------------------------- |
| `labtest_item_report` 查询失败 | data_gap       | data_gap       | 原查询错误原因                                       |
| 主表有报告、明细表为空         | data_gap       | data_gap       | required_field_missing                               |
| 无 PL/PH                       | not_applicable | not_applicable | trigger_absent_complete                              |
| 有 PL/PH、处置来源失败         | data_gap       | data_gap       | 原查询错误原因                                       |
| 有 PL/PH、报告时间缺失         | data_gap       | data_gap       | authoritative_time_missing                           |
| 有 PL/PH、2小时后有处置        | compliant      | compliant      | requirement_within_threshold / requirement_satisfied |
| 有 PL/PH、8小时后有处置        | non_compliant  | compliant      | threshold_exceeded / requirement_satisfied           |
| 有 PL/PH、无处置               | non_compliant  | non_compliant  | threshold_exceeded / required_document_missing       |

同时冻结：`critical_item_names`、`critical_flags`、`report_times`、`disposition_times`、052 的 `threshold_hours=6`、052 的 `actual_interval_hours`，以及全部 LLM/Token 统计为 0。

---

## 5. 开发任务

### Task A2.1：锁定公开入口冻结合同

**Files:**

- Modify: `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`

**Step 1：盘点并补齐公开入口冻结场景**

现有测试只覆盖“无处置”“主表有、明细无”和 `abnormal_indicator=PL`，不足以冻结抽离边界。
以公开入口 `execute_luxian_0609_native_extended_document_rules()` 建立不超过 10 个场景，
每个场景均同时选择 052/053；禁止只直接调用即将新增的内部模块作为唯一验收。

必须覆盖：

1. `labtest_item_report` 查询失败；
2. 主表有报告、明细为空；
3. 无 PL/PH；
4. PL/PH 后 2 小时有处置；
5. 恰好 6 小时有处置；
6. 8 小时后才有处置；
7. 无处置；
8. 危急值处置来源失败；
9. 危急值报告时间缺失；
10. 多个危急值中至少一项无处置或超过 6 小时。

第 10 项必须证明既有“每一项危急值都要有后续处置，052 中每项均须在 6 小时内”语义没有变成“任一项满足即可”。

**Step 2：增加双规则代表冻结用例**

代表场景使用：PL 危急值在报告后 2 小时形成处置记录。

断言：

```python
assert result.planned_rule_ids == ("LX0609-052", "LX0609-053")
assert [item.rule_id for item in result.decisions] == [
    "LX0609-052",
    "LX0609-053",
]
assert [item.reason_code for item in result.decisions] == [
    "requirement_within_threshold",
    "requirement_satisfied",
]
assert result.llm_call_count == 0
assert result.prompt_tokens == 0
assert result.completion_tokens == 0
assert result.total_tokens == 0
```

同时断言两条规则的展示事实和证据引用不为空。

**Step 3：增加重复执行一致性用例**

同一 Snapshot/MaterialStore 连续执行两次，比较 `results`、`decisions`、`customer_display_facts` 及 LLM/Token/API time 统计，预期完全相同。

**Step 4：运行基线测试**

Run:

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_native_extended_document_execution.py -q
```

Expected: 全部 PASS。

如果新增的行为冻结用例在现有代码上失败，停止抽离。先确认是测试材料错误还是既有业务缺陷，不得借结构拆分修改口径。

**Step 5：提交绿色测试基线**

```powershell
git add backend/tests/unit/test_luxian_0609_native_extended_document_execution.py
git commit -m "测试：锁定危急值规则公开入口合同"
```

---

### Task A2.2：建立危急值深模块

**Files:**

- Create: `backend/app/services/luxian_0609/extended_document_critical_value.py`
- Modify: `backend/app/services/luxian_0609/native_extended_document_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`

**Step 1：创建受控输入和 Outcome**

按第3节 Interface 创建 `CriticalValueItem`、`CriticalValueInput`、`CriticalValueOutcome` 和 `evaluate_critical_value_rules()`。不要创建基类、抽象工厂或通用执行注册表。

**Step 2：整体移动现有规则判断**

从原执行器移动 PL/PH 过滤、主表有记录但明细为空、报告时间完整性、处置存在性、6 小时间隔，以及 052/053 的状态、原因码和展示事实。原分支中的状态及原因码必须逐字保持。

**Step 3：原入口建立受控投影**

原入口继续负责使用现有 `_parse_datetime()` / `_row_time()` 解析时间，并将每条 `labtest_item_report` 投影为 `CriticalValueItem`：

- `flag_values` 必须按 `result_flag`、`abnormal_flag`、`abnormal_indicator`、`result_status`、`result_hint` 的既有顺序保留原始清洗值；
- `marker_text` 必须仅是当前行按既有 `_material_text()` 的受控文本投影；
- `display_flag` 必须仅按既有展示优先顺序投影；
- `crisis_value_record` 仅投影为处置时间，并传递原有查询错误原因。

入口不得提前计算“是否危急值”，也不得继续保留 PL/PH 判断、6 小时时限或最终状态判断；这些业务判断均由新模块唯一拥有。

**Step 4：原入口一次求值、按规则顺序分派**

在进入主循环前，仅当 selected 包含 052/053 时调用一次：

```python
critical_value_outcomes = {
    item.rule_id: item
    for item in evaluate_critical_value_rules(
        rule_ids=tuple(
            rule_id
            for rule_id in CRITICAL_VALUE_RULE_IDS
            if rule_id in selected
        ),
        inputs=critical_value_inputs,
    )
}
```

主循环中的 052/053 分支只允许读取 Outcome、追加展示事实、调用现有 `_decision()` 并 `continue`。

**Step 5：运行公开入口测试**

Run:

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_native_extended_document_execution.py -q
```

Expected: 与 A2.1 相同测试数量，全部 PASS。

**Step 6：检查依赖方向**

Run:

```powershell
rg -n "MaterialStore|EvidenceSnapshot|LLM|customer_renderer|result_aggregator|native_extended_document_execution" backend/app/services/luxian_0609/extended_document_critical_value.py
```

Expected: 无生产依赖匹配；允许文档字符串出现业务描述，但不得存在反向依赖。

**Step 7：提交结构抽离**

```powershell
git add backend/app/services/luxian_0609/extended_document_critical_value.py backend/app/services/luxian_0609/native_extended_document_execution.py
git commit -m "重构：抽离危急值规则判定模块"
```

---

### Task A2.3：Canonical 与组合回归验收

**Files:**

- Modify only if a missing assertion is proven: `backend/tests/unit/test_luxian_0609_native_extended_document_execution.py`
- Run only: Renderer、Aggregator、Registry、Contract tests

**Step 1：补一个公开链路 Canonical 断言**

复用 A2.1 的冻结场景，将公开入口 Decisions 送入既有 Reducer 和 Aggregator，断言 052/053 Canonical 的 `status`、`reason_code`、`customer_display_facts` 以及客户结论、证据说明和建议不变。不要为此修改 Renderer 或 Aggregator 生产代码。

**Step 2：运行组合回归**

Run:

```powershell
python -m pytest \
  backend/tests/unit/test_luxian_0609_native_extended_document_execution.py \
  backend/tests/unit/test_luxian_0609_customer_renderer.py \
  backend/tests/unit/test_luxian_0609_result_aggregator.py \
  backend/tests/unit/test_luxian_0609_executor_registry.py \
  backend/tests/unit/test_luxian_0609_rule_contracts.py \
  backend/tests/unit/test_luxian_0609_native_package.py \
  -q
```

Expected: 全部 PASS。

**Step 3：运行差异和编码检查**

Run:

```powershell
git diff --check
npm run check:encoding
```

Expected: 无空白错误；新增和修改文件均为 UTF-8 无 BOM、LF。

**Step 4：审查关键 diff**

必须人工确认：

- 原执行器已不存在 PL/PH 判定和 6 小时业务判断。
- 新模块没有数据库、MaterialStore、LLM 或 Canonical 依赖。
- 没有新状态、原因码或客户文案。
- 052/053 仍只读取原三个资料源。
- LLM/Token 统计仍为 0。
- `NativeExtendedDocumentExecutionResult` Interface 未变化。

**Step 5：提交最终验收断言**

仅在 A2.3 确实新增测试断言时提交：

```powershell
git add backend/tests/unit/test_luxian_0609_native_extended_document_execution.py
git commit -m "测试：锁定危急值规则Canonical合同"
```

如没有新增文件变化，不创建空提交。

---

## 6. 验收标准

A2 完成必须同时满足：

1. 公开入口函数名称、参数和返回结构不变。
2. 052/053 的 Native、Decision、Reducer、Canonical 结果完全等价。
3. 状态、原因码、证据引用、客户展示事实和顺序完全一致。
4. 两条规则仍为零 LLM 调用、零 Token。
5. 未增加数据库读取或第二 Evidence 来源。
6. PL/PH、处置存在性和 6 小时判断只有新模块一个所有者。
7. 原执行器只投影输入、调用模块并转换为 Decision。
8. 新模块无反向依赖和循环依赖。
9. 聚焦与组合回归全部通过。
10. 每个提交保持绿色且可独立回滚。

成功的判断不看减少了多少行，而看：

> 将来调整危急值标志、处置时限或展示事实时，只修改 `extended_document_critical_value.py` 和对应公开入口测试，不再进入巨型执行循环修改业务分支。

---

## 7. 停止条件

出现任一情况立即停止：

- 需要修改危急值业务口径才能让测试通过。
- 需要修改 Decision、Reducer、Finalizer、Renderer、Aggregator、Envelope、API 或前端。
- 需要新增 LLM 调用或 Prompt。
- 需要建立第二 Evidence 读取链。
- 需要同时抽离抗菌药、出院、手术或其他规则族。
- 抽离前后任何冻结输入出现状态、原因码、事实、证据或统计差异。
- 新模块必须反向依赖原执行器才能工作。

停止后保留已绿色提交，不通过扩大范围“顺手完成”。

---

## 8. A2 完成后的强制暂停

A2.3 完成后必须暂停并汇报：

- 实际修改文件和提交号。
- 公开入口及组合回归结果。
- 冻结输入两次执行的一致性结果。
- 新旧职责分布。
- 原执行器剩余行数仅作记录，不作为成功指标。
- 是否存在不得不跨越 seam 的业务逻辑。
- 是否建议继续抽离下一规则族。

未经再次确认，不继续抽离抗菌药、死亡/出院、术后、会诊、转科或其他规则族，也不启动 A3。
