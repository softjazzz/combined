-- 报表调度系统数据库迁移
-- 创建报表调度和执行历史相关表

-- 1. 创建调度任务表
CREATE TABLE IF NOT EXISTS yibao_scheduled_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    template_id TEXT NOT NULL,
    schedule_type TEXT NOT NULL CHECK (schedule_type IN ('daily', 'weekly', 'monthly', 'custom')),
    schedule_config JSONB NOT NULL DEFAULT '{}',
    parameters JSONB NOT NULL DEFAULT '{}',
    output_format TEXT NOT NULL CHECK (output_format IN ('csv', 'excel', 'pdf')),
    recipients JSONB NOT NULL DEFAULT '[]',
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_execution TIMESTAMPTZ,
    next_execution TIMESTAMPTZ,
    created_by UUID REFERENCES auth.users(id),
    updated_by UUID REFERENCES auth.users(id)
);

-- 2. 创建执行历史表
CREATE TABLE IF NOT EXISTS yibao_report_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES yibao_scheduled_reports(id) ON DELETE CASCADE,
    execution_time TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'running')),
    duration_ms INTEGER,
    error_message TEXT,
    output_size INTEGER,
    recipients_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. 创建报表模板表（如果不存在）
CREATE TABLE IF NOT EXISTS yibao_report_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL CHECK (type IN ('violations', 'departments', 'doctors', 'trends', 'summary')),
    fields JSONB NOT NULL DEFAULT '[]',
    default_format TEXT NOT NULL CHECK (default_format IN ('csv', 'excel', 'pdf')),
    parameters JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES auth.users(id)
);

