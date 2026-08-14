# 项目术语

## 当前在院病历

以同步执行时医院的当前住院状态为准：已经入院且尚未实际出院的三坐标病例。
入院日期不作为范围下限；无论住院一天或一个月，只要当前仍在院就应进入候选范围。
后续资料变化通过每张表的同步游标增量获取，不通过缩短入院日期范围实现。

## 期间出院病历

实际出院时间落在用户所选出院日期范围内的三坐标病例。“在院及已出院”表示
“当前在院病历 + 期间出院病历”；日期选择器只约束出院病例，不约束当前在院病例。

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

规则执行器唯一确定业务状态；聚合器装配规则决策、受控展示事实、子判定和可定位证据，
`finalize_luxian_0609_canonical_result` 只补齐兼容状态字段和资料缺口说明，不得把
`non_compliant` 改写为 `uncertain`。Envelope 保存前必须校验 `status`、
`result_status`、`display_status` 和 `is_compliant` 一致；终结器返回后，聚合器、
Envelope 保存、单一结果接口和前端均不得再次修改业务状态或原因码。

`is_compliant` 是 Canonical 状态的兼容布尔投影，不是第二套判定：

- `compliant`、`not_applicable`：`True`；
- `non_compliant`：`False`；
- `ai_suggested_non_compliant`、`ai_suggested_compliant`、`data_gap`、`uncertain`、
  `not_executed`、`technical_error`：`None`。

接口使用方必须以 `status` 为主状态；不得把 `is_compliant=None` 解释为不合规。
