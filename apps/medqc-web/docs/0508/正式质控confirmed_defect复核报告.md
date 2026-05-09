# 正式质控confirmed_defect复核报告

生成时间：2026-05-09 09:02:16

## 结论

- 本轮复核 confirmed_defect 候选：12 条。
- `likely_accurate/probably_acceptable/evidence_weak/possible_false_positive/needs_human_review` 分布：{'needs_human_review': 12}。
- 建议保持：0 条；建议降级：12 条。
- 需要收紧准入层：0 条。
- 当前后处理准入层可进入页面接入前的下一轮人工验收。
- 可以考虑扩大到 20 份小样本抽检。

## 自动复核分布

| label              | count |
| ------------------ | ----- |
| needs_human_review | 12    |

## 可以保持的 confirmed_defect

| visit_id | rule_id | rule_name | auto_review_label | auto_review_reason |
| -------- | ------- | --------- | ----------------- | ------------------ |

## 建议降级为 needs_review 或数据缺口

| visit_id | rule_id | rule_name                                                                                           | auto_review_label  | auto_review_reason                        | recommended_action        |
| -------- | ------- | --------------------------------------------------------------------------------------------------- | ------------------ | ----------------------------------------- | ------------------------- |
| 1883111  | SC-015  | 个人史、婚育史、月经史、家族史记录不全或与实际不符                                                  | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 1883111  | SC-018  | 体格检查遗漏主要阳性体征及有鉴别诊断意义的阴性体征，或记录不准确                                    | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 1883111  | SC-034  | 病程中对治疗措施、药物、医嘱变化未记录或分析                                                        | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 1915580  | SC-037  | 取材情况和病理结果未在病程记录中记录                                                                | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 1915580  | SC-050  | 上级医师查房无病情分析或欠缺、无诊疗意见或住院期间每周内无副主任医师以上的医师或医疗组长查房记录;上 | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 1915580  | SC-051  | 病危、病重、疑难病人无主(副主)任医师或科主任查房记录                                                | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 1915580  | SC-081  | 术前小结缺项或描述不清(简要病情、术前诊断、手术指征、拟施手术名称和方式、拟施麻醉方式、注意事项，并 | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 2024757  | SC-011  | 未描述与本次入院有关的重要的阴性症状以及与鉴别诊断有关的阳性症状                                    | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 2024757  | SC-020  | 入院记录无入院诊断或主次顺序错误或次要诊断有重要遗漏                                                | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 2246915  | SC-037  | 取材情况和病理结果未在病程记录中记录                                                                | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 2246915  | SC-110  | 急诊手术无主治及以上医师(注明姓名及职称)的指示记录                                                  | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |
| 2287309  | SC-118  | 出院记录缺项或内容错误(入院日期、出院日期、入院情况、入院诊断、诊疗经过、出院情况、出院医嘱、医师签 | needs_human_review | 后处理收紧后已不再属于 confirmed_defect。 | downgrade_to_needs_review |

## 验收问题回答

1. 12 条候选分布见上：{'needs_human_review': 12}。
2. 可以保持的 confirmed_defect：0 条，详见保持列表。
3. 需要降级：12 条，详见降级列表。
4. 准入层仍需收紧：0 条，主要是证据过短、诊断/出院/缺失类缺少上下文证明。
5. 当前不建议接页面展示，除非仅作为内部复核视图。
6. 当前不建议扩大到 20 份，应先稳定 confirmed_defect 质量。
7. 下一步优先修后处理准入层和证据提取，其次再治理规则口径。
