# LX0609 Canonical 结果状态收敛 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 LX0609 客户最终状态只在 Canonical 结果生成时确定一次，之后聚合、保存、单一结果接口和前端均不得改写 `status/reason_code`。

**Architecture:** 保留现有“解释不足时不把缺陷作为确定问题展示”的客户安全口径，不新增临床状态与展示状态双轨模型。`ReducedRuleDecision` 继续只负责结构化临床决策归约；新增一个小而深的 Canonical 结果终结模块，在受控事实和可定位证据齐备后一次生成最终客户结果。聚合器负责装配 Canonical 结果草稿并调用唯一终结器，但不再内置状态降级策略；终结器返回后只允许收集和搬运。

**Tech Stack:** Python 3、pytest、现有 LX0609 `RuleDecision/ReducedRuleDecision`、PostgreSQL JSON Envelope、Vue 3/TypeScript 固定读模型。

---

## 一、范围与产品合同

### 本阶段固定合同

1. `ReducedRuleDecision` 是临床规则决策，不等同于已持久化的 Canonical 客户结果。
2. Canonical 客户结果由以下输入一次性生成：
   - 已归约决策或 Native 结果草稿；
   - `customer_display_facts`；
   - `criterion_results`；
   - 可定位证据；
   - 受控规则目录身份。
3. `non_compliant` 只有在至少具备以下一项时才能作为确定问题交付：
   - 受控 `criterion_results`；
   - 受控 `customer_display_facts`；
   - 同时具有原文摘录和来源定位的证据。
4. 不满足第3条时，保持当前客户口径：
   - `status/result_status = uncertain`；
   - `reason_code = customer_explanation_incomplete`；
   - `is_compliant = None`。
5. 上述降级只能发生在 Canonical 终结模块内部一次。终结完成后，聚合器剩余流程、Envelope 写入、数据库读取、单一结果接口和前端不得再次改变状态。
6. 本阶段不新增 `decision_status/display_status` 双状态字段，不改变前端标签和现有客户统计口径。
7. Canonical 客户结果合法状态以 `luxian_0609_result_schema.py` 导出的唯一公共常量为准，终结器、聚合器和 Schema 不得各自复制状态集合。

### 明确排除

- 不拆分其他巨型执行器。
- 不清理33个运行开关。
- 不迁移规则族。
- 不改变任何具体质控规则的临床判定。
- 不调整数据库表结构。
- 不重新设计整个结果 Schema。
- 不顺手修改兼容链的业务保护规则。

## 二、目标数据链

```text
RuleDecision / Native draft
        ↓
ReducedRuleDecision + 受控展示事实 + 定位证据
        ↓
finalize_luxian_0609_canonical_result（唯一状态终结点）
        ↓
Canonical result item
        ↓ 只搬运
聚合结果 → Envelope保存 → 单一结果API → 前端渲染
```

## 三、验收指标

1. 当前已有两项安全行为保持不变：
   - 缺解释的不合规结果仍交付为 `uncertain`；
   - 有受控事实或定位证据的不合规结果仍为 `non_compliant`。
2. `luxian_0609_result_aggregator.py` 中删除 `_guard_customer_explanation_result` 实现，且聚合器不再直接执行该状态降级。
3. Canonical 终结函数返回后，不再存在 `status/result_status/reason_code/is_compliant` 写操作。
4. Envelope 数据库 JSON 中的每个 item 与终结函数输出在上述四个字段上完全一致。
5. 单一结果接口返回的 item 与数据库 Envelope 完全一致，不重投影、不读取 Bundle。
6. 前端继续只按服务端 `status` 分组，不推导或修正状态。
7. 聚焦后端测试、Envelope测试和前端固定读模型测试全部通过。
8. 选择至少一条“有解释的不合规”和一条“缺解释的降级结果”完成端到端回归，改造前后客户可见状态数量一致。

---

### Task 1：测试驱动建立唯一 Canonical 结果终结模块

**Files:**

- Modify: `backend/app/services/luxian_0609_result_schema.py:28-82`
- Create: `backend/app/services/luxian_0609/canonical_result_finalizer.py`
- Create: `backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py`

**Step 1: 将9种合法状态收敛为唯一公共常量**

在现有结果 Schema 模块中导出：

