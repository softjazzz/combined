# 正式质控结构化证据 84 条 POC-v6 二审完整性修复报告

生成时间：2026-05-15 14:14:50

## POC 范围

- 只读运行，不接页面，不写正式质控业务表，不改 Sheet2 验收链路。
- scope=all84_v6；规则数=84；evidence package：`admission_course_evidence`、`diagnostic_followup_evidence`、`order_consultation_evidence`、`surgery_perioperative_evidence_v4`、`discharge_special_evidence`。
- 小模型只抽取 evidence package；审核模型只基于 evidence package + coverage flags 输出四层终态。
- 本轮采用结构化强证据优先：植入物/耗材触发必须来自结构化表/字段或明确“植入/置入/使用 + 材料 + 数量”操作语句；样本文本词表仅作为 weak hint，不作为正式规则依据。
- gate 规则：trigger absent 优先系统驳回，weak text hint 不得覆盖 absent；依据已有证据驳回时必须保留可审计引用。

## 稳定性与解析

- visit 数：10；issue 决策数：840。
- 小模型 JSON 解析成功率：100.00%。
- extractor_provider_error=0，extractor_timeout=0，extractor_parse_error=0。
- adjudicator_provider_error=0，adjudicator_timeout=0，adjudicator_parse_error=0。
- absent_trigger_data_gap_count=0。
- rejected_without_supporting_quote_count（SC-036/SC-101）=0。
- confirmed_without_quote_count=0。
- rejected_existing_evidence_without_quote_count=0。
- weak_trigger_confirmed_count=0。

## Baseline 对比

- baseline_total_tokens=608247；poc_total_tokens=551980；token_delta=56267。
- all84 scope 与正式 84 条 baseline 是同规则范围但不同执行策略；P0/v3 scope 与 84 条 baseline 不是同口径。
- baseline_wall_clock_time=320.585s；poc_wall_clock_time=619.786s。
- baseline_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- baseline_target_rule_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- poc_display_status_counts=`{"confirmed_defect": 44, "data_quality_gap": 237, "rejected_by_system": 559}`。

## 同规则族分布

- baseline 目标规则 issue 数：143。
- baseline 目标规则按 rule 分布：`{"SC-004": {"data_quality_gap": 1}, "SC-010": {"rejected_by_system": 4}, "SC-013": {"data_quality_gap": 1, "rejected_by_system": 3}, "SC-015": {"confirmed_defect": 2, "data_quality_gap": 1, "rejected_by_system": 1}, "SC-018": {"confirmed_defect": 1, "rejected_by_system": 1}, "SC-020": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-032": {"rejected_by_system": 1}, "SC-033": {"rejected_by_system": 1}, "SC-034": {"rejected_by_system": 1}, "SC-036": {"confirmed_defect": 1, "data_quality_gap": 4, "rejected_by_system": 2}, "SC-037": {"data_quality_gap": 1}, "SC-038": {"data_quality_gap": 8}, "SC-043": {"data_quality_gap": 2, "rejected_by_system": 1}, "SC-044": {"confirmed_defect": 1, "rejected_by_system": 2}, "SC-046": {"data_quality_gap": 5, "rejected_by_system": 2}, "SC-047": {"data_quality_gap": 1, "rejected_by_system": 1}, "SC-050": {"confirmed_defect": 2, "data_quality_gap": 2, "rejected_by_system": 1}, "SC-051": {"data_quality_gap": 3, "rejected_by_system": 1}, "SC-066": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-070": {"data_quality_gap": 1}, "SC-075": {"data_quality_gap": 4}, "SC-076": {"data_quality_gap": 1}, "SC-081": {"confirmed_defect": 1, "data_quality_gap": 1}, "SC-083": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-085": {"rejected_by_system": 1}, "SC-097": {"confirmed_defect": 3}, "SC-099": {"confirmed_defect": 1, "data_quality_gap": 1, "rejected_by_system": 3}, "SC-100": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-101": {"data_quality_gap": 1}, "SC-107": {"data_quality_gap": 2, "rejected_by_system": 1}, "SC-108": {"data_quality_gap": 5, "rejected_by_system": 1}, "SC-110": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-113": {"data_quality_gap": 2}, "SC-114": {"data_quality_gap": 2}, "SC-118": {"data_quality_gap": 5, "rejected_by_system": 2}, "SC-121": {"confirmed_defect": 1, "data_quality_gap": 1}, "SC-123": {"confirmed_defect": 1, "data_quality_gap": 2, "rejected_by_system": 1}, "SC-125": {"data_quality_gap": 6, "rejected_by_system": 2}, "SC-143": {"data_quality_gap": 9}, "SC-146": {"data_quality_gap": 8, "rejected_by_system": 1}}`。
- POC 同规则网格决策分布：`{"confirmed_defect": 44, "data_quality_gap": 237, "rejected_by_system": 559}`。

