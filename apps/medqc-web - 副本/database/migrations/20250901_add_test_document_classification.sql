-- =============================================
-- 测试环境医疗文书分类体系数据库迁移
-- 版本: 1.0.0
-- 创建时间: 2025-09-01
-- 描述: 为测试环境添加层级化的医疗文书分类支持
-- 基于 medical_records_test 表
-- =============================================

-- 1. 创建文书分类表（一级目录）- 测试版
CREATE TABLE IF NOT EXISTS document_categories_test (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_code VARCHAR(50) UNIQUE NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. 创建文书类型表（二级目录）- 测试版
CREATE TABLE IF NOT EXISTS document_types_test (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID NOT NULL REFERENCES document_categories_test(id) ON DELETE CASCADE,
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

-- 3. 创建文书实例表（具体的文书记录）- 测试版
CREATE TABLE IF NOT EXISTS medical_documents_test (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID NOT NULL REFERENCES medical_records_test(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES document_categories_test(id),
    type_id UUID NOT NULL REFERENCES document_types_test(id),
    
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
    CONSTRAINT unique_test_record_document UNIQUE (record_id, type_id, title)
);

-- 4. 调整现有的 medical_records_test 表，添加文书分类支持
-- 检查列是否存在，如果不存在则添加
DO $$ 
BEGIN
    -- 添加文书分类统计字段
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'medical_records_test' 
                   AND column_name = 'document_count') THEN
        ALTER TABLE medical_records_test ADD COLUMN document_count INTEGER DEFAULT 0;
    END IF;
    
    -- 添加分类完成状态
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'medical_records_test' 
                   AND column_name = 'classification_status') THEN
        ALTER TABLE medical_records_test ADD COLUMN classification_status VARCHAR(20) DEFAULT 'pending' 
            CHECK (classification_status IN ('pending', 'processing', 'completed', 'failed'));
    END IF;
    
    -- 添加分类置信度
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'medical_records_test' 
                   AND column_name = 'classification_confidence') THEN
        ALTER TABLE medical_records_test ADD COLUMN classification_confidence DECIMAL(3,2) DEFAULT 0.0;
    END IF;
    
    -- 添加最后分类时间
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'medical_records_test' 
                   AND column_name = 'last_classified_at') THEN
        ALTER TABLE medical_records_test ADD COLUMN last_classified_at TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- 5. 插入一级分类数据
INSERT INTO document_categories_test (category_code, category_name, description, sort_order) VALUES
('admission_record', '入院记录', '患者入院时的基本信息和病情记录', 1),
('progress_note', '病程记录', '患者住院期间的病情变化和治疗过程记录', 2),
('operation_record', '手术记录', '手术相关的各类记录文书', 3),
('nursing_document', '护理文书', '护理相关的记录和评估文书', 4),
('discharge_record', '出院记录', '患者出院时的总结和后续指导', 5),
('examination_report', '检查报告', '各类检查和化验报告', 6),
('medical_order', '医嘱记录', '医生开具的各类医嘱记录', 7)
ON CONFLICT (category_code) DO NOTHING;

-- 6. 插入二级分类数据
-- 入院记录类
INSERT INTO document_types_test (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories_test WHERE category_code = 'admission_record'), 'admission_record', '入院记录', '标准入院记录', 1),
((SELECT id FROM document_categories_test WHERE category_code = 'admission_record'), 'admission_diagnosis', '入院诊断', '入院时的初步诊断', 2)
ON CONFLICT (type_code) DO NOTHING;

-- 病程记录类
INSERT INTO document_types_test (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories_test WHERE category_code = 'progress_note'), 'first_progress_note', '首次病程记录', '入院后首次病程记录', 1),
((SELECT id FROM document_categories_test WHERE category_code = 'progress_note'), 'daily_progress_note', '日常病程记录', '日常病程变化记录', 2),
((SELECT id FROM document_categories_test WHERE category_code = 'progress_note'), 'attending_progress', '上级医师查房记录', '主治医师查房记录', 3),
((SELECT id FROM document_categories_test WHERE category_code = 'progress_note'), 'consultation_record', '疑难病例讨论记录', '多学科讨论记录', 4),
((SELECT id FROM document_categories_test WHERE category_code = 'progress_note'), 'handover_record', '交接班记录', '医师交接班记录', 5),
((SELECT id FROM document_categories_test WHERE category_code = 'progress_note'), 'transfer_record', '转科记录', '科室间转移记录', 6),
((SELECT id FROM document_categories_test WHERE category_code = 'progress_note'), 'stage_summary', '阶段小结', '治疗阶段总结', 7)
ON CONFLICT (type_code) DO NOTHING;

-- 手术记录类
INSERT INTO document_types_test (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories_test WHERE category_code = 'operation_record'), 'preoperative_summary', '术前小结', '手术前病情总结', 1),
((SELECT id FROM document_categories_test WHERE category_code = 'operation_record'), 'preoperative_discussion', '术前讨论', '术前多学科讨论', 2),
((SELECT id FROM document_categories_test WHERE category_code = 'operation_record'), 'operation_record', '手术记录', '手术过程详细记录', 3),
((SELECT id FROM document_categories_test WHERE category_code = 'operation_record'), 'postoperative_first_note', '术后首次病程记录', '术后首次病程', 4),
((SELECT id FROM document_categories_test WHERE category_code = 'operation_record'), 'anesthesia_record', '麻醉记录', '麻醉过程记录', 5)
ON CONFLICT (type_code) DO NOTHING;

