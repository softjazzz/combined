# LX0609 质控结果链路技术债清理 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用可独立验收的小闭环修复 LX0609 从证据源、规则决策、结果聚合、Envelope 持久化到前端展示的数据链路，使技术故障不再伪装成业务数据缺口、已完成任务必有可验证的权威结果、同一证据目录驱动执行与展示。

**Architecture:** 不重写 49 条规则，也不新建第二套质控引擎。先冻结当前在途工作并建立链路不变量门禁，然后依次修复状态与统计语义、Evidence/Bundle 注册漂移、Envelope 交付一致性和证据可回放，最后收敛聚合器与前端双轨；每批只处理一个业务风险，并用聚焦测试、真实病例回读和性能对比验收。

**Tech Stack:** Python 3、FastAPI、SQLAlchemy、Pytest、Vue 3、TypeScript、Vitest、Ant Design Vue、现有 LX0609 EvidenceSnapshot/RuleDecision/Envelope/Bundle。

---

## 一、已确认基线

### 1.1 当前链路

```text
医院原始表
  -> Source Registry / Evidence Snapshot / Bundle
  -> Family Executor
  -> RuleDecision / Decision Reducer
  -> Result Aggregator
  -> Record Result Envelope
  -> Single-record Read Model / API
  -> 前端结果标准化、分组、证据定位
```

### 1.2 已确认的问题

1. `preane_surveil_record` 已进入 Evidence source registry，但没有进入 Bundle 核心表和手术域，执行与展示材料集合不一致。
2. 麻醉知情同意书缺少可靠物理来源能力；投影别名不能证明真实数据已接入。
3. Evidence snapshot 构建存在宽泛异常吞噬，技术错误可能退化成空材料或数据不足。
4. 主任务完成与 Record Result Envelope 写入不在同一交付状态中；写入失败后仍可能静默回退到 legacy batch。
5. 病例 `2496813` 最近结果为 49 条，但 23 条 `data_gap` 的 `data_gap_details` 全为空。
6. 无可判定规则时部分统计口径返回 `100%` 合规率。
7. 证据详情重新读取当前 Bundle，不是严格的执行时证据版本。
8. 单病历与批量语义规则页面仍有两套结果标准化路径。
9. 后端主链聚焦测试当前为 `155 passed / 15 failed`，尚无完整绿色发布门。

### 1.3 当前工作区约束

- 当前工作区包含大量未提交的跨模块修改，实施前必须先建立独立 worktree 或明确现有修改归属。
- 不允许用 reset、覆盖或批量格式化清理现有在途修改。
- 每个批次只提交白名单文件，禁止顺手修改无关规则族。
- 会诊 020/023、输血新数据源和 49 条规则医学逻辑重写不在本计划默认范围。

## 二、方案选择

### 方案 A：纵向小闭环清债（采用）

每批从后端事实到持久化、API 和页面回读形成一个闭环。优点是业务收益可证明、回滚边界明确；缺点是会暂时保留少量兼容代码。

### 方案 B：一次性重写结果引擎（不采用）

可以得到更整洁的最终架构，但会同时改动 49 条规则、状态语义和持久化，无法区分医学回归与架构回归。

### 方案 C：先修前端展示（不采用）

能快速改善文案，但无法解决错误状态、Envelope 缺失和证据版本漂移，容易把后端错误隐藏得更深。

## 三、统一完成标准

以下条件全部满足后，才可宣告本轮技术债清理完成：

1. 所有选中规则 exactly-once 输出，一个病历、一个规则、一个权威客户结果。
2. `technical_error` 不得映射为 `data_gap`、`uncertain` 或 `compliant`。
3. 每条 `data_gap` 都有受控 `reason_code`、缺失来源和客户可行动说明。
4. 分母为零时合规率为 `null`，页面显示“无可判定规则”，不得显示 `100%`。
5. Snapshot、Bundle 和前端来源标签由同一机器可读来源目录派生或接受一致性编译检查。
6. 任务只有在 Envelope 已成功交付后才能对客户表现为“结果可用”；legacy fallback 必须显式标记。
7. 结果中的证据引用可证明来自执行时同一 snapshot/version。
8. 后端主链 170 项测试全部通过；不得仅删除旧断言来获得绿色。
9. 病例 `2496813` 保持 49 个唯一规则结果，所有缺口均可解释。
10. 聚焦性能相较基线 P95 增幅不超过 10%，且不增加无触发病例的 LLM 调用。

