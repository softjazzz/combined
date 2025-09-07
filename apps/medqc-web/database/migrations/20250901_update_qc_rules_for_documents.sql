-- =============================================
-- 质控规则表调整以支持文书分类
-- 版本: 1.0.0
-- 创建时间: 2025-09-01
-- 描述: 调整质控规则表以支持不同文书类型的专门质控
-- =============================================

-- 1. 为qc_rules表添加文书类型相关字段
ALTER TABLE qc_rules ADD COLUMN IF NOT EXISTS applicable_categories UUID[] DEFAULT '{}';
ALTER TABLE qc_rules ADD COLUMN IF NOT EXISTS applicable_document_types UUID[] DEFAULT '{}';
ALTER TABLE qc_rules ADD COLUMN IF NOT EXISTS document_specific_config JSONB DEFAULT '{}';

-- 2. 创建质控模板表（针对不同文书类型的质控模板）
CREATE TABLE IF NOT EXISTS qc_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_name VARCHAR(200) NOT NULL,
    template_code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    
    -- 适用范围
    applicable_categories UUID[] DEFAULT '{}', -- 适用的文书分类
    applicable_document_types UUID[] DEFAULT '{}', -- 适用的文书类型
    
    -- 模板配置
    template_config JSONB NOT NULL DEFAULT '{}', -- 模板配置信息
    prompt_template TEXT, -- LLM提示词模板
    scoring_rules JSONB DEFAULT '{}', -- 评分规则
    
    -- 状态
    is_active BOOLEAN DEFAULT true,
    version VARCHAR(20) DEFAULT '1.0',
    
    -- 元数据
    created_by UUID REFERENCES user_profiles(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. 更新qc_results表以支持文书级别的质控
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS document_id UUID REFERENCES medical_documents(id) ON DELETE CASCADE;
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS template_id UUID REFERENCES qc_templates(id);
ALTER TABLE qc_results ADD COLUMN IF NOT EXISTS document_type_id UUID REFERENCES document_types(id);

-- 4. 创建文书质控结果表（更详细的文书级质控结果）
CREATE TABLE IF NOT EXISTS document_qc_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES medical_documents(id) ON DELETE CASCADE,
    template_id UUID REFERENCES qc_templates(id),
    rule_id UUID REFERENCES qc_rules(id),
    
    -- 质控结果
    result_status VARCHAR(20) NOT NULL CHECK (result_status IN ('passed', 'failed', 'warning', 'error')),
    score DECIMAL(5,2) DEFAULT 0,
    max_score DECIMAL(5,2) DEFAULT 100,
    confidence_score DECIMAL(3,2) CHECK (confidence_score BETWEEN 0 AND 1),
    
    -- 问题详情
    issue_category VARCHAR(50), -- 问题分类
    issue_description TEXT,
    evidence_text TEXT,
    evidence_location JSONB, -- 问题位置信息
    suggestions TEXT[],
    
    -- AI分析信息
    ai_reasoning TEXT,
    ai_model_used VARCHAR(100),
    analysis_time_ms INTEGER,
    
    -- 人工审核
    manual_review_status VARCHAR(20) DEFAULT 'pending' 
        CHECK (manual_review_status IN ('pending', 'confirmed', 'disputed', 'corrected')),
    manual_reviewer_id UUID REFERENCES user_profiles(id),
    manual_review_notes TEXT,
    manual_review_time TIMESTAMP WITH TIME ZONE,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. 插入基础质控模板
-- 入院记录质控模板
INSERT INTO qc_templates (template_name, template_code, description, applicable_categories, template_config, prompt_template) VALUES
('入院记录质控模板', 'ADMISSION_QC', '针对入院记录的专门质控模板', 
 ARRAY[(SELECT id FROM document_categories WHERE category_code = 'admission_record')],
 '{
   "required_sections": ["主诉", "现病史", "既往史", "个人史", "家族史", "体格检查", "辅助检查", "初步诊断"],
   "scoring_weights": {
     "completeness": 0.3,
     "accuracy": 0.4,
     "timeliness": 0.2,
     "consistency": 0.1
   }
 }',
 '请对以下入院记录进行质控检查：\n\n{content}\n\n检查要点：\n1. 主诉是否简明扼要\n2. 现病史是否详细完整\n3. 既往史、个人史、家族史是否询问\n4. 体格检查是否全面\n5. 辅助检查结果是否完整\n6. 初步诊断是否合理\n\n请给出详细的质控意见和评分。');

