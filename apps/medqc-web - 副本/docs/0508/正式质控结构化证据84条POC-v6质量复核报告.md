# 正式质控结构化证据 84 条 POC-v6 质量复核报告

## 复核范围

- 本轮只读复核 v6 已生成产物，不重跑模型，不扩大样本，不接页面，不写正式业务表。
- v6 原始终态分布：`{"rejected_by_system":559,"data_quality_gap":237,"confirmed_defect":44}`。
- 全量复核 44 条 confirmed_defect；抽样复核 rejected_by_system 50 条、data_quality_gap 50 条。

## confirmed_defect 复核结论

- confirmed_defect 总数：44。
- 建议保留展示：4。
- 建议降级为 data_quality_gap：18。
- 建议降级为 rejected_by_system：0。
- 需要 schema 修复：22。
- 需要 source sync 修复：0。

## rejected_by_system 抽样结论

- 抽样数量：50。
- rejected_keep：36。
- restore_to_confirmed_candidate：0。
- convert_to_data_quality_gap：13。
- needs_schema_fix：1。
- 初步结论：抽样中未直接发现可恢复为 confirmed 的高置信误驳回；主要风险是跨文书规则证据 schema 不足导致的保守驳回。

## data_quality_gap 抽样结论

- 抽样数量：50。
- data_gap_keep：50。
- promote_to_confirmed_candidate：0。
- convert_to_rejected：0。
- needs_schema_fix：0。
- 初步结论：data_gap 既包含真实源表/bundle 缺口，也包含 evidence schema 未抽到跨文书对照的情况；不应直接当医生缺陷。

## 规则级建议

- recommendation 分布：`{"needs_schema_fix_before_feature_flag":33,"not_suitable_for_structured_evidence_now":29,"ready_for_feature_flag":4,"source_data_blocked":18}`。
- 可考虑 feature flag 旁路规则：SC-008, SC-050, SC-118, SC-121。
- source_data_blocked 规则：SC-013, SC-015, SC-018, SC-037, SC-044, SC-047, SC-066, SC-070, SC-076, SC-081, SC-099, SC-100, SC-101, SC-123, SC-125, SC-138, SC-143, SC-146。
- needs_schema_fix_before_feature_flag 高频规则：SC-004, SC-009, SC-010, SC-011, SC-012, SC-019, SC-020, SC-023, SC-024, SC-025, SC-026, SC-027, SC-034, SC-036, SC-038, SC-043, SC-046, SC-051, SC-075, SC-083。

## 误报与误驳回风险

- 误报主要来自：弱 quote、缺源/空文书被直接包装为 confirmed、跨文书缺少 contrast_quote。
- rejected_by_system 抽样未发现明显可直接恢复 confirmed 的项目，但 SC-036/SC-070/SC-146 等跨文书规则仍需更完整证据 schema 才能排除漏报。
- data_quality_gap 的根因混合：源表/bundle 缺口、结构化字段缺失、抽取 schema 未覆盖，以及裁决模型保守。

## 是否进入 feature flag 旁路

- 不建议整包 84 条进入 feature flag。
- 可以挑选 confirmed_keep 率高、quote 强、跨文书依赖低的规则做小范围旁路验证。
- 对围手术、会诊落实、医嘱一致性、出院记录等跨域规则，应先补 evidence schema 和 source coverage，再进入 feature flag。

## 下一步

- 优先做 schema 修复：为跨文书规则补 `supporting_quote`、`contrast_quote`、字段矩阵和程序化证据摘要。
- 其次做 source/CDM/bundle 覆盖治理：麻醉、安全核查、耗材、出院带药等源表域需要明确缺源还是病历缺项。
- 暂不建议继续扩大样本或接入页面，直到规则级 gold set 能证明 confirmed_keep 率稳定。

## 产物

- `apps\medqc-web\docs\0508\formal_qc_structured_evidence_poc_84_v6_quality_review.csv`
- `apps\medqc-web\docs\0508\formal_qc_structured_evidence_poc_84_v6_quality_review.json`
- `apps\medqc-web\docs\0508\formal_qc_structured_evidence_poc_84_v6_rule_quality_summary.csv`
- `apps\medqc-web\docs\0508\formal_qc_structured_evidence_poc_84_v6_rule_quality_summary.json`
