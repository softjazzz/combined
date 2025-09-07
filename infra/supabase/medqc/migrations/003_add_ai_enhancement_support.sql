-- 003_add_ai_enhancement_support.sql
-- 添加AI增强功能支持的数据库表结构

-- AI学习记录表
CREATE TABLE IF NOT EXISTS ai_learning_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id VARCHAR(255) NOT NULL,
    original_score INTEGER NOT NULL,
    reviewed_score INTEGER NOT NULL,
    feedback TEXT,
    corrections JSONB DEFAULT '[]'::jsonb,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    reviewer_id UUID REFERENCES auth.users(id),
    hospital_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI知识库表
CREATE TABLE IF NOT EXISTS ai_knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(100) NOT NULL,
    pattern TEXT NOT NULL,
    confidence DECIMAL(3,2) DEFAULT 0.5,
    usage_count INTEGER DEFAULT 0,
    success_rate DECIMAL(3,2) DEFAULT 0.0,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    hospital_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI性能指标表
CREATE TABLE IF NOT EXISTS ai_performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    model_version VARCHAR(50) NOT NULL,
    metrics JSONB NOT NULL,
    hospital_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI学习任务表
CREATE TABLE IF NOT EXISTS ai_learning_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(255) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'medium',
    parameters JSONB DEFAULT '{}'::jsonb,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    hospital_id UUID
);

-- AI模型版本表
CREATE TABLE IF NOT EXISTS ai_model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version VARCHAR(50) UNIQUE NOT NULL,
    release_date TIMESTAMPTZ DEFAULT NOW(),
    improvements JSONB DEFAULT '[]'::jsonb,
    performance_metrics JSONB NOT NULL,
    is_active BOOLEAN DEFAULT false,
    rollback_available BOOLEAN DEFAULT true,
    hospital_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 多模态分析结果表
CREATE TABLE IF NOT EXISTS multimodal_analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID REFERENCES medical_records(id),
    text_analysis JSONB,
    image_analysis JSONB,
    structured_data_analysis JSONB,
    cross_modal_insights JSONB DEFAULT '[]'::jsonb,
    analysis_time TIMESTAMPTZ DEFAULT NOW(),
    hospital_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 上下文分析缓存表
CREATE TABLE IF NOT EXISTS context_analysis_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    context_data JSONB NOT NULL,
    expiry_time TIMESTAMPTZ NOT NULL,
    hospital_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 患者历史分析表
CREATE TABLE IF NOT EXISTS patient_history_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id VARCHAR(255) NOT NULL,
    record_id UUID REFERENCES medical_records(id),
    historical_pattern JSONB,
    risk_factors JSONB DEFAULT '[]'::jsonb,
    quality_trend JSONB,
    last_analysis TIMESTAMPTZ DEFAULT NOW(),
    hospital_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_learning_records_record_id ON ai_learning_records(record_id);
CREATE INDEX IF NOT EXISTS idx_ai_learning_records_timestamp ON ai_learning_records(timestamp);
CREATE INDEX IF NOT EXISTS idx_ai_learning_records_reviewer_id ON ai_learning_records(reviewer_id);
CREATE INDEX IF NOT EXISTS idx_ai_learning_records_hospital_id ON ai_learning_records(hospital_id);

CREATE INDEX IF NOT EXISTS idx_ai_knowledge_base_category ON ai_knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_base_confidence ON ai_knowledge_base(confidence);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_base_usage_count ON ai_knowledge_base(usage_count);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_base_hospital_id ON ai_knowledge_base(hospital_id);

CREATE INDEX IF NOT EXISTS idx_ai_performance_metrics_timestamp ON ai_performance_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_ai_performance_metrics_model_version ON ai_performance_metrics(model_version);
CREATE INDEX IF NOT EXISTS idx_ai_performance_metrics_hospital_id ON ai_performance_metrics(hospital_id);

CREATE INDEX IF NOT EXISTS idx_ai_learning_tasks_status ON ai_learning_tasks(status);
CREATE INDEX IF NOT EXISTS idx_ai_learning_tasks_priority ON ai_learning_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_ai_learning_tasks_type ON ai_learning_tasks(type);
CREATE INDEX IF NOT EXISTS idx_ai_learning_tasks_created_at ON ai_learning_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_learning_tasks_hospital_id ON ai_learning_tasks(hospital_id);

