# LX0609 Task 4：真实源表行数与读取上限审计 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用冻结样本的真实行数证明哪些 LX0609 权威资料源存在截断风险，并且只在有明确证据时调整单个源表读取上限。

**Architecture:** 保持 `EvidenceSnapshot/MaterialStore` 为唯一 Native 权威资料链，不新增 Bundle 或 payload 证据层。审计在一个 PostgreSQL `REPEATABLE READ、READ ONLY` 事务中冻结样本集合，并按物理表批量绑定完整三坐标统计真实行数；只有真实 `count > limit` 的候选病例才通过同一事务绑定的现有 reader 验证截断。审计报告形成决策门，未触顶则不修改生产代码，触顶且影响规则完整性时才进入条件性 TDD 调整。

**Tech Stack:** Python 3.10+、SQLAlchemy、PostgreSQL、pytest、Markdown

---

## 1. 已确认的当前事实

### 1.1 Native 主链的真实上限来源

当前上限定义在：

- `backend/app/services/bundles/assembly.py:333-379`：`_DOMAIN_FETCH_LIMITS`
- `backend/app/services/luxian_0609/source_evidence_reader.py:917-926`：Native reader 通过 `_source_limit()` 读取同一份配置

重点当前值：

| 资料源                       | 当前上限 |
| ---------------------------- | -------: |
| `daily_course_record`        |      200 |
| `senior_course_record`       |      200 |
| `consultation_record`        |      100 |
| `inpat_drug_order`           |      100 |
| `inpat_nondrug_order`        |      100 |
| `inpat_bill_item`            |      200 |
| `exam_master`                |      500 |
| `exam_item_report`           |     2000 |
| `labtest_master`             |      500 |
| `labtest_item_report`        |     5000 |
| 手术、麻醉、输血及多数单据表 |       50 |

兼容 fallback 中的 `_FALLBACK_DOC_FETCH_LIMITS` 不属于本 Task 的审计对象，不得与 Native 上限混用。

### 1.2 截断检测已经存在

`read_luxian_0609_snapshot_source_rows()` 已经：

1. 使用三坐标 `institute_id + patient_id + visit_id` 查询；
2. 使用稳定排序；
3. 查询 `limit + 1` 行；
4. 仅保存前 `limit` 行；
5. 多出一行时设置 `SnapshotSourceRows.truncated=True`；
6. Snapshot 将其映射为 `SourceCompleteness.TRUNCATED`。

已有测试：

- `backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py:1613-1660`
- `backend/tests/unit/test_luxian_0609_runtime_shadow_input_provider.py:717`
- `backend/tests/unit/test_luxian_0609_surgery_text_fact_contract.py:632`

因此本轮不得再建设第二套截断状态，也不得把所有表上限直接改成 1000。

## 2. 审计问题

Task 4 只回答以下问题：

1. 冻结病例在各物理资料表中实际有多少行？
2. 哪些病例达到或超过当前 Native limit？
3. reader 是否实际返回 `truncated=True`？
4. 触顶资料源被哪些 LX0609 规则使用？
5. 这些规则是否依赖“完整集合”才能作合规、不适用或不存在判断？
6. 调整上限后预计增加多少请求内行数和查询成本？

不在本 Task 解决：

- 源库根本没有数据；
- 同步字段映射缺失；
- 事件关联失败；
- 规则定义不清；
- LLM 调用扩容；
- 兼容 fallback 文书合并；
- 两份病例的全部质控结果修复。

---

## 3. 文件范围

### 第一阶段：只读审计

- Create: `backend/scripts/audit_luxian_0609_source_row_limits.py`
- Create: `backend/tests/unit/test_audit_luxian_0609_source_row_limits.py`
- Create: `docs/reports/2026-08-03-lx0609-source-row-limit-audit.md`

### 第二阶段：仅在审计证据成立后允许修改

- Conditional Modify: `backend/app/services/bundles/assembly.py:333-379`
- Conditional Test: `backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py`
- Conditional Test: 触顶资料源对应的一个现有 `backend/tests/unit/test_luxian_0609_native_*_execution.py`

### 禁止修改

- `backend/app/services/luxian_0609/evidence_material.py`
- `backend/app/services/luxian_0609/evidence_snapshot.py`
- `backend/app/services/luxian_0609/source_evidence_reader.py` 的读取和截断算法
- Canonical Result、Envelope、数据库表结构、API、前端
- `_FALLBACK_DOC_FETCH_LIMITS`
- LLM 配置和提示词

