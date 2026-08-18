# LX0609 Task 3：兼容 fallback 文书身份去重 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复兼容 fallback 合并时“同一源表最多保留一份文书”的缺陷，确保不同文书全部保留、真正重复文书只保留一份，并且不改变 MaterialStore 主链、规则判定和结果合同。

**Architecture:** 保持 `EvidenceSnapshot/MaterialStore` 为 LX0609 Native 规则的唯一权威资料源，只修改 `sample_programmatic_evidence.py` 中的兼容输入合并。以现有文书标识和内容字段计算一个局部、确定性的文书身份；身份相同则选择信息更完整的副本，身份不同则按原输入顺序保留。不得引入新的数据库字段、通用证据框架或第二套资料链。

**Tech Stack:** Python 3.11、pytest、SQLAlchemy（现有只读 fallback 查询，不改变查询合同）

---

## 1. 问题证据与根因

当前实现位于：

- `backend/app/services/sample_programmatic_evidence.py:162-184`
- 调用入口：`backend/app/services/sample_programmatic_evidence.py:457-490`

`_merge_fallback_items()` 先按 `source_table` 记录已有文书的最大文本长度，再决定是否加入 fallback 文书。其效果是：

1. 某张表已有一份正文超过 80 字的文书后，该表其余 fallback 文书全部被丢弃。
2. 某张表已有一份短文书时，只可能再追加一份更长文书，仍不能表达“一张表有多份不同文书”。
3. “文书是否重复”被错误等同于“是否来自同一张表”。

典型受影响资料包括日常病程、上级查房、会诊、手术核查和麻醉记录等一表多文书场景。

本缺陷的影响边界必须描述准确：

> 它影响 `sample_programmatic_evidence` 的兼容 fallback/Adapter 输入，不代表 MaterialStore 主链只读取一份文书，也不授权修改 Native executor、SourceEvidenceReader 或 Canonical Envelope。

## 2. 本轮范围

### 允许修改

- `backend/app/services/sample_programmatic_evidence.py`
- `backend/tests/unit/test_sample_programmatic_evidence.py`

### 明确不修改

- `backend/app/services/luxian_0609/evidence_material.py`
- `backend/app/services/luxian_0609/source_evidence_reader.py`
- 任何 `native_*_execution.py`
- Bundle/Scene 选择逻辑
- `_FALLBACK_DOC_FETCH_LIMITS` 和 SQL 查询上限
- LLM 调用、预算和提示词
- Canonical Result、Envelope、数据库和 API
- 前端展示

如果实现需要修改第三个生产文件，立即停止并重新评审，不扩大 Task 3。

## 3. 文书身份合同

### 3.1 身份优先级

在同一 `source_table` 内按以下顺序识别同一文书：

1. 稳定标识：优先使用现有非空 `document_id`；仅当现有输入明确带有 `record_id` 或 `id` 时才作为备选，不新增数据库字段。
2. 无稳定标识时，使用保守复合身份：
   - `source_table`
   - 规范化后的 `record_time/display_time/submit_datetime/last_modified_time/update_time` 首个非空值
   - `document_type`
   - 规范化正文的 SHA-256 摘要

正文规范化仅允许：去除首尾空白、合并连续空白。不得做医学术语替换、模糊相似度或 LLM 去重。

### 3.2 安全原则

- 同表不同 `document_id`：必须保留。
- 同表同 `document_id`：合并为一份。
- 无 ID、时间或正文任一关键成分不同：保守地视为不同文书并保留。
- 无 ID 且复合身份完全相同：视为重复副本。
- 无法可靠判断时宁可保留重复项，也不能误删真实文书。

### 3.3 重复副本的取舍

身份相同时选择 `_item_text()` 更完整的副本作为主体，并用另一副本中的非空定位字段补齐空值。不得把两个正文串接成一份新正文，也不得更改医学内容。

需保留的现有行为：

- 返回顺序以首次出现的位置为准。
- 单文书场景输出不变。
- fallback 元信息（入院/出院时间）处理不变。
- `primary_document_text` 中同一文书只渲染一次。

---

## 4. TDD 执行步骤

### Task 3.1：锁定“同表不同文书必须全部保留”

**Files:**

- Test: `backend/tests/unit/test_sample_programmatic_evidence.py`

**Step 1: 写失败测试**

新增：

```python
def test_build_programmatic_evidence_payload_should_keep_distinct_fallback_documents_from_same_table(monkeypatch):
    ...
```

构造：

- Bundle 已有 `daily_course_record/D1`，正文长度超过 80 字；
- fallback 返回同表 `daily_course_record/D2`；
- 两份记录时间和正文不同。

断言：

```python
documents = payload["programmatic_timeline"]["documents"]["daily_course_record"]
assert [item["document_id"] for item in documents] == ["D1", "D2"]
assert payload["primary_document_text"].count("日常病程记录") == 2
```

**Step 2: 运行测试并确认红灯**

在 `D:\LLM\LX888\apps\medqc-web` 执行：

```powershell
python -m pytest backend/tests/unit/test_sample_programmatic_evidence.py::test_build_programmatic_evidence_payload_should_keep_distinct_fallback_documents_from_same_table -q
```

Expected: FAIL；当前实现只保留 `D1`。

### Task 3.2：锁定“同一文书只保留更完整副本”

**Files:**

- Test: `backend/tests/unit/test_sample_programmatic_evidence.py`

**Step 1: 写失败测试**

新增：

```python
def test_build_programmatic_evidence_payload_should_deduplicate_same_document_id_and_keep_richer_copy(monkeypatch):
    ...
```

构造同表同 `document_id=D1`：Bundle 副本只有短摘要，fallback 副本包含完整正文和定位时间。

断言：

