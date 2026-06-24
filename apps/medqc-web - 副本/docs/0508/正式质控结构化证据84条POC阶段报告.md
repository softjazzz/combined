# 正式质控结构化证据 84 条 POC 阶段报告

生成时间：2026-05-15 01:58:51

## POC 范围

- 只读运行，不接页面，不写正式质控业务表，不改 Sheet2 验收链路。
- scope=all84；规则数=84；evidence package：`admission_record_evidence`、`first_course_diagnosis_evidence`、`course_progress_change_evidence`、`abnormal_result_followup_evidence`、`consultation_implementation_evidence`、`order_execution_treatment_evidence`、`surgery_perioperative_evidence`、`surgery_pathology_implant_evidence`、`discharge_record_evidence`。
- 小模型只抽取 evidence package；审核模型只基于 evidence package + coverage flags 输出四层终态。
- 本轮采用结构化强证据优先：植入物/耗材触发必须来自结构化表/字段或明确“植入/置入/使用 + 材料 + 数量”操作语句；样本文本词表仅作为 weak hint，不作为正式规则依据。
- gate 规则：trigger absent 优先系统驳回，weak text hint 不得覆盖 absent；依据已有证据驳回时必须保留可审计引用。

## 稳定性与解析

- visit 数：10；issue 决策数：840。
- 小模型 JSON 解析成功率：96.67%。
- extractor_provider_error=0，extractor_timeout=0，extractor_parse_error=3。
- adjudicator_provider_error=0，adjudicator_timeout=0，adjudicator_parse_error=0。
- absent_trigger_data_gap_count=0。
- rejected_without_supporting_quote_count（SC-036/SC-101）=0。
- confirmed_without_quote_count=0。
- rejected_existing_evidence_without_quote_count=0。
- weak_trigger_confirmed_count=0。

## Baseline 对比

- baseline_total_tokens=608247；poc_total_tokens=962527；token_delta=-354280。
- all84 scope 与正式 84 条 baseline 是同规则范围但不同执行策略；P0/v3 scope 与 84 条 baseline 不是同口径。
- baseline_wall_clock_time=320.585s；poc_wall_clock_time=2037.538s。
- baseline_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- baseline_target_rule_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- poc_display_status_counts=`{"confirmed_defect": 54, "data_quality_gap": 159, "rejected_by_system": 627}`。

## 同规则族分布

- baseline 目标规则 issue 数：143。
- baseline 目标规则按 rule 分布：`{"SC-004": {"data_quality_gap": 1}, "SC-010": {"rejected_by_system": 4}, "SC-013": {"data_quality_gap": 1, "rejected_by_system": 3}, "SC-015": {"confirmed_defect": 2, "data_quality_gap": 1, "rejected_by_system": 1}, "SC-018": {"confirmed_defect": 1, "rejected_by_system": 1}, "SC-020": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-032": {"rejected_by_system": 1}, "SC-033": {"rejected_by_system": 1}, "SC-034": {"rejected_by_system": 1}, "SC-036": {"confirmed_defect": 1, "data_quality_gap": 4, "rejected_by_system": 2}, "SC-037": {"data_quality_gap": 1}, "SC-038": {"data_quality_gap": 8}, "SC-043": {"data_quality_gap": 2, "rejected_by_system": 1}, "SC-044": {"confirmed_defect": 1, "rejected_by_system": 2}, "SC-046": {"data_quality_gap": 5, "rejected_by_system": 2}, "SC-047": {"data_quality_gap": 1, "rejected_by_system": 1}, "SC-050": {"confirmed_defect": 2, "data_quality_gap": 2, "rejected_by_system": 1}, "SC-051": {"data_quality_gap": 3, "rejected_by_system": 1}, "SC-066": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-070": {"data_quality_gap": 1}, "SC-075": {"data_quality_gap": 4}, "SC-076": {"data_quality_gap": 1}, "SC-081": {"confirmed_defect": 1, "data_quality_gap": 1}, "SC-083": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-085": {"rejected_by_system": 1}, "SC-097": {"confirmed_defect": 3}, "SC-099": {"confirmed_defect": 1, "data_quality_gap": 1, "rejected_by_system": 3}, "SC-100": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-101": {"data_quality_gap": 1}, "SC-107": {"data_quality_gap": 2, "rejected_by_system": 1}, "SC-108": {"data_quality_gap": 5, "rejected_by_system": 1}, "SC-110": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-113": {"data_quality_gap": 2}, "SC-114": {"data_quality_gap": 2}, "SC-118": {"data_quality_gap": 5, "rejected_by_system": 2}, "SC-121": {"confirmed_defect": 1, "data_quality_gap": 1}, "SC-123": {"confirmed_defect": 1, "data_quality_gap": 2, "rejected_by_system": 1}, "SC-125": {"data_quality_gap": 6, "rejected_by_system": 2}, "SC-143": {"data_quality_gap": 9}, "SC-146": {"data_quality_gap": 8, "rejected_by_system": 1}}`。
- POC 同规则网格决策分布：`{"confirmed_defect": 54, "data_quality_gap": 159, "rejected_by_system": 627}`。