如果必须修改上述禁止文件，立即停止 Task 4 并重新评审。

---

## 4. 审计输出合同

报告按资料源输出：

| 字段                     | 含义                                                          |
| ------------------------ | ------------------------------------------------------------- |
| `source_key`             | Native 权威资料源                                             |
| `physical_table`         | 实际 CDM 表；派生来源单独标记                                 |
| `current_limit`          | 当前 Native limit                                             |
| `sample_visit_count`     | 纳入统计的三坐标完整病例数                                    |
| `nonempty_visit_count`   | 至少一行的病例数                                              |
| `p50/p95/p99/max`        | 每病例真实行数分布，包含 0 行病例                             |
| `at_limit_count`         | 行数等于 limit 的病例数                                       |
| `above_limit_count`      | 行数大于 limit 的病例数                                       |
| `reader_truncated_count` | reader 实际标记截断的病例数                                   |
| `focus_case_a/b`         | 两份重点病例行数与截断状态                                    |
| `affected_rule_ids`      | 使用该资料源的 LX0609 规则                                    |
| `complete_set_required`  | 是否需要完整集合才能判定                                      |
| `recommendation`         | `keep_limit` / `availability_review` / `propose_limit_change` |

报告头还必须记录：

| 字段                           | 含义                                         |
| ------------------------------ | -------------------------------------------- |
| `audit_started_at`             | 一致性快照开始时间（UTC）                    |
| `git_commit`                   | 执行审计的代码版本                           |
| `transaction_isolation`        | 固定为 `repeatable_read`                     |
| `transaction_read_only`        | 固定为 `true`                                |
| `pool_id`                      | 唯一样本池 ID                                |
| `pool_name`                    | 样本池名称                                   |
| `frozen_coordinate_count`      | 冻结后三坐标数量                             |
| `coordinate_set_hash`          | 排序后三坐标集合的 SHA-256；不得输出坐标本身 |
| `excluded_missing_coordinates` | 三坐标缺失的样本数                           |
| `focus_coordinate_missing`     | 重点 visit 无法解析唯一坐标的数量            |
| `focus_coordinate_ambiguous`   | 重点 visit 命中多组三坐标的数量              |

隐私约束：

- 报告不得包含患者姓名、住院号、`patient_id`、`institute_id` 或文书正文。
- 普通病例不输出 visit_id；仅输出聚合分布。
- 两份指定病例在报告中写为 `focus_case_a`、`focus_case_b`。
- 坐标集合只允许输出按规范化排序计算的 `coordinate_set_hash`，不得输出哈希前材料。
- 审计脚本只执行 `SELECT`，不得执行 `INSERT/UPDATE/DELETE/DDL`。
- 样本池和 CDM 的所有统计查询必须位于同一个数据库一致性快照；报告文件在事务完成后写入本地文件系统。

---

## 5. TDD 与执行步骤

### Task 4.1：建立纯统计与脱敏合同

**Files:**

- Create: `backend/scripts/audit_luxian_0609_source_row_limits.py`
- Create: `backend/tests/unit/test_audit_luxian_0609_source_row_limits.py`

**Step 1: 写第一个失败测试——分布包含零行病例**

测试公共函数：

```python
def summarize_source_counts(
    *,
    counts_by_visit: dict[str, int],
    all_visit_refs: tuple[str, ...],
    current_limit: int,
) -> dict[str, int | float]:
    ...
```

测试输入：5 个病例，行数分别为 `0, 1, 2, 100, 101`，limit 为 100。

断言：

```python
assert summary["sample_visit_count"] == 5
assert summary["nonempty_visit_count"] == 4
assert summary["max"] == 101
assert summary["at_limit_count"] == 1
assert summary["above_limit_count"] == 1
```

**Step 2: 验证红灯**

```powershell
python -m pytest backend/tests/unit/test_audit_luxian_0609_source_row_limits.py::test_summary_includes_zero_row_visits_and_limit_hits -q
```

Expected: FAIL，审计模块尚不存在。

**Step 3: 实现最小纯函数并转绿**

百分位数必须使用确定性 nearest-rank 算法，不引入 pandas/numpy：

```python
def nearest_rank(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]
```

```powershell
python -m pytest backend/tests/unit/test_audit_luxian_0609_source_row_limits.py::test_summary_includes_zero_row_visits_and_limit_hits -q
```

Expected: PASS。

**Step 4: 写第二个失败测试——报告不得泄露坐标**

