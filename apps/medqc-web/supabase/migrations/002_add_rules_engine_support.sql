-- 002_add_rules_engine_support.sql
-- 添加规则引擎支持相关的表结构

-- 1. 质控规则配置表
CREATE TABLE IF NOT EXISTS qc_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL CHECK (category IN ('completeness', 'consistency', 'rationality', 'timeliness', 'similarity', 'compliance')),
    rule_type VARCHAR(20) NOT NULL CHECK (rule_type IN ('objective', 'subjective', 'hybrid')),
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'major', 'minor')),
    max_score INTEGER NOT NULL DEFAULT 100,
    weight DECIMAL(3,2) NOT NULL DEFAULT 1.0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    version VARCHAR(10) NOT NULL DEFAULT '1.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- 2. 质控规则执行历史表
CREATE TABLE IF NOT EXISTS qc_rule_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,
    rule_id UUID NOT NULL REFERENCES qc_rules(id) ON DELETE CASCADE,
    execution_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    passed BOOLEAN NOT NULL,
    score INTEGER NOT NULL,
    max_score INTEGER NOT NULL,
    deduction INTEGER NOT NULL DEFAULT 0,
    confidence DECIMAL(3,2) NOT NULL DEFAULT 0.0,
    execution_duration INTEGER NOT NULL DEFAULT 0, -- 执行时间（毫秒）
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. 质控问题详情表
CREATE TABLE IF NOT EXISTS qc_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES qc_rule_executions(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'major', 'minor')),
    location TEXT,
    suggestion TEXT,
    deduction INTEGER NOT NULL DEFAULT 0,
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. 增强质控结果表（扩展现有表）
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS rules_engine_score INTEGER;
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS ai_analysis_score INTEGER;
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS combined_score INTEGER;
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS processing_stats JSONB;
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS rules_engine_results JSONB;

-- 5. 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_qc_rules_category ON qc_rules(category);
CREATE INDEX IF NOT EXISTS idx_qc_rules_active ON qc_rules(is_active);
CREATE INDEX IF NOT EXISTS idx_qc_rule_executions_record ON qc_rule_executions(record_id);
CREATE INDEX IF NOT EXISTS idx_qc_rule_executions_rule ON qc_rule_executions(rule_id);
CREATE INDEX IF NOT EXISTS idx_qc_rule_executions_time ON qc_rule_executions(execution_time);
CREATE INDEX IF NOT EXISTS idx_qc_issues_execution ON qc_issues(execution_id);
CREATE INDEX IF NOT EXISTS idx_qc_issues_severity ON qc_issues(severity);

-- 6. 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_qc_rules_updated_at 
    BEFORE UPDATE ON qc_rules 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- 7. 插入默认规则配置
INSERT INTO qc_rules (rule_code, name, description, category, rule_type, severity, max_score, weight) VALUES
-- 完整性规则
('COMP_001', '基本信息完整性', '检查患者基本信息是否完整', 'completeness', 'objective', 'major', 100, 1.0),
('COMP_002', '诊断信息完整性', '检查诊断信息是否完整', 'completeness', 'objective', 'critical', 100, 1.5),
('COMP_003', '病程记录完整性', '检查病程记录是否完整', 'completeness', 'objective', 'major', 100, 1.2),

-- 一致性规则
('CONS_001', '诊断一致性', '检查入院诊断与出院诊断的一致性', 'consistency', 'hybrid', 'major', 100, 1.3),
('CONS_002', '时间逻辑一致性', '检查各时间节点的逻辑一致性', 'consistency', 'objective', 'major', 100, 1.0),
('CONS_003', '用药一致性', '检查用药与诊断的一致性', 'consistency', 'hybrid', 'major', 100, 1.2),

-- 合理性规则
('RATI_001', '诊断合理性', '检查诊断的合理性', 'rationality', 'subjective', 'major', 100, 1.4),
('RATI_002', '治疗合理性', '检查治疗方案的合理性', 'rationality', 'subjective', 'major', 100, 1.3),
('RATI_003', '药物剂量合理性', '检查药物剂量的合理性', 'rationality', 'hybrid', 'major', 100, 1.1),

-- 时效性规则
('TIME_001', '记录时效性', '检查病历记录的时效性', 'timeliness', 'objective', 'minor', 100, 0.8),
('TIME_002', '诊疗时效性', '检查诊疗活动的时效性', 'timeliness', 'objective', 'major', 100, 1.0),

-- 合规性规则
('COMP_001', '知情同意合规', '检查知情同意书的合规性', 'compliance', 'objective', 'critical', 100, 1.5),
('COMP_002', '医疗规范合规', '检查是否符合医疗规范', 'compliance', 'hybrid', 'major', 100, 1.2)