```python
CANONICAL_RESULT_STATUSES = (
    "non_compliant",
    "ai_suggested_non_compliant",
    "compliant",
    "ai_suggested_compliant",
    "not_applicable",
    "data_gap",
    "uncertain",
    "not_executed",
    "technical_error",
)
```

`_normalize_status`必须引用该常量。后续聚合器和终结器都从这里导入，禁止复制第三份枚举。

**Step 2: 写终结模块的失败测试**

覆盖以下真值表：

```python
@pytest.mark.parametrize(
    ("status", "has_facts", "has_criteria", "has_evidence", "expected"),
    [
        ("non_compliant", False, False, False, "uncertain"),
        ("non_compliant", True, False, False, "non_compliant"),
        ("non_compliant", False, True, False, "non_compliant"),
        ("non_compliant", False, False, True, "non_compliant"),
        ("compliant", False, False, False, "compliant"),
        ("data_gap", False, False, False, "data_gap"),
    ],
)
def test_finalizer_owns_customer_explanation_safety_policy(...):
    ...
```

额外覆盖：

- 全部9种合法状态均被接受；未知状态抛出`ValueError`。
- 除`non_compliant`解释不足外，其他状态和`reason_code`原样保留。
- 调用终结器两次结果相同，保证幂等。
- 输出始终满足`status == result_status`。
- `is_compliant`与最终状态一致：`compliant/not_applicable=True`，`non_compliant=False`，其余状态为`None`。
- `customer_evidence`只有定位信息、没有原文摘录时不算充分解释。
- 嵌套事实、证据和子判定内容不被修改。
- 降级必须同时更新`status/result_status/reason_code/is_compliant`。
- 输入字典及嵌套结构均不被原地修改。

**Step 3: 运行测试并确认失败**