-- 4. 创建邮件发送日志表
CREATE TABLE IF NOT EXISTS yibao_email_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID REFERENCES yibao_report_executions(id) ON DELETE CASCADE,
    recipient_email TEXT NOT NULL,
    recipient_name TEXT,
    subject TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'pending')),
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. 添加索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_scheduled_reports_enabled ON yibao_scheduled_reports(enabled);
CREATE INDEX IF NOT EXISTS idx_scheduled_reports_next_execution ON yibao_scheduled_reports(next_execution) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_scheduled_reports_template ON yibao_scheduled_reports(template_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_reports_created_by ON yibao_scheduled_reports(created_by);

CREATE INDEX IF NOT EXISTS idx_report_executions_job_id ON yibao_report_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_report_executions_status ON yibao_report_executions(status);
CREATE INDEX IF NOT EXISTS idx_report_executions_execution_time ON yibao_report_executions(execution_time DESC);

CREATE INDEX IF NOT EXISTS idx_email_logs_execution_id ON yibao_email_logs(execution_id);
CREATE INDEX IF NOT EXISTS idx_email_logs_status ON yibao_email_logs(status);
CREATE INDEX IF NOT EXISTS idx_email_logs_sent_at ON yibao_email_logs(sent_at DESC);

-- 6. 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_scheduled_reports_updated_at 
    BEFORE UPDATE ON yibao_scheduled_reports 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 7. 插入默认报表模板
INSERT INTO yibao_report_templates (id, name, description, type, fields, default_format, parameters) VALUES
('violations_summary', '违规汇总报告', '按时间范围统计的违规数据汇总', 'violations', 
 '["date", "total_violations", "block_count", "warn_count", "info_count", "unique_visits", "unique_rules"]', 
 'excel', 
 '{"timeRange": "30d", "granularity": "day", "includeDetails": false}'),

('department_performance', '科室质控绩效报告', '各科室质控表现对比分析', 'departments', 
 '["department_name", "total_violations", "violation_rate", "risk_level", "quality_score", "trend"]', 
 'excel', 
 '{"timeRange": "30d", "includeComparison": true, "sortBy": "total_violations"}'),

('doctor_quality_profile', '医生质控档案', '医生个人质控表现详细档案', 'doctors', 
 '["doctor_name", "department_name", "total_violations", "violation_rate", "quality_score", "performance_grade", "improvement_suggestions"]', 
 'pdf', 
 '{"timeRange": "30d", "includeProfile": true, "departmentFilter": null}'),

('trend_analysis', '趋势分析报告', '违规趋势变化分析和预测', 'trends', 
 '["date", "violations", "trend", "moving_average", "anomalies", "predictions"]', 
 'excel', 
 '{"timeRange": "90d", "includeAnalysis": true, "includePredictions": true}'),

('executive_summary', '管理层汇总报告', '面向管理层的综合质控报告', 'summary', 
 '["kpi_summary", "department_ranking", "risk_alerts", "improvement_recommendations"]', 
 'pdf', 
 '{"timeRange": "30d", "includeCharts": true, "executiveLevel": true}')

ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    type = EXCLUDED.type,
    fields = EXCLUDED.fields,
    default_format = EXCLUDED.default_format,
    parameters = EXCLUDED.parameters,
    updated_at = now();

-- 8. 创建用于获取待执行任务的函数
CREATE OR REPLACE FUNCTION get_pending_report_jobs()
RETURNS TABLE (
    id UUID,
    name TEXT,
    template_id TEXT,
    schedule_config JSONB,
    parameters JSONB,
    output_format TEXT,
    recipients JSONB,
    next_execution TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        sr.id,
        sr.name,
        sr.template_id,
        sr.schedule_config,
        sr.parameters,
        sr.output_format,
        sr.recipients,
        sr.next_execution
    FROM yibao_scheduled_reports sr
    WHERE sr.enabled = true 
      AND sr.next_execution <= now()
    ORDER BY sr.next_execution ASC;
END;
$$ LANGUAGE plpgsql;

-- 9. 创建更新下次执行时间的函数
CREATE OR REPLACE FUNCTION update_next_execution(
    job_id UUID,
    next_exec TIMESTAMPTZ
) RETURNS VOID AS $$
BEGIN
    UPDATE yibao_scheduled_reports 
    SET 
        last_execution = now(),
        next_execution = next_exec,
        updated_at = now()
    WHERE id = job_id;
END;
$$ LANGUAGE plpgsql;

-- 10. 创建获取执行统计的函数
CREATE OR REPLACE FUNCTION get_execution_stats(
    job_id_param UUID DEFAULT NULL,
    days_back INTEGER DEFAULT 30
) RETURNS TABLE (
    total_executions BIGINT,
    successful_executions BIGINT,
    failed_executions BIGINT,
    success_rate NUMERIC,
    avg_duration_ms NUMERIC,
    total_output_size BIGINT,
    total_recipients BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_executions,
        COUNT(*) FILTER (WHERE status = 'success') as successful_executions,
        COUNT(*) FILTER (WHERE status = 'failed') as failed_executions,
        ROUND(
            (COUNT(*) FILTER (WHERE status = 'success')::NUMERIC / NULLIF(COUNT(*), 0)) * 100, 
            2
        ) as success_rate,
        ROUND(AVG(duration_ms), 2) as avg_duration_ms,
        COALESCE(SUM(output_size), 0) as total_output_size,
        COALESCE(SUM(recipients_count), 0) as total_recipients
    FROM yibao_report_executions
    WHERE (job_id_param IS NULL OR job_id = job_id_param)
      AND execution_time >= (now() - (days_back || ' days')::INTERVAL);
END;
$$ LANGUAGE plpgsql;

-- 11. 创建清理旧执行记录的函数
CREATE OR REPLACE FUNCTION cleanup_old_executions(
    retention_days INTEGER DEFAULT 90
) RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM yibao_report_executions 
    WHERE execution_time < (now() - (retention_days || ' days')::INTERVAL);
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 12. 设置行级安全策略 (RLS)
ALTER TABLE yibao_scheduled_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_report_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_report_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE yibao_email_logs ENABLE ROW LEVEL SECURITY;

-- 创建基本的 RLS 策略（可根据实际需求调整）
CREATE POLICY "Users can view their own scheduled reports" ON yibao_scheduled_reports
    FOR SELECT USING (auth.uid() = created_by);

CREATE POLICY "Users can create scheduled reports" ON yibao_scheduled_reports
    FOR INSERT WITH CHECK (auth.uid() = created_by);

CREATE POLICY "Users can update their own scheduled reports" ON yibao_scheduled_reports
    FOR UPDATE USING (auth.uid() = created_by);

CREATE POLICY "Users can delete their own scheduled reports" ON yibao_scheduled_reports
    FOR DELETE USING (auth.uid() = created_by);

-- 执行历史的策略
CREATE POLICY "Users can view executions of their reports" ON yibao_report_executions
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM yibao_scheduled_reports 
            WHERE id = job_id AND created_by = auth.uid()
        )
    );

-- 报表模板的策略（所有用户可读）
CREATE POLICY "All users can view report templates" ON yibao_report_templates
    FOR SELECT USING (true);

-- 邮件日志的策略
CREATE POLICY "Users can view email logs of their reports" ON yibao_email_logs
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM yibao_report_executions re
            JOIN yibao_scheduled_reports sr ON re.job_id = sr.id
            WHERE re.id = execution_id AND sr.created_by = auth.uid()
        )
    );

-- 13. 创建通知函数（用于实时更新）
CREATE OR REPLACE FUNCTION notify_report_execution()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify(
        'report_execution_update',
        json_build_object(
            'job_id', NEW.job_id,
            'execution_id', NEW.id,
            'status', NEW.status,
            'execution_time', NEW.execution_time
        )::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER report_execution_notify
    AFTER INSERT OR UPDATE ON yibao_report_executions
    FOR EACH ROW EXECUTE FUNCTION notify_report_execution();

-- 14. 添加注释
COMMENT ON TABLE yibao_scheduled_reports IS '报表调度任务表';
COMMENT ON TABLE yibao_report_executions IS '报表执行历史表';
COMMENT ON TABLE yibao_report_templates IS '报表模板表';
COMMENT ON TABLE yibao_email_logs IS '邮件发送日志表';

COMMENT ON COLUMN yibao_scheduled_reports.schedule_config IS '调度配置JSON，包含时间、星期几、月份等信息';
COMMENT ON COLUMN yibao_scheduled_reports.parameters IS '报表生成参数JSON';
COMMENT ON COLUMN yibao_scheduled_reports.recipients IS '收件人列表JSON';
COMMENT ON COLUMN yibao_report_executions.duration_ms IS '执行耗时（毫秒）';
COMMENT ON COLUMN yibao_report_executions.output_size IS '输出文件大小（字节）';
