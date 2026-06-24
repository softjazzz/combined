# 正式原链路随机10病历 confirmed 二轮复核报告

生成时间：2026-05-15 17:37:59

## 范围

- 本轮只读取随机10病历原正式链路 issue_review 中的 first-pass `confirmed_defect`。
- 不重跑 84 条正式质控，不使用 structured evidence POC，不写业务表，不接页面。
- 第二轮 LLM 只允许输出 confirmed_defect / data_quality_gap / rejected_by_system / technical_error_internal。

## 结果

- first-pass confirmed_defect：8。
- 二轮保留 confirmed_defect：0。
- 二轮降级 data_quality_gap：3。
- 二轮驳回 rejected_by_system：5。
- technical_error_internal：0。
- provider_error=0，timeout=0，parse_error=0，model_tokens=6196。

## 误报高频规则

- `SC-121`：2
- `SC-118`：1
- `SC-123`：1
- `SC-036`：1
- `SC-050`：1
- `SC-055`：1
- `SC-008`：1

## 逐条复核

- `2032392` `SC-118` 出院记录缺项或内容错误(入院日期、出院日期、入院情况、入院诊断、诊疗经过、出院情况、出院医嘱、医师签：confirmed_defect -> data_quality_gap；strength=weak；reason=证据片段仅包含入院主诉及出院原因，未展示完整的出院记录结构。无法确认‘入院日期’、‘出院日期’、‘入院情况’等字段是否确实缺失，还是被截断在证据之外。根据通用准入门槛，缺完整文书上下文时优先 data_quality_gap。
- `2037363` `SC-121` 诊疗经过不全面、不详细(无主要药品名称或名称写错，无与诊断相关的重要辅助检查结果)：confirmed_defect -> rejected_by_system；strength=weak；reason=规则要求诊疗经过中无重要辅助检查结果。证据显示‘完善相关检查’，虽未列出具体结果，但属于书写概括而非明确缺失关键诊断依据（如手术指征已明确）。且 supporting_quote 过短，缺乏足够上下文证明‘重要’检查结果完全缺失导致诊疗逻辑断裂。轻微书写省略或概括不直接构成缺陷。
- `2037363` `SC-123` 出院带药不详细(无药品名称、用药剂量、给药途径、用药时间，或药名、剂量写错)：confirmed_defect -> rejected_by_system；strength=weak；reason=证据仅显示‘院外注意休养...创面每天换药’，未提及任何药物。根据规则约束5，‘无出院带药’不等于‘出院带药不详细’。若病历中确实无带药医嘱，则不构成此条缺陷；若有带药但此处未列出，因证据截断无法确认，但基于现有证据更倾向于无带药或证据不足，不得 confirmed。
- `2273484` `SC-036` 无重要辅助检查结果、无对异常检查结果的分析及处理意见：confirmed_defect -> rejected_by_system；strength=strong；reason=证据 supporting_quote 明确显示‘予以胺碘酮静推对症处理’。这构成了对异常心电图结果的实质性处理意见。规则 SC-036 要求‘无分析及处理意见’，此处已有处理措施，故规则不适用。原结论认为缺乏分析而忽略处理措施，属误报。
- `2273484` `SC-050` 上级医师查房无病情分析或欠缺、无诊疗意见或住院期间每周内无副主任医师以上的医师或医疗组长查房记录;上：confirmed_defect -> rejected_by_system；strength=weak；reason=证据显示上级医师查房记录以‘指出：1.患者...2.查体...3.辅助检查...’开头。虽然片段短，但未提供后续内容证明其‘无病情分析’。通常此类列举后会有分析。仅凭复述病史的开头不能断定整篇记录无分析。且 evidence_too_short 风险高，缺乏反证前的完整上下文，不宜 confirmed。结合 auto_screening 提示疑似误报，倾向于 rejected。
- `2273484` `SC-055` 抢救记录描述不清或抢救记录无标题：confirmed_defect -> data_quality_gap；strength=weak；reason=证据和引用均为截断片段（‘予以反复静推肾上腺素,于’），无法看到抢救记录的标题、时间、参与人员、抢救过程全貌及结果。根据通用准入门槛，证据太短、只有截断片段不得 confirmed_defect。无法判断是描述不清还是单纯数据截断，归为 data_quality_gap。
- `2110297` `SC-008` 主诉书写不规范或不能导出第一诊断。：confirmed_defect -> rejected_by_system；strength=weak；reason=主诉‘车祸致头面部、胸部等多处受伤40+分钟’已明确外伤机制、部位（头面部、胸部）及时间，符合急诊/创伤病历书写规范。虽然未直接写出‘骨折’二字，但‘多处受伤’结合后续诊断可逻辑推导，且规则重点在于能否导出第一诊断，此处证据不足以证明‘不能导出’或‘书写不规范’导致无法诊断，属于过度推断。
- `2110297` `SC-121` 诊疗经过不全面、不详细(无主要药品名称或名称写错，无与诊断相关的重要辅助检查结果)：confirmed_defect -> data_quality_gap；strength=medium；reason=仅凭出院记录中的诊疗经过片段‘予以止血...等治疗’无法判定为缺陷。需结合完整病程记录、医嘱单确认是否确实缺失具体药名。若其他文书中有详细记录，则此条不成立；若全篇均无，则需更多上下文支撑。当前仅有孤立片段，缺乏跨文书对照，优先归为数据质量缺口。

## 是否建议接入正式链路

- 建议作为 feature flag / 旁路 gate 继续验证：二轮显著降低 first-pass confirmed 数量，但需人工复核确认是否过严。
