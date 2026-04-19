# 终末内涵质控双轨 POC Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `/workstation-v4/records/final` 落地“快速初筛 + 深度复核”双轨终末内涵质控 POC，先解决默认批量模式的时间、成本和稳定性问题。

**Architecture:** 默认批量链路新增 `fast_screen` 执行模式，按文书域和判断层次固定分包，禁用 `fallback / single retry / selective refine`，失败直接落 `uncertain`。精审能力保留在单病历或问题点选场景，不再阻塞首轮批量返回。

**Tech Stack:** FastAPI, SQLAlchemy, Ant Design Vue, Vue 3, TypeScript, pytest, npm scripts

---

## 实施前提

### 约束 1：不要混提当前观测补丁

当前工作区已经存在一批**未提交**的观测实验改动：

- `apps/medqc-web/backend/app/routers/qc_sichuan.py`
- `apps/medqc-web/backend/app/services/qc_llm_client.py`
- `apps/medqc-web/backend/app/services/qc_rule_orchestrator.py`
- `apps/medqc-web/backend/app/services/sichuan_qc_service.py`
- `apps/medqc-web/backend/app/services/unified_rule_engine.py`
- `apps/medqc-web/backend/tests/unit/test_qc_llm_client.py`
- `apps/medqc-web/backend/tests/unit/test_unified_rule_engine.py`
- `apps/medqc-web/backend/scripts/compare_final_qc_models_2248248.py`

本计划默认：

1. 先把双轨 POC 功能单独实现。
2. 观测补丁后续单独提交，不与 POC 主功能混在一起。

### 约束 2：POC 只覆盖终末病历首批 12 条内涵规则

规则集固定为 `sc_content_v1`：

- `SC-023`
- `SC-024`
- `SC-025`
- `SC-026`
- `SC-027`
- `SC-032`
- `SC-033`
- `SC-036`
- `SC-121`
- `SC-122`
- `SC-123`
- `SC-125`

---

## Task 0: 稳定工作区并切分提交边界

**Files:**

- Modify: `apps/medqc-web/docs/plans/2026-04-19-final-intrinsic-qc-dual-track-poc.md`

**Step 1: 记录当前未提交实验改动**

Run:

```bash
git status --short
```

Expected:

- 只看到观测实验相关文件处于修改状态

**Step 2: 明确本轮 POC 功能提交白名单**

本轮 POC 只允许修改以下区域：

- 后端执行模式与分包定义
- 终末页前端入口和展示
- POC 单元测试 / 集成测试
- `docs/0418/QC` 下 POC 文档

**Step 3: 禁止把观测脚本混入 POC 提交**

不要把以下文件加入本轮 POC commit：

- `apps/medqc-web/backend/scripts/compare_final_qc_models_2248248.py`
- `qc_llm_client.py` 中仅用于 token/COT 观测的变动

**Step 4: 本任务完成后再进入功能开发**

**Step 5: Commit**

此任务不单独提交，作为后续任务执行前置检查。

---

## Task 1: 新增快速初筛分包定义模块

**Files:**

- Create: `apps/medqc-web/backend/app/services/fast_screen_qc.py`
- Test: `apps/medqc-web/backend/tests/unit/test_fast_screen_qc.py`

**Step 1: 写失败测试，固定 12 条规则的分包定义**

测试覆盖：

1. `sc_content_v1` 的快速初筛固定分包为 4 包：
   - 首次病程 A：`SC-023, SC-024`
   - 首次病程 B：`SC-025, SC-026, SC-027`
   - 日常病程：`SC-032, SC-033, SC-036`
   - 出院记录：`SC-121, SC-122, SC-123, SC-125`
2. 每包规则数 `<= 10`
3. 包信息中明确：
   - `document_type`
   - `rule_ids`
   - `allow_retry = false`
   - `allow_refine = false`

示例测试结构：

```python
def test_sc_content_v1_fast_screen_packages_should_be_fixed():
    packages = build_fast_screen_packages("sc_content_v1")
    assert [pkg["rule_ids"] for pkg in packages] == [
        ["SC-023", "SC-024"],
        ["SC-025", "SC-026", "SC-027"],
        ["SC-032", "SC-033", "SC-036"],
        ["SC-121", "SC-122", "SC-123", "SC-125"],
    ]
```