## POC 结论

- 本轮 POC 稳定性可接受，但 token 优势不明显；建议先优化切片规模再扩大。

## 84 条 inventory 摘要

- inventory_rule_count=84；evidence_family_count=9。
- structured_support_level=`{"partial": 53, "ready": 30, "unsupported": 1}`。
- 本轮不替换正式链路；下一步只建议挑选证据域做 feature flag 旁路验证。

## 分病历摘要

| visit_id | patient | wall(s) | extractor_calls | adjudicator_calls | tokens | confirmed | data_gap | rejected | parse_errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1915580 | 雷德超 | 191.00 | 9 | 17 | 93439 | 2 | 21 | 61 | 0 |
| 2024757 | 游德利 | 180.40 | 9 | 13 | 86773 | 6 | 9 | 69 | 0 |
| 2287309 | 陈光华 | 215.74 | 9 | 15 | 96837 | 3 | 18 | 63 | 0 |
| 2246915 | 黄金莲 | 260.72 | 9 | 18 | 117163 | 7 | 17 | 60 | 1 |
| 1883111 | 马章媛 | 163.93 | 9 | 13 | 74935 | 2 | 5 | 77 | 0 |
| 1966656 | 周光容 | 212.68 | 9 | 19 | 102405 | 13 | 16 | 55 | 0 |
| 2311318 | 范永勤 | 211.96 | 9 | 20 | 106115 | 7 | 21 | 56 | 0 |
| 2207717 | 邹才林 | 190.90 | 9 | 13 | 91747 | 1 | 7 | 76 | 1 |
| 1870471 | 蒲云鹏 | 233.94 | 9 | 16 | 102603 | 2 | 26 | 56 | 1 |
| 2268187 | 代云聪 | 176.27 | 9 | 18 | 90510 | 11 | 19 | 54 | 0 |

## confirmed_defect 明细

