# LX0609-047 输血后评价窗口验收

## 本轮范围

- 将既有 `evaluation_context.horizon` 声明为 047 的 decision support source，并由既有 Evidence Session 构造和绑定。
- 047 只在同一 assessment 内使用该冻结终点；不读取 `now`，不补当天 `23:59:59`，不改 API、聚合器、Finalizer 或 Prompt。
- 仅闭合“是否已过输血结束后 24 小时”的观察窗口。逐次输血与日常病程的关联仍未迁移：多次输血时，笼统日常病程评价不得分配给每一次输血。

## RED 反例

修复前，047 未取得 horizon，单次无评价一律判缺失；真实 typed + Binding + Canonical 反例为：

- 结束 `2026-01-01 16:00`，冻结日期 `2026-01-02`，无评价：错误为 non-compliant，正确为 not-applicable / `evaluation_window_not_mature`。
- 早次 `2026-01-01 10:00` 已在 `11:00` 评价，晚次 `2026-01-02 22:00` 明确未评价，冻结日期 `2026-01-03`：修复前全局 explicit-missing 标记错误判缺失；正确为窗口尚未成熟。

## 冻结口径

- 有及时、且不晚于冻结终点的评价：合规；已有结论不因终点资料缺失被覆盖。
- 无评价或明确缺失：仅当冻结终点可证明**严格晚于**结束后 24 小时，才判缺失；恰好 24 小时仍允许补记。
- 终点只有日期时，只有日期严格晚于 deadline 日期才可证明逾期；同日不得推断已过小时截止。
- 终点缺失：data-gap / `authoritative_time_missing`；终点早于输血结束：data-gap / `authoritative_time_conflict`；来源查询错误：technical error。
- 晚于冻结终点的评价记录不参与本次判定，避免未来文书倒灌。
- `evaluation_window_not_mature` 复用现有 not-applicable reason，并使用 047 专属客户文案；不投影“缺少评价”的临床事实。

## 验证

聚焦回归覆盖：typed Evidence Session → decision Binding → Canonical，日期精度窗口、精确 24 小时前/等于/后、无终点、及时/迟到评价、多次事件成熟与未成熟混合、以及一次 assessment 同时供状态与 facts 使用。

主协调独立执行窗口、既有输血、provider、聚合器所有权和 Finalizer 回归：`279 passed`（2.48 秒，15 条既有弃用警告）。独立审查代理执行窗口、provider、Binding 回归：`129 passed`（1.02 秒）；另以真实 EvidenceSession 核对 horizon 引用确实进入 RuleDecision 并经 Binding 保留。这些数量有重叠，不累加为总覆盖量。

## 变更规模与边界

这是业务缺陷修复，不是结构迁移。现有 native_transfusion_execution.py 从 3045 行变为 3217 行，净增 172 行；四个生产文件合计净增 183 行。未新增生产模块、公开 API、执行入口或 LLM 调用。

本次增补的终点读取、精度比较和窗口判定属于已有 047 assessment 的同一时间资格职责；保留在该职责内，避免创建转发壳。后续逐次病程关联不得继续无限堆入此文件，须先按完整 047 评估职责核定边界。状态和展示事实复用同一个 assessment，不重复计算。

状态：本地窗口及公共边界回归通过，正式入口反例仍在独立验收。多次输血提前跳过日常病程评价的既有缺陷尚未修复；不得将此提交称为 047 全部业务验收通过。无客户实际病例验收、无发布或部署。
