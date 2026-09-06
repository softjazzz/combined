# LX0609 核心质控聚合器稳妥收口实施计划

> 2026-09-06 验收节奏已修订：以 [本地优先实施计划](./2026-09-06-lx0609-local-first-convergence.md) 为准。全部计划阶段先本地验收，逐阶段审核提交并继续；客户验收集中在最后执行。下文原有“客户验收完成才进入下一族”“每族等待下一阶段授权”的流程由新计划替代。原有职责边界、行为冻结、失败语义及性能要求继续有效；历史基线数字不代表当前代码统计。

**Goal:** 在不改变现有质控口径、Canonical 合同、API 和前端展示语义的前提下，按完整规则族逐步移除 `luxian_0609_result_aggregator.py` 中的业务判断，使聚合器最终只负责结果装配、排序、去重和统计。

**Architecture:** 延续现有统一执行链，不新增引擎、Bundle、Resolver、状态机、注册中心或隐式 fallback。规则执行器负责适用性、状态、原因码、关键事实并选择 `fact_refs`；Binding 校验引用；规则族结果映射模块校验安全事实合同；公共证据投影组件将引用转换为文书 ID、字段路径和时间；Renderer 只组织声明式文案；Aggregator 只装配 Canonical 结果。

**Tech Stack:** Python 3.10、FastAPI、Pydantic、pytest、现有 LX0609 unified engine、PostgreSQL、Vue 3（仅用于业务入口验收，本计划不改前端）。

---

## 1. 架构决策记录（ADR）

### 决策状态

已批准进入受控实施；每完成一个规则族闭环后必须停止、提交、报告并等待下一阶段授权。

### 证据集合合同补充决策（2026-09-06）

已批准将 `customer_evidence` 解释为去重后的证据坐标集合，数组位置不表示证据优先级、
临床时序或证据角色。行为冻结和三入口验收必须比较证据数量以及
`source_type/source_document_id/field_path/record_time` 坐标集合，不比较数组顺序。

该决策不允许放宽证据真实性、同源性、数量、字段或时间要求，也不允许为展示排序新增
规则号分支。若以后需要“关键证据优先”等有业务含义的展示顺序，必须另立公共证据角色
合同任务，不得用 SHA 顺序、来源键字典序或材料序推断临床优先级。

### 当前证据

- `backend/app/services/luxian_0609_result_aggregator.py` 当前约 5613 行。
- 文件仍直接包含约 63 个规则号、184 次规则号引用。
- 基础时限族和会诊族的聚合器规则号分支已归零，说明按规则族迁移的路径可行。
- 生产规则 `076/077` 已证明可以不修改聚合器、保存、API DTO 和前端状态解释完成扩展。
- 聚合器中剩余规则号引用按当前规则族粗分：

| 规则族         | 规则                   | 聚合器规则号引用数 | 当前判断                                     |
| -------------- | ---------------------- | -----------------: | -------------------------------------------- |
| 检查检验       | 010–012、014–015       |                 44 | 第一优先级；边界集中，已有结果映射模块       |
| 手术麻醉       | 003、024、025、028–040 |                 45 | 第二阶段候选；必须按既有 executor 边界分波次 |
| 输血           | 041–048                |                 36 | 独立闭环候选                                 |
| 扩展文书       | 050–076 中仍有引用者   |                 36 | 范围过大，必须再按完整业务域拆分             |
| 病程质量       | 007–009、016–017       |                 18 | 独立闭环候选                                 |
| 肿瘤病理       | 013、019、026、027     |                  5 | 低风险收尾候选                               |
| 基础时限、会诊 | 已迁移规则             |                  0 | 不重复迁移，只做回归保护                     |

### 选择的方案

采用“行为冻结 → 一个完整规则族等价迁移 → 三入口真实验收 → 停止”的渐进式方案。

不采用以下方案：

