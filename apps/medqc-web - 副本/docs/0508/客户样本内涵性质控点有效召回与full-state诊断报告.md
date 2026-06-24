# 客户样本内涵性质控点有效召回与 full-state 诊断报告

生成时间：2026-05-27 23:36:06

## 执行边界

- 本轮只覆盖上一轮固定 20 条客户样本内涵性质控点；未扩大样本。
- 未改正式质控规则、gate、prompt，未写正式 QC 结果表。
- 对正式 84 条外规则直接按映射口径诊断；仅对正式 84 内样本执行只读 full-state 诊断。

## 有效召回重算

- 总样本：20 条。
- 可计入正式 84 条准确率母集：11 条。
- 正式 84 外剔除：9 条。
- exact_rule_hit：3 条。
- equivalent_family_hit：0 条。
- true_miss：0 条。
- diagnostic_insufficient：0 条。
- evidence_matrix_gap：0 条。
- gate_rejected_policy_correct：1 条。
- gate_rejected_needs_review：0 条。
- 有效召回率（exact + equivalent / formal84 母集）：27.27%。

## effective_recall_class 分布

- 全部样本：`{"exact_rule_hit": 3, "gate_rejected_policy_correct": 1, "mapping_out_of_formal_84": 9, "target_compliant_or_not_applicable": 7}`
- formal84 母集：`{"exact_rule_hit": 3, "gate_rejected_policy_correct": 1, "target_compliant_or_not_applicable": 7}`

## 正式 84 外样本

- Sheet2-R0043 / 1966729 / SC-116：出院病人无出院记录或死亡病人无死亡记录
- Sheet2-R0003 / 1870471 / SC-080：手术无术前小结
- Sheet2-R0004 / 1874568 / SC-080：手术无术前小结
- Sheet2-R0005 / 1872902 / SC-082：除以紧急抢救生命为目的的急诊手术外，其他住院患者手术无术前讨论或术者未参加
- Sheet2-R0006 / 1876706 / LXE-18：病程时效/缺失
- Sheet2-R0007 / 2137894 / LXE-18：病程时效/缺失
- Sheet2-R0013 / 1880757 / SC-048：入院48小时内无主治医师首次查房记录
- Sheet2-R0014 / 1878110 / SC-021：无首次病程记录
- Sheet2-R0019 / 1915306 / SC-082：除以紧急抢救生命为目的的急诊手术外，其他住院患者手术无术前讨论或术者未参加

处理建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则集，或修正 Sheet2 映射。

## 同族规则返回样本

- 无。

## 上轮 7 条 same_family_rule_returned 的 full-state 结论

- Sheet2-R0228 / SC-036：target_final=compliant；class=target_compliant_or_not_applicable；上轮同族=目标规则未出现在四层终态，但同 visit 同 pack/family 返回了其他规则：SC-073:data_quality_gap, SC-074:data_quality_gap, SC-083:data_quality_gap, SC-099:rejected_by_system, SC-121:data_quality_gap。这可能是同族规则替代、映射不一致，或目标规则被判 compliant 后未被 replay 脚本保存。。
- Sheet2-R0024 / SC-070：target_final=not_applicable；class=target_compliant_or_not_applicable；上轮同族=目标规则未出现在四层终态，但同 visit 同 pack/family 返回了其他规则：SC-083:data_quality_gap, SC-085:rejected_by_system, SC-099:data_quality_gap, SC-100:rejected_by_system, SC-101:rejected_by_system。这可能是同族规则替代、映射不一致，或目标规则被判 compliant 后未被 replay 脚本保存。。
- Sheet2-R0008 / SC-008：target_final=rejected_by_system；class=gate_rejected_policy_correct；上轮同族=目标规则未出现在四层终态，但同 visit 同 pack/family 返回了其他规则：SC-004:rejected_by_system, SC-007:rejected_by_system, SC-018:rejected_by_system, SC-075:data_quality_gap, SC-076:data_quality_gap。这可能是同族规则替代、映射不一致，或目标规则被判 compliant 后未被 replay 脚本保存。。
- Sheet2-R0034 / SC-036：target_final=compliant；class=target_compliant_or_not_applicable；上轮同族=目标规则未出现在四层终态，但同 visit 同 pack/family 返回了其他规则：SC-046:data_quality_gap, SC-070:data_quality_gap, SC-073:data_quality_gap, SC-074:data_quality_gap, SC-107:data_quality_gap。这可能是同族规则替代、映射不一致，或目标规则被判 compliant 后未被 replay 脚本保存。。
- Sheet2-R0032 / SC-036：target_final=compliant；class=target_compliant_or_not_applicable；上轮同族=目标规则未出现在四层终态，但同 visit 同 pack/family 返回了其他规则：SC-043:rejected_by_system, SC-046:data_quality_gap, SC-070:data_quality_gap, SC-073:data_quality_gap, SC-074:data_quality_gap。这可能是同族规则替代、映射不一致，或目标规则被判 compliant 后未被 replay 脚本保存。。
- Sheet2-R0081 / SC-009：target_final=compliant；class=target_compliant_or_not_applicable；上轮同族=目标规则未出现在四层终态，但同 visit 同 pack/family 返回了其他规则：SC-097:data_quality_gap, SC-110:data_quality_gap, SC-118:data_quality_gap, SC-123:rejected_by_system。这可能是同族规则替代、映射不一致，或目标规则被判 compliant 后未被 replay 脚本保存。。
- Sheet2-R0023 / SC-023：target_final=not_applicable；class=target_compliant_or_not_applicable；上轮同族=目标规则未出现在四层终态，但同 visit 同 pack/family 返回了其他规则：SC-004:data_quality_gap, SC-008:rejected_by_system, SC-018:data_quality_gap, SC-118:data_quality_gap, SC-123:rejected_by_system。这可能是同族规则替代、映射不一致，或目标规则被判 compliant 后未被 replay 脚本保存。。

