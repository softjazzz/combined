# LX0609-065 术后72小时观察窗口修复验收

## 问题与根因

065 原先仅按是否存在术后72小时内上级医师查房作出结论，没有声明或读取同一
Evidence Session 的 `evaluation_context.horizon`。因此，当观察窗口尚未结束时，
会提前输出 `non_compliant / required_document_missing`。

## 本次最小修改

- `source_registry.py`：仅为 065 声明既有 `evaluation_context.horizon` 决策资料；064、066 的资料声明不变。
- `native_extended_document_execution.py`：065 使用每台手术权威 `surgery_end_time + 72h` 与冻结评价终点逐台判定；终点只参与判定，不进入决策 `fact_refs` 或客户证据。
- 未修改 Aggregator、Finalizer、Renderer、API、数据库或前端。

## 状态语义

| 评价条件                                                     | 065 输出                                        |
| ------------------------------------------------------------ | ----------------------------------------------- |
| 评价终点早于任一手术的72小时截止点，且不存在已成熟缺查房事件 | `not_applicable / evaluation_window_not_mature` |
| 评价终点恰好到达或晚于截止点，且该台手术无上级医师查房       | `non_compliant / required_document_missing`     |
| 评价终点缺失                                                 | `data_gap / authoritative_time_missing`         |
| 评价终点日期与时间冲突，或早于手术结束时间                   | `data_gap / authoritative_time_conflict`        |

多台手术独立计算：已成熟且缺查房的手术仍输出确定缺陷，未成熟手术不计入缺陷台次。

## 验证

```powershell
py -3.10 -m pytest -q tests/unit/test_luxian_0609_native_extended_document_execution.py -k "065"
py -3.10 -m pytest -q tests/unit/test_luxian_0609_native_extended_document_execution.py -k "064 or 066"
```

结果：065 聚焦 14 项通过；064/066 邻接回归 29 项通过。