---

### Task 0：冻结实施基线和变更归属

**Files:**

- Create: `docs/reports/2026-07-30-lx0609-tech-debt-baseline.md`
- Reference: `docs/plans/2026-07-29-lx0609-result-chain-stabilization-ledger.md`
- Reference: `docs/plans/2026-07-29-lx0609-single-record-result-vertical-slice.md`

**Step 1: 建立独立实施工作区**

从明确的基线提交创建独立 worktree。若必须继承当前在途修改，先把 LX0609 相关 diff 清单写入基线报告，并由负责人确认归属；不得从当前混合工作区直接开始批量清理。

**Step 2: 记录基线**

报告至少记录：

```text
git commit
相关在途文件
170 项主链测试通过/失败数
病例 2496813 的 49 条状态分布
空 data_gap_details 数
重复 rule_id 数
Envelope 数量
一次执行的耗时和 LLM 调用数
```

**Step 3: 运行基线命令**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_mainline_services.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_record_result_read_model.py backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py -q
npm run test:unit -- --run tests/unit/views/workstation-v4/customer-sample-validation tests/unit/views/workstation-v4/semantic-rules/customerQcDisplayModel.spec.ts tests/unit/views/workstation-v4/semantic-rules/CustomerQcResultDetailCard.spec.ts
```

Expected：后端准确记录现有 15 项失败；前端 27 项通过。该步骤不修测试。

**Step 4: Commit**

```powershell
git add docs/reports/2026-07-30-lx0609-tech-debt-baseline.md
git commit -m "文档：冻结LX0609技术债治理基线"
```

---

### Task 1：统一失败语义和合规率口径

**Files:**

- Modify: `backend/app/services/luxian_0609/execution.py`
- Modify: `backend/app/services/sichuan_qc_service.py`
- Modify: `backend/app/services/luxian_0609/decision_reducer.py`
- Test: `backend/tests/unit/test_luxian_0609_mainline_services.py`
- Test: `backend/tests/unit/test_qc_sichuan_batch_throughput.py`
- Test: `backend/tests/unit/test_luxian_0609_decision_reducer.py`

**Step 1: 写失败测试**

新增以下不变量：

```python
def test_snapshot_internal_failure_becomes_technical_error():
    ...


def test_empty_or_unavailable_business_source_remains_data_gap():
    ...


def test_zero_decidable_rules_has_no_compliance_rate():
    ...
```

断言内部读取异常返回受控 `technical_error`；业务来源为空或能力不可用仍按规则合同映射；分母为零时 `compliance_rate is None`。

**Step 2: 验证 RED**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_decision_reducer.py backend/tests/unit/test_luxian_0609_mainline_services.py backend/tests/unit/test_qc_sichuan_batch_throughput.py -q
```

Expected：新增用例失败，证明当前错误折叠和 `0/0=100%` 行为仍存在。

**Step 3: 最小实现**

- 将 snapshot 构建异常转换为固定错误码，如 `EVIDENCE_SNAPSHOT_BUILD_FAILED`。
- 内部日志保留异常 trace；客户 DTO 不回显 SQL、路径、正文或堆栈。
- 禁止用空列表代替 `ERROR`。
- 将所有合规率计算收口到一个纯函数；分母为零返回 `None`。
- 不修改任何医学规则阈值和适用性判断。

**Step 4: 验证 GREEN**

运行 Step 2 命令。

Expected：新增用例及原有 reducer/统计测试全部通过。

**Step 5: Commit**

```powershell
git add backend/app/services/luxian_0609/execution.py backend/app/services/sichuan_qc_service.py backend/app/services/luxian_0609/decision_reducer.py backend/tests/unit/test_luxian_0609_mainline_services.py backend/tests/unit/test_qc_sichuan_batch_throughput.py backend/tests/unit/test_luxian_0609_decision_reducer.py
git commit -m "修复：统一质控失败语义和合规率口径"
```

---

### Task 2：建立单一来源目录并修复 Bundle 漂移

**Files:**