**Step 2: 运行测试确认失败**

Run:

```bash
py -3.10 -m pytest -q apps/medqc-web/backend/tests/unit/test_fast_screen_qc.py
```

Expected:

- FAIL，提示模块或函数不存在

**Step 3: 最小实现**

在 `fast_screen_qc.py` 中实现：

- `FAST_SCREEN_RULE_PACKAGES`
- `build_fast_screen_packages(rule_set_key: str) -> list[dict[str, Any]]`
- `is_fast_screen_mode(execution_mode: str) -> bool`

返回结构示例：

```python
{
    "package_key": "first_course_features",
    "document_type": "首次病程记录",
    "rule_ids": ["SC-023", "SC-024"],
    "allow_retry": False,
    "allow_refine": False,
}
```

**Step 4: 运行测试确认通过**

Run:

```bash
py -3.10 -m pytest -q apps/medqc-web/backend/tests/unit/test_fast_screen_qc.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add apps/medqc-web/backend/app/services/fast_screen_qc.py apps/medqc-web/backend/tests/unit/test_fast_screen_qc.py
git commit -m "新增终末内涵质控快速初筛分包定义"
```

---

## Task 2: 为批量任务创建接口增加快速初筛模式字段

**Files:**

- Modify: `apps/medqc-web/backend/app/routers/qc_sichuan.py`
- Modify: `apps/medqc-web/backend/app/services/qc_rule_sets.py`
- Test: `apps/medqc-web/backend/tests/unit/test_qc_sichuan_batch_throughput.py`

**Step 1: 写失败测试**

覆盖：

1. `POST /workspace/batch-jobs` 支持 `execution_mode="fast_screen"`
2. 创建任务时 `filters` 中保存：
   - `execution_mode`
   - `rule_set_key`
   - `bucket_strategy`
   - `batch_output_mode`
3. `fast_screen` 模式下强制：
   - `enable_selective_refine = false`
   - `max_refine_candidates = 0`

**Step 2: 运行测试确认失败**

Run:

```bash
py -3.10 -m pytest -q apps/medqc-web/backend/tests/unit/test_qc_sichuan_batch_throughput.py
```

Expected:

- FAIL，接口或 filters 字段不匹配

**Step 3: 最小实现**

在 `qc_sichuan.py` 中：

1. 给创建任务 payload 增加：
   - `execution_mode?: "default" | "fast_screen"`
2. 当 `execution_mode == "fast_screen"` 时：
   - 保存 `execution_mode`
   - 强制禁用 refine
   - 不走现有动态回退策略

在 `qc_rule_sets.py` 中：

1. 给 `sc_content_v1` 增加一个辅助字段，表明它可用于 `fast_screen`

**Step 4: 运行测试确认通过**

Run:

```bash
py -3.10 -m pytest -q apps/medqc-web/backend/tests/unit/test_qc_sichuan_batch_throughput.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add apps/medqc-web/backend/app/routers/qc_sichuan.py apps/medqc-web/backend/app/services/qc_rule_sets.py apps/medqc-web/backend/tests/unit/test_qc_sichuan_batch_throughput.py
git commit -m "为终末批量任务增加快速初筛模式"
```

---

## Task 3: 在后端增加快速初筛执行分支

**Files:**

- Modify: `apps/medqc-web/backend/app/services/sichuan_qc_service.py`
- Modify: `apps/medqc-web/backend/app/services/qc_input_adapters/running_final_bundle_runtime.py`
- Modify: `apps/medqc-web/backend/app/services/unified_rule_engine.py`
- Test: `apps/medqc-web/backend/tests/unit/test_running_final_bundle_orchestrated.py`
- Test: `apps/medqc-web/backend/tests/unit/test_unified_rule_engine_guardrails.py`

**Step 1: 写失败测试**

覆盖：

1. `execution_mode="fast_screen"` 时，不走 orchestrator 的动态 pack/fallback/retry/refine
2. 只按固定分包调用 `evaluate_batch_compact`
3. parse 失败或缺 rule 时，对应规则直接 `uncertain`
4. 批量输出必须走 `minimal` 模式

**Step 2: 运行测试确认失败**

Run:

