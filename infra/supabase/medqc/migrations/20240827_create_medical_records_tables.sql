-- 创建医疗记录相关表结构
-- 支持结构化和非结构化数据存储

-- 1. 医疗记录主表
CREATE TABLE medical_records (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_number VARCHAR(50) UNIQUE NOT NULL,
    record_name VARCHAR(200) NOT NULL,
    
    -- 患者基本信息
    patient_info JSONB NOT NULL DEFAULT '{}',
    
    -- 医疗信息
    department VARCHAR(100),
    primary_diagnosis TEXT,
    secondary_diagnosis JSONB DEFAULT '[]',
    major_surgery TEXT,
    
    -- 原始文本数据
    raw_text TEXT,
    
    -- AI解析结果
    ai_extraction_result JSONB DEFAULT '{}',
    ai_confidence_score DECIMAL(5,2) DEFAULT 0.0,
    
    -- 元数据
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    import_method VARCHAR(20) DEFAULT 'manual' CHECK (import_method IN ('manual', 'smart_import', 'batch_import')),
    
    -- 审计字段
    created_by UUID REFERENCES auth.users(id),
    last_modified_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 医疗文书表
CREATE TABLE medical_documents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
    
    -- 文书基本信息
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN (
        'admission_record', 'admission_record_24h_in', 'admission_record_24h_out',
        'first_progress_note', 'daily_progress_note', 'attending_first_progress',
        'attending_progress', 'consultation_record', 'handover_record', 'stage_summary',
        'operation_record', 'preoperative_summary',
        'discharge_record', 'death_record', 'death_case_discussion',
        'imaging_report', 'lab_report', 'other_examination',
        'surgery_consent', 'anesthesia_consent', 'blood_transfusion_consent',
        'special_treatment_consent', 'critical_illness_notice'
    )),
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    
    -- AI解析相关
    ai_classified BOOLEAN DEFAULT FALSE,
    ai_confidence_score DECIMAL(5,2) DEFAULT 0.0,
    ai_extraction_metadata JSONB DEFAULT '{}',
    
    -- 文书元数据
    document_metadata JSONB DEFAULT '{}',
    
    -- 排序和状态
    sort_order INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    
    -- 审计字段
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. AI解析历史表
CREATE TABLE ai_parsing_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
    
    -- 解析输入
    input_text TEXT NOT NULL,
    input_method VARCHAR(20) NOT NULL CHECK (input_method IN ('paste', 'upload', 'batch')),
    
    -- 解析结果
    extraction_result JSONB NOT NULL,
    confidence_scores JSONB DEFAULT '{}',
    processing_time_ms INTEGER,
    tokens_used INTEGER,
    
    -- 模型信息
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    api_endpoint VARCHAR(200),
    
    -- 用户反馈
    user_corrections JSONB DEFAULT '{}',
    user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 5),
    user_feedback TEXT,
    
    -- 审计字段
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. 质控点关联表
CREATE TABLE medical_record_quality_points (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
    quality_point_id UUID, -- 关联到质控规则表
    
    -- 关联信息
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    applied_by UUID REFERENCES auth.users(id),
    
    -- 质控结果
    check_result JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'passed', 'failed', 'ignored')),
    
    UNIQUE(record_id, quality_point_id)
);

-- 5. 文件上传记录表
CREATE TABLE file_upload_records (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_id UUID REFERENCES medical_records(id) ON DELETE CASCADE,
    
    -- 文件信息
    original_filename VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    file_type VARCHAR(100) NOT NULL,
    file_path VARCHAR(500),
    
    -- 处理状态
    processing_status VARCHAR(20) DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
    processing_result JSONB DEFAULT '{}',
    error_message TEXT,
    
    -- 审计字段
    uploaded_by UUID REFERENCES auth.users(id),
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引优化查询性能
CREATE INDEX idx_medical_records_record_number ON medical_records(record_number);
CREATE INDEX idx_medical_records_department ON medical_records(department);
CREATE INDEX idx_medical_records_status ON medical_records(status);
CREATE INDEX idx_medical_records_created_at ON medical_records(created_at);
CREATE INDEX idx_medical_records_patient_info ON medical_records USING GIN(patient_info);
CREATE INDEX idx_medical_records_ai_result ON medical_records USING GIN(ai_extraction_result);

CREATE INDEX idx_medical_documents_record_id ON medical_documents(record_id);
CREATE INDEX idx_medical_documents_type ON medical_documents(document_type);
CREATE INDEX idx_medical_documents_metadata ON medical_documents USING GIN(document_metadata);

CREATE INDEX idx_ai_parsing_history_record_id ON ai_parsing_history(record_id);
CREATE INDEX idx_ai_parsing_history_created_at ON ai_parsing_history(created_at);
CREATE INDEX idx_ai_parsing_history_result ON ai_parsing_history USING GIN(extraction_result);

CREATE INDEX idx_quality_points_record_id ON medical_record_quality_points(record_id);
CREATE INDEX idx_quality_points_status ON medical_record_quality_points(status);

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

CREATE TRIGGER update_medical_documents_updated_at 
    BEFORE UPDATE ON medical_documents 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 创建RLS (Row Level Security) 策略
ALTER TABLE medical_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE medical_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_parsing_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE medical_record_quality_points ENABLE ROW LEVEL SECURITY;
ALTER TABLE file_upload_records ENABLE ROW LEVEL SECURITY;

-- 基本的RLS策略 (可根据具体权限需求调整)
CREATE POLICY "Users can view their own medical records" ON medical_records
    FOR SELECT USING (auth.uid() = created_by OR auth.uid() = last_modified_by);

CREATE POLICY "Users can insert medical records" ON medical_records
    FOR INSERT WITH CHECK (auth.uid() = created_by);

CREATE POLICY "Users can update their own medical records" ON medical_records
    FOR UPDATE USING (auth.uid() = created_by OR auth.uid() = last_modified_by);

-- 为文书表创建类似的策略
CREATE POLICY "Users can view medical documents" ON medical_documents
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM medical_records 
            WHERE id = medical_documents.record_id 
            AND (created_by = auth.uid() OR last_modified_by = auth.uid())
        )
    );

