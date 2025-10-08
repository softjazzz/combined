/**
 * LLM 服务统一门面
 * 提供统一的接口，管理不同的 LLM 客户端
 */

import { BaseLLMClient } from './BaseLLMClient'
import { OpenAIClient } from './OpenAIClient'
import { DeepSeekClient } from './DeepSeekClient'
import { AliyunClient } from './AliyunClient'
import type {
  LLMConfig,
  ParseOptions,
  ParseResult,
  BatchParseResult,
  ExtractedMedicalData,
  CallOptions,
  LLMResponse
} from './types'
import { LLMConfigError } from './types'
import { llmConfigService, type UserLLMConfig as DBUserLLMConfig } from '../llmConfigService'

export class LLMServiceFacade {
  private client: BaseLLMClient | null = null
  private currentProvider: 'openai' | 'deepseek' | 'aliyun' | null = null

  /**
   * 从数据库加载配置并初始化
   */
  async loadConfigFromDatabase(configName: string = 'default', userId?: string): Promise<boolean> {
    try {
      const config = await llmConfigService.getConfigByName(configName, userId)

      if (!config) {
        console.warn(`配置 "${configName}" 不存在`)
        return false
      }

      return await this.initializeWithUserConfig(config)
    } catch (error) {
      console.error('加载配置失败:', error)
      return false
    }
  }

  /**
   * 使用用户配置初始化
   */
  async initializeWithUserConfig(userConfig: DBUserLLMConfig): Promise<boolean> {
    try {
      if (!userConfig.provider || !userConfig.model) {
        throw new LLMConfigError('配置缺少 provider 或 model 信息')
      }

      // 从数据库配置中提取 API key
      const apiKey = (userConfig as any).api_key_decrypted || ''

      const llmConfig: LLMConfig = {
        provider: this.normalizeProvider(userConfig.provider.provider_name),
        apiKey: apiKey,
        baseURL: userConfig.custom_endpoint || userConfig.provider.base_endpoint,
        model: userConfig.model.model_code,
        temperature: userConfig.custom_parameters?.temperature,
        maxTokens: userConfig.custom_parameters?.max_tokens
      }

      return await this.initialize(llmConfig.provider, llmConfig)
    } catch (error) {
      console.error('初始化失败:', error)
      return false
    }
  }

  /**
   * 初始化指定的 LLM 客户端
   */
  async initialize(
    provider: 'openai' | 'deepseek' | 'aliyun',
    config: LLMConfig
  ): Promise<boolean> {
    try {
      // 如果已经初始化了相同的提供商，直接返回
      if (this.client && this.currentProvider === provider) {
        this.client.updateConfig(config)
        return await this.client.initialize()
      }

      // 创建新的客户端
      switch (provider) {
        case 'openai':
          this.client = new OpenAIClient(config)
          break
        case 'deepseek':
          this.client = new DeepSeekClient(config)
          break
        case 'aliyun':
          this.client = new AliyunClient(config)
          break
        default:
          throw new LLMConfigError(`不支持的提供商: ${provider}`)
      }

      this.currentProvider = provider
      return await this.client.initialize()
    } catch (error) {
      console.error('LLM 服务初始化失败:', error)
      return false
    }
  }

  /**
   * 提取医疗数据（主要方法）
   */
  async extractMedicalData(
    text: string,
    options?: ParseOptions
  ): Promise<ExtractedMedicalData> {
    this.ensureInitialized()
    return await this.client!.extractMedicalData(text, options)
  }

  /**
   * 解析医疗文本
   */
  async parseMedicalText(text: string, options: ParseOptions = {}): Promise<ParseResult> {
    const startTime = Date.now()

    try {
      const data = await this.extractMedicalData(text, options)
      
      return {
        success: true,
        data,
        processingTime: Date.now() - startTime
      }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : '未知错误',
        processingTime: Date.now() - startTime
      }
    }
  }

  /**
   * 批量解析医疗文本
   */
  async parseBatchMedicalTexts(
    texts: string[],
    options: ParseOptions = {}
  ): Promise<BatchParseResult> {
    const startTime = Date.now()
    const results: ParseResult[] = []
    let successCount = 0
    let failureCount = 0

    for (const text of texts) {
      const result = await this.parseMedicalText(text, options)
      results.push(result)
      
      if (result.success) {
        successCount++
      } else {
        failureCount++
      }
    }

    return {
      success: true,
      results,
      totalProcessed: texts.length,
      successCount,
      failureCount,
      totalProcessingTime: Date.now() - startTime
    }
  }

  /**
   * 直接调用 LLM API
   */
  async callAPI(prompt: string, options?: CallOptions): Promise<LLMResponse> {
    this.ensureInitialized()
    return await this.client!.callAPI(prompt, options)
  }

  /**
   * 更新配置
   */
  updateConfig(updates: Partial<LLMConfig> | { pointerMode?: boolean; summaryMaxLength?: number }): void {
    if (this.client) {
      // 如果是简单的配置更新（pointerMode, summaryMaxLength）
      if ('pointerMode' in updates || 'summaryMaxLength' in updates) {
        // 这些配置暂时不影响客户端，可以忽略或存储
        console.log('配置已更新:', updates)
      } else {
        // 完整的 LLMConfig 更新
        this.client.updateConfig(updates as Partial<LLMConfig>)
      }
    }
  }

  /**
   * 获取当前配置
   */
  getCurrentConfig(): LLMConfig | null {
    return this.client?.getCurrentConfig() || null
  }

  /**
   * 获取用户配置
   */
  getUserConfig(): LLMConfig | null {
    return this.client?.getCurrentConfig() || null
  }

  /**
   * 检查是否已初始化
   */
  isReady(): boolean {
    return this.client?.isReady() || false
  }

  /**
   * 获取当前提供商
   */
  getCurrentProvider(): string | null {
    return this.currentProvider
  }

  // ==================== 私有辅助方法 ====================

  private ensureInitialized(): void {
    if (!this.client || !this.client.isReady()) {
      throw new LLMConfigError('LLM 服务未初始化，请先调用 initialize() 或 loadConfigFromDatabase()')
    }
  }

  private normalizeProvider(providerName: string): 'openai' | 'deepseek' | 'aliyun' {
    const normalized = providerName.toLowerCase()
    
    if (normalized.includes('openai')) return 'openai'
    if (normalized.includes('deepseek')) return 'deepseek'
    if (normalized.includes('aliyun') || normalized.includes('tongyi') || normalized.includes('通义')) return 'aliyun'
    
    // 默认返回 openai
    console.warn(`未知的提供商: ${providerName}，使用默认值 openai`)
    return 'openai'
  }
}

// 导出单例
export const llmService = new LLMServiceFacade()

