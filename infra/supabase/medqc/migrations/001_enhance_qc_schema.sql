-- =============================================
-- 病历质控系统数据库Schema升级
-- 版本: 1.0.0
-- 描述: 增强质控规则表，添加RAG和缓存支持
-- =============================================

-- 启用pgvector扩展（用于向量检索）
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. 增强qc_rules表结构
ALTER TABLE qc_rules 
ADD COLUMN IF NOT EXISTS rule_code TEXT UNIQUE;

ALTER TABLE qc_rules 
ADD COLUMN IF NOT EXISTS rule_type TEXT CHECK (rule_type IN ('objective', 'subjective', 'hybrid')) DEFAULT 'subjective';

ALTER TABLE qc_rules 
ADD COLUMN IF NOT EXISTS severity TEXT CHECK (severity IN ('critical', 'major', 'minor')) DEFAULT 'minor';

ALTER TABLE qc_rules 
ADD COLUMN IF NOT EXISTS max_score INTEGER DEFAULT 0;

ALTER TABLE qc_rules 
ADD COLUMN IF NOT EXISTS check_logic JSONB DEFAULT '{}';

ALTER TABLE qc_rules 
ADD COLUMN IF NOT EXISTS version TEXT DEFAULT '1.0';

-- 为rule_code添加唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_qc_rules_rule_code ON qc_rules(rule_code) WHERE rule_code IS NOT NULL;

