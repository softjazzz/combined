# LX0609 会诊族事件级 LLM 试点 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在完整资料链验收后，仅以会诊规则族验证“一个会诊事件一次 LLM 调用、多个语义事实和规则复用”的收益与成本。

**Architecture:** Python 使用 MaterialStore 建立稳定会诊事件键、适用性和时间关系；LLM 只读取单个会诊事件的最小必要片段并返回现有 Rule Contract 声明的受控事实。调用复用与去重仅存在于本次执行上下文，不新增静态 planner 或第二套 LLM 资格字段。

**Tech Stack:** Python 3.10、pytest、现有会诊 Native executor、现有 Rule Contract、受控 LLM client。

---

## 启动前提

- `2026-08-03-lx0609-evidence-materialstore-convergence.md` 已完成。
- 会诊源表的完整性和截断语义已锁定。
- 020～023 的资料路径均为 MaterialStore authoritative。
- 冻结验证集已准备，不用两份病例推导统计指标。
- 下述规则级/族级预算合同已由产品和技术共同接受；接受前本试点保持暂停。

## 试点边界

- 只处理 LX0609-020～023。
- 不修改手术、病程、输血或抗菌药规则族。
- 不新增 `decision_mode`。
- 沿用 `decision_authority` 和 `max_llm_calls_per_rule`。
- `semantic_fact_contract` 扩展现有 `Luxian0609RuleContract`；`event_id` 只在运行时生成。
- 未达到验收门槛时回退当前会诊执行器，不推广到其他族。

## 调用预算合同

`max_llm_calls_per_rule` 明确定义为“单份病例的一次完整质控执行内，该规则最多可归因的唯一 LLM 调用数”，不是每事件预算，也不是进程生命周期预算。

共享调用采用以下记账规则：

1. 一个调用若同时返回021、022、023所需事实，则 `family_unique_calls += 1`，并对021、022、023的 `rule_attributed_calls` 各加1。
2. 调用前必须同时满足：`family_unique_calls < 6`，且所有目标规则的 `rule_attributed_calls < max_llm_calls_per_rule`。
3. 同一 event_id 和 semantic fact contract 的重复请求不新增调用，也不重复扣减。
4. 某规则预算耗尽时，该规则剩余未评估事件返回 `uncertain/llm_budget_exhausted`；其他仍有预算的规则可以继续，但一次调用不得偷偷返回未授权事实。
5. 无会诊事件时调用数必须为0。

当前020～023的1/1/1/2预算无法支持最多6个事件。试点不得绕开该合同。Task 1必须在现有 Rule Contract 中把020～023的每病例预算明确调整为6，并保留族级总预算6作为更紧的上限；不新增旁路环境变量或第二套预算表。若不批准该预算变化，则本试点停止，维持现状。

### Task 1：建立会诊事实和两级预算合同基线

**Files:**

- Modify: `backend/app/services/luxian_0609/rule_contracts.py:137-214`
- Modify: `backend/app/data/luxian_0609_phase1_rule_contracts_extension_v1.json`
- Test: `backend/tests/unit/test_luxian_0609_rule_contracts.py`

**Step 1: 写失败测试**

为020～023声明已有语义事实名称，例如申请目的明确性、会诊意见明确性、执行记录归纳性。断言 `program_only` 规则不能声明语义事实，optional LLM 规则仍受现有调用预算约束。

增加预算语义测试：预算作用域是一次病例执行；020～023的合同预算均为6；族级总预算为6；共享调用必须同时记入所有覆盖规则；重复 event/fact 请求不重复扣减。

**Step 2: 扩展现有 Rule Contract**

只增加可选 `semantic_fact_contract: tuple[str, ...]`，并在现有合同JSON中把020～023的 `max_llm_calls_per_rule` 调整为6。不新增资格枚举、planner、预算配置文件或注册表。是否允许调用仍由 `decision_authority` 决定。

将 `Luxian0609RuleContract.__post_init__` 中按规则ID硬编码1/2次的校验改为受控范围校验：`program_only` 必须为0；`program_then_optional_llm` 必须为1～6。具体值仍只来自现有合同JSON。

**Step 3: 运行测试并提交**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_rule_contracts.py -q`

```powershell
git add backend/app/services/luxian_0609/rule_contracts.py backend/app/data/luxian_0609_phase1_rule_contracts_extension_v1.json backend/tests/unit/test_luxian_0609_rule_contracts.py
git commit -m "feat: 声明会诊语义事实合同"
```

### Task 2：建立运行时稳定会诊事件键

**Files:**

- Modify: `backend/app/services/luxian_0609/native_consultation_episode_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py`

**Step 1: 写事件关联测试**

覆盖一份申请对应一份记录、一份申请多份记录、多次会诊及缺少显式ID。事件键优先使用申请/会诊ID，回退到受控的 `visit + request_time + department + doctor` 组合。

**Step 2: 实现请求内 event_id**

event_id 不写入静态合同，不跨病例缓存，不持久化原文。无法稳定关联时返回具体 uncertain，不让 LLM 猜关联关系。

**Step 3: 运行测试并提交**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py -k "event or relation" -q`