CREATE INDEX IF NOT EXISTS idx_ai_model_versions_version ON ai_model_versions(version);
CREATE INDEX IF NOT EXISTS idx_ai_model_versions_is_active ON ai_model_versions(is_active);
CREATE INDEX IF NOT EXISTS idx_ai_model_versions_hospital_id ON ai_model_versions(hospital_id);

CREATE INDEX IF NOT EXISTS idx_multimodal_analysis_results_record_id ON multimodal_analysis_results(record_id);
CREATE INDEX IF NOT EXISTS idx_multimodal_analysis_results_analysis_time ON multimodal_analysis_results(analysis_time);
CREATE INDEX IF NOT EXISTS idx_multimodal_analysis_results_hospital_id ON multimodal_analysis_results(hospital_id);

CREATE INDEX IF NOT EXISTS idx_context_analysis_cache_cache_key ON context_analysis_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_context_analysis_cache_expiry_time ON context_analysis_cache(expiry_time);
CREATE INDEX IF NOT EXISTS idx_context_analysis_cache_hospital_id ON context_analysis_cache(hospital_id);

CREATE INDEX IF NOT EXISTS idx_patient_history_analysis_patient_id ON patient_history_analysis(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_history_analysis_record_id ON patient_history_analysis(record_id);
CREATE INDEX IF NOT EXISTS idx_patient_history_analysis_last_analysis ON patient_history_analysis(last_analysis);
CREATE INDEX IF NOT EXISTS idx_patient_history_analysis_hospital_id ON patient_history_analysis(hospital_id);

-- 创建更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为相关表添加更新时间触发器
CREATE TRIGGER update_ai_learning_records_updated_at
    BEFORE UPDATE ON ai_learning_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ai_knowledge_base_updated_at
    BEFORE UPDATE ON ai_knowledge_base
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_patient_history_analysis_updated_at
    BEFORE UPDATE ON patient_history_analysis
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 创建AI性能统计视图
CREATE OR REPLACE VIEW ai_performance_summary AS
SELECT 
    model_version,
    COUNT(*) as total_analyses,
    AVG((metrics->>'accuracy')::numeric) as avg_accuracy,
    AVG((metrics->>'precision')::numeric) as avg_precision,
    AVG((metrics->>'recall')::numeric) as avg_recall,
    AVG((metrics->>'f1_score')::numeric) as avg_f1_score,
    AVG((metrics->>'processing_time')::numeric) as avg_processing_time,
    AVG((metrics->>'user_satisfaction')::numeric) as avg_user_satisfaction,
    MIN(timestamp) as first_analysis,
    MAX(timestamp) as last_analysis
FROM ai_performance_metrics
GROUP BY model_version
ORDER BY last_analysis DESC;

-- 创建学习进度统计视图
CREATE OR REPLACE VIEW learning_progress_summary AS
SELECT 
    DATE(timestamp) as analysis_date,
    COUNT(*) as total_feedbacks,
    AVG(reviewed_score - original_score) as avg_score_improvement,
    COUNT(CASE WHEN reviewed_score > original_score THEN 1 END) as positive_feedbacks,
    COUNT(CASE WHEN reviewed_score < original_score THEN 1 END) as negative_feedbacks,
    COUNT(CASE WHEN reviewed_score = original_score THEN 1 END) as neutral_feedbacks
FROM ai_learning_records
GROUP BY DATE(timestamp)
ORDER BY analysis_date DESC;

-- 创建知识库统计视图
CREATE OR REPLACE VIEW knowledge_base_summary AS
SELECT 
    category,
    COUNT(*) as total_patterns,
    AVG(confidence) as avg_confidence,
    SUM(usage_count) as total_usage,
    AVG(success_rate) as avg_success_rate,
    COUNT(CASE WHEN confidence >= 0.8 THEN 1 END) as high_confidence_patterns,
    COUNT(CASE WHEN usage_count >= 10 THEN 1 END) as frequently_used_patterns
FROM ai_knowledge_base
GROUP BY category
ORDER BY total_patterns DESC;

-- 创建学习任务统计视图
CREATE OR REPLACE VIEW learning_tasks_summary AS
SELECT 
    type,
    status,
    priority,
    COUNT(*) as task_count,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_completion_time
FROM ai_learning_tasks
WHERE completed_at IS NOT NULL
GROUP BY type, status, priority
ORDER BY type, priority DESC;

-- 创建AI分析质量函数
CREATE OR REPLACE FUNCTION calculate_ai_analysis_quality(
    p_record_id UUID,
    p_time_window_hours INTEGER DEFAULT 24
)
RETURNS TABLE (
    quality_score NUMERIC,
    confidence_level TEXT,
    improvement_suggestions TEXT[]
) AS $$
DECLARE
    v_recent_feedback RECORD;
    v_pattern_matches INTEGER;
    v_knowledge_confidence NUMERIC;
BEGIN
    -- 获取最近的反馈
    SELECT 
        AVG(reviewed_score - original_score) as avg_improvement,
        COUNT(*) as feedback_count
    INTO v_recent_feedback
    FROM ai_learning_records
    WHERE record_id::text = p_record_id::text
    AND timestamp >= NOW() - INTERVAL '1 hour' * p_time_window_hours;

    -- 计算模式匹配度
    SELECT COUNT(*) INTO v_pattern_matches
    FROM ai_knowledge_base
    WHERE confidence >= 0.7
    AND usage_count >= 5;

    -- 计算知识库置信度
    SELECT AVG(confidence) INTO v_knowledge_confidence
    FROM ai_knowledge_base
    WHERE usage_count >= 1;

    -- 计算综合质量评分
    quality_score := COALESCE(
        (85 + COALESCE(v_recent_feedback.avg_improvement, 0) * 2 + 
         v_pattern_matches * 0.1 + 
         v_knowledge_confidence * 10), 
        75
    );

    -- 确定置信度级别
    confidence_level := CASE 
        WHEN quality_score >= 90 THEN 'HIGH'
        WHEN quality_score >= 75 THEN 'MEDIUM'
        ELSE 'LOW'
    END;

    -- 生成改进建议
    improvement_suggestions := ARRAY[
        '持续收集用户反馈以改进分析质量',
        '增加领域专家的知识输入',
        '优化算法参数以提高准确性'
    ];

    RETURN QUERY SELECT quality_score, confidence_level, improvement_suggestions;
END;
$$ LANGUAGE plpgsql;

-- 创建清理过期缓存的函数
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM context_analysis_cache 
    WHERE expiry_time < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 创建自动清理任务（需要pg_cron扩展）
-- SELECT cron.schedule('cleanup-expired-cache', '0 */6 * * *', 'SELECT cleanup_expired_cache();');

-- 创建RLS策略
ALTER TABLE ai_learning_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_knowledge_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_learning_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE multimodal_analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE context_analysis_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_history_analysis ENABLE ROW LEVEL SECURITY;

-- AI学习记录RLS策略
CREATE POLICY "用户可以查看自己医院的AI学习记录" ON ai_learning_records
    FOR SELECT USING (
        hospital_id IS NULL OR 
        hospital_id = (SELECT hospital_id FROM user_profiles WHERE user_id = auth.uid())
    );

CREATE POLICY "用户可以创建AI学习记录" ON ai_learning_records
    FOR INSERT WITH CHECK (
        reviewer_id = auth.uid()
    );

CREATE POLICY "用户可以更新自己创建的AI学习记录" ON ai_learning_records
    FOR UPDATE USING (
        reviewer_id = auth.uid()
    );

-- AI知识库RLS策略
CREATE POLICY "用户可以查看AI知识库" ON ai_knowledge_base
    FOR SELECT USING (
        hospital_id IS NULL OR 
        hospital_id = (SELECT hospital_id FROM user_profiles WHERE user_id = auth.uid())
    );

CREATE POLICY "管理员可以管理AI知识库" ON ai_knowledge_base
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE user_id = auth.uid() 
            AND role IN ('admin', 'qc_manager')
        )
    );