ON CONFLICT (rule_code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    category = EXCLUDED.category,
    rule_type = EXCLUDED.rule_type,
    severity = EXCLUDED.severity,
    max_score = EXCLUDED.max_score,
    weight = EXCLUDED.weight,
    updated_at = NOW();

-- 8. 创建RLS策略
ALTER TABLE qc_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_rule_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE qc_issues ENABLE ROW LEVEL SECURITY;

-- 质控规则访问策略
CREATE POLICY "Users can view qc_rules" ON qc_rules
    FOR SELECT USING (true);

CREATE POLICY "Admins can manage qc_rules" ON qc_rules
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.name IN ('admin', 'qc_manager')
        )
    );

-- 规则执行历史访问策略
CREATE POLICY "Users can view own hospital qc_rule_executions" ON qc_rule_executions
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM medical_records mr
            JOIN users u ON mr.hospital_id = u.hospital_id
            WHERE mr.id = qc_rule_executions.record_id
            AND u.id = auth.uid()
        )
    );

CREATE POLICY "QC staff can insert qc_rule_executions" ON qc_rule_executions
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.name IN ('admin', 'qc_manager', 'qc_staff')
        )
    );

-- 质控问题访问策略
CREATE POLICY "Users can view qc_issues through executions" ON qc_issues
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM qc_rule_executions qre
            JOIN medical_records mr ON qre.record_id = mr.id
            JOIN users u ON mr.hospital_id = u.hospital_id
            WHERE qre.id = qc_issues.execution_id
            AND u.id = auth.uid()
        )
    );

CREATE POLICY "QC staff can insert qc_issues" ON qc_issues
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.name IN ('admin', 'qc_manager', 'qc_staff')
        )
    );

-- 9. 创建视图便于查询
CREATE OR REPLACE VIEW qc_rule_execution_summary AS
SELECT 
    qre.id,
    qre.record_id,
    qr.rule_code,
    qr.name as rule_name,
    qr.category,
    qr.severity,
    qre.passed,
    qre.score,
    qre.max_score,
    qre.deduction,
    qre.confidence,
    qre.execution_time,
    qre.execution_duration,
    COUNT(qi.id) as issue_count
FROM qc_rule_executions qre
JOIN qc_rules qr ON qre.rule_id = qr.id
LEFT JOIN qc_issues qi ON qre.id = qi.execution_id
GROUP BY qre.id, qr.rule_code, qr.name, qr.category, qr.severity, qre.passed, qre.score, qre.max_score, qre.deduction, qre.confidence, qre.execution_time, qre.execution_duration;

-- 10. 创建统计函数
CREATE OR REPLACE FUNCTION get_qc_rule_statistics(
    p_hospital_id UUID DEFAULT NULL,
    p_start_date DATE DEFAULT NULL,
    p_end_date DATE DEFAULT NULL
)
RETURNS TABLE (
    category VARCHAR(50),
    total_executions BIGINT,
    passed_executions BIGINT,
    failed_executions BIGINT,
    pass_rate DECIMAL(5,2),
    avg_score DECIMAL(5,2),
    total_issues BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        qr.category,
        COUNT(qre.id) as total_executions,
        COUNT(qre.id) FILTER (WHERE qre.passed = true) as passed_executions,
        COUNT(qre.id) FILTER (WHERE qre.passed = false) as failed_executions,
        ROUND(
            (COUNT(qre.id) FILTER (WHERE qre.passed = true) * 100.0 / NULLIF(COUNT(qre.id), 0)), 
            2
        ) as pass_rate,
        ROUND(AVG(qre.score), 2) as avg_score,
        COUNT(qi.id) as total_issues
    FROM qc_rules qr
    LEFT JOIN qc_rule_executions qre ON qr.id = qre.rule_id
    LEFT JOIN medical_records mr ON qre.record_id = mr.id
    LEFT JOIN qc_issues qi ON qre.id = qi.execution_id
    WHERE (p_hospital_id IS NULL OR mr.hospital_id = p_hospital_id)
    AND (p_start_date IS NULL OR qre.execution_time::date >= p_start_date)
    AND (p_end_date IS NULL OR qre.execution_time::date <= p_end_date)
    GROUP BY qr.category
    ORDER BY qr.category;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON TABLE qc_rules IS '质控规则配置表';
COMMENT ON TABLE qc_rule_executions IS '质控规则执行历史表';
COMMENT ON TABLE qc_issues IS '质控问题详情表';
COMMENT ON FUNCTION get_qc_rule_statistics IS '获取质控规则统计信息'; 