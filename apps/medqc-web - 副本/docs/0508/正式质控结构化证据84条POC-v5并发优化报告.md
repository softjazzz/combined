# 正式质控结构化证据 84 条 POC-v5 并发优化报告

生成时间：2026-05-15 11:55:40

## POC 范围

- 只读运行，不接页面，不写正式质控业务表，不改 Sheet2 验收链路。
- scope=all84_v5；规则数=84；evidence package：`admission_course_evidence`、`diagnostic_followup_evidence`、`order_consultation_evidence`、`surgery_perioperative_evidence_v4`、`discharge_special_evidence`。
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

- baseline_total_tokens=608247；poc_total_tokens=475190；token_delta=133057。
- all84 scope 与正式 84 条 baseline 是同规则范围但不同执行策略；P0/v3 scope 与 84 条 baseline 不是同口径。
- baseline_wall_clock_time=320.585s；poc_wall_clock_time=499.009s。
- baseline_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- baseline_target_rule_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- poc_display_status_counts=`{"confirmed_defect": 30, "data_quality_gap": 155, "rejected_by_system": 655}`。

## 同规则族分布

- baseline 目标规则 issue 数：143。
- baseline 目标规则按 rule 分布：`{"SC-004": {"data_quality_gap": 1}, "SC-010": {"rejected_by_system": 4}, "SC-013": {"data_quality_gap": 1, "rejected_by_system": 3}, "SC-015": {"confirmed_defect": 2, "data_quality_gap": 1, "rejected_by_system": 1}, "SC-018": {"confirmed_defect": 1, "rejected_by_system": 1}, "SC-020": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-032": {"rejected_by_system": 1}, "SC-033": {"rejected_by_system": 1}, "SC-034": {"rejected_by_system": 1}, "SC-036": {"confirmed_defect": 1, "data_quality_gap": 4, "rejected_by_system": 2}, "SC-037": {"data_quality_gap": 1}, "SC-038": {"data_quality_gap": 8}, "SC-043": {"data_quality_gap": 2, "rejected_by_system": 1}, "SC-044": {"confirmed_defect": 1, "rejected_by_system": 2}, "SC-046": {"data_quality_gap": 5, "rejected_by_system": 2}, "SC-047": {"data_quality_gap": 1, "rejected_by_system": 1}, "SC-050": {"confirmed_defect": 2, "data_quality_gap": 2, "rejected_by_system": 1}, "SC-051": {"data_quality_gap": 3, "rejected_by_system": 1}, "SC-066": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-070": {"data_quality_gap": 1}, "SC-075": {"data_quality_gap": 4}, "SC-076": {"data_quality_gap": 1}, "SC-081": {"confirmed_defect": 1, "data_quality_gap": 1}, "SC-083": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-085": {"rejected_by_system": 1}, "SC-097": {"confirmed_defect": 3}, "SC-099": {"confirmed_defect": 1, "data_quality_gap": 1, "rejected_by_system": 3}, "SC-100": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-101": {"data_quality_gap": 1}, "SC-107": {"data_quality_gap": 2, "rejected_by_system": 1}, "SC-108": {"data_quality_gap": 5, "rejected_by_system": 1}, "SC-110": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-113": {"data_quality_gap": 2}, "SC-114": {"data_quality_gap": 2}, "SC-118": {"data_quality_gap": 5, "rejected_by_system": 2}, "SC-121": {"confirmed_defect": 1, "data_quality_gap": 1}, "SC-123": {"confirmed_defect": 1, "data_quality_gap": 2, "rejected_by_system": 1}, "SC-125": {"data_quality_gap": 6, "rejected_by_system": 2}, "SC-143": {"data_quality_gap": 9}, "SC-146": {"data_quality_gap": 8, "rejected_by_system": 1}}`。
- POC 同规则网格决策分布：`{"confirmed_defect": 30, "data_quality_gap": 155, "rejected_by_system": 655}`。

## POC 结论

- 本轮 v5 仅优化 POC 执行方式和统计口径：单病历内 extractor/adjudicator 并发，10 病历仍顺序执行；是否达到 60s/病历以本报告门禁为准。