构造含 `institute_id/patient_id/visit_id/patient_name` 的内部记录，断言最终报告对象及 JSON 中均不包含原值，只保留聚合统计和 `focus_case_a/b`。同时锁定：排序不同时 `coordinate_set_hash` 相同，任一坐标变化时哈希不同。

```powershell
python -m pytest backend/tests/unit/test_audit_luxian_0609_source_row_limits.py -k "redact or safe_report" -q
```

Expected: RED 后做最小实现，再转 GREEN。

### Task 4.2：建立只读病例选择和行数查询

**Files:**

- Modify: `backend/scripts/audit_luxian_0609_source_row_limits.py`
- Test: `backend/tests/unit/test_audit_luxian_0609_source_row_limits.py`

**Step 1: 锁定病例选择规则**

样本池参数合同：

- CLI 同时支持 `--pool-id` 和 `--pool-name`，二者互斥；正式审计优先使用 `--pool-id`。
- 使用 `--pool-name` 时必须精确匹配且恰好得到一条；0 条报 `pool_not_found`，多条报 `pool_name_ambiguous`，不得按更新时间或第一条选择。

0426 样本集合冻结规则：

1. 在一致性事务内读取唯一 pool 行并记录 `pool_id/pool_name`；
2. 从 `manual_problem_sample_pool_items` 只读取 `match_status='matched'` 的记录；
3. 三坐标完整的记录按规范化三元组去重；缺失记录只计入 `excluded_missing_coordinates`；
4. 计算排序后三坐标集合的 SHA-256，之后所有表统计只使用这份不可变 tuple；
5. 审计开始后即使样本池后台继续写入，也不得重新加载或扩大样本集合。

重点病例 A、B 的 visit 坐标解析规则：

1. 优先使用冻结样本集合中该 visit 已有的完整三坐标；
2. 只有样本池不存在时，才在同一事务内从 `cdm.mr`、`cdm.admission_record` 查询全部 `DISTINCT institute_id, patient_id, visit_id`；
3. 去重后恰好一组三坐标才接受；
4. 0 组记录 `focus_coordinate_missing`，多组记录 `focus_coordinate_ambiguous`；两种情况均排除；
5. 禁止 `LIMIT 1`、禁止任取第一条，后续不得用 visit_id 单坐标查询。

测试必须覆盖样本池名称 0/1/2 条、重点 visit 0/1/2 组三坐标。

**Step 2: 锁定一致性只读事务**

审计必须使用一个 connection 和一个事务：

```python
connection = engine.connect().execution_options(isolation_level="REPEATABLE READ")
with connection.begin():
    connection.exec_driver_sql("SET TRANSACTION READ ONLY")
    frozen_coordinates = load_frozen_coordinates(connection, ...)
    audit_result = audit_all_sources(connection, frozen_coordinates, ...)
```

约束：

- `SET TRANSACTION READ ONLY` 必须是事务中的第一条语句；
- pool 解析、样本读取、重点坐标补查、物理表统计和候选 reader 验证都复用该 connection；
- 报告内容在事务内组装，事务结束后才写本地 Markdown；
- 测试断言隔离级别、READ ONLY 设置顺序，并断言业务 SQL 无 `INSERT/UPDATE/DELETE/CREATE/ALTER/DROP`。

为让现有 reader 在同一事务中验证候选截断，审计脚本只允许实现一个非持有型 connection adapter，使 `bundle_assembly.engine.connect()` 返回当前 connection 的 `nullcontext`；不得修改 reader 生产接口，也不得复制 reader SQL。adapter 只存在于审计脚本进程，退出上下文后必须恢复原 engine。

**Step 3: 按表批量统计，禁止 N×M 查询**

审计表名只能来自现有受控常量与 source registry，不接受用户自由输入。每张物理表按固定 200 个坐标一批，使用参数绑定的 `VALUES` 集合 JOIN 并 GROUP BY：

```sql
WITH visit_keys(institute_id, patient_id, visit_id) AS (
    VALUES (:i0, :p0, :v0), (:i1, :p1, :v1)
)
SELECT k.institute_id, k.patient_id, k.visit_id, count(t.*) AS row_count
FROM visit_keys AS k
LEFT JOIN <受控 schema>.<受控 table> AS t
  ON t.institute_id = k.institute_id
 AND t.patient_id = k.patient_id
 AND t.visit_id = k.visit_id
GROUP BY k.institute_id, k.patient_id, k.visit_id
```

约束：

