# 会诊失败语义验收（闭环 1）

## 范围

- 生产入口使用 `native_consultation_episode_execution.py` 的会诊执行链。
- 本次只调整 LX0609-020、LX0609-023 的模型合同失败和会诊展示事实合同失败语义；不修改旧 `native_consultation_execution.py`、提示词、调用次数或重试策略。

## 冻结语义

| 输入条件                                 | 最终状态          | 原因码                                                |
| ---------------------------------------- | ----------------- | ----------------------------------------------------- |
| 一、二阶段模型输出结构非法或携带非法引用 | `technical_error` | `model_invalid_output`                                |
| 模型客户端缺失或模型调用异常             | `technical_error` | `model_transport_error`                               |
| 合法低置信或未解析语义结果               | `uncertain`       | `semantic_low_confidence` / `semantic_output_unknown` |
| 权威资料、住院窗口或候选范围不足         | 保持既有分支语义  | 保持既有原因码                                        |
| 会诊客户展示事实合同非法                 | `technical_error` | 原技术原因码；无原技术原因时为 `model_invalid_output` |

## 保护项

- 二阶段 020/023 失败不得改写已完成的 021/022 结果。
- Binding 与 Finalizer 必须保留 `technical_error` 及其技术原因码，不得重写为 `evaluation_unknown + semantic_output_unknown`。
- 技术错误的最终 Canonical 结果不得残留 `data_gap_details` 或临床缺口 `criterion_results`。
- 不新增模型调用、重试或 Prompt 变更。

## 验证边界

- 生产 `prepare → Binding → aggregate` 回归只覆盖首阶段模型正常响应但 `content` 非 JSON 的非法输出；它使用真实 plan、loader 和 episode 执行器。
- 二阶段非法输出覆盖 `episode → Binding → aggregate`，并由既有直接执行器回归证明 020/023 失败不会改写 021/022 的成功结论。
- 候选范围构造时的资料不足存在既有 `data_gap` 与 `uncertain` 分支；本闭环不改变该口径，后续如需统一须单独冻结真实病例与失败语义。
