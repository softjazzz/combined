# 正式原链路随机10病历 confirmed 二轮复核报告

生成时间：2026-05-15 16:11:48

## 范围

- 本轮只读取随机10病历原正式链路 issue_review 中的 first-pass `confirmed_defect`。
- 不重跑 84 条正式质控，不使用 structured evidence POC，不写业务表，不接页面。
- 第二轮 LLM 只允许输出 confirmed_defect / data_quality_gap / rejected_by_system / technical_error_internal。

## 结果

- first-pass confirmed_defect：18。
- 二轮保留 confirmed_defect：2。
- 二轮降级 data_quality_gap：6。
- 二轮驳回 rejected_by_system：10。
- technical_error_internal：0。
- provider_error=0，timeout=0，parse_error=0，model_tokens=12520。

## 误报高频规则

- `SC-015`：3
- `SC-097`：3
- `SC-118`：3
- `SC-123`：2
- `SC-014`：1
- `SC-010`：1
- `SC-008`：1
- `SC-036`：1
- `SC-121`：1

## 逐条复核

- `2229247` `SC-014` 未描述个人史、婚育史、月经史、家族史：confirmed_defect -> rejected_by_system；strength=strong；reason=患者为男性，规则要求记录月经史不适用。个人史已详细记录（居住、职业、疫区接触、不良嗜好等），家族史虽简略但已提及父母情况，不构成实质性缺陷。
- `2229247` `SC-015` 个人史、婚育史、月经史、家族史记录不全或与实际不符：confirmed_defect -> rejected_by_system；strength=medium；reason=同SC-014，男性病历无需记录月经史。个人史记录完整，家族史虽有简化但未完全缺失关键逻辑冲突，且证据片段不足以证明‘与实际不符’或严重不全。
- `2229247` `SC-097` 手术记录缺项或描述不清：confirmed_defect -> data_quality_gap；strength=weak；reason=仅凭‘术中诊断:’和‘失血量:’字段为空片段，无法确认完整手术记录中是否在其他位置（如术后总结）补充了相关信息，或缺少完整文书上下文对照，不能直接归责医生。
- `2229247` `SC-123` 出院带药不详细(无药品名称、用药剂量、给药途径、用药时间，或药名、剂量写错)：confirmed_defect -> confirmed_defect；strength=strong；reason=出院带药明确列出了药品名称、频次和剂量，但确实缺失给药途径（如口服/外用）。根据规则，缺给药途径属于记录不详细，证据充分且直接支撑缺陷。
- `2310639` `SC-015` 个人史、婚育史、月经史、家族史记录不全或与实际不符：confirmed_defect -> rejected_by_system；strength=medium；reason=虽然标注‘具体不详’，但这通常被视为轻微书写省略或信息获取困难，而非严重的记录不全或与实际不符。在无其他反证的情况下，优先视为非缺陷或需人工判断的轻微问题，系统判定为不适用严格缺陷标准。
- `2310639` `SC-097` 手术记录缺项或描述不清：confirmed_defect -> data_quality_gap；strength=weak；reason=仅看到‘切口愈合等级:’字段为空，缺乏完整手术记录上下文，无法确认是否在其他段落描述了愈合情况，或缺少跨文书对照，符合数据质量缺口特征。
- `2191573` `SC-097` 手术记录缺项或描述不清：confirmed_defect -> data_quality_gap；strength=weak；reason=证据仅显示字段标签为空（如'手术I助:'），未提供完整手术记录上下文以确认关键字段（术前/术后诊断、失血量）确实缺失或描述不清。存在跨文书或源数据同步缺口，无法归责医生书写缺陷。
- `2191573` `SC-123` 出院带药不详细(无药品名称、用药剂量、给药途径、用药时间，或药名、剂量写错)：confirmed_defect -> confirmed_defect；strength=strong；reason=出院带药中明确列出了醋酸钙片的规格、频次和剂量，但确实缺失给药途径（如口服）。根据规则要求，缺少给药途径属于记录不详细，证据直接支撑缺陷要件。
- `2035546` `SC-010` 现病史与主诉不符：confirmed_defect -> rejected_by_system；strength=medium；reason=主诉‘腹痛5小时余’与现病史‘5小前剧烈运动后...’在时间逻辑上是一致的（‘5小前’为‘5小时前’的常见笔误/省略，且均指向同一时间点发病）。规则约束明确指出此类省略/错字若无实质性时间冲突不得 confirmed。
- `2035546` `SC-118` 出院记录缺项或内容错误(入院日期、出院日期、入院情况、入院诊断、诊疗经过、出院情况、出院医嘱、医师签：confirmed_defect -> data_quality_gap；strength=weak；reason=提供的证据片段仅包含入院时间和部分体格检查摘要，未展示完整的出院记录全文。无法确认入院情况、诊疗经过及医师签名等核心要素是否真的缺失，疑似源文书或跨文书对照数据不全。
- `2035546` `SC-123` 出院带药不详细(无药品名称、用药剂量、给药途径、用药时间，或药名、剂量写错)：confirmed_defect -> rejected_by_system；strength=strong；reason=出院医嘱中仅包含饮食建议和随访计划，未列出任何药品。规则约束明确指出‘无出院带药’不等于‘出院带药不详细’。既然没有开药，就不存在带药记录不详细的缺陷。
- `2243538` `SC-008` 主诉书写不规范或不能导出第一诊断。：confirmed_defect -> rejected_by_system；strength=weak；reason=主诉‘腹痛7小时’符合基本书写规范（症状+时长）。虽然不能直接导出具体病因诊断，但规则通常指主诉完全无法反映病情或严重不规范。仅因缺乏特异性而判定为不能导出第一诊断过于严格，且证据过短，优先 rejected。
- `2243538` `SC-015` 个人史、婚育史、月经史、家族史记录不全或与实际不符：confirmed_defect -> rejected_by_system；strength=weak；reason=规则约束：SC-014/015中“具体不详”或“不详”通常视为信息缺失而非记录不全的缺陷，且饮酒史未量化属于轻微书写省略。证据仅显示“不详预防接种史”，缺乏实质性逻辑冲突或关键病史完全空白（如否认过敏史已记录）。优先 rejected_by_system。
- `2068785` `SC-036` 无重要辅助检查结果、无对异常检查结果的分析及处理意见：confirmed_defect -> rejected_by_system；strength=medium；reason=规则约束：SC-036要求异常结果后缺少分析/处理意见。但引用中包含“循环关注相对稳定”，这构成了对窦性心动过速的临床观察和处理态度（继续监测），符合“后续已有处理语义”。因此不构成缺陷。
- `2097628` `SC-118` 出院记录缺项或内容错误(入院日期、出院日期、入院情况、入院诊断、诊疗经过、出院情况、出院医嘱、医师签：confirmed_defect -> data_quality_gap；strength=weak；reason=规则约束：SC-118需确认完整出院记录核心要素缺失。当前证据和引用仅包含入院日期片段和随访信息，无法判断是否缺失“医师签名”、“出院诊断”等关键结构化字段。缺全文上下文，不能归责医生。
- `2097628` `SC-121` 诊疗经过不全面、不详细(无主要药品名称或名称写错，无与诊断相关的重要辅助检查结果)：confirmed_defect -> rejected_by_system；strength=weak；reason=规则约束：SC-121要求诊疗经过不全面。引用显示“予以阿莫西林克拉维酸钾抗感染、前列舒通改善排尿对症处理”，虽简略但记录了主要药品名称和处理措施。原结论称“缺乏关键辅助检查结果描述”，但引用中提及“完善相关检查”，且无明确反证表明检查缺失。属于轻微书写省略，非严重缺陷。
- `2097628` `SC-123` 出院带药不详细(无药品名称、用药剂量、给药途径、用药时间，或药名、剂量写错)：confirmed_defect -> rejected_by_system；strength=weak；reason=规则约束：SC-123针对“出院带药不详细”。引用中“予以阿莫西林...对症处理”位于住院期间治疗描述中，且后文列出生活方式医嘱（多饮水、复查）。若文书中确实无“出院带药”栏目或内容为“无”，则不属于“不详细”。鉴于证据未明确展示“存在出院带药但缺剂量/途径”，且引用语境偏向住院用药，判定为误报或证据不足。
- `1962391` `SC-118` 出院记录缺项或内容错误(入院日期、出院日期、入院情况、入院诊断、诊疗经过、出院情况、出院医嘱、医师签：confirmed_defect -> data_quality_gap；strength=weak；reason=规则约束：SC-118需确认完整出院记录缺项。引用显示“患者因摔伤致左髋疼痛1天。入院...”，暗示有入院记录，但未提供完整的出院记录文本以验证是否缺失“医师签名”、“出院诊断”等。证据碎片化，缺完整文书上下文，优先 data_quality_gap。

## 是否建议接入正式链路

- 建议作为 feature flag / 旁路 gate 继续验证：二轮显著降低 first-pass confirmed 数量，但需人工复核确认是否过严。