- 坐标只能通过 bind parameter 传入，不能拼接进 SQL；
- schema/table 只能从固定 allowlist 引用；
- 每表查询次数不得超过 `ceil(frozen_coordinate_count / 200)`；
- 统计必须保留 0 行病例；
- 只有 `count > current_limit` 的物理来源候选才调用现有 reader 验证 `truncated=True`，不得对全部病例逐一调用 reader。

测试以 401 个坐标、2 张表验证每表恰好 3 次批量查询，而不是 802 次。

**Step 4: 分开处理物理来源与派生来源**

- 物理来源：批量 `count(*)`，计算 P50/P95/P99/max；只对 `count > limit` 候选使用同事务 reader 验证截断。
- `inpat_nondrug_order.severity_order`、`inpat_nondrug_order.exam_lab_order` 等派生来源：继续调用现有受控 reader，不复制过滤 SQL；按固定批次顺序执行并单独记录调用量。
- `evaluation_context.horizon` 等非数据库来源：标记 `not_physical`，不纳入行数上限建议。

**Step 5: 聚焦测试**

```powershell
python -m pytest backend/tests/unit/test_audit_luxian_0609_source_row_limits.py -q
```

Expected: 全部 PASS；测试不得连接真实数据库。

### Task 4.3：执行冻结样本只读审计并生成报告

**Files:**

- Create: `docs/reports/2026-08-03-lx0609-source-row-limit-audit.md`

**Step 1: 运行只读审计**

先只读确认 `0426` 名称唯一并取得 pool ID；若 0 条或多条立即停止。正式审计命令使用明确 ID：

```powershell
python backend/scripts/audit_luxian_0609_source_row_limits.py --pool-id <唯一pool_id> --focus-visit-id <重点visit_id_A> --focus-visit-id <重点visit_id_B> --output docs/reports/2026-08-03-lx0609-source-row-limit-audit.md
```

Expected:

- 命令只读数据库并写本地 Markdown 报告；
- 输出纳入病例数、缺三坐标排除数、物理来源数、实际截断来源数；
- 输出审计时间、代码版本、pool ID、冻结病例数和坐标集合哈希；
- 确认事务为 `REPEATABLE READ、READ ONLY`；
- 不输出病历正文或患者信息。

**Step 2: 手工复核报告中的三类结论**

每个来源必须归入：

1. `keep_limit`：没有截断证据，包括正常稀疏和 0 行；保持配置。
2. `availability_review`：只有存在独立事件或其他权威来源证明“该资料本应存在”时，才转交同步/字段映射排查。
3. `propose_limit_change`：冻结快照真实行数超过 limit，且同一事务中的现有 reader 确认 `truncated=True`。

不能用“数据不足数量很多”反推上限过小，也不能仅凭 0 行生成 `availability_review`。如果没有外部存在性证据，0 行仍归 `keep_limit`。

**Step 3: 将触顶来源映射到规则**

结合：

- `docs/reports/2026-08-03-lx0609-rule-evidence-path-matrix.md`
- `backend/app/services/luxian_0609/native_package.py`
- `backend/app/services/luxian_0609/source_registry.py`

逐项记录触顶来源影响的规则 ID，以及该规则是否需要完整集合才能形成否定结论。

### Task 4.4：决策门——默认暂停

完成报告后必须暂停并汇报，不自动修改上限。

只有同时满足以下条件才建议继续 Task 4.5：

1. 至少一个冻结病例真实行数 `> current_limit`；
2. 现有 reader 通过同一事务绑定 connection 对该病例返回 `truncated=True`；
3. 至少一条 active LX0609 规则需要完整集合；
4. 数据不足根因确实是截断，不是同步缺失、字段映射或关联失败；
5. 已给出具体新上限及预计最大内存/查询行数变化。

若没有任何来源满足五项条件，Task 4 以“无需修改生产上限”完成，只提交审计工具、测试和报告。

### Task 4.5：条件性调整单一来源上限（当前未授权）

Task 4.1～4.4 完成后必须暂停。只有用户再次明确确认具体 source key 和拟议值，才允许执行本节。

**Files:**

- Conditional Modify: `backend/app/services/bundles/assembly.py:333-379`
- Conditional Test: `backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py`
- Conditional Test: 对应规则族现有测试文件

**Step 1: 先写失败测试**

对审计确认的具体 source key 锁定：

```python
def test_native_source_limit_uses_audited_value():
    assert luxian_0609_native_source_row_limit("<source_key>") == <audited_limit>
```

