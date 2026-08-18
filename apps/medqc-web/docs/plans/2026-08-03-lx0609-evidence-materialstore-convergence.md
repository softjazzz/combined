# LX0609 EvidenceMaterialStore 完整资料链收敛 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 找出仍依赖 Scene/旧 `evidence_payload` 的 LX0609 规则，并逐点收敛到现有 `EvidenceReadSession → EvidenceSnapshot → EvidenceMaterialStore` 唯一 Native 资料链。

**Architecture:** Scene Bundle 只决定病例场景和页面锚点；Native 规则的源资料由请求内 `EvidenceMaterialStore` 提供。先建立 75 条规则的真实资料路径表，再只修改已证实仍由兼容 payload 影响判定的规则；Domain Bundle 不进入 Native 权威路径。

**Tech Stack:** Python 3.10、FastAPI、SQLAlchemy/PostgreSQL、pytest、LX0609 Native Engine、EvidenceSnapshot/MaterialStore。

---

## 范围和硬约束

- 保留 `EvidenceMaterialStore` 为唯一 Native 权威资料源。
- `evidence_payload` 可继续服务旧 Adapter，但不能覆盖 MaterialStore 已提供的事实。
- 本计划不增加 LLM 调用，不修改提示词，不建设事件平台。
- 不修改 Canonical Envelope、保存结构和 API。
- 不统一调大 `_DOMAIN_FETCH_LIMITS`；任何上限调整必须有真实行数分布和截断证据。
- 每次只迁移一个规则族，聚焦测试通过后提交，再进入下一族。
- “数据不足从 38 条降到 13～16 条”只作为旧预测，不作为验收指标。

### Task 1：建立 75 条规则实际资料路径表

**Files:**

- Create: `docs/reports/2026-08-03-lx0609-rule-evidence-path-matrix.md`
- Inspect: `backend/app/services/luxian_0609/execution.py:183-448`
- Inspect: `backend/app/services/luxian_0609/native_package.py:90-259`
- Inspect: `backend/app/services/luxian_0609/rule_contracts.py:137-214`
- Inspect: `backend/app/services/luxian_0609/source_registry.py:524-647`
- Inspect: `backend/app/services/luxian_0609/executor_registry.py:117-335`
- Inspect: `backend/app/services/luxian_0609/evidence_snapshot_provider.py:147-520`
- Modify: `backend/app/services/luxian_0609/native_package.py:161-166`
- Test: `backend/tests/unit/test_luxian_0609_execution_routing.py`

**Step 1: 从权威规则目录导出 75 个规则 ID**

使用 `load_luxian_0609_rule_contracts()` 和 `load_luxian_0609_dependency_inventory()`，核对规则数量、executor 和 execution mode；不得手写另一份运行时注册表。

**Step 2: 逐规则记录真实读取路径**

矩阵每行至少包含：`rule_id`、`executor_key`、`source_registry声明`、`executor_registry补充source keys`、`实际materials.rows()/bounded_rows()位置`、`是否读取evidence_payload`、`payload是否影响最终状态`、`截断语义`、`迁移优先级`。仅检查通用 Evidence Provider 不算完成，必须追到具体 executor 的实际读取行。

**Step 3: 增加静态合同测试**

在 `test_luxian_0609_execution_routing.py` 增加断言：75 条规则全部有 executor、Rule Contract 和已注册 source keys；缺一项即失败。资料路径矩阵由代码审计形成，不让生产代码或测试反向解析 Markdown，也不复制一份运行时配置。

同时将 `native_package.py` 中“49点执行依赖清单”的过期 docstring 改为“不绑定固定数量的全量执行依赖清单”，不改任何运行逻辑。

