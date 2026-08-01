# MedQC 客户样本验证与 LX0609 发布候选 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把当前可运行但验收证据分散的客户样本验证模块，收敛成“状态真实、流程闭环、结果可复核、成本可度量、可安全回滚”的 LX0609 发布候选。

**Architecture:** 保留现有样本池、workspace batch、LX0609 分族子任务和结果抽屉，不重写业务框架。先生成与当前 HEAD/配置绑定的版本清单和验收工件，再用隔离样本完成页面到后端的端到端闭环，随后按规则风险补 Golden、准确性和性能门禁；旧映射链只作为按规则族可回滚的兼容路径。

**Tech Stack:** Vue 3、TypeScript、Ant Design Vue、FastAPI、Python、SQLAlchemy、pytest、Vitest、现有 sample-pool/workspace batch/LX0609 native package、受控 LLM client。

---

## 一、范围、原则与完成定义

### 本轮范围

- 客户样本池：导入、匹配、同步、病历聚合、就绪状态。
- 客户自建测试病历：生成、编辑、保存、按选中规则验证。
- LX0609：全 49 点/指定规则/规则族任务创建与聚合展示。
- 任务中心：进度、失败、取消、重试、结果、复核、导出。
- 规则质量：当前版本 Golden、真实样本复核、LLM 调用与 token、隐私检查。
- 发布：默认开关、回滚、release gate、交付说明。

### 不在本轮扩张的内容

- 不重写通用 Sichuan 规则引擎。
- 不继续做与客户样本验证无关的 workstation 大规模 UI 改版。
- 不为了消除 `data_gap` 猜测不存在的结构化字段。
- 不一次性把所有旧映射删除；只有通过门禁的规则族才切换默认路径。
- 不把单元测试、合成样本或“能跑完”当成真实准确率。

### 两级完成定义

**演示候选：**

- 客户样本页主流程可完成：选择样本 → 选择规则 → 创建任务 → 查看结果 → 复核 → 导出。
- 任务状态真实，失败不伪装成功；49 点顺序与选择范围准确。
- 客户可见结果无内部术语、原始 prompt/response、正文泄漏或三坐标泄漏。
- 固定 Fast5 和至少 10 份授权真实病历可稳定运行；有一份当前 HEAD 对应的验收报告。

**发布候选：**

- 每条默认启用规则至少有正例、反例、边界例中的适用组合，且有人工确认状态。
- 高风险 `non_compliant` 规则族的误报率达到批准阈值；来源不足不会误报。
- 固定 10 例端到端基准包含准确性、耗时、调用数、输入/输出/总 token、隐私与回滚证据。
- release gate 由当前 HEAD/配置生成，且阻塞项为零或有书面豁免。

## 二、里程碑与顺序

| 里程碑 | 目标                         | 预计净工作量 | 出口条件                                       |
| ------ | ---------------------------- | -----------: | ---------------------------------------------- |
| M0     | 当前版本真相与脏工作树隔离   |     0.5–1 天 | HEAD、开关、49 点路径、旧工件差异可机器读取    |
| M1     | 客户样本验证 E2E 闭环        |       1–2 天 | 导入到导出全流程通过，失败/取消/权限也验证     |
| M2     | 规则准确性、Golden、成本门禁 |       3–5 天 | 高风险误报收口，20 例报告与 Golden gate 可复跑 |
| M3     | 默认开关、回滚与发布候选     |       1–2 天 | 演练成功，当前 release gate 通过或明确豁免     |

---

### Task 1: 建立当前版本清单与静态工件防陈旧机制

**Files:**

- Create: `backend/scripts/build_luxian_0609_runtime_manifest.py`
- Create: `backend/tests/unit/test_luxian_0609_runtime_manifest.py`
- Modify: `backend/app/services/sample_validation_rule_sets.py`
- Test: `backend/tests/unit/test_qc_sample_pools_router.py`

**Step 1: 写失败测试**

