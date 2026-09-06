# LX0609 检查检验语义不确定与资料缺口分流

## 结论

检查检验族不再把所有受控语义 `unknown` 统一归为“数据不足”。状态按事实完整性分流：

| 场景                                                                     | Canonical 状态    | 原因码                                                                  |
| ------------------------------------------------------------------------ | ----------------- | ----------------------------------------------------------------------- |
| 目标事件、权威时间、报告结果正文和病程投影完整，但受控语义仍无法可靠判断 | `uncertain`       | `semantic_output_unknown`                                               |
| 报告只有项目名或时间，没有实际结果字段                                   | `data_gap`        | `required_field_missing`（执行器内部保留 `exam_lab_text_fact_unknown`） |
| 病程来源不完整或被裁剪                                                   | `data_gap`        | 对应来源缺口原因码                                                      |
| 多事件无法唯一关联                                                       | `data_gap`        | `association_failed`                                                    |
| 模型返回非法 JSON、非法合同或调用失败                                    | `technical_error` | 对应技术原因码                                                          |

## 判定边界

本次在检查/检验事件投影中增加 `result_text_available` 内部布尔事实。它只由既有结构化报告结果字段是否有值生成，不保存原文，不进入客户 DTO，也不新增摘要或 digest。

结果字段包括：

- 检查：`description/result/exam_result/exam_impression/exam_conclusion/impression/conclusion/recommendation/abnormal_sign`；
- 培养：`description/result/abnormal_indicator/organism_name/microbe_name/sensitivity_result/recommendation`。

分流顺序：

1. 事件或权威时间缺失时，先按资料缺口处理；
2. 阳性规则无法确认阳性，且报告结果字段为空时，保持 `data_gap`；
3. 报告结果和来源完整，但模型返回合同允许的 `unknown` 时，输出 `evaluation_unknown`，Canonical 对外为 `uncertain`；
4. 非法模型输出仍为 `technical_error`，不得降为业务状态。

## 修改边界

- 未修改 Prompt、模型参数、调用次数和 Token 路径；
- 未修改 Canonical 合同、数据库、API DTO 或前端状态解释；
- 旧聚合器检查检验事实白名单临时接受 `evaluation_unknown`，这是冻结正确语义所需的最小兼容；迁移提交 B 必须连同本族专属校验整体迁出并删除；
- 复用既有 `evaluation_unknown → uncertain` 公共映射；
- 多事件中确定缺陷仍优先于其他事件的资料缺口或语义不确定；
- `data_gap` 在聚合优先级中仍高于 `evaluation_unknown`，避免用模型犹豫掩盖真实资料缺失。

## 验证记录

TDD 先覆盖并验证以下相反场景：

- 完整但含混的培养报告 → `evaluation_unknown`；
- 缺少报告结果正文 → `data_gap`；
- 完整 CT/MRI 报告和病程存在，但语义无法可靠判断 → `evaluation_unknown`；
- RuleDecision 经 Binding/Reducer 后保持 `semantic_output_unknown`；
- Canonical 客户状态为 `uncertain`；
- 来源截断、关联失败和技术失败仍保持原有安全状态。

聚焦测试：

```powershell
Set-Location backend
py -3.10 -m pytest -q --tb=short `
  tests/unit/test_luxian_0609_native_exam_lab_execution.py `
  tests/unit/test_luxian_0609_customer_renderer.py
```

影响范围测试：

```powershell
Set-Location backend
py -3.10 -m pytest -q --tb=short `
  tests/unit/test_luxian_0609_result_aggregator.py `
  tests/unit/test_luxian_0609_canonical_result_finalizer.py `
  tests/unit/test_luxian_0609_decision_reducer.py `
  tests/unit/test_luxian_0609_mainline_services.py
```

验收结果：

- 聚焦测试：`533 passed`；
- 聚合器、Finalizer、Reducer 与主链影响范围：`687 passed`。

检查检验族的已知状态语义冲突已关闭，可以重新建立行为冻结提交 A。