- `1915580` `SC-123` discharge_record_evidence：quote=继续口服双氯芬酸钠缓释片 1 粒 qd、生血宝 15mltid、云南白药胶囊 2 粒 tid，仙灵骨葆胶囊 3 粒 bid；reason=出院带药记录中，双氯芬酸钠缓释片、云南白药胶囊、仙灵骨葆胶囊在住院期间长期/临时医嘱中未检索到相关医嘱记录，存在用药依据缺失及潜在不一致风险；且出院带药仅列出频次和剂量，未明确具体服用天数，不符合出院带药记录应详细（含用法用量天数）的要求。
- `1915580` `SC-122` discharge_record_evidence：quote=1.院外休息疗养 3 月...3.出院后 3 周到肿瘤科复诊，继续口服双氯芬酸钠缓释片 1 粒 qd、生血宝 15mltid、云南白药胶囊 2 粒 tid，仙灵骨葆胶囊 3 粒 bid；reason=出院医嘱中列出的部分带药（双氯芬酸钠缓释片、云南白药胶囊、仙灵骨葆胶囊）在住院期间长期/临时医嘱中未检索到记录（contradicting_evidence/missing_evidence指出drug_consistency_missing），且用法用量中未明确具体服用天数（dosage_duration_incomplete），导致出院医嘱的完整性和一致
- `2024757` `SC-034` order_execution_treatment_evidence：quote=病程记录：予以(4+7)利福平胶囊...口服 qd；(4+7)盐酸乙胺丁醇片...口服 qd；(4+7)异烟肼片...口服Qd，左氧氟沙星0.5g qd；硫糖铝+奥美拉唑抑酸护胃；reason=病程记录中明确记载了抗结核药物（利福平、乙胺丁醇、异烟肼、左氧氟沙星）及护胃药物（硫糖铝、奥美拉唑）的使用，但证据包显示这些关键治疗措施的医嘱记录缺失（missing_evidence），导致无法闭环核对治疗措施、药物及医嘱变化的完整记录与分析。
- `2024757` `SC-044` order_execution_treatment_evidence：quote=予以(4+7)利福平胶囊...口服 qd；(4+7)盐酸乙胺丁醇片...口服 qd；(4+7)异烟肼片...口服Qd，左氧氟沙星0.5g qd；reason=病程记录中明确记录了抗菌药物（左氧氟沙星等）的使用情况，但证据包中缺失对应的医嘱记录（missing_evidence: 抗结核药物医嘱 slot 中包含左氧氟沙星，护胃药物医嘱 slot 缺失）。根据规则，抗菌药物使用相关医嘱不完整，且使用情况未在完整的医嘱链条中体现，构成缺陷。
- `2024757` `SC-146` order_execution_treatment_evidence：quote=病程记录提及使用利福平、乙胺丁醇、异烟肼、左氧氟沙星及硫糖铝、奥美拉唑，但inpat_drug_order中无对应记录。；reason=病程记录中记录了抗结核药物和护胃药物的诊疗行为，但在提供的输入材料中未找到对应的长期或临时医嘱记录（missing_evidence），符合‘缺诊疗医嘱’的情形。
- `2024757` `SC-118` discharge_record_evidence：quote=slot: '出院情况', status: 'unknown', quote: ''; slot: '出院带药', status: 'absent'; missing_evidence: [{slot: '出院医嘱', reason: '输入材料中未包含出院医嘱的具体内容'}]；reason=出院记录存在缺项。根据证据包，'出院情况'状态为unknown且quote为空，'出院带药'状态为absent，'出院医嘱'在missing_evidence中明确缺失。规则要求出院记录应包括入院日期、出院日期、入院情况、入院诊断、诊疗经过、出院情况、出院医嘱等，当前记录缺少关键的出院情况、出院医嘱及出院带药内容，不符合完整性要求。
- `2024757` `SC-123` discharge_record_evidence：quote=slot: '出院带药', status: 'absent', source_table: 'inpat_drug_order', quote: ''; missing_evidence: [{slot: '出院带药完整信息', reason: '输入材料中未包含出院带药的具体药名、剂量、频次、用法、天数等原文'}]；reason=出院带药记录缺失或不详细。证据包显示'出院带药'状态为absent，且missing_evidence指出未包含出院带药的具体药名、剂量、频次、用法等原文。规则要求核查出院带药记录的详细程度，应记录清楚药品名称、用药剂量等，当前完全缺失该部分信息。
- `2024757` `SC-122` discharge_record_evidence：quote=missing_evidence: [{slot: '出院医嘱', reason: '输入材料中未包含出院医嘱的具体内容（如后续用药指导、复诊时间等）。'}]；reason=无出院医嘱或出院医嘱不全。证据包中missing_evidence明确指出'出院医嘱'缺失，reason为'输入材料中未包含出院医嘱的具体内容（如后续用药指导、复诊时间等）'。规则要求出院医嘱应包括用药、复查、随访等指导意见，当前记录缺失。
- `2287309` `SC-093` surgery_perioperative_evidence：quote=slot: 麻醉记录, status: absent, reason: 输入材料中麻醉记录表内容为空，缺失麻醉过程详细数据。；reason=证据包中麻醉记录状态为absent，且missing_evidence明确指出麻醉记录表内容为空，缺失麻醉过程详细数据，违反规则要求核查手术患者是否有麻醉记录。
- `2287309` `SC-094` surgery_perioperative_evidence：quote=slot: 麻醉记录, status: absent；reason=由于缺乏麻醉记录（见SC-093），无法核查麻醉记录内容的完整性和清晰度，包括患者一般情况、麻醉方式、术中用药等必要内容，符合规则描述的缺项或描述不清情形。
- `2287309` `SC-103` surgery_perioperative_evidence：quote=slot: 安全核查, status: absent, reason: 输入材料中手术安全核查记录表内容为空，缺失三方核查信息。；reason=证据包中手术安全核查记录状态为absent，且missing_evidence明确指出缺失三方核查信息，违反规则要求核查手术安全核查记录的完整性。
- `2246915` `SC-107` surgery_perioperative_evidence：quote=D10 source_table=surgery_record title=手术记录 time=2026-02-27 12:40:19; D12 source_table=postsurg_firstcourse_record title=术后首次病程记录 time=2026-02-27 13:15:28; senio；reason=术后三天内无连续病程记录或无上级医师查看病人记录。手术时间为2026-02-27，术后第一天应为2026-02-28，第二天为2026-03-01，第三天为2026-03-02。证据显示术后第一天的上级医师查房记录时间为2026-03-09（术后第10天），严重滞后；且术后第二天和第三天的日常病程记录中未体现上级医师查房内容，不符合‘术后三天内要有手术者或主
- `2246915` `SC-081` surgery_perioperative_evidence：quote=源数据中术前小结内容为空；reason=证据包中明确标记 missing_preop_summary，且 missing_evidence 指出术前小结内容为空。根据规则 SC-081，术前小结缺项属于缺陷。
- `2246915` `SC-093` surgery_perioperative_evidence：quote=源数据中麻醉记录内容为空；reason=证据包中明确标记 missing_anesthesia_record，且 missing_evidence 指出麻醉记录内容为空。根据规则 SC-093，核查手术患者是否有麻醉记录，缺失即构成缺陷。
- `2246915` `SC-097` surgery_perioperative_evidence：quote=记录时间：2026-02-27 12:40:19; 手术时间:2026年02月27日 09:25; 源数据中麻醉记录内容为空；reason=手术记录中手术时间与术后首次病程记录中的手术时间存在明显冲突（分别为12:40和09:25），且缺少麻醉记录以核实术中出血量等关键数据，导致手术记录完整性与清晰度不足。
- `2246915` `SC-103` surgery_perioperative_evidence：quote=源数据中手术安全核查记录内容为空；reason=证据包中明确标记 missing_safety_check，且 missing_evidence 指出手术安全核查记录内容为空。根据规则 SC-103，核查手术安全核查记录的完整性，缺失即构成缺陷。
- `2246915` `SC-105` surgery_perioperative_evidence：quote=D12 source_table=postsurg_firstcourse_record title=术后首次病程记录 time=2026-02-27 13:15:28；reason=术后首次病程记录中缺失关键要素。根据规则要求，术后首次病程记录应包含手术时间、术中诊断、麻醉方式、手术方式、手术简要经过、术后处理措施、术后应当特别注意观察的事项等。现有证据显示该记录仅记录了手术时间和查房内容（术后第二天），未体现术中诊断、麻醉方式、手术方式及手术简要经过等核心内容，属于描述不清/缺项。
- `2246915` `SC-123` discharge_record_evidence：quote=1.注意休息、营养; 2.禁性生活，剧烈运动三月，禁重体力劳动; 3.1 月后门诊定期随访、不适随诊。；reason=出院带药记录缺失或不详细。证据包显示出院带药状态为absent，且missing_evidence指出无法确认出院带药的药名、剂量、频次、用法、天数。虽然日常病程中有用药建议，但出院医嘱部分未列出具体药品名称、剂量、给药途径及时间，不符合出院带药记录需清晰具体的要求。
- `1883111` `SC-123` discharge_record_evidence：quote=患者马章媛...患方要求出院到上级医院治疗。1.院外继续治疗 2.随访方式：门诊随访周期：每 1 个月随访日期:2025 年 08 月 10 日。；reason=出院记录中未列出具体的出院带药名称、剂量、给药途径及用法用量。虽然出院医嘱提及“继续抗肿瘤治疗”和“院外继续治疗”，但缺乏具体的药品明细（如依诺肝素钠的具体用法），不符合出院带药记录应详细记录药品名称、剂量、途径、时间等要求。
- `1883111` `SC-125` discharge_record_evidence：quote=1.院外继续治疗 2.随访方式：门诊随访周期：每 1 个月随访日期:2025 年 08 月 10 日。; 给于复方电解质醋酸钠葡萄糖补充能量，依诺肝素钠抗凝，等对症支持治疗；reason=出院诊断顺序错误。根据规范，主要诊断应为导致患者本次住院主要原因的疾病。本例患者因“左侧乳腺癌术后复发伴骨、双肺转移”入院，该诊断应排在首位。然而，出院记录及病程记录中列出的诊断顺序将“左侧乳腺癌...”列为第1项，但后续诊断中包含“骨继发恶性肿瘤”、“双肺继发恶性肿瘤”等具体转移部位诊断，且存在“高血压”、“冠心病”等基础病。更关键的是，在提供的`admi
- `1966656` `SC-034` order_execution_treatment_evidence：quote=继续予以左氧氟沙星抗感染,其余治疗上继续予以卡络磺钠止血、补液等对症处理；reason=病程记录中明确提及使用左氧氟沙星抗感染、卡络磺钠止血及补液等治疗措施，但证据包中缺失对应的药物医嘱或执行记录（missing_evidence_antibiotic, missing_evidence_hemostatic, missing_evidence_fluid），导致无法证实治疗措施已正确下达和执行，符合‘病程中对治疗措施、药物、医嘱变化未记录或分
- `1966656` `SC-044` order_execution_treatment_evidence：quote=继续予以左氧氟沙星抗感染；reason=病程记录中记录了抗菌药物（左氧氟沙星）的使用情况，但在提供的证据包中未找到对应的抗菌药物医嘱记录（missing_evidence_antibiotic）。根据规则，抗菌药物治疗的住院患者病历中，抗菌药物使用相关医嘱应完整，且使用情况在病程记录中有相应记录。此处医嘱缺失导致记录不完整。
- `1966656` `SC-146` order_execution_treatment_evidence：quote=继续予以左氧氟沙星抗感染,其余治疗上继续予以卡络磺钠止血、补液等对症处理；reason=病程记录中明确提及使用左氧氟沙星抗感染、卡络磺钠止血及补液等治疗措施，但在提供的证据包中未找到对应的长期或临时医嘱记录，导致诊疗医嘱与病程记录不一致。
- `1966656` `SC-081` surgery_perioperative_evidence：quote=术前小结文档内容为空，缺少关键的手术指征、禁忌症排除及风险评估描述。；reason=术前小结文档状态为absent，内容为空，无法提供简要病情、术前诊断、手术指征等必要内容，符合规则描述的缺项或描述不清。
- `1966656` `SC-084` surgery_perioperative_evidence：quote=术前小结 status: absent ... missing_evidence: 术前小结文档内容为空，缺少关键的手术指征、禁忌症排除及风险评估描述。；reason=规则要求术前讨论结论必须记入病历。证据显示存在术前讨论记录（2025-09-04），但required_evidence中明确标记“术前小结”状态为absent，且missing_evidence指出“术前小结文档内容为空”。术前小结是体现术前讨论结论（如手术指征、拟行术式等）的关键文书之一，其缺失导致术前讨论结论未在规定的标准文书中完整体现/记入。
- `1966656` `SC-092` surgery_perioperative_evidence：quote=required_evidence slot '麻醉记录' status: absent；reason=规则要求麻醉术前访视记录完整。证据包中required_evidence显示'麻醉记录'状态为absent，且missing_evidence指出'麻醉记录单'内容为空。虽然术后首次病程提到了麻醉方式，但这属于术后记录，不能替代术前访视记录。术前访视记录缺项。
- `1966656` `SC-093` surgery_perioperative_evidence：quote=麻醉记录文档内容为空，缺少麻醉过程、生命体征监测及用药记录。；reason=麻醉记录文档状态为absent，缺失麻醉记录存在性证据。
- `1966656` `SC-094` surgery_perioperative_evidence：quote=麻醉记录文档内容为空，缺少麻醉过程、生命体征监测及用药记录。；reason=由于麻醉记录整体缺失（status: absent），导致无法核查其内容的完整性和清晰度，符合规则描述。
- `1966656` `SC-106` surgery_perioperative_evidence：quote=coverage_flags: bundle_missing:postane_surveil_record；reason=规则要求麻醉术后访视记录。证据包中programmatic_coverage的coverage_flags明确包含'bundle_missing:postane_surveil_record'，且required_evidence中未列出麻醉术后访视记录为present。缺失该记录构成缺陷。
- `1966656` `SC-097` surgery_perioperative_evidence：quote=手术结束时间: (empty)；reason=手术记录中缺失手术结束时间，导致无法计算手术时长，且缺少麻醉记录、术前小结及手术安全核查记录等关键围手术期文书，不符合手术记录内容完整性和清晰度的要求。
- `1966656` `SC-103` surgery_perioperative_evidence：quote=手术安全核查记录文档内容为空，缺少三方核查签字及核对信息。；reason=手术安全核查记录文档状态为absent，缺失三方核查签字及核对信息，符合规则描述。
- `1966656` `SC-118` discharge_record_evidence：quote=required_evidence中slot '出院诊断' status为absent; required_evidence中未提供入院日期、出院日期、入院情况、入院诊断字段证据; trigger quotes中未包含入院/出院日期及医师签名信息；reason=出院记录中缺失入院日期、出院日期、入院情况、入院诊断及医师签名等关键要素，不符合出院记录完整性要求。
- `1966656` `SC-125` discharge_record_evidence：quote=required_evidence中slot '出院诊断' status=absent, source_table='admission_record_diagnosis', quote='<empty>'；reason=出院诊断字段在结构化数据中缺失（status=absent），无法确认出院诊断是否准确、规范及顺序正确，属于漏填或无法校验。
- `2311318` `SC-107` surgery_perioperative_evidence：quote=手术开始时间：2026-04-06 11:00:00+08 手术结束时间：2026-04-06 12:30:00+08; 患者于2026年4月6日在全麻下行左侧内踝骨折闭合复位空心螺钉内固定+左侧外踝骨折切开复位钢板内固定术... record_time: 2026-04-14 08:00:00；reason=术后三天内无连续病程记录或无上级医师查看病人记录。手术时间为2026-04-06，术后首次病程记录时间为2026-04-14，间隔超过3天；且术后3天内（4月6日-9日）缺失所有日常病程记录及上级查房记录，不符合术后需连续记录三天病程并包含上级医师查房的要求。
- `2311318` `SC-081` surgery_perioperative_evidence：quote=术前小结缺项或描述不清(简要病情、术前诊断、手术指征、拟施手术名称和方式、拟施麻醉方式、注意事项，并记录手术者术前查看患者相关情况)；reason=术前小结缺项或描述不清。证据包显示术前小结（presurg_summary）状态为absent，源数据中该文档内容为空，导致无法核查简要病情、术前诊断、手术指征等必要内容。
- `2311318` `SC-093` surgery_perioperative_evidence：quote=检查内容：核查手术患者是否有麻醉记录。麻醉记录应另页书写，由麻醉医师在麻醉实施中记录麻醉经过及处理措施，应符合WS329-2011标准。本规则检查的是麻醉记录的存在性。；reason=无麻醉记录。证据包显示麻醉记录（anesthesia_record）状态为absent，源数据中该文档内容为空，不符合WS329-2011标准关于麻醉记录存在性的要求。
- `2311318` `SC-103` surgery_perioperative_evidence：quote=检查内容：核查手术安全核查记录的完整性和清晰度。虽然有核查记录，但可能缺少病人身份、手术部位、手术方式、麻醉及手术风险、物品清点、输血信息（如适用）、三方签字等必要内容。本规则检查的是手术安全核查记录的质量。；reason=手术安全核查记录缺项或描述不清。证据包显示手术安全核查记录（surgery_safecheck_record）状态为absent，源数据中该文档内容为空，缺少病人身份、手术部位、三方签字等必要内容。
- `2311318` `SC-105` surgery_perioperative_evidence：quote=患者于2026年4月6日在全麻下行左侧内踝骨折闭合复位空心螺钉内固定+左侧外踝骨折切开复位钢板内固定术... record_time: 2026-04-14 08:00:00；reason=术后首次病程记录存在严重的时间逻辑错误，记录时间为2026-04-14，而手术时间为2026-04-06，间隔8天，不符合‘术后即时完成’的定义，且内容描述过于简略，未体现术中诊断、麻醉方式等完整要素（虽提及全麻和术式，但时间缺失导致记录无效/不清）。
- `2311318` `SC-118` discharge_record_evidence：quote=患者神志清楚,对答切题...现患者病情明显好转,拟转回当地医院继续治疗,拟于今日办理转院手续。；reason=出院记录中缺失“入院日期”、“出院日期”及“入院诊断”字段。证据显示出院记录正文仅包含患者现状、诊疗经过和出院医嘱，未明确记录入院与出院的具体日期，也未列出独立的出院诊断列表（coverage_flags: discharge_diagnosis_missing_in_text），不符合出院记录完整性要求。
- `2311318` `SC-122` discharge_record_evidence：quote=1.院外注意休养,低盐低脂糖尿病饮食,每日监测血压血糖。2.每2-3天换药一次...6.如有不适,立即就诊。；reason=出院医嘱部分存在明显缺项。根据evidence_package中的required_evidence和missing_evidence，'出院带药'字段状态为absent，且missing_evidence明确指出'出院记录中未列出具体的出院带药名称、剂量、频次、用法及天数'。出院医嘱应包含用药指导，缺失具体带药信息属于医嘱不全。
- `2207717` `SC-123` discharge_record_evidence：quote=5、出院带药：神农镇痛膏 1贴 外用 bid*7天;；reason=出院带药‘神农镇痛膏’仅记录了用法用量（1贴 外用 bid*7天），未明确记录具体的给药途径细节（如‘外用’虽提及但缺乏更详细的贴敷部位或频次说明，且通常膏药需注明具体使用部位或方法，更重要的是，根据规则描述‘应记录清楚药品名称、用药剂量、给药途径、用药时间、减药停药安排等’，此处‘bid’指每日两次，但未明确是早晚各一次还是其他具体时间，且缺少明确的减停药
- `1870471` `SC-097` surgery_perioperative_evidence：quote=手术开始时间：2025-06-29 23:25:00+08；reason=missing_evidence指出手术结束时间、手术医师签名、麻醉医师签名、失血量字段为空，导致手术记录缺项或描述不清。
- `1870471` `SC-118` discharge_record_evidence：quote=required_evidence: {"slot": "出院诊断", "status": "absent"}；reason=出院记录中缺失‘入院诊断’和‘出院诊断’字段。证据包显示 required_evidence 中 '出院诊断' 状态为 absent，且 missing_evidence 明确指出无出院诊断表或明确诊断列表。根据规则 SC-118，出院记录必须包含入院诊断和出院诊断，当前记录不完整。
- `2268187` `SC-081` surgery_perioperative_evidence：quote=输入材料中未包含独立的术前小结文档；reason=术前小结缺项或描述不清。证据包明确指出未包含独立的术前小结文档，且日常病程记录中仅提及手术建议及实施过程，缺乏术前小结要求的简要病情、术前诊断、手术指征、拟施手术名称和方式、拟施麻醉方式、注意事项等完整内容。
- `2268187` `SC-083` surgery_perioperative_evidence：quote=输入材料中未包含术前讨论记录文档；reason=四级手术术前讨论未多学科讨论。证据包显示未包含术前讨论记录文档。虽然该手术为局部浸润麻醉下的清创引流术，通常不属于四级手术，但鉴于病历中完全缺失术前讨论相关记录（包括非四级手术的常规术前讨论），且规则要求住院患者手术必须实施术前讨论，此处判定为术前讨论记录缺失导致的缺陷。若严格依据手术分级，该手术可能无需多学科讨论，但术前讨论本身是必须的，故归因于术前讨论记
- `2268187` `SC-084` surgery_perioperative_evidence：quote=输入材料中未包含术前讨论记录文档；reason=术前讨论的结论未记入病历。由于缺乏术前讨论记录，自然无法体现术前讨论结论。
- `2268187` `SC-085` surgery_perioperative_evidence：quote=输入材料中未包含术前讨论记录文档；reason=结论记录不完整。同上，缺乏术前讨论记录导致结论缺失。
- `2268187` `SC-092` surgery_perioperative_evidence：quote=输入材料中未包含麻醉科专用麻醉记录单；reason=麻醉术前访视记录缺项或描述不清。证据包明确指出未包含麻醉科专用麻醉记录单及相关访视记录。
- `2268187` `SC-093` surgery_perioperative_evidence：quote=输入材料中未包含麻醉科专用麻醉记录单；reason=无麻醉记录。证据包明确指出未包含麻醉科专用麻醉记录单。
- `2268187` `SC-094` surgery_perioperative_evidence：quote=输入材料中未包含麻醉科专用麻醉记录单；reason=麻醉记录缺项或描述不清。由于缺乏麻醉记录单，无法核查其内容的完整性和清晰度。
- `2268187` `SC-106` surgery_perioperative_evidence：quote=bundle_missing:postane_surveil_record；reason=麻醉术后访视记录缺项或描述不清。证据包中未包含麻醉术后访视记录，且missing_evidence中虽未明确列出此项，但anesthesia_record缺失通常伴随访视记录缺失，且coverage_flags中无postane_surveil_record。
- `2268187` `SC-103` surgery_perioperative_evidence：quote=输入材料中未包含手术安全核查表；reason=手术安全核查记录缺项或描述不清。证据包明确指出未包含手术安全核查表。
- `2268187` `SC-105` surgery_perioperative_evidence：quote=输入材料中缺少手术当日或次日立即书写的术后首次病程记录，仅见后续日常病程记录；reason=术后首次病程记录缺项或描述不清。证据包明确指出缺少手术当日或次日立即书写的术后首次病程记录。
- `2268187` `SC-118` discharge_record_evidence：quote=与患者及家属沟通，建议行左膝关节感染切开、清创引流术，患者及家属同意后于2026-03-10 11:41在局部浸润麻醉下行左膝皮肤感染清创引流术。；reason=出院记录中诊疗经过内容过于简略，仅描述了一次手术过程，未全面详细记录病情演变及住院期间的其他重要诊疗活动（如抗感染治疗、查房调整等），不符合规则要求的‘全面详细’。

## 是否值得扩大

- 建议先做同规则族成本评估和 POC issue 抽样复核，再决定是否接入更多规则族；本 POC 不改变正式主链路。
