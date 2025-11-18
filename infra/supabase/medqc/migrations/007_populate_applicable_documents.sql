-- ============================================================================
-- Migration 007: 填充 applicable_documents 字段
-- ============================================================================
-- 
-- 目的：为现有的质控规则配置适用的文书类型
-- 
-- 背景：
-- Migration 006 添加了 applicable_documents 字段，但现有规则的该字段为空。
-- 本脚本根据规则名称和描述，智能配置每条规则适用的文书类型。
--
-- 执行方式：
-- 1. 在 Supabase Dashboard 的 SQL Editor 中执行
-- 2. 或使用 psql: psql $DATABASE_URL -f 007_populate_applicable_documents.sql
--
-- ============================================================================

-- 开始事务
BEGIN;

-- ============================================================================
-- 步骤 1: 配置入院记录相关规则
-- ============================================================================

UPDATE qc_rules 
SET applicable_documents = ARRAY['入院记录', '24小时入院记录']
WHERE (
    name LIKE '%入院%' 
    OR description LIKE '%入院%'
    OR name LIKE '%既往史%'
    OR name LIKE '%家族史%'
    OR name LIKE '%个人史%'
    OR name LIKE '%体格检查%'
    OR name LIKE '%初步诊断%'
)
AND (applicable_documents IS NULL OR array_length(applicable_documents, 1) IS NULL OR array_length(applicable_documents, 1) = 0);

-- ============================================================================
-- 步骤 2: 配置病程记录相关规则
-- ============================================================================

UPDATE qc_rules 
SET applicable_documents = ARRAY['病程记录', '首次病程记录', '日常病程记录', '上级医师查房记录', '疑难病例讨论记录', '交接班记录', '转科记录', '阶段小结']
WHERE (
    name LIKE '%病程%' 
    OR description LIKE '%病程%'
    OR name LIKE '%病情变化%'
    OR name LIKE '%诊疗措施%'
    OR name LIKE '%查房%'
)
AND (applicable_documents IS NULL OR array_length(applicable_documents, 1) IS NULL OR array_length(applicable_documents, 1) = 0);

-- ============================================================================
-- 步骤 3: 配置首次病程记录专用规则
-- ============================================================================

UPDATE qc_rules 
SET applicable_documents = ARRAY['首次病程记录']
WHERE (
    name LIKE '%首次%' 
    OR description LIKE '%首次%'
    OR name LIKE '%初步诊断%'
    OR name LIKE '%诊疗计划%'
)
AND (applicable_documents IS NULL OR array_length(applicable_documents, 1) IS NULL OR array_length(applicable_documents, 1) = 0);

-- ============================================================================
-- 步骤 4: 配置手术记录相关规则
-- ============================================================================

UPDATE qc_rules 
SET applicable_documents = ARRAY['手术记录', '术前小结', '术前讨论', '术后首次病程记录', '麻醉记录']
WHERE (
    name LIKE '%手术%' 
    OR description LIKE '%手术%'
    OR name LIKE '%术前%'
    OR name LIKE '%术后%'
    OR name LIKE '%麻醉%'
    OR name LIKE '%切口%'
    OR name LIKE '%植入%'
)
AND (applicable_documents IS NULL OR array_length(applicable_documents, 1) IS NULL OR array_length(applicable_documents, 1) = 0);

-- ============================================================================
-- 步骤 5: 配置出院记录相关规则
-- ============================================================================

UPDATE qc_rules 
SET applicable_documents = ARRAY['出院记录', '出院小结', '死亡记录', '死亡病例讨论记录']
WHERE (
    name LIKE '%出院%' 
    OR description LIKE '%出院%'
    OR name LIKE '%死亡%'
    OR name LIKE '%出入量%'
    OR name LIKE '%随访%'
)
AND (applicable_documents IS NULL OR array_length(applicable_documents, 1) IS NULL OR array_length(applicable_documents, 1) = 0);

-- ============================================================================
-- 步骤 6: 配置主诉和现病史相关规则（适用于入院记录和首次病程记录）
-- ============================================================================

UPDATE qc_rules 
SET applicable_documents = ARRAY['入院记录', '24小时入院记录', '首次病程记录']
WHERE (
    name LIKE '%主诉%' 
    OR description LIKE '%主诉%'
    OR name LIKE '%现病史%'
    OR description LIKE '%现病史%'
)
AND (applicable_documents IS NULL OR array_length(applicable_documents, 1) IS NULL OR array_length(applicable_documents, 1) = 0);

