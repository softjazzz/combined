# 正式质控结构化证据 84 条 POC-v4 优化报告

生成时间：2026-05-15 10:16:27

## POC 范围

- 只读运行，不接页面，不写正式质控业务表，不改 Sheet2 验收链路。
- scope=all84_v4；规则数=84；evidence package：`admission_course_evidence`、`diagnostic_followup_evidence`、`order_consultation_evidence`、`surgery_perioperative_evidence_v4`、`discharge_special_evidence`。
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

- baseline_total_tokens=608247；poc_total_tokens=432912；token_delta=175335。
- all84 scope 与正式 84 条 baseline 是同规则范围但不同执行策略；P0/v3 scope 与 84 条 baseline 不是同口径。
- baseline_wall_clock_time=320.585s；poc_wall_clock_time=1043.244s。
- baseline_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- baseline_target_rule_display_status_counts=`{"confirmed_defect": 14, "data_quality_gap": 85, "rejected_by_system": 44}`。
- poc_display_status_counts=`{"confirmed_defect": 36, "data_quality_gap": 129, "rejected_by_system": 675}`。

## 同规则族分布

- baseline 目标规则 issue 数：143。
- baseline 目标规则按 rule 分布：`{"SC-004": {"data_quality_gap": 1}, "SC-010": {"rejected_by_system": 4}, "SC-013": {"data_quality_gap": 1, "rejected_by_system": 3}, "SC-015": {"confirmed_defect": 2, "data_quality_gap": 1, "rejected_by_system": 1}, "SC-018": {"confirmed_defect": 1, "rejected_by_system": 1}, "SC-020": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-032": {"rejected_by_system": 1}, "SC-033": {"rejected_by_system": 1}, "SC-034": {"rejected_by_system": 1}, "SC-036": {"confirmed_defect": 1, "data_quality_gap": 4, "rejected_by_system": 2}, "SC-037": {"data_quality_gap": 1}, "SC-038": {"data_quality_gap": 8}, "SC-043": {"data_quality_gap": 2, "rejected_by_system": 1}, "SC-044": {"confirmed_defect": 1, "rejected_by_system": 2}, "SC-046": {"data_quality_gap": 5, "rejected_by_system": 2}, "SC-047": {"data_quality_gap": 1, "rejected_by_system": 1}, "SC-050": {"confirmed_defect": 2, "data_quality_gap": 2, "rejected_by_system": 1}, "SC-051": {"data_quality_gap": 3, "rejected_by_system": 1}, "SC-066": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-070": {"data_quality_gap": 1}, "SC-075": {"data_quality_gap": 4}, "SC-076": {"data_quality_gap": 1}, "SC-081": {"confirmed_defect": 1, "data_quality_gap": 1}, "SC-083": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-085": {"rejected_by_system": 1}, "SC-097": {"confirmed_defect": 3}, "SC-099": {"confirmed_defect": 1, "data_quality_gap": 1, "rejected_by_system": 3}, "SC-100": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-101": {"data_quality_gap": 1}, "SC-107": {"data_quality_gap": 2, "rejected_by_system": 1}, "SC-108": {"data_quality_gap": 5, "rejected_by_system": 1}, "SC-110": {"data_quality_gap": 1, "rejected_by_system": 2}, "SC-113": {"data_quality_gap": 2}, "SC-114": {"data_quality_gap": 2}, "SC-118": {"data_quality_gap": 5, "rejected_by_system": 2}, "SC-121": {"confirmed_defect": 1, "data_quality_gap": 1}, "SC-123": {"confirmed_defect": 1, "data_quality_gap": 2, "rejected_by_system": 1}, "SC-125": {"data_quality_gap": 6, "rejected_by_system": 2}, "SC-143": {"data_quality_gap": 9}, "SC-146": {"data_quality_gap": 8, "rejected_by_system": 1}}`。
- POC 同规则网格决策分布：`{"confirmed_defect": 36, "data_quality_gap": 129, "rejected_by_system": 675}`。

## POC 结论

- 本轮 v4 与正式 84 条 baseline 是同规则范围对比：调用数和 token 明显下降，但平均耗时仍高于 60s/病历目标，暂不建议替换正式主链路。

## v4 执行结构优化对比

