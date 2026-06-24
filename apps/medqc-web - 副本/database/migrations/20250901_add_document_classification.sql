-- =============================================
-- 医疗文书分类体系数据库迁移
-- 版本: 1.0.0
-- 创建时间: 2025-09-01
-- 描述: 添加层级化的医疗文书分类支持
-- =============================================

-- 1. 创建文书分类表（一级目录）
CREATE TABLE IF NOT EXISTS document_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_code VARCHAR(50) UNIQUE NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 创建文书类型表（二级目录）
CREATE TABLE IF NOT EXISTS document_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID NOT NULL REFERENCES document_categories(id) ON DELETE CASCADE,
    type_code VARCHAR(50) UNIQUE NOT NULL,
    type_name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    -- 质控相关配置
    qc_template_id UUID, -- 关联专门的质控模板
    required_sections JSONB DEFAULT '[]', -- 必需的章节
    validation_rules JSONB DEFAULT '{}', -- 验证规则
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. 创建文书实例表（具体的文书记录）
CREATE TABLE IF NOT EXISTS medical_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES medical_records(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES document_categories(id),
    type_id UUID NOT NULL REFERENCES document_types(id),
    
    -- 文书基本信息
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT, -- AI生成的摘要
    
    -- 分类信息
    ai_classified BOOLEAN DEFAULT false, -- 是否AI自动分类
    classification_confidence DECIMAL(3,2) DEFAULT 0.0, -- 分类置信度
    manual_verified BOOLEAN DEFAULT false, -- 是否人工验证
    
    -- 位置信息（在原始病历中的位置）
    position_info JSONB DEFAULT '{}', -- 存储位置标记信息
    sort_order INTEGER DEFAULT 0,
    
    -- 状态信息
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    
    -- 质控相关
    qc_status VARCHAR(20) DEFAULT 'pending' CHECK (qc_status IN ('pending', 'passed', 'failed', 'reviewing')),
    qc_score DECIMAL(5,2),
    qc_issues JSONB DEFAULT '[]',
    
    -- 元数据
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- 索引
    CONSTRAINT unique_record_document UNIQUE (record_id, type_id, title)
);

-- 4. 插入一级分类数据
INSERT INTO document_categories (category_code, category_name, description, sort_order) VALUES
('admission_record', '入院记录', '患者入院时的基本信息和病情记录', 1),
('progress_note', '病程记录', '患者住院期间的病情变化和治疗过程记录', 2),
('operation_record', '手术记录', '手术相关的各类记录文书', 3),
('nursing_document', '护理文书', '护理相关的记录和评估文书', 4),
('discharge_record', '出院记录', '患者出院时的总结和后续指导', 5),
('examination_report', '检查报告', '各类检查和化验报告', 6),
('medical_order', '医嘱记录', '医生开具的各类医嘱记录', 7);

-- 5. 插入二级分类数据
-- 入院记录类
INSERT INTO document_types (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories WHERE category_code = 'admission_record'), 'admission_record', '入院记录', '标准入院记录', 1),
((SELECT id FROM document_categories WHERE category_code = 'admission_record'), 'admission_diagnosis', '入院诊断', '入院时的初步诊断', 2);

-- 病程记录类
INSERT INTO document_types (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories WHERE category_code = 'progress_note'), 'first_progress_note', '首次病程记录', '入院后首次病程记录', 1),
((SELECT id FROM document_categories WHERE category_code = 'progress_note'), 'daily_progress_note', '日常病程记录', '日常病程变化记录', 2),
((SELECT id FROM document_categories WHERE category_code = 'progress_note'), 'attending_progress', '上级医师查房记录', '主治医师查房记录', 3),
((SELECT id FROM document_categories WHERE category_code = 'progress_note'), 'consultation_record', '疑难病例讨论记录', '多学科讨论记录', 4),
((SELECT id FROM document_categories WHERE category_code = 'progress_note'), 'handover_record', '交接班记录', '医师交接班记录', 5),
((SELECT id FROM document_categories WHERE category_code = 'progress_note'), 'transfer_record', '转科记录', '科室间转移记录', 6),
((SELECT id FROM document_categories WHERE category_code = 'progress_note'), 'stage_summary', '阶段小结', '治疗阶段总结', 7);

