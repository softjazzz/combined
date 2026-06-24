-- =============================================
-- 向量搜索设置脚本
-- 使用 Supabase 向量数据库实现中文语义搜索
-- =============================================

-- 确保 vector 扩展已启用
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================
-- 1. 向量搜索相关表
-- =============================================

-- 文档向量存储表
CREATE TABLE IF NOT EXISTS document_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,
    content_type VARCHAR(50) NOT NULL CHECK (content_type IN ('full_content', 'diagnosis', 'summary', 'section')),
    section_name VARCHAR(100), -- 如果是分段内容，记录段落名称
    content_text TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL, -- 内容哈希，用于去重
    embedding vector(1536), -- OpenAI text-embedding-ada-002 的维度
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 唯一约束：同一记录的同一类型内容只能有一个向量
    CONSTRAINT unique_record_content UNIQUE (record_id, content_type, content_hash)
);

-- 搜索历史表（用于优化和分析）
CREATE TABLE IF NOT EXISTS vector_search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_profiles(id),
    search_query TEXT NOT NULL,
    search_type VARCHAR(50) DEFAULT 'semantic' CHECK (search_type IN ('semantic', 'hybrid', 'similarity')),
    results_count INTEGER DEFAULT 0,
    search_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- 2. 向量搜索索引
-- =============================================

-- 创建向量相似度搜索索引（使用余弦相似度）
CREATE INDEX IF NOT EXISTS idx_document_embeddings_vector_cosine 
ON document_embeddings USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- 创建向量内积搜索索引
CREATE INDEX IF NOT EXISTS idx_document_embeddings_vector_ip 
ON document_embeddings USING ivfflat (embedding vector_ip_ops) 
WITH (lists = 100);

-- 其他索引
CREATE INDEX IF NOT EXISTS idx_document_embeddings_record_id ON document_embeddings(record_id);
CREATE INDEX IF NOT EXISTS idx_document_embeddings_content_type ON document_embeddings(content_type);
CREATE INDEX IF NOT EXISTS idx_document_embeddings_hash ON document_embeddings(content_hash);
CREATE INDEX IF NOT EXISTS idx_vector_search_history_user ON vector_search_history(user_id);
CREATE INDEX IF NOT EXISTS idx_vector_search_history_created ON vector_search_history(created_at);

-- =============================================
-- 3. 向量搜索函数
-- =============================================