再构造 `<audited_limit> + 1` 行，断言：

```python
assert result.limit_rows == <audited_limit>
assert result.truncated is True
assert len(result.rows) == <audited_limit>
```

**Step 2: 验证红灯后只改一个常量值**

不得修改 reader 算法。一次只调整一个 `source_key`，不顺手调整同族其他表。

**Step 3: 锁定规则失败语义**

对受影响规则增加或复用一条测试：截断材料不得形成基于“未发现”的 `compliant/not_applicable`；应得到受控 `data_gap/uncertain`，并说明资料读取未完整。

**Step 4: 聚焦回归**

```powershell
python -m pytest backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py backend/tests/unit/test_audit_luxian_0609_source_row_limits.py <对应规则族测试文件> -q
```

Expected: PASS。

---

## 6. 闭环检查与提交

### 无生产上限修改时

```powershell
python -m pytest backend/tests/unit/test_audit_luxian_0609_source_row_limits.py backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py -q
git diff --check
git add backend/scripts/audit_luxian_0609_source_row_limits.py backend/tests/unit/test_audit_luxian_0609_source_row_limits.py docs/reports/2026-08-03-lx0609-source-row-limit-audit.md
git commit -m "audit: 核对LX0609资料读取上限"
```

### 有审计支持的单表修改时

第一提交只保存审计证据：

```powershell
git add backend/scripts/audit_luxian_0609_source_row_limits.py backend/tests/unit/test_audit_luxian_0609_source_row_limits.py docs/reports/2026-08-03-lx0609-source-row-limit-audit.md
git commit -m "audit: 核对LX0609资料读取上限"
```

用户确认具体上限后，第二提交只包含配置与对应合同：

```powershell
git add backend/app/services/bundles/assembly.py backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py <对应规则族测试文件>
git commit -m "fix: 按审计结果调整LX0609资料上限"
```

闭环时只运行一次编码检查和关键 diff 审查，不在每个小测试后运行全量检查。

---

## 7. 验收标准

Task 4 第一阶段完成必须满足：

1. `--pool-id` 明确唯一；名称解析 0 条或多条时停止。
2. 样本池和 CDM 审计全部位于同一个 `REPEATABLE READ、READ ONLY` 事务。
3. 报告记录审计时间、Git commit、pool ID、冻结病例数和脱敏坐标集合哈希。
4. 0426 样本池和两份重点病例均纳入或明确记录 `missing/ambiguous` 排除原因。
5. 重点 visit 补查只有恰好一组三坐标时才接受，禁止 `LIMIT 1`。
6. 所有统计查询使用完整三坐标并且只读。
7. 物理表采用每表批量 GROUP BY 查询，不得按病例逐表 N×M 查询。
8. 只有 `count > limit` 的物理来源候选调用现有 reader 确认截断。
9. 报告包含每个 Native 物理来源的真实分布、当前 limit 和截断数量。
10. 报告不含患者信息、原始三坐标或文书正文。
11. 物理来源、派生来源和非数据库来源没有混算。
12. 0 行或正常稀疏默认 `keep_limit`；`availability_review` 必须有独立存在性证据。
13. 每个 `propose_limit_change` 均有具体病例触顶证据和受影响规则 ID。
14. 未触顶来源不修改上限。
15. 不修改 MaterialStore、reader 截断算法、规则状态或 Canonical 结果。

若进入条件性调整，还必须满足：

16. 一次只修改一个有证据的 source key。
17. reader 继续使用 limit+1，并能正确标记 TRUNCATED。
18. 截断资料不能形成错误合规或不适用结论。
19. 查询行数/内存增长在报告中量化。

## 8. 停止条件

出现以下任一情况立即停止，不继续调上限：

- 0426 样本池无法稳定解析完整三坐标；
- 样本池名称匹配 0 条或多条，且未提供明确 pool ID；
- 重点 visit 返回多组三坐标，无法证明唯一身份；
- 无法建立单一 `REPEATABLE READ、READ ONLY` 一致性事务；
- 本地 PG 与实际客户数据分布不具备代表性；
- 数据不足源于同步缺表或字段映射，而非截断；
- 需要复制现有 reader 的复杂过滤 SQL；
- 需要同时修改多个规则族才能验证收益；
- 拟议上限会显著增加单病例内存，但没有查询耗时数据；
- 需要数据库写操作。

Task 4 完成后继续暂停会诊事件级 LLM 试点；是否进入 Task 5 需根据审计报告重新评估。
