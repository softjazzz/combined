/**
 * 语义质控规则服务
 * 连接前端与Python语义规则引擎
 */

import { getAccessToken } from '@/utils/auth-token'
import { resolveApiBaseUrl } from '@/utils/api-helpers'

export interface SemanticRuleDefinition {
  rule_id: string
  rule_name: string
  description: string
  category: string
  defect_level: string // 支持中文和英文值
  deduction_score?: number
  is_veto_defect: boolean
  complexity: string // 支持中文和英文值
  system_role: string
  task_description: string
  input_format: Record<string, string>
  evaluation_criteria: string[]
  output_format: Record<string, string>
  prompt_template: string
}

export interface SemanticRuleResult {
  rule_id: string
  rule_name: string
  compliant: boolean
  confidence: number
  evidence: string
  reasoning: string
  defect_details?: Record<string, unknown>
  execution_time: number
  token_usage?: {
    prompt: number
    completion: number
    total: number
  }
}

export interface SemanticRuleExecutionStats {
  total_executions: number
  successful_executions: number
  failed_executions: number
  total_tokens: number
  total_time: number
  success_rate: number
  avg_execution_time: number
}

export interface CustomRuleRequest {
  rule_name: string
  description: string
  natural_language_rule: string
  category: string
  severity: 'critical' | 'major' | 'minor'
  examples?: string[]
}

export class SemanticRulesService {
  private baseURL: string

  constructor() {
    this.baseURL = resolveApiBaseUrl()
  }

  private buildHeaders(includeJson: boolean = true): Record<string, string> {
    const headers: Record<string, string> = {}
    const token = getAccessToken()
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
    if (includeJson) {
      headers['Content-Type'] = 'application/json'
    }
    return headers
  }

  // ------------------- CRUD & Import/Export -------------------

  async create(rule: Partial<SemanticRuleDefinition>) {
    const res = await fetch(`${this.baseURL}/api/v1/semantic-rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rule),
    })
    if (!res.ok) throw new Error('创建规则失败')
    const data = await res.json()
    return data.rule as SemanticRuleDefinition
  }

  async update(ruleId: string, patch: Partial<SemanticRuleDefinition>) {
    const res = await fetch(`${this.baseURL}/api/v1/semantic-rules/${ruleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    if (!res.ok) throw new Error('更新规则失败')
    const data = await res.json()
    return data.rule as SemanticRuleDefinition
  }

  async remove(ruleId: string) {
    const res = await fetch(`${this.baseURL}/api/v1/semantic-rules/${ruleId}`, {
      method: 'DELETE',
    })
    if (!res.ok) throw new Error('删除规则失败')
    const data = await res.json()
    return data.deleted as number
  }

  async import(rules: Partial<SemanticRuleDefinition>[]) {
    const res = await fetch(`${this.baseURL}/api/v1/semantic-rules/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules }),
    })
    if (!res.ok) throw new Error('导入规则失败')
    const data = await res.json()
    return data.inserted as number
  }

  async export() {
    const res = await fetch(`${this.baseURL}/api/v1/semantic-rules/export`)
    if (!res.ok) throw new Error('导出规则失败')
    const data = await res.json()
    return (data.rules || []) as SemanticRuleDefinition[]
  }

  /**
   * 获取所有语义规则
   */
  async getAllSemanticRules(): Promise<{
    success: boolean
    data?: SemanticRuleDefinition[]
    error?: string
  }> {
    try {
      const response = await fetch(`${this.baseURL}/api/v1/semantic-rules`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '获取语义规则失败')
      }

      const data = await response.json()
      return {
        success: true,
        data: data.rules || [],
      }
    } catch (error) {
      console.error('获取语义规则失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '获取语义规则失败',
      }
    }
  }

  /**
   * 获取单个语义规则详情
   */
  async getSemanticRule(ruleId: string): Promise<{
    success: boolean
    data?: SemanticRuleDefinition
    error?: string
  }> {
    try {
      const response = await fetch(`${this.baseURL}/api/v1/semantic-rules/${ruleId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '获取规则详情失败')
      }

      const data = await response.json()
      return {
        success: true,
        data: data.rule,
      }
    } catch (error) {
      console.error('获取规则详情失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '获取规则详情失败',
      }
    }
  }

  /**
   * 执行语义规则测试
   */
  async executeSemanticRule(
    ruleId: string,
    inputData: Record<string, unknown>,
    useMockLLM: boolean = false,
  ): Promise<{
    success: boolean
    data?: SemanticRuleResult
    error?: string
  }> {
    try {
      const response = await fetch(`${this.baseURL}/api/v1/semantic-rules/${ruleId}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          input_data: inputData,
          use_mock_llm: useMockLLM,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '规则执行失败')
      }

      const data = await response.json()
      return {
        success: true,
        data: data.result,
      }
    } catch (error) {
      console.error('规则执行失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '规则执行失败',
      }
    }
  }

  /**
   * 批量执行语义规则
   */
  async executeBatchSemanticRules(
    ruleIds: string[],
    inputData: Record<string, unknown>,
    useMockLLM: boolean = false,
  ): Promise<{
    success: boolean
    data?: SemanticRuleResult[]
    error?: string
  }> {
    try {
      const response = await fetch(`${this.baseURL}/api/v1/semantic-rules/batch-execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rule_ids: ruleIds,
          input_data: inputData,
          use_mock_llm: useMockLLM,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '批量执行失败')
      }

      const data = await response.json()
      return {
        success: true,
        data: data.results || [],
      }
    } catch (error) {
      console.error('批量执行失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '批量执行失败',
      }
    }
  }

  /**
   * 创建自定义语义规则
   */
  async createCustomRule(request: CustomRuleRequest): Promise<{
    success: boolean
    data?: SemanticRuleDefinition
    error?: string
  }> {
    try {
      const response = await fetch(`${this.baseURL}/api/v1/semantic-rules/custom`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '创建自定义规则失败')
      }

      const data = await response.json()
      return {
        success: true,
        data: data.rule,
      }
    } catch (error) {
      console.error('创建自定义规则失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '创建自定义规则失败',
      }
    }
  }

  /**
   * 获取语义规则引擎统计信息
   */
  async getEngineStats(): Promise<{
    success: boolean
    data?: SemanticRuleExecutionStats
    error?: string
  }> {
    try {
      const response = await fetch(`${this.baseURL}/api/v1/semantic-rules/stats`, {
        method: 'GET',
        headers: this.buildHeaders(),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '获取统计信息失败')
      }

      const data = await response.json()
      return {
        success: true,
        data: data.stats,
      }
    } catch (error) {
      console.error('获取统计信息失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '获取统计信息失败',
      }
    }
  }

  /**
   * 验证LLM连接状态
   */
  async validateLLMConnection(): Promise<{
    success: boolean
    data?: {
      real_llm_available: boolean
      mock_mode: boolean
      provider: string
      model: string
    }
    error?: string
  }> {
    try {
      const response = await fetch(`${this.baseURL}/api/v1/semantic-rules/validate-llm`, {
        method: 'GET',
        headers: this.buildHeaders(),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'LLM连接验证失败')
      }

      const data = await response.json()
      return {
        success: true,
        data: data.connection_info,
      }
    } catch (error) {
      console.error('LLM连接验证失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : 'LLM连接验证失败',
      }
    }
  }
}

// 导出单例实例
export const semanticRulesService = new SemanticRulesService()