为 runtime manifest 定义安全输出：

```python
def test_runtime_manifest_is_bound_to_head_and_flags():
    manifest = build_runtime_manifest(
        git_head="abc123",
        settings=_settings(),
        rule_catalog=_catalog_49(),
    )
    assert manifest["schema_version"] == "lx0609-runtime-manifest-v1"
    assert manifest["git_head"] == "abc123"
    assert manifest["customer_rule_count"] == 49
    assert manifest["flags"]["native_consultation"] is False
    assert "api_key" not in repr(manifest).lower()
```

再为 `sample_validation_rule_sets.py` 增加测试：release/evaluation 工件的 `git_head` 与当前 manifest 不一致时，页面元数据必须显示 `stale`，不能继续显示“当前正式口径”。

**Step 2: 运行 RED**

```powershell
cd backend
python -m pytest tests/unit/test_luxian_0609_runtime_manifest.py tests/unit/test_qc_sample_pools_router.py -k "runtime_manifest or stale" -q --confcutdir=tests/unit
```

Expected: FAIL，缺少 manifest 和 stale 判定。

**Step 3: 最小实现**

manifest 只包含：

- git HEAD；
- 49 个客户规则 ID、族、执行路径（native/compat/gate-only）；
- 与 LX0609 相关的布尔开关；-规则包版本、模型名称、策略版本；
- 生成时间和 schema version。

禁止包含环境变量原值、API key、数据库 URL、患者信息或原始文本。

**Step 4: GREEN 与提交**

```powershell
python -m pytest tests/unit/test_luxian_0609_runtime_manifest.py tests/unit/test_qc_sample_pools_router.py -q --confcutdir=tests/unit
git add backend/scripts/build_luxian_0609_runtime_manifest.py backend/tests/unit/test_luxian_0609_runtime_manifest.py backend/app/services/sample_validation_rule_sets.py backend/tests/unit/test_qc_sample_pools_router.py
git commit -m "绑定0609验收工件与运行版本"
```

### Task 2: 重新生成当前 HEAD 的验收工件流水线

**Files:**

- Modify: `scripts/qc/run_luxian_0609_release_gate.py`
- Modify: `scripts/qc/build_luxian_0609_page_closure_evidence.py`
- Modify: `scripts/qc/evaluate_luxian_0609_rules.py`
- Create: `backend/tests/unit/test_luxian_0609_release_artifact_freshness.py`
- Update generated artifacts only after acceptance: `docs/0602/luxian_0609_*.json`

**Step 1: 写失败测试**

要求每个工件都有：

```json
{
  "schema_version": "...",
  "generated_at": "...",
  "git_head": "...",
  "runtime_manifest_hash": "...",
  "evidence_scope": "synthetic|real|mixed"
}
```

工件缺字段、HEAD 不一致、Golden 含 `pending` 却声称 ready，release gate 必须失败。

**Step 2: 运行 RED**

```powershell
cd backend
python -m pytest tests/unit/test_luxian_0609_release_artifact_freshness.py -q --confcutdir=tests/unit
```

**Step 3: 实现统一生成顺序**

```text
runtime manifest
→ catalog audit
→ candidate coverage
→ golden/evaluation
→ customer sample page evidence
→ release gate
```

每个脚本读取上一步 hash，不允许读取失败后保留的旧输出冒充新结果。生成文件前先在临时目录完成校验，再由脚本原子替换目标工件。

**Step 4: 运行与提交**

```powershell
python -m pytest tests/unit/test_luxian_0609_release_artifact_freshness.py -q --confcutdir=tests/unit
python ..\scripts\qc\run_luxian_0609_release_gate.py
git add scripts/qc backend/tests/unit/test_luxian_0609_release_artifact_freshness.py
git commit -m "重建0609版本化验收流水线"
```

生成的 `docs/0602` 工件单独审查、单独提交，不与代码混合。

### Task 3: 固化客户样本验证 API 合同