结论：上轮按终态行观察到的同族返回，在 full-state 中没有被直接认定为等价覆盖；其中多数目标规则被明确判为 compliant/not_applicable，应先复核 Sheet2 映射和客户问题是否超出正式规则范围。

## SC-083 gate 复核

- Sheet2-R0195 / 2213827：class=target_compliant_or_not_applicable；level4=True；mdt_equivalent=True；departments=等多学科;级手术术前讨论已包含麻醉科;麻醉科；quote=参与人员: 银娟副主任医师，杨晶主治医师、魏欣主治医师，刘敏住院医师，麻醉科李世元主任医师，刘隆平护士长，王燕护士。
- Sheet2-R0125 / 2104341：class=exact_rule_hit；level4=True；mdt_equivalent=True；departments=讨论记录中未明确提及多学科；quote=讨论时间: 2025-12-02 14:43:55 讨论地点: 申威主治医师。讨论地点：:妇科办公室。 主持人: 申威主治医师。讨论地点：:妇科办公室。 参与人员: 邹红缨主任医师、银娟副主任医师、申威、杨晶主治医师、李治贤住院医师、刘贤忠麻醉医师、黄丽护士、刘隆平护士长。。

结论：按客户已确认口径，多科/多学科会诊可替代 MDT；若客户原问题实际关注具体专科会诊或诊断依据，应标记为 mapping_or_rule_scope_mismatch，而不是直接判 SC-083 gate 错。

## 上轮 2 条 gate_rejected 的 full-state 结论

- Sheet2-R0195 / SC-083：target_final=compliant；class=target_compliant_or_not_applicable；gate=pass_through；reason=原始结果为合规或不适用，不进入缺陷清单。。
- Sheet2-R0125 / SC-083：target_final=data_quality_gap；class=exact_rule_hit；gate=data_gap_not_defect；reason=术前讨论参与人员包括多科室，但未明确标注为多学科讨论，且手术等级未明确为四级，无法确认缺陷。

结论：上轮 gate_rejected 不能直接视为 gate 错；full-state 显示需要结合 SC-083 客户口径和原问题范围复核。

## P0 阻断项

- Sheet2-R0008 / SC-008 / gate_rejected_policy_correct：目标规则有可审计终态 rejected_by_system，但被 gate/guardrail 分流：rejected_by_system。 建议：复核 gate evidence 与客户样本锚点；若冲突，补 evidence matrix 或修正样本映射。
- Sheet2-R0043 / SC-116 / mapping_out_of_formal_84：SC-116 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。 建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。
- Sheet2-R0003 / SC-080 / mapping_out_of_formal_84：SC-080 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。 建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。
- Sheet2-R0004 / SC-080 / mapping_out_of_formal_84：SC-080 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。 建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。
- Sheet2-R0005 / SC-082 / mapping_out_of_formal_84：SC-082 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。 建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。
- Sheet2-R0006 / LXE-18 / mapping_out_of_formal_84：LXE-18 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。 建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。
- Sheet2-R0007 / LXE-18 / mapping_out_of_formal_84：LXE-18 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。 建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。
- Sheet2-R0013 / SC-048 / mapping_out_of_formal_84：SC-048 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。 建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。
- Sheet2-R0014 / SC-021 / mapping_out_of_formal_84：SC-021 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。 建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。
- Sheet2-R0019 / SC-082 / mapping_out_of_formal_84：SC-082 不在正式 sc_content_full_v1 84 条规则内，不能计入 formal84 召回率母集。 建议：从 formal84 准确率母集剔除，或新增客户专项扩展规则/修正 Sheet2 映射。

## 是否建议客户机 3-5 份冒烟

- 默认不建议。
- 阻断原因：formal84 外映射、同族等价口径、SC-083 gate 与客户原问题范围仍需先收口；否则客户机冒烟会把映射/口径问题误读成模型质量问题。

## 下一步建议

1. 先修 Sheet2 mapping：剔除 formal84 外规则或建立客户专项扩展规则集。
2. 对上轮 same_family_rule_returned 的 7 条样本，按 full-state 结果复核为什么目标规则被判 compliant/not_applicable 或 gate 分流，先修映射/验收口径，不要默认算模型漏召回。
3. 对 exact_rule_hit 但质量标签仍为 should_confirm 的样本，进入二审质量复核；这类是“召回后裁决质量”问题，不是 not_returned 问题。
4. SC-083 样本先区分 MDT 缺失与具体专科会诊/诊断依据问题，不要混在同一规则验收。