## POC 结论

- 本轮 v6 不再优化速度，专门修复二审缺失输出：每个 expected_rule_id 必须有唯一裁决；缺失只补裁 missing ids，补裁仍缺失时进入 technical_error_internal。

## v6 二审完整性修复

- baseline_total_tokens=608247；all84_v3_total_tokens=962527；all84_v4_total_tokens=432912；all84_v5_total_tokens=475190；all84_v6_total_tokens=551980。
- baseline_wall_clock_time=320.585s；all84_v4_wall_clock_time=1043.244s；all84_v5_wall_clock_time=499.009s；all84_v6_wall_clock_time=619.786s。
- baseline_llm_calls=unknown；all84_v3_llm_calls=252；all84_v4_llm_calls=97；all84_v5_llm_calls=112；all84_v6_llm_calls=112。
- extractor_calls=50；adjudicator_calls=62；extractor_concurrency=3；adjudicator_concurrency=3。
- 平均每病历调用数=11.2；平均每病历耗时=61.979s；token 相对 baseline=90.75%；wall time 相对 v5=24.2%。

## v6 裁决完整性口径

- total_rule_decision_count=840：最终四层终态裁决总数，10 病历应为 840。
- programmatic_decision_count=112：未送二审、由本地 gate 直接落终态的规则数。
- rules_sent_to_adjudicator_count=728：实际进入二审模型的规则数。
- adjudicator_output_rule_count=728：二审首轮加补裁成功返回的唯一规则裁决数。
- initial_missing_adjudicator_output_count=0：首轮缺失输出数。
- adjudicator_retry_count=0；adjudicator_retry_recovered_count=0。
- missing_adjudicator_output_count=0：补裁后仍缺失数；该值不再映射为 rejected_by_system，未恢复则进入 technical_error_internal。
- extra_adjudicator_output_count=1；duplicate_adjudicator_output_count=0。
- final_technical_error_internal_count=0。

## v6 门禁

- missing_adjudicator_output_count=0：达成。
- technical_error_internal=0：达成。
- provider/timeout/parse_error=0：达成。

## 84 条 inventory 摘要

- inventory_rule_count=84；evidence_family_count=5。
- structured_support_level=`{"partial": 53, "ready": 30, "unsupported": 1}`。
- 本轮不替换正式链路；下一步只建议挑选证据域做 feature flag 旁路验证。

## 分病历摘要

