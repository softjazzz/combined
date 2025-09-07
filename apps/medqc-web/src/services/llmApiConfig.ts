/**
 * LLM API配置管理器 - 增强版
 * 支持多种大模型API的配置和切换，支持多模型选择
 */

// 模型选项接口
export interface ModelOption {
  value: string
  label: string
  description: string
  contextLength?: number
  pricing?: string
  features?: string[]
}

// 原有接口保持兼容
export interface LLMApiConfig {
  name: string
  displayName: string
  endpoint: string
  model: string
  requiresApiKey: boolean
  description: string
  features: string[]
}

// 增强的API配置接口
export interface EnhancedLLMApiConfig {
  name: string
  displayName: string
  endpoint: string
  defaultModel: string
  availableModels: ModelOption[] // 支持多模型选择
  requiresApiKey: boolean
  description: string
  features: string[]
  requestFormat: 'openai' | 'baidu' | 'custom' // API请求格式
}

// 预定义的API配置
export const LLM_API_CONFIGS: Record<string, LLMApiConfig> = {
  // OpenAI GPT-4
  openai: {
    name: 'openai',
    displayName: 'OpenAI GPT-4',
    endpoint: 'https://api.openai.com/v1/chat/completions',
    model: 'gpt-4',
    requiresApiKey: true,
    description: '最强大的通用大模型，医疗理解能力优秀',
    features: ['高准确率', '强推理能力', '多语言支持']
  },

  // 百度文心一言
  baidu: {
    name: 'baidu',
    displayName: '百度文心一言',
    endpoint: 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions',
    model: 'ERNIE-Bot-4',
    requiresApiKey: true,
    description: '百度自研大模型，中文理解能力强',
    features: ['中文优化', '企业级服务', '数据安全']
  },

  // 阿里通义千问 (修正端点)
  alibaba: {
    name: 'alibaba',
    displayName: '阿里通义千问',
    endpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
    model: 'qwen-plus',
    requiresApiKey: true,
    description: '阿里云大模型服务，企业级可靠性，兼容OpenAI格式',
    features: ['企业级', '高并发', '多模态', '中文优化']
  },

  // 腾讯混元
  tencent: {
    name: 'tencent',
    displayName: '腾讯混元',
    endpoint: 'https://hunyuan.tencentcloudapi.com/v1/chat/completions',
    model: 'hunyuan-pro',
    requiresApiKey: true,
    description: '腾讯自研大模型，医疗垂直能力强',
    features: ['医疗专业', '安全合规', '高性能']
  },

  // 智谱ChatGLM
  zhipu: {
    name: 'zhipu',
    displayName: '智谱ChatGLM',
    endpoint: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    model: 'glm-4',
    requiresApiKey: true,
    description: '清华智谱开源大模型，可本地部署',
    features: ['开源友好', '可本地部署', '中文优化']
  },

  // 本地部署模型
  local: {
    name: 'local',
    displayName: '本地部署模型',
    endpoint: 'http://localhost:8001/v1/chat/completions',
    model: 'medical-llm',
    requiresApiKey: false,
    description: '本地部署的医疗专用模型，数据完全私有',
    features: ['数据私有', '无网络依赖', '可定制']
  },

  // 模拟模式
  mock: {
    name: 'mock',
    displayName: '模拟模式',
    endpoint: '',
    model: 'mock',
    requiresApiKey: false,
    description: '用于开发测试的模拟模式，返回预设数据',
    features: ['开发测试', '无需API', '快速响应']
  }
}

/**
 * API配置管理器
 */
export class LLMApiConfigManager {
  private currentConfig: LLMApiConfig
  private apiKey: string = ''

  constructor(configName: string = 'mock') {
    this.currentConfig = LLM_API_CONFIGS[configName] || LLM_API_CONFIGS.mock
  }

  /**
   * 获取当前配置
   */
  getCurrentConfig(): LLMApiConfig {
    return this.currentConfig
  }

  /**
   * 切换API配置
   */
  switchConfig(configName: string, apiKey?: string): void {
    if (!LLM_API_CONFIGS[configName]) {
      throw new Error(`未知的API配置: ${configName}`)
    }

    this.currentConfig = LLM_API_CONFIGS[configName]
    
    if (apiKey) {
      this.apiKey = apiKey
    }

    console.log(`已切换到: ${this.currentConfig.displayName}`)
  }

