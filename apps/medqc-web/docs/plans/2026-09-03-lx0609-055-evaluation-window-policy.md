# LX0609-055 抗菌药物效果评价窗口状态口径

## 1. 背景与问题

LX0609-055 用于核对抗菌药物计划开始或实际启用后 48～72 小时内是否记录效果评价。

当前实现发现抗菌药物医嘱后，会立即检查是否存在 48～72 小时内的效果评价；若未找到，可能直接生成 `non_compliant / threshold_exceeded`。这会把尚未进入评价窗口或评价窗口尚未结束的在院病例提前判为确定问题。

本问题不属于资料缺失：当抗菌药物名称、启用时间和任务评价时点均已明确时，系统已经具备判断窗口是否成熟的全部资料。

## 2. 已确认业务口径

以每一次抗菌药物计划开始或实际启用时间 `T0` 为起点，以任务创建时冻结的病例评价时点 `T_eval` 为判定终点。多条医嘱必须逐事件计算，不得以某一条医嘱的成熟状态覆盖其他医嘱。

| 场景                                         | Canonical 状态   | 原因码                          | 含义                               |
| -------------------------------------------- | ---------------- | ------------------------------- | ---------------------------------- |
| 未使用抗菌药物                               | `not_applicable` | `trigger_absent_complete`       | 本质控点未触发                     |
| `T_eval < T0`                                | `data_gap`       | `authoritative_time_conflict`   | 时间轴冲突，不能可靠判定           |
| `0 ≤ T_eval - T0 < 48小时`                   | `not_applicable` | `evaluation_window_not_started` | 尚未进入 48～72 小时评价窗口       |
| `48小时 ≤ T_eval - T0 < 72小时`              | `not_applicable` | `evaluation_window_not_mature`  | 评价窗口进行中，尚未到最终判定时点 |
| `T_eval - T0 ≥ 72小时`，窗口内存在有效评价   | `compliant`      | `requirement_within_threshold`  | 已在规定窗口完成评价               |
| `T_eval - T0 ≥ 72小时`，窗口内不存在有效评价 | `non_compliant`  | `threshold_exceeded`            | 已超过最终时限，确定缺少评价       |
| 启用时间或评价时点缺失                       | `data_gap`       | `authoritative_time_missing`    | 缺少完成时间计算所需的权威资料     |

“不适用”表示在本次冻结评价时点尚不能启动最终质控判定，不等同于永久不适用。重新创建任务后，应使用新的冻结评价时点重新计算。

## 3. 多事件合成规则

1. 每条抗菌药物启用事件分别计算窗口状态。
2. 尚未到期的药物不得进入 `unmatched_antimicrobials`。
3. 只有已经达到或超过 72 小时、且窗口内未找到有效评价的药物，才能进入 `unmatched_antimicrobials`。
4. 同一病例同时存在成熟和未成熟事件时：
   - 任一成熟事件违反要求，病例结果为 `non_compliant`，结论只列出已到期但未评价的事件；
   - 成熟事件均合规、其余事件尚未成熟时，病例结果为 `not_applicable`，展示尚未到期的事件；
   - 所有事件均已成熟且均合规时，病例结果为 `compliant`。
5. 事件关联不唯一时继续使用现有安全边界，不得猜测评价记录对应的药物事件。

## 4. 客户展示文案

不足 48 小时：

> 抗菌药物启用后尚未进入 48～72 小时效果评价窗口，本次暂不适用。

已满 48 小时但不足 72 小时：

> 抗菌药物效果评价窗口尚未结束，本次暂不判定为质控问题。

已超过 72 小时且无评价：

> 已超过抗菌药物启用后 72 小时，未找到 48～72 小时内的效果评价记录。

客户展示事实至少保留：药物名称、启用时间、冻结评价时点、已间隔小时数、窗口起止时间和逐事件状态。不得在客户文案或普通日志中展示患者身份信息。

## 5. 统计口径

- `not_applicable` 必须从合规率分子和分母中排除。
- 尚未到期的事件不得计入确定问题、资料待核实或合规数量。
- `evaluation_window_not_started` 与 `evaluation_window_not_mature` 必须可以在调试信息中区分。

## 6. 后续最小实施范围

本次仅冻结业务口径，不修改执行代码。后续实现应保持现有 LX0609 主链不变，仅完成以下小闭环：

1. LX0609-055 读取现有 `evaluation_context.horizon`，不得新增第二套评价时点来源。
2. 在规则执行器内增加逐事件 72 小时成熟门。
3. Renderer 仅根据规则事实生成上述客户文案，不重新判断状态。
4. Finalizer、Aggregator、数据库、API 和前端继续原样搬运 Canonical 状态与原因码。
5. 不增加新的 Bundle、Resolver、状态机或兼容回退链。

## 7. 最小验收用例

至少冻结以下回归用例：

1. 启用后 24 小时、无评价：`not_applicable / evaluation_window_not_started`。
2. 启用后 60 小时、无评价：`not_applicable / evaluation_window_not_mature`。
3. 启用后 73 小时、在第 60 小时有有效评价：`compliant / requirement_within_threshold`。
4. 启用后 73 小时、无有效评价：`non_compliant / threshold_exceeded`。
5. 两条药物事件，一条已到期缺评价、一条尚未到期：结果为 `non_compliant`，且 `unmatched_antimicrobials` 只包含已到期事件。
6. 启用时间晚于冻结评价时点：`data_gap / authoritative_time_conflict`。
7. 缺少启用时间或冻结评价时点：`data_gap / authoritative_time_missing`。

真实病例验收还需确认：结果卡片状态、解释文案、调试信息中的逐事件时间，以及证据文书定位保持一致。