| visit_id | patient | wall(s) | extractor_calls | adjudicator_calls | tokens | confirmed | data_gap | rejected | parse_errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1915580 | 雷德超 | 49.57 | 5 | 5 | 43099 | 3 | 14 | 67 | 0 |
| 2024757 | 游德利 | 48.14 | 5 | 5 | 49683 | 1 | 22 | 61 | 0 |
| 2287309 | 陈光华 | 61.60 | 5 | 7 | 58490 | 4 | 30 | 50 | 0 |
| 2246915 | 黄金莲 | 67.05 | 5 | 7 | 69194 | 9 | 20 | 55 | 0 |
| 1883111 | 马章媛 | 47.86 | 5 | 5 | 41109 | 3 | 22 | 59 | 0 |
| 1966656 | 周光容 | 61.42 | 5 | 7 | 57474 | 2 | 30 | 52 | 0 |
| 2311318 | 范永勤 | 76.31 | 5 | 7 | 61042 | 1 | 34 | 49 | 0 |
| 2207717 | 邹才林 | 72.13 | 5 | 5 | 54977 | 1 | 13 | 70 | 0 |
| 1870471 | 蒲云鹏 | 75.00 | 5 | 7 | 61557 | 10 | 25 | 49 | 0 |
| 2268187 | 代云聪 | 60.70 | 5 | 7 | 55355 | 10 | 27 | 47 | 0 |

## confirmed_defect 明细

