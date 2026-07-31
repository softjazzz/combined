# 客户样本同步源表增量能力审计

> 本报告为只读结构审计结果，不会改变当前同步行为。字段存在不等于业务语义可靠，
> `updated_at` 策略仍须以客户源库更新行为验证为准。

## 审计范围

- 证据方式：customer_csv_headers
- 结构证据：客户导出 CDM CSV 表头（仅字段名）
- 已取得结构的表：54 张
- 同步契约表及显式缺口：62 张

## 策略汇总

- `updated_at`：54 张
- `append_only_record_time`：0 张
- `full_visit_reload`：8 张
- 第一阶段契约缺口：1 张

## 关键结论

- 不能把 `list_sync_tables()` 默认的 `date_field=update_time` 当作字段真实存在的证明。
- 仅有记录/报告时间不能证明表只增不改；未有显式受控声明时一律整病历重拉。
- 更新时间字段存在的表仍需验证：旧记录修改时该字段是否同步变化、是否单调且非空。
- 第一版不承诺识别源库物理删除；存在软删除字段时才可同步删除状态。
- `inpat_registration` 是第一阶段病历可见性的必需表，但当前未纳入 `list_sync_tables`；Task 3 必须正式补入同步表契约。

## 逐表结果

| 表名 | 契约状态 | 观测列数 | 主键/业务键 | 更新时间 | 记录时间 | 删除标记 | 推荐策略 | 风险与待确认 |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| admission_record | configured | 48 | patient_id, visit_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| admission_record_diagnosis | configured | 38 | patient_id, visit_id, diagnosis_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| anesthesia_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| blood_application | configured | 0 | patient_id, visit_id, application_id | — | — | — | full_visit_reload | 缺少可区分同一病历多行记录的稳定主键；未取得表结构，需补充源表字段清单；配置声明的时间字段不存在：update_time |
| bloodtrans_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| consultation_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| crisis_value_record | configured | 0 | patient_id, visit_id, document_id | — | — | — | full_visit_reload | 缺少可区分同一病历多行记录的稳定主键；未取得表结构，需补充源表字段清单；配置声明的时间字段不存在：update_time |
| daily_admission_record | configured | 31 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| daily_admission_record_diagnosis | configured | 38 | patient_id, visit_id, diagnosis_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| daily_course_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| daily_death_record | configured | 28 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| daily_death_record_diagnosis | configured | 38 | patient_id, visit_id, diagnosis_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| death_discussion | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| death_record | configured | 23 | patient_id, visit_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| diagnosis | configured | 24 | patient_id, visit_id, diagnosis_id | update_time | diagnosis_datetime | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| diffcase_discussion_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| discharge_record | configured | 38 | patient_id, visit_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| discharge_record_diagnosis | configured | 38 | patient_id, visit_id, diagnosis_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| docpat_commu_record | configured | 0 | patient_id, visit_id, document_id | — | — | — | full_visit_reload | 缺少可区分同一病历多行记录的稳定主键；未取得表结构，需补充源表字段清单；配置声明的时间字段不存在：update_time |
| exam_item_report | configured | 43 | patient_id, visit_id, exam_no, item_no | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| exam_master | configured | 49 | patient_id, visit_id, exam_no | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| first_course_record | configured | 41 | patient_id, visit_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| first_course_record_diagnosis | configured | 38 | patient_id, visit_id, diagnosis_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| handoff_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| handover_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| inpat_bill_item | configured | 0 | patient_id, visit_id, bill_item_id | — | — | — | full_visit_reload | 缺少可区分同一病历多行记录的稳定主键；未取得表结构，需补充源表字段清单；配置声明的时间字段不存在：update_time |
| inpat_drug_order | configured | 35 | patient_id, visit_id, order_id | update_time | prescribed_datetime | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| inpat_nondrug_order | configured | 28 | patient_id, visit_id, order_id | update_time | prescribed_datetime | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| inpat_prescription | configured | 55 | patient_id, visit_id, prescription_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| inpat_prescription_item | configured | 49 | patient_id, visit_id, prescription_id, item_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| inpat_registration | missing_from_sync_contract | 0 | patient_id, visit_id | — | — | — | full_visit_reload | 第一阶段必需表尚未纳入 list_sync_tables；需在 Task 3 正式加入同步表契约；缺少可区分同一病历多行记录的稳定主键；未取得表结构，需补充源表字段清单 |
| labtest_item_report | configured | 37 | patient_id, visit_id, test_no, item_no | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| labtest_master | configured | 25 | patient_id, visit_id, test_no | update_time | report_datetime | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| medical_insurance_settlement | configured | 0 | patient_id, visit_id | — | — | — | full_visit_reload | 缺少可区分同一病历多行记录的稳定主键；未取得表结构，需补充源表字段清单；配置声明的时间字段不存在：update_time |
| medical_insurance_settlement_cost | configured | 0 | patient_id, visit_id, medinsur_serial_item_id | — | — | — | full_visit_reload | 缺少可区分同一病历多行记录的稳定主键；未取得表结构，需补充源表字段清单；配置声明的时间字段不存在：update_time |
| mr | configured | 77 | patient_id, visit_id | update_time | — | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| mr_cost | configured | 37 | patient_id, visit_id | update_time | — | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| mr_diagnosis | configured | 38 | patient_id, visit_id, diagnosis_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| mr_surgery | configured | 30 | patient_id, visit_id | update_time | — | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| newborn_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| nursing_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| pathology_exam_master | configured | 21 | patient_id, visit_id, document_id | update_time | request_datetime | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| pathology_exam_report | configured | 20 | patient_id, visit_id, document_id | update_time | report_datetime | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| postane_surveil_record | configured | 0 | patient_id, visit_id, document_id | — | — | — | full_visit_reload | 缺少可区分同一病历多行记录的稳定主键；未取得表结构，需补充源表字段清单；配置声明的时间字段不存在：update_time |
| postsurg_firstcourse_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| preane_surveil_record | configured | 28 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| preane_surveil_record_diagnosis | configured | 38 | patient_id, visit_id, diagnosis_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| presurg_discussion | configured | 27 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| presurg_summary | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| rescue_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| senior_course_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| summary_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| surgery_application | configured | 26 | patient_id, visit_id, document_id | update_time | — | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| surgery_inform_consent | configured | 30 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| surgery_inventory_record | configured | 27 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| surgery_record | configured | 38 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| surgery_risk_assessment | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| surgery_safecheck_record | configured | 23 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| transfer_in_record | configured | 39 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| transfer_in_record_diagnosis | configured | 38 | patient_id, visit_id, diagnosis_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |
| transfer_out_record | configured | 38 | patient_id, visit_id, document_id | update_time | record_time | — | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新；未发现软删除标记，无法通过水位识别物理删除 |
| transfer_out_record_diagnosis | configured | 38 | patient_id, visit_id, diagnosis_id | update_time | record_time | is_deleted | updated_at | 需验证该更新时间字段在新增和每次修改时均可靠更新 |

## Task 2/3 前置确认

1. 对所有推荐 `updated_at` 的表，用一条旧记录修改实验验证水位字段确实变化。
2. 只有院方书面确认“只增不改”的表，才允许配置 `append_only_record_time`。
3. 明确各表软删除字段；无删除标记的表纳入出院收口全量核对。
4. Task 3 将 `inpat_registration` 纳入第一阶段同步契约，并补齐业务键。