**Step 4: 运行测试**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_execution_routing.py backend/tests/unit/test_luxian_0609_rule_contracts.py -q`

Expected: PASS；人工复核报告中没有“未知资料来源”的 active 规则。

**Step 5: 提交**

```powershell
git add docs/reports/2026-08-03-lx0609-rule-evidence-path-matrix.md backend/app/services/luxian_0609/native_package.py backend/tests/unit/test_luxian_0609_execution_routing.py
git commit -m "test: 锁定LX0609规则资料路径"
```

### Task 2：按病例状态选择正确 Scene 锚点

**Files:**

- Modify: `backend/app/routers/qc_sample_pools.py:1138-1260`
- Modify: `backend/app/routers/qc_sichuan.py:264-273`
- Modify: `backend/app/routers/qc_sichuan.py:2887-2960`
- Modify: `backend/app/routers/qc_sichuan.py:4090-4143`
- Modify only if required: `backend/app/services/custom_qc_sample_pool_service.py`
- Test: `backend/tests/unit/test_qc_sample_pools_router.py`
- Test: `backend/tests/unit/test_running_final_bundle_orchestrated.py`
- Test: `backend/tests/unit/test_qc_sichuan_batch_throughput.py`

**Step 1: 写失败测试**

覆盖同一批次混合在院和出院病例：任务查询范围为 running/all/final 的不同组合下，在院病例仍优先使用 running Scene，出院病例仍优先使用 final Scene。断言 Scene 只影响病例锚点和评价时点，不改变 Native 的 MaterialStore 来源。

增加以下失败场景：任务级 `current_scope=running`、病例 `record.scope=final` 时，必须先尝试 final；final 加载失败、running 成功时，必须记录实际加载的 running 和 Scene 不确定性；同一病例由 running 变为 final 后，不得复用旧的 queued/running 任务。

**Step 2: 验证测试失败**

Run: `python -m pytest backend/tests/unit/test_qc_sample_pools_router.py backend/tests/unit/test_running_final_bundle_orchestrated.py backend/tests/unit/test_qc_sichuan_batch_throughput.py -k "mixed_status or scene_scope or idempotency" -q`

Expected: 当前统一使用 pool scene 时 FAIL。

**Step 3: 做最小修改**

明确拆开两个概念：

- `query_scope`：用户筛选任务病例的范围，只用于 `collect_records()`。
- `record_scene`：单份病例的住院状态快照，用于选择 running/final Bundle。

在 `qc_sichuan.py` 中将候选顺序改为病例 Scene 优先，任务级 scope 只在病例状态未知时作为 fallback。循环加载时保存 `loaded_scene`；`package_bundle["scene"]` 必须赋值为实际成功加载的 Scene，不能再用 `setdefault()`推测。

病例状态无法确认时，不让75条规则整体进入数据不足。应使用可用 Scene 继续执行，同时在内部 package metadata 记录 `scene_resolution=uncertain_fallback`、候选顺序和实际 Scene；该元数据只用于审计，不改变 MaterialStore 权威资料。

任务幂等身份加入有序的病例状态快照：`record_id + record_scene + discharge_datetime(如有)`。因此同一 visit 从 running 转为 final 后会形成新任务身份；不得仅使用 record ID 集合去重。

**Step 4: 运行聚焦测试**

Run: `python -m pytest backend/tests/unit/test_qc_sample_pools_router.py backend/tests/unit/test_running_final_bundle_orchestrated.py backend/tests/unit/test_qc_sichuan_batch_throughput.py -q`

Expected: PASS。

**Step 5: 提交**

```powershell
git add backend/app/routers/qc_sample_pools.py backend/app/routers/qc_sichuan.py backend/app/services/custom_qc_sample_pool_service.py backend/tests/unit/test_qc_sample_pools_router.py backend/tests/unit/test_running_final_bundle_orchestrated.py backend/tests/unit/test_qc_sichuan_batch_throughput.py
git commit -m "fix: 按病例状态选择质控场景"
```

### Task 3：修复兼容 fallback 的文书身份去重

**Files:**

- Modify: `backend/app/services/sample_programmatic_evidence.py:150-190`
- Test: `backend/tests/unit/test_sample_programmatic_evidence.py`

**Step 1: 写失败测试**

构造同一 `source_table` 下两份不同文书、同一文书重复副本及缺少主键的三种输入。预期保留两份不同文书，只合并真正重复项。

**Step 2: 验证测试失败**

Run: `python -m pytest backend/tests/unit/test_sample_programmatic_evidence.py -k "fallback and identity" -q`

Expected: 当前按表保留最长一条时 FAIL。

**Step 3: 实现稳定文书身份**

身份优先级只使用现有字段：源表主键/文书ID；其次使用 `source_table + record_time + document_type + content_hash`。不得只按表名去重，也不得新增数据库字段。

**Step 4: 运行聚焦测试**

Run: `python -m pytest backend/tests/unit/test_sample_programmatic_evidence.py -q`

Expected: PASS，且既有兼容输入不回归。

**Step 5: 提交**

```powershell
git add backend/app/services/sample_programmatic_evidence.py backend/tests/unit/test_sample_programmatic_evidence.py
git commit -m "fix: 按文书身份合并兼容证据"
```

### Task 4：统计真实源表行数并校准读取上限

**Files:**

- Create: `docs/reports/2026-08-03-lx0609-source-row-distribution.md`
- Modify only with evidence: `backend/app/services/bundles/assembly.py:333-379`
- Test: `backend/tests/unit/test_luxian_0609_source_evidence_reader.py`

**Step 1: 对冻结样本池执行只读统计**

至少覆盖 0426 样本池和两份问题病例，按源表记录 P50/P95/P99/max、当前 limit、达到 limit 的病例数。重点检查 `inpat_drug_order`、`inpat_nondrug_order`、`daily_course_record`、`consultation_record`、检查检验明细。

**Step 2: 记录结论而不预设新上限**

只有当 P99 或真实问题病例达到当前 limit，且规则需要完整集合证明“未发现”时，才提出具体新值。源表确实超限时，规则必须看到 `SourceCompleteness.TRUNCATED`，不得判合规。

**Step 3: 写截断测试**

验证 reader 使用 limit+1 或等价方式区分完整与截断；截断材料进入规则后只能得到具体 `data_gap/uncertain`，不能得到基于缺失搜索的 compliant。

**Step 4: 仅修改有证据的表上限**

禁止把所有医嘱直接改为 1000。每个调整值都写入报告，并说明内存和查询耗时变化。

**Step 5: 运行测试并提交**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_source_evidence_reader.py backend/tests/unit/test_luxian_0609_evidence_snapshot_provider.py -q`