  /**
   * 设置API密钥
   */
  setApiKey(apiKey: string): void {
    this.apiKey = apiKey
  }

  /**
   * 获取API密钥
   */
  getApiKey(): string {
    return this.apiKey
  }

  /**
   * 验证配置是否完整
   */
  validateConfig(): { valid: boolean; message: string } {
    if (this.currentConfig.requiresApiKey && !this.apiKey) {
      return {
        valid: false,
        message: `${this.currentConfig.displayName} 需要配置API密钥`
      }
    }

    return {
      valid: true,
      message: '配置有效'
    }
  }

  /**
   * 获取所有可用配置
   */
  static getAllConfigs(): LLMApiConfig[] {
    return Object.values(LLM_API_CONFIGS)
  }

  /**
   * 根据特性筛选配置
   */
  static getConfigsByFeature(feature: string): LLMApiConfig[] {
    return Object.values(LLM_API_CONFIGS).filter(config => 
      config.features.includes(feature)
    )
  }

  /**
   * 获取推荐配置
   */
  static getRecommendedConfigs(): {
    development: LLMApiConfig
    production: LLMApiConfig
    medical: LLMApiConfig
  } {
    return {
      development: LLM_API_CONFIGS.mock,      // 开发环境推荐
      production: LLM_API_CONFIGS.baidu,     // 生产环境推荐
      medical: LLM_API_CONFIGS.local         // 医疗场景推荐
    }
  }
}

/**
 * 创建配置好的LLM服务实例
 */
export function createLLMService(configName: string, apiKey?: string) {
  const configManager = new LLMApiConfigManager(configName)
  
  if (apiKey) {
    configManager.setApiKey(apiKey)
  }

  const validation = configManager.validateConfig()
  if (!validation.valid) {
    console.warn(`LLM配置警告: ${validation.message}`)
  }

  const config = configManager.getCurrentConfig()
  
  // 动态导入LLMService避免循环依赖
  return import('./llmServiceNew').then(({ LLMService }) => {
    return new LLMService({
      apiEndpoint: config.endpoint,
      apiKey: configManager.getApiKey(),
      model: config.model
    })
  })
}

/**
 * 快速配置函数
 */
export const quickConfigs = {
  // 开发测试
  development: () => createLLMService('mock'),
  
  // OpenAI GPT-4
  openai: (apiKey: string) => createLLMService('openai', apiKey),
  
  // 百度文心一言
  baidu: (apiKey: string) => createLLMService('baidu', apiKey),
  
  // 本地部署
  local: (endpoint?: string) => {
    const config = { ...LLM_API_CONFIGS.local }
    if (endpoint) {
      config.endpoint = endpoint
    }
    return createLLMService('local')
  }
}

// 导出默认配置管理器实例
export const defaultConfigManager = new LLMApiConfigManager('mock')

// =====================================================
// 增强的多模型配置 (新增)
// =====================================================

