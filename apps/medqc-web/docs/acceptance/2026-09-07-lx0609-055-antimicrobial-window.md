# LX0609-055 抗菌药物效果评价窗口闭环

## 问题与根因

旧实现仅依据是否存在 48～72 小时内评价记录作出结论，未消费任务创建时冻结的
`evaluation_context.horizon`。因此，刚开始用药或窗口尚未结束的事件会被提前输出为
`non_compliant / threshold_exceeded`。

## 固定口径

- 启用时间优先 `planned_start_datetime`，缺失时回退 `prescribed_datetime`。
- 每一条抗菌药物启用事件独立使用同一冻结评价终点计算。
- 小于 48 小时：`not_applicable / evaluation_window_not_started`。
- 大于等于 48 小时且小于 72 小时：`not_applicable / evaluation_window_not_mature`。
- 大于等于 72 小时：再核对 48～72 小时内的有效评价；有则合规，无则确定问题。
- 评价终点早于启用时间、启用时间缺失或评价终点缺失：保持 `data_gap`，不得伪装为不适用。
- 同时存在成熟与未成熟事件时，只有成熟且无评价的事件计入确定问题和
  `unmatched_antimicrobials`；成熟事件均合规而仍有未成熟事件时，整体为不适用。

## 职责边界

本闭环只调整执行器的逐事件窗口判断、既有冻结终点来源绑定、声明式 Renderer 文案和
Canonical 原因码白名单。没有修改 Aggregator、Finalizer、任务入口、保存接口、API 或前端
状态解释。

## 验收

新增 Native → Binding → Aggregator → Renderer 端到端夹具，验证 60 小时无评价时：

- Canonical `status=not_applicable`；
- `reason_code=evaluation_window_not_mature`；
- 未成熟事件不进入 `unmatched_antimicrobials`；
- 客户结论使用“效果评价窗口尚未结束”的声明式文案；
- Native 执行器输出保留每个事件的启用时间、窗口起止、冻结评价时点、已间隔小时数和事件状态。

当前 Aggregator 的旧 055 安全投影只接受既有字段，因此会剥离 `event_windows` 与
`window_state`，但不改变 Canonical 状态、原因码、`unmatched_antimicrobials` 或 Renderer
结论。本闭环不向旧聚合器增加规则专属字段；抗菌药规则族迁移到 Finalizer mapping 时，
该映射将作为唯一展示事实所有者，把上述逐事件事实重新投影到 Canonical 结果。

另外覆盖 24 小时、60 小时、73 小时有/无评价、成熟与未成熟混合、时间轴冲突、终点缺失
以及计划开始时间缺失时的已批准下达时间回退。
