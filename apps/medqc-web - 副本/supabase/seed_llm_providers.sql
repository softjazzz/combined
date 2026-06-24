-- 初始化LLM提供商和模型数据
-- 用于支持大模型API配置的持久化存储

-- 清理现有数据（可选）
-- DELETE FROM user_llm_configs;
-- DELETE FROM llm_models;
-- DELETE FROM llm_api_providers;

-- 插入LLM API提供商
INSERT INTO llm_api_providers (
    provider_code, 
    provider_name, 
    base_endpoint, 
    request_format, 
    requires_api_key, 
    description, 
    features, 
    is_active, 
    sort_order
) VALUES 
-- 阿里云通义千问
(
    'alibaba',
    '阿里通义千问',
    'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'openai',
    true,
    '阿里云大模型服务，企业级可靠性，兼容OpenAI格式',
    '["企业级", "高开发", "多模态", "中文优化"]',
    true,
    1
),
-- 百度文心一言
(
    'baidu',
    '百度文心一言',
    'https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop',
    'baidu',
    true,
    '百度自研大模型，中文理解能力强',
    '["中文优化", "企业级服务", "数据安全"]',
    true,
    2
),
-- OpenAI
(
    'openai',
    'OpenAI',
    'https://api.openai.com/v1',
    'openai',
    true,
    '业界领先的大语言模型服务',
    '["全球领先", "多语言", "强大推理"]',
    true,
    3
),
-- 智谱AI
(
    'zhipu',
    '智谱ChatGLM',
    'https://open.bigmodel.cn/api/paas/v4',
    'openai',
    true,
    '清华大学技术背景，中英文双语优化',
    '["学术背景", "双语优化", "推理能力"]',
    true,
    4
),
-- 本地部署
(
    'local',
    '本地部署模型',
    'http://localhost:11434/v1',
    'openai',
    false,
    '本地部署的医疗专用模型，数据完全私有',
    '["数据私有", "无网络依赖", "可定制"]',
    true,
    5
),
-- 模拟服务（用于测试）
(
    'mock',
    '模拟服务',
    'http://localhost:8080/mock',
    'openai',
    false,
    '用于开发和测试的模拟服务',
    '["开发测试", "无需API密钥"]',
    true,
    99
)
ON CONFLICT (provider_code) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    base_endpoint = EXCLUDED.base_endpoint,
    description = EXCLUDED.description,
    features = EXCLUDED.features,
    updated_at = NOW();