-- 语义搜索函数（余弦相似度）
CREATE OR REPLACE FUNCTION semantic_search_medical_records(
    query_embedding vector(1536),
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10,
    content_types TEXT[] DEFAULT ARRAY['full_content', 'diagnosis', 'summary']
)
RETURNS TABLE (
    record_id UUID,
    record_number VARCHAR(50),
    patient_name VARCHAR(100),
    diagnosis_primary TEXT,
    content_snippet TEXT,
    similarity_score FLOAT,
    content_type VARCHAR(50),
    section_name VARCHAR(100)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        mr.id as record_id,
        mr.record_number,
        mr.patient_name,
        mr.diagnosis_primary,
        LEFT(de.content_text, 200) || '...' as content_snippet,
        1 - (de.embedding <=> query_embedding) as similarity_score,
        de.content_type,
        de.section_name
    FROM document_embeddings de
    JOIN medical_records mr ON de.record_id = mr.id
    WHERE 
        de.content_type = ANY(content_types)
        AND 1 - (de.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY de.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- 混合搜索函数（结合向量搜索和关键词搜索）
CREATE OR REPLACE FUNCTION hybrid_search_medical_records(
    query_embedding vector(1536),
    search_keywords TEXT,
    vector_weight FLOAT DEFAULT 0.7,
    keyword_weight FLOAT DEFAULT 0.3,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    record_id UUID,
    record_number VARCHAR(50),
    patient_name VARCHAR(100),
    diagnosis_primary TEXT,
    content_snippet TEXT,
    combined_score FLOAT,
    vector_score FLOAT,
    keyword_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH vector_results AS (
        SELECT 
            mr.id,
            mr.record_number,
            mr.patient_name,
            mr.diagnosis_primary,
            LEFT(de.content_text, 200) || '...' as content_snippet,
            1 - (de.embedding <=> query_embedding) as v_score
        FROM document_embeddings de
        JOIN medical_records mr ON de.record_id = mr.id
        WHERE de.content_type = 'full_content'
    ),
    keyword_results AS (
        SELECT 
            mr.id,
            GREATEST(
                similarity(mr.content, search_keywords),
                similarity(mr.diagnosis_primary, search_keywords),
                similarity(mr.patient_name, search_keywords)
            ) as k_score
        FROM medical_records mr
        WHERE 
            mr.content % search_keywords 
            OR mr.diagnosis_primary % search_keywords 
            OR mr.patient_name % search_keywords
    )
    SELECT 
        vr.id as record_id,
        vr.record_number,
        vr.patient_name,
        vr.diagnosis_primary,
        vr.content_snippet,
        (vr.v_score * vector_weight + COALESCE(kr.k_score, 0) * keyword_weight) as combined_score,
        vr.v_score as vector_score,
        COALESCE(kr.k_score, 0) as keyword_score
    FROM vector_results vr
    LEFT JOIN keyword_results kr ON vr.id = kr.id
    WHERE vr.v_score > 0.5 OR COALESCE(kr.k_score, 0) > 0.3
    ORDER BY combined_score DESC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- 相似病例推荐函数
CREATE OR REPLACE FUNCTION find_similar_cases(
    source_record_id UUID,
    similarity_threshold FLOAT DEFAULT 0.8,
    max_results INTEGER DEFAULT 5
)
RETURNS TABLE (
    record_id UUID,
    record_number VARCHAR(50),
    patient_name VARCHAR(100),
    diagnosis_primary TEXT,
    similarity_score FLOAT,
    common_keywords TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    WITH source_embedding AS (
        SELECT embedding 
        FROM document_embeddings 
        WHERE record_id = source_record_id 
        AND content_type = 'full_content'
        LIMIT 1
    )
    SELECT 
        mr.id as record_id,
        mr.record_number,
        mr.patient_name,
        mr.diagnosis_primary,
        1 - (de.embedding <=> se.embedding) as similarity_score,
        ARRAY[]::TEXT[] as common_keywords -- 可以后续扩展关键词提取
    FROM document_embeddings de
    JOIN medical_records mr ON de.record_id = mr.id
    CROSS JOIN source_embedding se
    WHERE 
        de.content_type = 'full_content'
        AND de.record_id != source_record_id
        AND 1 - (de.embedding <=> se.embedding) >= similarity_threshold
    ORDER BY de.embedding <=> se.embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- 4. 向量管理函数
-- =============================================

-- 批量插入向量数据函数
CREATE OR REPLACE FUNCTION upsert_document_embedding(
    p_record_id UUID,
    p_content_type VARCHAR(50),
    p_section_name VARCHAR(100),
    p_content_text TEXT,
    p_embedding vector(1536),
    p_token_count INTEGER DEFAULT 0
)
RETURNS UUID AS $$
DECLARE
    content_hash_val VARCHAR(64);
    embedding_id UUID;
BEGIN
    -- 计算内容哈希
    content_hash_val := encode(sha256(p_content_text::bytea), 'hex');
    
    -- 插入或更新向量数据
    INSERT INTO document_embeddings (
        record_id, content_type, section_name, content_text, 
        content_hash, embedding, token_count
    ) VALUES (
        p_record_id, p_content_type, p_section_name, p_content_text,
        content_hash_val, p_embedding, p_token_count
    )
    ON CONFLICT (record_id, content_type, content_hash) 
    DO UPDATE SET
        embedding = EXCLUDED.embedding,
        token_count = EXCLUDED.token_count,
        updated_at = NOW()
    RETURNING id INTO embedding_id;
    
    RETURN embedding_id;
END;
$$ LANGUAGE plpgsql;

-- 清理过期向量数据
CREATE OR REPLACE FUNCTION cleanup_orphaned_embeddings()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM document_embeddings 
    WHERE record_id NOT IN (SELECT id FROM medical_records);
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- 5. 搜索统计和分析
-- =============================================

-- 记录搜索历史
CREATE OR REPLACE FUNCTION log_vector_search(
    p_user_id UUID,
    p_search_query TEXT,
    p_search_type VARCHAR(50),
    p_results_count INTEGER,
    p_search_time_ms INTEGER
)
RETURNS UUID AS $$
DECLARE
    history_id UUID;
BEGIN
    INSERT INTO vector_search_history (
        user_id, search_query, search_type, results_count, search_time_ms
    ) VALUES (
        p_user_id, p_search_query, p_search_type, p_results_count, p_search_time_ms
    ) RETURNING id INTO history_id;
    
    RETURN history_id;
END;
$$ LANGUAGE plpgsql;

-- 获取搜索统计
CREATE OR REPLACE FUNCTION get_search_statistics(
    days_back INTEGER DEFAULT 30
)
RETURNS TABLE (
    total_searches BIGINT,
    unique_users BIGINT,
    avg_results_per_search NUMERIC,
    avg_search_time_ms NUMERIC,
    popular_queries TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    WITH stats AS (
        SELECT 
            COUNT(*) as total_searches,
            COUNT(DISTINCT user_id) as unique_users,
            AVG(results_count) as avg_results,
            AVG(search_time_ms) as avg_time
        FROM vector_search_history 
        WHERE created_at >= NOW() - INTERVAL '%s days' % days_back
    ),
    popular AS (
        SELECT ARRAY_AGG(search_query ORDER BY search_count DESC) as queries
        FROM (
            SELECT search_query, COUNT(*) as search_count
            FROM vector_search_history 
            WHERE created_at >= NOW() - INTERVAL '%s days' % days_back
            GROUP BY search_query
            ORDER BY search_count DESC
            LIMIT 10
        ) t
    )
    SELECT 
        s.total_searches,
        s.unique_users,
        s.avg_results,
        s.avg_time,
        p.queries
    FROM stats s, popular p;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- 6. 触发器和自动化
-- =============================================

-- 自动更新时间戳触发器
CREATE TRIGGER update_document_embeddings_updated_at 
    BEFORE UPDATE ON document_embeddings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 验证向量搜索设置
DO $$
BEGIN
    RAISE NOTICE '=== 向量搜索设置验证 ===';
    
    -- 检查 vector 扩展
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE '✅ vector 扩展已启用';
    ELSE
        RAISE NOTICE '❌ vector 扩展未启用';
    END IF;
    
    -- 检查表创建
    IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'document_embeddings') THEN
        RAISE NOTICE '✅ document_embeddings 表已创建';
    END IF;
    
    -- 检查索引
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_document_embeddings_vector_cosine') THEN
        RAISE NOTICE '✅ 向量索引已创建';
    END IF;
    
    -- 检查函数
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'semantic_search_medical_records') THEN
        RAISE NOTICE '✅ 语义搜索函数已创建';
    END IF;
    
    RAISE NOTICE '=== 设置完成 ===';
    RAISE NOTICE '提示：需要使用 OpenAI API 或其他嵌入服务生成向量数据';
END $$;
