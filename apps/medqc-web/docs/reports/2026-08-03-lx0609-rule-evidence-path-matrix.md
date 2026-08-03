# LX0609 75条规则实际资料路径矩阵

日期：2026-08-03

## 审计范围

本报告只描述当前全量主线。权威调用链为：

`prepare_luxian_0609_execution → EvidenceReadSession → EvidenceSnapshot/MaterialStore → executor → RuleDecision`

审计同时核对了 Rule Contract、Dependency Inventory、Source Registry、Executor Registry，以及每个 executor 内实际调用 materials.rows()/bounded_rows() 的位置。Domain Bundle 不属于该权威链。

## 结论

- Rule Contract与Dependency Inventory均为75条，ID顺序完全一致（LX0609-001～075）。
- 当前75条全部为Native执行模式；全量主线会选择75条Typed Decision。
- 75条规则的声明资料和executor补充资料均能解析为已注册source key，没有未知资料来源。
- 当前全量Typed主线未发现由外部Scene/旧evidence_payload直接决定最终状态的规则。
- basic_timeliness、exam_lab、tumor_pathology、course_quality、surgery_gate、surgery_document、transfusion共7个executor仍接收兼容payload；其旧payload分支只在Typed关闭/回滚路径生效，后续必须用冲突输入测试逐族证明后才能删除。
- surgery_presence会使用由同一MaterialStore派生的内部payload，这不是Scene旧payload；LX0609-032另在MaterialStore上检查多台手术关联风险。
- consultation_quality、surgery_mdt、extended_document不读取外部兼容payload。
- Source Registry声明的是规则适用资料；Executor Registry会增加执行支持资料。两者并集才是EvidenceReadSession的实际预取范围。
- extended_document按executor预取较宽的支持资料，但最终规则读取集中在native_extended_document_execution.py:665-727；这是后续性能审计项，不是第二证据来源。

## 字段说明

- 资料声明：Source Registry解析出的物理source keys。
- Executor补充：Executor Registry因门控、关联或展示补充的source keys。CONS_SUPPORT和EXT_ALL在表后展开。
- 实际读取点：executor内MaterialStore读取位置；surgery_presence标记的是MaterialStore派生payload链。
- 旧payload影响：仅描述当前全量Typed主线，不代表回滚路径。
- 截断：R表示rows()受Snapshot完整性约束；B表示bounded_rows()同时依赖Snapshot完整性门。两者都不得用截断前缀证明“未发现”。

## 75条矩阵

