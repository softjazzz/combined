# LX0609 检查检验 24 小时观察窗状态口径修复

## 结论

检查检验族 `LX0609-011/012/014/015` 在目标报告已经存在、但从报告时间到冻结评价时点尚未满 24 小时时，统一输出：

```text
status = not_applicable
reason_code = evaluation_window_not_mature
```

该场景表示规则的观察窗口尚未成熟，不表示资料缺失，也不得提前判定缺陷。窗口成熟后，应以届时冻结的病历资料重新评估。

本次是进入聚合器行为冻结前的独立业务口径修复，不属于聚合器职责迁移。

## 修改边界

- 执行器只调整观察窗状态选择，不改变 24 小时阈值、触发事件、阳性判定或语义 Prompt。
- 结果映射保留 `evaluation_window_not_mature` 原因码，不将其改写为“无触发事件”。
- Renderer 仅增加四条规则的声明式“不适用”说明，不重新判断业务状态。
- Aggregator、Canonical 合同、数据库、API DTO 和前端均未修改。
- 模型调用次数、Prompt 和输入 Token 路径未修改。

## 状态边界

| 场景                               | 状态              | 原因码                         |
| ---------------------------------- | ----------------- | ------------------------------ |
| 报告后不足 24 小时                 | `not_applicable`  | `evaluation_window_not_mature` |
| 报告后已满 24 小时且未找到要求记录 | `non_compliant`   | 原规则缺陷原因码               |
| 缺少权威评价时点                   | `data_gap`        | `authoritative_time_missing`   |
| 权威时间相互冲突                   | `data_gap`        | `authoritative_time_conflict`  |
| 无目标事件或阳性触发               | `not_applicable`  | `trigger_absent_complete`      |
| 查询、合同或模型技术失败           | `technical_error` | 对应技术原因码                 |

## 验证记录

TDD 首次运行覆盖旧行为，相关断言按批准口径修改后由失败转为通过。

聚焦验证：

```powershell
Set-Location backend
py -3.10 -m pytest -q --tb=short `
  tests/unit/test_luxian_0609_native_exam_lab_execution.py `
  tests/unit/test_luxian_0609_customer_renderer.py
```

结果：`529 passed`。

Canonical 闭环单测覆盖：执行器 `RuleDecision` → Binding/Reducer → Aggregator/Renderer，确认 `LX0609-012` 在 24 小时差 1 秒时仍保持 `not_applicable / evaluation_window_not_mature`。

影响范围验证：

```powershell
Set-Location backend
py -3.10 -m pytest -q --tb=short `
  tests/unit/test_luxian_0609_result_aggregator.py `
  tests/unit/test_luxian_0609_canonical_result_finalizer.py `
  tests/unit/test_luxian_0609_decision_reducer.py `
  tests/unit/test_luxian_0609_mainline_services.py
```

结果：`687 passed`。

## 后续阻塞项状态

本提交完成时，“适用事实已经存在，但受控语义输出为 unknown”仍可能落为 `data_gap`。后续独立口径闭环已按以下边界完成分流：

1. 输入事实或来源字段确实缺失；
2. 输入事实完整，但模型无法可靠判断。

只有第二类进入 `uncertain`；第一类保持 `data_gap`。详见 `2026-09-06-lx0609-exam-lab-semantic-unknown-policy.md`。两项口径修复均未混入聚合器迁移，现在可以进入提交 A。
