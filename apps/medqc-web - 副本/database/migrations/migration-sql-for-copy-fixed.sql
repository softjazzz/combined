-- 004_add_analytics_and_reporting.sql
-- 360度数据分析和智能报表系统数据库结构

-- 0. 创建用户角色表（如果不存在）
CREATE TABLE IF NOT EXISTS user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'qc_manager', 'qc_staff', 'doctor')),
    hospital_id UUID,
    department VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, role)
);

-- 1. 数据立方体表 - 用于OLAP分析
CREATE TABLE data_cubes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cube_name VARCHAR(100) NOT NULL,
    dimensions JSONB NOT NULL, -- 维度定义
    measures JSONB NOT NULL, -- 度量定义
    aggregation_rules JSONB, -- 聚合规则
    refresh_schedule VARCHAR(50), -- 刷新计划
    last_refresh TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- 2. 分析指标表
CREATE TABLE analytics_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_code VARCHAR(50) UNIQUE NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(30) NOT NULL, -- count, sum, avg, ratio, trend
    category VARCHAR(30) NOT NULL, -- department, doctor, time, quality, efficiency
    calculation_formula TEXT, -- 计算公式
    unit VARCHAR(20), -- 单位
    target_value DECIMAL(10,2), -- 目标值
    warning_threshold DECIMAL(10,2), -- 警告阈值
    critical_threshold DECIMAL(10,2), -- 严重阈值
    is_active BOOLEAN DEFAULT true,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. 分析结果表
CREATE TABLE analytics_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_id UUID REFERENCES analytics_metrics(id),
    dimension_values JSONB NOT NULL, -- 维度值 {department: "内科", date: "2024-01"}
    metric_value DECIMAL(15,4) NOT NULL,
    comparison_value DECIMAL(15,4), -- 对比值
    trend_direction VARCHAR(10), -- up, down, stable
    trend_percentage DECIMAL(5,2), -- 趋势百分比
    calculation_date DATE NOT NULL,
    calculation_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    data_source VARCHAR(50), -- 数据来源
    confidence_level DECIMAL(3,2) DEFAULT 1.0, -- 置信度
    
    -- 创建复合索引
    UNIQUE(metric_id, dimension_values, calculation_date)
);

-- 4. 报表模板表
CREATE TABLE report_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_code VARCHAR(50) UNIQUE NOT NULL,
    template_name VARCHAR(100) NOT NULL,
    template_type VARCHAR(30) NOT NULL, -- qc_summary, performance, trend, comparison
    description TEXT,
    layout_config JSONB NOT NULL, -- 布局配置
    chart_configs JSONB NOT NULL, -- 图表配置
    filters JSONB, -- 过滤器配置
    schedule_config JSONB, -- 定时配置
    output_formats TEXT[] DEFAULT ARRAY['pdf', 'excel'], -- 输出格式
    is_active BOOLEAN DEFAULT true,
    is_system_template BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- 5. 报表实例表
CREATE TABLE report_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES report_templates(id),
    report_name VARCHAR(100) NOT NULL,
    report_period VARCHAR(30) NOT NULL, -- daily, weekly, monthly, quarterly, yearly
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    parameters JSONB, -- 报表参数
    status VARCHAR(20) DEFAULT 'pending', -- pending, generating, completed, failed
    progress INTEGER DEFAULT 0, -- 生成进度
    file_path TEXT, -- 文件路径
    file_size BIGINT, -- 文件大小
    mime_type VARCHAR(100), -- 文件类型
    generation_time INTEGER, -- 生成耗时(秒)
    error_message TEXT, -- 错误信息
    generated_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE, -- 过期时间
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- 6. 数据快照表 - 用于历史数据对比
CREATE TABLE data_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_name VARCHAR(100) NOT NULL,
    snapshot_type VARCHAR(30) NOT NULL, -- daily, weekly, monthly
    snapshot_date DATE NOT NULL,
    data_summary JSONB NOT NULL, -- 数据摘要
    record_count INTEGER NOT NULL,
    avg_qc_score DECIMAL(5,2),
    department_stats JSONB, -- 科室统计
    doctor_stats JSONB, -- 医生统计
    quality_indicators JSONB, -- 质量指标
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. 对比分析表
CREATE TABLE comparison_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_name VARCHAR(100) NOT NULL,
    analysis_type VARCHAR(30) NOT NULL, -- department_vs_department, period_vs_period, doctor_vs_doctor
    baseline_criteria JSONB NOT NULL, -- 基线条件
    comparison_criteria JSONB NOT NULL, -- 对比条件
    analysis_results JSONB NOT NULL, -- 分析结果
    insights JSONB, -- 洞察分析
    recommendations JSONB, -- 建议
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- 8. 预警规则表
CREATE TABLE alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name VARCHAR(100) NOT NULL,
    metric_id UUID REFERENCES analytics_metrics(id),
    condition_type VARCHAR(20) NOT NULL, -- threshold, trend, anomaly
    condition_config JSONB NOT NULL, -- 条件配置
    alert_level VARCHAR(20) NOT NULL, -- info, warning, critical
    notification_config JSONB, -- 通知配置
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- 9. 预警记录表
CREATE TABLE alert_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id UUID REFERENCES alert_rules(id),
    alert_level VARCHAR(20) NOT NULL,
    alert_message TEXT NOT NULL,
    metric_value DECIMAL(15,4),
    dimension_values JSONB,
    triggered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by UUID REFERENCES auth.users(id),
    resolution_notes TEXT,
    is_resolved BOOLEAN DEFAULT false
);

