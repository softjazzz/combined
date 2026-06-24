/**
 * 阿里云通义千问 LLM 客户端实现
 * 阿里云 API 也兼容 OpenAI 格式
 */

import { OpenAIClient } from './OpenAIClient'
import type { LLMConfig } from './types'

export class AliyunClient extends OpenAIClient {
  constructor(config: LLMConfig) {
    // 阿里云通义千问使用 OpenAI 兼容的 API 格式
    super({
      ...config,
      baseURL: config.baseURL || 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    })
  }

  async initialize(): Promise<boolean> {
    try {
      this.validateConfig()
      
      // 阿里云特定的初始化逻辑（如果需要）
      console.log('阿里云通义千问客户端初始化...')
      
      // 测试连接
      const testPrompt = 'Hello'
      await this.callAPI(testPrompt, { maxTokens: 5 })
      
      this.isInitialized = true
      console.log('阿里云通义千问客户端初始化成功')
      return true
    } catch (error) {
      console.error('阿里云通义千问客户端初始化失败:', error)
      this.isInitialized = false
      return false
    }
  }

  /**
   * 阿里云特定的请求头
   */
  protected buildHeaders(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.config.apiKey}`,
      'X-DashScope-SSE': 'disable' // 禁用 SSE
    }
  }
}