```powershell
git add docs/reports/2026-08-03-lx0609-source-row-distribution.md backend/app/services/bundles/assembly.py backend/tests/unit/test_luxian_0609_source_evidence_reader.py
git commit -m "fix: 按真实分布校准LX0609资料上限"
```

### Task 5：逐族移除旧 payload 的判定权

**Files:**

- Modify only when matrix marks authoritative legacy read: `backend/app/services/luxian_0609/native_course_quality_execution.py`
- Then reassess: `backend/app/services/luxian_0609/native_surgery_gate_execution.py`
- Then reassess: `backend/app/services/luxian_0609/native_surgery_document_execution.py`
- Then reassess: `backend/app/services/luxian_0609/native_exam_lab_execution.py`
- Then reassess: `backend/app/services/luxian_0609/native_tumor_pathology_execution.py`
- Then reassess: `backend/app/services/luxian_0609/native_transfusion_execution.py`
- Tests: matching `backend/tests/unit/test_luxian_0609_native_*_execution.py`

**Step 1: 从矩阵选择一个规则族**

只有满足“当前 active 规则的最终状态仍会被 `evidence_payload` 决定”的规则族才进入修改。优先处理两份问题病例实际命中的族。

**Step 2: 写冲突输入测试**

构造 MaterialStore 有完整事实、旧 payload 缺失或相反的输入，断言最终状态只服从 MaterialStore。兼容 payload 只能补展示字段，不能覆盖权威事实。

**Step 3: 做最小迁移并运行该族测试**

一次只改一个执行器；测试通过立即提交。若必须跨两个规则族共享新抽象，停止并重新评审，不继续扩范围。

**Step 4: 更新资料路径矩阵**

将该族标记为 `material_store_authoritative`，记录删除或降级的 payload 读取点。

**Step 5: 逐族重复，随时可停止**

每族一个提交，未证明受影响的文件不修改。不得一次提交六个执行器。

### Task 6：两份真实病例功能回归和 38 条根因分类

**Files:**

- Create: `docs/reports/2026-08-03-lx0609-two-case-evidence-regression.md`
- Update: `docs/reports/2026-08-03-lx0609-rule-evidence-path-matrix.md`
- Use: `backend/scripts/run_luxian_0609_fixed10_readonly.py`

**Step 1: 重跑 2496813、359787**

记录每条规则的状态、实际 MaterialStore source key、完整性、使用行数和理由。数据库写入如有需要，执行前单独取得授权。

**Step 2: 分类原 38 条数据不足**

逐条归为：`读取遗漏`、`事件关联失败`、`口径缺失`、`源库确实缺失`、`需要语义判断`。不允许用一个总数替代逐条证据。

**Step 3: 验收功能结果**

- 资料实际存在的规则不再因为 Scene 只取 3 条而数据不足。
- 截断或源表缺失时返回客户可懂的具体缺口。
- MaterialStore、最终 Canonical item、数据库 Envelope、单一结果 API 的状态和 reason code 一致。
- 本阶段不计算 P95、98%重复一致率或 off-focus。

**Step 4: 运行回归测试**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_execution_routing.py backend/tests/unit/test_luxian_0609_source_evidence_reader.py backend/tests/unit/test_sample_programmatic_evidence.py backend/tests/unit/test_luxian_0609_execution_contract.py -q`

Expected: PASS。

**Step 5: 提交**

```powershell
git add docs/reports/2026-08-03-lx0609-two-case-evidence-regression.md docs/reports/2026-08-03-lx0609-rule-evidence-path-matrix.md
git commit -m "test: 验收LX0609完整资料链"
```

## 完成定义

- 75 条规则都有真实资料路径记录。
- Native 判定只有 MaterialStore 一个权威资料源。
- fallback 不再按表丢失同表不同文书。
- 读取上限有真实分布依据，截断状态可观察且不会误判合规。
- 两份问题病例完成逐条根因复核。
- 不新增 LLM 调用，不改变结果交付合同。

## 当前批准顺序

1. Task 1可立即执行。
2. Task 2已按逐病例Scene、实际加载Scene和状态快照幂等身份完成修订，可在Task 1后执行。
3. Task 3与Task 2解耦，可独立执行；为便于回归定位，仍建议按Task 1→2→3顺序提交。
4. Task 1～3聚焦测试通过后暂停复核，再决定是否进入Task 4～6。
