-- 添加非结构化数据支持
-- 用于存储复制粘贴的原始病历文本

-- 非结构化医疗文档表
CREATE TABLE IF NOT EXISTS unstructured_medical_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基本信息
    title VARCHAR(255) NOT NULL DEFAULT '未命名文档',
    document_type VARCHAR(50) DEFAULT 'raw_text' CHECK (document_type IN ('raw_text', 'copied_record', 'uploaded_file', 'scanned_document')),
    
    -- 原始内容
    raw_content TEXT NOT NULL,
    content_length INTEGER GENERATED ALWAYS AS (length(raw_content)) STORED,
    
    -- 元数据
    source VARCHAR(100) DEFAULT 'manual_input' CHECK (source IN ('manual_input', 'copy_paste', 'file_upload', 'api_import')),
    original_filename VARCHAR(255),
    mime_type VARCHAR(100),
    file_size INTEGER,
    
    -- 处理状态
    processing_status VARCHAR(50) DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),
    structured_record_id UUID REFERENCES medical_records(id) ON DELETE SET NULL,
    
    -- 提取的结构化信息（JSON格式）
    extracted_data JSONB DEFAULT '{}',
    extraction_confidence DECIMAL(3,2) CHECK (extraction_confidence >= 0 AND extraction_confidence <= 1),
    
    -- 质控分析
    qc_analysis_id UUID REFERENCES qc_analysis_results(id) ON DELETE SET NULL,
    qc_status VARCHAR(50) DEFAULT 'not_analyzed' CHECK (qc_status IN ('not_analyzed', 'analyzing', 'completed', 'failed')),
    
    -- 标签和分类
    tags TEXT[] DEFAULT '{}',
    category VARCHAR(100),
    priority_level INTEGER DEFAULT 1 CHECK (priority_level >= 1 AND priority_level <= 5),
    
    -- 用户和权限
    created_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- 软删除
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    deleted_by UUID REFERENCES user_profiles(id) ON DELETE SET NULL
);

-- 创建索引
CREATE INDEX idx_unstructured_docs_created_by ON unstructured_medical_documents(created_by);
CREATE INDEX idx_unstructured_docs_department ON unstructured_medical_documents(department_id);
CREATE INDEX idx_unstructured_docs_status ON unstructured_medical_documents(processing_status);
CREATE INDEX idx_unstructured_docs_qc_status ON unstructured_medical_documents(qc_status);
CREATE INDEX idx_unstructured_docs_created_at ON unstructured_medical_documents(created_at DESC);
CREATE INDEX idx_unstructured_docs_type ON unstructured_medical_documents(document_type);
CREATE INDEX idx_unstructured_docs_source ON unstructured_medical_documents(source);

-- 全文搜索索引
CREATE INDEX idx_unstructured_docs_content_search ON unstructured_medical_documents USING gin(to_tsvector('chinese', raw_content));

-- GIN索引用于JSONB查询
CREATE INDEX idx_unstructured_docs_extracted_data ON unstructured_medical_documents USING gin(extracted_data);
CREATE INDEX idx_unstructured_docs_tags ON unstructured_medical_documents USING gin(tags);

-- 更新时间戳触发器
CREATE OR REPLACE FUNCTION update_unstructured_docs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_unstructured_docs_updated_at
    BEFORE UPDATE ON unstructured_medical_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_unstructured_docs_updated_at();

-- RLS策略
ALTER TABLE unstructured_medical_documents ENABLE ROW LEVEL SECURITY;

-- 用户只能访问自己创建的文档或同部门的文档
CREATE POLICY "用户可以查看自己创建的非结构化文档" ON unstructured_medical_documents
    FOR SELECT USING (
        created_by = auth.uid() OR
        department_id IN (
            SELECT department_id FROM user_profiles WHERE user_id = auth.uid()
        )
    );

