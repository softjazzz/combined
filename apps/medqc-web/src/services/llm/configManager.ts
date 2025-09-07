/**
 * LLM配置管理器 - 负责管理LLM服务的配置
 */

import { LLMConfig } from '@/types/medical'
import { llmConfigService, type UserLLMConfig } from '../llmConfigService'

export class LLMConfigManager {
  private currentConfig: UserLLMConfig | null = null
  private apiEndpoint: string
  private apiKey: string
  private model: string
  private pointerMode: boolean
  private summaryMaxLength: number

  constructor(config: LLMConfig = {}) {
    // 使用配置参数，支持运行时传入API信息
    this.apiEndpoint = config.apiEndpoint || 'https://api.openai.com/v1/chat/completions'
    this.apiKey = config.apiKey || ''
    this.model = config.model || 'gpt-4'

    // 从环境变量读取指针模式与摘要长度（可被传入参数覆盖）
    const envPointer = this.getEnvBoolean('VITE_LLM_POINTER_MODE', true)
    const envSumLen = this.getEnvNumber('VITE_LLM_SUMMARY_MAXLEN', 80)

    // 默认启用指针模式以节省token和避免截断
    this.pointerMode = config.pointerMode !== undefined ? config.pointerMode : true
    this.summaryMaxLength = config.summaryMaxLength !== undefined ? config.summaryMaxLength : envSumLen
  }

  /**
   * 从数据库加载LLM配置
   */
  async loadConfigFromDatabase(configName: string = 'default', userId?: string): Promise<boolean> {
    try {
      // 1) 先尝试加载用户级默认配置
      let config = await llmConfigService.getConfigByName(configName, userId)

      // 2) 若用户级不存在，则回退到全局默认（user_id = null）
      if (!config) {
        config = await llmConfigService.getConfigByName(configName)
      }

      if (!config) {
        console.warn(`未找到LLM配置: ${configName}`)
        return false
      }

      this.currentConfig = config

      // 更新服务配置
      if (config.provider) {
        this.apiEndpoint = config.custom_endpoint || config.provider.base_endpoint
      }

      if ((config as any).api_key_decrypted) {
        this.apiKey = (config as any).api_key_decrypted
      }

      if (config.model) {
        this.model = config.model.model_code
      }

      console.log(`已加载LLM配置: ${config.config_name}`, {
        provider: config.provider?.provider_name,
        model: config.model?.model_name,
        endpoint: this.apiEndpoint
      })

      return true
    } catch (error) {
      console.error('加载LLM配置失败:', error)
      return false
    }
  }

  /**
   * 获取当前配置信息
   */
  getCurrentConfig(): UserLLMConfig | null {
    return this.currentConfig
  }

  /**
   * 更新LLM服务配置
   */
  updateConfig(config: LLMConfig) {
    if (config.apiEndpoint) this.apiEndpoint = config.apiEndpoint
    if (config.apiKey !== undefined) this.apiKey = config.apiKey
    if (config.model) this.model = config.model
    if (config.pointerMode !== undefined) this.pointerMode = !!config.pointerMode
    if (config.summaryMaxLength !== undefined) {
      this.summaryMaxLength = Math.max(0, Math.min(80, config.summaryMaxLength))
    }

    console.log('LLM服务配置已更新:', {
      endpoint: this.apiEndpoint,
      hasApiKey: !!this.apiKey,
      model: this.model,
      pointerMode: this.pointerMode,
      summaryMaxLength: this.summaryMaxLength
    })
  }

  /**
   * 获取API端点
   */
  getApiEndpoint(): string {
    return this.apiEndpoint
  }

  /**
   * 获取API密钥
   */
  getApiKey(): string {
    return this.apiKey
  }

  /**
   * 获取模型名称
   */
  getModel(): string {
    return this.model
  }

  /**
   * 获取指针模式状态
   */
  getPointerMode(): boolean {
    return this.pointerMode
  }

  /**
   * 获取摘要最大长度
   */
  getSummaryMaxLength(): number {
    return this.summaryMaxLength
  }

  /**
   * 检查配置是否完整
   */
  isConfigValid(): boolean {
    return !!(this.apiEndpoint && this.apiKey && this.model)
  }

  /**
   * 获取配置摘要
   */
  getConfigSummary(): {
    provider: string
    model: string
    endpoint: string
    hasApiKey: boolean
    pointerMode: boolean
    summaryMaxLength: number
  } {
    return {
      provider: this.currentConfig?.provider?.provider_name || '未知',
      model: this.currentConfig?.model?.model_name || this.model,
      endpoint: this.apiEndpoint,
      hasApiKey: !!this.apiKey,
      pointerMode: this.pointerMode,
      summaryMaxLength: this.summaryMaxLength
    }
  }

  /**
   * 构建API请求配置
   */
  buildAPIRequest(prompt: string): any {
    // OpenAI格式 (包括阿里云DashScope兼容模式)
    if (this.apiEndpoint.includes('openai.com') || this.apiEndpoint.includes('dashscope.aliyuncs.com')) {
      return {
        model: this.model,
        messages: [
          {
            role: 'system',
            content: '你是一个专业的医疗信息抽取助手。严格要求：只输出一个有效的JSON对象；不要输出任何解释、前后缀、自然语言、Markdown代码块或```围栏；不要换行说明。'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.1,
        top_p: 0,
        max_tokens: 1500,
        stop: ['```'],
        response_format: { type: 'json_object' as any }
      }
    }

    // 百度文心一言格式
    if (this.apiEndpoint.includes('baidubce.com')) {
      return {
        messages: [
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.1,
        top_p: 0.8,
        penalty_score: 1.0
      }
    }

    // 智谱ChatGLM格式 (也使用OpenAI兼容格式)
    if (this.apiEndpoint.includes('bigmodel.cn')) {
      return {
        model: this.model,
        messages: [
          {
            role: 'system',
            content: '你是一个专业的医疗信息抽取助手，请严格按照JSON格式输出结果。'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: 0.1
      }
    }

    // 默认使用OpenAI兼容格式 (大多数API都支持)
    return {
      model: this.model,
      messages: [
        {
          role: 'system',
          content: '你是一个专业的医疗信息抽取助手，请严格按照JSON格式输出结果。'
        },
        {
          role: 'user',
          content: prompt
        }
      ],
      temperature: 0.1,
      max_tokens: 4000
    }
  }

  /**
   * 获取环境变量布尔值
   */
  private getEnvBoolean(key: string, defaultValue: boolean): boolean {
    const value = import.meta.env[key]
    if (value === undefined) return defaultValue
    return value === 'true' || value === '1'
  }

  /**
   * 获取环境变量数值
   */
  private getEnvNumber(key: string, defaultValue: number): number {
    const value = import.meta.env[key]
    if (value === undefined) return defaultValue
    const parsed = parseInt(value, 10)
    return isNaN(parsed) ? defaultValue : parsed
  }

  /**
   * 重置配置到默认值
   */
  resetToDefaults(): void {
    this.apiEndpoint = 'https://api.openai.com/v1/chat/completions'
    this.apiKey = ''
    this.model = 'gpt-4'
    this.pointerMode = true
    this.summaryMaxLength = 80
    this.currentConfig = null
  }

  /**
   * 导出配置
   */
  exportConfig(): LLMConfig {
    return {
      apiEndpoint: this.apiEndpoint,
      apiKey: this.apiKey,
      model: this.model,
      pointerMode: this.pointerMode,
      summaryMaxLength: this.summaryMaxLength
    }
  }

  /**
   * 从配置对象导入
   */
  importConfig(config: LLMConfig): void {
    this.updateConfig(config)
  }
}
