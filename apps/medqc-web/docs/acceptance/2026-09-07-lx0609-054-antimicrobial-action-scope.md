# LX0609-054 抗菌药调整理由触发范围修复验收

## 修复范围

- 规则：`LX0609-054` 抗菌药物使用、停用、更换、联合或超说明书使用时的理由记录。
- 修改点：原生扩展文书执行器中的 054 触发事件与逐事件理由关联。
- 未修改：聚合器、Finalizer、Renderer、DTO、任务入口、API、数据库。

## 状态口径

| 情形                                                             | 状态             | 原因码                    |
| ---------------------------------------------------------------- | ---------------- | ------------------------- |
| 仅存在普通抗菌药医嘱，未读取到“具体药物 + 明确动作”的病程事实    | `not_applicable` | `trigger_absent_complete` |
| 已确认动作且同一病程已写明理由                                   | `compliant`      | `requirement_satisfied`   |
| 已确认动作但未找到理由                                           | `non_compliant`  | `requirement_violated`    |
| 动作无法关联本次受控医嘱，或多次同名动作与分开的理由不能唯一关联 | `data_gap`       | `association_failed`      |
| 医嘱或病程来源不可用、截断                                       | `data_gap`       | 保持来源原因码            |

动作优先按 `related_order_id/source_order_id/order_id` 关联受控医嘱；没有标识时，只有同药名候选医嘱唯一才可关联。普通医嘱的 `order_status`、`update_time` 不被用于推断停用、替换或其他动作。超说明书仅在病程正文中同时存在具体药物和明确“超说明书”表述时触发。规则保持纯 Python，不调用 LLM，也不产生 `uncertain`。

## 本地验证

执行：

```powershell
py -3.10 -m pytest -q backend/tests/unit/test_luxian_0609_native_extended_document_execution.py -k "054"
```

结果：9 项通过。`test_054_order_only_case_survives_binding_aggregator_and_renderer` 覆盖 Native → Binding → Aggregator → Renderer，验证停止状态和更新时间不能使普通医嘱误触发 054。