```bash
py -3.10 -m pytest -q apps/medqc-web/backend/tests/unit/test_running_final_bundle_orchestrated.py apps/medqc-web/backend/tests/unit/test_unified_rule_engine_guardrails.py
```

Expected:

- FAIL，说明当前仍走现有动态批量链路

**Step 3: 最小实现**

在 `sichuan_qc_service.py` 中新增或内联：

- `_evaluate_fast_screen_packages(...)`

逻辑：

1. 读取 final bundle 文书
2. 按 `fast_screen_qc.py` 固定分包
3. 每包直接调用 `rule_engine.evaluate_batch_compact(...)`
4. 不允许：
   - fallback
   - single retry
   - selective refine
5. 对 parse/missing 问题规则直接降为 `uncertain`

在 `running_final_bundle_runtime.py` 中透传 `execution_mode`

在 `unified_rule_engine.py` 中只保留：

- 最小输出
- 结构解析
- 不额外重试

**Step 4: 运行测试确认通过**

Run:

```bash
py -3.10 -m pytest -q apps/medqc-web/backend/tests/unit/test_running_final_bundle_orchestrated.py apps/medqc-web/backend/tests/unit/test_unified_rule_engine_guardrails.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add apps/medqc-web/backend/app/services/sichuan_qc_service.py apps/medqc-web/backend/app/services/qc_input_adapters/running_final_bundle_runtime.py apps/medqc-web/backend/app/services/unified_rule_engine.py apps/medqc-web/backend/tests/unit/test_running_final_bundle_orchestrated.py apps/medqc-web/backend/tests/unit/test_unified_rule_engine_guardrails.py
git commit -m "新增终末内涵质控快速初筛执行分支"
```

---

## Task 4: 输出协议压缩为首轮短版结果

**Files:**

- Modify: `apps/medqc-web/backend/app/services/unified_rule_engine.py`
- Modify: `apps/medqc-web/backend/app/services/custom_qc_workspace_service.py`
- Test: `apps/medqc-web/backend/tests/unit/test_unified_rule_engine_guardrails.py`

**Step 1: 写失败测试**

覆盖：

1. `batch_output_mode="minimal"` 时，每条问题仅保留：
   - `finding_short`
   - `evidence_short`
   - `suggestion_short`
2. 长文 findings/evidence/suggestion 被截断或移除
3. 导出默认使用短版字段

**Step 2: 运行测试确认失败**

Run:

```bash
py -3.10 -m pytest -q apps/medqc-web/backend/tests/unit/test_unified_rule_engine_guardrails.py
```

Expected:

- FAIL

**Step 3: 最小实现**

在 `unified_rule_engine.py` 中新增短版字段生成逻辑：

```python
{
    "finding_short": "...",
    "evidence_short": "...",
    "suggestion_short": "...",
}
```

规则：

- 每字段控制在短摘要
- 首轮批量页面只读短版字段

**Step 4: 运行测试确认通过**

Run:

```bash
py -3.10 -m pytest -q apps/medqc-web/backend/tests/unit/test_unified_rule_engine_guardrails.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add apps/medqc-web/backend/app/services/unified_rule_engine.py apps/medqc-web/backend/app/services/custom_qc_workspace_service.py apps/medqc-web/backend/tests/unit/test_unified_rule_engine_guardrails.py
git commit -m "压缩终末内涵质控首轮短版输出"
```

---

## Task 5: 终末页接入快速初筛入口

**Files:**

- Modify: `apps/medqc-web/src/views/dashboard/records/FinalRecordsView.vue`
- Modify: `apps/medqc-web/src/services/sichuan-rule-workspace-service.ts`
- Modify: `apps/medqc-web/src/views/workstation-v4/semantic-rules/types.ts`
- Test: `apps/medqc-web/tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts`

**Step 1: 写失败测试**

覆盖：

1. 终末页默认发起任务时传：
   - `execution_mode = "fast_screen"`
2. 默认文案改成：
   - `内涵质控快速初筛`
3. 结果详情优先展示问题卡片和待复核摘要

**Step 2: 运行测试确认失败**

Run:

```bash
npm run test:unit -- tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
```

Expected:

- FAIL

**Step 3: 最小实现**

在 `FinalRecordsView.vue`：