- Modify: `backend/app/services/luxian_0609/source_registry.py`
- Modify: `backend/app/services/bundles/assembly.py`
- Modify: `backend/app/services/bundles/emr_view.py`
- Modify: `backend/app/services/luxian_0609/source_evidence_reader.py`
- Test: `backend/tests/unit/test_luxian_0609_source_evidence_reader.py`
- Test: `backend/tests/unit/test_luxian_0609_evidence_snapshot.py`
- Create: `backend/tests/unit/test_luxian_0609_source_catalog_consistency.py`

**Step 1: 写来源一致性失败测试**

测试遍历客户可用 source catalog，验证：

- 每个可展示文书源都有 Bundle table/domain/label。
- 每个规则引用的 source key 都存在。
- physical source、projection alias 和 capability-unavailable 三种类型不可混淆。
- `preane_surveil_record`、`postane_surveil_record`、`anesthesia_record` 能通过相同三坐标绑定。

**Step 2: 验证 RED**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_source_catalog_consistency.py backend/tests/unit/test_luxian_0609_source_evidence_reader.py backend/tests/unit/test_luxian_0609_evidence_snapshot.py -q
```

Expected：至少因 `preane_surveil_record` 缺少 Bundle/domain/label 而失败。

**Step 3: 最小实现**

- 在现有 source registry 中补充 `bundle_table`、`domain_key`、`display_label`、`capability_kind` 等静态元数据，或建立一个只读 catalog adapter。
- Bundle 和 EMR view 从目录派生配置；若暂不能直接派生，先用编译测试强制一致。
- 对麻醉知情同意书明确标记：
  - 有物理表：注册精确表和三坐标查询。
  - 没有物理表：保持 `capability_unavailable`，禁止用别名伪装已接入。
- 不在此任务中猜测 consent 表名或新增模糊全文检索。

**Step 4: 真实病例只读验证**

对 `2496813` 重建只读 snapshot/bundle，记录：

```text
anesthesia_record = 2
preane_surveil_record = 0 / complete
postane_surveil_record = 0 / complete
consent source = unavailable 或真实查询结果
```

Expected：Snapshot 与 Bundle 对相同来源给出一致的可用性和计数语义。

**Step 5: Commit**

```powershell
git add backend/app/services/luxian_0609/source_registry.py backend/app/services/bundles/assembly.py backend/app/services/bundles/emr_view.py backend/app/services/luxian_0609/source_evidence_reader.py backend/tests/unit/test_luxian_0609_source_catalog_consistency.py backend/tests/unit/test_luxian_0609_source_evidence_reader.py backend/tests/unit/test_luxian_0609_evidence_snapshot.py
git commit -m "重构：统一质控证据源与Bundle目录"
```

---

### Task 3：使每条数据缺口都可解释

**Files:**

- Modify: `backend/app/services/luxian_0609/customer_renderer.py`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py`
- Modify: `backend/app/services/luxian_0609/rule_contracts.py`
- Test: `backend/tests/unit/test_luxian_0609_customer_renderer.py`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`
- Test: `backend/tests/unit/test_luxian_0609_rule_contracts.py`

**Step 1: 写失败测试**

```python
def test_every_data_gap_has_controlled_details():
    ...


def test_technical_error_is_not_rendered_as_missing_document():
    ...


def test_capability_unavailable_and_record_empty_have_distinct_copy():
    ...
```

最小 `data_gap_details` 契约：

```json
{
  "source_key": "preane_surveil_record",
  "source_label": "术前麻醉访视记录",
  "gap_kind": "record_empty",
  "reason_code": "PREANE_RECORD_MISSING",
  "action": "请确认该病历是否应形成术前麻醉访视记录"
}
```

**Step 2: 最小实现**

- 由 rule contract/source observation 生成缺口说明，不从中文模型分析反推。
- `record_empty`、`capability_unavailable`、`source_error`、`source_truncated` 分别表达。
- `source_error` 必须进入技术错误语义，不允许生成“医院未提供文书”。
- 对历史结果缺少结构化详情时显示“历史结果缺少结构化缺口信息，建议重新质控”，不编造来源。

**Step 3: 运行测试**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_customer_renderer.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_rule_contracts.py -q
```

Expected：全部通过。

**Step 4: 真实病例验收**

重跑或只读重放 `2496813`：

- 49 个唯一规则结果。
- 所有 `data_gap` 的详情非空。
- 麻醉来源缺口文案与真实 source observation 一致。
- 不因补充解释改变原始医学状态。

