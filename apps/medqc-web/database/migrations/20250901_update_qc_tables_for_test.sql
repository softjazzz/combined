-- =============================================
-- 测试环境质控表调整以支持文书分类
-- 版本: 1.0.0
-- 创建时间: 2025-09-01
-- 描述: 调整现有质控表以支持层级化文书分类
-- =============================================

-- 1. 为现有的qc_rules表添加文书类型相关字段
DO $$ 
BEGIN
    -- 添加适用的文书分类
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'qc_rules' 
                   AND column_name = 'applicable_categories') THEN
        ALTER TABLE qc_rules ADD COLUMN applicable_categories UUID[] DEFAULT '{}';
    END IF;
    
    -- 添加适用的文书类型
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'qc_rules' 
                   AND column_name = 'applicable_document_types') THEN
        ALTER TABLE qc_rules ADD COLUMN applicable_document_types UUID[] DEFAULT '{}';
    END IF;
    
    -- 添加文书特定配置
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'qc_rules' 
                   AND column_name = 'document_specific_config') THEN
        ALTER TABLE qc_rules ADD COLUMN document_specific_config JSONB DEFAULT '{}';
    END IF;
END $$;

-- 2. 创建质控模板表（针对不同文书类型的质控模板）
CREATE TABLE IF NOT EXISTS qc_templates_test (
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
    created_by UUID, -- 可以为空，因为测试环境可能没有用户系统
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. 为现有的qc_results表添加文书级别的质控支持
DO $$ 
BEGIN
    -- 添加文书ID引用
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'qc_results' 
                   AND column_name = 'document_id') THEN
        ALTER TABLE qc_results ADD COLUMN document_id UUID;
        -- 注意：这里不添加外键约束，因为可能引用不同的文书表
    END IF;
    
    -- 添加模板ID引用
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'qc_results' 
                   AND column_name = 'template_id') THEN
        ALTER TABLE qc_results ADD COLUMN template_id UUID REFERENCES qc_templates_test(id);
    END IF;
    
    -- 添加文书类型ID
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'qc_results' 
                   AND column_name = 'document_type_id') THEN
        ALTER TABLE qc_results ADD COLUMN document_type_id UUID;
    END IF;
    
    -- 添加质控级别标识
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'qc_results' 
                   AND column_name = 'qc_level') THEN
        ALTER TABLE qc_results ADD COLUMN qc_level VARCHAR(20) DEFAULT 'record' 
            CHECK (qc_level IN ('record', 'document', 'section'));
    END IF;
END $$;

