-- ============================================================================
-- Migration 008: 统一 applicable_documents 字段为英文代码
-- ============================================================================
-- 
-- 目的：将 qc_rules.applicable_documents 字段中的中文名称统一转换为英文代码
-- 
-- 背景：
-- 当前 applicable_documents 字段存在中英文混用的问题：
-- - 英文代码：progress_note, admission_record, discharge_record 等
-- - 中文名称：病程记录, 入院记录, 出院记录 等
--
-- 解决方案：
-- 统一使用英文代码，提高数据一致性和查询性能
--
-- 执行方式：
-- 1. 在 Supabase Dashboard 的 SQL Editor 中执行
-- 2. 或使用 psql: psql $DATABASE_URL -f 008_standardize_applicable_documents.sql
--
-- ============================================================================

BEGIN;

-- ============================================================================
-- 步骤 1: 创建临时函数，将中文名称转换为英文代码
-- ============================================================================

CREATE OR REPLACE FUNCTION convert_document_name_to_code(doc_name TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN CASE
        -- 病程记录类
        WHEN doc_name IN ('病程记录', '病程') THEN 'progress_note'
        WHEN doc_name IN ('首次病程记录', '首次病程') THEN 'first_progress_note'
        WHEN doc_name IN ('日常病程记录', '日常病程') THEN 'daily_progress_note'
        WHEN doc_name IN ('上级医师查房记录', '查房记录', '上级医师首次查房记录', '首次查房') THEN 'attending_progress'
        WHEN doc_name IN ('会诊记录', '会诊') THEN 'consultation_record'
        WHEN doc_name IN ('交接班记录', '交班记录') THEN 'handover_record'
        WHEN doc_name IN ('阶段小结', '阶段性小结') THEN 'stage_summary'
        WHEN doc_name IN ('转科记录', '转科') THEN 'transfer_record'
        WHEN doc_name IN ('疑难病例讨论记录', '疑难病例讨论') THEN 'difficult_case_discussion'
        
        -- 入院记录类
        WHEN doc_name IN ('入院记录', '入院病历') THEN 'admission_record'
        WHEN doc_name IN ('24小时入院记录', '24h入院记录') THEN 'admission_record_24h_in'
        WHEN doc_name IN ('24小时入出院记录', '24h入出院记录') THEN 'admission_record_24h_out'
        
        -- 出院记录类
        WHEN doc_name IN ('出院记录', '出院病历') THEN 'discharge_record'
        WHEN doc_name IN ('出院小结', '出院总结') THEN 'discharge_summary'
        WHEN doc_name IN ('死亡记录', '死亡病历') THEN 'death_record'
        WHEN doc_name IN ('死亡病例讨论记录', '死亡讨论') THEN 'death_case_discussion'
        
        -- 手术记录类
        WHEN doc_name IN ('手术记录', '手术') THEN 'operation_record'
        WHEN doc_name IN ('术前小结', '术前总结') THEN 'preoperative_summary'
        WHEN doc_name IN ('术前讨论', '术前讨论记录') THEN 'preoperative_discussion'
        WHEN doc_name IN ('术后首次病程记录', '术后首程') THEN 'postoperative_first_progress'
        WHEN doc_name IN ('麻醉记录', '麻醉') THEN 'anesthesia_record'
        
        -- 检查报告类
        WHEN doc_name IN ('检查报告', '辅助检查') THEN 'examination_report'
        WHEN doc_name IN ('影像学报告', '影像报告') THEN 'imaging_report'
        WHEN doc_name IN ('实验室报告', '化验报告', '检验报告') THEN 'lab_report'
        WHEN doc_name IN ('病理报告', '病理') THEN 'pathology_report'
        
        -- 知情同意书类
        WHEN doc_name IN ('知情同意书', '同意书') THEN 'consent_form'
        WHEN doc_name IN ('手术知情同意书', '手术同意书') THEN 'surgery_consent'
        WHEN doc_name IN ('麻醉知情同意书', '麻醉同意书') THEN 'anesthesia_consent'
        WHEN doc_name IN ('输血知情同意书', '输血同意书') THEN 'blood_transfusion_consent'
        WHEN doc_name IN ('特殊治疗知情同意书', '特殊治疗同意书') THEN 'special_treatment_consent'
        WHEN doc_name IN ('病危通知书', '病重通知书') THEN 'critical_illness_notice'
        
        -- 其他
        WHEN doc_name IN ('医嘱记录', '医嘱') THEN 'medical_order'
        WHEN doc_name IN ('用药记录', '用药') THEN 'medication_record'
        WHEN doc_name IN ('护理记录', '护理') THEN 'nursing_record'
        
        -- 如果已经是英文代码，直接返回
        ELSE doc_name
    END;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================================
-- 步骤 2: 备份当前数据（可选，用于回滚）
-- ============================================================================

-- 创建备份表（如果不存在）
CREATE TABLE IF NOT EXISTS qc_rules_applicable_documents_backup (
    rule_id UUID,
    rule_code VARCHAR(20),
    old_applicable_documents TEXT[],
    backup_time TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 备份当前数据
INSERT INTO qc_rules_applicable_documents_backup (rule_id, rule_code, old_applicable_documents)
SELECT id, rule_code, applicable_documents
FROM qc_rules
WHERE applicable_documents IS NOT NULL
AND array_length(applicable_documents, 1) > 0;

-- ============================================================================
-- 步骤 3: 更新 qc_rules 表的 applicable_documents 字段
-- ============================================================================

DO $$
DECLARE
    rule_record RECORD;
    old_docs TEXT[];
    new_docs TEXT[];
    updated_count INTEGER := 0;
BEGIN
    RAISE NOTICE 'Starting conversion of applicable_documents from Chinese to English codes...';
    
    -- 遍历所有有 applicable_documents 的规则
    FOR rule_record IN 
        SELECT id, rule_code, applicable_documents 
        FROM qc_rules 
        WHERE applicable_documents IS NOT NULL
        AND array_length(applicable_documents, 1) > 0
    LOOP
        old_docs := rule_record.applicable_documents;
        
        -- 转换每个文书类型
        SELECT ARRAY(
            SELECT DISTINCT convert_document_name_to_code(unnest(old_docs))
        ) INTO new_docs;
        
        -- 更新规则
        UPDATE qc_rules 
        SET applicable_documents = new_docs
        WHERE id = rule_record.id;
        
        updated_count := updated_count + 1;
        
        -- 如果有变化，记录日志
        IF old_docs::TEXT != new_docs::TEXT THEN
            RAISE NOTICE 'Updated rule %: % -> %', 
                rule_record.rule_code, 
                old_docs, 
                new_docs;
        END IF;
    END LOOP;
    
    RAISE NOTICE 'Conversion completed. Updated % rules.', updated_count;
END $$;

-- ============================================================================
-- 步骤 4: 清理临时函数
-- ============================================================================

DROP FUNCTION convert_document_name_to_code(TEXT);

-- ============================================================================
-- 步骤 5: 显示迁移结果统计
-- ============================================================================

DO $$
DECLARE
    total_rules INTEGER;
    rules_with_docs INTEGER;
    unique_doc_types INTEGER;
BEGIN
    -- 统计总规则数
    SELECT COUNT(*) INTO total_rules FROM qc_rules WHERE is_active = true;
    
    -- 统计有 applicable_documents 的规则数
    SELECT COUNT(*) INTO rules_with_docs 
    FROM qc_rules 
    WHERE is_active = true 
    AND applicable_documents IS NOT NULL 
    AND array_length(applicable_documents, 1) > 0;
    
    -- 统计唯一文书类型数
    SELECT COUNT(DISTINCT unnest) INTO unique_doc_types
    FROM (
        SELECT unnest(applicable_documents) 
        FROM qc_rules 
        WHERE is_active = true
        AND applicable_documents IS NOT NULL
        AND array_length(applicable_documents, 1) > 0
    ) AS doc_types;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '迁移结果统计:';
    RAISE NOTICE '========================================';
    RAISE NOTICE '总规则数: %', total_rules;
    RAISE NOTICE '有文书类型配置的规则数: % (%.1f%%)', 
        rules_with_docs, 
        (rules_with_docs::FLOAT / total_rules * 100);
    RAISE NOTICE '唯一文书类型数: %', unique_doc_types;
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- 步骤 6: 显示每种文书类型的规则数量
-- ============================================================================

SELECT 
    unnest(applicable_documents) AS document_type_code,
    COUNT(*) AS rule_count
FROM qc_rules
WHERE is_active = true
AND applicable_documents IS NOT NULL
AND array_length(applicable_documents, 1) > 0
GROUP BY document_type_code
ORDER BY rule_count DESC;

-- ============================================================================
-- 步骤 7: 验证数据（检查是否还有中文名称）
-- ============================================================================

DO $$
DECLARE
    chinese_count INTEGER;
    rule_record RECORD;
BEGIN
    -- 检查是否还有中文字符
    SELECT COUNT(*) INTO chinese_count
    FROM qc_rules
    WHERE is_active = true
    AND applicable_documents IS NOT NULL
    AND array_length(applicable_documents, 1) > 0
    AND EXISTS (
        SELECT 1
        FROM unnest(applicable_documents) AS doc
        WHERE doc ~ '[\u4e00-\u9fa5]'  -- 匹配中文字符
    );

    IF chinese_count > 0 THEN
        RAISE WARNING '警告: 仍有 % 条规则包含中文文书类型名称，请检查！', chinese_count;

        -- 显示这些规则
        RAISE NOTICE '包含中文的规则:';
        FOR rule_record IN
            SELECT rule_code, applicable_documents
            FROM qc_rules
            WHERE is_active = true
            AND applicable_documents IS NOT NULL
            AND array_length(applicable_documents, 1) > 0
            AND EXISTS (
                SELECT 1
                FROM unnest(applicable_documents) AS doc
                WHERE doc ~ '[\u4e00-\u9fa5]'
            )
            LIMIT 10
        LOOP
            RAISE NOTICE '  规则 %: %', rule_record.rule_code, rule_record.applicable_documents;
        END LOOP;
    ELSE
        RAISE NOTICE '✅ 验证通过: 所有文书类型已转换为英文代码';
    END IF;
END $$;

-- ============================================================================
-- 步骤 8: 显示完成信息
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Migration 008 completed successfully!';
    RAISE NOTICE 'Standardized applicable_documents field to use English codes';
    RAISE NOTICE 'Backup saved in qc_rules_applicable_documents_backup table';
    RAISE NOTICE '========================================';
END $$;

COMMIT;

-- ============================================================================
-- 回滚脚本（如果需要）
-- ============================================================================

-- 如果需要回滚，执行以下脚本：
/*
BEGIN;

UPDATE qc_rules r
SET applicable_documents = b.old_applicable_documents
FROM qc_rules_applicable_documents_backup b
WHERE r.id = b.rule_id;

RAISE NOTICE '✅ Rollback completed successfully!';

COMMIT;
*/

