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
