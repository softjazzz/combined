# LX0609-009 病情变化后 24 小时评价窗口状态修复

## 问题

已识别到病情变化事件和权威评价终点，但事件发生后尚未满 24 小时，旧实现将
`evaluation_window_not_mature` 合成为 `data_gap`。这会把尚未到期的观察窗口误展示为临床资料不足。

## 固定口径

- 变化事件存在、事件时间和评价终点均可核验、但截至评价终点未满 24 小时：
  `not_applicable / evaluation_window_not_mature`。
- 事件时间或对应病程时间缺失、评价终点缺失或冲突：保持 `data_gap`。
- 窗口成熟且存在 24 小时内对应病程：`compliant`。
- 窗口成熟但没有及时对应病程：`non_compliant`。
- 受控语义输出或执行合同异常：保持 `technical_error`。

## 改动范围

仅调整 `course_quality/rules_008_009.py` 中 009 的语义合成分支；不修改
Aggregator、Finalizer、结果映射、Prompt、API 或前端。客户文案继续使用已有的通用
`evaluation_window_not_mature` 文案。

## 验证

先将精确时间边界测试改为预期 `not_applicable`，确认旧实现失败（实际为 `data_gap`）；
再完成最小修复并运行：

```text
py -3.10 -m pytest -q backend/tests/unit/test_luxian_0609_native_course_quality_execution.py
215 passed
```

该测试经过 Native → Binding → Finalizer → Aggregator → Renderer 的 Canonical 合成断言；
同时覆盖窗口未成熟、窗口成熟缺失记录、模型时间回显被忽略及语义未知不推翻每日覆盖。