-- 用户可以创建非结构化文档
CREATE POLICY "用户可以创建非结构化文档" ON unstructured_medical_documents
    FOR INSERT WITH CHECK (created_by = auth.uid());

-- 用户可以更新自己创建的文档
CREATE POLICY "用户可以更新自己创建的非结构化文档" ON unstructured_medical_documents
    FOR UPDATE USING (created_by = auth.uid());

-- 用户可以软删除自己创建的文档
CREATE POLICY "用户可以删除自己创建的非结构化文档" ON unstructured_medical_documents
    FOR UPDATE USING (created_by = auth.uid());

-- 文档处理日志表（可选，用于跟踪处理过程）
CREATE TABLE IF NOT EXISTS document_processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES unstructured_medical_documents(id) ON DELETE CASCADE,
    
    processing_step VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('started', 'completed', 'failed', 'skipped')),
    
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    
    processing_time_ms INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_processing_logs_document_id ON document_processing_logs(document_id);
CREATE INDEX idx_processing_logs_created_at ON document_processing_logs(created_at DESC);

-- 插入一些示例数据
INSERT INTO unstructured_medical_documents (
    title, 
    document_type, 
    raw_content, 
    source,
    tags,
    category,
    created_by,
    department_id
) VALUES 
(
    '示例病历文档1',
    'raw_text',
    '患者张某，男，45岁，主诉：胸痛3天。现病史：患者3天前无明显诱因出现胸痛，呈压榨性，持续性，伴有气短、出汗。既往史：高血压病史5年，规律服药。体格检查：血压150/90mmHg，心率85次/分，心律齐，双肺呼吸音清晰。辅助检查：心电图示：ST段压低。血常规：白细胞计数正常。诊断：1.冠心病 2.高血压病。治疗方案：给予抗血小板聚集、调脂、扩冠等治疗。',
    'manual_input',
    ARRAY['示例', '心血管', '内科'],
    '心血管内科',
    (SELECT id FROM user_profiles WHERE email = 'admin@medqc.com' LIMIT 1),
    (SELECT id FROM departments WHERE name = '心血管内科' LIMIT 1)
),
(
    '示例病历文档2', 
    'copied_record',
    '患者李某，女，32岁，孕38周。主诉：规律宫缩6小时。现病史：患者孕38周，今晨开始出现规律宫缩，间隔5-6分钟，持续30-40秒，伴有少量阴道流血。既往史：既往月经规律，末次月经2023年1月15日，预产期2023年10月22日。产检过程顺利，无异常。体格检查：宫高36cm，腹围98cm，胎心率140次/分，胎位LOA，宫口开大3cm。辅助检查：B超示：单胎头位，胎盘位置正常，羊水量正常。诊断：1.妊娠38周 2.临产。处理：入产房待产，密切监测产程进展。',
    'copy_paste',
    ARRAY['示例', '产科', '妊娠'],
    '妇产科',
    (SELECT id FROM user_profiles WHERE email = 'doctor@medqc.com' LIMIT 1),
    (SELECT id FROM departments WHERE name = '妇产科' LIMIT 1)
);

-- 添加注释
COMMENT ON TABLE unstructured_medical_documents IS '非结构化医疗文档表，用于存储原始病历文本';
COMMENT ON COLUMN unstructured_medical_documents.raw_content IS '原始文档内容，支持大文本存储';
COMMENT ON COLUMN unstructured_medical_documents.extracted_data IS '从原始内容中提取的结构化数据，JSON格式';
COMMENT ON COLUMN unstructured_medical_documents.processing_status IS '文档处理状态：pending-待处理，processing-处理中，completed-已完成，failed-失败';
COMMENT ON COLUMN unstructured_medical_documents.qc_status IS '质控分析状态';
COMMENT ON COLUMN unstructured_medical_documents.tags IS '文档标签数组，用于分类和搜索';

COMMENT ON TABLE document_processing_logs IS '文档处理日志表，记录处理过程的详细信息';
