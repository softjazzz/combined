-- =====================================================
-- 质控LLM配置设置
-- 为质控分析功能配置专门的LLM配置
-- =====================================================

-- 1. 确保LLM配置表存在（如果还没有运行过LLM配置迁移）
CREATE TABLE IF NOT EXISTS llm_api_providers (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    provider_code VARCHAR(50) UNIQUE NOT NULL,
    provider_name VARCHAR(100) NOT NULL,
    base_endpoint VARCHAR(500) NOT NULL,
    request_format VARCHAR(20) NOT NULL DEFAULT 'openai',
    requires_api_key BOOLEAN DEFAULT TRUE,
    description TEXT,
    features JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS llm_models (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    provider_id UUID REFERENCES llm_api_providers(id) ON DELETE CASCADE,
    model_code VARCHAR(100) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    description TEXT,
    context_length INTEGER,
    pricing_tier VARCHAR(20),
    capabilities JSONB DEFAULT '[]',
    parameters JSONB DEFAULT '{}',
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_llm_configs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID,
    config_name VARCHAR(100) NOT NULL,
    provider_id UUID REFERENCES llm_api_providers(id),
    model_id UUID REFERENCES llm_models(id),
    api_key_encrypted TEXT,
    custom_endpoint VARCHAR(500),
    custom_parameters JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_user_config UNIQUE (user_id, config_name)
);

-- 2. 插入质控专用的LLM提供商配置（如果不存在）
INSERT INTO llm_api_providers (provider_code, provider_name, base_endpoint, request_format, description, features, sort_order)
VALUES 
-- 阿里云DashScope（推荐用于质控分析）
('dashscope', '阿里云DashScope', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'openai', 
 '阿里云通义千问系列模型，中文理解能力强，适合医疗质控分析', 
 '["中文优化", "医疗理解", "快速响应", "成本效益"]', 1),

-- OpenAI（高质量分析）
('openai', 'OpenAI GPT', 'https://api.openai.com/v1', 'openai',
 'OpenAI GPT系列模型，推理能力强，适合复杂质控规则', 
 '["强推理能力", "多语言支持", "高准确率"]', 2),

-- DeepSeek（成本优化）
('deepseek', 'DeepSeek', 'https://api.deepseek.com/v1', 'openai',
 'DeepSeek模型，成本低廉，适合大规模质控分析', 
 '["成本优化", "快速响应", "中文支持"]', 3)

ON CONFLICT (provider_code) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    base_endpoint = EXCLUDED.base_endpoint,
    description = EXCLUDED.description,
    features = EXCLUDED.features,
    updated_at = NOW();

-- 3. 插入质控专用的模型配置
INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, parameters, is_default)
SELECT 
    p.id,
    'qwen2.5-14b-instruct',
    '通义千问2.5-14B',
    '适合医疗质控分析的中等规模模型，平衡性能和成本',
    32768,
    'standard',
    '["医疗理解", "中文优化", "逻辑推理"]',
    '{"temperature": 0.1, "top_p": 0.8, "max_tokens": 1000}',
    true
FROM llm_api_providers p WHERE p.provider_code = 'dashscope'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, parameters, is_default)
SELECT 
    p.id,
    'qwen2.5-32b-instruct',
    '通义千问2.5-32B',
    '高性能医疗质控分析模型，适合复杂规则判断',
    32768,
    'premium',
    '["医疗理解", "中文优化", "强推理能力"]',
    '{"temperature": 0.1, "top_p": 0.8, "max_tokens": 1000}',
    false
FROM llm_api_providers p WHERE p.provider_code = 'dashscope'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, parameters, is_default)
SELECT 
    p.id,
    'gpt-4o-mini',
    'GPT-4o Mini',
    'OpenAI经济型模型，适合标准质控分析',
    128000,
    'standard',
    '["强推理能力", "多语言支持", "成本优化"]',
    '{"temperature": 0.1, "max_tokens": 1000}',
    true
FROM llm_api_providers p WHERE p.provider_code = 'openai'
ON CONFLICT DO NOTHING;

INSERT INTO llm_models (provider_id, model_code, model_name, description, context_length, pricing_tier, capabilities, parameters, is_default)
SELECT 
    p.id,
    'deepseek-chat',
    'DeepSeek Chat',
    'DeepSeek对话模型，成本低廉适合大规模质控',
    32768,
    'economy',
    '["成本优化", "中文支持", "快速响应"]',
    '{"temperature": 0.1, "max_tokens": 1000}',
    true
FROM llm_api_providers p WHERE p.provider_code = 'deepseek'
ON CONFLICT DO NOTHING;

-- 4. 创建质控分析专用配置
INSERT INTO user_llm_configs (user_id, config_name, provider_id, model_id, custom_parameters, is_active)
SELECT 
    NULL, -- 全局配置
    'qc_analysis',
    p.id,
    m.id,
    '{"purpose": "quality_control", "analysis_type": "medical_document", "response_format": "json"}',
    true
