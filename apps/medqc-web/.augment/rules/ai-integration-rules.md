---
title: "AI集成开发规范"
description: "DeepSeek AI集成的开发标准和最佳实践"
version: "2.0"
category: "ai"
priority: "high"
type: "manual"
---
# AI集成开发规范

## 🤖 AI服务集成原则

### 1. AI服务封装
```typescript
// services/ai-service.ts
export class AIService {
  private readonly apiKey: string
  private readonly baseURL: string
  private readonly timeout: number = 30000

  constructor() {
    this.apiKey = process.env.VITE_DEEPSEEK_API_KEY!
    this.baseURL = process.env.VITE_DEEPSEEK_BASE_URL!
    
    if (!this.apiKey) {
      throw new Error('DeepSeek API密钥未配置')
    }
  }

  async analyzeQuality(prompt: string, context: MedicalRecord): Promise<AIAnalysisResult> {
    try {
      const response = await this.makeRequest({
        model: 'deepseek-chat',
        messages: [
          {
            role: 'system',
            content: this.getSystemPrompt()
          },
          {
            role: 'user',
            content: this.buildAnalysisPrompt(prompt, context)
          }
        ],
        temperature: 0.1, // 降低随机性，提高一致性
        max_tokens: 1000
      })

      return this.parseAnalysisResult(response)
    } catch (error) {
      console.error('AI质量分析失败:', error)
      throw new AIServiceError('AI分析服务暂时不可用', error)
    }
  }

  private getSystemPrompt(): string {
    return `
你是一个专业的医疗质控专家，负责评估病历质量。
请严格按照医疗行业标准和质控规范进行分析。
分析结果必须客观、准确、有建设性。

评估标准：
1. 完整性：信息是否完整
2. 一致性：信息是否前后一致
3. 合理性：医疗决策是否合理
4. 及时性：时间节点是否符合要求

输出格式：
{
  "score": 扣分分数(0-100),
  "level": "pass|warning|fail",
  "message": "简要说明",
  "suggestions": ["改进建议1", "改进建议2"],
  "details": "详细分析"
}
`
  }
}
```

### 2. 错误处理和重试机制
```typescript
export class AIServiceError extends Error {
  constructor(
    message: string,
    public readonly originalError?: any,
    public readonly retryable: boolean = true
  ) {
    super(message)
    this.name = 'AIServiceError'
  }
}

export class AIRetryManager {
  private readonly maxRetries = 3
  private readonly baseDelay = 1000

  async executeWithRetry<T>(
    operation: () => Promise<T>,
    context: string
  ): Promise<T> {
    let lastError: Error

    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        return await operation()
      } catch (error) {
        lastError = error as Error
        
        if (!this.shouldRetry(error, attempt)) {
          break
        }

        const delay = this.calculateDelay(attempt)
        console.warn(`AI操作失败，${delay}ms后重试 (${attempt}/${this.maxRetries}):`, error)
        await this.sleep(delay)
      }
    }

    throw new AIServiceError(
      `AI操作在${this.maxRetries}次重试后仍然失败: ${context}`,
      lastError
    )
  }

  private shouldRetry(error: any, attempt: number): boolean {
    if (attempt >= this.maxRetries) return false
    
    // 网络错误或服务器错误可以重试
    if (error.code === 'NETWORK_ERROR' || error.status >= 500) {
      return true
    }
    
    // API限流可以重试
    if (error.status === 429) {
      return true
    }
    
    return false
  }

  private calculateDelay(attempt: number): number {
    return this.baseDelay * Math.pow(2, attempt - 1) // 指数退避
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }
}
```

### 3. 提示词模板管理
```typescript
// config/ai-prompts.ts
export const AI_PROMPTS = {
  QUALITY_ANALYSIS: {
    COMPLETENESS: `
请评估以下病历的完整性：
{medical_record}

重点检查：
1. 患者基本信息是否完整
2. 病史记录是否详细
3. 检查结果是否齐全
4. 诊疗过程是否完整记录

请给出具体的缺失项目和改进建议。
`,
    
    CONSISTENCY: `
请分析以下病历的一致性：
{medical_record}

重点检查：
1. 入院诊断与出院诊断的一致性
2. 症状与检查结果的一致性
3. 治疗方案与诊断的一致性
4. 时间逻辑的一致性

请指出不一致之处并提供解释。
`,
    
    RATIONALITY: `
请评估以下医疗决策的合理性：
患者信息：{patient_info}
诊断：{diagnosis}
治疗方案：{treatment}

评估要点：
1. 诊断是否准确
2. 治疗方案是否适当
3. 用药是否合理
4. 是否遵循临床指南

请提供专业的医学评估意见。
`
  },
  
  DIAGNOSIS_ANALYSIS: `
请分析以下诊断的准确性和完整性：
症状：{symptoms}
检查结果：{test_results}
当前诊断：{current_diagnosis}

