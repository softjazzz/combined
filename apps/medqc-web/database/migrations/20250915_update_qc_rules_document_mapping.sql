-- =============================================
-- 更新现有质控规则的文书类别映射
-- 版本: 1.0.0
-- 日期: 2025-09-15
-- 描述: 根据规则名称和描述，智能映射到对应的文书类别
-- =============================================

-- 1. 入院记录相关规则
UPDATE qc_rules SET 
    document_categories = ARRAY['admission_record']::document_category_enum[],
    primary_document_category = 'admission_record'::document_category_enum,
    document_section_targets = ARRAY['主诉', '现病史', '既往史', '体格检查', '入院诊断']
WHERE 
    name ILIKE '%入院%' OR 
    name ILIKE '%主诉%' OR 
    name ILIKE '%现病史%' OR 
    name ILIKE '%既往史%' OR 
    name ILIKE '%体格检查%' OR 
    name ILIKE '%入院诊断%' OR
    description ILIKE '%入院记录%' OR
    description ILIKE '%主诉%';

-- 2. 病程记录相关规则
UPDATE qc_rules SET 
    document_categories = ARRAY['progress_note']::document_category_enum[],
    primary_document_category = 'progress_note'::document_category_enum,
    document_section_targets = ARRAY['病情变化', '治疗措施', '医嘱记录', '首次病程']
WHERE 
    name ILIKE '%病程%' OR 
    name ILIKE '%首次病程%' OR 
    name ILIKE '%日常病程%' OR 
    name ILIKE '%上级医师%' OR 
    name ILIKE '%查房%' OR
    name ILIKE '%交接班%' OR
    description ILIKE '%病程记录%' OR
    description ILIKE '%病情变化%';

-- 3. 出院记录相关规则
UPDATE qc_rules SET 
    document_categories = ARRAY['discharge_record']::document_category_enum[],
    primary_document_category = 'discharge_record'::document_category_enum,
    document_section_targets = ARRAY['入院情况', '诊疗经过', '出院诊断', '出院医嘱']
WHERE 
    name ILIKE '%出院%' OR 
    name ILIKE '%出院记录%' OR 
    name ILIKE '%出院诊断%' OR 
    name ILIKE '%出院医嘱%' OR
    name ILIKE '%诊疗经过%' OR
    description ILIKE '%出院记录%' OR
    description ILIKE '%出院诊断%';

-- 4. 手术相关记录规则
UPDATE qc_rules SET 
    document_categories = ARRAY['operation_record']::document_category_enum[],
    primary_document_category = 'operation_record'::document_category_enum,
    document_section_targets = ARRAY['手术指征', '手术过程', '术后处理', '麻醉记录']
WHERE 
    name ILIKE '%手术%' OR 
    name ILIKE '%术前%' OR 
    name ILIKE '%术后%' OR 
    name ILIKE '%麻醉%' OR 
    name ILIKE '%手术记录%' OR
    name ILIKE '%术前讨论%' OR
    description ILIKE '%手术%' OR
    description ILIKE '%麻醉%';

-- 5. 辅助检查相关规则
UPDATE qc_rules SET 
    document_categories = ARRAY['examination_report']::document_category_enum[],
    primary_document_category = 'examination_report'::document_category_enum,
    document_section_targets = ARRAY['检查项目', '检查结果', '诊断意见', '影像学']
WHERE 
    name ILIKE '%检查%' OR 
    name ILIKE '%化验%' OR 
    name ILIKE '%影像%' OR 
    name ILIKE '%病理%' OR 
    name ILIKE '%实验室%' OR
    name ILIKE '%CT%' OR
    name ILIKE '%MRI%' OR
    name ILIKE '%X线%' OR
    description ILIKE '%检查%' OR
    description ILIKE '%化验%';

-- 6. 知情同意书相关规则
UPDATE qc_rules SET 
    document_categories = ARRAY['consent_form']::document_category_enum[],
    primary_document_category = 'consent_form'::document_category_enum,
    document_section_targets = ARRAY['风险告知', '患者签字', '医师签字', '知情同意']
WHERE 
    name ILIKE '%知情同意%' OR 
    name ILIKE '%同意书%' OR 
    name ILIKE '%风险告知%' OR 
    name ILIKE '%签字%' OR
    name ILIKE '%授权%' OR
    description ILIKE '%知情同意%' OR
    description ILIKE '%同意书%';

-- 7. 通用规则（适用于多个文书类别）
UPDATE qc_rules SET 
    document_categories = ARRAY['admission_record', 'progress_note', 'discharge_record']::document_category_enum[],
    primary_document_category = 'progress_note'::document_category_enum,
    document_section_targets = ARRAY['诊断', '治疗', '医嘱']
WHERE 
    (name ILIKE '%诊断%' AND name NOT ILIKE '%入院诊断%' AND name NOT ILIKE '%出院诊断%') OR
    name ILIKE '%治疗%' OR 
    name ILIKE '%医嘱%' OR
    name ILIKE '%用药%' OR
    description ILIKE '%诊断依据%' OR
    description ILIKE '%治疗方案%';

-- 8. 完整性检查规则（适用于所有文书）
UPDATE qc_rules SET 
    document_categories = ARRAY['admission_record', 'progress_note', 'discharge_record', 'operation_record', 'examination_report', 'consent_form']::document_category_enum[],
    primary_document_category = 'admission_record'::document_category_enum,
    document_section_targets = ARRAY['基本信息', '完整性']
WHERE 
    name ILIKE '%完整性%' OR 
    name ILIKE '%缺失%' OR 
    name ILIKE '%空白%' OR
    name ILIKE '%必填%' OR
    description ILIKE '%完整性%' OR
    description ILIKE '%缺失%';

-- 9. 时效性检查规则（适用于多个文书）
UPDATE qc_rules SET 
    document_categories = ARRAY['admission_record', 'progress_note', 'operation_record']::document_category_enum[],
    primary_document_category = 'progress_note'::document_category_enum,
    document_section_targets = ARRAY['时间', '及时性']
WHERE 
    name ILIKE '%时间%' OR 
    name ILIKE '%及时%' OR 
    name ILIKE '%超时%' OR
    name ILIKE '%24小时%' OR
    name ILIKE '%8小时%' OR
    description ILIKE '%时间%' OR
    description ILIKE '%及时%';

-- 10. 为没有映射的规则设置默认值
UPDATE qc_rules SET 
    document_categories = ARRAY['progress_note']::document_category_enum[],
    primary_document_category = 'progress_note'::document_category_enum,
    document_section_targets = ARRAY['通用']
WHERE 
    document_categories IS NULL OR 
    array_length(document_categories, 1) IS NULL OR
    primary_document_category IS NULL;