1. **按行数机械拆文件**：只能移动代码，不能消除重复业务所有者。
2. **一次性重写聚合器**：回归面覆盖 77 条规则及多个入口，无法可靠证明行为等价。
3. **为迁移新增第二套抽象层**：会让迁移期的双重业务所有者变成永久技术债。
4. **先删全部兼容路径**：未证明客户链路不再使用，发布风险不可接受。

### 不变量

迁移期间必须始终满足：

- `aggregate_luxian_0609_results()` 公开入口保持兼容。
- `LUXIAN_0609_UNIFIED_ENGINE_ENABLED=true` 的生产主链不改变。
- 不修改 Prompt、判定阈值、状态含义和客户结论文案。
- 不新增数据库迁移、API 字段或前端结果解释逻辑。
- 不给 DTO、Prompt、trace 或中间结果新增 SHA/digest。
- 执行器只选择真实 `fact_refs`，不自行拼装客户证据 DTO。
- 公共证据投影是文书 ID、字段路径和时间坐标的唯一所有者。
- 技术失败必须保持 `technical_error`，不得伪装为业务资料问题。

### 固定失败语义

| 场景                                                 | Canonical 状态                        |
| ---------------------------------------------------- | ------------------------------------- |
| 合同不匹配、执行器异常、超时、非法结构、非法事实引用 | `technical_error`                     |
| 已接入数据源缺少判定所需资料                         | `data_gap`                            |
| 事实存在但语义无法可靠判断                           | `uncertain`                           |
| 触发事件不存在或观察窗口尚未成熟                     | 按已批准规则口径进入 `not_applicable` |

## 2. 总体阶段与停止点

```text
阶段 A：冻结剩余业务所有权基线
    ↓ 独立提交，只含测试和文档
阶段 B：检查检验族 010–012、014–015 等价迁移
    ↓ 独立提交，只迁职责、不改口径
阶段 C：检查检验族三入口和性能验收
    ↓ 独立提交，验收通过后停止
阶段 D：按收益逐族迁移旧债
    ↓ 每个规则族重复 A/B/C，不连续扩张
阶段 E：全部规则族迁出后清理通用聚合器
```

任何阶段出现以下情况必须立即停止：

- 需要修改 API DTO、保存结构或前端状态解释才能完成迁移；
- 同一事实需要增加第二个来源解释器；
- 需要新增 fallback 或运行时开关才能维持行为；
- 状态、原因码、客户事实、证据坐标集合或 Prompt 出现非预期漂移；
- 真实模型调用次数或输入 Token 增加；
- 无法把技术失败稳定映射为 `technical_error`。

## 3. 第一闭环：检查检验族 010–012、014–015

第一闭环只处理：

- `LX0609-010`：CT/MRI 检查前病程说明；
- `LX0609-011`：危急检查结果处理；
- `LX0609-012`：CT/MRI 阳性结果 24 小时内分析；
- `LX0609-014`：危急检验结果处理；
- `LX0609-015`：培养阳性结果 24 小时内分析。

已有 `exam_lab_result_mapping.py` 承担该族结果映射，因此优先扩展现有完整职责，除非只读审计证明它无法承载安全事实合同；不得仅为降低聚合器行数新建平行投影模块。

### Task 1：建立剩余业务所有权基线

**Files:**

- Create: `docs/acceptance/2026-09-06-lx0609-aggregator-remaining-ownership-baseline.md`
- Read only: `backend/app/services/luxian_0609_result_aggregator.py`
- Read only: `backend/app/services/luxian_0609/native_exam_lab_execution.py`
- Read only: `backend/app/services/luxian_0609/exam_lab_result_mapping.py`
- Read only: `backend/app/services/luxian_0609/canonical_result_finalizer.py`
- Read only: `backend/app/services/luxian_0609/customer_evidence_enrichment.py`

**Step 1：记录聚合器中的检查检验专属职责**

记录并分类全部 44 次规则号引用，至少区分：

1. 安全事实结构校验；
2. `010` 特殊状态/事实复制；
3. 检查与检验来源类型 allowlist；
4. 文书证据选择和坐标转换；
5. Canonical 装配；
6. 纯历史兼容。

