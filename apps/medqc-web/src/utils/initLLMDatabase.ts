/**
 * 初始化LLM数据库数据
 * 用于在前端直接初始化LLM提供商和模型数据
 */

import { supabase } from '@/lib/supabase'

// LLM提供商数据
const LLM_PROVIDERS = [
  {
    provider_code: 'alibaba',
    provider_name: '阿里通义千问',
    base_endpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    request_format: 'openai',
    requires_api_key: true,
    description: '阿里云大模型服务，企业级可靠性，兼容OpenAI格式',
    features: ['企业级', '高开发', '多模态', '中文优化'],
    is_active: true,
    sort_order: 1,
  },
  {
    provider_code: 'baidu',
    provider_name: '百度文心一言',
    base_endpoint: 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop',
    request_format: 'baidu',
    requires_api_key: true,
    description: '百度自研大模型，中文理解能力强',
    features: ['中文优化', '企业级服务', '数据安全'],
    is_active: true,
    sort_order: 2,
  },
  {
    provider_code: 'openai',
    provider_name: 'OpenAI',
    base_endpoint: 'https://api.openai.com/v1',
    request_format: 'openai',
    requires_api_key: true,
    description: '业界领先的大语言模型服务',
    features: ['全球领先', '多语言', '强大推理'],
    is_active: true,
    sort_order: 3,
  },
  {
    provider_code: 'siliconflow',
    provider_name: '硅基流动 SiliconFlow',
    base_endpoint: 'https://api.siliconflow.cn/v1',
    request_format: 'openai',
    requires_api_key: true,
    description: '兼容 OpenAI 协议的 MaaS 平台，适合补充多种开源模型调用',
    features: ['OpenAI兼容', '开源模型', '推理模型', '中文支持'],
    is_active: true,
    sort_order: 4,
  },
  {
    provider_code: 'mock',
    provider_name: '模拟服务',
    base_endpoint: 'http://localhost:8080/mock',
    request_format: 'openai',
    requires_api_key: false,
    description: '用于开发和测试的模拟服务',
    features: ['开发测试', '无需API密钥'],
    is_active: true,
    sort_order: 99,
  },
]

// LLM模型数据
const LLM_MODELS = [
  // 阿里云模型
  {
    provider_code: 'alibaba',
    model_code: 'qwen-plus',
    model_name: 'Qwen-Plus (通义千问Plus)',
    description: '高性能通用模型，适合复杂推理任务',
    context_length: 32768,
    pricing_tier: 'medium',
    capabilities: ['文本生成', '代码生成', '数学推理', '多语言'],
    parameters: { temperature: 0.7, max_tokens: 8192 },
    is_default: true, // 阿里云的默认模型
    is_active: true,
    sort_order: 1,
  },
  {
    provider_code: 'alibaba',
    model_code: 'qwen-turbo',
    model_name: 'Qwen-Turbo (通义千问Turbo)',
    description: '快速响应模型，适合日常对话和简单任务',
    context_length: 8192,
    pricing_tier: 'low',
    capabilities: ['快速响应', '日常对话', '文本处理'],
    parameters: { temperature: 0.7, max_tokens: 4096 },
    is_default: false, // 非默认
    is_active: true,
    sort_order: 2,
  },
  // 百度模型
  {
    provider_code: 'baidu',
    model_code: 'ernie-4.0-8k',
    model_name: 'ERNIE-4.0-8K (文心一言4.0)',
    description: '百度最新一代大模型，中文能力突出',
    context_length: 8192,
    pricing_tier: 'high',
    capabilities: ['中文优化', '知识问答', '创意写作'],
    parameters: { temperature: 0.7, max_tokens: 4096 },
    is_default: true, // 百度的默认模型
    is_active: true,
    sort_order: 1,
  },
  // OpenAI模型
  {
    provider_code: 'openai',
    model_code: 'gpt-4o-mini',
    model_name: 'GPT-4o Mini',
    description: '轻量级高性能模型，成本更低',
    context_length: 128000,
    pricing_tier: 'medium',
    capabilities: ['高性价比', '快速响应', '多用途'],
    parameters: { temperature: 0.7, max_tokens: 16384 },
    is_default: true, // OpenAI的默认模型
    is_active: true,
    sort_order: 1,
  },
  // SiliconFlow 模型
  {
    provider_code: 'siliconflow',
    model_code: 'Qwen/Qwen3.5-27B',
    model_name: 'Qwen/Qwen3.5-27B',
    description: 'Qwen3.5 27B 模型，适合更复杂的生成与推理任务',
    context_length: 32768,
    pricing_tier: 'medium',
    capabilities: ['文本生成', '代码生成', '复杂推理', '中文优化'],
    parameters: { temperature: 0.7, max_tokens: 8192 },
    is_default: true,
    is_active: true,
    sort_order: 1,
  },
  {
    provider_code: 'siliconflow',
    model_code: 'Qwen/Qwen3.5-9B',
    model_name: 'Qwen/Qwen3.5-9B',
    description: 'Qwen3.5 9B 模型，平衡速度、成本与质量',
    context_length: 32768,
    pricing_tier: 'low',
    capabilities: ['文本生成', '日常推理', '代码生成', '中文优化'],
    parameters: { temperature: 0.7, max_tokens: 8192 },
    is_default: false,
    is_active: true,
    sort_order: 2,
  },
  {
    provider_code: 'siliconflow',
    model_code: 'Qwen/Qwen3.5-4B',
    model_name: 'Qwen/Qwen3.5-4B',
    description: 'Qwen3.5 4B 轻量模型，适合低成本快速调用',
    context_length: 32768,
    pricing_tier: 'low',
    capabilities: ['快速响应', '轻量生成', '基础代码生成', '中文支持'],
    parameters: { temperature: 0.7, max_tokens: 4096 },
    is_default: false,
    is_active: true,
    sort_order: 3,
  },
  // 模拟模型
  {
    provider_code: 'mock',
    model_code: 'mock-model',
    model_name: 'Mock Model (模拟模型)',
    description: '用于开发测试的模拟模型',
    context_length: 4096,
    pricing_tier: 'low',
    capabilities: ['测试专用'],
    parameters: { temperature: 0.7, max_tokens: 2048 },
    is_default: true, // 模拟的默认模型
    is_active: true,
    sort_order: 1,
  },
]

