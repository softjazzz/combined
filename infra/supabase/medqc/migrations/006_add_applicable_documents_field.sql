-- 006_add_applicable_documents_field.sql
-- 添加 applicable_documents 字段以优化规则筛选性能
-- 
-- 背景：
-- 当前 applicable_documents 存储在 check_logic JSONB 字段中，导致：
-- 1. 查询性能差（需要 JSONB 查询或应用层筛选）
-- 2. 无法使用高效索引
-- 3. 查询语法复杂
-- 4. 数据一致性差
--
-- 改进：
-- 1. 添加独立的 applicable_documents TEXT[] 字段
-- 2. 从 check_logic JSONB 字段迁移数据
-- 3. 创建 GIN 索引以优化查询性能
-- 4. 支持数据库层面的高效筛选

-- ============================================================================
-- 步骤 1: 添加 applicable_documents 字段
-- ============================================================================

-- 添加字段（如果不存在）
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qc_rules' 
        AND column_name = 'applicable_documents'
    ) THEN
        ALTER TABLE qc_rules 
        ADD COLUMN applicable_documents TEXT[] DEFAULT '{}';
        
        RAISE NOTICE 'Added applicable_documents column to qc_rules table';
    ELSE
        RAISE NOTICE 'applicable_documents column already exists in qc_rules table';
    END IF;
END $$;

-- 添加列注释
COMMENT ON COLUMN qc_rules.applicable_documents IS '适用的病历单据类型列表。空数组表示适用于所有单据类型（通用规则）。';

-- ============================================================================
-- 步骤 2: 从 check_logic JSONB 字段迁移数据
-- ============================================================================

-- 迁移数据：从 check_logic->applicable_documents 复制到新字段
DO $$
DECLARE
    updated_count INTEGER := 0;
    rule_record RECORD;
    applicable_docs TEXT[];
BEGIN
    RAISE NOTICE 'Starting data migration from check_logic to applicable_documents...';
    
    -- 遍历所有规则
    FOR rule_record IN 
        SELECT id, rule_code, check_logic 
        FROM qc_rules 
        WHERE check_logic IS NOT NULL
    LOOP
        -- 尝试从 check_logic JSONB 中提取 applicable_documents
        BEGIN
            -- 检查 check_logic->applicable_documents 是否存在
            IF rule_record.check_logic ? 'applicable_documents' THEN
                -- 提取 applicable_documents 数组
                SELECT ARRAY(
                    SELECT jsonb_array_elements_text(rule_record.check_logic->'applicable_documents')
                ) INTO applicable_docs;
                
                -- 更新规则
                UPDATE qc_rules 
                SET applicable_documents = applicable_docs
                WHERE id = rule_record.id;
                
                updated_count := updated_count + 1;
                
                RAISE NOTICE 'Migrated rule %: % documents', 
                    rule_record.rule_code, 
                    array_length(applicable_docs, 1);
            END IF;
        EXCEPTION
            WHEN OTHERS THEN
                RAISE WARNING 'Failed to migrate rule %: %', 
                    rule_record.rule_code, 
                    SQLERRM;
        END;
    END LOOP;
    
    RAISE NOTICE 'Data migration completed. Updated % rules.', updated_count;
END $$;

-- ============================================================================
-- 步骤 3: 创建 GIN 索引以优化查询性能
-- ============================================================================

-- 创建 GIN 索引（如果不存在）
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'qc_rules' 
        AND indexname = 'idx_qc_rules_applicable_documents'
    ) THEN
        CREATE INDEX idx_qc_rules_applicable_documents 
        ON qc_rules USING GIN (applicable_documents);
        
        RAISE NOTICE 'Created GIN index on applicable_documents column';
    ELSE
        RAISE NOTICE 'GIN index on applicable_documents already exists';
    END IF;
END $$;

-- 添加索引注释
COMMENT ON INDEX idx_qc_rules_applicable_documents IS 'GIN 索引用于优化按病历单据类型筛选规则的查询性能';

-- ============================================================================
-- 步骤 4: 创建辅助函数和视图
-- ============================================================================