请评估：
1. 诊断是否支持症状和检查结果
2. 是否遗漏重要诊断
3. 诊断的准确性和特异性
4. 是否需要进一步检查
`
}

export class PromptBuilder {
  static build(template: string, variables: Record<string, any>): string {
    let prompt = template
    
    for (const [key, value] of Object.entries(variables)) {
      const placeholder = `{${key}}`
      prompt = prompt.replace(new RegExp(placeholder, 'g'), String(value))
    }
    
    return prompt
  }
  
  static validateTemplate(template: string, requiredVars: string[]): boolean {
    for (const variable of requiredVars) {
      if (!template.includes(`{${variable}}`)) {
        console.warn(`提示词模板缺少必需变量: ${variable}`)
        return false
      }
    }
    return true
  }
}
```

### 4. AI分析结果处理
```typescript
// utils/ai-result-parser.ts
export interface AIAnalysisResult {
  score: number
  level: 'pass' | 'warning' | 'fail'
  message: string
  suggestions: string[]
  details?: string
  confidence?: number
}

export class AIResultParser {
  static parse(rawResponse: string): AIAnalysisResult {
    try {
      // 尝试解析JSON格式
      const parsed = JSON.parse(rawResponse)
      return this.validateAndNormalize(parsed)
    } catch (error) {
      // 如果不是JSON，尝试从文本中提取信息
      return this.parseFromText(rawResponse)
    }
  }

  private static validateAndNormalize(data: any): AIAnalysisResult {
    const result: AIAnalysisResult = {
      score: this.normalizeScore(data.score),
      level: this.normalizeLevel(data.level),
      message: String(data.message || ''),
      suggestions: Array.isArray(data.suggestions) ? data.suggestions : [],
      details: data.details ? String(data.details) : undefined,
      confidence: data.confidence ? Number(data.confidence) : undefined
    }

    // 验证必需字段
    if (result.score < 0 || result.score > 100) {
      throw new Error(`无效的分数值: ${result.score}`)
    }

    if (!['pass', 'warning', 'fail'].includes(result.level)) {
      throw new Error(`无效的级别值: ${result.level}`)
    }

    return result
  }

  private static normalizeScore(score: any): number {
    const num = Number(score)
    if (isNaN(num)) return 0
    return Math.max(0, Math.min(100, num))
  }

  private static normalizeLevel(level: any): 'pass' | 'warning' | 'fail' {
    const str = String(level).toLowerCase()
    if (['pass', 'passed', '通过'].includes(str)) return 'pass'
    if (['warning', 'warn', '警告'].includes(str)) return 'warning'
    return 'fail'
  }
}
```

### 5. AI服务监控和日志
```typescript
// utils/ai-monitor.ts
export class AIServiceMonitor {
  private static metrics = {
    totalRequests: 0,
    successfulRequests: 0,
    failedRequests: 0,
    averageResponseTime: 0,
    lastError: null as Error | null
  }

  static recordRequest(startTime: number, success: boolean, error?: Error) {
    const responseTime = Date.now() - startTime
    
    this.metrics.totalRequests++
    if (success) {
      this.metrics.successfulRequests++
    } else {
      this.metrics.failedRequests++
      this.metrics.lastError = error || null
    }
    
    // 更新平均响应时间
    this.metrics.averageResponseTime = 
      (this.metrics.averageResponseTime * (this.metrics.totalRequests - 1) + responseTime) / 
      this.metrics.totalRequests

    // 记录详细日志
    console.log('AI服务调用记录:', {
      success,
      responseTime,
      error: error?.message,
      metrics: this.getMetrics()
    })
  }

  static getMetrics() {
    return {
      ...this.metrics,
      successRate: this.metrics.totalRequests > 0 
        ? (this.metrics.successfulRequests / this.metrics.totalRequests * 100).toFixed(2) + '%'
        : '0%'
    }
  }

  static resetMetrics() {
    this.metrics = {
      totalRequests: 0,
      successfulRequests: 0,
      failedRequests: 0,
      averageResponseTime: 0,
      lastError: null
    }
  }
}
```

## 🔧 AI集成最佳实践

### 1. 性能优化
- 使用合适的温度参数(0.1-0.3)保证结果一致性
- 限制最大token数量避免超时
- 实现请求缓存减少重复调用
- 使用批量处理提高效率

### 2. 安全考虑
- API密钥安全存储和轮换
- 输入数据脱敏处理
- 输出结果验证和过滤
- 访问频率限制

### 3. 用户体验
- 提供加载状态指示
- 实现优雅的错误处理
- 支持操作取消
- 提供分析进度反馈

## 🚨 AI集成注意事项
1. **不要完全依赖AI结果** - AI分析仅作为辅助工具
2. **保护患者隐私** - 发送给AI的数据必须脱敏
3. **处理网络异常** - 实现完善的错误处理和重试机制
4. **监控服务质量** - 记录和分析AI服务的性能指标
5. **版本兼容性** - 考虑AI模型更新对系统的影响

## 📋 AI集成检查清单
- [ ] API密钥配置正确
- [ ] 实现了错误处理和重试
- [ ] 提示词模板经过验证
- [ ] 结果解析逻辑完整
- [ ] 包含性能监控
- [ ] 用户体验友好
- [ ] 数据隐私保护到位