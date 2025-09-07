-- =============================================
-- 病历质控系统基础Schema初始化
-- 版本: 0.1.0
-- 描述: 创建基础表结构
-- =============================================

-- 1. 创建医疗记录表
CREATE TABLE IF NOT EXISTS medical_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_name TEXT NOT NULL,
  patient_id TEXT,
  department TEXT,
  content TEXT NOT NULL,
  status TEXT CHECK (status IN ('pending', 'analyzing', 'completed', 'failed')) DEFAULT 'pending',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 创建质控规则表
CREATE TABLE IF NOT EXISTS qc_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL,
  prompt_template TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. 创建质控结果表
CREATE TABLE IF NOT EXISTS qc_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,
  score INTEGER CHECK (score >= 0 AND score <= 100),
  issues JSONB DEFAULT '[]',
  suggestions TEXT,
  analysis_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. 创建用户角色表（用于权限管理）
CREATE TABLE IF NOT EXISTS user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'qc_manager', 'qc_staff', 'doctor')),
  hospital_id TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, role)
);

-- 5. 创建基础索引
CREATE INDEX IF NOT EXISTS idx_medical_records_status ON medical_records(status);
CREATE INDEX IF NOT EXISTS idx_medical_records_created ON medical_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qc_rules_category ON qc_rules(category);
CREATE INDEX IF NOT EXISTS idx_qc_rules_active ON qc_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_qc_results_record ON qc_results(record_id);
CREATE INDEX IF NOT EXISTS idx_qc_results_analysis_time ON qc_results(analysis_time DESC);
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);

-- 6. 创建更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- 7. 添加更新时间触发器
CREATE TRIGGER update_medical_records_updated_at 
  BEFORE UPDATE ON medical_records 
  FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_qc_rules_updated_at 
  BEFORE UPDATE ON qc_rules 
  FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- 8. 启用行级安全策略
ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;

-- 9. 创建基础RLS策略
-- 允许认证用户查看医疗记录
CREATE POLICY "认证用户可以查看医疗记录" ON medical_records
  FOR SELECT USING (auth.role() = 'authenticated');

-- 允许认证用户查看质控规则
CREATE POLICY "认证用户可以查看质控规则" ON qc_rules
  FOR SELECT USING (auth.role() = 'authenticated');

-- 允许认证用户查看质控结果
CREATE POLICY "认证用户可以查看质控结果" ON qc_results
  FOR SELECT USING (auth.role() = 'authenticated');

-- 完成提示
DO $$
BEGIN
  RAISE NOTICE '==============================================';
  RAISE NOTICE '病历质控系统基础Schema初始化完成！';
  RAISE NOTICE '已创建表:';
  RAISE NOTICE '- medical_records (医疗记录)';
  RAISE NOTICE '- qc_rules (质控规则)';
  RAISE NOTICE '- qc_results (质控结果)';
  RAISE NOTICE '- user_roles (用户角色)';
  RAISE NOTICE '==============================================';
END $$; 