- baseline_total_tokens=608247；all84_v3_total_tokens=962527；all84_v4_total_tokens=432912。
- baseline_wall_clock_time=320.585s；all84_v3_wall_clock_time=2037.538s；all84_v4_wall_clock_time=1043.244s。
- baseline_llm_calls=unknown；all84_v3_llm_calls=252；all84_v4_llm_calls=97。
- extractor_calls=50；adjudicator_calls=47；平均每病历调用数=9.7；平均每病历耗时=104.324s。
- token_vs_v3_change=-55.02%；wall_vs_v3_change=-48.8%。
- programmatic_rejected_count=604；programmatic_data_gap_count=0。
- skipped_adjudicator_rule_count=604；adjudicated_rule_count=765。
- input_document_chars=187487；compact_package_chars=121574。

## v4 目标达成情况

- <=12 LLM calls/病历：达成（当前 9.7）。
- token <= baseline 608247：达成（当前 432912）。
- 平均耗时 <=60s/病历：未达成（当前 104.324s）。
- 结论：v4 压缩了调用数，但仍需继续压缩 extractor 输入和二审策略；本轮仍不建议替换正式主链路。

## 84 条 inventory 摘要

- inventory_rule_count=84；evidence_family_count=5。
- structured_support_level=`{"partial": 53, "ready": 30, "unsupported": 1}`。
- 本轮不替换正式链路；下一步只建议挑选证据域做 feature flag 旁路验证。

## 分病历摘要

| visit_id | patient | wall(s) | extractor_calls | adjudicator_calls | tokens | confirmed | data_gap | rejected | parse_errors |
| -------- | ------- | ------: | --------------: | ----------------: | -----: | --------: | -------: | -------: | -----------: |
| 1915580  | 雷德超  |   97.67 |               5 |                 5 |  40684 |         5 |       11 |       68 |            0 |
| 2024757  | 游德利  |  109.65 |               5 |                 4 |  40525 |         0 |       14 |       70 |            0 |
| 2287309  | 陈光华  |   98.61 |               5 |                 5 |  43750 |         3 |       15 |       66 |            0 |
| 2246915  | 黄金莲  |  131.41 |               5 |                 5 |  51255 |         9 |        9 |       66 |            0 |
| 1883111  | 马章媛  |   81.02 |               5 |                 4 |  32925 |         1 |        9 |       74 |            0 |
| 1966656  | 周光容  |   95.40 |               5 |                 5 |  42688 |         2 |       14 |       68 |            0 |
| 2311318  | 范永勤  |  106.10 |               5 |                 5 |  47725 |         6 |       13 |       65 |            0 |
| 2207717  | 邹才林  |   80.91 |               5 |                 4 |  39483 |         1 |        8 |       75 |            0 |
| 1870471  | 蒲云鹏  |  142.10 |               5 |                 5 |  51470 |         4 |       15 |       65 |            0 |
| 2268187  | 代云聪  |  100.36 |               5 |                 5 |  42407 |         5 |       21 |       58 |            0 |

## confirmed_defect 明细