每个分支必须记录“当前事实所有者、迁移后的唯一所有者、删除条件”，不能只记录行号。

**Step 2：记录静态所有权现状，不提交失败守卫**

基线文档记录五条规则当前的规则号出现次数、所属函数和职责分类。提交 A 不创建、跳过或 `xfail` “聚合器分支必须归零”的测试；硬性归零守卫只在迁移提交 B 中新增并立即保持绿色，避免用预期失败制造误导性的绿色基线。

**Step 3：确认通用逻辑白名单**

允许聚合器继续保留：

- 通用结果选择；
- 通用字段复制；
- 通用去重、排序、统计；
- 与规则号无关的敏感字段清理；
- 公开聚合入口。

不允许保留：按 `010/011/012/014/015` 重新判断状态、事实合法性、文书类型或证据坐标。

本任务暂不提交；与 Task 2 的状态语义审计和行为冻结测试一起形成提交 A。

### Task 2：冻结检查检验族现有行为

**Files:**

- Modify: `backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py`
- Modify: `backend/tests/unit/test_luxian_0609_result_aggregator.py`
- Modify: `backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py`
- Create: `backend/tests/integration/test_luxian_0609_exam_lab_family_convergence.py`

**Step 1：先审计批准的状态语义，不合格则停止迁移**

先建立“规则 × 可达状态”矩阵，逐条核对当前生产结果是否符合批准口径：

| 状态              | 可达条件                                               |
| ----------------- | ------------------------------------------------------ |
| `not_applicable`  | 无触发事件，或该规则批准口径明确规定观察窗口未成熟     |
| `compliant`       | 触发事件存在且要求已满足                               |
| `non_compliant`   | 触发事件存在且已有事实证明违反要求                     |
| `data_gap`        | 已接入来源缺少完成判定必需的资料、时间或关联           |
| `uncertain`       | 仅限确实包含语义判断且事实存在、模型无法可靠判断的路径 |
| `technical_error` | 合同错误、执行异常、超时、非法输出或非法引用           |

不得要求每条规则人为产生全部六种状态。每条规则只冻结真实可达状态；不可达状态必须在矩阵中注明原因，家族整体覆盖所有实际可达的批准状态。

如果发现窗口未成熟仍输出 `data_gap`、技术异常仍输出业务状态等口径冲突：

1. 停止本架构迁移；
2. 记录真实病例、当前状态和批准状态；
3. 另建独立业务口径修复闭环；
4. 修复获批并完成回归后重新建立冻结基线；
5. 不得在等价迁移提交 B 中顺便改变状态。

**Step 2：按可达状态矩阵冻结现有行为**

覆盖本族真实可达状态，并额外冻结关键业务形状：无触发事件、正常满足、已证明违反、有医嘱无报告、报告关联不唯一、一次检查多项目、多次同类检查、培养阳性与普通检验并存。

`010` 额外冻结医嘱、检查主记录、报告与病程的一对一关联；`015` 额外冻结培养触发不得混入全血细胞等普通检验。

**Step 3：冻结 Canonical 结果**

对相同输入逐项比较：

- `status`；
- `reason_code`；
- `customer_display_facts`；
- `criterion_results`（如存在）；
- `fact_refs` 指向的语义来源；
- 客户证据的来源类型、真实文书 ID、字段路径和记录时间坐标集合；
- 客户结论和处理建议；
- LLM 调用次数、Prompt 和输入 Token。

测试比较语义与来源定位，不随意断言 SHA。

**Step 4：冻结三种执行入口**

相同病例、相同规则、相同评价时间分别通过：

- 单规则/预生产执行入口；
- 病历池运行或终末批量质控入口；
- 客户样本验证入口。

记录每条规则的实际 `executor_key`，确认三入口走同一 unified execution path，且没有异常回退。

**Step 5：运行冻结测试**