-- 手术记录类
INSERT INTO document_types (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories WHERE category_code = 'operation_record'), 'preoperative_summary', '术前小结', '手术前病情总结', 1),
((SELECT id FROM document_categories WHERE category_code = 'operation_record'), 'preoperative_discussion', '术前讨论', '术前多学科讨论', 2),
((SELECT id FROM document_categories WHERE category_code = 'operation_record'), 'operation_record', '手术记录', '手术过程详细记录', 3),
((SELECT id FROM document_categories WHERE category_code = 'operation_record'), 'postoperative_first_note', '术后首次病程记录', '术后首次病程', 4),
((SELECT id FROM document_categories WHERE category_code = 'operation_record'), 'anesthesia_record', '麻醉记录', '麻醉过程记录', 5);

-- 护理文书类
INSERT INTO document_types (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories WHERE category_code = 'nursing_document'), 'nursing_record', '护理记录单', '日常护理记录', 1),
((SELECT id FROM document_categories WHERE category_code = 'nursing_document'), 'temperature_chart', '体温单', '体温监测记录', 2),
((SELECT id FROM document_categories WHERE category_code = 'nursing_document'), 'nursing_plan', '护理计划单', '护理计划制定', 3),
((SELECT id FROM document_categories WHERE category_code = 'nursing_document'), 'nursing_assessment', '护理评估单', '护理评估记录', 4);

-- 出院记录类
INSERT INTO document_types (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories WHERE category_code = 'discharge_record'), 'discharge_record', '出院记录', '出院总结记录', 1),
((SELECT id FROM document_categories WHERE category_code = 'discharge_record'), 'discharge_summary', '出院小结', '出院情况小结', 2),
((SELECT id FROM document_categories WHERE category_code = 'discharge_record'), 'death_record', '死亡记录', '患者死亡记录', 3);

-- 检查报告类
INSERT INTO document_types (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories WHERE category_code = 'examination_report'), 'imaging_examination', '影像学检查', 'CT、MRI等影像检查', 1),
((SELECT id FROM document_categories WHERE category_code = 'examination_report'), 'laboratory_test', '实验室检查', '血液、尿液等化验检查', 2),
((SELECT id FROM document_categories WHERE category_code = 'examination_report'), 'pathology_examination', '病理检查', '病理切片检查', 3),
((SELECT id FROM document_categories WHERE category_code = 'examination_report'), 'special_examination', '特殊检查', '心电图、超声等特殊检查', 4);

-- 医嘱记录类
INSERT INTO document_types (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories WHERE category_code = 'medical_order'), 'long_term_order', '长期医嘱', '长期执行的医嘱', 1),
((SELECT id FROM document_categories WHERE category_code = 'medical_order'), 'temporary_order', '临时医嘱', '临时性医嘱', 2),
((SELECT id FROM document_categories WHERE category_code = 'medical_order'), 'order_execution', '医嘱执行记录', '医嘱执行情况记录', 3);

-- 6. 创建索引
CREATE INDEX idx_medical_documents_record_id ON medical_documents(record_id);
CREATE INDEX idx_medical_documents_category_id ON medical_documents(category_id);
CREATE INDEX idx_medical_documents_type_id ON medical_documents(type_id);
CREATE INDEX idx_medical_documents_status ON medical_documents(status);
CREATE INDEX idx_medical_documents_qc_status ON medical_documents(qc_status);
CREATE INDEX idx_document_types_category_id ON document_types(category_id);

-- 7. 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_document_categories_updated_at BEFORE UPDATE ON document_categories FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_document_types_updated_at BEFORE UPDATE ON document_types FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_medical_documents_updated_at BEFORE UPDATE ON medical_documents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