- 最终只有一份 `D1`；
- 使用完整正文；
- 首次出现位置不变；
- `primary_document_text` 不重复渲染。

**Step 2: 写无 ID 的边界测试**

新增：

```python
def test_build_programmatic_evidence_payload_should_use_conservative_identity_when_document_id_is_missing(monkeypatch):
    ...
```

同一输入同时覆盖：

- 时间、类型、正文完全相同的两个无 ID 副本，最终保留一份；
- 时间或正文不同的无 ID 文书，分别保留。

**Step 3: 运行新增测试并确认至少一项红灯**

```powershell
python -m pytest backend/tests/unit/test_sample_programmatic_evidence.py -k "distinct_fallback_documents or deduplicate_same_document_id or conservative_identity" -q
```

Expected: 当前按表长文本门槛的实现不能同时满足三项合同。

### Task 3.3：实现最小文书身份与合并

**Files:**

- Modify: `backend/app/services/sample_programmatic_evidence.py:108-184`

**Step 1: 增加局部辅助函数**

只在当前模块内增加：

```python
def _normalize_identity_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _safe_text(value))


def _fallback_document_identity(item: dict[str, Any]) -> tuple[str, ...]:
    ...


def _merge_duplicate_document(
    existing: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    ...
```

实现约束：

- 使用标准库 `hashlib.sha256`；
- 不创建类、注册表、配置开关或新模块；
- 不引入相似度阈值；
- 不改 `_item_text()` 的业务语义。

**Step 2: 用身份索引替换表级长度门槛**

`_merge_fallback_items()` 改为：

1. 依次消费 `items` 和 `fallback_items`；
2. 计算文书身份；
3. 新身份追加；
4. 已存在身份在原位置合并更完整副本；
5. 返回稳定顺序列表。

不得改变 `_flatten_inventory_items()` 的调用结构。

**Step 3: 运行三个新增测试**

```powershell
python -m pytest backend/tests/unit/test_sample_programmatic_evidence.py -k "distinct_fallback_documents or deduplicate_same_document_id or conservative_identity" -q
```

Expected: 3 passed。

### Task 3.4：兼容回归与边界审查

**Files:**

- Test: `backend/tests/unit/test_sample_programmatic_evidence.py`

**Step 1: 运行整个模块测试**

```powershell
python -m pytest backend/tests/unit/test_sample_programmatic_evidence.py -q
```

Expected: 全部 PASS。

**Step 2: 运行 Task 1～3 组合聚焦回归**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_execution_routing.py backend/tests/unit/test_qc_sample_pools_router.py backend/tests/unit/test_qc_sichuan_batch_throughput.py backend/tests/unit/test_luxian_0609_mainline_services.py backend/tests/unit/test_sample_programmatic_evidence.py -q
```

Expected:

- Task 1 的 75 条规则资料路径合同不回归；
- Task 2 的 Scene 选择、状态变化幂等和 MaterialStore 合同不回归；
- Task 3 的同表多文书合同通过。

本轮不因历史全量测试中的既有失败扩大修改范围。若组合回归出现新失败，先证明与本 diff 的因果关系。

**Step 3: 编码和关键 diff 检查**

只在闭环完成后运行一次：

```powershell
npm run check:encoding
git diff --check
git diff -- backend/app/services/sample_programmatic_evidence.py backend/tests/unit/test_sample_programmatic_evidence.py
```

审查重点：

- 无 UTF-8 BOM，保持 LF；
- 只修改白名单文件；
- 未修改读取上限、SQL、MaterialStore、规则状态或结果字段；
- 没有把“同表”继续作为重复身份；
- 没有用模糊相似度误合并文书；
- 顺序和单文书输出保持稳定。

### Task 3.5：独立提交并暂停

**Step 1: 提交**

```powershell
git add backend/app/services/sample_programmatic_evidence.py backend/tests/unit/test_sample_programmatic_evidence.py
git commit -m "fix: 按文书身份合并兼容证据"
```

**Step 2: 暂停并汇报**

汇报内容必须包含：

- 实际修改文件；
- 三类文书身份测试结果；
- Task 1～3 组合回归结果；
- 修改前后同表多文书数量示例；
- 身份优先级和“无法确认时保留”的安全策略；
- 仍保留的 7 个兼容 payload 入口；
- 剩余风险及是否建议进入 Task 4。

未经再次确认，不进入 Task 4，不调整源表读取上限，也不启动会诊事件级 LLM 试点。

---

## 5. 验收标准

Task 3 只有同时满足以下条件才算完成：

1. 同一 `source_table` 的两份不同文书均进入 `programmatic_timeline.documents`。
2. 同一稳定文书 ID 的重复副本只保留一份，且保留更完整正文和可用定位字段。
3. 无 ID 时只合并复合身份完全一致的副本；存在歧义时保留。
4. 原有单文书、时间锚点和 fallback meta 测试全部通过。
5. Task 1～2 的聚焦合同不回归。
6. MaterialStore 仍是唯一 Native 权威资料源。
7. 不增加 LLM 调用，不修改规则状态和 Canonical 结果。
8. 改动仅限两个白名单文件并形成一个独立绿色提交。

## 6. 风险与回滚

- **误合并风险：** 通过“稳定 ID 优先、无 ID 使用严格复合身份、歧义时保留”控制。
- **重复展示风险：** 不确定副本可能同时保留，这是有意的保守行为，优先避免丢失真实证据。
- **性能风险：** 合并复杂度为 O(n)，仅对当前已受上限约束的兼容文书集合执行，不新增数据库查询。
- **范围扩张风险：** 行数上限和截断语义属于 Task 4，本任务禁止顺手修改。
- **回滚方式：** 独立提交可整体回滚；不涉及数据库迁移、数据重写或接口变化。
