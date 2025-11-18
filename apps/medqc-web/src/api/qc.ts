export interface TestQCRulePayload {
  rule_id: string
  medical_text: string
}

export interface QCIssue {
  description: string
  evidence?: string
}

export type QCStatus = 'compliant' | 'non_compliant' | 'not_applicable' | 'uncertain' | 'error'

export interface QCApplicability {
  is_applicable: boolean
  reason?: string
  method?: string
}

export interface TestQCRuleData {
  rule_id: string
  rule_name?: string
  is_compliant: boolean
  status?: QCStatus
  issues?: QCIssue[]
  findings?: string
  evidence?: string
  suggestion?: string
  confidence?: number
  llm_raw_output?: string
  applicability?: QCApplicability
  not_applicable?: boolean
  not_applicable_reason?: string
  evidence_verified?: boolean
  evidence_span?: [number, number] | null
  metadata?: Record<string, any>
}

export interface TestQCRuleResponse {
  success: boolean
  data?: TestQCRuleData
  message?: string
  status?: number
  raw?: unknown
}

/**
 * 调用 /api/v1/qc/sichuan/test-rule
 */
export async function testQCRule(payload: TestQCRulePayload): Promise<TestQCRuleResponse> {
  try {
    const response = await fetch('/api/v1/qc/sichuan/test-rule', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })

    const result = await response.json().catch(() => ({}))

    if (!response.ok) {
      return {
        success: false,
        message: result?.detail || result?.message || response.statusText,
        status: response.status,
        raw: result
      }
    }

    // API 统一返回 { success, data, error/message }
    if (result?.success === false) {
      return {
        success: false,
        message: result?.error || result?.message || '质控评估失败',
        status: response.status,
        raw: result
      }
    }

    return {
      success: true,
      data: result?.data as TestQCRuleData,
      message: result?.message,
      raw: result
    }
  } catch (error: any) {
    return {
      success: false,
      message: error?.message || '网络异常或服务器不可用'
    }
  }
}

// ============= 批量质控接口（优化版） =============

export interface BatchQCEvaluatePayload {
  document_id: string
  document_content: string
  document_type: string
  rule_ids: string[]
  persist?: boolean
  prompt_mode?: string  // 提示词优化方案：current/plan_a/plan_b/plan_c
}

export interface BatchQCResult {
  rule_id: string
  rule_name: string
  is_compliant: boolean
  status?: QCStatus
  applicability?: QCApplicability
  not_applicable?: boolean
  not_applicable_reason?: string
  evidence_verified?: boolean
  findings?: string
  evidence?: string
  suggestion?: string
  confidence?: number
  metadata?: Record<string, any>
}

export interface BatchQCEvaluateResponse {
  success: boolean
  data?: {
    document_id: string
    evaluation_summary: {
      compliance_rate: number
      issues_found?: number
      total_rules?: number
      compliant_rules?: number
      not_applicable?: number
      overall_grade?: string
      critical_violations?: number
      model?: string  // 使用的模型名称
    }
    evaluation_results?: BatchQCResult[]
    performance_metrics?: {
      processing_time: number
      token_usage: number
      estimated_cost: number
    }
    optimization_metrics?: {
      token_savings_rate: number
      cost_savings: number
    }
    prompt_mode?: string  // 提示词优化方案
    llm_info?: {
      model?: string
      api_endpoint?: string
    }
  }
  message?: string
  status?: number
}

/**
 * 批量质控评估（优化版提示词）
 * 一次性评估多个规则，节省80% Token使用量
 */
