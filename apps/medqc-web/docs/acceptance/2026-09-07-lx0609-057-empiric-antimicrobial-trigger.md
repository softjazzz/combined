# LX0609-057 经验用药触发修复验收

## 问题与边界

旧实现把“留取培养后启用抗菌药、待药敏结果调整”当作经验用药，也把仅有抗菌药医嘱的病例交付为资料不足。这会将目标治疗或尚未触发的规则误报为需要核对经验用药理由。

本次仅修改 native 执行器，不改变聚合器、Finalizer、资料 DTO 或 LLM 调用边界。057 的适用性口径为：

- 仅出现明确肯定的经验用药表述时触发，包括“经验性用药”“经验用药”“经验性抗感染（治疗）”“经验性抗菌治疗”，以及带明确抗菌用药动作的“经验性”。
- “根据药敏”“培养结果后调整”“目标治疗”等目标治疗语境不触发。
- 没有明确触发且资料来源完整：`not_applicable / trigger_absent_complete`。
- 明确经验用药能唯一关联到药物事件：有理由或无样可采理由为 `compliant`，缺失理由为 `non_compliant`。
- 多药或多事件不能唯一关联：`data_gap / association_failed`；来源不可用或截断仍按既有资料不足语义处理。

本规则不调用 LLM，也不引入 `uncertain`。

## 验收

已按 Native → Binding → Aggregator → Renderer 运行以下反例和正例：

- 培养、药敏、调整方案：不适用；
- 仅普通抗菌药医嘱：不适用；
- 明确经验性抗感染且有重症感染理由：合规；
- 明确经验性抗感染但两个药物事件无法唯一归属：资料不足；
- 明确经验用药但未记录理由：不合规。

执行命令：

```powershell
py -3.10 -m pytest -q backend/tests/unit/test_luxian_0609_native_extended_document_execution.py -k '057'
py -3.10 -m pytest -q backend/tests/unit/test_luxian_0609_native_extended_document_execution.py backend/tests/unit/test_luxian_0609_native_package.py backend/tests/unit/test_luxian_0609_rule_contracts.py
```

结果：7 项 057 聚焦测试及 282 项扩展文书/执行包/规则合同回归通过。