// 增强的API配置，支持多模型选择
export const ENHANCED_LLM_API_CONFIGS: Record<string, EnhancedLLMApiConfig> = {

  // 阿里通义千问系列 - 修正端点并支持多模型
  alibaba: {
    name: 'alibaba',
    displayName: '阿里通义千问',
    endpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
    defaultModel: 'qwen-plus',
    availableModels: [
      {
        value: 'qwen-plus',
        label: 'Qwen-Plus',
        description: '平衡性能和成本的选择，推荐使用',
        contextLength: 32768,
        pricing: '中',
        features: ['平衡性能', '中等成本', '推荐']
      },
      {
        value: 'qwen-turbo',
        label: 'Qwen-Turbo',
        description: '快速响应，适合简单任务',
        contextLength: 8192,
        pricing: '低',
        features: ['快速响应', '成本低']
      },
      {
        value: 'qwen-max',
        label: 'Qwen-Max',
        description: '最强性能，适合复杂任务',
        contextLength: 32768,
        pricing: '高',
        features: ['最强性能', '复杂推理']
      },
      {
        value: 'qwen2.5-14b-instruct',
        label: 'Qwen2.5-14B-Instruct',
        description: '14B参数指令调优模型',
        contextLength: 32768,
        pricing: '中',
        features: ['14B参数', '指令调优']
      },
      {
        value: 'qwen2.5-32b-instruct',
        label: 'Qwen2.5-32B-Instruct',
        description: '32B参数指令调优模型',
        contextLength: 32768,
        pricing: '高',
        features: ['32B参数', '指令调优']
      },
      {
        value: 'qwen3-235b-a22b-instruct-2507',
        label: 'Qwen3-235B',
        description: '超大参数模型，顶级性能',
        contextLength: 32768,
        pricing: '很高',
        features: ['超大参数', '顶级性能']
      },
      {
        value: 'qwen-flash-2025-07-28',
        label: 'Qwen Flash (2025-07-28)',
        description: '最新Flash版本，极速响应',
        contextLength: 32768,
        pricing: '低',
        features: ['极速响应', '最新版本']
      },
      {
        value: 'qwen3-30b-a3b-instruct-2507',
        label: 'Qwen3-30B-A3B',
        description: '30B参数指令模型',
        contextLength: 32768,
        pricing: '高',
        features: ['30B参数', '指令优化']
      },
      {
        value: 'qwen3-30b-a3b-instruct-2507',
        label: 'Qwen3-30B-A3B',
        description: '30B参数模型，高性能推理',
        contextLength: 32768,
        pricing: '高',
        features: ['高性能', '平衡推理', '多任务']
      },
      {
        value: 'qwen2.5-7b-1m',
        label: 'Qwen2.5-7B-1M',
        description: '7B参数模型，支持1M上下文长度',
        contextLength: 1048576,
        pricing: '中',
        features: ['超长上下文', '高效推理', '成本优化']
      },
      {
        value: 'qwen2.5-32b-instruct',
        label: 'Qwen2.5-32B',
        description: '32B参数模型，强大的推理能力',
        contextLength: 32768,
        pricing: '高',
        features: ['强推理', '多领域', '高准确率']
      },
      {
        value: 'qwen2.5-14b-instruct',
        label: 'Qwen2.5-14B',
        description: '14B参数模型，性能与成本平衡',
        contextLength: 32768,
        pricing: '中',
        features: ['平衡性能', '中等成本', '通用能力']
      },
      {
        value: 'qwen-flash-2025-07-28',
        label: 'Qwen Flash (2025-07-28)',
        description: '最新Flash版本，极速响应',
        contextLength: 8192,
        pricing: '低',
        features: ['极速响应', '最新版本', '高效处理']
      },
      {
        value: 'qwen3-4b',
        label: 'Qwen3-4B',
        description: '轻量级Qwen3模型，快速高效',
        contextLength: 32768,
        pricing: '低',
        features: ['轻量级', '快速响应', '成本友好']
      },
      {
        value: 'qwen3-8b',
        label: 'Qwen3-8B',
        description: '中等规模Qwen3模型，性能均衡',
        contextLength: 32768,
        pricing: '中',
        features: ['性能均衡', '多场景适用', '稳定可靠']
      },
      {
        value: 'qwen3-14b',
        label: 'Qwen3-14B',
        description: '大规模Qwen3模型，强大性能',
        contextLength: 32768,
        pricing: '高',
        features: ['大规模参数', '强大性能', '专业任务']
      }
    ],
    requiresApiKey: true,
    description: '阿里云大模型服务，企业级可靠性，兼容OpenAI格式',
    features: ['企业级', '高并发', '多模态', '中文优化'],
    requestFormat: 'openai' // 使用兼容模式，格式与OpenAI一致
  },

  // 百度文心一言系列
  baidu: {
    name: 'baidu',
    displayName: '百度文心一言',
    endpoint: 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions',
    defaultModel: 'ERNIE-4.0-8K',
    availableModels: [
      {
        value: 'ERNIE-4.0-8K',
        label: 'ERNIE-4.0-8K',
        description: '文心4.0标准版',
        contextLength: 8192,
        pricing: '中',
        features: ['中文优化', '企业级']
      },
      {
        value: 'ERNIE-4.0-Turbo-8K',
        label: 'ERNIE-4.0-Turbo-8K',
        description: '文心4.0加速版',
        contextLength: 8192,
        pricing: '低',
        features: ['快速响应', '成本低']
      },
      {
        value: 'ERNIE-3.5-8K',
        label: 'ERNIE-3.5-8K',
        description: '文心3.5经济版',
        contextLength: 8192,
        pricing: '很低',
        features: ['经济实惠', '基础功能']
      }
    ],
    requiresApiKey: true,
    description: '百度自研大模型，中文理解能力强',
    features: ['中文优化', '企业级服务', '数据安全'],
    requestFormat: 'baidu'
  },





  // 本地部署
  local: {
    name: 'local',
    displayName: '本地部署模型',
    endpoint: 'http://localhost:8001/v1/chat/completions',
    defaultModel: 'medical-llm',
    availableModels: [
      {
        value: 'medical-llm',
        label: 'Medical-LLM',
        description: '医疗专用模型',
        contextLength: 8192,
        pricing: '免费',
        features: ['医疗专业', '本地部署']
      }
    ],
    requiresApiKey: false,
    description: '本地部署的医疗专用模型，数据完全私有',
    features: ['数据私有', '无网络依赖', '可定制'],
    requestFormat: 'openai'
  },

  // 模拟模式
  mock: {
    name: 'mock',
    displayName: '模拟模式',
    endpoint: '',
    defaultModel: 'mock',
    availableModels: [
      {
        value: 'mock',
        label: 'Mock Model',
        description: '模拟测试模型',
        contextLength: 8192,
        pricing: '免费',
        features: ['开发测试', '快速响应']
      }
    ],
    requiresApiKey: false,
    description: '用于开发测试的模拟模式，返回预设数据',
    features: ['开发测试', '无需API', '快速响应'],
    requestFormat: 'openai'
  }
}