```powershell
git add backend/app/services/luxian_0609/native_consultation_episode_execution.py backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py
git commit -m "feat: 建立会诊事件运行时关联键"
```

### Task 3：单事件单次调用、两级预算扣减并复用事实

**Files:**

- Modify: `backend/app/services/luxian_0609/native_consultation_episode_execution.py`
- Modify only if existing call is delegated there: `backend/app/services/luxian_0609/native_consultation_execution.py`
- Test: `backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py`

**Step 1: 写调用复用测试**

同一事件同时命中021～023时，只允许一次模型请求；返回的多个受控事实分别供相关规则消费。不同事件不得错误复用。

覆盖三次会诊的病例，断言每个事件最多一次调用、每条覆盖规则累计3次、族累计3次。再覆盖7次会诊，断言前6次受控执行，第7次返回 `uncertain/llm_budget_exhausted`，不会被判合规。

**Step 2: 裁剪最小输入**

输入只包含当前会诊申请、对应会诊记录、执行记录及必要时间/角色字段；禁止发送整份病例或任意前三份文书。

**Step 3: 设置试点预算**

实现请求内预算账本：`family_unique_calls`、`rule_attributed_calls`、`seen_event_fact_keys`。每次调用先校验规则级和族级预算，再原子扣减；超过上限时返回具体未评估事件，不静默合规。预算账本不持久化、不进入客户Envelope。

**Step 4: 运行测试并提交**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py backend/tests/unit/test_luxian_0609_native_consultation_execution.py -q`

```powershell
git add backend/app/services/luxian_0609/native_consultation_episode_execution.py backend/app/services/luxian_0609/native_consultation_execution.py backend/tests/unit/test_luxian_0609_native_consultation_episode_execution.py backend/tests/unit/test_luxian_0609_native_consultation_execution.py
git commit -m "feat: 复用会诊事件语义事实"
```

### Task 4：修复唯一调用和 Token 统计

**Files:**

- Modify: `backend/app/services/luxian_0609/execution.py:129-151`
- Modify as needed: `backend/app/services/luxian_0609/execution_contract.py`
- Test: `backend/tests/unit/test_luxian_0609_execution_contract.py`
- Test: `backend/tests/unit/test_luxian_0609_execution_routing.py`

**Step 1: 写共享调用归因测试**

一次会诊事件调用覆盖三条规则时，断言：`unique_call_count=1`、token只累计一次、covered rule IDs包含三条、程序规则token为0。

**Step 2: 增加请求内 call_id**

call_id 只用于执行遥测和归因，不进入客户结果。禁止把一个族的总token复制到每条结果。

**Step 3: 运行测试并提交**

Run: `python -m pytest backend/tests/unit/test_luxian_0609_execution_contract.py backend/tests/unit/test_luxian_0609_execution_routing.py -q`

```powershell
git add backend/app/services/luxian_0609/execution.py backend/app/services/luxian_0609/execution_contract.py backend/tests/unit/test_luxian_0609_execution_contract.py backend/tests/unit/test_luxian_0609_execution_routing.py
git commit -m "fix: 按唯一会诊调用统计模型用量"
```

### Task 5：使用足量冻结集验收试点

**Files:**

- Create: `docs/reports/2026-08-03-lx0609-consultation-llm-pilot-report.md`
- Use: existing readonly LX0609 runner and会诊单测 fixtures

**Step 1: 冻结至少30份病例**

样本至少包括：10份无会诊、10份单次会诊、10份多次或关联复杂会诊；状态真值需人工确认。两份问题病例可包含在内，但不能替代冻结集。

**Step 2: 重复运行稳定性子集**

从冻结集中选择至少10份包含语义调用的病例，每份运行3次。若实际模型调用总数少于30，只报告观察值，不宣称通过 off-focus 百分比门槛。

**Step 3: 对比 deterministic/current baseline**

记录规则级准确率、uncertain/data_gap、唯一调用数、token、P50/P95延迟、off-focus、三次结果一致率和fallback率。

**Step 4: 应用推广门槛**

- 不降低020～023规则级准确率。
- 语义相关 uncertain/data_gap 至少下降20个百分点。
- 至少30次调用时 off-focus ≤3%。
- 10份×3次重复结果一致率 ≥98%。
- 至少30份端到端执行后，新增 P95 延迟 ≤8秒。
- 无会诊病例保持0次LLM调用。

**Step 5: 作出唯一结论**

报告只能给出 `通过并允许评估下一规则族` 或 `未通过并保持当前实现`。不得因为试点通过自动推广到手术、病程、输血和抗菌药族。

**Step 6: 提交报告**

```powershell
git add docs/reports/2026-08-03-lx0609-consultation-llm-pilot-report.md
git commit -m "test: 验收会诊事件级LLM试点"
```

## 完成定义

- 静态 Rule Contract 只有一套 LLM 资格和预算定义。
- event_id 和调用复用只存在于运行时。
- 相同会诊事件最多调用一次并复用多个受控事实。
- token按唯一调用累计，不广播到每条规则。
- 统计结论来自至少30份冻结病例，而非两份功能病例。
- 未通过门槛时不扩展其他规则族。
