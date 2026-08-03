# 项目术语

## 泸县 0609 规则总表

客户确认的 75 条质控点完整业务范围。唯一权威数据源是
`backend/app/data/luxian_0609_rule_master_v1.json`。规则总表不等于当前执行清单。

## 可执行规则

规则总表中 `implementation_status=active` 的规则。当前共 63 条；现有规则包装器、
Native 执行器和结果 API 只能处理这一集合，不能为未启用规则生成占位结果。

## 合同就绪规则

规则总表中 `implementation_status=contract_ready` 的规则。业务定义已经足以进入开发，
但尚未接入当前执行链。当前为 LX0609-052、053、058、070。

## 待定义规则

规则总表中 `implementation_status=pending_definition` 的规则。必须先补齐总表中记录的
定义缺口，才能进入开发和执行。当前共 8 条。

## LX0609 结构化规则决策

`ReducedRuleDecision` 是规则事实经过固定状态机归约后的临床决策。它不读取客户展示
文案，也不等同于最终保存的客户结果。

## LX0609 Canonical 客户结果

聚合器先装配规则决策、受控展示事实、子判定和可定位证据，再由
`finalize_luxian_0609_canonical_result` 唯一确定最终客户状态。缺少可核对解释的
`non_compliant` 在这里一次性降级为 `uncertain`；终结器返回后，聚合器、Envelope
保存、单一结果接口和前端均不得再次修改 `status`、`result_status`、`reason_code`
或 `is_compliant`。
