# 泸县0609真实样本Golden Set候选报告

- 来源文件：`D:/LLM/LX888/apps/medqc-web/docs/0602/luxian_0609_first_pass_review_sheet.csv`
- coverage 文件：`D:/LLM/LX888/apps/medqc-web/docs/0602/luxian_0609_candidate_coverage.json`
- 候选数量：28
- 人工状态：pending
- 系统状态：pending_system_run；需要后续在客户样本验证任务中回填系统结果。
- 边界：本报告只建立人工标注和系统对比框架，不声明真实样本准确率。

## 分层分布

- 时限: 3
- 查房/病重病危: 3
- 检查检验: 0
- 会诊: 5
- 手术麻醉: 7
- 输血: 0
- 肿瘤病理/化疗: 0
- 其他: 10

## 缺口

- 当前候选源未发现这些规则族的真实 visit_id：检查检验、输血、肿瘤病理/化疗。
- 这些规则族只能进入待发现清单，不能用合成样本替代真实准确率。

## 待办

1. 质控员逐行填写 `human_status`、`evidence_ok`、`error_type`。
2. 运行系统质控后回填 `system_status` 和 `system_evidence_summary`。
3. 只有完成对比后，才能计算真实样本准确率。
