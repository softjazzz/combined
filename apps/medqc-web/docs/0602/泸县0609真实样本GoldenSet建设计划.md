# 泸县0609真实样本Golden Set建设计划

## 已生成产物

- `docs/0602/泸县0609真实样本GoldenSet标注表.csv`
- `docs/0602/泸县0609真实样本GoldenSet系统人工对比表.csv`
- `docs/0602/luxian_0609_real_golden_candidates.json`
- `docs/0602/泸县0609真实样本GoldenSet候选报告.md`

生成脚本：

```powershell
python backend\scripts\build_luxian_0609_real_golden_set.py --target-size 28
```

## 候选来源

候选来自 `luxian_0609_first_pass_review_sheet.csv` 和 `luxian_0609_candidate_coverage.json`。脚本优先选择已有证据片段、ready 状态、优先级高的真实 visit_id，并按规则族分层。

当前候选表已生成 28 条，但现有候选源缺少检查检验、输血、肿瘤病理/化疗三类真实 visit_id。这些缺口写入 `missing_family_gaps`，后续需要从客户样本池继续发现，不能用合成样本替代。

## 标注字段

人工标注表的核心字段：

- `system_status`：系统输出状态，初始为 `pending_system_run`。
- `human_status`：人工结论，初始为 `pending`。
- `is_match`：系统与人工是否一致，初始为 `pending`。
- `evidence_ok`：证据链是否足以支撑结论，初始为 `pending`。
- `error_type`：错误类型，人工复核后填写。
- `reviewer_note`：质控员备注。

## 对比流程

1. 在客户样本验证入口运行 `luxian_0609_qc_v1`。
2. 将系统结果回填到 `泸县0609真实样本GoldenSet系统人工对比表.csv`。
3. 质控员完成 `human_status` 和 `evidence_ok`。
4. 计算一致率前先剔除 `pending`，并单列 `data_gap`、`not_executed`、`technical_error`。

## 边界

当前只完成候选和对比框架，不形成真实准确率结论。合成样本只能用于机制回归，不能作为真实样本准确率。
