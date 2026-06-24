-- =============================================
-- 医疗质控系统数据库初始化脚本 - 第二部分
-- 版本: 2.0.0 (全新设计)
-- 创建时间: 2024-12-25
-- 新 Supabase 项目: https://dgsdkdbjpucyawnyfbdu.supabase.co
-- =============================================

-- =============================================
-- 第五步：统计分析相关表
-- =============================================

-- 10. 分析指标表
CREATE TABLE analytics_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(50) NOT NULL
        CHECK (metric_type IN ('count', 'percentage', 'average', 'sum', 'ratio', 'rate', 'trend')),
    category VARCHAR(50) NOT NULL
        CHECK (category IN ('quality', 'performance', 'usage', 'cost', 'compliance', 'timeliness', 'accuracy', 'efficiency', 'productivity', 'volume')),
    description TEXT,
    calculation_formula TEXT,
    unit VARCHAR(20),
    target_value DECIMAL(10,2),
    warning_threshold DECIMAL(10,2),
    critical_threshold DECIMAL(10,2),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 11. 报告模板表
CREATE TABLE report_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_name VARCHAR(200) NOT NULL,
    template_type VARCHAR(50) NOT NULL
        CHECK (template_type IN ('daily', 'weekly', 'monthly', 'quarterly', 'annual', 'custom')),
    description TEXT,
    template_config JSONB NOT NULL DEFAULT '{}',
    chart_configs JSONB DEFAULT '[]',
    filter_options JSONB DEFAULT '{}',
    export_formats TEXT[] DEFAULT ARRAY['pdf', 'excel'],
    is_public BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_by UUID NOT NULL REFERENCES user_profiles(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 12. 数据快照表
CREATE TABLE data_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL,
    snapshot_type VARCHAR(50) NOT NULL
        CHECK (snapshot_type IN ('daily', 'weekly', 'monthly')),
    department_id UUID REFERENCES departments(id),
    metrics_data JSONB NOT NULL DEFAULT '{}',
    summary_stats JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_snapshot UNIQUE (snapshot_date, snapshot_type, department_id)
);

-- =============================================
-- 第六步：创建索引优化
-- =============================================

-- 用户档案表索引
CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_user_profiles_department ON user_profiles(department_id);
CREATE INDEX idx_user_profiles_role ON user_profiles(role_type);
CREATE INDEX idx_user_profiles_active ON user_profiles(is_active);

-- 科室表索引
CREATE INDEX idx_departments_code ON departments(code);
CREATE INDEX idx_departments_category ON departments(category);
CREATE INDEX idx_departments_active ON departments(is_active);

-- 医疗记录表索引
CREATE INDEX idx_medical_records_number ON medical_records(record_number);
CREATE INDEX idx_medical_records_patient ON medical_records(patient_id);
CREATE INDEX idx_medical_records_department ON medical_records(department_id);
CREATE INDEX idx_medical_records_doctor ON medical_records(doctor_id);
CREATE INDEX idx_medical_records_status ON medical_records(status);
CREATE INDEX idx_medical_records_type ON medical_records(record_type);
CREATE INDEX idx_medical_records_dates ON medical_records(admission_date, discharge_date);
CREATE INDEX idx_medical_records_created ON medical_records(created_at);
CREATE INDEX idx_medical_records_qc_grade ON medical_records(qc_grade);

-- 全文搜索索引（使用默认配置，兼容性更好）
CREATE INDEX idx_medical_records_content_gin ON medical_records USING gin(to_tsvector('simple', content));
CREATE INDEX idx_medical_records_diagnosis_gin ON medical_records USING gin(to_tsvector('simple', diagnosis_primary));

-- 如果需要中文分词，可以使用以下替代方案：
-- 1. 使用 pg_trgm 扩展进行模糊匹配
CREATE INDEX idx_medical_records_content_trgm ON medical_records USING gin(content gin_trgm_ops);
CREATE INDEX idx_medical_records_diagnosis_trgm ON medical_records USING gin(diagnosis_primary gin_trgm_ops);

-- 质控规则表索引
CREATE INDEX idx_qc_rules_code ON qc_rules(rule_code);
CREATE INDEX idx_qc_rules_category ON qc_rules(category);
CREATE INDEX idx_qc_rules_type ON qc_rules(rule_type);
CREATE INDEX idx_qc_rules_severity ON qc_rules(severity);
CREATE INDEX idx_qc_rules_active ON qc_rules(is_active);
CREATE INDEX idx_qc_rules_departments ON qc_rules USING gin(applicable_departments);

-- 质控结果表索引
CREATE INDEX idx_qc_results_record ON qc_results(record_id);
CREATE INDEX idx_qc_results_rule ON qc_results(rule_id);
CREATE INDEX idx_qc_results_batch ON qc_results(analysis_batch_id);
CREATE INDEX idx_qc_results_status ON qc_results(result_status);
CREATE INDEX idx_qc_results_review ON qc_results(manual_review_status);
CREATE INDEX idx_qc_results_created ON qc_results(created_at);