```powershell
Set-Location backend
py -3.10 -m pytest -q tests/unit/test_luxian_0609_native_exam_lab_execution.py tests/unit/test_luxian_0609_result_aggregator.py tests/unit/test_luxian_0609_canonical_result_finalizer.py tests/integration/test_luxian_0609_exam_lab_family_convergence.py
```

预期：迁移前全部冻结行为绿色，且状态语义审计无冲突。若发现业务缺陷，停止迁移并单独修复，不得冻结已知错误后继续搬运。

**Step 6：提交 A——行为冻结**

```powershell
git add -- docs/acceptance/2026-09-06-lx0609-aggregator-remaining-ownership-baseline.md backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py backend/tests/integration/test_luxian_0609_exam_lab_family_convergence.py
git diff --cached --name-only
git commit -m "测试：冻结检查检验质控族现有行为"
```

提交 A 只包含测试和基线文档，不修改任何生产代码，也不包含预期失败、`skip` 或 `xfail` 的归零守卫。

### Task 3：把安全事实合同迁至现有规则族映射模块

**Files:**

- Modify: `backend/app/services/luxian_0609/exam_lab_result_mapping.py`
- Modify: `backend/app/services/luxian_0609/canonical_result_finalizer.py`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py`
- Test: `backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`

**Step 1：先写失败测试**

测试要求 Finalizer 对检查检验族：

- 接受合法安全事实合同；
- 对缺字段、非法枚举、非法引用 fail closed 为 `technical_error`；
- 不把合同错误映射为 `data_gap` 或 `uncertain`；
- 其他尚未迁移规则保持原路径。

**Step 2：实现规则族事实验证**

在 `exam_lab_result_mapping.py` 中增加最小稳定接口，例如：

```python
def validate_exam_lab_customer_display_facts(
    rule_id: str,
    facts: Mapping[str, object],
) -> dict[str, object] | None:
    ...
```

该接口只验证和规范化本规则族已有事实，不重新计算业务状态，不生成客户证据。

**Step 3：接入 Finalizer**

让 `canonical_result_finalizer.py` 将 `010–012、014–015` 识别为由 Finalizer 安全收口的 executor facts；非法合同统一转为 `technical_error`。

**Step 4：删除聚合器旧事实解释**

删除 `safe_luxian_0609_customer_display_facts()` 中该族分支，以及 `_copy_native_customer_fields()`、聚合入口中 `010` 的特殊事实校验和复制分支。

不能把这些分支原样复制到另一个聚合器辅助文件；迁移后事实合同只有规则族映射模块一个所有者。

**Step 5：运行聚焦测试**

```powershell
Set-Location backend
py -3.10 -m pytest -q tests/unit/test_luxian_0609_canonical_result_finalizer.py tests/unit/test_luxian_0609_result_aggregator.py tests/unit/test_luxian_0609_native_exam_lab_execution.py
```

### Task 4：收口 `fact_refs` 与公共证据投影

**Files:**

- Modify if required: `backend/app/services/luxian_0609/native_exam_lab_execution.py`
- Modify if required: `backend/app/services/luxian_0609/exam_lab_fact_extraction.py`
- Reuse first: `backend/app/services/luxian_0609/customer_evidence_enrichment.py`
- Modify: `backend/app/services/luxian_0609_result_aggregator.py`
- Test: `backend/tests/integration/test_luxian_0609_exam_lab_family_convergence.py`

**Step 1：先证明证据投影缺口**

逐条检查 executor 的 `fact_refs` 是否能唯一指向：

- 检查/检验医嘱；
- `exam_master` 或 `labtest_master`；
- `exam_item_report`、`labtest_item_report` 或培养报告；
- 对应病程记录；
- 规则判定使用的权威时间字段。

只有现有公共投影无法表达真实已选引用时，才允许修改 `customer_evidence_enrichment.py`，且修改必须是与规则号无关的公共能力。

**Step 2：执行器只选择引用**

补齐缺失的 `fact_refs`，但不在执行器内拼装 `document_id`、`field_path`、`record_time` 客户 DTO。

**Step 3：Binding 与公共投影校验**

要求 Binding 验证：

- 引用实际存在于本次 snapshot/materials；
- 引用属于同一病历；
- 文书来源类型与事实类型一致；
- 不允许仅凭标题、时间邻近或关键字猜测文书。

**Step 4：删除聚合器规则专属证据策略**

删除 `010–012、014–015` 的来源 allowlist、来源类型转换、source document fallback 和专属证据生成分支。

**Step 5：验证真实定位**

至少覆盖：

- 一次检查一份报告；
- 一次检查多检查项目；
- 多次同类检查；
- 有医嘱无报告；
- 有报告但关联不唯一；
- 培养阳性与普通检验并存。

每项证据必须定位到真实文书 ID、字段和时间，禁止生成 `unknown-report` 或文书级猜测定位。

### Task 5：完成检查检验族聚合器分支归零

**Files:**

- Modify: `backend/app/services/luxian_0609_result_aggregator.py`
- Create: `backend/tests/unit/test_luxian_0609_aggregator_ownership_guard.py`
- Test: `backend/tests/unit/test_luxian_0609_result_aggregator.py`

**Step 1：新增并启用静态硬守卫**

检查聚合器源码不再出现 `LX0609-010/011/012/014/015`。

```python
def test_exam_lab_rule_ids_are_not_interpreted_by_aggregator():
    source = AGGREGATOR_PATH.read_text(encoding="utf-8")
    for rule_id in ("010", "011", "012", "014", "015"):
        assert f'LX0609-{rule_id}' not in source