-- 10. 创建索引
CREATE INDEX idx_analytics_results_metric_date ON analytics_results(metric_id, calculation_date);
CREATE INDEX idx_analytics_results_dimensions ON analytics_results USING GIN(dimension_values);
CREATE INDEX idx_report_instances_template_period ON report_instances(template_id, period_start, period_end);
CREATE INDEX idx_data_snapshots_date_type ON data_snapshots(snapshot_date, snapshot_type);
CREATE INDEX idx_alert_records_triggered ON alert_records(triggered_at) WHERE NOT is_resolved;

-- 11. 创建分析视图
CREATE VIEW v_department_analytics AS
SELECT 
    mr.department,
    COUNT(*) as total_records,
    AVG(qr.overall_score) as avg_qc_score,
    COUNT(CASE WHEN qr.grade = 'A' THEN 1 END) as grade_a_count,
    COUNT(CASE WHEN qr.grade = 'B' THEN 1 END) as grade_b_count,
    COUNT(CASE WHEN qr.grade = 'C' THEN 1 END) as grade_c_count,
    AVG(qr.confidence_score) as avg_confidence,
    DATE_TRUNC('month', mr.created_at) as month
FROM medical_records mr
LEFT JOIN qc_results qr ON mr.id = qr.record_id
WHERE mr.created_at >= NOW() - INTERVAL '1 year'
GROUP BY mr.department, DATE_TRUNC('month', mr.created_at);

CREATE VIEW v_doctor_performance AS
SELECT 
    COALESCE(u.raw_user_meta_data->>'display_name', u.email) as doctor_name,
    mr.department,
    COUNT(*) as total_records,
    AVG(qr.overall_score) as avg_qc_score,
    COUNT(CASE WHEN qr.grade = 'A' THEN 1 END) as grade_a_count,
    COUNT(CASE WHEN qr.grade = 'B' THEN 1 END) as grade_b_count,
    COUNT(CASE WHEN qr.grade = 'C' THEN 1 END) as grade_c_count,
    AVG(EXTRACT(EPOCH FROM (qr.analysis_time - mr.created_at))/3600) as avg_processing_hours,
    DATE_TRUNC('month', mr.created_at) as month
FROM medical_records mr
LEFT JOIN qc_results qr ON mr.id = qr.record_id
LEFT JOIN auth.users u ON mr.doctor_id = u.id
WHERE mr.created_at >= NOW() - INTERVAL '1 year'
GROUP BY COALESCE(u.raw_user_meta_data->>'display_name', u.email), mr.department, DATE_TRUNC('month', mr.created_at);

CREATE VIEW v_quality_trends AS
SELECT 
    DATE_TRUNC('day', mr.created_at) as date,
    COUNT(*) as daily_records,
    AVG(qr.overall_score) as avg_qc_score,
    STDDEV(qr.overall_score) as score_stddev,
    COUNT(CASE WHEN qr.grade = 'A' THEN 1 END)::FLOAT / COUNT(*) * 100 as grade_a_rate,
    COUNT(CASE WHEN qr.grade = 'B' THEN 1 END)::FLOAT / COUNT(*) * 100 as grade_b_rate,
    COUNT(CASE WHEN qr.grade = 'C' THEN 1 END)::FLOAT / COUNT(*) * 100 as grade_c_rate,
    AVG(qr.confidence_score) as avg_confidence
FROM medical_records mr
LEFT JOIN qc_results qr ON mr.id = qr.record_id
WHERE mr.created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', mr.created_at)
ORDER BY date;

