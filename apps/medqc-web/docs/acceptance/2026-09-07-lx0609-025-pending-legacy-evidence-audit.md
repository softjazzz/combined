# LX0609-025 pending 与 legacy evidence 收口审计

## 范围与结论

本次先完成只读审计，随后按主审结论退役正式不可达的 legacy display-evidence
兼容分支；未修改 025 的业务口径、发布状态、phase、Prompt 或 native 事实。

`LX0609-025` 已在正式客户结果链中失败关闭：它会输出受控的
`not_executed / policy_definition_pending`，没有临床合规状态、判定事实或客户证据。
因此，正式结果链当前不存在由 legacy adapter 生成 025 客户证据的路径。

主审已确认 `aggregate_luxian_0609_results()` 是内部装配入口，生产任务链没有 raw
025 facts 依赖，影子结果也不进入客户结果。因此本次已删除
`legacy_surgery_gate_customer_evidence()`、聚合器的 raw display-facts 证据投影和
旧证据合并缓存。正式 025 的 phase-gate 输出保持不变；未来启用时只能以
`RuleDecision.fact_refs -> Binding -> 公共证据投影` 产生证据。

## 正式目录与 phase 的单一来源

规则总表 [`luxian_0609_rule_master_v1.json`](../../backend/app/data/luxian_0609_rule_master_v1.json)
将 025 声明为：

- `implementation_status=active`：规则已注册，能被客户选择；
- `phase_status=pending_definition`：本次不参与正式临床结论；
- `pending_reason_code=implant_five_field_real_gold_pending`；
- 原因：五字段口径已经冻结，但多台手术、文书缺失及字段冲突尚未完成真实病例金标验收。

[`phase_scope.py`](../../backend/app/services/luxian_0609/phase_scope.py) 不再自有 025
或 pending 清单；它只投影总表。`partition_luxian_0609_rule_scope()` 把 025 列入
`withheld`，`build_luxian_0609_pending_definition_result()` 唯一生成以下正式合同：

```text
status=not_executed
is_compliant=null
facts={}
evidence=[]
metadata.execution_source=lx0609_phase_gate
metadata.reason_code=policy_definition_pending
metadata.pending_reason_code=implant_five_field_real_gold_pending
```

## 三个正式入口的实际路径

```text
客户选择 025
  -> rule master / phase projection
  -> package plan.not_executed_rule_ids
  -> 从 prepared/legacy 执行集合移除
  -> phase gate 生成 not_executed 空证据结果
  -> 保存并由 API/前端原样展示
```

`prepare_luxian_0609_execution()` 仅从 `package_plan.native_executor_batches` 调度
正式 native 结果。由于 025 位于 `not_executed_rule_ids`，它不会进入
`surgery_gate` batch，也不会进入兼容执行器或 LLM fallback。

现有三入口集成验收
[`test_luxian_0609_all_rules_three_entry_acceptance.py`](../../backend/tests/integration/test_luxian_0609_all_rules_three_entry_acceptance.py)
同时覆盖：工作台任务、批量任务和客户样本验证。其对每个非 `phase_1_target`
规则均断言上述 `not_executed / policy_definition_pending` 和
`execution_source=lx0609_phase_gate`；三入口 Canonical tuple 相等。025 不属于
客户交付排除项（033/034/035/041/042），故会作为第 025 条受控 pending 结果交付。

另有 package/路由防护：

- `test_luxian_0609_native_package.py`：即使 `native_surgery_gate_enabled=True`，只选
  025 时仍无 native batch，且 025 在 `prepared_rule_ids_to_remove`；
- `test_luxian_0609_execution_routing.py`：025 的正式结果无证据、无 native LLM 调用；
- `resolve_package_entry_execution_rule_ids()` 先做 phase partition，不会将 025 展开成
  旧 compatibility 执行 ID。

## native surgery gate 与影子执行

`native_surgery_gate_execution.py` 仍把 025 保留在 `SURGERY_GATE_RULE_IDS`，因此
**直接调用** `execute_luxian_0609_native_surgery_gate_rules(rule_ids=("LX0609-025",))`
仍可运行。这是金标/影子准备能力，并非正式临床任务的 executor batch。

例外是 `LUXIAN_0609_025_SHADOW_ENABLED=true`：
`prepare_luxian_0609_execution()` 会调用 `run_luxian_0609_025_shadow()`，后者可调用
native surgery gate。其输出被标记为 `shadow_only=true`、`release_eligible=false`，仅
写入 `luxian_0609_025_shadow` 诊断元数据；不会替换或追加 025 的正式临床质控结果。
这意味着“native 025 从未被正式编排调用”并不准确；准确边界是：**可被正式编排做
影子诊断调用，但从不进入正式客户判定链。**

## 已退役的 legacy adapter

原 `legacy_surgery_gate_customer_evidence()` 位于
[`surgery_gate_result_mapping.py`](../../backend/app/services/luxian_0609/surgery_gate_result_mapping.py)，
唯一调用点是聚合器的 `_customer_evidence_from_display_facts()`。它只处理 025，并从
历史 raw facts 中读取：

- `implant_event_details[*].source_document_id`，或
- `source_document_type=surgery_record` 与 `source_document_id`。

它没有接收或验证 `fact_refs`，仅恢复裸 source-document 坐标，因此是第二证据所有者。
025 pending 期间，phase-gate 结果的 facts/evidence 均为空，本就不会触发该 adapter。

本次已将其与聚合器的 `_customer_evidence_from_display_facts()`、
`customer_evidence_by_rule` 缓存、`_merge_customer_evidence()` 一并删除；reduced
legacy fallback 直接使用 `_customer_evidence_from_reduced_decision()` 的结果，保留原有
fact-ref 反查行为。原生直出结果亦不再由 display facts 恢复任何私有文书 ID。

## 未来启用的前置条件

025 启用前必须完成独立闭环：

1. 执行器为每次手术及植入物五字段判定输出精确、同源的 `fact_refs`，包括多台手术、
   文书缺失和字段冲突；不得再输出 source-document ID 作为可供聚合器解释的裸 facts。
2. Binding 拒绝不存在、跨就诊或不属于选中手术记录的引用；公共证据投影从这些引用生成
   文书 ID、字段路径和时间。
3. 以真实金标病例冻结 025 的 `status`、`reason_code`、关键事实和证据坐标；覆盖完整、
   缺字段、多台手术、缺文书、冲突字段和数据源异常。
4. 三正式入口均验证：025 仅在批准启用后出现 `executor_key=surgery_gate`；pending 期间
   始终为 phase gate、无 native batch、无 compatibility/LLM fallback。
5. 不得恢复 raw display-facts 文书 ID 投影或新的 legacy adapter；所有客户证据均经过
   公共 `fact_refs` 投影。

## 本次验证

建议仅运行以下聚焦测试，避免把本次审计扩大为全量回归：

```powershell
py -3.10 -m pytest `
  tests/unit/test_luxian_0609_phase_scope.py `
  tests/unit/test_luxian_0609_native_package.py `
  tests/unit/test_luxian_0609_execution_routing.py `
  -q

py -3.10 -m pytest `
  tests/integration/test_luxian_0609_all_rules_three_entry_acceptance.py::test_requested_75_empty_materials_deliver_70_equivalently_across_three_entries `
  -q
```

未额外新增测试：上述既有测试已覆盖目录派生、package 排除、单入口 phase result、以及
三入口 Canonical 一致性。本次将旧原生结果中的裸 private document ID 明确断言为不再
投影，并增加聚合器源码守卫，防止 legacy adapter 回流。
