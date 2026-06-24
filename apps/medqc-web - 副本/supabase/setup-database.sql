-- 医疗质控系统数据库初始化脚本 - 增强版
-- 请在Supabase SQL Editor中执行此脚本
-- 版本: 2.0 - 支持多模型LLM配置

-- =====================================================
-- 1. 创建医疗记录主表
-- =====================================================
CREATE TABLE IF NOT EXISTS medical_records (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_number VARCHAR(50) UNIQUE NOT NULL,
    record_name VARCHAR(200) NOT NULL,
    
    -- 患者基本信息 (JSONB存储)
    patient_info JSONB NOT NULL DEFAULT '{}',
    
    -- 医疗信息
    department VARCHAR(100),
    primary_diagnosis TEXT,
    secondary_diagnosis JSONB DEFAULT '[]',
    major_surgery TEXT,
    
    -- 原始文本数据
    raw_text TEXT,
    
    -- AI解析结果 (增强版，包含模型信息)
    ai_extraction_result JSONB DEFAULT '{}',
    ai_confidence_score DECIMAL(5,2) DEFAULT 0.0,
    ai_model_used VARCHAR(100), -- 新增：记录使用的具体模型
    ai_provider VARCHAR(50),    -- 新增：记录AI服务提供商
    
    -- 状态和元数据
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    import_method VARCHAR(20) DEFAULT 'manual' CHECK (import_method IN ('manual', 'smart_import', 'batch_import')),
    
    -- 审计字段
    created_by UUID,
    last_modified_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 2. 创建医疗文书表
-- =====================================================
CREATE TABLE IF NOT EXISTS medical_documents (
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
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 3. 创建LLM API配置表 (新增)
-- =====================================================
CREATE TABLE IF NOT EXISTS llm_api_providers (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    provider_code VARCHAR(50) UNIQUE NOT NULL, -- 如: 'alibaba', 'openai', 'baidu'
    provider_name VARCHAR(100) NOT NULL,       -- 如: '阿里通义千问'
    base_endpoint VARCHAR(500) NOT NULL,       -- 统一的基础端点
    request_format VARCHAR(20) NOT NULL DEFAULT 'openai', -- 'openai', 'baidu', 'custom'
    requires_api_key BOOLEAN DEFAULT TRUE,
    description TEXT,
    features JSONB DEFAULT '[]',               -- 特性标签数组
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 4. 创建LLM模型配置表 (新增)
-- =====================================================
CREATE TABLE IF NOT EXISTS llm_models (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    provider_id UUID REFERENCES llm_api_providers(id) ON DELETE CASCADE,
    model_code VARCHAR(100) NOT NULL,          -- 如: 'qwen-turbo', 'gpt-4'
    model_name VARCHAR(100) NOT NULL,          -- 如: 'Qwen-Turbo'
    description TEXT,
    context_length INTEGER,                    -- 上下文长度
    pricing_tier VARCHAR(20),                  -- 'low', 'medium', 'high', 'very_high'
    capabilities JSONB DEFAULT '[]',           -- 能力标签数组
    parameters JSONB DEFAULT '{}',             -- 默认参数配置
    is_default BOOLEAN DEFAULT FALSE,          -- 是否为该提供商的默认模型
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 确保每个提供商只有一个默认模型（移除DEFERRABLE以支持ON CONFLICT）
    CONSTRAINT unique_default_per_provider UNIQUE (provider_id, is_default)
);

-- =====================================================
-- 5. 创建用户LLM配置表 (新增)
-- =====================================================
CREATE TABLE IF NOT EXISTS user_llm_configs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID, -- 可以为NULL，表示全局配置
    config_name VARCHAR(100) NOT NULL,         -- 配置名称，如 'default', 'medical_analysis'
    provider_id UUID REFERENCES llm_api_providers(id),
    model_id UUID REFERENCES llm_models(id),
    api_key_encrypted TEXT,                    -- 加密存储的API密钥
    custom_endpoint VARCHAR(500),              -- 自定义端点（可选）
    custom_parameters JSONB DEFAULT '{}',      -- 自定义参数
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 确保用户的配置名称唯一
    CONSTRAINT unique_user_config UNIQUE (user_id, config_name)
);

-- =====================================================
-- 6. 创建AI解析历史表 (增强版)
-- =====================================================
CREATE TABLE IF NOT EXISTS ai_parsing_history (
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
    
    -- 模型信息 (增强版)
    provider_id UUID REFERENCES llm_api_providers(id),
    model_id UUID REFERENCES llm_models(id),
    model_name VARCHAR(100),                   -- 冗余存储，便于查询
    model_version VARCHAR(50),
    
    -- 用户反馈
    user_corrections JSONB DEFAULT '{}',
    user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 5),
    user_feedback TEXT,
    
    -- 审计字段
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 7. 创建索引
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_medical_records_record_number ON medical_records(record_number);
CREATE INDEX IF NOT EXISTS idx_medical_records_department ON medical_records(department);
CREATE INDEX IF NOT EXISTS idx_medical_records_status ON medical_records(status);
CREATE INDEX IF NOT EXISTS idx_medical_records_created_at ON medical_records(created_at);
CREATE INDEX IF NOT EXISTS idx_medical_records_patient_info ON medical_records USING GIN(patient_info);
CREATE INDEX IF NOT EXISTS idx_medical_records_ai_result ON medical_records USING GIN(ai_extraction_result);
CREATE INDEX IF NOT EXISTS idx_medical_records_ai_provider ON medical_records(ai_provider);

CREATE INDEX IF NOT EXISTS idx_medical_documents_record_id ON medical_documents(record_id);
CREATE INDEX IF NOT EXISTS idx_medical_documents_type ON medical_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_medical_documents_metadata ON medical_documents USING GIN(document_metadata);

CREATE INDEX IF NOT EXISTS idx_llm_providers_code ON llm_api_providers(provider_code);
CREATE INDEX IF NOT EXISTS idx_llm_providers_active ON llm_api_providers(is_active);

CREATE INDEX IF NOT EXISTS idx_llm_models_provider ON llm_models(provider_id);
CREATE INDEX IF NOT EXISTS idx_llm_models_code ON llm_models(model_code);
CREATE INDEX IF NOT EXISTS idx_llm_models_active ON llm_models(is_active);
CREATE INDEX IF NOT EXISTS idx_llm_models_default ON llm_models(is_default);

CREATE INDEX IF NOT EXISTS idx_user_llm_configs_user ON user_llm_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_llm_configs_active ON user_llm_configs(is_active);

CREATE INDEX IF NOT EXISTS idx_ai_parsing_history_record_id ON ai_parsing_history(record_id);
CREATE INDEX IF NOT EXISTS idx_ai_parsing_history_created_at ON ai_parsing_history(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_parsing_history_provider ON ai_parsing_history(provider_id);
CREATE INDEX IF NOT EXISTS idx_ai_parsing_history_model ON ai_parsing_history(model_id);

-- =====================================================
-- 8. 创建更新时间触发器
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 应用触发器到医疗记录表
DROP TRIGGER IF EXISTS update_medical_records_updated_at ON medical_records;
CREATE TRIGGER update_medical_records_updated_at 
    BEFORE UPDATE ON medical_records 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 应用触发器到医疗文书表
DROP TRIGGER IF EXISTS update_medical_documents_updated_at ON medical_documents;
CREATE TRIGGER update_medical_documents_updated_at
    BEFORE UPDATE ON medical_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 应用触发器到LLM API提供商表
DROP TRIGGER IF EXISTS update_llm_api_providers_updated_at ON llm_api_providers;
CREATE TRIGGER update_llm_api_providers_updated_at
    BEFORE UPDATE ON llm_api_providers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 应用触发器到LLM模型表
DROP TRIGGER IF EXISTS update_llm_models_updated_at ON llm_models;
CREATE TRIGGER update_llm_models_updated_at
    BEFORE UPDATE ON llm_models
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 应用触发器到用户LLM配置表
DROP TRIGGER IF EXISTS update_user_llm_configs_updated_at ON user_llm_configs;
CREATE TRIGGER update_user_llm_configs_updated_at
    BEFORE UPDATE ON user_llm_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 9. 创建统计视图 (增强版)
-- =====================================================
CREATE OR REPLACE VIEW medical_records_with_documents AS
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

CREATE OR REPLACE VIEW medical_records_stats AS
SELECT
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE created_at >= date_trunc('month', CURRENT_DATE)) as monthly_new,
    COUNT(*) FILTER (WHERE status = 'draft') as pending_review,
    COUNT(*) FILTER (WHERE import_method = 'smart_import') as smart_imported,
    COUNT(*) FILTER (WHERE ai_confidence_score > 0) as ai_processed,
    AVG(ai_confidence_score) FILTER (WHERE ai_confidence_score > 0) as avg_confidence,
    COUNT(*) FILTER (WHERE ai_confidence_score >= 90) as high_confidence,
    COUNT(*) FILTER (WHERE ai_confidence_score < 70) as low_confidence
FROM medical_records
WHERE status != 'archived';

-- 创建LLM使用统计视图
CREATE OR REPLACE VIEW llm_usage_stats AS
SELECT
    p.provider_name,
    m.model_name,
    COUNT(*) as usage_count,
    AVG(aph.processing_time_ms) as avg_processing_time,
    SUM(aph.tokens_used) as total_tokens_used,
    AVG((aph.confidence_scores->>'overall')::numeric) as avg_confidence
FROM ai_parsing_history aph
JOIN llm_api_providers p ON aph.provider_id = p.id
JOIN llm_models m ON aph.model_id = m.id
WHERE aph.created_at >= date_trunc('month', CURRENT_DATE)
GROUP BY p.provider_name, m.model_name
ORDER BY usage_count DESC;

-- =====================================================
-- 10. 插入LLM API提供商配置数据
-- =====================================================

-- OpenAI
INSERT INTO llm_api_providers (
    provider_code, provider_name, base_endpoint, request_format,
    requires_api_key, description, features, sort_order
) VALUES (
    'openai',
    'OpenAI GPT',
    'https://api.openai.com/v1/chat/completions',
    'openai',
    TRUE,
    '最强大的通用大模型，医疗理解能力优秀',
    '["高准确率", "强推理能力", "多语言支持"]',
    1
) ON CONFLICT (provider_code) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    base_endpoint = EXCLUDED.base_endpoint,
    description = EXCLUDED.description,
    features = EXCLUDED.features;

-- 阿里通义千问 (修正端点)
INSERT INTO llm_api_providers (
    provider_code, provider_name, base_endpoint, request_format,
    requires_api_key, description, features, sort_order
) VALUES (
    'alibaba',
    '阿里通义千问',
    'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
    'openai',
    TRUE,
    '阿里云大模型服务，企业级可靠性，兼容OpenAI格式',
    '["企业级", "高并发", "多模态", "中文优化"]',
    2
) ON CONFLICT (provider_code) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    base_endpoint = EXCLUDED.base_endpoint,
    description = EXCLUDED.description,
    features = EXCLUDED.features;

-- 百度文心一言
INSERT INTO llm_api_providers (
    provider_code, provider_name, base_endpoint, request_format,
    requires_api_key, description, features, sort_order
) VALUES (
    'baidu',
    '百度文心一言',
    'https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions',
    'baidu',
    TRUE,
    '百度自研大模型，中文理解能力强',
    '["中文优化", "企业级服务", "数据安全"]',
    3
) ON CONFLICT (provider_code) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    base_endpoint = EXCLUDED.base_endpoint,
    description = EXCLUDED.description,
    features = EXCLUDED.features;

-- 腾讯混元
INSERT INTO llm_api_providers (
    provider_code, provider_name, base_endpoint, request_format,
    requires_api_key, description, features, sort_order
) VALUES (
    'tencent',
    '腾讯混元',
    'https://hunyuan.tencentcloudapi.com/v1/chat/completions',
    'openai',
    TRUE,
    '腾讯自研大模型，医疗垂直能力强',
    '["医疗专业", "安全合规", "高性能"]',
    4
) ON CONFLICT (provider_code) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    base_endpoint = EXCLUDED.base_endpoint,
    description = EXCLUDED.description,
    features = EXCLUDED.features;

-- 智谱ChatGLM
INSERT INTO llm_api_providers (
    provider_code, provider_name, base_endpoint, request_format,
    requires_api_key, description, features, sort_order
) VALUES (
    'zhipu',
    '智谱ChatGLM',
    'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    'openai',
    TRUE,
    '清华智谱开源大模型，可本地部署',
    '["开源友好", "可本地部署", "中文优化"]',
    5
) ON CONFLICT (provider_code) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    base_endpoint = EXCLUDED.base_endpoint,
    description = EXCLUDED.description,
    features = EXCLUDED.features;

-- 本地部署
INSERT INTO llm_api_providers (
    provider_code, provider_name, base_endpoint, request_format,
    requires_api_key, description, features, sort_order
) VALUES (
    'local',
    '本地部署模型',
    'http://localhost:8000/v1/chat/completions',
    'openai',
    FALSE,
    '本地部署的医疗专用模型，数据完全私有',
    '["数据私有", "无网络依赖", "可定制"]',
    6
) ON CONFLICT (provider_code) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    base_endpoint = EXCLUDED.base_endpoint,
    description = EXCLUDED.description,
    features = EXCLUDED.features;

-- 模拟模式
INSERT INTO llm_api_providers (
    provider_code, provider_name, base_endpoint, request_format,
    requires_api_key, description, features, sort_order
) VALUES (
    'mock',
    '模拟模式',
    '',
    'mock',
    FALSE,
    '用于开发测试的模拟模式，返回预设数据',
    '["开发测试", "无需API", "快速响应"]',
    7
) ON CONFLICT (provider_code) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    base_endpoint = EXCLUDED.base_endpoint,
    description = EXCLUDED.description,
    features = EXCLUDED.features;

-- =====================================================
-- 11. 插入模型配置数据
-- =====================================================

-- OpenAI 模型
INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'gpt-4', 'GPT-4', '最强大的模型，适合复杂推理', 8192, 'high', '["复杂推理", "高准确率"]', TRUE, 1
FROM llm_api_providers p WHERE p.provider_code = 'openai'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'gpt-4-turbo', 'GPT-4 Turbo', '更快的GPT-4版本', 128000, 'medium', '["快速响应", "长文本"]', FALSE, 2
FROM llm_api_providers p WHERE p.provider_code = 'openai'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'gpt-3.5-turbo', 'GPT-3.5 Turbo', '性价比最高的选择', 16385, 'low', '["性价比高", "快速响应"]', FALSE, 3
FROM llm_api_providers p WHERE p.provider_code = 'openai'
ON CONFLICT DO NOTHING;

-- 阿里通义千问模型
INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'qwen-turbo', 'Qwen-Turbo', '快速响应，适合简单任务', 8192, 'low', '["快速响应", "成本低"]', FALSE, 1
FROM llm_api_providers p WHERE p.provider_code = 'alibaba'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'qwen-plus', 'Qwen-Plus', '平衡性能和成本的选择', 32768, 'medium', '["平衡性能", "中等成本"]', TRUE, 2
FROM llm_api_providers p WHERE p.provider_code = 'alibaba'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'qwen-max', 'Qwen-Max', '最强性能，适合复杂任务', 32768, 'high', '["最强性能", "复杂推理"]', FALSE, 3
FROM llm_api_providers p WHERE p.provider_code = 'alibaba'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'qwen3-235b-a22b-instruct-2507', 'Qwen3-235B', '超大参数模型，顶级性能', 32768, 'very_high', '["超大参数", "顶级性能"]', FALSE, 4
FROM llm_api_providers p WHERE p.provider_code = 'alibaba'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'qwen-doc-turbo', 'Qwen-Doc-Turbo', '专门优化文档理解', 32768, 'medium', '["文档理解", "结构化提取"]', FALSE, 5
FROM llm_api_providers p WHERE p.provider_code = 'alibaba'
ON CONFLICT DO NOTHING;

-- 百度文心一言模型
INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'ERNIE-4.0-8K', 'ERNIE-4.0-8K', '文心4.0标准版', 8192, 'medium', '["中文优化", "企业级"]', TRUE, 1
FROM llm_api_providers p WHERE p.provider_code = 'baidu'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'ERNIE-4.0-Turbo-8K', 'ERNIE-4.0-Turbo-8K', '文心4.0加速版', 8192, 'low', '["快速响应", "成本低"]', FALSE, 2
FROM llm_api_providers p WHERE p.provider_code = 'baidu'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'ERNIE-3.5-8K', 'ERNIE-3.5-8K', '文心3.5经济版', 8192, 'very_low', '["经济实惠", "基础功能"]', FALSE, 3
FROM llm_api_providers p WHERE p.provider_code = 'baidu'
ON CONFLICT DO NOTHING;

-- 腾讯混元模型
INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'hunyuan-lite', 'Hunyuan-Lite', '轻量版本，快速响应', 4096, 'low', '["轻量级", "快速响应"]', FALSE, 1
FROM llm_api_providers p WHERE p.provider_code = 'tencent'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'hunyuan-standard', 'Hunyuan-Standard', '标准版本，平衡性能', 8192, 'medium', '["平衡性能", "标准功能"]', TRUE, 2
FROM llm_api_providers p WHERE p.provider_code = 'tencent'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'hunyuan-pro', 'Hunyuan-Pro', '专业版本，最强性能', 32768, 'high', '["医疗专业", "长文本"]', FALSE, 3
FROM llm_api_providers p WHERE p.provider_code = 'tencent'
ON CONFLICT DO NOTHING;

-- 智谱ChatGLM模型
INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'glm-4', 'GLM-4', '最新一代模型', 128000, 'medium', '["长文本", "多模态"]', TRUE, 1
FROM llm_api_providers p WHERE p.provider_code = 'zhipu'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'glm-4-air', 'GLM-4-Air', '轻量高效版本', 128000, 'low', '["轻量级", "高效率"]', FALSE, 2
FROM llm_api_providers p WHERE p.provider_code = 'zhipu'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'glm-4-flash', 'GLM-4-Flash', '极速响应版本', 128000, 'very_low', '["极速响应", "超低成本"]', FALSE, 3
FROM llm_api_providers p WHERE p.provider_code = 'zhipu'
ON CONFLICT DO NOTHING;

-- 本地部署和模拟模式模型
INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'medical-llm', 'Medical-LLM', '医疗专用模型', 8192, 'free', '["医疗专业", "本地部署"]', TRUE, 1
FROM llm_api_providers p WHERE p.provider_code = 'local'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, is_default, sort_order)
SELECT p.id, 'mock', 'Mock Model', '模拟测试模型', 8192, 'free', '["开发测试", "快速响应"]', TRUE, 1
FROM llm_api_providers p WHERE p.provider_code = 'mock'
ON CONFLICT DO NOTHING;

-- =====================================================
-- 12. 插入示例医疗记录数据 (增强版)
-- =====================================================
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
    ai_model_used,
    ai_provider,
    import_method,
    status
) VALUES 
(
    'MR20240827001',
    '张三病历',
    '{"name": "张三", "age": 65, "gender": "男", "id_number": "***************"}',
    '内科',
    '高血压病',
    '无',
    '患者张三，男，65岁，因头晕、头痛3天入院。患者3天前无明显诱因出现头晕、头痛，伴恶心，无呕吐，无发热，无胸闷气短。既往有高血压病史10年，平时服用降压药物治疗，血压控制尚可。',
    '{"extraction_time": "2024-08-27T10:30:00Z", "model_used": "qwen-plus", "provider": "alibaba", "fields_extracted": ["patient_name", "age", "gender", "department", "diagnosis"], "confidence_scores": {"patient_name": 95, "department": 88, "diagnosis": 92, "overall": 89}}',
    89.5,
    'qwen-plus',
    'alibaba',
    'smart_import',
    'active'
) ON CONFLICT (record_number) DO UPDATE SET
    ai_extraction_result = EXCLUDED.ai_extraction_result,
    ai_model_used = EXCLUDED.ai_model_used,
    ai_provider = EXCLUDED.ai_provider;

