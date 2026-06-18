# 泸县0609质控结果-证据链Schema

## 适用范围

本文定义 `luxian_0609_qc_v1` 在客户样本验证和影子运行中的结果字段、状态口径和统计方式。该 schema 兼容旧字段 `rule_id`、`status`、`is_compliant`、`findings`、`evidence`、`suggestion`、`metadata`，前端可继续降级展示旧字段。

## 状态口径

| 状态              | 含义                           | 缺陷计数 |   合格分母 | 人工复核       |
| ----------------- | ------------------------------ | -------: | ---------: | -------------- |
| `non_compliant`   | 证据支持存在缺陷               |     计入 |       计入 | `pending`      |
| `compliant`       | 证据支持符合要求               |   不计入 |       计入 | `not_required` |
| `not_applicable`  | 无触发事件或规则不适用         |   不计入 |     不计入 | `not_required` |
| `data_gap`        | 已发现触发事实，但缺关键数据   |   不计入 |     不计入 | `pending`      |
| `uncertain`       | 证据不足或边界判断，需人工复核 |   不计入 | 计入待复核 | `pending`      |
| `not_executed`    | 规则未执行或当前能力不支持     |   不计入 |     不计入 | `pending`      |
| `technical_error` | 执行异常、解析失败或内部错误   |   不计入 |     不计入 | `pending`      |

合格率只使用 `compliant / (总规则数 - not_applicable - data_gap - not_executed - technical_error)`。`data_gap` 不能显示为合格，`not_applicable` 不能进入合格分母。

## 标准字段

| 字段               | 说明                                                           |
| ------------------ | -------------------------------------------------------------- |
| `rule_set_key`     | 固定为 `luxian_0609_qc_v1`                                     |
| `rule_set_version` | 规则集版本，例如 `2026-06-09`                                  |
| `rule_version`     | 单条规则版本                                                   |
| `executor_type`    | `program`、`llm`、`cross_document`、`cross_table`、`hybrid` 等 |
| `result_status`    | 七状态之一，与 `status` 保持兼容                               |
| `trigger_facts`    | 触发事实列表，包含事实类型、值、来源和时间                     |
| `dependencies`     | 所需来源、缺失来源、数据缺口原因和覆盖级别                     |
| `missing_sources`  | `data_gap` 或缺数据时的扁平缺失来源                            |
| `source_table`     | 首要证据来源表                                                 |
| `source_document`  | 首要来源文书或文书类型                                         |
| `source_field`     | 首要来源字段                                                   |
| `quote`            | 可展示的短原文片段，不包含完整病历全文                         |
| `threshold`        | 阈值或规则判定条件                                             |
| `expected_value`   | 期望值                                                         |
| `actual_value`     | 实际值                                                         |
| `delta`            | 实际值与阈值差异                                               |
| `decision_summary` | 判定摘要                                                       |
| `review_status`    | `pending` 或 `not_required`                                    |

## 证据要求

- 程序化时限规则必须输出触发时间、截止时间、实际时间、实际耗时和超出差值。
- 跨文书规则必须至少保留两个 `evidence_items`，每项包含 `source_document_name`、`record_time`、`quote`。
- 跨表联查规则必须输出 `source_table`、`source_field`、`actual_value`；缺表或缺字段时写入 `missing_sources`。
- `data_gap` 必须有 `missing_sources` 或 `dependencies.data_gap_reason`。
- 严禁输出 `prompt`、`raw_response`、`llm_raw_output`、`embedding`、`medical_text`、完整病历全文和内部执行链路敏感字段。