-- 12. 创建分析函数
CREATE OR REPLACE FUNCTION calculate_department_ranking(
    p_period_start DATE DEFAULT NOW() - INTERVAL '1 month',
    p_period_end DATE DEFAULT NOW()
) RETURNS TABLE (
    department VARCHAR,
    total_records BIGINT,
    avg_score DECIMAL,
    grade_a_rate DECIMAL,
    rank_by_score INTEGER,
    rank_by_volume INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        mr.department,
        COUNT(*) as total_records,
        ROUND(AVG(qr.overall_score), 2) as avg_score,
        ROUND(COUNT(CASE WHEN qr.grade = 'A' THEN 1 END)::DECIMAL / COUNT(*) * 100, 2) as grade_a_rate,
        RANK() OVER (ORDER BY AVG(qr.overall_score) DESC) as rank_by_score,
        RANK() OVER (ORDER BY COUNT(*) DESC) as rank_by_volume
    FROM medical_records mr
    LEFT JOIN qc_results qr ON mr.id = qr.record_id
    WHERE mr.created_at >= p_period_start AND mr.created_at <= p_period_end
    GROUP BY mr.department
    ORDER BY avg_score DESC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION generate_quality_insight(
    p_department VARCHAR DEFAULT NULL,
    p_period_days INTEGER DEFAULT 30
) RETURNS JSONB AS $$
DECLARE
    result JSONB;
    current_avg DECIMAL;
    previous_avg DECIMAL;
    trend_direction VARCHAR;
    improvement_rate DECIMAL;
BEGIN
    -- 计算当前周期平均分
    SELECT AVG(qr.overall_score) INTO current_avg
    FROM medical_records mr
    LEFT JOIN qc_results qr ON mr.id = qr.record_id
    WHERE (p_department IS NULL OR mr.department = p_department)
    AND mr.created_at >= NOW() - INTERVAL '1 day' * p_period_days;
    
    -- 计算上一周期平均分
    SELECT AVG(qr.overall_score) INTO previous_avg
    FROM medical_records mr
    LEFT JOIN qc_results qr ON mr.id = qr.record_id
    WHERE (p_department IS NULL OR mr.department = p_department)
    AND mr.created_at >= NOW() - INTERVAL '1 day' * (p_period_days * 2)
    AND mr.created_at < NOW() - INTERVAL '1 day' * p_period_days;
    
    -- 计算趋势
    IF current_avg > previous_avg THEN
        trend_direction := 'improving';
        improvement_rate := ROUND((current_avg - previous_avg) / previous_avg * 100, 2);
    ELSIF current_avg < previous_avg THEN
        trend_direction := 'declining';
        improvement_rate := ROUND((previous_avg - current_avg) / previous_avg * 100, 2);
    ELSE
        trend_direction := 'stable';
        improvement_rate := 0;
    END IF;
    
    result := jsonb_build_object(
        'current_avg_score', current_avg,
        'previous_avg_score', previous_avg,
        'trend_direction', trend_direction,
        'improvement_rate', improvement_rate,
        'analysis_period_days', p_period_days,
        'department', COALESCE(p_department, 'all')
    );
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- 13. 插入默认分析指标
INSERT INTO analytics_metrics (metric_code, metric_name, metric_type, category, unit, target_value, warning_threshold, critical_threshold, display_order) VALUES
('total_records', '总病案数', 'count', 'volume', '份', 1000, 800, 500, 1),
('avg_qc_score', '平均质控评分', 'avg', 'quality', '分', 85, 80, 75, 2),
('grade_a_rate', '优秀率(A级)', 'ratio', 'quality', '%', 60, 50, 40, 3),
('grade_b_rate', '良好率(B级)', 'ratio', 'quality', '%', 30, 35, 40, 4),
('grade_c_rate', '需改进率(C级)', 'ratio', 'quality', '%', 10, 15, 20, 5),
('avg_processing_time', '平均处理时间', 'avg', 'efficiency', '小时', 4, 6, 8, 6),
('completion_rate', '完成率', 'ratio', 'efficiency', '%', 95, 90, 85, 7),
('doctor_productivity', '医生工作量', 'count', 'productivity', '份/天', 20, 15, 10, 8),
('error_rate', '错误率', 'ratio', 'quality', '%', 5, 8, 12, 9),
('review_rate', '复审率', 'ratio', 'quality', '%', 10, 15, 20, 10);

-- 14. 插入默认报表模板
INSERT INTO report_templates (template_code, template_name, template_type, description, layout_config, chart_configs, is_system_template) VALUES
('qc_monthly_summary', '月度质控工作总结', 'qc_summary', '月度质控工作全面总结报告', 
 '{"sections": ["overview", "department_analysis", "doctor_performance", "quality_trends", "recommendations"]}',
 '{"charts": [{"type": "line", "title": "质控评分趋势"}, {"type": "bar", "title": "科室对比"}, {"type": "pie", "title": "等级分布"}]}',
 true),
('department_comparison', '科室对比分析', 'comparison', '各科室质控指标对比分析报告',
 '{"sections": ["comparison_matrix", "ranking", "best_practices", "improvement_areas"]}',
 '{"charts": [{"type": "radar", "title": "科室雷达图"}, {"type": "bar", "title": "排名对比"}, {"type": "scatter", "title": "质量分布"}]}',
 true),
('doctor_performance', '医生绩效报告', 'performance', '医生个人质控绩效分析报告',
 '{"sections": ["individual_summary", "peer_comparison", "improvement_tracking", "goals"]}',
 '{"charts": [{"type": "gauge", "title": "个人评分"}, {"type": "line", "title": "历史趋势"}, {"type": "bar", "title": "同级对比"}]}',
 true),
('quality_trends', '质量趋势分析', 'trend', '质控质量长期趋势分析报告',
 '{"sections": ["trend_overview", "seasonal_analysis", "forecast", "risk_assessment"]}',
 '{"charts": [{"type": "line", "title": "长期趋势"}, {"type": "heatmap", "title": "季节性分析"}, {"type": "forecast", "title": "预测分析"}]}',
 true);

-- 15. 创建RLS策略
ALTER TABLE data_cubes ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE comparison_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_records ENABLE ROW LEVEL SECURITY;

-- 管理员和质控管理员可以访问所有数据
CREATE POLICY "Admin and QC managers can access all analytics data" ON analytics_results
FOR ALL USING (
    EXISTS (
        SELECT 1 FROM user_roles ur
        WHERE ur.user_id = auth.uid()
        AND ur.role IN ('admin', 'qc_manager')
    )
);

-- 医生只能查看自己相关的数据
CREATE POLICY "Doctors can view their own analytics" ON analytics_results
FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM user_roles ur
        WHERE ur.user_id = auth.uid()
        AND ur.role = 'doctor'
        AND (dimension_values->>'doctor_id' = auth.uid()::text OR dimension_values->>'department' = ur.department)
    )
);