-- 插入对应的文书记录
INSERT INTO medical_documents (
    record_id,
    document_type,
    title,
    content,
    ai_classified,
    ai_confidence_score,
    sort_order
) 
SELECT 
    mr.id,
    'admission_record',
    '入院记录',
    '患者张三，男，65岁，因头晕、头痛3天入院。患者3天前无明显诱因出现头晕、头痛，伴恶心，无呕吐，无发热，无胸闷气短。既往有高血压病史10年，平时服用降压药物治疗，血压控制尚可。',
    true,
    95.0,
    1
FROM medical_records mr 
WHERE mr.record_number = 'MR20240827001'
ON CONFLICT DO NOTHING;

INSERT INTO medical_documents (
    record_id,
    document_type,
    title,
    content,
    ai_classified,
    ai_confidence_score,
    sort_order
) 
SELECT 
    mr.id,
    'first_progress_note',
    '首次病程记录',
    '患者入院后完善相关检查，血压180/100mmHg，心率78次/分，律齐，各瓣膜听诊区未闻及病理性杂音。初步诊断：高血压病。',
    true,
    88.0,
    2
FROM medical_records mr 
WHERE mr.record_number = 'MR20240827001'
ON CONFLICT DO NOTHING;

-- =====================================================
-- 13. 创建默认用户配置
-- =====================================================
INSERT INTO user_llm_configs (
    user_id, config_name, provider_id, model_id, is_active
)
SELECT
    NULL, -- 全局配置
    'default',
    p.id,
    m.id,
    TRUE