**Files:**

- Modify: `backend/app/routers/qc_sample_pools.py`
- Modify: `backend/app/services/custom_qc_sample_pool_service.py`
- Test: `backend/tests/unit/test_qc_sample_pools_router.py`
- Test: `backend/tests/unit/test_custom_qc_sample_pool_service.py`

**Step 1: 补 API 合同测试**

覆盖：

- 未匹配、歧义、未同步、bundle 未就绪不能发起任务；
- 指定 LX0609 规则只影响执行范围，不扩展到全 49；
- 规则族父任务的 `child_job_ids/family_scopes` 数量和顺序一致；
- 相同用户、样本、规则范围在去重窗口内不能创建重复任务；
- 非 customer 模式拒绝 `selected_rule_ids`；
- 空规则、非法规则、无权限、无可执行病历返回明确 4xx；
- 同步只写本地状态，不调用客户源写接口。

**Step 2: 运行 RED**

```powershell
cd backend
python -m pytest tests/unit/test_qc_sample_pools_router.py tests/unit/test_custom_qc_sample_pool_service.py -q --confcutdir=tests/unit
```

**Step 3: 最小修复**

只修 API/服务契约缺口；不改规则判断、不改页面视觉。统一响应中增加安全 `operation_ref` 与 `execution_scope_hash`，供任务去重和审计使用，不返回三坐标。

**Step 4: GREEN 与提交**

```powershell
python -m pytest tests/unit/test_qc_sample_pools_router.py tests/unit/test_custom_qc_sample_pool_service.py -q --confcutdir=tests/unit
git add backend/app/routers/qc_sample_pools.py backend/app/services/custom_qc_sample_pool_service.py backend/tests/unit/test_qc_sample_pools_router.py backend/tests/unit/test_custom_qc_sample_pool_service.py
git commit -m "固化客户样本验证任务合同"
```

### Task 4: 客户样本验证前端流程与状态语义收口

**Files:**

- Modify: `src/views/workstation-v4/CustomerSampleValidationView.vue`
- Modify: `src/services/manual-case-sample-service.ts`
- Modify: `src/views/workstation-v4/customer-sample-validation/types.ts`
- Test: `tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts`
- Test: `tests/unit/services/manual-case-sample-service.spec.ts`

**Step 1: 写失败测试**

覆盖页面真实行为：

- 选中 5 条规则，提交请求只包含这 5 条；
- 总任务展示 7 个质控族子任务时，文案不把它们说成 7 份病历；
- 运行中禁止重复提交；失败时保留用户选择并允许重试；
- 未匹配/未同步/未 bundle 病历说明阻塞原因；
- 任务状态优先级：异常/不合规 → 数据不足/建议态 → 合规 → 不适用；
- `ai_suggested_non_compliant` 不计入确定不合规；
- stale release metadata 明确显示“验收工件待更新”。

