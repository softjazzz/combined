import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type {
  CustomQcBatchTestResult,
  CustomQcDraftRule,
  CustomQcPromptGenerationResult,
  CustomQcRecordPayload,
  CustomQcSingleTestResult,
} from '@/types/custom-qc'

type ServiceResult<T> = {
  success: boolean
  data?: T
  message?: string
}

function toErrorMessage(error: unknown, fallback: string): string {
  return extractApiErrorMessageFromError(error, fallback)
}

async function requestEnvelope<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  fallbackMessage: string,
): Promise<ServiceResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return {
      success: normalized.success,
      data: normalized.data,
      message: normalized.message,
    }
  } catch (error) {
    return {
      success: false,
      message: toErrorMessage(error, fallbackMessage),
    }
  }
}

export async function generateCustomQcPrompt(payload: {
  scene: 'running' | 'final'
  document_type: string
  rule_name: string
  description: string
  severity: 'critical' | 'major' | 'minor'
}) {
  return requestEnvelope<CustomQcPromptGenerationResult>(
    {
      method: 'POST',
      url: '/api/v1/custom-qc/prompt/generate',
      data: payload,
    },
    '生成 Prompt 失败',
  )
}

export async function testCustomQcSingle(payload: {
  rule: CustomQcDraftRule
  records: CustomQcRecordPayload[]
  temperature?: number
  top_p?: number
  max_tokens?: number
}) {
  return requestEnvelope<CustomQcSingleTestResult>(
    {
      method: 'POST',
      url: '/api/v1/custom-qc/test',
      data: payload,
    },
    '单病历测试失败',
  )
}

export async function testCustomQcBatch(payload: {
  rule: CustomQcDraftRule
  records: CustomQcRecordPayload[]
  temperature?: number
  top_p?: number
  max_tokens?: number
}) {
  return requestEnvelope<CustomQcBatchTestResult>(
    {
      method: 'POST',
      url: '/api/v1/custom-qc/test/batch',
      data: payload,
    },
    '批量测试失败',
  )
}

export async function saveCustomQcTestResult(payload: {
  mode: string
  document_type: string
  rule_ids: string[]
  medical_text?: string
  medical_text_length: number
  stats: Record<string, unknown>
  performance: Record<string, unknown>
  results?: unknown[]
  payload?: Record<string, unknown>
  document_id?: string
  metadata?: Record<string, unknown>
  model?: string
}) {
  return requestEnvelope<{ id: string; path: string }>(
    {
      method: 'POST',
      url: '/api/v1/qc/sichuan/results/save',
      data: payload,
    },
    '保存测试结果失败',
  )
}