-- 2. 创建规则向量存储表（用于RAG）
CREATE TABLE IF NOT EXISTS qc_rules_embeddings (
  id UUID PRIMARY KEY REFERENCES qc_rules(id) ON DELETE CASCADE,
  rule_text TEXT NOT NULL,
  embedding VECTOR(1536), -- OpenAI/DeepSeek embedding维度
  category TEXT NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 为向量检索添加索引
CREATE INDEX IF NOT EXISTS idx_qc_rules_embeddings_category ON qc_rules_embeddings(category);

-- 3. 创建分析缓存表
CREATE TABLE IF NOT EXISTS qc_analysis_cache (
  content_hash TEXT PRIMARY KEY,
  segment_type TEXT NOT NULL, -- 'admission', 'progress', 'surgical', 'discharge' etc.
  analysis_result JSONB NOT NULL,
  rule_version TEXT NOT NULL,
  confidence_score DECIMAL CHECK (confidence_score >= 0 AND confidence_score <= 1),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  access_count INTEGER DEFAULT 0
);

-- 缓存表索引
CREATE INDEX IF NOT EXISTS idx_qc_cache_expires ON qc_analysis_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_qc_cache_segment_type ON qc_analysis_cache(segment_type);

-- 4. 创建分析历史表
CREATE TABLE IF NOT EXISTS qc_analysis_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL,
  analysis_result JSONB NOT NULL,
  changes_from_previous JSONB,
  analyst_type TEXT CHECK (analyst_type IN ('ai', 'human', 'hybrid')) DEFAULT 'ai',
  analysis_time_ms INTEGER, -- 分析耗时（毫秒）
  rule_version TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 历史表索引
CREATE INDEX IF NOT EXISTS idx_qc_history_record ON qc_analysis_history(record_id, version_number);
CREATE INDEX IF NOT EXISTS idx_qc_history_created ON qc_analysis_history(created_at DESC);

-- 5. 增强qc_results表
ALTER TABLE qc_results 
ADD COLUMN IF NOT EXISTS grade TEXT CHECK (grade IN ('A', 'B', 'C'));

ALTER TABLE qc_results 
ADD COLUMN IF NOT EXISTS category_scores JSONB DEFAULT '{}';

ALTER TABLE qc_results 
ADD COLUMN IF NOT EXISTS confidence_score DECIMAL CHECK (confidence_score >= 0 AND confidence_score <= 1);

ALTER TABLE qc_results 
ADD COLUMN IF NOT EXISTS rule_version TEXT DEFAULT '1.0';

-- 6. 创建性能优化索引
CREATE INDEX IF NOT EXISTS idx_qc_rules_active ON qc_rules(category, is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_qc_rules_type_severity ON qc_rules(rule_type, severity) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_medical_records_status ON medical_records(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qc_results_grade ON qc_results(grade, analysis_time DESC);

-- 7. 创建向量相似度匹配函数
CREATE OR REPLACE FUNCTION match_qc_rules(
  query_embedding VECTOR(1536),
  match_threshold FLOAT DEFAULT 0.7,
  match_count INT DEFAULT 5,
  filter_category TEXT DEFAULT NULL
)
RETURNS TABLE (
  rule_id UUID,
  rule_code TEXT,
  rule_name TEXT,
  rule_category TEXT,
  similarity FLOAT
)
LANGUAGE SQL STABLE
AS $$
  SELECT 
    qr.id,
    qr.rule_code,
    qr.name,
    qr.category,
    1 - (qre.embedding <=> query_embedding) as similarity
  FROM qc_rules_embeddings qre
  JOIN qc_rules qr ON qr.id = qre.id
  WHERE 
    qr.is_active = true
    AND 1 - (qre.embedding <=> query_embedding) > match_threshold
    AND (filter_category IS NULL OR qr.category = filter_category)
  ORDER BY qre.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- 8. 创建缓存清理函数
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS INTEGER
LANGUAGE SQL
AS $$
  DELETE FROM qc_analysis_cache 
  WHERE expires_at < NOW();
  
  SELECT ROW_COUNT();
$$;

-- 9. 创建分析统计视图
CREATE OR REPLACE VIEW qc_analysis_stats AS
SELECT 
  DATE(qr.analysis_time) as analysis_date,
  qr.grade,
  COUNT(*) as count,
  AVG(qr.score) as avg_score,
  AVG(qr.confidence_score) as avg_confidence,
  AVG(qah.analysis_time_ms) as avg_analysis_time_ms
FROM qc_results qr
LEFT JOIN qc_analysis_history qah ON qr.record_id = qah.record_id
WHERE qr.analysis_time >= NOW() - INTERVAL '30 days'
GROUP BY DATE(qr.analysis_time), qr.grade
ORDER BY analysis_date DESC, qr.grade;

-- 10. 创建规则使用统计视图  
CREATE OR REPLACE VIEW qc_rule_usage_stats AS
SELECT 
  qr.rule_code,
  qr.name as rule_name,
  qr.category,
  qr.severity,
  COUNT(CASE WHEN violations.value->>'ruleId' = qr.rule_code THEN 1 END) as violation_count,
  COUNT(qres.id) as total_analyses,
  ROUND(
    COUNT(CASE WHEN violations.value->>'ruleId' = qr.rule_code THEN 1 END)::DECIMAL / 
    NULLIF(COUNT(qres.id), 0) * 100, 2
  ) as violation_rate
FROM qc_rules qr
CROSS JOIN qc_results qres
CROSS JOIN LATERAL jsonb_array_elements(qres.issues) as violations
WHERE qres.analysis_time >= NOW() - INTERVAL '30 days'
GROUP BY qr.rule_code, qr.name, qr.category, qr.severity
ORDER BY violation_count DESC;

-- 11. 创建数据清理策略
-- 定期清理过期缓存（可以通过cron job调用）
CREATE OR REPLACE FUNCTION schedule_cache_cleanup()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  -- 清理7天前的缓存
  DELETE FROM qc_analysis_cache 
  WHERE created_at < NOW() - INTERVAL '7 days';
  
  -- 清理90天前的分析历史（保留最近版本）
  DELETE FROM qc_analysis_history 
  WHERE created_at < NOW() - INTERVAL '90 days'
  AND version_number < (
    SELECT MAX(version_number) 
    FROM qc_analysis_history qah2 
    WHERE qah2.record_id = qc_analysis_history.record_id
  );
  
  RAISE NOTICE 'Cache cleanup completed';
END;
$$;

-- 12. 添加触发器，自动更新embedding表的时间戳
CREATE OR REPLACE FUNCTION update_embedding_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trigger_update_embedding_timestamp
  BEFORE UPDATE ON qc_rules_embeddings
  FOR EACH ROW
  EXECUTE FUNCTION update_embedding_timestamp();

-- 13. 添加RLS（行级安全）策略
-- 为qc_rules表启用RLS
ALTER TABLE qc_rules ENABLE ROW LEVEL SECURITY;

-- 管理员可以管理所有规则
CREATE POLICY "管理员可以管理所有规则" ON qc_rules
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM user_roles 
      WHERE user_id = auth.uid() 
      AND role IN ('admin', 'qc_manager')
    )
  );

-- 普通用户只能查看激活的规则
CREATE POLICY "用户可以查看激活规则" ON qc_rules
  FOR SELECT USING (is_active = true);

-- 14. 创建种子数据函数（为测试提供基础数据）
CREATE OR REPLACE FUNCTION create_sample_medical_record()
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
  record_id UUID;
BEGIN
  INSERT INTO medical_records (
    patient_name, patient_id, department, content, status
  ) VALUES (
    '测试患者', 'TEST001', '内科', 
    '入院记录：患者因胸痛3小时入院。主诉：胸痛3小时。现病史：患者3小时前无明显诱因出现胸痛...',
    'pending'
  ) RETURNING id INTO record_id;
  
  RETURN record_id;
END;
$$;

-- 完成提示
DO $$
BEGIN
  RAISE NOTICE '==============================================';
  RAISE NOTICE '病历质控系统数据库Schema升级完成！';
  RAISE NOTICE '新增功能:';
  RAISE NOTICE '- 增强的质控规则表（支持分类、严重程度、评分）';
  RAISE NOTICE '- 向量检索支持（RAG）';
  RAISE NOTICE '- 分析结果缓存';
  RAISE NOTICE '- 分析历史追踪';
  RAISE NOTICE '- 性能优化索引';
  RAISE NOTICE '- 统计分析视图';
  RAISE NOTICE '==============================================';
END $$; 