-- 创建函数：获取适用于指定文书类型的规则
CREATE OR REPLACE FUNCTION get_applicable_rules(
    p_document_type TEXT,
    p_is_active BOOLEAN DEFAULT true
)
RETURNS TABLE (
    id UUID,
    rule_code VARCHAR(50),
    name VARCHAR(200),
    description TEXT,
    category VARCHAR(50),
    rule_type VARCHAR(20),
    severity VARCHAR(20),
    prompt_template TEXT,
    check_logic JSONB,
    applicable_documents TEXT[],
    max_score INTEGER,
    weight DECIMAL(3,2),
    is_active BOOLEAN,
    version VARCHAR(10)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.id,
        r.rule_code,
        r.name,
        r.description,
        r.category,
        r.rule_type,
        r.severity,
        r.prompt_template,
        r.check_logic,
        r.applicable_documents,
        r.max_score,
        r.weight,
        r.is_active,
        r.version
    FROM qc_rules r
    WHERE 
        (p_is_active IS NULL OR r.is_active = p_is_active)
        AND (
            -- 通用规则（applicable_documents 为空）
            r.applicable_documents IS NULL 
            OR array_length(r.applicable_documents, 1) IS NULL
            OR array_length(r.applicable_documents, 1) = 0
            -- 或者包含指定的文书类型
            OR p_document_type = ANY(r.applicable_documents)
        )
    ORDER BY r.severity DESC, r.weight DESC, r.rule_code;
END;
$$ LANGUAGE plpgsql;

-- 添加函数注释
COMMENT ON FUNCTION get_applicable_rules(TEXT, BOOLEAN) IS '获取适用于指定文书类型的质控规则。如果规则的 applicable_documents 为空，则视为通用规则。';

-- 创建视图：规则统计
CREATE OR REPLACE VIEW qc_rules_statistics AS
SELECT 
    -- 总规则数
    COUNT(*) AS total_rules,
    COUNT(*) FILTER (WHERE is_active = true) AS active_rules,
    COUNT(*) FILTER (WHERE is_active = false) AS inactive_rules,
    
    -- 按类别统计
    COUNT(*) FILTER (WHERE category = 'completeness') AS completeness_rules,
    COUNT(*) FILTER (WHERE category = 'consistency') AS consistency_rules,
    COUNT(*) FILTER (WHERE category = 'rationality') AS rationality_rules,
    COUNT(*) FILTER (WHERE category = 'timeliness') AS timeliness_rules,
    COUNT(*) FILTER (WHERE category = 'compliance') AS compliance_rules,
    
    -- 按严重程度统计
    COUNT(*) FILTER (WHERE severity = 'critical') AS critical_rules,
    COUNT(*) FILTER (WHERE severity = 'major') AS major_rules,
    COUNT(*) FILTER (WHERE severity = 'minor') AS minor_rules,
    
    -- 按规则类型统计
    COUNT(*) FILTER (WHERE rule_type = 'objective') AS objective_rules,
    COUNT(*) FILTER (WHERE rule_type = 'subjective') AS subjective_rules,
    COUNT(*) FILTER (WHERE rule_type = 'hybrid') AS hybrid_rules,
    
    -- 通用规则和特定规则
    COUNT(*) FILTER (
        WHERE applicable_documents IS NULL 
        OR array_length(applicable_documents, 1) IS NULL
        OR array_length(applicable_documents, 1) = 0
    ) AS universal_rules,
    COUNT(*) FILTER (
        WHERE applicable_documents IS NOT NULL 
        AND array_length(applicable_documents, 1) > 0
    ) AS specific_rules
FROM qc_rules;

-- 添加视图注释
COMMENT ON VIEW qc_rules_statistics IS '质控规则统计视图，提供各维度的规则数量统计';

-- 创建视图：按文书类型统计规则数量
CREATE OR REPLACE VIEW qc_rules_by_document_type AS
SELECT 
    unnest(applicable_documents) AS document_type,
    COUNT(*) AS rule_count,
    COUNT(*) FILTER (WHERE is_active = true) AS active_rule_count,
    COUNT(*) FILTER (WHERE severity = 'critical') AS critical_rule_count,
    COUNT(*) FILTER (WHERE severity = 'major') AS major_rule_count,
    COUNT(*) FILTER (WHERE severity = 'minor') AS minor_rule_count,
    array_agg(rule_code ORDER BY severity DESC, weight DESC) AS rule_codes
FROM qc_rules
WHERE 
    applicable_documents IS NOT NULL 
    AND array_length(applicable_documents, 1) > 0
GROUP BY document_type
ORDER BY rule_count DESC;

-- 添加视图注释
COMMENT ON VIEW qc_rules_by_document_type IS '按病历单据类型统计规则数量，不包括通用规则';

-- ============================================================================
-- 步骤 5: 验证数据迁移
-- ============================================================================

-- 输出迁移统计信息
DO $$
DECLARE
    total_rules INTEGER;
    rules_with_docs INTEGER;
    universal_rules INTEGER;
BEGIN
    -- 统计总规则数
    SELECT COUNT(*) INTO total_rules FROM qc_rules;
    
    -- 统计有 applicable_documents 的规则数
    SELECT COUNT(*) INTO rules_with_docs 
    FROM qc_rules 
    WHERE applicable_documents IS NOT NULL 
    AND array_length(applicable_documents, 1) > 0;
    
    -- 统计通用规则数
    SELECT COUNT(*) INTO universal_rules 
    FROM qc_rules 
    WHERE applicable_documents IS NULL 
    OR array_length(applicable_documents, 1) IS NULL
    OR array_length(applicable_documents, 1) = 0;
    
    RAISE NOTICE '=== Migration Statistics ===';
    RAISE NOTICE 'Total rules: %', total_rules;
    RAISE NOTICE 'Rules with applicable_documents: %', rules_with_docs;
    RAISE NOTICE 'Universal rules: %', universal_rules;
    RAISE NOTICE '============================';
END $$;

-- ============================================================================
-- 步骤 6: 示例查询
-- ============================================================================

-- 示例 1: 查询适用于"首次病程记录"的所有激活规则
-- SELECT * FROM get_applicable_rules('首次病程记录', true);

-- 示例 2: 查询适用于"首次病程记录"的规则（使用数组操作符）
-- SELECT * FROM qc_rules 
-- WHERE is_active = true 
-- AND '首次病程记录' = ANY(applicable_documents);

-- 示例 3: 查询适用于多种文书类型的规则
-- SELECT * FROM qc_rules 
-- WHERE is_active = true 
-- AND applicable_documents && ARRAY['首次病程记录', '病程记录'];

-- 示例 4: 查询通用规则
-- SELECT * FROM qc_rules 
-- WHERE is_active = true 
-- AND (
--     applicable_documents IS NULL 
--     OR array_length(applicable_documents, 1) IS NULL
--     OR array_length(applicable_documents, 1) = 0
-- );

-- 示例 5: 统计每种文书类型的规则数量
-- SELECT * FROM qc_rules_by_document_type;

-- 示例 6: 查看规则统计
-- SELECT * FROM qc_rules_statistics;

-- ============================================================================
-- 完成
-- ============================================================================

RAISE NOTICE '✅ Migration 006 completed successfully!';
RAISE NOTICE 'Added applicable_documents TEXT[] field to qc_rules table';
RAISE NOTICE 'Created GIN index for optimized query performance';
RAISE NOTICE 'Created helper functions and views for rule management';