|规则|Executor|资料声明|Executor补充|实际读取点|旧payload影响|截断|后续优先级|
|---|---|---|---|---|---|---|---|
|LX0609-001|basic_timeliness|admission_record|admission_record,inpat_registration|native_basic_timeliness.py:372,1128|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-002|basic_timeliness|daily_course_record,first_course_record,senior_course_record|admission_record,first_course_record,inpat_registration|native_basic_timeliness.py:372,1128|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-003|surgery_gate|surgery_record,mr_surgery|surgery_record|native_surgery_gate_execution.py:783,799,1073-1074,1163|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-004|basic_timeliness|rescue_record|rescue_record|native_basic_timeliness.py:372,1128|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-005|basic_timeliness|senior_course_record|admission_record,daily_course_record,inpat_registration,senior_course_record|native_basic_timeliness.py:372,1128|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-006|basic_timeliness|daily_course_record,senior_course_record|admission_record,daily_course_record,inpat_registration,senior_course_record|native_basic_timeliness.py:372,1128|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-007|course_quality|daily_course_record,senior_course_record|daily_course_record,senior_course_record|native_course_quality_execution.py:601,873,960,1092,1193,1298,1550-1606,2565,2777|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-008|course_quality|daily_course_record,exam_master,exam_item_report,labtest_master,labtest_item_report,senior_course_record|daily_course_record,inpat_nondrug_order.severity_order,senior_course_record|native_course_quality_execution.py:601,873,960,1092,1193,1298,1550-1606,2565,2777|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-009|course_quality|daily_course_record,exam_master,exam_item_report,labtest_master,labtest_item_report,senior_course_record|daily_course_record,inpat_nondrug_order.severity_order,senior_course_record|native_course_quality_execution.py:601,873,960,1092,1193,1298,1550-1606,2565,2777|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-010|exam_lab|daily_course_record,first_course_record,inpat_nondrug_order,inpat_drug_order,rescue_record,senior_course_record|—|native_exam_lab_execution.py:310|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-011|exam_lab|daily_course_record,first_course_record,rescue_record,senior_course_record|—|native_exam_lab_execution.py:310|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-012|exam_lab|daily_course_record,first_course_record,rescue_record,senior_course_record|—|native_exam_lab_execution.py:310|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-013|tumor_pathology|daily_course_record,surgery_record,mr_surgery|pathology_exam_master,pathology_exam_report|native_tumor_pathology_execution.py:320,374|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-014|exam_lab|daily_course_record,first_course_record,rescue_record,senior_course_record|—|native_exam_lab_execution.py:310|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-015|exam_lab|daily_course_record,first_course_record,labtest_item_report,rescue_record,senior_course_record|—|native_exam_lab_execution.py:310|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-016|course_quality|admission_record,first_course_record|daily_course_record,senior_course_record|native_course_quality_execution.py:601,873,960,1092,1193,1298,1550-1606,2565,2777|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-017|course_quality|daily_course_record,first_course_record,rescue_record,senior_course_record|daily_course_record,senior_course_record|native_course_quality_execution.py:601,873,960,1092,1193,1298,1550-1606,2565,2777|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-018|course_quality|admission_record|daily_course_record,senior_course_record|native_course_quality_execution.py:601,873,960,1092,1193,1298,1550-1606,2565,2777|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-019|tumor_pathology|daily_course_record,surgery_record,mr_surgery|pathology_exam_master,pathology_exam_report|native_tumor_pathology_execution.py:320,374|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-020|consultation_quality|consultation_record,daily_course_record|CONS_SUPPORT(7)|native_consultation_episode_execution.py:486,622,645；native_consultation_execution.py:2046,2356|不读取|B+Snapshot门|—|
|LX0609-021|consultation_quality|consultation_record|CONS_SUPPORT(7)|native_consultation_episode_execution.py:486,622,645；native_consultation_execution.py:2046,2356|不读取|B+Snapshot门|—|
|LX0609-022|consultation_quality|consultation_record|CONS_SUPPORT(7)|native_consultation_episode_execution.py:486,622,645；native_consultation_execution.py:2046,2356|不读取|B+Snapshot门|—|
|LX0609-023|consultation_quality|consultation_record,daily_course_record|CONS_SUPPORT(7)|native_consultation_episode_execution.py:486,622,645；native_consultation_execution.py:2046,2356|不读取|B+Snapshot门|—|
|LX0609-024|surgery_gate|surgery_record,mr_surgery|surgery_record|native_surgery_gate_execution.py:783,799,1073-1074,1163|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-025|surgery_gate|surgery_record,mr_surgery|surgery_record|native_surgery_gate_execution.py:783,799,1073-1074,1163|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-026|tumor_pathology|daily_course_record,inpat_nondrug_order,inpat_drug_order|daily_course_record,diagnosis,inpat_drug_order|native_tumor_pathology_execution.py:320,374|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-027|tumor_pathology|discharge_record|diagnosis,discharge_record|native_tumor_pathology_execution.py:320,374|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-028|surgery_gate|daily_course_record|surgery_record|native_surgery_gate_execution.py:783,799,1073-1074,1163|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-029|surgery_document|postsurg_firstcourse_record,presurg_discussion,presurg_summary,surgery_record,mr_surgery|—|native_surgery_document_execution.py:512,549,610-613,642,677,727,814,1341|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-030|surgery_presence|surgery_record,mr_surgery|inpat_nondrug_order,surgery_application|native_execution.py:297-320,382|内部MaterialStore派生；非旧payload|R+Snapshot门|—|
|LX0609-031|surgery_gate|postsurg_firstcourse_record,presurg_discussion,presurg_summary,surgery_record,mr_surgery|surgery_record|native_surgery_gate_execution.py:783,799,1073-1074,1163|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-032|surgery_presence|anesthesia_record,postsurg_firstcourse_record,presurg_discussion,presurg_summary,surgery_record,mr_surgery,surgery_risk_assessment,surgery_safecheck_record|inpat_nondrug_order,surgery_application|native_execution.py:297-320,382|内部MaterialStore派生；非旧payload|R+Snapshot门|—|
|LX0609-033|surgery_gate|anesthesia_record,consent_form,surgery_inform_consent,postsurg_firstcourse_record,presurg_discussion,presurg_summary,surgery_record,mr_surgery,surgery_risk_assessment,surgery_safecheck_record|surgery_record|native_surgery_gate_execution.py:783,799,1073-1074,1163|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-034|surgery_document|anesthesia_record,consent_form,surgery_inform_consent|—|native_surgery_document_execution.py:512,549,610-613,642,677,727,814,1341|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-035|surgery_document|anesthesia_record,consent_form,surgery_inform_consent|—|native_surgery_document_execution.py:512,549,610-613,642,677,727,814,1341|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-036|surgery_document|anesthesia_record|—|native_surgery_document_execution.py:512,549,610-613,642,677,727,814,1341|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-037|surgery_document|anesthesia_record,consent_form,surgery_inform_consent|—|native_surgery_document_execution.py:512,549,610-613,642,677,727,814,1341|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-038|surgery_document|consent_form,surgery_inform_consent|—|native_surgery_document_execution.py:512,549,610-613,642,677,727,814,1341|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-039|surgery_document|presurg_discussion|—|native_surgery_document_execution.py:512,549,610-613,642,677,727,814,1341|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-040|surgery_mdt|postsurg_firstcourse_record,presurg_discussion,presurg_summary,surgery_record,mr_surgery|consultation_record,mr_surgery,presurg_discussion|native_mdt_execution.py:616,674|不读取|R+Snapshot门|—|
|LX0609-041|transfusion|bloodtrans_record,mr_bloodtrans,consent_form,surgery_inform_consent|bloodtrans_record,mr_bloodtrans|native_transfusion_execution.py:478,484,509,567,1698|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-042|transfusion|consent_form,surgery_inform_consent|bloodtrans_record,mr_bloodtrans|native_transfusion_execution.py:478,484,509,567,1698|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-043|transfusion|daily_course_record,exam_item_report|bloodtrans_record,mr_bloodtrans|native_transfusion_execution.py:478,484,509,567,1698|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-044|transfusion|bloodtrans_record,mr_bloodtrans,daily_course_record|bloodtrans_record,mr_bloodtrans|native_transfusion_execution.py:478,484,509,567,1698|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-045|transfusion|bloodtrans_record,mr_bloodtrans,daily_course_record|bloodtrans_record,mr_bloodtrans|native_transfusion_execution.py:478,484,509,567,1698|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-046|transfusion|bloodtrans_record,mr_bloodtrans,daily_course_record|bloodtrans_record,mr_bloodtrans|native_transfusion_execution.py:478,484,509,567,1698|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-047|transfusion|bloodtrans_record,mr_bloodtrans,daily_course_record|bloodtrans_record,mr_bloodtrans|native_transfusion_execution.py:478,484,509,567,1698|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-048|transfusion|bloodtrans_record,mr_bloodtrans,daily_course_record,first_course_record,postsurg_firstcourse_record,presurg_discussion,presurg_summary,senior_course_record,surgery_record,mr_surgery|bloodtrans_record,mr_bloodtrans|native_transfusion_execution.py:478,484,509,567,1698|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-049|transfusion|daily_course_record,exam_item_report,inpat_nondrug_order,inpat_drug_order|bloodtrans_record,mr_bloodtrans|native_transfusion_execution.py:478,484,509,567,1698|全量Typed不影响；回滚路径读取|R+Snapshot门|P2冲突测试|
|LX0609-050|extended_document|daily_course_record,diffcase_discussion_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-051|extended_document|death_record,death_discussion|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-052|extended_document|labtest_item_report,crisis_value_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-053|extended_document|labtest_item_report,crisis_value_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-054|extended_document|inpat_drug_order,daily_course_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-055|extended_document|inpat_drug_order,daily_course_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-056|extended_document|inpat_drug_order,labtest_master|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-057|extended_document|inpat_drug_order,daily_course_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-058|extended_document|inpat_drug_order,consultation_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-059|extended_document|inpat_drug_order,daily_course_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-060|extended_document|death_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-061|extended_document|discharge_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-062|extended_document|discharge_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-063|extended_document|diagnosis,discharge_record_diagnosis|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-064|extended_document|surgery_record,mr_surgery,daily_course_record,senior_course_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-065|extended_document|surgery_record,mr_surgery,senior_course_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-066|extended_document|surgery_record,mr_surgery,postsurg_firstcourse_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-067|extended_document|discharge_record,daily_course_record,senior_course_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-068|extended_document|discharge_record,senior_course_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-069|extended_document|consultation_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-070|extended_document|bloodtrans_record,mr_bloodtrans,labtest_item_report|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-071|extended_document|handoff_record,handover_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-072|extended_document|transfer_in_record,transfer_out_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-073|extended_document|transfer_in_record,transfer_out_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-074|extended_document|daily_course_record,senior_course_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|
|LX0609-075|extended_document|inpat_nondrug_order,daily_course_record|EXT_ALL(25)|native_extended_document_execution.py:248；调用点665-727|不读取|R+Snapshot门|—|

