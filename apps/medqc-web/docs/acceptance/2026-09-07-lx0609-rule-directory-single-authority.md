# LX0609 规则目录单一来源收口验收

## 目标

消除规则总表与发布阶段文件对规则集合和暂停状态的重复定义。正式任务链的规则编号、目录注册状态、发布阶段及暂停原因统一由 `luxian_0609_rule_master_v1.json` 声明。

## 迁移结果

- `phase_scope.py` 只把规则总表投影为执行计划所需的只读结构，不再读取第二份规则目录。
- 删除重复的 `luxian_0609_phase_scope_v1.json`；公开接口 `load_luxian_0609_phase_scope()`、`partition_luxian_0609_rule_scope()` 和 pending 结果结构保持兼容。
- `025`、`028`、`049`、`056`、`059`、`075` 的既有暂停阶段与原因迁入规则总表，正式任务仍为 71 条执行、6 条 `not_executed`。
- 旧 package 兼容入口也先按总表投影过滤暂停规则，不能再把暂停规则展开到旧执行器。
- 未修改 Aggregator、Finalizer、Renderer、Prompt、API 或前端。

## 验收边界

- 正式单规则、批量质控和客户样本验证均经 package plan 与 phase gate；暂停规则不会产生临床业务状态。
- 新规则扩展只需在唯一规则总表声明，不再同步维护第二份固定编号清单。
- 直接绕过 package/public execution 手工调用私有执行器不属于正式入口；最终残留审计仍会检查其不能进入客户结果链。

## 聚焦验证

```text
phase/master/contracts/package/routing/production-boundary: 87 passed
phase + pending gate: 13 passed
production extension boundary: 5 passed
```
