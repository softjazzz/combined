-- 数据库表结构更新脚本
-- 为qc_results表添加缺失的字段

-- =====================================================
-- 更新qc_results表结构
-- =====================================================

-- 删除现有的qc_results表（因为我们需要重新创建结构）
DROP TABLE IF EXISTS qc_results CASCADE;

-- 重新创建qc_results表，包含所有必需字段
CREATE TABLE qc_results (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  medical_record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
  record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE, -- 兼容性字段
  analysis_result JSONB NOT NULL,
  overall_score INTEGER NOT NULL,
  completeness_score INTEGER,
  consistency_score INTEGER,
  rationality_score INTEGER,
  timeliness_score INTEGER,
  grade TEXT CHECK (grade IN ('A', 'B', 'C')),
  issues JSONB DEFAULT '[]'::jsonb,
  suggestions JSONB DEFAULT '[]'::jsonb,
  ai_model TEXT NOT NULL,
  analysis_time_ms INTEGER,
  confidence_score DECIMAL(5,2),
  rule_version TEXT,
  analysis_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 为qc_results表启用RLS并创建开发策略
ALTER TABLE qc_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anonymous access for development" ON qc_results
  FOR ALL USING (true) WITH CHECK (true);

-- 创建索引优化查询性能
CREATE INDEX idx_qc_results_medical_record_id ON qc_results(medical_record_id);
CREATE INDEX idx_qc_results_record_id ON qc_results(record_id);
CREATE INDEX idx_qc_results_overall_score ON qc_results(overall_score);
CREATE INDEX idx_qc_results_grade ON qc_results(grade);
CREATE INDEX idx_qc_results_ai_model ON qc_results(ai_model);
CREATE INDEX idx_qc_results_created_at ON qc_results(created_at);

-- =====================================================
-- 确认表结构
-- =====================================================

-- 显示qc_results表的列信息
SELECT 
  column_name, 
  data_type, 
  is_nullable, 
  column_default
FROM information_schema.columns 
WHERE table_name = 'qc_results' 
ORDER BY ordinal_position; 