export async function batchEvaluateQC(payload: BatchQCEvaluatePayload): Promise<BatchQCEvaluateResponse> {
  try {
    const response = await fetch('/api/v1/qc/sichuan/evaluate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })

    const result = await response.json().catch(() => ({}))

    if (!response.ok) {
      return {
        success: false,
        message: result?.detail || result?.message || response.statusText,
        status: response.status
      }
    }

    // 后端直接返回评估结果（不包装在 success/data 中）
    return {
      success: true,
      data: {
        document_id: result.document_id,
        evaluation_summary: result.evaluation_summary || {},
        evaluation_results: result.evaluation_results || [],
        performance_metrics: result.performance_metrics,
        optimization_metrics: result.optimization_metrics,
        prompt_mode: result.prompt_mode || payload.prompt_mode,
        llm_info: result.llm_info
      }
    }
  } catch (error: any) {
    return {
      success: false,
      message: error?.message || '网络异常或服务器不可用'
    }
  }
}

// ============= 质控结果历史查询接口 =============

export interface QCHistoryRecord {
  id: string
  document_id: string
  document_type: string
  mode: string  // 'optimized_batch' | 'sequential_batch'
  prompt_mode?: string  // 'plan_a' | 'plan_b' | 'plan_c' | 'current'
  model?: string  // 使用的模型名称
  compliance_rate: number
  issues_count: number
  total_rules: number
  created_at: string
  stats?: Record<string, any>
  performance?: Record<string, any>
  metadata?: Record<string, any>
}

export interface QCHistoryListResponse {
  success: boolean
  data?: {
    records: QCHistoryRecord[]
    total: number
    page: number
    page_size: number
  }
  message?: string
}

export interface QCHistoryDetailResponse {
  success: boolean
  data?: {
    id: string
    document_id: string
    document_type: string
    mode: string
    prompt_mode?: string
    model?: string  // 使用的模型名称
    rule_ids: string[]
    medical_text_length: number
    stats: Record<string, any>
    performance: Record<string, any>
    results?: any[]
    payload?: any
    metadata?: Record<string, any>
    created_at: string
    saved_at?: string
  }
  message?: string
}

/**
 * 获取质控结果历史列表
 */
export async function getQCHistoryList(params?: {
  page?: number
  page_size?: number
  document_type?: string
  mode?: string
  start_date?: string
  end_date?: string
  has_issues?: boolean
}): Promise<QCHistoryListResponse> {
  try {
    const queryParams = new URLSearchParams()
    if (params?.page) queryParams.append('page', params.page.toString())
    if (params?.page_size) queryParams.append('page_size', params.page_size.toString())
    if (params?.document_type) queryParams.append('document_type', params.document_type)
    if (params?.mode) queryParams.append('mode', params.mode)
    if (params?.start_date) queryParams.append('start_date', params.start_date)
    if (params?.end_date) queryParams.append('end_date', params.end_date)
    if (params?.has_issues !== undefined) queryParams.append('has_issues', params.has_issues.toString())

    const url = `/api/v1/qc/sichuan/results/history${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    const result = await response.json().catch(() => ({}))

    if (!response.ok) {
      return {
        success: false,
        message: result?.detail || result?.message || response.statusText
      }
    }

    return {
      success: true,
      data: result
    }
  } catch (error: any) {
    return {
      success: false,
      message: error?.message || '网络异常或服务器不可用'
    }
  }
}

/**
 * 获取指定ID的质控结果详情
 */
export async function getQCHistoryDetail(resultId: string): Promise<QCHistoryDetailResponse> {
  try {
    const response = await fetch(`/api/v1/qc/sichuan/results/${resultId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    const result = await response.json().catch(() => ({}))

    if (!response.ok) {
      return {
        success: false,
        message: result?.detail || result?.message || response.statusText
      }
    }

    return {
      success: true,
      data: result
    }
  } catch (error: any) {
    return {
      success: false,
      message: error?.message || '网络异常或服务器不可用'
    }
  }
}

/**
 * 获取最新一次质控结果
 */
export async function getLatestQCResult(): Promise<QCHistoryDetailResponse> {
  try {
    const response = await fetch('/api/v1/qc/sichuan/results/latest', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    const result = await response.json().catch(() => ({}))

    if (!response.ok) {
      return {
        success: false,
        message: result?.detail || result?.message || response.statusText
      }
    }

    return {
      success: true,
      data: result
    }
  } catch (error: any) {
    return {
      success: false,
      message: error?.message || '网络异常或服务器不可用'
    }
  }
}
