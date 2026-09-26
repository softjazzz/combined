/**
 * 人工缺陷审核 API（需 QC_RESULTS.REVIEW 权限）
 *
 * 只处理任务受领产生的人工缺陷；与整改审核、申诉复核互不复用。
 */

import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export type ManualDefectReviewStatus = 'pending' | 'approved' | 'rejected'
export type ManualDefectReviewDecision = 'approved' | 'rejected'

export interface ManualDefectReviewItem {
  id: string
  institute_id: string | null
  patient_id: string | null
  visit_id: string | null
  task_id: string | null
  task_record_id: string | null
  run_number: number | null
  rule_code: string | null
  rule_name: string | null
  description: string | null
  severity: string | null
  location: string | null
  suggestion: string | null
  manual_review_status: ManualDefectReviewStatus
  manual_created_by: string | null
  created_at: string | null
}

export interface ManualDefectReviewPage {
  items: ManualDefectReviewItem[]
  total: number
  page: number
  page_size: number
}

/** 单病例人工缺陷：按 created_at 倒序，最多返回 200 条；total 为精确总数，可能大于 items 长度。 */
export interface CaseManualDefectList {
  items: ManualDefectReviewItem[]
  total: number
}

export interface CaseManualDefectQuery {
  institute_id: string
  patient_id: string
  visit_id: string
}

export interface ManualDefectReviewPayload {
  decision: ManualDefectReviewDecision
  reason?: string | null
  expected_status: 'pending'
}

export interface ManualDefectReviewResult {
  id: string
  manual_review_status: ManualDefectReviewDecision
  previous_status: 'pending'
  reason: string | null
  reviewer_id: string
  reviewed_at: string
  history_id: string
}

export interface ManualDefectReviewApiResult<T> {
  success: boolean
  data?: T
  message?: string
  /** HTTP 状态码；网络异常时为 undefined。 */
  status?: number
  /** 409 结构化错误的业务 code（如 not_pending）。 */
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
): Promise<ManualDefectReviewApiResult<T>> {
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

/** 按审核状态分页读取人工缺陷（精确 total）。 */
export async function getManualDefects(reviewStatus: ManualDefectReviewStatus = 'pending', page = 1, pageSize = 20) {
  return request<ManualDefectReviewPage>({
    method: 'GET',
    url: '/api/v1/manual-defects',
    params: { review_status: reviewStatus, page, page_size: pageSize },
  }, '读取人工缺陷失败')
}

/** 通过/驳回人工缺陷；仅 pending 可审（服务端 CAS）。 */
export async function reviewManualDefect(defectId: string, payload: ManualDefectReviewPayload) {
  return request<ManualDefectReviewResult>({
    method: 'POST',
    url: `/api/v1/manual-defects/${encodeURIComponent(defectId)}/review`,
    data: payload,
  }, '提交人工缺陷审核失败')
}

/** 按三坐标读取单病例全部人工缺陷（含已审核），供病历结果抽屉只读展示。 */
export async function getCaseManualDefects(query: CaseManualDefectQuery) {
  return request<CaseManualDefectList>({
    method: 'GET',
    url: '/api/v1/manual-defects/case',
    params: { institute_id: query.institute_id, patient_id: query.patient_id, visit_id: query.visit_id },
  }, '读取本病例人工缺陷失败')
}
