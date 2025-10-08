/**
 * DeepSeek LLM 客户端实现
 * DeepSeek API 兼容 OpenAI 格式
 */

import { OpenAIClient } from './OpenAIClient'
import type { LLMConfig } from './types'

export class DeepSeekClient extends OpenAIClient {
  constructor(config: LLMConfig) {
    // DeepSeek 使用 OpenAI 兼容的 API 格式
    super({
      ...config,
      baseURL: config.baseURL || 'https://api.deepseek.com/v1'
    })
  }

  async initialize(): Promise<boolean> {
    try {
      this.validateConfig()
      
      // DeepSeek 特定的初始化逻辑（如果需要）
      console.log('DeepSeek 客户端初始化...')
      
      // 测试连接
      const testPrompt = 'Hello'
      await this.callAPI(testPrompt, { maxTokens: 5 })
      
      this.isInitialized = true
      console.log('DeepSeek 客户端初始化成功')
      return true
    } catch (error) {
      console.error('DeepSeek 客户端初始化失败:', error)
      this.isInitialized = false
      return false
    }
  }

  /**
   * DeepSeek 特定的请求头
   */
  protected buildHeaders(): Record<string, string> {
    return {
      ...super.buildHeaders(),
      'X-Provider': 'DeepSeek'
    }
  }
}