-- AI性能指标RLS策略
CREATE POLICY "用户可以查看AI性能指标" ON ai_performance_metrics
    FOR SELECT USING (
        hospital_id IS NULL OR 
        hospital_id = (SELECT hospital_id FROM user_profiles WHERE user_id = auth.uid())
    );

CREATE POLICY "系统可以插入AI性能指标" ON ai_performance_metrics
    FOR INSERT WITH CHECK (true);

-- AI学习任务RLS策略
CREATE POLICY "用户可以查看AI学习任务" ON ai_learning_tasks
    FOR SELECT USING (
        hospital_id IS NULL OR 
        hospital_id = (SELECT hospital_id FROM user_profiles WHERE user_id = auth.uid())
    );

CREATE POLICY "系统可以管理AI学习任务" ON ai_learning_tasks
    FOR ALL USING (true);

-- AI模型版本RLS策略
CREATE POLICY "用户可以查看AI模型版本" ON ai_model_versions
    FOR SELECT USING (
        hospital_id IS NULL OR 
        hospital_id = (SELECT hospital_id FROM user_profiles WHERE user_id = auth.uid())
    );

CREATE POLICY "管理员可以管理AI模型版本" ON ai_model_versions
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE user_id = auth.uid() 
            AND role = 'admin'
        )
    );