**Step 5: Commit**

```powershell
git add backend/app/services/luxian_0609/customer_renderer.py backend/app/services/luxian_0609_result_aggregator.py backend/app/services/luxian_0609/rule_contracts.py backend/tests/unit/test_luxian_0609_customer_renderer.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_rule_contracts.py
git commit -m "修复：补齐质控数据缺口的受控解释"
```

---

### Task 4：修复 Envelope 交付一致性

**Files:**

- Modify: `backend/app/services/custom_qc_workspace_service.py`
- Modify: `backend/app/services/luxian_0609/record_result_read_model.py`
- Modify: `backend/alembic/versions/20260729_000023_add_luxian_0609_record_result_envelopes.py`，仅当尚未发布且允许修改；否则新建 migration
- Test: `backend/tests/unit/test_luxian_0609_record_result_read_model.py`
- Test: `backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py`

**Step 1: 写交付状态失败测试**

覆盖：

```python
def test_completed_job_without_envelope_is_not_result_ready():
    ...


def test_envelope_write_failure_is_visible_to_read_model():
    ...


def test_retry_under_same_root_does_not_merge_duplicate_rule_slots():
    ...


def test_legacy_fallback_is_explicitly_marked():
    ...
```

**Step 2: 设计最小交付状态**

优先复用任务元数据，只有无法可靠表达时才新增字段：

```text
result_delivery_state:
  pending
  ready
  failed
  legacy_fallback
```

约束：

- `job.status=completed` 只代表执行完成。
- 客户页面只有在 `result_delivery_state=ready` 时显示“结果已生成”。
- Envelope 写入失败必须可重试，并保留固定错误码。
- 读取端只能选择一个权威 envelope；不得拼接同一 root 下多个重试代次。

**Step 3: 最小实现**

- 将 Envelope 写入和交付状态更新置于可验证事务边界。
- 为权威槽位建立唯一约束或确定性代次选择。
- legacy fallback 暂时保留，但 DTO 必须暴露安全的 `result_source=legacy_fallback` 和重新执行提示。
- 不在本任务删除历史表或重写旧结果。

**Step 4: 运行测试**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_record_result_read_model.py backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py -q
```

Expected：Envelope 成功、失败、重试和旧结果四条路径全部通过。

**Step 5: Commit**

```powershell
git add backend/app/services/custom_qc_workspace_service.py backend/app/services/luxian_0609/record_result_read_model.py backend/tests/unit/test_luxian_0609_record_result_read_model.py backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py backend/alembic/versions
git commit -m "修复：保证质控结果Envelope可验证交付"
```

---

### Task 5：固定执行时证据版本

**Files:**

- Modify: `backend/app/services/luxian_0609/evidence_snapshot.py`
- Modify: `backend/app/services/custom_qc_workspace_service.py`
- Modify: `backend/app/services/luxian_0609/record_result_read_model.py`
- Test: `backend/tests/unit/test_luxian_0609_single_record_evidence_excerpt.py`
- Test: `backend/tests/unit/test_luxian_0609_record_result_read_model.py`

**Step 1: 写失败测试**

验证文书在执行后变化时：

- 结果仍带执行时 `snapshot_hash`、`source_ref` 和 `source_version/hash`。
- 当前文书与执行时版本不一致时，API 明确返回 `evidence_version_changed`。
- 不得把当前正文冒充执行时原文。

**Step 2: 选择最小存储方案**

优先保存：

```text
snapshot_hash
source_ref
source_content_hash
safe_excerpt（仅规则命中的最小必要片段，可选）
```

不默认保存整份病历正文。若安全片段也不允许持久化，则返回版本变化提示，并提供当前文书作为“当前版本”，不得标注为执行证据。

**Step 3: 实现并验证**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_single_record_evidence_excerpt.py backend/tests/unit/test_luxian_0609_record_result_read_model.py -q
```

Expected：原版本、已变化、已删除、无可定位文书四条路径均有明确语义。

**Step 4: Commit**

```powershell
git add backend/app/services/luxian_0609/evidence_snapshot.py backend/app/services/custom_qc_workspace_service.py backend/app/services/luxian_0609/record_result_read_model.py backend/tests/unit/test_luxian_0609_single_record_evidence_excerpt.py backend/tests/unit/test_luxian_0609_record_result_read_model.py
git commit -m "功能：固定质控结果的执行时证据版本"
```

