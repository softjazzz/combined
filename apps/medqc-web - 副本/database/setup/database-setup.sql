-- 病案质控系统数据库设置脚本
-- 请在Supabase控制台的SQL编辑器中执行此脚本

-- =====================================================
-- 1. 创建medical_records表
-- =====================================================

-- 删除现有表（如果存在）
DROP TABLE IF EXISTS medical_records CASCADE;

-- 创建medical_records表
CREATE TABLE medical_records (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  patient_name TEXT NOT NULL,
  patient_age INTEGER,
  patient_gender TEXT CHECK (patient_gender IN ('M', 'F', 'U')),
  department TEXT,
  admission_date DATE,
  record_type TEXT CHECK (record_type IN ('inpatient', 'outpatient', 'emergency')),
  content TEXT NOT NULL,
  file_url TEXT,
  file_name TEXT,
  file_size INTEGER,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'analyzing', 'completed', 'failed')),
  qc_score INTEGER,
  qc_grade TEXT CHECK (qc_grade IN ('A', 'B', 'C')),
  hospital_id UUID,
  doctor_id UUID,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_medical_records_status ON medical_records(status);
CREATE INDEX idx_medical_records_department ON medical_records(department);
CREATE INDEX idx_medical_records_created_at ON medical_records(created_at);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_medical_records_updated_at 
  BEFORE UPDATE ON medical_records 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 2. 创建qc_results表
-- =====================================================

CREATE TABLE IF NOT EXISTS qc_results (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  medical_record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
  overall_score INTEGER NOT NULL,
  completeness_score INTEGER,
  consistency_score INTEGER,
  rationality_score INTEGER,
  timeliness_score INTEGER,
  issues JSONB,
  suggestions JSONB,
  analysis_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 3. 创建qc_rules表
-- =====================================================

CREATE TABLE IF NOT EXISTS qc_rules (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL,
  weight DECIMAL(3,2) DEFAULT 1.0,
  is_active BOOLEAN DEFAULT true,
  prompt_template TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 4. 创建qc_analysis_cache表
-- =====================================================

CREATE TABLE IF NOT EXISTS qc_analysis_cache (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  content_hash TEXT UNIQUE NOT NULL,
  analysis_result JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  expires_at TIMESTAMP WITH TIME ZONE
);

-- =====================================================
-- 5. 创建qc_analysis_history表
-- =====================================================

CREATE TABLE IF NOT EXISTS qc_analysis_history (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  medical_record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
  analysis_result JSONB NOT NULL,
  analysis_version TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 6. 设置RLS策略（仅用于开发环境）
-- =====================================================

-- 为所有表启用RLS
ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_analysis_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_analysis_history ENABLE ROW LEVEL SECURITY;

-- 创建允许匿名用户操作的策略（仅用于开发环境）
CREATE POLICY "Allow anonymous access for development" ON medical_records
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow anonymous access for development" ON qc_results
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow anonymous access for development" ON qc_rules
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow anonymous access for development" ON qc_analysis_cache
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow anonymous access for development" ON qc_analysis_history
  FOR ALL USING (true) WITH CHECK (true);

-- =====================================================
-- 7. 插入初始质控规则数据
-- =====================================================

INSERT INTO qc_rules (name, description, category, weight, prompt_template) VALUES
('完整性检查', '检查病历记录的完整性', 'completeness', 1.0, '请检查病历记录是否包含所有必要的信息字段'),
('一致性检查', '检查病历记录内部信息的一致性', 'consistency', 1.0, '请检查病历记录中各项信息是否前后一致'),
('合理性检查', '检查诊断和治疗方案的合理性', 'rationality', 1.0, '请检查诊断是否合理，治疗方案是否恰当'),
('及时性检查', '检查病历记录的及时性', 'timeliness', 1.0, '请检查病历记录是否及时完成');

-- =====================================================
-- 完成信息
-- =====================================================

-- 显示创建的表
SELECT 
  schemaname, 
  tablename, 
  tableowner 
FROM pg_tables 
WHERE tablename IN ('medical_records', 'qc_results', 'qc_rules', 'qc_analysis_cache', 'qc_analysis_history'); 