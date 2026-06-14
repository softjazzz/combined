# 泸县0609质控点-golden-cases复核队列质量报告

## 汇总

- 输入复核队列：`D:\LLM\LX888\apps\medqc-web\docs\0602\luxian_0609_golden_review_queue_merged.csv`
- 行数：178
- 错误数：0
- 状态分布：{"pending": 178}
- 样本类型分布：{"positive": 106, "negative": 36, "boundary": 36}
- 已接受规则数：0

## 复核队列门禁

- `accepted` 必须填写 `accepted_case_type`、`reviewer_note`、`evidence_expectation`。
- `rejected` 必须填写 `reject_reason`，且不能填写 `accepted_case_type`。
- `pending` 不能填写 `accepted_case_type` 或 `reject_reason`。
- `positive accepted` 的 `expected_hit` 不能为 false；`negative accepted` 的 `expected_hit` 不能为 true。

## 错误明细

无。
