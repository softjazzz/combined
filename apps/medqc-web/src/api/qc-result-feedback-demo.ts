import { ApiService } from '@/services/apiService'
import { ensureClinicalSourceModeInitialized } from '@/api/clinicalSources'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export type QcResultFeedbackType = 'correct' | 'incorrect' | 'note'

export type QcResultExpectedStatus =
  | 'non_compliant'
  | 'compliant'
  | 'data_gap'
  | 'not_applicable'
  | 'evaluation_unknown'
  | 'not_executed'

export type QcResultFeedbackErrorCategory =
  | 'wrong_status'
  | 'wrong_reason'
  | 'wrong_evidence'
  | 'missing_data_read'
  | 'wrong_suggestion'
  | 'rule_definition'
  | 'other'

export interface QcResultFeedbackRecord {
  id?: string
  root_job_id?: string
  record_ref?: string
  rule_id: string
  rule_name?: string
  patient_name?: string
  record_number?: string
  visit_id?: string
  department?: string
  care_phase?: string
  original_status: string
  feedback_type: QcResultFeedbackType
  expected_status?: QcResultExpectedStatus | null
  error_category?: QcResultFeedbackErrorCategory | null
  comment?: string | null
  created_at?: string
  updated_at?: string
}

export interface SaveQcResultFeedbackInput {
  feedback_type: QcResultFeedbackType
  expected_status?: QcResultExpectedStatus
  error_category?: QcResultFeedbackErrorCategory
  comment?: string
}

export interface QcResultFeedbackApiResult<T> {
  success: boolean
  data?: T
  message?: string
  status?: number
}

const FEEDBACK_PATH = '/api/v1/qc/sichuan/workspace/result-feedback-demo'

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function asNonEmptyString(value: unknown): string | undefined {
  const text = typeof value === 'string' ? value.trim() : ''
  return text || undefined
}

function isFeedbackType(value: unknown): value is QcResultFeedbackType {
  return value === 'correct' || value === 'incorrect' || value === 'note'
}

function normalizeFeedback(value: unknown, ruleIdHint?: string): QcResultFeedbackRecord | null {
  if (!isRecord(value)) return null
  const ruleId = asNonEmptyString(value.rule_id) || asNonEmptyString(ruleIdHint)
  const originalStatus = asNonEmptyString(value.original_status)
  const feedbackType = value.feedback_type
  if (!ruleId || !originalStatus || !isFeedbackType(feedbackType)) return null
  return {
    id: asNonEmptyString(value.id),
    root_job_id: asNonEmptyString(value.root_job_id),
    record_ref: asNonEmptyString(value.record_ref),
    rule_id: ruleId,
    rule_name: asNonEmptyString(value.rule_name),
    patient_name: asNonEmptyString(value.patient_name),
    record_number: asNonEmptyString(value.record_number),
    visit_id: asNonEmptyString(value.visit_id),
    department: asNonEmptyString(value.department),
    care_phase: asNonEmptyString(value.care_phase),
    original_status: originalStatus,
    feedback_type: feedbackType,
    expected_status: asNonEmptyString(value.expected_status) as QcResultExpectedStatus | undefined,
    error_category: asNonEmptyString(value.error_category) as
      QcResultFeedbackErrorCategory | undefined,
    comment: typeof value.comment === 'string' ? value.comment : undefined,
    created_at: asNonEmptyString(value.created_at),
    updated_at: asNonEmptyString(value.updated_at),
  }
}

function normalizeFeedbackList(value: unknown): QcResultFeedbackRecord[] {
  const source = isRecord(value) ? value.items : value
  if (!Array.isArray(source)) return []
  return source.flatMap((item) => {
    const feedback = normalizeFeedback(item)
    return feedback ? [feedback] : []
  })
}

function normalizeFeedbackMap(value: unknown): Record<string, QcResultFeedbackRecord> {
  const map: Record<string, QcResultFeedbackRecord> = {}
  const source =
    isRecord(value) && ('feedbacks' in value || 'items' in value)
      ? (value.feedbacks ?? value.items)
      : value

  if (Array.isArray(source)) {
    source.forEach((item) => {
      const feedback = normalizeFeedback(item)
      if (feedback) map[feedback.rule_id] = feedback
    })
    return map
  }

  if (!isRecord(source)) return map
  Object.entries(source).forEach(([ruleId, item]) => {
    const feedback = normalizeFeedback(item, ruleId)
    if (feedback) map[feedback.rule_id] = feedback
  })
  return map
}

async function request<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  fallbackMessage: string,
): Promise<QcResultFeedbackApiResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return {
      success: normalized.success,
      data: normalized.data,
      message: normalized.message,
      status: response.status,
    }
  } catch (error: unknown) {
    return {
      success: false,
      message: extractApiErrorMessageFromError(error, fallbackMessage),
      status:
        error && typeof error === 'object' && 'response' in error
          ? Number((error as { response?: { status?: unknown } }).response?.status) || undefined
          : undefined,
    }
  }
}

export async function getQcResultFeedbackDemo(params: {
  rootJobId: string
  recordRef: string
}): Promise<QcResultFeedbackApiResult<Record<string, QcResultFeedbackRecord>>> {
  const result = await request<unknown>(
    {
      method: 'GET',
      url: FEEDBACK_PATH,
      params: {
        root_job_id: params.rootJobId,
        record_ref: params.recordRef,
      },
    },
    '读取质控反馈失败',
  )
  if (!result.success) {
    return result as QcResultFeedbackApiResult<Record<string, QcResultFeedbackRecord>>
  }
  return {
    ...result,
    data: normalizeFeedbackMap(result.data),
  }
}

export async function listQcResultFeedbackDemo(
  limit = 200,
): Promise<QcResultFeedbackApiResult<QcResultFeedbackRecord[]>> {
  await ensureClinicalSourceModeInitialized()
  const result = await request<unknown>(
    {
      method: 'GET',
      url: `${FEEDBACK_PATH}/all`,
      params: { limit },
    },
    '读取质控反馈记录失败',
  )
  if (!result.success) {
    return result as QcResultFeedbackApiResult<QcResultFeedbackRecord[]>
  }
  return { ...result, data: normalizeFeedbackList(result.data) }
}

export async function saveQcResultFeedbackDemo(params: {
  rootJobId: string
  recordRef: string
  ruleId: string
  input: SaveQcResultFeedbackInput
}): Promise<QcResultFeedbackApiResult<QcResultFeedbackRecord>> {
  await ensureClinicalSourceModeInitialized()
  const result = await request<unknown>(
    {
      method: 'PUT',
      url: `${FEEDBACK_PATH}/${encodeURIComponent(params.ruleId)}`,
      data: {
        root_job_id: params.rootJobId,
        record_ref: params.recordRef,
        feedback_type: params.input.feedback_type,
        ...(params.input.expected_status ? { expected_status: params.input.expected_status } : {}),
        ...(params.input.error_category ? { error_category: params.input.error_category } : {}),
        ...(params.input.comment?.trim() ? { comment: params.input.comment.trim() } : {}),
      },
    },
    '保存质控反馈失败',
  )
  if (!result.success) {
    return result as QcResultFeedbackApiResult<QcResultFeedbackRecord>
  }
  const feedback = normalizeFeedback(result.data, params.ruleId)
  return feedback
    ? { ...result, data: feedback }
    : { success: false, message: '反馈响应格式不完整', status: result.status }
}