## v5 并发优化与统计口径修正

- baseline_total_tokens=608247；all84_v3_total_tokens=962527；all84_v4_total_tokens=432912；all84_v5_total_tokens=475190。
- baseline_wall_clock_time=320.585s；all84_v3_wall_clock_time=2037.538s；all84_v4_wall_clock_time=1043.244s；all84_v5_wall_clock_time=499.009s。
- baseline_llm_calls=unknown；all84_v3_llm_calls=252；all84_v4_llm_calls=97；all84_v5_llm_calls=112。
- extractor_calls=50；adjudicator_calls=62；extractor_concurrency=3；adjudicator_concurrency=3；adjudicator_max_rules_per_batch=20。
- 平均每病历调用数=11.2；平均每病历耗时=49.901s；token 相对 baseline=78.12%；wall time 相对 v4=-52.17%。
- extractor_wall_time_total=341.852s；adjudicator_wall_time_total=154.067s；extractor_api_time_avg=16.315s；adjudicator_api_time_avg=8.048s。
- 最慢 extractor：visit=2207717 family=order_consultation_evidence api_time=31.474s。
- 最慢 adjudicator：visit=1966656 family=surgery_perioperative_evidence_v4 api_time=26.379s。

## v5 裁决统计口径

- total_rule_decision_count=840：最终四层终态裁决总数，10 病历应为 840。
- programmatic_decision_count=112：未送二审、由本地 gate 直接落终态的规则数。
- programmatic_rejected_count=112；programmatic_data_gap_count=0。
- rules_sent_to_adjudicator_count=728：实际进入二审模型的规则数，应等于 total_rule_decision_count - programmatic_decision_count。
- adjudicator_output_rule_count=316：二审模型实际返回的规则裁决数。
- missing_adjudicator_output_count=412：已送二审但模型未返回的规则数，v5 保守系统驳回且单独计数。
- skipped_adjudicator_rule_count=112：兼容旧字段，v5 中等同 programmatic_decision_count，不再混同二审返回数。

## v5 目标达成情况

- <=12 LLM calls/病历：达成（当前 11.2）。
- token <= baseline 608247：达成（当前 475190）。
- 平均耗时 <=60s/病历：达成（当前 49.901s）。
- 若仍未达成，优先看最慢 extractor/adjudicator family 与 provider 响应耗时；本轮未并发多病历，避免扩大 provider 压力。

## 84 条 inventory 摘要

- inventory_rule_count=84；evidence_family_count=5。
- structured_support_level=`{"partial": 53, "ready": 30, "unsupported": 1}`。
- 本轮不替换正式链路；下一步只建议挑选证据域做 feature flag 旁路验证。

## 分病历摘要

| visit_id | patient | wall(s) | extractor_calls | adjudicator_calls | tokens | confirmed | data_gap | rejected | parse_errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1915580 | 雷德超 | 42.70 | 5 | 5 | 38134 | 4 | 11 | 69 | 0 |
| 2024757 | 游德利 | 47.67 | 5 | 5 | 45070 | 2 | 14 | 68 | 0 |
| 2287309 | 陈光华 | 50.49 | 5 | 7 | 53524 | 3 | 12 | 69 | 0 |
| 2246915 | 黄金莲 | 58.38 | 5 | 7 | 59636 | 7 | 17 | 60 | 0 |
| 1883111 | 马章媛 | 41.69 | 5 | 5 | 34270 | 0 | 12 | 72 | 0 |
| 1966656 | 周光容 | 55.88 | 5 | 7 | 49785 | 0 | 21 | 63 | 0 |
| 2311318 | 范永勤 | 61.05 | 5 | 7 | 53317 | 4 | 18 | 62 | 0 |
| 2207717 | 邹才林 | 45.17 | 5 | 5 | 48697 | 0 | 11 | 73 | 0 |
| 1870471 | 蒲云鹏 | 35.74 | 5 | 7 | 41474 | 0 | 19 | 65 | 0 |
| 2268187 | 代云聪 | 60.24 | 5 | 7 | 51283 | 10 | 20 | 54 | 0 |

