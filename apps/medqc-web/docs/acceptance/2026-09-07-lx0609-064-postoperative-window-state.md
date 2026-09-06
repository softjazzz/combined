# LX0609-064 术后三日观察窗口状态修复验收

## 修复范围

- 规则：`LX0609-064` 术后连续三日病程及术者查房记录。
- 修改点：`_postoperative_window_gate()` 的“观察窗口尚未成熟”分支。
- 未修改：聚合器、Finalizer、Renderer、资料源注册、任务入口、API、数据库。

## 状态语义

| 情形                        | 状态                                 | 原因码                         |
| --------------------------- | ------------------------------------ | ------------------------------ |
| 术后三日观察窗口尚未结束    | `not_applicable`                     | `evaluation_window_not_mature` |
| 评价终点缺失                | `data_gap`                           | `authoritative_time_missing`   |
| 评价终点日期与时间冲突      | `data_gap`                           | `authoritative_time_conflict`  |
| 观察窗口成熟且记录完整/缺失 | 保持原 `compliant` / `non_compliant` | 保持原原因码                   |

未成熟窗口不是临床资料缺失，也不应提前判定术后病程缺失；因此改为“不适用”。窗口事实、证据坐标及客户文案保持既有合同。

## 本地验证

执行：

```powershell
py -3.10 -m pytest backend/tests/unit/test_luxian_0609_native_extended_document_execution.py -k "064" backend/tests/unit/test_luxian_0609_decision_binding.py backend/tests/unit/test_luxian_0609_customer_renderer.py -q
```

结果：25 项通过。`test_064_window_maturity_gap_survives_customer_projection` 覆盖 Native → Binding → Aggregator → Renderer；断言 Canonical 状态为 `not_applicable`、原因码不变、事实和客户提示不变。