-- 护理文书类
INSERT INTO document_types_test (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories_test WHERE category_code = 'nursing_document'), 'nursing_record', '护理记录单', '日常护理记录', 1),
((SELECT id FROM document_categories_test WHERE category_code = 'nursing_document'), 'temperature_chart', '体温单', '体温监测记录', 2),
((SELECT id FROM document_categories_test WHERE category_code = 'nursing_document'), 'nursing_plan', '护理计划单', '护理计划制定', 3),
((SELECT id FROM document_categories_test WHERE category_code = 'nursing_document'), 'nursing_assessment', '护理评估单', '护理评估记录', 4)
ON CONFLICT (type_code) DO NOTHING;

-- 出院记录类
INSERT INTO document_types_test (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories_test WHERE category_code = 'discharge_record'), 'discharge_record', '出院记录', '出院总结记录', 1),
((SELECT id FROM document_categories_test WHERE category_code = 'discharge_record'), 'discharge_summary', '出院小结', '出院情况小结', 2),
((SELECT id FROM document_categories_test WHERE category_code = 'discharge_record'), 'death_record', '死亡记录', '患者死亡记录', 3)
ON CONFLICT (type_code) DO NOTHING;

-- 检查报告类
INSERT INTO document_types_test (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories_test WHERE category_code = 'examination_report'), 'imaging_examination', '影像学检查', 'CT、MRI等影像检查', 1),
((SELECT id FROM document_categories_test WHERE category_code = 'examination_report'), 'laboratory_test', '实验室检查', '血液、尿液等化验检查', 2),
((SELECT id FROM document_categories_test WHERE category_code = 'examination_report'), 'pathology_examination', '病理检查', '病理切片检查', 3),
((SELECT id FROM document_categories_test WHERE category_code = 'examination_report'), 'special_examination', '特殊检查', '心电图、超声等特殊检查', 4)
ON CONFLICT (type_code) DO NOTHING;

-- 医嘱记录类
INSERT INTO document_types_test (category_id, type_code, type_name, description, sort_order) VALUES
((SELECT id FROM document_categories_test WHERE category_code = 'medical_order'), 'long_term_order', '长期医嘱', '长期执行的医嘱', 1),
((SELECT id FROM document_categories_test WHERE category_code = 'medical_order'), 'temporary_order', '临时医嘱', '临时性医嘱', 2),
((SELECT id FROM document_categories_test WHERE category_code = 'medical_order'), 'order_execution', '医嘱执行记录', '医嘱执行情况记录', 3)
ON CONFLICT (type_code) DO NOTHING;

-- 7. 创建索引
CREATE INDEX IF NOT EXISTS idx_medical_documents_test_record_id ON medical_documents_test(record_id);
CREATE INDEX IF NOT EXISTS idx_medical_documents_test_category_id ON medical_documents_test(category_id);
CREATE INDEX IF NOT EXISTS idx_medical_documents_test_type_id ON medical_documents_test(type_id);
CREATE INDEX IF NOT EXISTS idx_medical_documents_test_status ON medical_documents_test(status);
CREATE INDEX IF NOT EXISTS idx_medical_documents_test_qc_status ON medical_documents_test(qc_status);
CREATE INDEX IF NOT EXISTS idx_document_types_test_category_id ON document_types_test(category_id);

-- 8. 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_document_categories_test_updated_at BEFORE UPDATE ON document_categories_test FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_document_types_test_updated_at BEFORE UPDATE ON document_types_test FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_medical_documents_test_updated_at BEFORE UPDATE ON medical_documents_test FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 9. 创建视图，方便查询文书分类统计
CREATE OR REPLACE VIEW document_classification_stats_test AS
SELECT 
    dc.category_name,
    dt.type_name,
    COUNT(md.id) as document_count,
    AVG(md.classification_confidence) as avg_confidence,
    COUNT(CASE WHEN md.manual_verified THEN 1 END) as verified_count,
    COUNT(CASE WHEN md.qc_status = 'passed' THEN 1 END) as qc_passed_count
FROM document_categories_test dc
LEFT JOIN document_types_test dt ON dc.id = dt.category_id
LEFT JOIN medical_documents_test md ON dt.id = md.type_id
GROUP BY dc.category_name, dt.type_name, dc.sort_order, dt.sort_order
ORDER BY dc.sort_order, dt.sort_order;

-- 10. 创建函数，用于更新病历的文书统计
CREATE OR REPLACE FUNCTION update_medical_record_test_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- 更新文书数量
    UPDATE medical_records_test 
    SET 
        document_count = (
            SELECT COUNT(*) 
            FROM medical_documents_test 
            WHERE record_id = COALESCE(NEW.record_id, OLD.record_id)
        ),
        classification_confidence = (
            SELECT AVG(classification_confidence) 
            FROM medical_documents_test 
            WHERE record_id = COALESCE(NEW.record_id, OLD.record_id)
        ),
        last_classified_at = NOW()
    WHERE id = COALESCE(NEW.record_id, OLD.record_id);
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- 创建触发器
CREATE TRIGGER update_medical_record_test_stats_trigger
    AFTER INSERT OR UPDATE OR DELETE ON medical_documents_test
    FOR EACH ROW EXECUTE FUNCTION update_medical_record_test_stats();
