import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

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
  execution_time?: number
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

type NormalizedResponse<T> =
  | NormalizedSuccessResponse<T>
  | NormalizedFailedResponse

interface NormalizedSuccessResponse<T> {
  ok: true
  normalized: { success: boolean; data?: T; message?: string }
  raw: unknown
  status: number
}

interface NormalizedFailedResponse {
  ok: false
  message: string
  raw?: unknown
  status?: number
}

function isNormalizedFailedResponse<T>(
  response: NormalizedResponse<T>,
): response is NormalizedFailedResponse {
  return response.ok === false
}

function extractNormalizedMessage(raw: unknown, fallbackMessage: string): string {
  return extractApiErrorMessageFromError(
    { response: { data: raw } },
    fallbackMessage,
  )
}

async function requestNormalized<T = unknown>(
  config: Parameters<typeof ApiService.requestRaw>[0],
): Promise<NormalizedResponse<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    return {
      ok: true,
      normalized: normalizeApiSuccess<T>(response.data),
      raw: response.data,
      status: response.status,
    }
  } catch (error: any) {
    return {
      ok: false,
      message: extractApiErrorMessageFromError(error, '网络异常或服务器不可用'),
      raw: error?.response?.data,
      status: error?.response?.status,
    }
  }
}

/**
 * 调用 /api/v1/qc/sichuan/test-rule
 */
export async function testQCRule(payload: TestQCRulePayload): Promise<TestQCRuleResponse> {
  try {
    const response = await requestNormalized<TestQCRuleData>({
      method: 'POST',
      url: '/api/v1/qc/sichuan/test-rule',
      data: payload,
    })

    if (isNormalizedFailedResponse(response)) {
      return {
        success: false,
        message: response.message,
        status: response.status,
        raw: response.raw,
      }
    }

    const normalized = response.normalized
    if (!normalized.success) {
      return {
        success: false,
        message: extractNormalizedMessage(response.raw, '质控评估失败'),
        status: response.status,
        raw: response.raw,
      }
    }

    return {
      success: true,
      data: normalized.data as TestQCRuleData,
      message: normalized.message,
      raw: response.raw,
    }
  } catch (error: any) {
    return {
      success: false,
      message: error?.message || '网络异常或服务器不可用',
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
  prompt_mode?: string // 提示词优化方案：current/plan_a/plan_b/plan_c
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
      model?: string // 使用的模型名称
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
    prompt_mode?: string // 提示词优化方案
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
export async function batchEvaluateQC(
  payload: BatchQCEvaluatePayload,
): Promise<BatchQCEvaluateResponse> {
  try {
    const response = await requestNormalized<any>({
      method: 'POST',
      url: '/api/v1/qc/sichuan/evaluate',
      data: payload,
    })

    if (isNormalizedFailedResponse(response)) {
      return {
        success: false,
        message: response.message,
        status: response.status,
      }
    }

    const normalized = response.normalized
    if (!normalized.success) {
      return {
        success: false,
        message: extractNormalizedMessage(response.raw, '质控评估失败'),
        status: response.status,
      }
    }
    const payloadData = (normalized.data || {}) as any

    return {
      success: true,
      data: {
        document_id: payloadData.document_id,
        evaluation_summary: payloadData.evaluation_summary || {},
        evaluation_results: payloadData.evaluation_results || [],
        performance_metrics: payloadData.performance_metrics,
        optimization_metrics: payloadData.optimization_metrics,
        prompt_mode: payloadData.prompt_mode || payload.prompt_mode,
        llm_info: payloadData.llm_info,
      },
      message: normalized.message,
    }
  } catch (error: any) {
    return {
      success: false,
      message: error?.message || '网络异常或服务器不可用',
    }
  }
}

// ============= 质控结果历史查询接口 =============

export interface QCHistoryRecord {
  id: string
  document_id: string
  document_type: string
  mode: string // 'optimized_batch' | 'sequential_batch'
  prompt_mode?: string // 'plan_a' | 'plan_b' | 'plan_c' | 'current'
  model?: string // 使用的模型名称
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
    model?: string // 使用的模型名称
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
    if (params?.has_issues !== undefined)
      queryParams.append('has_issues', params.has_issues.toString())

    const url = `/api/v1/qc/sichuan/results/history${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    const response = await requestNormalized<QCHistoryListResponse['data']>({
      method: 'GET',
      url,
    })

    if (isNormalizedFailedResponse(response)) {
      return {
        success: false,
        message: response.message,
      }
    }

    const normalized = response.normalized
    if (!normalized.success) {
      return {
        success: false,
        message: extractNormalizedMessage(response.raw, '获取质控历史失败'),
      }
    }

    return {
      success: true,
      data: normalized.data,
    }
  } catch (error: any) {
    return {
      success: false,
      message: error?.message || '网络异常或服务器不可用',
    }
  }
}

/**
 * 获取指定ID的质控结果详情
 */
export async function getQCHistoryDetail(resultId: string): Promise<QCHistoryDetailResponse> {
  try {
    const response = await requestNormalized<QCHistoryDetailResponse['data']>({
      method: 'GET',
      url: `/api/v1/qc/sichuan/results/${resultId}`,
    })

    if (isNormalizedFailedResponse(response)) {
      return {
        success: false,
        message: response.message,
      }
    }

    const normalized = response.normalized
    if (!normalized.success) {
      return {
        success: false,
        message: extractNormalizedMessage(response.raw, '获取质控结果详情失败'),
      }
    }

    return {
      success: true,
      data: normalized.data,
    }
  } catch (error: any) {
    return {
      success: false,
      message: error?.message || '网络异常或服务器不可用',
    }
  }
}

/**
 * 获取最新一次质控结果
 */
export async function getLatestQCResult(): Promise<QCHistoryDetailResponse> {
  try {
    const response = await requestNormalized<QCHistoryDetailResponse['data']>({
      method: 'GET',
      url: '/api/v1/qc/sichuan/results/latest',
    })

    if (isNormalizedFailedResponse(response)) {
      return {
        success: false,
        message: response.message,
      }
    }

    const normalized = response.normalized
    if (!normalized.success) {
      return {
        success: false,
        message: extractNormalizedMessage(response.raw, '获取最新质控结果失败'),
      }
    }

    return {
      success: true,
      data: normalized.data,
    }
  } catch (error: any) {
    return {
      success: false,
      message: error?.message || '网络异常或服务器不可用',
    }
  }
}