FROM llm_api_providers p
JOIN llm_models m ON p.id = m.provider_id
WHERE p.provider_code = 'mock' AND m.model_code = 'mock'
ON CONFLICT (user_id, config_name) DO NOTHING;

-- =====================================================
-- 14. 添加表注释
-- =====================================================
COMMENT ON TABLE medical_records IS '医疗记录主表，存储病历的基本信息和AI解析结果';
COMMENT ON TABLE medical_documents IS '医疗文书表，存储各类医疗文档内容';
COMMENT ON TABLE llm_api_providers IS 'LLM API提供商配置表，存储各大模型厂商的基础信息';
COMMENT ON TABLE llm_models IS 'LLM模型配置表，存储每个提供商的具体模型信息';
COMMENT ON TABLE user_llm_configs IS '用户LLM配置表，存储用户的个性化模型配置';
COMMENT ON TABLE ai_parsing_history IS 'AI解析历史记录，用于追踪和改进AI性能';

COMMENT ON COLUMN medical_records.patient_info IS '患者信息JSONB字段，存储姓名、年龄、性别等';
COMMENT ON COLUMN medical_records.ai_extraction_result IS 'AI解析结果JSONB字段，存储完整的解析输出';
COMMENT ON COLUMN medical_records.ai_model_used IS '使用的具体AI模型名称';
COMMENT ON COLUMN medical_records.ai_provider IS 'AI服务提供商标识';
COMMENT ON COLUMN medical_records.raw_text IS '原始病历文本，用于重新解析和审计';
COMMENT ON COLUMN llm_api_providers.base_endpoint IS '统一的API基础端点地址';
COMMENT ON COLUMN llm_api_providers.request_format IS 'API请求格式类型，用于适配不同厂商';
COMMENT ON COLUMN llm_models.context_length IS '模型支持的最大上下文长度';
COMMENT ON COLUMN llm_models.pricing_tier IS '定价层级，用于成本控制';
COMMENT ON COLUMN user_llm_configs.api_key_encrypted IS '加密存储的API密钥';
COMMENT ON COLUMN medical_documents.ai_extraction_metadata IS 'AI解析元数据，存储置信度、关键词等';

