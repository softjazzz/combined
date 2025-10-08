-- 质控规则文书类型映射修复SQL
-- 生成时间: 2025-09-16 20:40:32

UPDATE qc_rules SET 
    document_categories = ARRAY['admission_record','examination_report']::document_category_enum[],
    primary_document_category = 'admission_record'::document_category_enum
WHERE id = '2';  -- 现病史完整性检查

UPDATE qc_rules SET 
    document_categories = ARRAY['operation_record','examination_report']::document_category_enum[],
    primary_document_category = 'operation_record'::document_category_enum
WHERE id = '4';  -- 手术记录完整性检查

UPDATE qc_rules SET 
    document_categories = ARRAY['progress_note','examination_report']::document_category_enum[],
    primary_document_category = 'progress_note'::document_category_enum
WHERE id = '6';  -- 抢救记录详细性检查

UPDATE qc_rules SET 
    document_categories = ARRAY['operation_record']::document_category_enum[],
    primary_document_category = 'operation_record'::document_category_enum
WHERE id = '7';  -- 植入物信息完整性

UPDATE qc_rules SET 
    document_categories = ARRAY['consent_form']::document_category_enum[],
    primary_document_category = 'consent_form'::document_category_enum
WHERE id = '8';  -- 知情同意书签字完整性

UPDATE qc_rules SET 
    document_categories = ARRAY['admission_record']::document_category_enum[],
    primary_document_category = 'admission_record'::document_category_enum
WHERE id = '9';  -- 既往史记录完整性

UPDATE qc_rules SET 
    document_categories = ARRAY['admission_record','examination_report']::document_category_enum[],
    primary_document_category = 'admission_record'::document_category_enum
WHERE id = '10';  -- 体格检查详细性

UPDATE qc_rules SET 
    document_categories = ARRAY['progress_note']::document_category_enum[],
    primary_document_category = 'progress_note'::document_category_enum
WHERE id = '11';  -- 首次病程记录及时性

UPDATE qc_rules SET 
    document_categories = ARRAY['progress_note']::document_category_enum[],
    primary_document_category = 'progress_note'::document_category_enum
WHERE id = '12';  -- 上级医师查房记录

UPDATE qc_rules SET 
    document_categories = ARRAY['operation_record']::document_category_enum[],
    primary_document_category = 'operation_record'::document_category_enum
WHERE id = '13';  -- 术前讨论记录完整性

UPDATE qc_rules SET 
    document_categories = ARRAY['operation_record']::document_category_enum[],
    primary_document_category = 'operation_record'::document_category_enum
WHERE id = '14';  -- 麻醉记录规范性

UPDATE qc_rules SET 
    document_categories = ARRAY['discharge_record']::document_category_enum[],
    primary_document_category = 'discharge_record'::document_category_enum
WHERE id = '15';  -- 出院医嘱完整性

UPDATE qc_rules SET 
    document_categories = ARRAY['examination_report']::document_category_enum[],
    primary_document_category = 'examination_report'::document_category_enum
WHERE id = '16';  -- 检查报告及时性

UPDATE qc_rules SET 
    document_categories = ARRAY['examination_report']::document_category_enum[],
    primary_document_category = 'examination_report'::document_category_enum
WHERE id = '17';  -- 化验结果一致性

UPDATE qc_rules SET 
    document_categories = ARRAY['examination_report']::document_category_enum[],
    primary_document_category = 'examination_report'::document_category_enum
WHERE id = '18';  -- 影像检查完整性

UPDATE qc_rules SET 
    document_categories = ARRAY['consent_form']::document_category_enum[],
    primary_document_category = 'consent_form'::document_category_enum
WHERE id = '19';  -- 风险告知书签字

UPDATE qc_rules SET 
    document_categories = ARRAY['progress_note']::document_category_enum[],
    primary_document_category = 'progress_note'::document_category_enum
WHERE id = '20';  -- 会诊记录详细性