/**
 * 初始化LLM提供商数据
 */
export async function initLLMProviders(): Promise<void> {
  console.log('开始初始化LLM提供商数据...')

  for (const provider of LLM_PROVIDERS) {
    const { error } = await supabase.from('llm_api_providers').upsert(provider, {
      onConflict: 'provider_code',
      ignoreDuplicates: false,
    })

    if (error) {
      console.error(`插入提供商 ${provider.provider_code} 失败:`, error)
      throw error
    }
  }

  console.log(`成功初始化 ${LLM_PROVIDERS.length} 个LLM提供商`)
}

/**
 * 初始化LLM模型数据
 */
export async function initLLMModels(): Promise<void> {
  console.log('开始初始化LLM模型数据...')

  // 首先获取所有提供商的ID映射
  const { data: providers, error: providerError } = await supabase
    .from('llm_api_providers')
    .select('id, provider_code')

  if (providerError) {
    console.error('获取提供商数据失败:', providerError)
    throw providerError
  }

  const providerMap = new Map(providers?.map((p) => [p.provider_code, p.id]) || [])

  // 插入模型数据
  for (const model of LLM_MODELS) {
    const providerId = providerMap.get(model.provider_code)
    if (!providerId) {
      console.warn(`未找到提供商 ${model.provider_code}，跳过模型 ${model.model_code}`)
      continue
    }

    // 先检查模型是否已存在
    const { data: existingModel } = await supabase
      .from('llm_models')
      .select('id')
      .eq('provider_id', providerId)
      .eq('model_code', model.model_code)
      .single()

    const modelData = {
      provider_id: providerId,
      model_code: model.model_code,
      model_name: model.model_name,
      description: model.description,
      context_length: model.context_length,
      pricing_tier: model.pricing_tier,
      capabilities: model.capabilities,
      parameters: model.parameters,
      is_default: model.is_default,
      is_active: model.is_active,
      sort_order: model.sort_order,
    }

    let error
    if (existingModel) {
      // 更新现有模型
      const { error: updateError } = await supabase
        .from('llm_models')
        .update(modelData)
        .eq('id', existingModel.id)
      error = updateError
    } else {
      // 如果是默认模型，先清除该提供商的其他默认模型
      if (model.is_default) {
        await supabase
          .from('llm_models')
          .update({ is_default: false })
          .eq('provider_id', providerId)
          .eq('is_default', true)
      }

      // 插入新模型
      const { error: insertError } = await supabase.from('llm_models').insert(modelData)
      error = insertError
    }

    if (error) {
      console.error(`处理模型 ${model.model_code} 失败:`, error)
      throw error
    }
  }

  console.log(`成功初始化 ${LLM_MODELS.length} 个LLM模型`)
}

/**
 * 创建默认配置
 */
export async function createDefaultConfig(): Promise<void> {
  console.log('创建默认配置...')

  // 获取阿里通义提供商与 qwen-plus 模型，作为系统默认
  const { data: provider } = await supabase
    .from('llm_api_providers')
    .select('id')
    .eq('provider_code', 'alibaba')
    .single()

  if (!provider) {
    console.warn('未找到阿里通义提供商（alibaba），跳过创建默认配置')
    return
  }

  const { data: model } = await supabase
    .from('llm_models')
    .select('id')
    .eq('provider_id', provider.id)
    .eq('model_code', 'qwen-plus')
    .single()

  if (!model) {
    console.warn('未找到 qwen-plus 模型，跳过创建默认配置')
    return
  }

  // 创建默认配置（全局）
  const { error } = await supabase.from('user_llm_configs').upsert(
    {
      user_id: null, // 全局配置
      config_name: 'default',
      provider_id: provider.id,
      model_id: model.id,
      is_active: true,
    },
    {
      onConflict: 'user_id,config_name',
      ignoreDuplicates: false,
    },
  )

  if (error) {
    console.error('创建默认配置失败:', error)
    throw error
  }

  console.log('成功创建默认配置')
}

/**
 * 完整初始化LLM数据库
 */
export async function initLLMDatabase(): Promise<void> {
  try {
    await initLLMProviders()
    await initLLMModels()
    await createDefaultConfig()
    console.log('✅ LLM数据库初始化完成')
  } catch (error) {
    console.error('❌ LLM数据库初始化失败:', error)
    throw error
  }
}
