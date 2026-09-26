/**
 * 病历初审/复审 API（任务受领范围 + 运行/终末列表病例范围）
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

export type RecordReviewContext = 'task' | 'workspace'

/** 审核决定中与上下文无关的公共字段。 */
export interface RecordReviewEntryBase {
  id: string
  request_id: string
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

/** 一次审核决定（只追加、不可修改）。 */
export interface RecordReviewEntry extends RecordReviewEntryBase {
  task_id: string
  task_record_id: string
  run_number: number
}

/** 病例上下文历史：同一病例的任务与列表决定合并返回，workspace 行无任务字段。 */
export interface CaseRecordReviewEntry extends RecordReviewEntryBase {
  review_context: RecordReviewContext
  task_id: string | null
  task_record_id: string | null
  run_number: number | null
}

/** 审核视图中与上下文无关的公共字段，供共享展示/交互使用。 */
export interface RecordReviewViewBase<E extends RecordReviewEntryBase = RecordReviewEntryBase> {
  state: RecordReviewState
  stage: RecordReviewStage | null
  reason_code: string | null
  can_submit: boolean
  current: E | null
  history: E[]
  result: { job_id: string | null; envelope_id: string | null }
}

export interface RecordReviewView extends RecordReviewViewBase<RecordReviewEntry> {
  task_id: string
  task_record_id: string
  run_number: number
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

/** 病例（三坐标）上下文审核视图：以单病历最新 ready 结果为当前结果对象。 */
export interface CaseRecordReviewView extends RecordReviewViewBase<CaseRecordReviewEntry> {
  review_context: 'workspace'
  institute_id: string
  patient_id: string
  visit_id: string
  rule_set_key: string
}

export interface CaseRecordReviewIdentity {
  institute_id: string
  patient_id: string
  visit_id: string
}

export interface CaseRecordReviewSubmitPayload extends CaseRecordReviewIdentity {
  job_id: string
  envelope_id: string
  decision: RecordReviewDecision
  reason?: string | null
  request_id: string
}

export interface CaseRecordReviewSubmitResult extends CaseRecordReviewEntry {
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

const CASE_REVIEW_URL = '/api/v1/record-reviews/case'

/** 读取病例在最新 ready 结果上的审核状态、当前决定与历史（需 QC_RESULTS.REVIEW）。 */
export async function getCaseRecordReview(identity: CaseRecordReviewIdentity) {
  return request<CaseRecordReviewView>({
    method: 'GET',
    url: CASE_REVIEW_URL,
    params: {
      institute_id: identity.institute_id,
      patient_id: identity.patient_id,
      visit_id: identity.visit_id,
    },
  }, '读取病例审核状态失败')
}

/** 对病例最新 ready 结果对象提交审核；job_id/envelope_id 与服务端不一致时返回 409 result_changed。 */
export async function submitCaseRecordReview(payload: CaseRecordReviewSubmitPayload) {
  return request<CaseRecordReviewSubmitResult>({
    method: 'POST',
    url: CASE_REVIEW_URL,
    data: payload,
  }, '提交病例审核失败')
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