**Step 2: 运行 RED**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/services/manual-case-sample-service.spec.ts
```

**Step 3: 最小实现**

保持现有页面布局，只调整 DTO 边界、状态分类、提示和任务去重交互。不要借此重构整个 6000+ 行页面；若逻辑必须抽离，只抽 `taskStatus`、`ruleScope`、`releaseFreshness` 三个纯函数模块并各自测试。

**Step 4: 验证与提交**

```powershell
npm run test:unit -- tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/services/manual-case-sample-service.spec.ts
npm run type-check
npm run check:encoding
git add src/views/workstation-v4/CustomerSampleValidationView.vue src/services/manual-case-sample-service.ts src/views/workstation-v4/customer-sample-validation/types.ts tests/unit/views/workstation-v4/CustomerSampleValidationView.spec.ts tests/unit/services/manual-case-sample-service.spec.ts
git commit -m "收口客户样本验证运行状态"
```

### Task 5: 建立可长期复跑的客户样本 E2E 验收器

**Files:**

- Create: `backend/scripts/run_customer_sample_validation_e2e.py`
- Create: `backend/tests/unit/test_customer_sample_validation_e2e.py`
- Create: `docs/acceptance/customer-sample-validation-e2e.md`

**Step 1: 写失败测试**

验收器必须支持：

- `--dry-run`：只检查样本/规则/服务就绪，不写任务；
- `--fixture-pool`：仅使用隔离测试样本池；
- `--selected-rule-ids`：显式限定 LX0609 规则；
- `--output`：仅输出安全 ledger；
- 没有 `--allow-local-writes` 时禁止导入、同步、创建任务；
- 输出不包含患者身份、正文、原始时间、SQL、prompt 或 raw response。

**Step 2: 运行 RED**

```powershell
cd backend
python -m pytest tests/unit/test_customer_sample_validation_e2e.py -q --confcutdir=tests/unit
```

**Step 3: 实现五段式验收**

```text
preflight → fixture/import → match/sync → run/poll → review/export/privacy
```

所有阶段记录固定状态枚举和耗时；失败后停止，不继续制造下游任务。

**Step 4: 受控执行**

先 dry-run，再在隔离本地测试库中明确启用本地写：

```powershell
python scripts/run_customer_sample_validation_e2e.py --dry-run --fixture-pool lx0609-e2e-v1
python scripts/run_customer_sample_validation_e2e.py --fixture-pool lx0609-e2e-v1 --selected-rule-ids LX0609-001,LX0609-017,LX0609-029 --allow-local-writes --output tmp-safe-e2e.json
```

不得把 `tmp-safe-e2e.json` 提交。

**Step 5: 提交**

```powershell
git add backend/scripts/run_customer_sample_validation_e2e.py backend/tests/unit/test_customer_sample_validation_e2e.py docs/acceptance/customer-sample-validation-e2e.md
git commit -m "新增客户样本验证端到端验收器"
```

### Task 6: 结果隐私、复核与导出一致性

**Files:**

- Modify: `backend/app/services/luxian_0609_result_review_service.py`
- Modify: `backend/app/services/custom_qc_workspace_service.py`
- Modify: `backend/app/routers/qc_sichuan.py`
- Modify: `src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue`
- Test: `backend/tests/unit/test_luxian_0609_result_review_service.py`
- Test: `backend/tests/unit/test_qc_sichuan_result_review.py`
- Test: `tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts`

**Step 1: 写失败测试**

同一结果在 API、复核报告、HTML/CSV/XLSX 导出、前端抽屉中必须具有一致状态与 reason code。测试禁止出现：

- `LLM`、`prompt`、`raw_response`、`medical_text`、`record_content`、`documents`、`bundle`；
- 患者三坐标、姓名、证件、电话；
- `data_gap` 被显示成缺陷；
- `ai_suggested_non_compliant` 被统计为确定不合规。

**Step 2: 运行 RED**

```powershell
cd backend
python -m pytest tests/unit/test_luxian_0609_result_review_service.py tests/unit/test_qc_sichuan_result_review.py -q --confcutdir=tests/unit
cd ..
npm run test:unit -- tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
```

**Step 3: 最小修复与提交**

只在唯一 DTO/formatter 边界做安全化，禁止每个页面各写一套关键词清洗。

```powershell
git add backend/app/services/luxian_0609_result_review_service.py backend/app/services/custom_qc_workspace_service.py backend/app/routers/qc_sichuan.py src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue backend/tests/unit/test_luxian_0609_result_review_service.py backend/tests/unit/test_qc_sichuan_result_review.py tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
git commit -m "统一样本验证结果安全边界"
```

### Task 7: 建立规则级 Golden 台账和高风险误报门禁

**Files:**

- Modify: `backend/scripts/build_luxian_0609_golden_ledger.py`
- Modify: `backend/scripts/run_luxian_0609_golden_gate.py`
- Modify: `backend/scripts/run_luxian_0609_preproduction_benchmark20.py`
- Test: corresponding `backend/tests/unit/test_luxian_0609_*golden*.py`
- Artifact input: `docs/0602/泸县0609质控点-golden-cases.json`

**Step 1: 固定 Golden 合同**

每条 case 只保存安全 ID、规则、期望状态、受控 reason、证据来源类型、人工审阅状态和策略版本。原文只在授权审阅会话内使用，不写入 ledger。

**Step 2: 分批补样本**

按优先级而非规则编号：

1. 会产生确定 `non_compliant` 的高风险规则；
2. 共享时间/文书投影根因的确定性规则；
3. 需要一次裁剪 LLM 的语义规则；
4. 稀有事件和上游数据受限规则。

每批 1–3 条，至少含：适用正例、适用反例、来源不足或边界例。无真实阴性时允许合成，但必须标注 `synthetic`，不能计入真实准确率。

**Step 3: 门禁指标**

- 高风险 `non_compliant` 精确率 ≥ 95%；
- 总体状态一致率 ≥ 90%，但 `data_gap/evaluation_unknown` 单独统计；
- technical error < 1%；
- 无触发规则 0 模型调用；
- 每规则/每病例调用和 token 不高于批准预算；
- 同输入三次运行的确定状态稳定率 ≥ 95%。

**Step 4: 固定20例基准**

```powershell
cd backend
python scripts/run_luxian_0609_preproduction_benchmark20.py --help
python scripts/run_luxian_0609_golden_gate.py --help
```

先按脚本实际参数执行 dry/read-only，再生成安全 ledger。不得凭空猜参数；不得输出或提交真实正文。

**Step 5: 提交代码和人工工件分离**

```powershell
git commit -m "完善0609规则级Golden门禁"
```

Golden 人工结论单独提交，提交信息注明样本类型和审阅范围。

### Task 8: 性能、调用与 token 归因闭环

**Files:**

- Modify: `backend/app/services/luxian_0609/execution.py`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py`
- Modify: `backend/scripts/run_luxian_0609_preproduction_benchmark20.py`
- Test: `backend/tests/unit/test_luxian_0609_mainline_services.py`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`

**Step 1: 写失败测试**

每个 batch/病例/质控族至少能统计：

```json
{
  "llm_call_count": 0,
  "prompt_tokens": 0,
  "completion_tokens": 0,
  "total_tokens": 0,
  "covered_customer_rule_ids": [],
  "latency_ms": 0
}
```

不要求逐 prompt 明细；一次调用覆盖多个规则时必须列出覆盖规则 ID。自动分包探测只允许离线基准，线上使用固定包大小，解析失败才拆包或单条重试。

**Step 2: GREEN 条件**

- `total_tokens == prompt_tokens + completion_tokens`；
- 所有调用均可归属到病例和规则集合；
- 未调用模型的病例为显式 0，不是字段缺失；
- 失败重试计入调用数和 token；
- 客户输出只显示聚合成本，不显示 prompt。

**Step 3: 运行测试与提交**

```powershell
cd backend
python -m pytest tests/unit/test_luxian_0609_mainline_services.py tests/unit/test_luxian_0609_result_aggregator.py -q --confcutdir=tests/unit
git commit -m "补齐0609模型调用与成本归因"
```

### Task 9: Feature flag、回滚与发布演练

**Files:**

- Modify: `backend/app/core/settings.py`
- Modify: `backend/app/services/luxian_0609/native_package.py`
- Modify: `backend/app/services/luxian_0609/execution.py`
- Test: `backend/tests/unit/test_settings_llm_env_alias.py`
- Test: `backend/tests/unit/test_luxian_0609_native_package.py`
- Create: `docs/operations/luxian-0609-rollout-rollback.md`

**Step 1: 建立规则族开关矩阵**

每族状态只能是：

- `compat`：旧映射主路径；
- `shadow`：原生旁路，不改客户结果；
- `native`：原生主路径，旧路径为回退。

禁止多个布尔开关形成无法解释的组合；若保留既有布尔设置，启动时必须解析成唯一族状态并输出安全 manifest。

**Step 2: 回滚测试**

- native → compat 不改客户规则顺序/数量；
- 回滚不需要数据库 migration；
- 正在运行的任务固定启动时策略，不因中途改环境变量而混用路径；
- 回滚后新任务走 compat，旧任务仍可查看结果。

**Step 3: 本地演练**

仅在本地开发环境：启动受控实例，分别运行 shadow/native/compat 的 Fast5，比较状态、调用、耗时和客户 DTO；然后恢复默认配置。

**Step 4: 提交**

```powershell
git add backend/app/core/settings.py backend/app/services/luxian_0609/native_package.py backend/app/services/luxian_0609/execution.py backend/tests/unit/test_settings_llm_env_alias.py backend/tests/unit/test_luxian_0609_native_package.py docs/operations/luxian-0609-rollout-rollback.md
git commit -m "完善0609分族发布与回滚策略"
```

### Task 10: 发布候选总验收

**Files:**

- Update: `docs/0602/luxian_0609_release_gate.json`
- Update: `docs/0602/luxian_0609_qc_eval.json`
- Update: `docs/0602/luxian_0609_customer_sample_page_evidence.json`
- Create: `docs/acceptance/2026-07-luxian-0609-release-candidate.md`

**Step 1: 运行工程检查**

```powershell
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
cd backend
python -m pytest tests/unit/test_qc_sample_pools_router.py tests/unit/test_custom_qc_sample_pool_service.py tests/unit/test_luxian_0609_mainline_services.py tests/unit/test_luxian_0609_result_aggregator.py -q --confcutdir=tests/unit
```

**Step 2: 并发运行客户样本 E2E 与固定 10 例 benchmark**

仅使用隔离样本/明确授权数据，保留安全 ledger。检查：

- 固定 10 例任务全部终态，并使用受控并发度避免模型限流污染耗时数据；
- 结果数量 = 病例 × 选中客户规则数量；
- 无敏感泄漏；
- 失败、取消、重试、复核、导出均有证据；
- 准确性和成本门禁满足；
- 回滚演练通过。

**Step 3: 生成当前 release gate**

release gate 报告必须包含当前 HEAD、runtime manifest hash、模型/策略版本和样本范围。任何旧工件、pending 人工标签或无来源准确率都必须阻止自动宣称 ready。

**Step 4: 人工批准后提交**

```powershell
git add docs/0602/luxian_0609_release_gate.json docs/0602/luxian_0609_qc_eval.json docs/0602/luxian_0609_customer_sample_page_evidence.json docs/acceptance/2026-07-luxian-0609-release-candidate.md
git commit -m "形成0609客户样本验证发布候选"
```

不自动 push；由用户确认后再推送。

## 三、执行纪律

- 每个 Task 单独分支/工作树或至少单独 commit；开始前记录 `git status`，精确暂存文件。
- 主协调 Agent 亲自审查关键 diff、状态映射、模型输入边界、真实样本结果和 token；不得仅凭测试数量接受。
- 实现 Agent 只执行已明确任务和文件白名单；测试 Agent 独立证伪。
- 每 1–2 个业务点形成一个闭环，不同时修改规则逻辑、任务架构和 UI。
- 遇到结构化字段/确定时间/精确存在性用 Python；一个小闭环内 Python 无法稳定处理语义或跨文书关联时，立即切换裁剪 LLM，并锁定输入、枚举、失败语义、调用/token 上限和真实验收集。

## 四、建议技能

- `@executing-plans`：逐 Task 执行本计划。
- `@Code`：编码、测试、精确提交。
- `@diagnosing-bugs`：任务、投影、状态或性能异常。
- `@medqc-workstation-design`：Task 4/6 的页面与结果 UI。
- `@architecture-designer`：仅在 Task 9 的开关/回滚边界确需调整时使用。