-- 缓存表索引
CREATE INDEX idx_qc_cache_hash ON qc_analysis_cache(content_hash);
CREATE INDEX idx_qc_cache_rule ON qc_analysis_cache(rule_id);
CREATE INDEX idx_qc_cache_expires ON qc_analysis_cache(expires_at);

-- 批量任务表索引
CREATE INDEX idx_batch_tasks_type ON batch_processing_tasks(task_type);
CREATE INDEX idx_batch_tasks_status ON batch_processing_tasks(status);
CREATE INDEX idx_batch_tasks_created_by ON batch_processing_tasks(created_by);
CREATE INDEX idx_batch_tasks_created ON batch_processing_tasks(created_at);

-- 分析历史表索引
CREATE INDEX idx_qc_history_record ON qc_analysis_history(record_id);
CREATE INDEX idx_qc_history_batch ON qc_analysis_history(analysis_batch_id);
CREATE INDEX idx_qc_history_created ON qc_analysis_history(created_at);

-- 告警记录表索引
CREATE INDEX idx_alerts_type ON alert_records(alert_type);
CREATE INDEX idx_alerts_severity ON alert_records(severity);
CREATE INDEX idx_alerts_status ON alert_records(status);
CREATE INDEX idx_alerts_record ON alert_records(related_record_id);
CREATE INDEX idx_alerts_created ON alert_records(created_at);

-- 数据快照表索引
CREATE INDEX idx_snapshots_date ON data_snapshots(snapshot_date);
CREATE INDEX idx_snapshots_type ON data_snapshots(snapshot_type);
CREATE INDEX idx_snapshots_department ON data_snapshots(department_id);

-- =============================================
-- 第七步：创建统计分析视图
-- =============================================

-- 科室质控统计视图
CREATE VIEW v_department_qc_stats AS
SELECT 
    d.id as department_id,
    d.name as department_name,
    d.code as department_code,
    COUNT(mr.id) as total_records,
    COUNT(CASE WHEN mr.status = 'completed' THEN 1 END) as completed_records,
    COUNT(CASE WHEN mr.qc_grade = '甲级' THEN 1 END) as grade_a_count,
    COUNT(CASE WHEN mr.qc_grade = '乙级' THEN 1 END) as grade_b_count,
    COUNT(CASE WHEN mr.qc_grade = '丙级' THEN 1 END) as grade_c_count,
    ROUND(AVG(mr.qc_score), 2) as avg_qc_score,
    COUNT(CASE WHEN mr.created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as records_last_30_days
FROM departments d
LEFT JOIN medical_records mr ON d.id = mr.department_id
WHERE d.is_active = true
GROUP BY d.id, d.name, d.code;

-- 医生质控表现视图
CREATE VIEW v_doctor_performance AS
SELECT 
    up.id as doctor_id,
    up.full_name as doctor_name,
    up.department_id,
    d.name as department_name,
    COUNT(mr.id) as total_records,
    COUNT(CASE WHEN mr.qc_grade = '甲级' THEN 1 END) as grade_a_count,
    ROUND(
        COUNT(CASE WHEN mr.qc_grade = '甲级' THEN 1 END) * 100.0 / NULLIF(COUNT(mr.id), 0), 
        2
    ) as grade_a_rate,
    ROUND(AVG(mr.qc_score), 2) as avg_qc_score,
    COUNT(CASE WHEN mr.created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as records_last_30_days
FROM user_profiles up
LEFT JOIN medical_records mr ON up.id = mr.doctor_id
LEFT JOIN departments d ON up.department_id = d.id
WHERE up.role_type = 'doctor' AND up.is_active = true
GROUP BY up.id, up.full_name, up.department_id, d.name;

-- 质控趋势视图
CREATE VIEW v_qc_trends AS
SELECT 
    DATE(mr.created_at) as analysis_date,
    COUNT(mr.id) as total_records,
    COUNT(CASE WHEN mr.qc_grade = '甲级' THEN 1 END) as grade_a_count,
    COUNT(CASE WHEN mr.qc_grade = '乙级' THEN 1 END) as grade_b_count,
    COUNT(CASE WHEN mr.qc_grade = '丙级' THEN 1 END) as grade_c_count,
    ROUND(AVG(mr.qc_score), 2) as avg_score,
    COUNT(CASE WHEN qr.result_status = 'failed' THEN 1 END) as total_issues
FROM medical_records mr
LEFT JOIN qc_results qr ON mr.id = qr.record_id
WHERE mr.status = 'completed'
GROUP BY DATE(mr.created_at)
ORDER BY analysis_date DESC;