-- 报表实例访问策略
CREATE POLICY "Users can access reports based on role" ON report_instances
FOR ALL USING (
    EXISTS (
        SELECT 1 FROM user_roles ur
        WHERE ur.user_id = auth.uid()
        AND (ur.role IN ('admin', 'qc_manager') OR created_by = auth.uid())
    )
);

-- 16. 创建触发器更新时间戳
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_data_cubes_updated_at BEFORE UPDATE ON data_cubes
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analytics_metrics_updated_at BEFORE UPDATE ON analytics_metrics
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_report_templates_updated_at BEFORE UPDATE ON report_templates
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 17. 创建定时任务函数（需要pg_cron扩展）
CREATE OR REPLACE FUNCTION schedule_daily_analytics()
RETURNS void AS $$
BEGIN
    -- 每日数据快照
    INSERT INTO data_snapshots (snapshot_name, snapshot_type, snapshot_date, data_summary, record_count, avg_qc_score, department_stats, doctor_stats, quality_indicators)
    SELECT 
        'Daily Snapshot ' || CURRENT_DATE,
        'daily',
        CURRENT_DATE,
        jsonb_build_object(
            'total_records', COUNT(*),
            'avg_score', AVG(qr.overall_score),
            'grade_distribution', jsonb_build_object(
                'A', COUNT(CASE WHEN qr.grade = 'A' THEN 1 END),
                'B', COUNT(CASE WHEN qr.grade = 'B' THEN 1 END),
                'C', COUNT(CASE WHEN qr.grade = 'C' THEN 1 END)
            )
        ),
        COUNT(*),
        AVG(qr.overall_score),
        (SELECT jsonb_object_agg(department, dept_stats) FROM (
            SELECT mr.department, jsonb_build_object('count', COUNT(*), 'avg_score', AVG(qr.overall_score)) as dept_stats
            FROM medical_records mr
            LEFT JOIN qc_results qr ON mr.id = qr.record_id
            WHERE DATE(mr.created_at) = CURRENT_DATE
            GROUP BY mr.department
        ) dept_data),
        '{}',
        jsonb_build_object(
            'completion_rate', COUNT(CASE WHEN mr.status = 'completed' THEN 1 END)::FLOAT / COUNT(*) * 100,
            'avg_processing_time', AVG(EXTRACT(EPOCH FROM (qr.analysis_time - mr.created_at))/3600)
        )
    FROM medical_records mr
    LEFT JOIN qc_results qr ON mr.id = qr.record_id
    WHERE DATE(mr.created_at) = CURRENT_DATE;
    
    -- 更新分析结果
    -- 这里可以添加更多的分析计算逻辑
    
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE data_cubes IS '数据立方体定义表';
COMMENT ON TABLE analytics_metrics IS '分析指标定义表';
COMMENT ON TABLE analytics_results IS '分析结果数据表';
COMMENT ON TABLE report_templates IS '报表模板配置表';
COMMENT ON TABLE report_instances IS '报表实例记录表';
COMMENT ON TABLE data_snapshots IS '数据快照表';
COMMENT ON TABLE comparison_analyses IS '对比分析表';
COMMENT ON TABLE alert_rules IS '预警规则表';
COMMENT ON TABLE alert_records IS '预警记录表'; 