Run:

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py -q
```

Expected: FAIL，原因是终结模块尚不存在。

**Step 4: 实现最小接口**

只暴露一个接口：

```python
def finalize_luxian_0609_canonical_result(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """生成最终客户结果；返回后状态字段不可再被下游改写。"""
```

实现要求：

- 从输入复制新字典，不原地修改。
- 仅当`status == non_compliant`时检查解释充分性。
- 解释充分性规则与当前 `_guard_customer_explanation_result` 完全一致。
- 保留规则040的专属客户文案。
- 从`luxian_0609_result_schema.py`导入唯一合法状态常量。
- 保证幂等：已经降级的结果再次调用不得改变字段。
- 使用深复制或等价方式保证嵌套事实、证据和子判定不被修改。
- 不读取数据库、Bundle、Settings或LLM。
- 不引入新的类、注册表或配置开关。

**Step 5: 运行终结模块测试**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py -q
```

Expected: PASS。

**Step 6: 提交绿色闭环**

```powershell
git add backend/app/services/luxian_0609_result_schema.py backend/app/services/luxian_0609/canonical_result_finalizer.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py
git commit -m "refactor: 建立LX0609结果唯一终结接口"
```

不得单独提交失败测试；该提交必须保持基线绿色并可独立回滚。

---

### Task 2：迁移全部四条结果出口

**Files:**

- Modify: `backend/app/services/luxian_0609_result_aggregator.py:39-49`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py:3875-3927`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py:4215-4242`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py:4288-4323`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py:4324-4365`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py:4380-4442`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`

**Step 1: 删除聚合器内重复的合法状态集合**

聚合器从`luxian_0609_result_schema.py`导入`CANONICAL_RESULT_STATUSES`，现有`_status`和汇总逻辑继续引用它。

**Step 2: 在四个出口调用同一终结接口**

必须迁移：

1. Canonical `ReducedRuleDecision`路径；
2. `lx0609_native`路径；
3. 直接兼容结果路径；
4. 映射/fallback路径。

调用时机必须在以下内容全部补齐之后：

- Schema；
- `criterion_results`；
- `customer_display_facts`；
- `customer_evidence/evidence_items`；
- 受控客户文案。

兼容路径原有的`_guard_customer_display_result`必须继续保留，并且位于终结器之前。本阶段不改变兼容链业务重判行为。

**Step 3: 删除聚合器本地解释保护函数**

删除：

```python
def _guard_customer_explanation_result(...):
    ...
```

聚合器只能调用终结接口，不再拥有解释充分性真值表和降级文案。

**Step 4: 为四个分支增加一致性断言**

分别覆盖：

- `ReducedRuleDecision`路径；
- `metadata.execution_source == lx0609_native`路径。
- 直接兼容结果路径；
- 映射/fallback路径。

四条路径输入相同解释条件时，最终状态和原因码必须一致。并保留以下已有行为测试：

- `test_reduced_non_compliant_without_explanation_facts_is_not_exposed_as_customer_defect`
- `test_reduced_non_compliant_with_controlled_facts_keeps_customer_defect_status`
- `test_empty_reduced_tuple_preserves_legacy_native_branch`

**Step 5: 运行聚焦回归**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py -q
```

Expected: PASS；既有状态数量和文案合同不变。

**Step 6: 提交迁移**

```powershell
git add backend/app/services/luxian_0609_result_aggregator.py backend/app/services/luxian_0609_result_schema.py backend/app/services/luxian_0609/canonical_result_finalizer.py backend/tests/unit/test_luxian_0609_result_aggregator.py
git commit -m "refactor: 收敛LX0609最终状态所有权"
```

---

### Task 3：锁定保存与单一结果接口的原样传递

**Files:**

- Modify: `backend/tests/unit/test_luxian_0609_canonical_result_delivery.py`
- Modify: `backend/tests/unit/test_custom_qc_workspace_service_records.py`
- Only if required by failing tests: `backend/app/services/custom_qc_workspace_service.py:4251-4427`

**Step 1: 增强Envelope写入测试**

输入终结后的结果：

```python
{
    "rule_id": "LX0609-029",
    "status": "uncertain",
    "result_status": "uncertain",
    "reason_code": "customer_explanation_incomplete",
    "is_compliant": None,
}
```

断言数据库`envelope_json.items[0]`四个字段逐字一致。

**Step 2: 增强读取测试**

断言单一结果接口：

- 不调用客户安全投影；
- 不读取Bundle；
- 不根据证据数量重算状态；
- 返回数据库Envelope中的原值。

**Step 3: 运行交付链测试**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_canonical_result_delivery.py backend/tests/unit/test_custom_qc_workspace_service_records.py -q
```

Expected: PASS。

**Step 4: 仅在测试证明有改写时修改生产代码**

若当前保存/读取已经原样传递，不得为了“统一风格”修改`custom_qc_workspace_service.py`。

**Step 5: 提交交付不变量**

```powershell
git add backend/tests/unit/test_luxian_0609_canonical_result_delivery.py backend/tests/unit/test_custom_qc_workspace_service_records.py
git commit -m "test: 锁定Canonical结果直通交付"
```

如果失败测试证明必须修改`custom_qc_workspace_service.py`，则提交命令必须同时包含：

```powershell
git add backend/app/services/custom_qc_workspace_service.py backend/tests/unit/test_luxian_0609_canonical_result_delivery.py backend/tests/unit/test_custom_qc_workspace_service_records.py
git commit -m "fix: 保证Canonical结果原样写入和读取"
```

---

### Task 4：锁定前端只渲染合同

**Files:**

- Modify: `tests/unit/views/workstation-v4/customer-sample-validation/single-record-result-model.spec.ts`
- Only if required by failing tests: `src/views/workstation-v4/customer-sample-validation/single-record-result-model.ts`

**Step 1: 增加固定读模型测试**

分别输入：

- `non_compliant + customer_explanation_incomplete`；
- `uncertain + customer_explanation_incomplete`。

断言前端：

- 保留后端`status`；
- 不根据`reason_code`改状态；
- 不根据证据为空改状态；
- 只映射中文标签、色调和排序。

**Step 2: 运行前端聚焦测试**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/customer-sample-validation/single-record-result-model.spec.ts
```

Expected: PASS。

**Step 3: 无失败则不改前端生产代码**

当前前端注释已经声明“不修改服务端最终状态”。如果测试直接通过，只提交测试，不改实现。

**Step 4: 提交前端合同**

```powershell
git add tests/unit/views/workstation-v4/customer-sample-validation/single-record-result-model.spec.ts
git commit -m "test: 锁定质控结果前端只渲染合同"
```

---

### Task 5：真实链路回归与收口审查

**Files:**

- No required production changes
- Update only if documentation is stale: `CONTEXT.md`

**Step 1: 运行完整聚焦测试组**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_canonical_result_delivery.py backend/tests/unit/test_custom_qc_workspace_service_records.py -q
```

Expected: PASS。

**Step 2: 运行前端结果链测试**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/customer-sample-validation/single-record-result-model.spec.ts
```

Expected: PASS。

**Step 3: 对一份真实或现有冻结病例重跑结果**

必须至少包含：

- 一条有解释事实的`non_compliant`；
- 一条缺解释而降级的`uncertain`；
- 一条`compliant`；
- 一条`data_gap`。

记录改造前后：规则ID、最终状态、原因码、证据数量。预期客户可见结果完全一致。

**Step 4: 核对数据库与API**

对同一规则逐字段比较：

```text
finalizer output
  == database envelope item
  == single-record result API item
```

至少核对`rule_id/status/reason_code/conclusion/evidence`。

**Step 5: 执行一次阶段质量检查**

只在整个闭环结束时执行，不在每个小补丁后重复：

```powershell
npm run check:encoding
npm run lint
```

如本阶段没有修改共享TypeScript类型，无需把完整`type-check`作为每个提交的阻塞项；准备正式发布时再运行完整门禁。

**Step 6: 最终审查**

使用以下静态检查确认状态所有权已经集中：

```powershell
rg -n '"status"\s*:|"result_status"\s*:|"reason_code"\s*:' backend/app/services/luxian_0609_result_aggregator.py backend/app/services/luxian_0609/canonical_result_finalizer.py
```

人工确认：聚合器只能构造草稿或调用终结接口；终结接口返回后没有状态改写。

**Step 7: 提交文档和最终修正**

```powershell
git add CONTEXT.md docs/plans/2026-08-03-lx0609-canonical-result-state-convergence.md
git commit -m "docs: 明确LX0609最终状态所有权"
```

---

## 四、停止条件与剩余风险

出现以下任一情况立即停止扩范围：

1. 必须修改具体规则的临床判定才能完成迁移。
2. 必须新增数据库字段或双状态模型。
3. 真实病例状态数量发生变化且不能由既有安全合同解释。
4. 需要同时重构聚合器、Reducer和所有Native执行器。
5. 兼容链业务保护逻辑被意外带入本阶段。

本阶段完成后仍保留的技术债：

- 兼容路径中的 `_guard_customer_display_result`；
- 33个运行开关；
- `prepare_luxian_0609_execution`超大编排函数；
- 多个规则族巨型执行器；
- 巨型测试文件。

这些债务必须作为后续独立任务处理，不能并入本闭环。

---

## 五、执行记录

- Task 1：`3dab4b87c`，建立唯一状态常量和 Canonical 终结器；17项合同测试通过。
- Task 2：`7c9eb93a8`，当时识别的四条结果出口统一进入终结器；122项聚焦测试通过。
- Task 3：`a187786b1`，锁定Envelope/API直通并保留`is_compliant=None`；15项测试通过。
- Task 4：`5180fef73`，锁定前端只渲染服务端状态；4项测试通过。
- Task 5 初次审查后发现 Trigger Gate 第五条出口、空壳事实判定和批任务交付装配仍有缺口，
  不再沿用“四条出口已经完全收口”的结论。
- `4ec02589b`：第五条 Trigger Gate 出口进入终结器；空字符串和嵌套空容器不再作为充分解释，
  同时保留 `False` 和 `0` 这类有效受控事实。
- `df5ca1691`：批任务装配保留 `result_status`，并原样保留 Canonical `is_compliant=None`。
- `36ace2345`：Canonical 客户结果绕开旧 LX0609-016 批任务保护，禁止其在终结后把合规重判为数据不足。
- 最终后端聚焦回归177项通过；前端结果模型4项通过；`npm run check:encoding`与
  `npm run lint`通过。
- 冻结病例任务 `4abe6e48-e297-4a31-9908-c865fe77a9cf` 完成75条结果：
  `non_compliant=6`、`uncertain=2`、`compliant=17`、`data_gap=38`、`not_applicable=12`。
  已确认终结器四字段幂等、Canonical交付投影与数据库Envelope完全一致、Envelope与
  单一结果API完全一致，并逐字段核对 `rule_id/status/result_status/reason_code/is_compliant/conclusion/evidence`。
