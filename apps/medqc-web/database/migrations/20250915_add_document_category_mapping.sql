-- =============================================
-- 添加质控规则与文书类别映射
-- 版本: 1.0.0
-- 日期: 2025-09-15
-- 描述: 为质控规则添加文书类别字段，建立规则与文书类型的对应关系
-- =============================================

-- 1. 创建文书类别枚举类型
DO $$ BEGIN
    CREATE TYPE document_category_enum AS ENUM (
        'progress_note',      -- 病程记录
        'admission_record',   -- 入院记录
        'discharge_record',   -- 出院记录
        'operation_record',   -- 手术相关记录
        'examination_report', -- 辅助检查
        'consent_form'        -- 知情同意书
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. 为 qc_rules 表添加文书类别相关字段
ALTER TABLE qc_rules 
ADD COLUMN IF NOT EXISTS document_categories document_category_enum[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS primary_document_category document_category_enum,
ADD COLUMN IF NOT EXISTS applicable_document_types TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS document_section_targets TEXT[] DEFAULT '{}';

-- 3. 添加字段注释
COMMENT ON COLUMN qc_rules.document_categories IS '适用的文书类别数组，一个规则可以适用于多个文书类别';
COMMENT ON COLUMN qc_rules.primary_document_category IS '主要适用的文书类别，用于分类显示';
COMMENT ON COLUMN qc_rules.applicable_document_types IS '适用的具体文书类型，如admission_record_24h等';
COMMENT ON COLUMN qc_rules.document_section_targets IS '目标文书章节，如主诉、现病史等';

-- 4. 创建文书类别配置表
CREATE TABLE IF NOT EXISTS document_category_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_code document_category_enum NOT NULL UNIQUE,
    category_name VARCHAR(50) NOT NULL,
    category_description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    
    -- 质控配置
    default_weight DECIMAL(3,2) DEFAULT 1.0,
    required_sections TEXT[] DEFAULT '{}',
    optional_sections TEXT[] DEFAULT '{}',
    
    -- 元数据
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. 插入六个标准文书类别配置
INSERT INTO document_category_config (
    category_code, 
    category_name, 
    category_description, 
    sort_order,
    default_weight,
    required_sections
) VALUES 
(
    'admission_record', 
    '入院记录', 
    '患者入院时的基本信息、主诉、现病史、既往史、体格检查等记录',
    1,
    1.2,
    ARRAY['主诉', '现病史', '既往史', '体格检查', '入院诊断']
),
(
    'progress_note', 
    '病程记录', 
    '住院期间的病情变化、治疗过程、医嘱执行等动态记录',
    2,
    1.0,
    ARRAY['病情变化', '治疗措施', '医嘱记录']
),
(
    'discharge_record', 
    '出院记录', 
    '患者出院时的诊疗总结、出院诊断、治疗效果等记录',
    3,
    1.3,
    ARRAY['入院情况', '诊疗经过', '出院诊断', '出院医嘱']
),
(
    'operation_record', 
    '手术相关记录', 
    '手术记录、麻醉记录、术前讨论、术后总结等手术相关文书',
    4,
    1.5,
    ARRAY['手术指征', '手术过程', '术后处理']
),
(
    'examination_report', 
    '辅助检查', 
    '影像学检查、实验室检查、病理检查等辅助检查报告',
    5,
    0.8,
    ARRAY['检查项目', '检查结果', '诊断意见']
),
(
    'consent_form', 
    '知情同意书', 
    '各类医疗操作的知情同意书、风险告知书等',
    6,
    1.1,
    ARRAY['风险告知', '患者签字', '医师签字']
)
ON CONFLICT (category_code) DO UPDATE SET
    category_name = EXCLUDED.category_name,
    category_description = EXCLUDED.category_description,
    sort_order = EXCLUDED.sort_order,
    default_weight = EXCLUDED.default_weight,
    required_sections = EXCLUDED.required_sections,
    updated_at = NOW();

-- 6. 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_qc_rules_document_categories
ON qc_rules USING GIN (document_categories);

CREATE INDEX IF NOT EXISTS idx_qc_rules_primary_document_category
ON qc_rules (primary_document_category);

CREATE INDEX IF NOT EXISTS idx_document_category_config_sort_order
ON document_category_config (sort_order);

-- 7. 创建更新时间戳的触发器
CREATE OR REPLACE FUNCTION update_document_category_config_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_document_category_config_updated_at
    BEFORE UPDATE ON document_category_config
    FOR EACH ROW
    EXECUTE FUNCTION update_document_category_config_updated_at();