- `1915580` `SC-097` surgery_perioperative_evidence_v4：quote=手术开始时间：2025-08-12 14:15:00+08；reason=手术记录中缺失手术结束时间，导致手术经过描述不完整，不符合手术记录缺项或描述不清的缺陷标准。
- `1915580` `SC-103` surgery_perioperative_evidence_v4：quote=手术安全核查记录内容为空；reason=证据包明确指出手术安全核查记录内容为空，缺失三方签字及必要核查内容，违反手术安全核查规定。
- `1915580` `SC-099` surgery_perioperative_evidence_v4：quote=虽有骨髓瘤疑似诊断，但未发现明确的术中病理取材记录或病理报告单；reason=术前讨论提示骨髓瘤疑似诊断，但术中取材情况和病理结果未在手术记录中记录，且无病理报告支持，违反术中取材记录规定。
- `1915580` `SC-118` discharge_special_evidence：quote=患者因腰痛 2小时入院...病情好转平稳，予以出院。；reason=出院记录中缺失出院诊断字段，不符合出院记录完整性要求。
- `1915580` `SC-123` discharge_special_evidence：quote=继续口服双氯芬酸钠缓释片1粒qd、生血宝15mltid、云南白药胶囊2粒tid，仙灵骨葆胶囊3粒bid；；reason=出院带药记录中未明确用药天数（duration），不符合出院带药应记录具体使用方法、剂量、用药时间等详细程度的要求。
- `2287309` `SC-093` surgery_perioperative_evidence_v4：quote=anesthesia_record_missing；reason=证据包中coverage_flags明确标记'anesthesia_record_missing'，且missing_evidence指出'anesthesia_record_content'缺失，具体麻醉过程、用药及生命体征监测数据为空。规则要求核查手术患者是否有麻醉记录的存在性。
- `2287309` `SC-094` surgery_perioperative_evidence_v4：quote=anesthesia_record_missing；reason=由于麻醉记录整体缺失（见SC-093裁决），导致无法核查麻醉记录内容的完整性和清晰度，包括患者一般情况、麻醉诱导、术中用药等必要内容。
- `2287309` `SC-103` surgery_perioperative_evidence_v4：quote=safe_check_missing；reason=证据包中coverage_flags明确标记'safe_check_missing'，且missing_evidence指出'surgery_safe_check'缺失，手术安全核查记录表内容为空，缺失三方核查签字及时间点证据。
- `2246915` `SC-020` admission_course_evidence：quote=入院记录诊断表项为空，未在入院记录中明确列出入院诊断。；reason=入院记录中未明确列出入院诊断，诊断表项为空。
- `2246915` `SC-023` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-09 08:34:39 <empty>；reason=首次病程记录缺失。证据显示入院记录时间为2026-02-24，但首次病程记录表项为空或时间严重滞后（2026-03-09），不符合入院后8小时内完成且包含病例特点的要求。
- `2246915` `SC-024` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-09 08:34:39 <empty>；reason=首次病程记录缺失，导致无法归纳提炼病例特点。
- `2246915` `SC-025` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-09 08:34:39 <empty>；reason=首次病程记录缺失，导致无诊断依据、鉴别诊断及诊疗计划。
- `2246915` `SC-093` surgery_perioperative_evidence_v4：quote=输入材料中麻醉记录表为空，缺少详细的麻醉过程、生命体征监测数据及具体用药记录。；reason=数据质量标志明确指出'missing_anesthesia_record'，且缺失证据列表中说明'输入材料中麻醉记录表为空'，符合无麻醉记录的定义。
- `2246915` `SC-103` surgery_perioperative_evidence_v4：quote=输入材料中手术安全核查表为空，缺少三方核查签字及关键步骤确认信息。；reason=数据质量标志明确指出'missing_safety_check_record'，且缺失证据列表中说明'输入材料中手术安全核查表为空'，符合手术安全核查记录缺项的定义。
- `2246915` `SC-118` discharge_special_evidence：quote=患者因“发现阴道可复性肿物2+年”入院...于2026年02月27日 在全麻下行经阴道子宫切除术阴道前后壁修补术经阴道单侧输卵管卵巢切除术膀胱膨出修补术尿道折叠术,术后予以预防感染、对症治疗。；reason=出院记录中缺失出院诊断字段，且诊疗经过描述过于简略，未详细记录病情演变及重要辅助检查结果，不符合出院记录完整性要求。
- `2246915` `SC-123` discharge_special_evidence：quote=1.注意休息、营养; 2.禁性生活,剧烈运动三月,禁重体力劳动; 3.1月后；reason=出院记录中未记录具体的出院带药信息（包括药品名称、用药剂量、给药途径、用药时间等），仅包含生活指导，不符合出院带药记录详细程度的要求。
- `2246915` `SC-121` discharge_special_evidence：quote=患者因“发现阴道可复性肿物2+年”入院...于2026年02月27日 在全麻下行经阴道子宫切除术阴道前后壁修补术经阴道单侧输卵管卵巢切除术膀胱膨出修补术尿道折叠术,术后予以预防感染、对症治疗。；reason=诊疗经过记录不全面、不详细，仅简述手术名称及术后一般处理，缺乏与诊断相关的重要辅助检查结果及主要药品名称的详细记录。
- `1883111` `SC-123` discharge_special_evidence：quote=输入材料中仅包含住院期间临时医嘱（艾司奥美拉唑、氯化钠），未包含明确的出院带药清单（药名、剂量、频次、用法、天数）。出院记录及查房记录中仅提及“继续抗肿瘤治疗”，无具体药物明细。；reason=出院记录及查房记录中未包含具体的出院带药清单，缺乏药品名称、剂量、给药途径、用药时间等关键信息。仅提及“继续抗肿瘤治疗”而无具体药物明细，不符合出院带药记录详细程度的要求。
- `1966656` `SC-097` surgery_perioperative_evidence_v4：quote=手术记录中未填写手术结束时间；reason=证据包data_quality_flags包含missing_surgery_end_time，且missing_evidence中记录“手术记录中未填写手术结束时间”。手术记录缺项（缺少手术起止时间）属于描述不清/缺项。
- `1966656` `SC-103` surgery_perioperative_evidence_v4：quote=缺少手术安全核查记录文档；reason=证据包missing_evidence中明确记录“缺少手术安全核查记录文档”，违反必须存在手术安全核查记录的规定。
- `2311318` `SC-020` admission_course_evidence：quote=入院诊断: <empty>；reason=入院记录中缺少“入院诊断”字段，仅有初步诊断。根据规则要求，入院记录必须包含入院诊断，且主次顺序应有序排列。证据显示入院诊断slot状态为absent。
- `2311318` `SC-023` admission_course_evidence：quote=首次病程记录: <empty>；reason=首次病程记录缺失。规则要求首次病程记录需突出病例特点。证据显示首次病程记录slot状态为absent。
- `2311318` `SC-024` admission_course_evidence：quote=首次病程记录: <empty>；reason=首次病程记录缺失，导致无法归纳提炼病例特点。
- `2311318` `SC-025` admission_course_evidence：quote=首次病程记录: <empty>；reason=首次病程记录缺失，导致无诊断依据、鉴别诊断、诊疗计划。
- `2311318` `SC-026` admission_course_evidence：quote=首次病程记录: <empty>；reason=首次病程记录缺失，导致诊断依据或鉴别诊断不充分（因完全缺失）。
- `2311318` `SC-027` admission_course_evidence：quote=首次病程记录: <empty>；reason=首次病程记录缺失，导致诊疗计划不全面、不具体（因完全缺失）。
- `2207717` `SC-123` discharge_special_evidence：quote=神农镇痛膏 1贴 外用 bid*7天;；reason=出院带药记录不完整。虽然记录了药品名称（神农镇痛膏）、剂量（1贴）、用法（外用）和频次（bid），但缺少具体的用药时间说明（如早晚各一次的具体时间点或餐前餐后等明确指引，虽bid隐含每日两次，但规则要求具体用药时间/减停药安排）。更关键的是，规则要求“带药要记录使用方法、剂量、用药时间、减停药、随访时间等”，当前记录仅简略提及bid*7天，对于外用膏药的详细
- `1870471` `SC-081` surgery_perioperative_evidence_v4：quote=新建S章节:手术时间：2025年06月30日；麻醉方式：静吸复合全麻；手术方式：腹腔镜下阑尾切除术；reason=证据包明确指出术前小结表内容为空（missing_evidence），且data_quality_flags显示empty_required_form_preop_summary，导致术前小结缺项或描述不清。
- `1870471` `SC-093` surgery_perioperative_evidence_v4：quote=新建S章节:手术时间：2025年06月30日；麻醉方式：静吸复合全麻；手术方式：腹腔镜下阑尾切除术；reason=证据包明确指出麻醉记录单缺失，reason为麻醉记录表内容为空，且coverage_flags包含missing_anesthesia_record。
- `1870471` `SC-094` surgery_perioperative_evidence_v4：quote=新建S章节:手术时间：2025年06月30日；麻醉方式：静吸复合全麻；手术方式：腹腔镜下阑尾切除术；reason=由于麻醉记录缺失（见SC-093裁决），无法核查麻醉记录内容的完整性和清晰度，符合麻醉记录缺项或描述不清的定义。
- `1870471` `SC-103` surgery_perioperative_evidence_v4：quote=新建S章节:手术时间：2025年06月30日；麻醉方式：静吸复合全麻；手术方式：腹腔镜下阑尾切除术；reason=证据包明确指出手术安全核查记录缺失，reason为手术安全核查表内容为空，且coverage_flags包含missing_safety_check。
- `2268187` `SC-023` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录内容为空，缺失病例特点。
- `2268187` `SC-024` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录内容为空，未归纳提炼病例特点。
- `2268187` `SC-025` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录内容为空，缺失诊断依据、鉴别诊断及诊疗计划。
- `2268187` `SC-026` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录内容为空，诊断依据及鉴别诊断缺失。
- `2268187` `SC-027` admission_course_evidence：quote=[D5] source_table=first_course_record title=首次病程记录 time=2026-03-17 09:24:31 <empty>；reason=首次病程记录内容为空，诊疗计划缺失。

## 是否值得扩大

- 建议先做同规则族成本评估和 POC issue 抽样复核，再决定是否接入更多规则族；本 POC 不改变正式主链路。