---

### Task 6：收敛聚合器职责并恢复主链全绿

**Files:**

- Modify: `backend/app/services/luxian_0609_result_aggregator.py`
- Modify: `backend/app/services/luxian_0609/decision_reducer.py`
- Modify: `backend/app/services/luxian_0609/customer_renderer.py`
- Test: `backend/tests/unit/test_luxian_0609_mainline_services.py`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`

**Step 1: 对 15 项失败分类**

每项只能归入：

1. 产品缺陷；
2. 新合同已批准、旧测试过期；
3. 测试 fixture 不完整；
4. 行为尚未决策。

把分类、证据和批准结论写入基线报告附录。禁止直接批量改 expected。

**Step 2: 固定职责边界**

- Reducer：只根据正交决策维度生成规范状态。
- Aggregator：只处理 exactly-once、顺序、兼容输入和安全字段汇总。
- Customer renderer：只生成客户文案和显示降级，不改变内部规范状态。
- Legacy adapter：只处理明确标记的历史结果，不参与当前结果竞争。

**Step 3: 修复 fixture 与契约测试**

所有执行上下文 fixture 使用正式构造器，避免 `SimpleNamespace` 漏掉新增字段。对新合同确已批准的旧断言，先补充架构决策说明，再更新测试。

**Step 4: 运行全套主链测试**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_mainline_services.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_record_result_read_model.py backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py -q
```

Expected：170 项全部通过。

**Step 5: Commit**

```powershell
git add backend/app/services/luxian_0609_result_aggregator.py backend/app/services/luxian_0609/decision_reducer.py backend/app/services/luxian_0609/customer_renderer.py backend/tests/unit/test_luxian_0609_mainline_services.py backend/tests/unit/test_luxian_0609_result_aggregator.py docs/reports/2026-07-30-lx0609-tech-debt-baseline.md
git commit -m "重构：收敛质控结果聚合职责并恢复主链门禁"
```

---

### Task 7：统一前端结果标准化与来源标签

**Files:**

- Modify: `src/domain/customer-qc/result-normalizer.ts`
- Modify: `src/views/workstation-v4/customer-sample-validation/single-record-result-model.ts`
- Modify: `src/views/workstation-v4/semantic-rules/customer-qc-display-model.ts`
- Modify: `src/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue`
- Test: `tests/unit/domain/customer-qc/result-normalizer.spec.ts`
- Test: `tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts`
- Test: `tests/unit/views/workstation-v4/semantic-rules/customerQcDisplayModel.spec.ts`

**Step 1: 写跨入口契约测试**

同一 DTO 输入单病历和批量结果模型，断言：

- 状态文案、颜色语义和分组一致。
- `technical_error`、`data_gap`、`uncertain` 都不能进入合规/确定问题。
- `compliance_rate=null` 显示“无可判定规则”。
- 后端来源标签优先，前端未知来源使用安全通用标签。
- `legacy_fallback` 和证据版本变化有明确提示。

**Step 2: 收敛共享纯函数**

共享：

```text
normalizeCanonicalStatus
getStatusPresentation
groupCustomerResult
formatComplianceRate
formatEvidenceSourceLabel
```

页面模型只保留布局所需转换，不再各自维护状态真值表。不得在浏览器中重新判定医学状态。

**Step 3: 运行聚焦测试**

```powershell
npm run test:unit -- --run tests/unit/domain/customer-qc/result-normalizer.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts tests/unit/views/workstation-v4/semantic-rules/customerQcDisplayModel.spec.ts
```

Expected：全部通过。

**Step 4: 浏览器验收**

检查：

1. 49 条结果数与 API 一致。
2. 23 条数据缺口均有原因和行动说明。
3. 技术错误使用独立提示，不伪装成缺文书。
4. 无可判定规则不显示 100%。
5. Evidence 版本变化不会显示成执行时原文。

**Step 5: Commit**

```powershell
git add src/domain/customer-qc/result-normalizer.ts src/views/workstation-v4/customer-sample-validation/single-record-result-model.ts src/views/workstation-v4/semantic-rules/customer-qc-display-model.ts src/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue tests/unit/domain/customer-qc/result-normalizer.spec.ts tests/unit/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.spec.ts tests/unit/views/workstation-v4/semantic-rules/customerQcDisplayModel.spec.ts
git commit -m "重构：统一质控结果前端展示契约"
```