1. 默认规则集仍为 `sc_content_v1`
2. 创建任务时附带：
   - `execution_mode: "fast_screen"`

在类型文件中补齐：

- `execution_mode`
- `finding_short`
- `evidence_short`
- `suggestion_short`

**Step 4: 运行测试确认通过**

Run:

```bash
npm run test:unit -- tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add apps/medqc-web/src/views/dashboard/records/FinalRecordsView.vue apps/medqc-web/src/services/sichuan-rule-workspace-service.ts apps/medqc-web/src/views/workstation-v4/semantic-rules/types.ts apps/medqc-web/tests/unit/views/workstation-v4/semantic-rules/SemanticRulesBatchResultDrawer.spec.ts
git commit -m "终末页接入内涵质控快速初筛入口"
```

---

## Task 6: 结果抽屉按“快速初筛 / 深度复核”双层展示

**Files:**

- Modify: `apps/medqc-web/src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue`
- Modify: `apps/medqc-web/src/views/workstation-v4/utils/structuredQc.ts`
- Test: `apps/medqc-web/tests/unit/views/workstation-v4/structuredQc.spec.ts`

**Step 1: 写失败测试**

覆盖：

1. 快速初筛任务默认只展示：
   - 状态横幅
   - 核心 KPI
   - 问题/待复核卡片
2. 问题卡片优先读取短版字段
3. 高级调试信息折叠

**Step 2: 运行测试确认失败**

Run:

```bash
npm run test:unit -- tests/unit/views/workstation-v4/structuredQc.spec.ts
```

Expected:

- FAIL

**Step 3: 最小实现**

在抽屉页中新增：

- `执行模式 = 快速初筛` 的文案与徽标
- 问题卡片优先用 `finding_short / evidence_short / suggestion_short`
- 提供“深度复核”按钮占位

**Step 4: 运行测试确认通过**

Run:

```bash
npm run test:unit -- tests/unit/views/workstation-v4/structuredQc.spec.ts
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add apps/medqc-web/src/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue apps/medqc-web/src/views/workstation-v4/utils/structuredQc.ts apps/medqc-web/tests/unit/views/workstation-v4/structuredQc.spec.ts
git commit -m "按快速初筛模式精简终末批量任务结果展示"
```

---

## Task 7: 小样本验证与文档回填

**Files:**

- Modify: `apps/medqc-web/docs/0418/QC/终末内涵质控双轨POC实施计划.md`
- Modify: `apps/medqc-web/docs/0418/QC/P1a-2248248-完整病历内涵质控深测记录.md`
- Create: `apps/medqc-web/docs/0418/QC/终末内涵质控快速初筛验证记录.md`

**Step 1: 脚本验证**

对至少两份病历执行：

- `2248248`
- `MV2-REAL-001`

记录：

- wall time
- first result latency
- total token
- 问题数 / 待复核数

**Step 2: 回填结果**

把验证结果补到：

- `终末内涵质控双轨POC实施计划.md`
- `终末内涵质控快速初筛验证记录.md`

**Step 3: 运行基础检查**

Run in `apps/medqc-web`:

```bash
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
```

Expected:

- 全部通过

**Step 4: Commit**

```bash
git add apps/medqc-web/docs/0418/QC/终末内涵质控双轨POC实施计划.md apps/medqc-web/docs/0418/QC/P1a-2248248-完整病历内涵质控深测记录.md apps/medqc-web/docs/0418/QC/终末内涵质控快速初筛验证记录.md
git commit -m "补充终末内涵质控快速初筛验证记录"
```

---

## 建议执行顺序

1. `Task 0`
2. `Task 1`
3. `Task 2`
4. `Task 3`
5. `Task 4`
6. `Task 5`
7. `Task 6`
8. `Task 7`

---

## 实施时的硬性约束

1. 不要把当前观测实验补丁与 POC 主功能混提。
2. 不要为了快速过关恢复旧的 fallback 风暴。
3. 快速初筛模式默认不允许自动回退到单条重跑。
4. 快速初筛模式优先服务于：
   - 首轮速度
   - 结果可读
   - 待复核承接灰区

---

## 当前默认假设

本计划默认采用 **Subagent-Driven（当前会话）** 的执行方式，但不额外新建 worktree，直接在当前分支内按任务拆小提交推进。
