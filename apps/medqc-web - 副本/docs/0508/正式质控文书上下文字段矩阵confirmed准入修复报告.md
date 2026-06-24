# 正式质控文书上下文字段矩阵confirmed准入修复报告

## 改动摘要

- 本轮不新增 applicability gate，不改页面，不写正式 QC 结果表。
- 在二审 confirmed guardrail 增加 SC-012 / SC-013 / SC-118 / SC-121 的规则对应文书、指定段落和字段矩阵准入。
- 短证据不再一刀切降级；只有来源不明、段落不明或字段矩阵不完整时才转 data_quality_gap。
- SC-013 的“不详预防接种史”保留 policy_pending_vaccination_unknown，不直接 confirmed。

## A/B 结果

- Baseline confirmed=7；keep=2；keep_rate=28.6%。
- After confirmed=7；keep=4；keep_rate=57.1%。
- After confirmed review counts：{"confirmed_keep": 4, "downgrade_to_data_gap": 3}。

## 7 条 targeted confirmed 对比

- 2262370 SC-118: confirmed_defect/keep -> rejected_by_system/；matrix_rule=；blocked=否。
- 1962863 SC-013: confirmed_defect/downgrade_to_rejected_by_system -> not_emitted/；matrix_rule=；blocked=否。
- 2048454 SC-012: confirmed_defect/downgrade_to_data_gap -> data_quality_gap/；matrix_rule=SC-012；blocked=SC-012 confirmed 需要证明证据来自入院记录现病史/发病后至入院前段落；当前来源或段落不足。。
- 2048454 SC-121: confirmed_defect/downgrade_to_data_gap -> confirmed_defect/confirmed_keep；matrix_rule=SC-121；blocked=否。
- 2083787 SC-013: confirmed_defect/downgrade_to_data_gap -> not_emitted/；matrix_rule=；blocked=否。
- 2328501 SC-121: confirmed_defect/keep -> rejected_by_system/；matrix_rule=；blocked=否。
- 2262981 SC-013: confirmed_defect/downgrade_to_data_gap -> rejected_by_system/；matrix_rule=SC-013；blocked=confirmed_defect 缺少二审 adjudicator_reason，不能作为正式确认缺陷。。

## 结论

- SC-012 这类来源明确的短句缺陷不应因 quote 短被降级；但如果本轮结果缺少入院记录现病史上下文，仍应进入 data_quality_gap。
- SC-013 预防接种史“不详”仍不直接 confirmed，需客户口径确认。
- SC-118 / SC-121 只有在完整出院记录字段矩阵或跨文书对照支持时才保留 confirmed。
- 本轮 keep rate 如仍未达 70%，下一轮应继续治理文书完整性类规则的字段矩阵，而不是扩大样本。