---

### Task 8：真实病例、性能与发布门验收

**Files:**

- Create: `docs/reports/2026-07-30-lx0609-tech-debt-acceptance.md`
- Modify: `backend/scripts/run_luxian_0609_quality_gate.py`
- Test: `backend/tests/unit/test_luxian_0609_quality_gate.py`

**Step 1: 扩展统一质量门**

自动阻断：

```text
selected/output rule set 不一致
重复 rule_id
technical_error 被折叠
data_gap_details 为空
0/0 合规率为 100
Envelope 未 ready 却返回权威结果
Snapshot/Bundle source catalog 漂移
执行证据缺少 snapshot/source version
```

**Step 2: 真实病例验收**

至少包含：

- `2496813`：49 条全量链路。
- 一例无可判定规则病例。
- 一例 Envelope 写入失败的合成故障。
- 一例文书执行后发生版本变化的合成病例。
- 一例来源 capability unavailable。

报告只记录脱敏引用、状态计数、错误码、耗时和调用数，不写患者姓名与正文。

**Step 3: 性能验收**

与 Task 0 基线比较：

- P50/P95 总耗时。
- 数据库查询次数。
- Bundle/Snapshot 构建次数。
- LLM 调用次数及 token。
- Envelope 写入与读取耗时。

停止条件：P95 增幅超过 10%、无触发病例增加 LLM 调用、同一执行构造多份 snapshot。出现任一条件时不得发布。

**Step 4: 完整质量门**

```powershell
python backend/scripts/run_luxian_0609_quality_gate.py
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
python -m pytest backend/tests/unit/test_luxian_0609_mainline_services.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_record_result_read_model.py backend/tests/integration/test_qc_sichuan_workspace_batch_flow.py -q
```

Expected：所有门禁通过；报告包含真实病例、性能和失败语义证据。

**Step 5: Commit**

```powershell
git add backend/scripts/run_luxian_0609_quality_gate.py backend/tests/unit/test_luxian_0609_quality_gate.py docs/reports/2026-07-30-lx0609-tech-debt-acceptance.md
git commit -m "验收：固化LX0609结果链路发布门"
```

## 四、建议排期与决策门

| 批次 | 内容               |   预计 | 发布价值           | 决策门             |
| ---- | ------------------ | -----: | ------------------ | ------------------ |
| 0    | 基线冻结           | 0.5 天 | 防止覆盖在途工作   | 修改归属明确       |
| 1    | 失败语义、合规率   | 1–2 天 | 消除错误业务含义   | 聚焦测试全绿       |
| 2    | Source/Bundle 统一 | 2–3 天 | 执行与展示同源     | 真实病例来源一致   |
| 3    | 数据缺口解释       | 1–2 天 | 客户可理解、可行动 | 空详情归零         |
| 4    | Envelope 交付      | 2–3 天 | 任务完成即结果可用 | 故障与重试测试通过 |
| 5    | 证据版本           | 2–3 天 | 可审计、可追溯     | 版本变化用例通过   |
| 6    | 聚合器收敛         | 2–3 天 | 主链合同稳定       | 170/170            |
| 7    | 前端统一           | 1–2 天 | 多入口一致         | 跨入口契约通过     |
| 8    | 总验收             | 1–2 天 | 可发布证据         | 质量门全绿         |

每完成一个批次都可以独立发布或回滚。若 Task 1–4 尚未完成，不启动大范围聚合器拆分或前端重构。

## 五、明确不做

- 不一次性重写 49 条规则。
- 不新增长期双轨引擎。
- 不依靠关键词或模糊全文检索猜测麻醉同意书来源。
- 不把历史结果不可逆改写为新合同。
- 不用前端文案掩盖后端 `technical_error`。
- 不为追求测试全绿删除仍成立的业务不变量。
- 不在本轮默认启用会诊 shadow 规则或扩大 LLM 使用范围。

## 六、最终退出条件

本计划不是以“代码合并”结束，而是以下业务证据同时成立：

```text
真实病例结果唯一且完整
缺口可解释
技术故障可识别
任务结果可交付
执行证据可回放
Bundle 与 Snapshot 同源
多个前端入口展示一致
主链与发布门全绿
性能和模型成本不劣化
```
