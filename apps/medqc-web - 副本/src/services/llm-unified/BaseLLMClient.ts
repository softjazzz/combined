/**
 * LLM 客户端抽象基类
 * 定义所有 LLM 客户端的通用接口和行为
 */

import type {
  LLMConfig,
  CallOptions,
  LLMResponse,
  ExtractedMedicalData,
  ParseOptions,
  ParseResult
} from './types'
import { LLMConfigError, LLMAPIError, LLMParseError } from './types'

export abstract class BaseLLMClient {
  protected config: LLMConfig
  protected isInitialized = false

  constructor(config: LLMConfig) {
    this.config = config
  }

  // ==================== 抽象方法（子类必须实现） ====================

  /**
   * 初始化客户端
   */
  abstract initialize(): Promise<boolean>

  /**
   * 调用 LLM API
   */
  abstract callAPI(prompt: string, options?: CallOptions): Promise<LLMResponse>

  /**
   * 提取医疗数据
   */
  abstract extractMedicalData(text: string, options?: ParseOptions): Promise<ExtractedMedicalData>

  // ==================== 通用方法 ====================

  /**
   * 验证配置
   */
  protected validateConfig(): boolean {
    if (!this.config.apiKey) {
      throw new LLMConfigError('API Key 未配置')
    }
    if (!this.config.baseURL) {
      throw new LLMConfigError('Base URL 未配置')
    }
    if (!this.config.model) {
      throw new LLMConfigError('Model 未配置')
    }
    return true
  }

  /**
   * 处理错误
   */
  protected handleError(error: unknown, context?: string): never {
    const prefix = context ? `[${context}] ` : ''
    
    if (error instanceof LLMConfigError || error instanceof LLMAPIError || error instanceof LLMParseError) {
      throw error
    }
    
    if (error instanceof Error) {
      console.error(`${prefix}LLM Error:`, error)
      throw new LLMAPIError(`${prefix}${error.message}`, error)
    }
    
    console.error(`${prefix}Unknown error:`, error)
    throw new LLMAPIError(`${prefix}未知错误`, error)
  }

  /**
   * 构建请求头
   */
  protected buildHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.config.apiKey}`
    }
  }

  /**
   * 发送 HTTP 请求
   */
  protected async sendRequest(
    url: string,
    body: unknown,
    options?: { timeout?: number }
  ): Promise<Response> {
    const controller = new AbortController()
    const timeout = options?.timeout || this.config.timeout || 60000

    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: this.buildHeaders(),
        body: JSON.stringify(body),
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        const errorText = await response.text()
        throw new LLMAPIError(
          `API 请求失败: ${response.status} ${response.statusText}`,
          { status: response.status, body: errorText }
        )
      }

      return response
    } catch (error) {
      clearTimeout(timeoutId)
      
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new LLMAPIError('请求超时', { timeout })
      }
      
      throw error
    }
  }

  /**
   * 解析 JSON 响应
   */
  protected async parseJSONResponse<T = unknown>(response: Response): Promise<T> {
    try {
      return await response.json() as T
    } catch (error) {
      throw new LLMParseError('响应解析失败', error)
    }
  }

  /**
   * 验证响应数据
   */
  protected validateResponse(data: unknown): void {
    if (!data || typeof data !== 'object') {
      throw new LLMParseError('无效的响应数据')
    }
  }

  // ==================== Getter/Setter ====================

  /**
   * 获取当前配置
   */
  getCurrentConfig(): LLMConfig {
    return { ...this.config }
  }

  /**
   * 更新配置
   */
  updateConfig(updates: Partial<LLMConfig>): void {
    this.config = { ...this.config, ...updates }
    this.isInitialized = false
  }

  /**
   * 检查是否已初始化
   */
  isReady(): boolean {
    return this.isInitialized
  }

  /**
   * 获取提供商名称
   */
  getProviderName(): string {
    return this.config.provider
  }

  /**
   * 获取模型名称
   */
  getModelName(): string {
    return this.config.model
  }
}