/**
 * 增强的API配置管理器
 */
export class EnhancedLLMApiConfigManager {
  private currentConfig: EnhancedLLMApiConfig
  private selectedModel: string
  private apiKey: string = ''

  constructor(configName: string = 'mock', model?: string) {
    this.currentConfig = ENHANCED_LLM_API_CONFIGS[configName] || ENHANCED_LLM_API_CONFIGS.mock
    this.selectedModel = model || this.currentConfig.defaultModel
  }

  /**
   * 切换API配置
   */
  switchConfig(configName: string, apiKey?: string): void {
    if (!ENHANCED_LLM_API_CONFIGS[configName]) {
      throw new Error(`未知的API配置: ${configName}`)
    }

    this.currentConfig = ENHANCED_LLM_API_CONFIGS[configName]
    this.selectedModel = this.currentConfig.defaultModel

    if (apiKey) {
      this.apiKey = apiKey
    }

    console.log(`已切换到: ${this.currentConfig.displayName}`)
  }

  /**
   * 切换模型
   */
  switchModel(modelValue: string): void {
    const availableModels = this.currentConfig.availableModels.map(m => m.value)
    if (!availableModels.includes(modelValue)) {
      throw new Error(`模型 ${modelValue} 不支持当前API服务商`)
    }

    this.selectedModel = modelValue
    console.log(`已切换模型到: ${modelValue}`)
  }

  /**
   * 获取当前配置
   */
  getCurrentConfig(): EnhancedLLMApiConfig {
    return this.currentConfig
  }

  /**
   * 获取当前选中的模型
   */
  getCurrentModel(): string {
    return this.selectedModel
  }

  /**
   * 获取当前选中的模型信息
   */
  getCurrentModelInfo(): ModelOption | undefined {
    return this.currentConfig.availableModels.find(m => m.value === this.selectedModel)
  }

  /**
   * 获取可用模型列表
   */
  getAvailableModels(): ModelOption[] {
    return this.currentConfig.availableModels
  }

  /**
   * 设置API密钥
   */
  setApiKey(apiKey: string): void {
    this.apiKey = apiKey
  }

  /**
   * 获取API密钥
   */
  getApiKey(): string {
    return this.apiKey
  }

  /**
   * 验证配置是否完整
   */
  validateConfig(): { valid: boolean; message: string } {
    if (this.currentConfig.requiresApiKey && !this.apiKey) {
      return {
        valid: false,
        message: `${this.currentConfig.displayName} 需要配置API密钥`
      }
    }

    return {
      valid: true,
      message: '配置有效'
    }
  }

  /**
   * 获取完整配置（包含选中的模型）
   */
  getFullConfig(): {
    config: EnhancedLLMApiConfig
    selectedModel: string
    modelInfo: ModelOption | undefined
    apiKey: string
  } {
    return {
      config: this.currentConfig,
      selectedModel: this.selectedModel,
      modelInfo: this.getCurrentModelInfo(),
      apiKey: this.apiKey
    }
  }

  /**
   * 获取所有可用配置
   */
  static getAllConfigs(): EnhancedLLMApiConfig[] {
    return Object.values(ENHANCED_LLM_API_CONFIGS)
  }
}
