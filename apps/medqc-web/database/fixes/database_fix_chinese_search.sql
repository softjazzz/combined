-- =============================================
-- 中文全文搜索修复脚本
-- 解决 "chinese" 配置不存在的问题
-- =============================================

-- 方案1: 检查并创建中文搜索配置（如果支持）
DO $$
BEGIN
    -- 检查是否存在中文配置
    IF NOT EXISTS (
        SELECT 1 FROM pg_ts_config WHERE cfgname = 'chinese'
    ) THEN
        -- 尝试创建简单的中文配置（基于 simple）
        BEGIN
            CREATE TEXT SEARCH CONFIGURATION chinese (COPY = simple);
            RAISE NOTICE '创建了中文搜索配置';
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE '无法创建中文搜索配置，将使用默认配置';
        END;
    ELSE
        RAISE NOTICE '中文搜索配置已存在';
    END IF;
END $$;

-- 方案2: 删除可能失败的索引，重新创建兼容版本
DROP INDEX IF EXISTS idx_medical_records_content_gin;
DROP INDEX IF EXISTS idx_medical_records_diagnosis_gin;

-- 创建兼容的全文搜索索引
DO $$
BEGIN
    -- 尝试使用中文配置
    IF EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'chinese') THEN
        CREATE INDEX idx_medical_records_content_gin ON medical_records USING gin(to_tsvector('chinese', content));
        CREATE INDEX idx_medical_records_diagnosis_gin ON medical_records USING gin(to_tsvector('chinese', diagnosis_primary));
        RAISE NOTICE '使用中文配置创建全文搜索索引';
    ELSE
        -- 使用默认配置
        CREATE INDEX idx_medical_records_content_gin ON medical_records USING gin(to_tsvector('simple', content));
        CREATE INDEX idx_medical_records_diagnosis_gin ON medical_records USING gin(to_tsvector('simple', diagnosis_primary));
        RAISE NOTICE '使用默认配置创建全文搜索索引';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE '全文搜索索引创建失败: %', SQLERRM;
END $$;

-- 方案3: 使用 pg_trgm 扩展进行模糊搜索（更适合中文）
-- 这种方式对中文搜索效果更好
CREATE INDEX IF NOT EXISTS idx_medical_records_content_trgm ON medical_records USING gin(content gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_medical_records_diagnosis_trgm ON medical_records USING gin(diagnosis_primary gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_medical_records_patient_name_trgm ON medical_records USING gin(patient_name gin_trgm_ops);

-- 创建搜索函数，支持中文模糊搜索
CREATE OR REPLACE FUNCTION search_medical_records(
    search_term TEXT,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    record_number VARCHAR(50),
    patient_name VARCHAR(100),
    diagnosis_primary TEXT,
    content_snippet TEXT,
    similarity_score REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        mr.id,
        mr.record_number,
        mr.patient_name,
        mr.diagnosis_primary,
        LEFT(mr.content, 200) || '...' as content_snippet,
        GREATEST(
            similarity(mr.content, search_term),
            similarity(mr.diagnosis_primary, search_term),
            similarity(mr.patient_name, search_term)
        ) as similarity_score
    FROM medical_records mr
    WHERE 
        mr.content % search_term 
        OR mr.diagnosis_primary % search_term 
        OR mr.patient_name % search_term
    ORDER BY similarity_score DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- 创建全文搜索函数（兼容版本）
CREATE OR REPLACE FUNCTION fulltext_search_medical_records(
    search_term TEXT,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    record_number VARCHAR(50),
    patient_name VARCHAR(100),
    diagnosis_primary TEXT,
    content_snippet TEXT,
    rank_score REAL
) AS $$
DECLARE
    ts_config TEXT;
BEGIN
    -- 动态选择搜索配置
    SELECT CASE 
        WHEN EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'chinese') 
        THEN 'chinese' 
        ELSE 'simple' 
    END INTO ts_config;
    
    RETURN QUERY EXECUTE format('
        SELECT 
            mr.id,
            mr.record_number,
            mr.patient_name,
            mr.diagnosis_primary,
            LEFT(mr.content, 200) || ''...'' as content_snippet,
            ts_rank(to_tsvector(%L, mr.content), plainto_tsquery(%L, %L)) as rank_score
        FROM medical_records mr
        WHERE 
            to_tsvector(%L, mr.content) @@ plainto_tsquery(%L, %L)
            OR to_tsvector(%L, mr.diagnosis_primary) @@ plainto_tsquery(%L, %L)
        ORDER BY rank_score DESC
        LIMIT %L
    ', ts_config, ts_config, search_term, ts_config, ts_config, search_term, ts_config, ts_config, search_term, limit_count);
END;
$$ LANGUAGE plpgsql;

-- 验证搜索功能
DO $$
BEGIN
    RAISE NOTICE '=== 搜索功能验证 ===';
    
    -- 检查 pg_trgm 扩展
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
        RAISE NOTICE '✅ pg_trgm 扩展已启用，支持模糊搜索';
    ELSE
        RAISE NOTICE '❌ pg_trgm 扩展未启用';
    END IF;
    
    -- 检查全文搜索配置
    IF EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'chinese') THEN
        RAISE NOTICE '✅ 中文全文搜索配置可用';
    ELSE
        RAISE NOTICE '⚠️  使用默认搜索配置（simple）';
    END IF;
    
    -- 检查索引
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_medical_records_content_trgm') THEN
        RAISE NOTICE '✅ 模糊搜索索引已创建';
    END IF;
    
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_medical_records_content_gin') THEN
        RAISE NOTICE '✅ 全文搜索索引已创建';
    END IF;
    
    RAISE NOTICE '=== 验证完成 ===';
END $$;

-- 使用示例注释
/*
-- 模糊搜索示例（推荐用于中文）
SELECT * FROM search_medical_records('心脏病', 5);

-- 全文搜索示例
SELECT * FROM fulltext_search_medical_records('心脏病 高血压', 5);

-- 直接使用 similarity 搜索
SELECT 
    patient_name, 
    diagnosis_primary,
    similarity(diagnosis_primary, '心脏病') as score
FROM medical_records 
WHERE diagnosis_primary % '心脏病'
ORDER BY score DESC
LIMIT 5;
*/