-- 病程记录质控模板
INSERT INTO qc_templates (template_name, template_code, description, applicable_categories, template_config, prompt_template) VALUES
('病程记录质控模板', 'PROGRESS_QC', '针对病程记录的专门质控模板',
 ARRAY[(SELECT id FROM document_categories WHERE category_code = 'progress_note')],
 '{
   "required_sections": ["病情变化", "诊疗措施", "效果评估"],
   "scoring_weights": {
     "timeliness": 0.4,
     "completeness": 0.3,
     "consistency": 0.3
   }
 }',
 '请对以下病程记录进行质控检查：\n\n{content}\n\n检查要点：\n1. 记录是否及时\n2. 病情变化描述是否准确\n3. 诊疗措施是否合理\n4. 效果评估是否客观\n5. 与前次记录是否连贯\n\n请给出详细的质控意见和评分。');

-- 手术记录质控模板
INSERT INTO qc_templates (template_name, template_code, description, applicable_categories, template_config, prompt_template) VALUES
('手术记录质控模板', 'SURGERY_QC', '针对手术记录的专门质控模板',
 ARRAY[(SELECT id FROM document_categories WHERE category_code = 'operation_record')],
 '{
   "required_sections": ["术前诊断", "手术指征", "手术过程", "术中所见", "术后处理"],
   "scoring_weights": {
     "completeness": 0.4,
     "accuracy": 0.4,
     "timeliness": 0.2
   }
 }',
 '请对以下手术记录进行质控检查：\n\n{content}\n\n检查要点：\n1. 术前诊断是否明确\n2. 手术指征是否充分\n3. 手术过程描述是否详细\n4. 术中所见记录是否完整\n5. 术后处理是否恰当\n6. 记录是否及时完成\n\n请给出详细的质控意见和评分。');

-- 护理文书质控模板
INSERT INTO qc_templates (template_name, template_code, description, applicable_categories, template_config, prompt_template) VALUES
('护理文书质控模板', 'NURSING_QC', '针对护理文书的专门质控模板',
 ARRAY[(SELECT id FROM document_categories WHERE category_code = 'nursing_document')],
 '{
   "required_sections": ["护理评估", "护理措施", "效果观察"],
   "scoring_weights": {
     "completeness": 0.3,
     "timeliness": 0.4,
     "accuracy": 0.3
   }
 }',
 '请对以下护理文书进行质控检查：\n\n{content}\n\n检查要点：\n1. 护理评估是否全面\n2. 护理措施是否恰当\n3. 效果观察是否及时\n4. 记录是否规范\n5. 时间节点是否准确\n\n请给出详细的质控意见和评分。');

-- 出院记录质控模板
INSERT INTO qc_templates (template_name, template_code, description, applicable_categories, template_config, prompt_template) VALUES
('出院记录质控模板', 'DISCHARGE_QC', '针对出院记录的专门质控模板',
 ARRAY[(SELECT id FROM document_categories WHERE category_code = 'discharge_record')],
 '{
   "required_sections": ["入院情况", "诊疗经过", "出院诊断", "出院医嘱", "随访计划"],
   "scoring_weights": {
     "completeness": 0.4,
     "consistency": 0.3,
     "accuracy": 0.3
   }
 }',
 '请对以下出院记录进行质控检查：\n\n{content}\n\n检查要点：\n1. 入院情况总结是否准确\n2. 诊疗经过是否完整\n3. 出院诊断是否明确\n4. 出院医嘱是否合理\n5. 随访计划是否制定\n6. 与住院过程是否一致\n\n请给出详细的质控意见和评分。');

-- 6. 创建索引
CREATE INDEX idx_qc_templates_categories ON qc_templates USING GIN (applicable_categories);
CREATE INDEX idx_qc_templates_document_types ON qc_templates USING GIN (applicable_document_types);
CREATE INDEX idx_document_qc_results_document_id ON document_qc_results(document_id);
CREATE INDEX idx_document_qc_results_template_id ON document_qc_results(template_id);
CREATE INDEX idx_document_qc_results_status ON document_qc_results(result_status);
CREATE INDEX idx_qc_rules_categories ON qc_rules USING GIN (applicable_categories);
CREATE INDEX idx_qc_rules_document_types ON qc_rules USING GIN (applicable_document_types);

-- 7. 创建更新时间触发器
CREATE TRIGGER update_qc_templates_updated_at BEFORE UPDATE ON qc_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_document_qc_results_updated_at BEFORE UPDATE ON document_qc_results FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