-- 插入LLM模型
INSERT INTO llm_models (
    provider_id,
    model_code,
    model_name,
    display_name,
    description,
    context_length,
    max_tokens,
    pricing_info,
    capabilities,
    is_active,
    sort_order
) VALUES 
-- 阿里云模型
(
    (SELECT id FROM llm_api_providers WHERE provider_code = 'alibaba'),
    'qwen-plus',
    'Qwen-Plus',
    '通义千问Plus',
    '高性能通用模型，适合复杂推理任务',
    32768,
    8192,
    '{"input_price": 0.004, "output_price": 0.012, "currency": "CNY", "unit": "1K tokens"}',
    '["文本生成", "代码生成", "数学推理", "多语言"]',
    true,
    1
),
(
    (SELECT id FROM llm_api_providers WHERE provider_code = 'alibaba'),
    'qwen-turbo',
    'Qwen-Turbo',
    '通义千问Turbo',
    '快速响应模型，适合日常对话和简单任务',
    8192,
    4096,
    '{"input_price": 0.002, "output_price": 0.006, "currency": "CNY", "unit": "1K tokens"}',
    '["快速响应", "日常对话", "文本处理"]',
    true,
    2
),
(
    (SELECT id FROM llm_api_providers WHERE provider_code = 'alibaba'),
    'qwen2.5-7b-1m',
    'Qwen2.5-7B-1M',
    'Qwen2.5-7B-1M',
    '7B参数模型，支持1M上下文长度',
    1048576,
    8192,
    '{"input_price": 0.001, "output_price": 0.003, "currency": "CNY", "unit": "1K tokens"}',
    '["长上下文", "7B参数", "高效推理"]',
    true,
    3
),
-- 百度模型
(
    (SELECT id FROM llm_api_providers WHERE provider_code = 'baidu'),
    'ernie-4.0-8k',
    'ERNIE-4.0-8K',
    '文心一言4.0',
    '百度最新一代大模型，中文能力突出',
    8192,
    4096,
    '{"input_price": 0.03, "output_price": 0.09, "currency": "CNY", "unit": "1K tokens"}',
    '["中文优化", "知识问答", "创意写作"]',
    true,
    1
),
(
    (SELECT id FROM llm_api_providers WHERE provider_code = 'baidu'),
    'ernie-3.5-8k',
    'ERNIE-3.5-8K',
    '文心一言3.5',
    '性价比优秀的中文大模型',
    8192,
    4096,
    '{"input_price": 0.012, "output_price": 0.012, "currency": "CNY", "unit": "1K tokens"}',
    '["性价比高", "中文理解", "通用任务"]',
    true,
    2
),
-- OpenAI模型
(
    (SELECT id FROM llm_api_providers WHERE provider_code = 'openai'),
    'gpt-4o',
    'GPT-4o',
    'GPT-4o',
    'OpenAI最新多模态模型，性能卓越',
    128000,
    4096,
    '{"input_price": 5.0, "output_price": 15.0, "currency": "USD", "unit": "1M tokens"}',
    '["多模态", "强推理", "代码生成"]',
    true,
    1
),
(
    (SELECT id FROM llm_api_providers WHERE provider_code = 'openai'),
    'gpt-4o-mini',
    'GPT-4o-mini',
    'GPT-4o Mini',
    '轻量级高性能模型，成本更低',
    128000,
    16384,
    '{"input_price": 0.15, "output_price": 0.6, "currency": "USD", "unit": "1M tokens"}',
    '["高性价比", "快速响应", "多用途"]',
    true,
    2
),
-- 智谱模型
(
    (SELECT id FROM llm_api_providers WHERE provider_code = 'zhipu'),
    'glm-4',
    'GLM-4',
    'ChatGLM-4',
    '智谱AI最新一代模型，中英文能力均衡',
    128000,
    4096,
    '{"input_price": 0.1, "output_price": 0.1, "currency": "CNY", "unit": "1K tokens"}',
    '["双语优化", "逻辑推理", "代码理解"]',
    true,
    1
),
-- 本地模型
(
    (SELECT id FROM llm_api_providers WHERE provider_code = 'local'),
    'medical-llama',
    'Medical-Llama',
    '医疗专用Llama',
    '针对医疗场景优化的本地部署模型',
    4096,
    2048,
    '{"cost": "免费", "note": "本地部署无API费用"}',
    '["医疗专用", "本地部署", "数据私有"]',
    true,
    1
),
-- 模拟模型
(
    (SELECT id FROM llm_api_providers WHERE provider_code = 'mock'),
    'mock-model',
    'Mock Model',
    '模拟模型',
    '用于开发测试的模拟模型',
    4096,
    2048,
    '{"cost": "免费", "note": "仅用于测试"}',
    '["测试专用"]',
    true,
    1
)
ON CONFLICT (provider_id, model_code) DO UPDATE SET
    model_name = EXCLUDED.model_name,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    context_length = EXCLUDED.context_length,
    max_tokens = EXCLUDED.max_tokens,
    pricing_info = EXCLUDED.pricing_info,
    capabilities = EXCLUDED.capabilities,
    updated_at = NOW();

-- 创建默认配置（如果不存在）
INSERT INTO user_llm_configs (
    user_id,
    config_name,
    provider_id,
    model_id,
    is_active
) 
SELECT
    NULL, -- 全局配置
    'default',
    p.id,
    m.id,
    TRUE
FROM llm_api_providers p
JOIN llm_models m ON p.id = m.provider_id
WHERE p.provider_code = 'mock' AND m.model_code = 'mock-model'
ON CONFLICT (user_id, config_name) DO NOTHING;

-- 验证数据插入
SELECT 
    p.provider_name,
    COUNT(m.id) as model_count
FROM llm_api_providers p
LEFT JOIN llm_models m ON p.id = m.provider_id
WHERE p.is_active = true
GROUP BY p.id, p.provider_name
ORDER BY p.sort_order;