CREATE POLICY "Users can insert medical documents" ON medical_documents
    FOR INSERT WITH CHECK (auth.uid() = created_by);

CREATE POLICY "Users can update medical documents" ON medical_documents
    FOR UPDATE USING (auth.uid() = created_by);

-- 创建视图简化查询
CREATE VIEW medical_records_with_documents AS
SELECT 
    mr.*,
    COALESCE(
        json_agg(
            json_build_object(
                'id', md.id,
                'document_type', md.document_type,
                'title', md.title,
                'content', md.content,
                'ai_classified', md.ai_classified,
                'ai_confidence_score', md.ai_confidence_score,
                'sort_order', md.sort_order,
                'created_at', md.created_at
            ) ORDER BY md.sort_order, md.created_at
        ) FILTER (WHERE md.id IS NOT NULL),
        '[]'::json
    ) as documents
FROM medical_records mr
LEFT JOIN medical_documents md ON mr.id = md.record_id AND md.status = 'active'
GROUP BY mr.id;

-- 创建统计视图
CREATE VIEW medical_records_stats AS
SELECT 
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE created_at >= date_trunc('month', CURRENT_DATE)) as monthly_new,
    COUNT(*) FILTER (WHERE status = 'draft') as pending_review,
    COUNT(*) FILTER (WHERE import_method = 'smart_import') as smart_imported,
    COUNT(*) FILTER (WHERE ai_confidence_score > 0) as ai_processed,
    AVG(ai_confidence_score) FILTER (WHERE ai_confidence_score > 0) as avg_confidence
FROM medical_records
WHERE status != 'archived';

-- 插入示例数据 (可选)
INSERT INTO medical_records (
    record_number, 
    record_name, 
    patient_info, 
    department, 
    primary_diagnosis, 
    major_surgery,
    raw_text,
    ai_extraction_result,
    ai_confidence_score,
    import_method,
    created_by
) VALUES 
(
    'MR20240827001',
    '张三病历',
    '{"name": "张三", "age": 65, "gender": "男", "id_number": "***************"}',
    '内科',
    '高血压病',
    '无',
    '患者张三，男，65岁，因"头晕、头痛3天"入院...',
    '{"extraction_time": "2024-08-27T10:30:00Z", "model_used": "medical-llm-v1", "fields_extracted": ["patient_name", "age", "gender", "department", "diagnosis"]}',
    89.5,
    'smart_import',
    (SELECT id FROM auth.users LIMIT 1)
);

-- 添加注释
COMMENT ON TABLE medical_records IS '医疗记录主表，存储病历的基本信息和AI解析结果';
COMMENT ON TABLE medical_documents IS '医疗文书表，存储各类医疗文档内容';
COMMENT ON TABLE ai_parsing_history IS 'AI解析历史记录，用于追踪和改进AI性能';
COMMENT ON TABLE medical_record_quality_points IS '医疗记录与质控点的关联表';
COMMENT ON TABLE file_upload_records IS '文件上传记录表，追踪文件处理状态';

COMMENT ON COLUMN medical_records.patient_info IS '患者信息JSONB字段，存储姓名、年龄、性别等';
COMMENT ON COLUMN medical_records.ai_extraction_result IS 'AI解析结果JSONB字段，存储完整的解析输出';
COMMENT ON COLUMN medical_records.raw_text IS '原始病历文本，用于重新解析和审计';
COMMENT ON COLUMN medical_documents.ai_extraction_metadata IS 'AI解析元数据，存储置信度、关键词等';
