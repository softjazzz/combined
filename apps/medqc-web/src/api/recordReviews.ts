/**
 * 病历初审/复审 API（任务受领范围）
 *
 * 状态、阶段与原因码均由服务端推导，前端原样展示，不在本地重新解释。
 */

import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type { DashboardScene } from '@/api/dashboard'

export type RecordReviewState = 'pending_review' | 'pending_recheck' | 'approved' | 'doubtful' | 'unavailable'
export type RecordReviewStage = 'initial' | 'recheck'
export type RecordReviewDecision = 'approved' | 'doubtful'
export type RecordReviewConflictCode =
  | 'result_changed'
  | 'already_decided'
  | 'idempotency_conflict'
  | 'result_unavailable'
  | 'unsupported_rule_set'
  | 'state_conflict'

/** 一次审核决定（只追加、不可修改）。 */
export interface RecordReviewEntry {
  id: string
  request_id: string
  task_id: string
  task_record_id: string
  run_number: number
  job_id: string
  envelope_id: string
  rule_set_key: string
  rule_set_version: string
  stage: RecordReviewStage
  decision: RecordReviewDecision
  reason: string | null
  reviewer_id: string
  created_at: string
}

export interface RecordReviewView {
  task_id: string
  task_record_id: string
  run_number: number
  state: RecordReviewState
  stage: RecordReviewStage | null
  reason_code: string | null
  can_submit: boolean
  current: RecordReviewEntry | null
  history: RecordReviewEntry[]
  result: { job_id: string | null; envelope_id: string | null }
}

export interface RecordReviewSubmitPayload {
  run_number: number
  decision: RecordReviewDecision
  reason?: string | null
  request_id: string
  envelope_id: string
}

export interface RecordReviewSubmitResult extends RecordReviewEntry {
  state: RecordReviewDecision
  idempotent: boolean
}

export interface RecordReviewTodoItem {
  task_id: string
  task_name: string | null
  task_scene: string | null
  task_record_id: string
  record_status: string
  institute_id: string
  patient_id: string
  visit_id: string
  rule_set_key: string
  rule_set_version: string
  run_number: number
  job_id: string
  envelope_id: string
  stage: RecordReviewStage
  state: Extract<RecordReviewState, 'pending_review' | 'pending_recheck'>
}

export interface RecordReviewTodoPage {
  items: RecordReviewTodoItem[]
  total: number
  page: number
  page_size: number
  stage: RecordReviewStage | null
  scene: DashboardScene
}

export interface RecordReviewTodoQuery {
  stage?: RecordReviewStage
  scene?: DashboardScene
  page?: number
  page_size?: number
}

export interface RecordReviewApiResult<T> {
  success: boolean
  data?: T
  message?: string
  /** HTTP 状态码；网络异常时为 undefined。 */
  status?: number
  /** 409 等结构化错误的业务 code。 */
  code?: string
}

/**
 * 读取结构化错误 detail（如 409 `{code, message}`）。
 * 后端统一异常包装把 HTTPException.detail 放在 `error` 字段；直连 FastAPI 时位于 `detail`。
 */
function extractErrorDetail(error: unknown): { code?: string; message?: string } {
  if (!isAxiosError(error)) return {}
  const body: unknown = error.response?.data
  if (typeof body !== 'object' || body === null) return {}
  for (const key of ['detail', 'error'] as const) {
    const candidate: unknown = (body as Record<string, unknown>)[key]
    if (typeof candidate === 'object' && candidate !== null) {
      const { code, message } = candidate as Record<string, unknown>
      if (typeof code === 'string' && code.trim()) {
        return { code, message: typeof message === 'string' && message.trim() ? message : undefined }
      }
    }
  }
  return {}
}

async function request<T>(
  config: Parameters<typeof ApiService.requestRaw>[0],
  fallback: string,
): Promise<RecordReviewApiResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return { success: normalized.success, data: normalized.data, message: normalized.message, status: response.status }
  } catch (error) {
    const detail = extractErrorDetail(error)
    return {
      success: false,
      message: detail.message || extractApiErrorMessageFromError(error, fallback),
      status: isAxiosError(error) ? error.response?.status : undefined,
      code: detail.code,
    }
  }
}

function reviewUrl(taskId: string, taskRecordId: string) {
  return `/api/v1/tasks/${encodeURIComponent(taskId)}/records/${encodeURIComponent(taskRecordId)}/review`
}

/** 读取受领病历在指定运行上的审核状态、当前决定与历史。 */
export async function getTaskRecordReview(taskId: string, taskRecordId: string, runNumber: number) {
  return request<RecordReviewView>({
    method: 'GET',
    url: reviewUrl(taskId, taskRecordId),
    params: { run_number: runNumber },
  }, '读取病历审核状态失败')
}

/** 提交审核决定；request_id 由客户端生成，结果不确定时沿用原编号安全重试。 */
export async function submitTaskRecordReview(taskId: string, taskRecordId: string, payload: RecordReviewSubmitPayload) {
  return request<RecordReviewSubmitResult>({
    method: 'POST',
    url: reviewUrl(taskId, taskRecordId),
    data: payload,
  }, '提交病历审核失败')
}

/** 本人待初审/待复审病例（与首页计数同一谓词，total 为精确值）。 */
export async function getRecordReviewTodos(query: RecordReviewTodoQuery = {}) {
  const params: Record<string, string | number> = {}
  if (query.stage) params.stage = query.stage
  if (query.scene) params.scene = query.scene
  if (query.page) params.page = query.page
  if (query.page_size) params.page_size = query.page_size
  return request<RecordReviewTodoPage>({
    method: 'GET',
    url: '/api/v1/record-reviews/todo',
    params,
  }, '读取病历审核待办失败')
}