-- =====================================================
-- 15. 创建便捷查询函数
-- =====================================================

-- 获取提供商的所有模型
CREATE OR REPLACE FUNCTION get_provider_models(provider_code_param VARCHAR)
RETURNS TABLE (
    model_id UUID,
    model_code VARCHAR,
    model_name VARCHAR,
    description TEXT,
    context_length INTEGER,
    pricing_tier VARCHAR,
    capabilities JSONB,
    is_default BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.model_code,
        m.model_name,
        m.description,
        m.context_length,
        m.pricing_tier,
        m.capabilities,
        m.is_default
    FROM llm_models m
    JOIN llm_api_providers p ON m.provider_id = p.id
    WHERE p.provider_code = provider_code_param
      AND m.is_active = TRUE
    ORDER BY m.sort_order;
END;
$$ LANGUAGE plpgsql;

-- 获取用户的LLM配置
CREATE OR REPLACE FUNCTION get_user_llm_config(user_id_param UUID, config_name_param VARCHAR DEFAULT 'default')
RETURNS TABLE (
    provider_code VARCHAR,
    provider_name VARCHAR,
    base_endpoint VARCHAR,
    model_code VARCHAR,
    model_name VARCHAR,
    custom_endpoint VARCHAR,
    custom_parameters JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.provider_code,
        p.provider_name,
        p.base_endpoint,
        m.model_code,
        m.model_name,
        uc.custom_endpoint,
        uc.custom_parameters
    FROM user_llm_configs uc
    JOIN llm_api_providers p ON uc.provider_id = p.id
    JOIN llm_models m ON uc.model_id = m.id
    WHERE uc.user_id = user_id_param
      AND uc.config_name = config_name_param
      AND uc.is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 16. 创建测试表 (用于开发和测试)
-- =====================================================

-- 创建医疗记录测试表 - 独立测试用，简化设计，无外键依赖，便于测试
CREATE TABLE IF NOT EXISTS medical_records_test (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    record_number VARCHAR(50) UNIQUE NOT NULL,
    record_name VARCHAR(200) NOT NULL,

    -- 患者基本信息 (JSONB存储)
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

    -- 文书内容 (直接存储在主表中，简化结构)
    documents JSONB DEFAULT '[]',

    -- 状态和元数据
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    import_method VARCHAR(20) DEFAULT 'manual' CHECK (import_method IN ('manual', 'smart_import', 'batch_import')),

    -- 审计字段 (简化，无用户关联)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_medical_records_test_record_number ON medical_records_test(record_number);
CREATE INDEX IF NOT EXISTS idx_medical_records_test_department ON medical_records_test(department);
CREATE INDEX IF NOT EXISTS idx_medical_records_test_status ON medical_records_test(status);
CREATE INDEX IF NOT EXISTS idx_medical_records_test_created_at ON medical_records_test(created_at);
CREATE INDEX IF NOT EXISTS idx_medical_records_test_patient_info ON medical_records_test USING GIN(patient_info);
CREATE INDEX IF NOT EXISTS idx_medical_records_test_ai_result ON medical_records_test USING GIN(ai_extraction_result);
CREATE INDEX IF NOT EXISTS idx_medical_records_test_documents ON medical_records_test USING GIN(documents);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_medical_records_test_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 应用触发器
DROP TRIGGER IF EXISTS update_medical_records_test_updated_at ON medical_records_test;
CREATE TRIGGER update_medical_records_test_updated_at
    BEFORE UPDATE ON medical_records_test
    FOR EACH ROW EXECUTE FUNCTION update_medical_records_test_updated_at();

-- 插入测试数据
INSERT INTO medical_records_test (
    record_number,
    record_name,
    patient_info,
    department,
    primary_diagnosis,
    major_surgery,
    raw_text,
    ai_extraction_result,
    ai_confidence_score,
    documents,
    import_method,
    status
) VALUES
(
    'TEST20240827001',
    '张三测试病历',
    '{"name": "张三", "age": 65, "gender": "男", "phone": "138****8888"}',
    '内科',
    '高血压病',
    '无',
    '患者张三，男，65岁，因头晕、头痛3天入院。患者3天前无明显诱因出现头晕、头痛，伴恶心，无呕吐，无发热，无胸闷气短。既往有高血压病史10年，平时服用降压药物治疗，血压控制尚可。',
    '{"extraction_time": "2024-08-27T10:30:00Z", "model_used": "qwen-plus", "provider": "alibaba", "fields_extracted": ["patient_name", "age", "gender", "department", "diagnosis"], "confidence_scores": {"patient_name": 95, "department": 88, "diagnosis": 92, "overall": 89}}',
    89.5,
    '[
        {
            "id": "doc1",
            "type": "admission_record",
            "title": "入院记录",
            "content": "患者张三，男，65岁，因头晕、头痛3天入院。患者3天前无明显诱因出现头晕、头痛，伴恶心，无呕吐。既往有高血压病史10年。",
            "ai_confidence": 95,
            "ai_classified": true
        },
        {
            "id": "doc2",
            "type": "first_progress_note",
            "title": "首次病程记录",
            "content": "患者入院后完善相关检查，血压180/100mmHg，心率78次/分，律齐，各瓣膜听诊区未闻及病理性杂音。初步诊断：高血压病。",
            "ai_confidence": 88,
            "ai_classified": true
        }
    ]',
    'smart_import',
    'active'
),
(
    'TEST20240827002',
    '李四测试病历',
    '{"name": "李四", "age": 45, "gender": "女", "phone": "139****9999"}',
    '外科',
    '阑尾炎',
    '阑尾切除术',
    '患者李四，女，45岁，因右下腹痛6小时入院。患者6小时前无明显诱因出现右下腹痛，呈持续性钝痛，伴恶心、呕吐。',
    '{"extraction_time": "2024-08-27T11:00:00Z", "model_used": "qwen-plus", "provider": "alibaba", "fields_extracted": ["patient_name", "age", "gender", "department", "diagnosis", "surgery"], "confidence_scores": {"patient_name": 98, "department": 92, "diagnosis": 90, "surgery": 87, "overall": 91}}',
    91.0,
    '[
        {
            "id": "doc3",
            "type": "admission_record",
            "title": "入院记录",
            "content": "患者李四，女，45岁，因右下腹痛6小时入院。患者6小时前无明显诱因出现右下腹痛，呈持续性钝痛，伴恶心、呕吐。",
            "ai_confidence": 92,
            "ai_classified": true
        },
        {
            "id": "doc4",
            "type": "operation_record",
            "title": "手术记录",
            "content": "手术名称：腹腔镜阑尾切除术。手术过程：患者全麻后，取仰卧位，常规消毒铺巾。建立CO2气腹，置入腹腔镜探查。",
            "ai_confidence": 87,
            "ai_classified": true
        }
    ]',
    'smart_import',
    'active'
) ON CONFLICT (record_number) DO NOTHING;

-- 创建测试用的统计视图
CREATE OR REPLACE VIEW medical_records_test_stats AS
SELECT
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE created_at >= date_trunc('month', CURRENT_DATE)) as monthly_new,
    COUNT(*) FILTER (WHERE status = 'draft') as pending_review,
    COUNT(*) FILTER (WHERE import_method = 'smart_import') as smart_imported,
    COUNT(*) FILTER (WHERE ai_confidence_score > 0) as ai_processed,
    AVG(ai_confidence_score) FILTER (WHERE ai_confidence_score > 0) as avg_confidence,
    COUNT(*) FILTER (WHERE ai_confidence_score >= 90) as high_confidence,
    COUNT(*) FILTER (WHERE ai_confidence_score < 70) as low_confidence
FROM medical_records_test
WHERE status != 'archived';

-- 添加表注释
COMMENT ON TABLE medical_records_test IS '医疗记录测试表 - 用于开发和测试智能病历导入功能';
COMMENT ON COLUMN medical_records_test.patient_info IS '患者信息JSONB字段，存储姓名、年龄、性别等基本信息';
COMMENT ON COLUMN medical_records_test.ai_extraction_result IS 'AI解析结果JSONB字段，存储完整的解析输出和置信度';
COMMENT ON COLUMN medical_records_test.documents IS '文书内容JSONB数组，直接存储所有文书避免表关联';
COMMENT ON COLUMN medical_records_test.raw_text IS '原始病历文本，用于重新解析和审计';

-- =====================================================
-- 完成提示
-- =====================================================
SELECT 'Enhanced database setup completed successfully!' as message,
       COUNT(*) as providers_configured
FROM llm_api_providers
WHERE is_active = TRUE;

SELECT 'Total models configured:' as message,
       COUNT(*) as models_count
FROM llm_models
WHERE is_active = TRUE;

SELECT 'Test table created successfully!' as message,
       COUNT(*) as sample_records_inserted
FROM medical_records_test;