-- ============================================================================
-- 步骤 7: 配置诊断相关规则（适用于多种文书）
-- ============================================================================

UPDATE qc_rules 
SET applicable_documents = ARRAY['入院记录', '首次病程记录', '出院记录', '死亡记录']
WHERE (
    name LIKE '%诊断%' 
    OR description LIKE '%诊断%'
)
AND name NOT LIKE '%初步诊断%'  -- 排除初步诊断（已在入院记录中配置）
AND (applicable_documents IS NULL OR array_length(applicable_documents, 1) IS NULL OR array_length(applicable_documents, 1) = 0);

-- ============================================================================
-- 步骤 8: 配置通用规则（适用于所有文书类型）
-- ============================================================================

-- 以下规则保持为空数组，表示适用于所有文书类型：
-- - 格式规范性
-- - 时间记录
-- - 签名完整性
-- - 等等

UPDATE qc_rules 
SET applicable_documents = ARRAY[]::TEXT[]
WHERE (
    name LIKE '%格式%' 
    OR name LIKE '%规范%'
    OR name LIKE '%签名%'
    OR name LIKE '%时间%'
    OR name LIKE '%完整性%'
    OR category = 'compliance'
)
AND (applicable_documents IS NULL OR array_length(applicable_documents, 1) IS NULL OR array_length(applicable_documents, 1) = 0);

-- ============================================================================
-- 步骤 9: 显示配置结果统计
-- ============================================================================

DO $$
DECLARE
    total_rules INTEGER;
    configured_rules INTEGER;
    universal_rules INTEGER;
    unconfigured_rules INTEGER;
BEGIN
    -- 统计总规则数
    SELECT COUNT(*) INTO total_rules FROM qc_rules WHERE is_active = true;
    
    -- 统计已配置规则数（有具体文书类型）
    SELECT COUNT(*) INTO configured_rules 
    FROM qc_rules 
    WHERE is_active = true 
    AND applicable_documents IS NOT NULL 
    AND array_length(applicable_documents, 1) > 0;
    
    -- 统计通用规则数（空数组）
    SELECT COUNT(*) INTO universal_rules 
    FROM qc_rules 
    WHERE is_active = true 
    AND (
        applicable_documents IS NULL 
        OR array_length(applicable_documents, 1) IS NULL 
        OR array_length(applicable_documents, 1) = 0
    );
    
    -- 统计未配置规则数
    unconfigured_rules := total_rules - configured_rules - universal_rules;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '规则配置统计:';
    RAISE NOTICE '========================================';
    RAISE NOTICE '总规则数: %', total_rules;
    RAISE NOTICE '已配置规则数: % (%.1f%%)', configured_rules, (configured_rules::FLOAT / total_rules * 100);
    RAISE NOTICE '通用规则数: % (%.1f%%)', universal_rules, (universal_rules::FLOAT / total_rules * 100);
    RAISE NOTICE '未配置规则数: % (%.1f%%)', unconfigured_rules, (unconfigured_rules::FLOAT / total_rules * 100);
    RAISE NOTICE '========================================';
END $$;

-- ============================================================================
-- 步骤 10: 显示每种文书类型的规则数量
-- ============================================================================

SELECT 
    unnest(applicable_documents) AS document_type,
    COUNT(*) AS rule_count
FROM qc_rules
WHERE is_active = true
AND applicable_documents IS NOT NULL
AND array_length(applicable_documents, 1) > 0
GROUP BY document_type
ORDER BY rule_count DESC;

-- ============================================================================
-- 步骤 11: 显示未配置的规则（需要手动配置）
-- ============================================================================

SELECT 
    rule_code,
    name,
    category,
    description
FROM qc_rules
WHERE is_active = true
AND (
    applicable_documents IS NULL 
    OR array_length(applicable_documents, 1) IS NULL
)
ORDER BY category, name;

-- ============================================================================
-- 步骤 12: 显示完成信息
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '✅ Migration 007 completed successfully!';
    RAISE NOTICE 'Populated applicable_documents field for existing rules';
    RAISE NOTICE 'Please review the unconfigured rules and manually configure them if needed';
    RAISE NOTICE '========================================';
END $$;

-- 提交事务
COMMIT;