-- 4. 创建文书质控结果表（更详细的文书级质控结果）
CREATE TABLE IF NOT EXISTS document_qc_results_test (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL, -- 引用 medical_documents_test.id
    template_id UUID REFERENCES qc_templates_test(id),
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
    manual_reviewer_id UUID, -- 可以为空
    manual_review_notes TEXT,
    manual_review_time TIMESTAMP WITH TIME ZONE,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. 插入基础质控模板
-- 入院记录质控模板
INSERT INTO qc_templates_test (template_name, template_code, description, applicable_categories, template_config, prompt_template) VALUES
('入院记录质控模板', 'ADMISSION_QC_TEST', '针对入院记录的专门质控模板', 
 ARRAY[(SELECT id FROM document_categories_test WHERE category_code = 'admission_record')],
 '{
   "required_sections": ["主诉", "现病史", "既往史", "个人史", "家族史", "体格检查", "辅助检查", "初步诊断"],
   "scoring_weights": {
     "completeness": 0.3,
     "accuracy": 0.4,
     "timeliness": 0.2,
     "consistency": 0.1
   }
 }',
 '请对以下入院记录进行质控检查：

{content}

检查要点：
1. 主诉是否简明扼要
2. 现病史是否详细完整
3. 既往史、个人史、家族史是否询问
4. 体格检查是否全面
5. 辅助检查结果是否完整
6. 初步诊断是否合理

请给出详细的质控意见和评分。')
ON CONFLICT (template_code) DO NOTHING;

-- 病程记录质控模板
INSERT INTO qc_templates_test (template_name, template_code, description, applicable_categories, template_config, prompt_template) VALUES
('病程记录质控模板', 'PROGRESS_QC_TEST', '针对病程记录的专门质控模板',
 ARRAY[(SELECT id FROM document_categories_test WHERE category_code = 'progress_note')],
 '{
   "required_sections": ["病情变化", "诊疗措施", "效果评估"],
   "scoring_weights": {
     "timeliness": 0.4,
     "completeness": 0.3,
     "consistency": 0.3
   }
 }',
 '请对以下病程记录进行质控检查：

{content}

检查要点：
1. 记录是否及时
2. 病情变化描述是否准确
3. 诊疗措施是否合理
4. 效果评估是否客观
5. 与前次记录是否连贯

请给出详细的质控意见和评分。')
ON CONFLICT (template_code) DO NOTHING;

-- 护理文书质控模板
INSERT INTO qc_templates_test (template_name, template_code, description, applicable_categories, template_config, prompt_template) VALUES
('护理文书质控模板', 'NURSING_QC_TEST', '针对护理文书的专门质控模板',
 ARRAY[(SELECT id FROM document_categories_test WHERE category_code = 'nursing_document')],
 '{
   "required_sections": ["护理评估", "护理措施", "效果观察"],
   "scoring_weights": {
     "completeness": 0.3,
     "timeliness": 0.4,
     "accuracy": 0.3
   }
 }',
 '请对以下护理文书进行质控检查：

{content}

检查要点：
1. 护理评估是否全面
2. 护理措施是否恰当
3. 效果观察是否及时
4. 记录是否规范
5. 时间节点是否准确

请给出详细的质控意见和评分。')
ON CONFLICT (template_code) DO NOTHING;

-- 医嘱记录质控模板
INSERT INTO qc_templates_test (template_name, template_code, description, applicable_categories, template_config, prompt_template) VALUES
('医嘱记录质控模板', 'ORDER_QC_TEST', '针对医嘱记录的专门质控模板',
 ARRAY[(SELECT id FROM document_categories_test WHERE category_code = 'medical_order')],
 '{
   "required_sections": ["医嘱内容", "执行时间", "执行人员"],
   "scoring_weights": {
     "accuracy": 0.4,
     "completeness": 0.3,
     "timeliness": 0.3
   }
 }',
 '请对以下医嘱记录进行质控检查：

{content}

检查要点：
1. 医嘱内容是否准确完整
2. 用药剂量是否合理
3. 执行时间是否准确
4. 执行记录是否完整
5. 是否有医师签名

请给出详细的质控意见和评分。')
ON CONFLICT (template_code) DO NOTHING;

-- 6. 创建索引
CREATE INDEX IF NOT EXISTS idx_qc_templates_test_categories ON qc_templates_test USING GIN (applicable_categories);
CREATE INDEX IF NOT EXISTS idx_qc_templates_test_document_types ON qc_templates_test USING GIN (applicable_document_types);
CREATE INDEX IF NOT EXISTS idx_document_qc_results_test_document_id ON document_qc_results_test(document_id);
CREATE INDEX IF NOT EXISTS idx_document_qc_results_test_template_id ON document_qc_results_test(template_id);
CREATE INDEX IF NOT EXISTS idx_document_qc_results_test_status ON document_qc_results_test(result_status);
CREATE INDEX IF NOT EXISTS idx_qc_rules_categories ON qc_rules USING GIN (applicable_categories);
CREATE INDEX IF NOT EXISTS idx_qc_rules_document_types ON qc_rules USING GIN (applicable_document_types);

-- 7. 创建更新时间触发器
CREATE TRIGGER update_qc_templates_test_updated_at BEFORE UPDATE ON qc_templates_test FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_document_qc_results_test_updated_at BEFORE UPDATE ON document_qc_results_test FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 8. 创建视图，方便查询质控统计
CREATE OR REPLACE VIEW qc_stats_by_document_type_test AS
SELECT 
    dc.category_name,
    dt.type_name,
    COUNT(dqr.id) as total_qc_count,
    COUNT(CASE WHEN dqr.result_status = 'passed' THEN 1 END) as passed_count,
    COUNT(CASE WHEN dqr.result_status = 'failed' THEN 1 END) as failed_count,
    AVG(dqr.score) as avg_score,
    AVG(dqr.confidence_score) as avg_confidence
FROM document_categories_test dc
LEFT JOIN document_types_test dt ON dc.id = dt.category_id
LEFT JOIN medical_documents_test md ON dt.id = md.type_id
LEFT JOIN document_qc_results_test dqr ON md.id = dqr.document_id
GROUP BY dc.category_name, dt.type_name, dc.sort_order, dt.sort_order
ORDER BY dc.sort_order, dt.sort_order;
