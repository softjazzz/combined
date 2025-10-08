/**
 * OpenAI LLM 客户端实现
 */

import { BaseLLMClient } from './BaseLLMClient'
import type {
  LLMConfig,
  CallOptions,
  LLMResponse,
  ExtractedMedicalData,
  ParseOptions
} from './types'
import { LLMAPIError, LLMParseError } from './types'

interface OpenAIMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

interface OpenAIRequest {
  model: string
  messages: OpenAIMessage[]
  temperature?: number
  max_tokens?: number
  top_p?: number
  frequency_penalty?: number
  presence_penalty?: number
  stream?: boolean
}

interface OpenAIResponse {
  id: string
  object: string
  created: number
  model: string
  choices: Array<{
    index: number
    message: {
      role: string
      content: string
    }
    finish_reason: string
  }>
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}

export class OpenAIClient extends BaseLLMClient {
  constructor(config: LLMConfig) {
    super(config)
  }

  async initialize(): Promise<boolean> {
    try {
      this.validateConfig()
      
      // 测试连接
      const testPrompt = 'Hello'
      await this.callAPI(testPrompt, { maxTokens: 5 })
      
      this.isInitialized = true
      return true
    } catch (error) {
      console.error('OpenAI 客户端初始化失败:', error)
      this.isInitialized = false
      return false
    }
  }

  async callAPI(prompt: string, options?: CallOptions): Promise<LLMResponse> {
    if (!this.isInitialized) {
      await this.initialize()
    }

    const requestBody: OpenAIRequest = {
      model: this.config.model,
      messages: [
        {
          role: 'user',
          content: prompt
        }
      ],
      temperature: options?.temperature ?? this.config.temperature ?? 0.7,
      max_tokens: options?.maxTokens ?? this.config.maxTokens ?? 2000,
      top_p: options?.topP,
      frequency_penalty: options?.frequencyPenalty,
      presence_penalty: options?.presencePenalty,
      stream: options?.stream ?? false
    }

    try {
      const url = `${this.config.baseURL}/chat/completions`
      const response = await this.sendRequest(url, requestBody)
      const data = await this.parseJSONResponse<OpenAIResponse>(response)

      this.validateResponse(data)

      if (!data.choices || data.choices.length === 0) {
        throw new LLMParseError('响应中没有生成内容')
      }

      return {
        content: data.choices[0].message.content,
        usage: {
          promptTokens: data.usage.prompt_tokens,
          completionTokens: data.usage.completion_tokens,
          totalTokens: data.usage.total_tokens
        },
        model: data.model,
        finishReason: data.choices[0].finish_reason
      }
    } catch (error) {
      this.handleError(error, 'OpenAI API Call')
    }
  }

  async extractMedicalData(
    text: string,
    options?: ParseOptions
  ): Promise<ExtractedMedicalData> {
    const prompt = this.buildMedicalExtractionPrompt(text, options)
    
    try {
      const response = await this.callAPI(prompt, {
        temperature: 0.3,
        maxTokens: options?.summaryMaxLength || 4000
      })

      return this.parseMedicalResponse(response.content, text)
    } catch (error) {
      this.handleError(error, 'Medical Data Extraction')
    }
  }

  // ==================== 私有辅助方法 ====================

  private buildMedicalExtractionPrompt(text: string, options?: ParseOptions): string {
    const tasks: string[] = []

    if (options?.extractPatientInfo !== false) {
      tasks.push('- 患者基本信息（姓名、年龄、性别、科室）')
    }

    if (options?.extractDiagnosis !== false) {
      tasks.push('- 诊断信息（主要诊断、次要诊断）')
    }

    if (options?.extractSurgeryInfo !== false) {
      tasks.push('- 手术信息（主要手术）')
    }

    if (options?.classifyDocuments) {
      tasks.push('- 文书分类（识别文书类型和标题）')
    }

    const prompt = `你是一个专业的医疗文本分析助手。请从以下病历文本中提取信息：

需要提取的信息：
${tasks.join('\n')}

病历文本：
${text}

请以 JSON 格式返回提取的信息，格式如下：
{
  "recordNumber": "病历号",
  "patientName": "患者姓名",
  "patientAge": 年龄,
  "patientGender": "性别",
  "department": "科室",
  "primaryDiagnosis": "主要诊断",
  "secondaryDiagnosis": ["次要诊断1", "次要诊断2"],
  "majorSurgery": "主要手术",
  "documents": [
    {
      "id": "文档ID",
      "type": "文档类型",
      "title": "文档标题",
      "content": "文档摘要",
      "confidence": 0.95
    }
  ],
  "confidence": 0.9
}

注意：
1. 如果某些信息无法提取，请使用空字符串或空数组
2. confidence 表示提取的置信度（0-1之间）
3. 只返回 JSON，不要包含其他说明文字`

    return prompt
  }

  private parseMedicalResponse(content: string, originalText: string): ExtractedMedicalData {
    try {
      // 尝试提取 JSON
      const jsonMatch = content.match(/\{[\s\S]*\}/)
      if (!jsonMatch) {
        throw new LLMParseError('响应中未找到 JSON 数据')
      }

      const data = JSON.parse(jsonMatch[0]) as Partial<ExtractedMedicalData>

      // 验证必需字段
      return {
        recordNumber: data.recordNumber || '',
        patientName: data.patientName || '未识别',
        patientAge: data.patientAge,
        patientGender: data.patientGender,
        department: data.department || '',
        primaryDiagnosis: data.primaryDiagnosis || '',
        secondaryDiagnosis: data.secondaryDiagnosis || [],
        majorSurgery: data.majorSurgery || '',
        documents: (data.documents || []).map(doc => ({
          ...doc,
          extractedAt: new Date()
        })),
        confidence: data.confidence || 0.5,
        content: originalText
      }
    } catch (error) {
      if (error instanceof SyntaxError) {
        throw new LLMParseError('JSON 解析失败', error)
      }
      throw error
    }
  }
}