- `1915580` `SC-097` surgery_perioperative_evidence_v4：quote=手术结束时间：status absent; 植入物/耗材信息: status weak；reason=证据包中coverage_flags标记'missing_surgery_end_time'和'missing_implant_details'，且required_evidence显示手术结束时间为absent，植入物信息为weak。规则SC-097要求手术记录包括手术结束时间、出血量、输血量等。缺少手术结束时间和详细的植入物信息属于缺项或描述不清。
- `1915580` `SC-105` surgery_perioperative_evidence_v4：quote=新建S章节:手术时间：2025年08月12日；麻醉方式：静吸复合全麻；手术方式：胸12椎骨折切开复位内固定术；reason=术后首次病程记录中缺失‘术中诊断’、‘手术简要经过’及‘术后应当特别注意观察的事项’等关键内容。现有记录仅包含手术时间、麻醉方式和手术方式，不符合规则对术后首次病程记录完整性的要求。
- `1915580` `SC-118` discharge_special_evidence：quote=患者因腰痛 2 小时入院...病情好转平稳，予以出院。；reason=出院记录中缺失出院诊断字段，且未包含完整的出院情况、出院医嘱（如随访时间等）及医师签名信息，不符合出院记录完整性要求。
- `2024757` `SC-047` admission_course_evidence：quote=诊断类型: 修正诊断 诊断名称: 1.继发性肺结核...；reason=证据显示存在修正诊断（入院记录诊断-修正诊断-4），诊断为继发性肺结核等。根据SC-047规则，修正诊断时应记录修改或补充的理由及诊断依据。虽然证据中提到了TB-DNA阳性和胃镜结果作为支撑，但这些信息散落在不同时间的查房记录中，且修正诊断的时间（10-22）晚于部分依据产生的时间。关键在于，修正诊断记录本身是否包含了‘理由及依据’的明确陈述？证据中的修正诊
- `2287309` `SC-047` admission_course_evidence：quote=目前诊断：1.左肺上叶占位性病变... 目前考虑诊断：1.左肺上叶腺癌...；reason=contradicting_evidence显示诊断从'左肺上叶占位性病变'修正为'左肺上叶腺癌'，但evidence_package中missing_evidence指出病理报告缺失，且required_evidence和supporting_evidence中均未提供记录修改理由及诊断依据的病程片段，符合修正诊断未记录理由及依据的特征。
- `2287309` `SC-146` order_consultation_evidence：quote=[D5] ...可给予沙美特罗替卡松500ug 吸入 bid+噻托溴铵粉雾剂18ug 吸入 qd...；reason=呼吸科会诊建议给予沙美特罗替卡松和噻托溴铵粉雾剂，但证据包明确指出'missing_evidence'中存在这两项药物的医嘱或执行记录缺失，导致诊疗医嘱与病程/会诊记录不一致，形成诊疗闭环断裂。
- `2287309` `SC-118` discharge_special_evidence：quote=患者于1年前,慢性起病... 现患者病情恢复可，予以办理出院。1.胸外科门诊随访(每周一、周四张京副主任医师门诊),注意休息,加强营养,适当活动;2.伤口每3天换药,若敷料渗湿需立即更换敷料,术后14天左右视伤口恢复情况拆线;引流管处缝线于拔管后12天左右视伤口恢复情况拆线;3.术后1月复查胸部增强CT,术后1年内每3；reason=出院记录中缺失入院日期、出院日期、入院情况、入院诊断、诊疗经过、出院情况等核心要素。证据显示出院记录仅包含简短的随访和换药医嘱，未体现完整的病历结构要求。
- `2287309` `SC-121` discharge_special_evidence：quote=2026--3-24日在全麻下行胸腔镜下左肺上叶结节楔形切除术+胸腔镜下胸腔粘连松解术... (住院)局部切除组织活检检查与诊断 (左肺上叶):楔形肺叶切除标本,浸润性非粘液腺癌(贴壁型为主+腺泡型),肿瘤大小1.5x1.2x1.0cm;一一肺切缘:未见癌;一一肿瘤分级:高分化;一一脉管侵犯:脉管内未见癌栓;一一神经侵；reason=诊疗经过描述不全面、不详细。出院记录中缺乏主要药品名称及与诊断相关的重要辅助检查结果的具体描述，仅提及手术名称和病理结果片段，未形成完整的诊疗经过叙述。
- `2246915` `SC-008` admission_course_evidence：quote=发现阴道可复性肿物2+年 患者于2+年前无诱因 出现阴道口见一大小约5 *4 cm大小肿物脱出阴道口；reason=入院记录中主诉/现病史描述为“发现阴道可复性肿物2+年”，虽能提示妇科脱垂疾病，但入院诊断部分在证据中被标记为“empty_diagnosis_tables”且“未在入院记录正文中明确列出标准入院诊断列表”。主诉需能导出第一诊断，若诊断列表缺失或混乱，则视为主诉与诊断对应关系不规范或不能有效导出诊断。此外，上级查房记录中列出的诊断为“子宫脱垂II度；阴道前壁
- `2246915` `SC-010` admission_course_evidence：quote=发现阴道可复性肿物2+年 患者于2+年前无诱因 出现阴道口见一大小约5 *4 cm大小肿物脱出阴道口；reason=入院记录中现病史描述简略，且入院诊断部分缺失（empty_diagnosis_tables）。上级查房记录中提到的诊断“子宫脱垂II度；阴道前壁脱垂伴膀胱膨出II度”与入院记录中的主诉“发现阴道可复性肿物2+年”在逻辑上相关，但由于入院诊断缺失，无法确认现病史是否充分支撑了最终诊断，且现病史描述过于简单，未能完整反映病情发展全过程以支持诊断，存在不符或支撑不
- `2246915` `SC-020` admission_course_evidence：quote=入院记录诊断表为空，未在入院记录正文中明确列出标准入院诊断列表。；reason=证据包明确指出“missing_admission_diagnosis_section”、“empty_diagnosis_tables”以及“未在入院记录正文中明确列出标准入院诊断列表”。入院记录无入院诊断，符合SC-020规则定义的缺陷。
- `2246915` `SC-050` admission_course_evidence：quote=[D6] source_table=senior_course_record title=邹红缨主任医师查房记录 time=2026-03-09 08:34:39 quote='患者为71岁女性，起病缓，病程长，患者因“发现阴道可复性肿物2+年”入院'；reason=证据包显示 senior_course_record (邹红缨主任医师查房记录) 存在，但其 quote 仅为一般性病史回顾和诊断依据，未体现具体的‘病情分析’（如鉴别诊断、当前治疗难点分析）及‘诊疗意见’（如下一步具体调整方案）。且 trigger 指出首次病程缺失，整体病程记录质量低下，上级查房记录若仅复述病史而无深度分析，符合‘无病情分析或欠缺’。
- `2246915` `SC-093` surgery_perioperative_evidence_v4：quote=输入材料中麻醉记录表为空，缺失详细的麻醉过程、用药及生命体征监测数据。；reason=coverage_flags明确标记'anesthesia_record_missing'，且data_quality_flags标记'anesthesia_record_empty'，missing_evidence指出'麻醉记录单'缺失。符合无麻醉记录的缺陷定义。
- `2246915` `SC-094` surgery_perioperative_evidence_v4：quote=输入材料中麻醉记录表为空，缺失详细的麻醉过程、用药及生命体征监测数据。；reason=由于麻醉记录本身缺失（见SC-093裁决），自然导致麻醉记录内容缺项或描述不清。在记录完全缺失的情况下，视为质量缺陷。
- `2246915` `SC-106` surgery_perioperative_evidence_v4：quote=programmatic_coverage bundle_missing:postane_surveil_record；reason=programmatic_coverage中bundle_missing包含'postane_surveil_record'，且missing_evidence虽未直接列出但结合麻醉记录缺失及无其他访视证据，通常术后访视依赖于麻醉记录或独立文书。此处更直接的证据是coverage_flags未覆盖post_op_visit，且无相关quote。根据常规质控逻
- `2246915` `SC-103` surgery_perioperative_evidence_v4：quote=输入材料中手术安全核查表为空，缺失三方核查签字信息。；reason=coverage_flags明确标记'safe_check_missing'，且data_quality_flags标记'safe_check_record_empty'，missing_evidence指出'手术安全核查记录'缺失。符合手术安全核查记录缺项的定义。
- `2246915` `SC-123` discharge_special_evidence：quote=slot:出院带药 status:missing_evidence reason:出院记录中未列出具体药物名称、剂量、频次、用法及天数，仅提及生活注意事项；日常病程记录中的阿司匹林和阿托伐他汀为门诊随访建议，非正式出院带药医嘱。；reason=出院带药记录缺失或不详细。证据包明确指出'outpatient_medicine_missing'且'missing_discharge_medicine_details'，required_evidence中出院带药状态为'missing_evidence'，reason指出出院记录中未列出具体药物名称、剂量、频次、用法及天数。
- `1883111` `SC-118` discharge_special_evidence：quote=[D1] source_table=discharge_record title=出院记录 time=2025-07-11 21:31:02 ... 给于复方电解质醋酸钠葡萄糖补充能量，依诺肝素钠抗凝，等对症支持治疗，患方要求出院到上级医院治疗。；reason=出院记录中缺少入院日期、入院情况、入院诊断、诊疗经过（详细）、出院情况等核心要素。证据仅显示出院记录片段，未包含完整的入院及诊疗过程描述，不符合出院记录完整性要求。
- `1883111` `SC-123` discharge_special_evidence：quote=slot: 出院带药, status: missing_evidence; slot: 出院医嘱, quote: 4.用药指导：继续抗肿瘤治疗。；reason=出院带药记录缺失详细信息。证据显示出院带药状态为missing_evidence，且出院医嘱中仅提及“继续抗肿瘤治疗”，未记录具体药品名称、剂量、给药途径、用药时间等关键信息，违反出院带药详细记录规定。
- `1883111` `SC-121` discharge_special_evidence：quote=[D1] source_table=discharge_record title=出院记录 time=2025-07-11 21:31:02 ... 给于复方电解质醋酸钠葡萄糖补充能量，依诺肝素钠抗凝，等对症支持治疗，患方要求出院到上级医院治疗。；reason=诊疗经过描述不全面、不详细。出院记录中未体现主要药品名称的完整使用情况及与诊断相关的重要辅助检查结果，仅简述了部分对症治疗和出院原因，缺乏详细的诊疗演变过程。
- `1966656` `SC-093` surgery_perioperative_evidence_v4：quote=麻醉记录表为空，缺少具体的麻醉用药、生命体征监测数据等详细记录。；reason=证据包中data_quality_flags明确包含'missing_anesthesia_record'，且missing_evidence中指出'anesthesia_detailed_record'缺失，理由为'麻醉记录表为空'，符合无麻醉记录的定义。
- `1966656` `SC-094` surgery_perioperative_evidence_v4：quote=麻醉记录表为空，缺少具体的麻醉用药、生命体征监测数据等详细记录。；reason=由于麻醉记录缺失（见SC-093裁决），自然无法核查麻醉记录内容的完整性和清晰度，属于缺项或描述不清。
- `2311318` `SC-020` admission_course_evidence：quote=入院记录诊断表中入院诊断字段为空；reason=入院记录诊断表中入院诊断字段为空（见missing_evidence），尽管supporting_evidence中有初步诊断列表，但正式入院诊断结构缺失或未按规范录入入院诊断字段，导致无标准入院诊断或主次顺序错误/重要遗漏风险。根据coverage_flags 'incomplete_admission_diagnosis_structure' 及 mis
- `2207717` `SC-034` order_consultation_evidence：quote=会诊建议：建议 1、停用可能导致肝功能不全的药物；证据缺失：missing_drug_stop_order, required_evidence slot '会诊意见执行 - 停用可疑药物' status: absent；reason=会诊意见明确要求‘停用可能导致肝功能不全的药物’，但证据包显示‘missing_drug_stop_order’且required_evidence中‘会诊意见执行 - 停用可疑药物’状态为absent。病程记录中未体现对可疑药物的停用医嘱及分析，违反治疗措施变化需记录的规定。
- `1870471` `SC-009` admission_course_evidence：quote=文档标题显示为首次病程记录但内容为空；reason=首次病程记录（现病史的主要载体）被标记为缺失（empty_required_document_content），导致现病史记录不全或缺失，无法体现发病情况、主要症状特点、伴随症状及诊治经过等必要内容。
- `1870471` `SC-011` admission_course_evidence：quote=文档标题显示为首次病程记录但内容为空；reason=由于首次病程记录/现病史缺失，无法判断是否描述了与鉴别诊断有关的阴性症状（如反跳痛、肌紧张等腹膜刺激征描述）及阳性症状。
- `1870471` `SC-012` admission_course_evidence：quote=文档标题显示为首次病程记录但内容为空；reason=首次病程记录缺失，导致无法核查发病后到入院前在院内、外接受检查与治疗的详细经过及效果。
- `1870471` `SC-023` admission_course_evidence：quote=文档标题显示为首次病程记录但内容为空；reason=首次病程记录缺失（内容为空），因此必然不存在病例特点。
- `1870471` `SC-024` admission_course_evidence：quote=文档标题显示为首次病程记录但内容为空；reason=首次病程记录缺失，无法归纳提炼病例特点。
- `1870471` `SC-025` admission_course_evidence：quote=文档标题显示为首次病程记录但内容为空；reason=首次病程记录缺失，导致无诊断依据、鉴别诊断、诊疗计划。
- `1870471` `SC-026` admission_course_evidence：quote=文档标题显示为首次病程记录但内容为空；reason=首次病程记录缺失，导致无诊断依据及鉴别诊断。
- `1870471` `SC-027` admission_course_evidence：quote=文档标题显示为首次病程记录但内容为空；reason=首次病程记录缺失，导致无诊疗计划。
- `1870471` `SC-093` surgery_perioperative_evidence_v4：quote=source_table: anesthesia_record, reason: 源数据为空；reason=证据包中 missing_evidence 明确列出 'anesthesia_record'，且 data_quality_flags 包含 'missing_anesthesia_record'。规则 SC-093 要求核查手术患者是否有麻醉记录，缺失即构成缺陷。
- `1870471` `SC-103` surgery_perioperative_evidence_v4：quote=source_table: surgery_safecheck_record, reason: 源数据为空；reason=证据包中 missing_evidence 明确列出 'surgery_safecheck_record'（手术安全核查记录），且 data_quality_flags 包含 'missing_safety_check'。规则 SC-103 要求核查手术安全核查记录，缺失即构成缺陷。
- `2268187` `SC-019` admission_course_evidence：quote=2026-03-11 一般细菌涂片检查:涂片细菌结果 未查见细菌,2026-03-12 分泌物一般细菌培养:分泌物一般细菌培养 培养两日无细菌生长；reason=支持性证据显示存在辅助检查（细菌涂片、培养），但在入院记录或病程记录的引用片段中，未明确记录这些关键检查结果对诊断的支持作用或具体数值/结论的完整抄录，且证据包提示source_quote_quality为weak，存在记录不完善风险。但更直接的缺陷在于首次病程记录的完全缺失导致诊疗计划依据不足。此处针对SC-019，鉴于有检查但未在提供的短quote中体现
- `2268187` `SC-023` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=证据包明确指出首次病程记录为空（<empty>），且时间晚于入院记录，导致首次病程记录中必然缺失病例特点。
- `2268187` `SC-024` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录为空，自然无法归纳提炼病例特点。
- `2268187` `SC-025` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录为空，缺失诊断依据、鉴别诊断和诊疗计划中的任意一项或多项。
- `2268187` `SC-026` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录为空，无法进行诊断依据或鉴别诊断的分析。
- `2268187` `SC-027` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录为空，缺失诊疗计划。
- `2268187` `SC-081` surgery_perioperative_evidence_v4：quote=与患者及家属沟通，建议行左膝关节感染切开、清创引流术，患者及家属同意后于2026-03-10 11:41在局部浸润麻醉下行左膝皮肤感染清创引流术。；reason=规则要求术前小结包含简要病情、术前诊断、手术指征、拟施手术名称和方式、拟施麻醉方式、注意事项等。证据中明确标记 'no_formal_operation_record' 且 'presurg_summary' 缺失（bundle_missing:presurg_summary）。虽然日常病程中有部分信息，但缺少独立的、结构化的术前小结文书，导致关键要素（如手
- `2268187` `SC-092` surgery_perioperative_evidence_v4：quote=在局部浸润麻醉下行左膝皮肤感染清创引流术...以2%利多卡因行局部浸润麻醉；reason=规则要求有麻醉术前访视记录。证据明确标记 'no_formal_anesthesia_record' 且 'bundle_missing:anesthesia_record'。虽然日常病程提到了麻醉方式，但缺少独立的、符合规范的麻醉术前访视记录单，导致内容缺项。
- `2268187` `SC-097` surgery_perioperative_evidence_v4：quote=予以取培养，予以生理盐水、双氧水、碘伏交替冲洗创面...髌上囊内置入橡皮引流条；reason=规则要求手术记录内容完整清晰。证据明确标记 'no_formal_operation_record' 且 'bundle_missing:surgery_record'。虽然日常病程中有简短描述，但缺少独立的手术记录单，导致术中所见、止血情况、缝合方式等关键细节可能缺失或不符合规范格式，属于缺项或描述不清。
- `2268187` `SC-105` surgery_perioperative_evidence_v4：quote=trigger: 日常病程记录中明确描述了手术名称、麻醉方式、手术时间及过程；reason=术后首次病程记录缺项或描述不清。证据显示手术过程仅记录在‘日常病程记录’中，缺少独立的‘术后首次病程记录’文书（programmatic_coverage中bundle_missing:postsurg_firstcourse_record）。虽然日常病程中有手术描述，但根据规则定义，术后首次病程记录应由参加手术的医师在术后即时完成并作为独立文书存在，当前病

## 是否值得扩大

- 建议先做同规则族成本评估和 POC issue 抽样复核，再决定是否接入更多规则族；本 POC 不改变正式主链路。