-- 多模态分析结果RLS策略
CREATE POLICY "用户可以查看多模态分析结果" ON multimodal_analysis_results
    FOR SELECT USING (
        hospital_id IS NULL OR 
        hospital_id = (SELECT hospital_id FROM user_profiles WHERE user_id = auth.uid())
    );

CREATE POLICY "系统可以创建多模态分析结果" ON multimodal_analysis_results
    FOR INSERT WITH CHECK (true);

-- 上下文分析缓存RLS策略
CREATE POLICY "用户可以访问上下文分析缓存" ON context_analysis_cache
    FOR ALL USING (
        hospital_id IS NULL OR 
        hospital_id = (SELECT hospital_id FROM user_profiles WHERE user_id = auth.uid())
    );

-- 患者历史分析RLS策略
CREATE POLICY "用户可以查看患者历史分析" ON patient_history_analysis
    FOR SELECT USING (
        hospital_id IS NULL OR 
        hospital_id = (SELECT hospital_id FROM user_profiles WHERE user_id = auth.uid())
    );

CREATE POLICY "系统可以管理患者历史分析" ON patient_history_analysis
    FOR ALL USING (true);

-- 插入初始数据
INSERT INTO ai_model_versions (version, improvements, performance_metrics, is_active) VALUES
('1.0.0', 
 '["基础AI分析功能", "规则引擎集成", "多模态分析支持"]'::jsonb,
 '{"accuracy": 0.88, "precision": 0.85, "recall": 0.82, "f1_score": 0.835, "processing_time": 3200, "user_satisfaction": 0.87, "improvement_rate": 0.05}'::jsonb,
 true)
ON CONFLICT (version) DO NOTHING;

-- 插入默认知识库条目
INSERT INTO ai_knowledge_base (category, pattern, confidence, usage_count, success_rate, metadata) VALUES
('completeness', '基本信息完整性检查', 0.95, 100, 0.92, '{"rule_type": "basic", "severity": "high"}'::jsonb),
('consistency', '诊断一致性验证', 0.90, 85, 0.88, '{"rule_type": "logical", "severity": "medium"}'::jsonb),
('rationality', '治疗合理性分析', 0.85, 70, 0.83, '{"rule_type": "clinical", "severity": "high"}'::jsonb),
('timeliness', '时效性检查', 0.80, 60, 0.78, '{"rule_type": "temporal", "severity": "medium"}'::jsonb),
('compliance', '合规性验证', 0.92, 90, 0.89, '{"rule_type": "regulatory", "severity": "critical"}'::jsonb)
ON CONFLICT DO NOTHING;

-- 创建通知函数
CREATE OR REPLACE FUNCTION notify_learning_progress()
RETURNS TRIGGER AS $$
BEGIN
    -- 当有新的学习记录时发送通知
    PERFORM pg_notify('learning_progress', 
        json_build_object(
            'record_id', NEW.record_id,
            'improvement', NEW.reviewed_score - NEW.original_score,
            'timestamp', NEW.timestamp
        )::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建学习进度通知触发器
CREATE TRIGGER notify_learning_progress_trigger
    AFTER INSERT ON ai_learning_records
    FOR EACH ROW EXECUTE FUNCTION notify_learning_progress();

-- 添加评论
COMMENT ON TABLE ai_learning_records IS 'AI学习记录表，存储用户反馈和纠正信息';
COMMENT ON TABLE ai_knowledge_base IS 'AI知识库表，存储学习到的模式和规则';
COMMENT ON TABLE ai_performance_metrics IS 'AI性能指标表，记录系统性能数据';
COMMENT ON TABLE ai_learning_tasks IS 'AI学习任务表，管理后台学习任务';
COMMENT ON TABLE ai_model_versions IS 'AI模型版本表，管理模型版本和发布';
COMMENT ON TABLE multimodal_analysis_results IS '多模态分析结果表，存储综合分析结果';
COMMENT ON TABLE context_analysis_cache IS '上下文分析缓存表，提高分析效率';
COMMENT ON TABLE patient_history_analysis IS '患者历史分析表，存储患者历史模式';

COMMENT ON FUNCTION calculate_ai_analysis_quality IS '计算AI分析质量评分';
COMMENT ON FUNCTION cleanup_expired_cache IS '清理过期缓存数据';
COMMENT ON FUNCTION notify_learning_progress IS '发送学习进度通知'; 