## Executor补充资料别名

- CONS_SUPPORT(7)：consultation_record、daily_course_record、senior_course_record、surgery_record、exam_item_report、labtest_item_report、inpat_drug_order。
- EXT_ALL(25)：bloodtrans_record、consultation_record、crisis_value_record、daily_course_record、death_discussion、death_record、diagnosis、diffcase_discussion_record、discharge_record、discharge_record_diagnosis、handoff_record、handover_record、inpat_drug_order、inpat_nondrug_order、inpat_registration、labtest_item_report、labtest_master、mr_surgery、physician_change_event、postsurg_firstcourse_record、senior_course_record、surgery_record、transfer_in_record、transfer_out_record。

## 仍保留兼容payload的执行器

|Executor|兼容读取入口|当前全量Typed是否影响状态|建议|
|---|---|---|---|
|basic_timeliness|native_basic_timeliness.py:1146-1164|否|先做MaterialStore与payload冲突测试，再决定删除|
|course_quality|native_course_quality_execution.py:2750-2757|否|同上|
|exam_lab|native_exam_lab_execution.py:1177-1182|否|同上|
|tumor_pathology|native_tumor_pathology_execution.py:984-1000|否|同上|
|surgery_gate|native_surgery_gate_execution.py:2036-2069|否；仅legacy_selected|保留回滚能力至逐族验收|
|surgery_document|native_surgery_document_execution.py:1616-1620|否；仅legacy_selected|保留回滚能力至逐族验收|
|transfusion|native_transfusion_execution.py:1805,1844-1853|否；Typed改用MaterialStore documents|先做冲突测试|

## Task 2～3前的风险提示

- 本报告是静态主线审计，不替代真实病例trace。
- Typed开关关闭时，上述7族会重新进入兼容payload路径；因此现阶段不能直接删除函数参数。
- source keys已注册不代表源表一定有数据，也不代表事件关联已经成功。
- 截断reason code在不同executor中仍不完全统一，需在后续真实病例回归中逐条核对。