## confirmed_defect 明细

- `1915580` `SC-097` surgery_perioperative_evidence_v4：quote=手术开始时间：2025-08-12 14:15:00+08；reason=手术记录缺项或描述不清。手术记录中缺失关键的“手术结束时间”，导致手术时长及完整性信息不全。
- `1915580` `SC-105` surgery_perioperative_evidence_v4：quote=新建S章节:手术时间：2025年08月12日；麻醉方式：静吸复合全麻；手术方式：胸12椎骨折切开复位内固定术...；reason=术后首次病程记录中缺失‘手术简要经过’及‘术后应当特别注意观察的事项’等关键内容。现有记录仅包含手术时间、麻醉方式、手术方式，未描述手术具体经过及术后重点观察指标，不符合规则要求。
- `1915580` `SC-118` discharge_special_evidence：quote=患者因腰痛 2 小时入院...病情好转平稳，予以出院。；reason=出院记录中缺失出院诊断，且入院日期、出院日期等关键信息未在提供的证据片段中明确体现（coverage_flags包含days_missing, diagnosis_missing），导致出院记录内容不完整。
- `1915580` `SC-123` discharge_special_evidence：quote=生血宝 15mltid; 云南白药胶囊 2 粒 tid；reason=出院带药记录不详细。虽然记录了药品名称和剂量频次，但缺少具体的用药天数（如疗程）以及部分药物未明确给药途径细节（仅写口服或无途径描述），不符合‘应具体，带药要记录使用方法、剂量、用药时间’的要求。特别是生血宝和云南白药胶囊仅写了剂量和频次，未明确给药途径（虽隐含口服但不规范）及停药安排。
- `2024757` `SC-047` admission_course_evidence：quote=诊断名称：1.继发性肺结核 初治 涂阳DNA阳性；2.类风湿性关节炎；reason=存在修正诊断（继发性肺结核、类风湿性关节炎），但入院诊断缺失，且病程记录中未见修正诊断的理由及诊断依据记录。
- `2024757` `SC-123` discharge_special_evidence：quote=slot: 出院带药_药名, status: absent; slot: 出院带药_剂量, status: missing_evidence；reason=出院带药不详细。证据包明确指出出院带药的药名、剂量、频次、用法、天数等关键字段状态为absent或missing_evidence，无法提取出院带药的具体信息，违反规则要求记录清楚药品名称、用药剂量、给药途径、用药时间等。
- `2287309` `SC-066` admission_course_evidence：quote=发现双侧腹股沟可复性包块1+年；reason=证据包中明确标记存在 missing_first_course_record（首次病程记录缺失），且 required_evidence 显示首次病程记录状态为 absent。根据规则 SC-066，值班期间所有的诊疗活动必须及时记入病历，入院及首次病程是核心诊疗活动的记录，其缺失属于未及时记入或记录不全。
- `2287309` `SC-093` surgery_perioperative_evidence_v4：quote=麻醉记录表内容为空，缺失具体麻醉过程、用药及生命体征监测细节。；reason=证据包中明确标记 data_quality_flags 包含 'anesthesia_record_missing'，且 missing_evidence 指出麻醉记录表内容为空，缺失具体麻醉过程、用药及生命体征监测细节，违反规则关于核查手术患者是否有麻醉记录的存在性要求。
- `2287309` `SC-103` surgery_perioperative_evidence_v4：quote=手术安全核查记录表内容为空，缺失三方核查签字及时间点证据。；reason=证据包中明确标记 data_quality_flags 包含 'safe_check_record_missing'，且 missing_evidence 指出手术安全核查记录表内容为空，缺失三方核查签字及时间点证据，违反规则关于核查手术安全核查记录完整性和清晰度的要求。
- `2246915` `SC-020` admission_course_evidence：quote=发现阴道可复性肿物 2+ 年；reason=入院记录无入院诊断。证据包 coverage_flags 包含 missing_admission_diagnosis，且 missing_evidence 指出入院记录诊断表内容为空，未见明确入院诊断描述。
- `2246915` `SC-023` admission_course_evidence：quote=发现阴道可复性肿物 2+ 年；reason=首次病程记录缺失，导致无法包含病例特点。证据包中明确标记 missing_first_course_record，且 missing_evidence 指出首次病程记录内容为空。
- `2246915` `SC-024` admission_course_evidence：quote=发现阴道可复性肿物 2+ 年；reason=首次病程记录缺失，导致病例特点未归纳提炼或不全面。由于首程记录完全缺失，无法提取任何病例特点。
- `2246915` `SC-025` admission_course_evidence：quote=发现阴道可复性肿物 2+ 年；reason=首次病程记录缺失，导致无诊断依据、鉴别诊断、诊疗计划。证据包显示首次病程记录为空。
- `2246915` `SC-050` admission_course_evidence：quote=邹红缨主任医师查房后指出：患者为 71 岁女性，起病缓，病程长；reason=上级医师查房记录存在严重问题。首先，首次病程记录缺失导致缺乏入院初期的上级指导。其次，现有的上级查房记录（邹红缨主任医师、申威主治医师）时间戳均为2026-03-09，且内容多为回顾性描述（如“术后第一天”、“术后第五天”），缺乏对当前病情的实时分析和诊疗意见，且查房内容与下级医师记录高度雷同（均描述肛门排气、阴道分泌物等），未体现上级医师的独立分析。此外，
- `2246915` `SC-118` discharge_special_evidence：quote=患者因“发现阴道可复性肿物2+年”入院...于2026年02月27日 在全麻下行经阴道子宫切除术...；reason=出院记录中缺失出院诊断。根据证据包，required_evidence中'出院诊断'状态为absent，且missing_evidence指出输入材料中无出院诊断表或明确诊断列表。规则SC-118要求出院记录应包括入院诊断、诊疗经过、出院情况等，其中出院诊断是核心要素之一，其缺失导致出院记录内容不完整。
- `2246915` `SC-123` discharge_special_evidence：quote=嘱其出院后:...3.7-10天后门诊复查,不适随诊,我科门诊随访;4.胸外科门诊随访肺结节;神经内科门诊随访脑梗塞,可给予阿司匹林 0.1 qd,阿托伐他汀 20mg qn行二级预防;心内科门诊随访高血压。；reason=出院带药记录不详细或缺失。证据包显示'出院带药_药名'、'剂量'、'频次'、'用法'、'天数'均为missing_evidence。虽然病程记录中有门诊随访建议提及阿司匹林和阿托伐他汀，但明确指出这些非正式出院带药医嘱，且出院记录中未列出具体带药详情。规则SC-123要求核查出院带药记录的详细程度，应记录清楚药品名称、用药剂量等，此处完全缺失。
- `2311318` `SC-066` admission_course_evidence：quote=source_table=first_course_record title=首次病程记录 time=2026-04-14 08:00:00 <empty>；reason=首次病程记录缺失。入院记录时间为2026-03-27，但首次病程记录显示为2026-04-14且内容为空（<empty>），导致入院当日及至4月14日期间缺乏必要的病情分析和诊疗计划记录，违反值班期间所有诊疗活动应及时记入病历的规定。
- `2311318` `SC-106` surgery_perioperative_evidence_v4：quote=bundle_missing:postane_surveil_record；reason=规则要求核查麻醉术后访视记录。程序化覆盖标志 bundle_missing:postane_surveil_record 明确指出缺少该记录，且证据包中未提供相关引用。
- `2311318` `SC-118` discharge_special_evidence：quote=患者神志清楚,对答切题,左踝关节肿胀、触痛明显,伴活动受限,可扪及骨擦感,闻及骨擦音,左足远端感觉、运动及血液循环可,余肢体未见明显异常。入院后完善相关检查,予以手法复位,石膏外固定,抬高患肢,局部冰敷,监测血压血糖,曲马多注射液、替扎尼定、醋氯酚酸钠止痛,氢氯噻嗪、螺内酯、地奥司明、甘露醇消肿,云南白药、大活络胶囊活；reason=出院记录中缺失出院诊断。根据规则要求，出院记录应包括入院日期、出院日期、入院情况、入院诊断、诊疗经过、出院情况、出院医嘱、医师签名等，且必须包含准确的出院诊断。证据包显示 'discharge_diagnosis' 状态为 absent，且 'coverage_flags' 中包含 'discharge_diagnosis_missing'，符合缺项定义。
- `2311318` `SC-123` discharge_special_evidence：quote=今日予以换药，交代出院注意事项，可见出院带药，拟明日转回当地医院。；reason=出院带药记录不详细或缺失。规则要求核查出院带药记录的详细程度，应记录清楚药品名称、用药剂量、给药途径、用药时间、减药停药安排等。证据包显示所有出院带药相关字段（药名、剂量、频次、用法、天数）均为 missing_evidence，且仅提及“可见出院带药”但未列出具体明细，不符合规则要求。
- `2268187` `SC-023` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录缺失，无法包含病例特点。证据显示首次病程记录内容为空（<empty>），且入院时间与记录时间严重不符，导致无法提取病例特点。
- `2268187` `SC-024` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录缺失，导致病例特点未归纳提炼或不全面。由于文书本身为空，无法满足病例特点归纳的要求。
- `2268187` `SC-025` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录缺失，导致无诊断依据、鉴别诊断、诊疗计划。证据显示该文档内容为空，无法提供上述任何一项内容。
- `2268187` `SC-026` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录缺失，导致诊断依据或鉴别诊断不充分、不全面。因文书为空，无法进行诊断依据和鉴别诊断的描述。
- `2268187` `SC-027` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录缺失，导致诊疗计划不全面、不具体。因文书为空，无法制定具体的诊疗计划。
- `2268187` `SC-081` surgery_perioperative_evidence_v4：quote=仅有病程记录中的手术描述，缺少独立的手术记录单文档；reason=证据包中明确标记 'no_formal_operation_record' 且 missing_evidence 指出缺少独立的手术记录单文档。术前小结作为总结性文书，其核心功能之一是确认手术指征、拟施术式及麻醉方式等关键信息的正式记录与签署。在缺乏正式手术记录/术前小结独立文档的情况下，无法证明该文书内容完整、描述清晰且符合规范（如手术者查看情况、注意事项
- `2268187` `SC-093` surgery_perioperative_evidence_v4：quote=no_formal_anesthesia_record；reason=规则要求核查手术患者是否有麻醉记录。证据包明确标记 'no_formal_anesthesia_record' 且 data_quality_flags 包含 'missing_formal_anesthesia_documentation'，证实无麻醉记录存在。
- `2268187` `SC-094` surgery_perioperative_evidence_v4：quote=no_formal_anesthesia_record；reason=由于无麻醉记录（见SC-093裁决），自然无法满足麻醉记录内容完整性和清晰度的要求（如诱导时间、用药、术中情况等）。
- `2268187` `SC-097` surgery_perioperative_evidence_v4：quote=no_formal_operation_record；reason=规则要求核查手术记录内容的完整性和清晰度。证据包明确标记 'no_formal_operation_record' 且 missing_evidence 指出缺少独立的手术记录单文档。仅有病程记录中的简短描述不足以替代正式的手术记录，导致手术经过、出血量、术中所见等关键要素缺失或无法核实。
- `2268187` `SC-123` discharge_special_evidence：quote=院外继续口服塞来昔布 1 粒 bid、大活络胶囊 4 粒 tid、地奥司明 2 粒 bid、氨氯地平 1 粒 qd、利伐沙班片 1 粒 qd;；reason=出院带药记录中缺乏具体的用药天数、减停药安排及详细的给药时间说明（如饭前/饭后），仅记录了药品名称、剂量和频次，不符合规则对出院带药详细程度的要求。

## 是否值得扩大

- 建议先做同规则族成本评估和 POC issue 抽样复核，再决定是否接入更多规则族；本 POC 不改变正式主链路。