```

该测试随提交 B 创建，创建时必须立即绿色；不得使用 `skip`、`xfail` 或宽松计数替代归零断言。

**Step 2：确认归零口径**

“归零”必须同时满足：

- 规则号条件分支为 0；
- 规则专属状态解释为 0；
- 规则专属事实结构校验为 0；
- 规则专属证据生成和来源转换为 0；
- Renderer 中没有新增该族业务判断。

聚合器行数下降只是记录项，不是验收目标。

**Step 3：检查生产代码净变化**

报告：

- 聚合器迁移前后行数；
- 新增/扩展模块行数；
- 生产代码净增减；
- 被迁出的完整职责；
- 公开接口变化（预期为无）；
- 仍留在聚合器的规则族职责。

**Step 4：提交 B——行为等价迁移**

```powershell
git add -- backend/app/services/luxian_0609_result_aggregator.py backend/app/services/luxian_0609/exam_lab_result_mapping.py backend/app/services/luxian_0609/canonical_result_finalizer.py backend/app/services/luxian_0609/native_exam_lab_execution.py backend/app/services/luxian_0609/exam_lab_fact_extraction.py backend/app/services/luxian_0609/customer_evidence_enrichment.py backend/tests/unit/test_luxian_0609_aggregator_ownership_guard.py backend/tests/unit/test_luxian_0609_native_exam_lab_execution.py backend/tests/unit/test_luxian_0609_result_aggregator.py backend/tests/unit/test_luxian_0609_canonical_result_finalizer.py backend/tests/integration/test_luxian_0609_exam_lab_family_convergence.py
git diff --cached --name-only
git commit -m "重构：等价迁移检查检验质控族职责"
```

只暂存实际发生变更且属于本闭环的文件。提交 B 不修改业务口径、Prompt 或客户文案。

### Task 6：检查检验族三入口及性能验收

**Files:**

- Create: `docs/acceptance/2026-09-06-lx0609-exam-lab-family-convergence.md`
- Test: all files changed in Tasks 1–5

**Step 1：运行结构与影响范围测试**

```powershell
Set-Location backend
py -3.10 -m pytest -q tests/unit/test_luxian_0609_aggregator_ownership_guard.py tests/unit/test_luxian_0609_native_exam_lab_execution.py tests/unit/test_luxian_0609_result_aggregator.py tests/unit/test_luxian_0609_canonical_result_finalizer.py tests/integration/test_luxian_0609_exam_lab_family_convergence.py
```

再运行 LX0609 unified engine、规则目录、Canonical 保存与客户渲染相关影响范围测试；不得用无关全量测试数量代替业务证据。

**Step 2：按业务覆盖矩阵选择真实病例**

病例数量不作为验收目标。至少五份只是下限；必须持续增加病例，直到覆盖：

- 每条规则至少一份真实适用病例；
- 无触发事件；
- 正常满足；
- 已证明违反；
- 有医嘱无报告；
- 报告关联不唯一；
- 一次检查多项目；
- 多次同类检查；
- 培养阳性与普通检验同时存在。

每个覆盖格记录病例安全引用、触发规则、预期状态、证据来源和实际结果。不得用病例总数替代矩阵完整性。

**Step 3：真实业务入口一致性**

对覆盖矩阵中的相同病例逐一核对三入口：

- `executor_key` 一致；
- Canonical 状态和原因码一致；
- 关键事实一致；
- 证据文书 ID、字段和时间一致；
- 客户结论一致；
- 无旧执行器或聚合兼容结果回退。

**Step 4：性能协议**

确定性 Stub：

- LLM 调用次数完全一致；
- Prompt 和输入 Token 完全一致；
- Canonical 结果完全一致；`customer_evidence` 按已批准的去重坐标集合比较，数组顺序不
  表示业务语义。

性能比较固定使用提交 A 与提交 B 的两个独立 worktree；两个环境使用同一只读数据库快照、相同评价时间、模型、模型参数、环境变量和病例覆盖集。

真实模型：

- 两个 worktree 分别预热；
- 提交 A 与提交 B 交替运行至少 10 次，避免时段和服务波动单边影响；
- 调用次数完全一致；
- 输入 Token 不增加；
- 比较中位耗时，回归不得超过 10%；
- 输出 Token 只记录自然波动，不以单次结果作结论。

对不调用 LLM 的规则，应明确记录 `0 → 0`，不能只写“无明显变化”。

**Step 5：形成验收报告**

报告必须包含：

- 行为等价证据；
- 三入口执行路径；
- 真实病例证据坐标；
- LLM 调用、Token 和耗时；
- 聚合器专属分支归零证明；
- 代码净变化；
- 未迁移遗留职责；
- 回滚提交点。

**Step 6：提交 C——验收记录并停止**

```powershell
git add -- docs/acceptance/2026-09-06-lx0609-exam-lab-family-convergence.md
git diff --cached --name-only
git commit -m "文档：记录检查检验质控族收口验收"
```

提交 C 只记录三入口、真实病例覆盖矩阵和性能结论，不再修改生产逻辑。若验收发现缺陷，不得在提交 C 中修补；回到独立修复闭环处理并重新验收。

只暂存本闭环明确文件；不得把当前工作区中其他前端修改和临时文件带入提交。提交前若命令中的暂存文件列表与预期不符，立即取消提交并核对。

完成后停止，不自动进入下一规则族。

## 4. 后续规则族迁移顺序

后续每个规则族都必须重新执行“基线审计 → 行为冻结 → 等价迁移 → 三入口验收 → 独立提交 → 停止”。建议顺序：

### 第二闭环：输血族 041–049

原因：边界相对集中，当前约 36 次规则号引用，且已有独立 native executor。重点冻结输血事件关联、输血前检查、输血记录与效果评价证据。

### 第三闭环：手术麻醉族，按 executor 边界分波次

不得一次处理全部 16 条规则。先只读审计实际 `executor_key`，再分为：

1. 手术存在性/同步规则；
2. surgery gate；
3. surgery document；
4. `040` MDT。

每个波次都必须形成完整、可独立测试的业务职责；禁止按函数数量碎片化拆分。

### 第四闭环：病程质量族 007–009、016–018、077

重点冻结语义 Prompt、最小上下文、语义枚举、调用次数和真实模型十次性能。`018/077` 当前虽未在聚合器出现，也必须作为同执行器回归范围，防止迁移破坏新规则。

### 第五闭环：肿瘤病理族 013、019、026、027

规则号引用较少，适合在高风险规则族之后作为收尾验证，但仍需证明病理来源和诊断/治疗事件关联的单一所有权。

### 第六阶段：扩展文书族 050–076

当前 executor 覆盖面过大，不能把 27 条规则一次迁移。先做只读领域审计，再按真实完整职责选择小闭环，例如：

- 抗菌药物 054–059；
- 死亡/出院及时性与完整性；
- 交接班、转科、阶段小结 071–074；
- 有创操作 075；
- 其他已证明边界完整的文书域。

这一步只允许复用现有 execution contract；除非出现两个已发生、独立且无法由现有边界表达的问题，否则不得新增框架层。

## 5. 最终聚合器清理

只有所有旧规则族完成迁移后才能执行：

1. 删除已无调用者的 `safe_luxian_0609_customer_display_facts()`；
2. 删除按规则号选择证据、复制事实和修正状态的遗留函数；
3. 保留 `aggregate_luxian_0609_results()`、通用装配、排序、去重、统计和敏感字段通用过滤；
4. 如仍存在至少 250 行连续、完整且可独立测试的通用装配职责，才评审是否迁入一个深模块；
5. 不创建只有转发作用的空壳文件，不以最终行数作为成功标准。

最终完成定义：

```text
新增或修改一条普通规则
→ 规则声明与合同
→ 所属执行器输出 RuleDecision + fact_refs
→ Binding 校验
→ 规则族安全事实验证
→ 公共证据投影
→ Canonical Result
→ Aggregator 仅装配
```

聚合器、公共任务入口、保存逻辑、API DTO 和前端状态解释均不需要增加规则专属代码。

## 6. 稳定性与回滚策略

- 每个规则族固定三个独立提交：A 行为冻结、B 行为等价迁移、C 验收记录。
- 提交 A 只含测试和基线文档，不修改生产逻辑，也不包含预期失败的归零守卫。
- 提交 B 只含等价迁移、确定性回归和立即绿色的归零守卫，不修改业务口径。
- 提交 C 只含三入口、真实病例和性能验收记录，不再修改生产逻辑。
- 结构迁移与业务口径修复绝不混在同一提交。
- 每个提交必须可以通过普通 `git revert <commit>` 单独回滚，不依赖数据库降级。
- 不删除未证明无客户调用的兼容入口；已迁移规则的主链不得再依赖兼容入口。
- 工作区存在其他改动时，使用精确路径暂存，提交前执行 `git diff --cached --name-only` 核对。
- 冻结前发现旧行为不符合批准状态语义时必须停止；另建最小 TDD 业务口径修复任务，修复获批并重新冻结后才能迁移。

## 7. 每个闭环的发布门

一个规则族只有同时满足以下条件才允许进入可发布状态：

- 聚合器中的该族规则专属业务分支为 0；
- 状态、原因码、客户事实、证据定位和文案与冻结基线一致；
- 技术失败保持 `technical_error`；
- 三个真实业务入口走同一 `executor_key` 且无异常 fallback；
- 公共证据投影能定位真实文书 ID、字段和时间；
- LLM 调用次数不增加、输入 Token 不增加、十次中位耗时回归不超过 10%；
- 没有数据库、API DTO 和前端解释改动；
- 聚焦测试和影响范围测试绿色；
- 验收报告列出剩余风险，不以测试数量替代业务结论。

## 8. 首轮预期收益与剩余风险

首轮迁移预期移除聚合器约 44 次检查检验规则号引用，并消除该族在“执行器事实 → 聚合器二次解释 → 证据专属重投影”之间的重复所有权。

首轮结束后仍然存在的风险：

- 手术麻醉和输血族仍有较多聚合器业务分支；
- 扩展文书 executor 职责范围较宽；
- 未迁移旧规则仍可能依赖兼容投影；
- 聚合器文件仍可能很长，但只要新增规则不再进入它，扩展性目标已经持续改善。

因此首轮成功不代表技术债清零；它只授权进入下一规则族的独立评审，不授权连续批量迁移。