FROM llm_api_providers p
JOIN llm_models m ON p.id = m.provider_id
WHERE p.provider_code = 'dashscope' AND m.model_code = 'qwen2.5-14b-instruct'
ON CONFLICT (user_id, config_name) DO UPDATE SET
    provider_id = EXCLUDED.provider_id,
    model_id = EXCLUDED.model_id,
    custom_parameters = EXCLUDED.custom_parameters,
    updated_at = NOW();

-- 5. 创建文档提取专用配置（如果不存在）
INSERT INTO user_llm_configs (user_id, config_name, provider_id, model_id, custom_parameters, is_active)
SELECT 
    NULL, -- 全局配置
    'extraction',
    p.id,
    m.id,
    '{"purpose": "document_extraction", "analysis_type": "medical_parsing", "response_format": "json"}',
    true
FROM llm_api_providers p
JOIN llm_models m ON p.id = m.provider_id
WHERE p.provider_code = 'dashscope' AND m.model_code = 'qwen2.5-14b-instruct'
ON CONFLICT (user_id, config_name) DO NOTHING;

-- 6. 创建默认配置（如果不存在）
INSERT INTO user_llm_configs (user_id, config_name, provider_id, model_id, is_active)
SELECT 
    NULL, -- 全局配置
    'default',
    p.id,
    m.id,
    true
FROM llm_api_providers p
JOIN llm_models m ON p.id = m.provider_id
WHERE p.provider_code = 'dashscope' AND m.model_code = 'qwen2.5-14b-instruct'
ON CONFLICT (user_id, config_name) DO NOTHING;

-- 7. 创建索引（如果不存在）
CREATE INDEX IF NOT EXISTS idx_llm_providers_code ON llm_api_providers(provider_code);
CREATE INDEX IF NOT EXISTS idx_llm_providers_active ON llm_api_providers(is_active);
CREATE INDEX IF NOT EXISTS idx_llm_models_provider ON llm_models(provider_id);
CREATE INDEX IF NOT EXISTS idx_llm_models_code ON llm_models(model_code);
CREATE INDEX IF NOT EXISTS idx_llm_models_active ON llm_models(is_active);
CREATE INDEX IF NOT EXISTS idx_llm_models_default ON llm_models(is_default);
CREATE INDEX IF NOT EXISTS idx_user_llm_configs_user ON user_llm_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_llm_configs_config ON user_llm_configs(config_name);
CREATE INDEX IF NOT EXISTS idx_user_llm_configs_active ON user_llm_configs(is_active);

-- 8. 创建便捷查询视图
CREATE OR REPLACE VIEW qc_llm_configs_view AS
SELECT 
    c.id as config_id,
    c.config_name,
    c.user_id,
    p.provider_code,
    p.provider_name,
    p.base_endpoint,
    m.model_code,
    m.model_name,
    m.description as model_description,
    c.custom_endpoint,
    c.custom_parameters,
    c.is_active,
    c.created_at,
    c.updated_at
FROM user_llm_configs c
JOIN llm_api_providers p ON c.provider_id = p.id
JOIN llm_models m ON c.model_id = m.id
WHERE c.is_active = true AND p.is_active = true AND m.is_active = true;

-- 9. 创建获取质控配置的函数
CREATE OR REPLACE FUNCTION get_qc_llm_config(config_name_param TEXT DEFAULT 'qc_analysis')
RETURNS TABLE (
    provider_code TEXT,
    provider_name TEXT,
    base_endpoint TEXT,
    model_code TEXT,
    model_name TEXT,
    custom_endpoint TEXT,
    custom_parameters JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        v.provider_code::TEXT,
        v.provider_name::TEXT,
        v.base_endpoint::TEXT,
        v.model_code::TEXT,
        v.model_name::TEXT,
        v.custom_endpoint::TEXT,
        v.custom_parameters
    FROM qc_llm_configs_view v
    WHERE v.config_name = config_name_param
      AND v.user_id IS NULL  -- 全局配置
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- 10. 添加表注释
COMMENT ON TABLE llm_api_providers IS 'LLM API提供商配置表，存储各大模型厂商的基础信息';
COMMENT ON TABLE llm_models IS 'LLM模型配置表，存储每个提供商的具体模型信息';
COMMENT ON TABLE user_llm_configs IS '用户LLM配置表，存储用户的个性化模型配置，支持不同用途的配置';
COMMENT ON VIEW qc_llm_configs_view IS '质控LLM配置视图，便于查询完整的配置信息';
COMMENT ON FUNCTION get_qc_llm_config IS '获取质控LLM配置的便捷函数';

-- 完成提示
DO $$
BEGIN
    RAISE NOTICE '质控LLM配置设置完成！';
    RAISE NOTICE '已创建以下配置：';
    RAISE NOTICE '  - qc_analysis: 质控分析专用配置';
    RAISE NOTICE '  - extraction: 文档提取专用配置';
    RAISE NOTICE '  - default: 默认配置';
    RAISE NOTICE '可以通过 SELECT * FROM qc_llm_configs_view; 查看所有配置';
END $$;
