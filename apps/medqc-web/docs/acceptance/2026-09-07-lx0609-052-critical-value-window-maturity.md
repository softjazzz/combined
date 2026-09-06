# LX0609-052 危急值 6 小时处置：评价窗口成熟度闭环

## 范围

仅调整 `LX0609-052`：危急值报告后尚未达到 6 小时评价截止点时，不提前输出确定问题。`LX0609-053` 的资料来源、判定和 Canonical 结果保持不变。

## 判定合同

- 具有精确评价时间：评价时间达到报告时间加 6 小时才进入缺失处置判定；未达到时为 `not_applicable/evaluation_window_not_mature`。
- 仅具有评价日期：仅当评价日期严格晚于截止日期才视为窗口成熟；同日不提前判定缺陷。
- 评价终点缺失或与报告时间冲突：`data_gap`，原因为 `authoritative_time_missing` 或 `authoritative_time_conflict`。
- 窗口成熟后仍无处置：维持 `non_compliant/threshold_exceeded`；及时处置与既有超时处置结论不变。

## 资料与事实所有者

`evaluation_context.horizon` 由同一 Evidence Session 冻结，并只为 052 装载。执行器输出 `fact_refs` 与窗口事实；Binding 保持引用校验；公共投影生成客户证据。

本次在聚合器中仅补充 052 已定义事实的临时合同白名单与一致性校验，使 Native → Binding → Aggregator → Renderer 能保持 `not_applicable`。该白名单仍属于旧的 critical-value 聚合器所有者，计划在完整危急值规则族迁移时整体迁出；未为其他规则新增分支。

## 验收

- TDD 红测：未提供评价终点的旧实现把未满 6 小时情形提前输出 `non_compliant`，且 052 来源合同未包含 `evaluation_context.horizon`。
- 聚焦回归：052 的精确时间、日期型、缺失/冲突、窗口成熟和 053 冻结用例通过。
- 全链路：052 未成熟案例经 Native → Binding → Aggregator/Renderer 后为 `not_applicable/evaluation_window_not_mature`，客户事实包含截止时间与“窗口未成熟”；053 Canonical 结果逐字段不变。
