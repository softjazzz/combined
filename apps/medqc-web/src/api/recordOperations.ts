/**
 * 病历级操作记录时间线 API（需 QC_RESULTS.REVIEW 权限）
 *
 * 时间线只做装配和排序，每条事件的事实仍由其来源 owner 负责；前端原样展示，不重新判定状态。
 * 合同见 docs/plans/2026-09-27-v36-case-operation-timeline-design.md。
 */

import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import type { RecordReviewContext, RecordReviewDecision, RecordReviewStage } from '@/api/recordReviews'
import type { ManualDefectReviewDecision } from '@/api/manualDefectReviews'

export type KnownCaseOperationType =
  | 'qc_run_completed'
  | 'record_review'
  | 'manual_defect_created'
  | 'manual_defect_reviewed'
  | 'task_record_completed'
  | RectificationOperationType

export type RectificationOperationType =
  | 'rectification_assigned'
  | 'rectification_submitted'
  | 'rectification_approved'
  | 'rectification_rejected'
  | 'rectification_urged'
  | 'rectification_urge_withdrawn'

/** 整改 owner 的冻结来源及事件快照，不从当前病例结果推导归属。 */
export interface RectificationOperationSummary {
  rectification_id: string
  target_kind: string
  target_id: string
  scene: string
  root_job_id: string
  envelope_id: string
  rule_set_key: string
  rule_set_version: string
  version: number
  old_status: string | null
  new_status: string
  comment: string
  recipient_id: string
  related_event_id?: string | null
}

/** 质控运行完成：结果对象 join 批量任务。 */
export interface QcRunCompletedSummary {
  job_id?: string | null
  rule_set_version?: string | null
  result_count?: number | null
  task_id?: string | null
  task_run_number?: number | null
}

/** 病历初审/复审决定。 */
export interface RecordReviewSummary {
  review_context?: RecordReviewContext | null
  stage?: RecordReviewStage | null
  decision?: RecordReviewDecision | null
  reason?: string | null
  job_id?: string | null
  task_id?: string | null
}

/** 人工缺陷创建。 */
export interface ManualDefectCreatedSummary {
  defect_id?: string | null
  rule_name?: string | null
  task_id?: string | null
  run_number?: number | null
}

/** 人工缺陷审核（通过/驳回）。 */
export interface ManualDefectReviewedSummary {
  defect_id?: string | null
  decision?: ManualDefectReviewDecision | null
  reason?: string | null
}

/** 任务病历开始/完成处理。 */
export interface TaskRecordSummary {
  task_id?: string | null
  task_record_id?: string | null
  completed_run_number?: number | null
}

interface CaseOperationBase {
  id: string
  occurred_at: string | null
  actor_id: string | null
  actor_name: string | null
}

export type KnownCaseOperation =
  | (CaseOperationBase & { type: 'qc_run_completed'; summary: QcRunCompletedSummary })
  | (CaseOperationBase & { type: 'record_review'; summary: RecordReviewSummary })
  | (CaseOperationBase & { type: 'manual_defect_created'; summary: ManualDefectCreatedSummary })
  | (CaseOperationBase & { type: 'manual_defect_reviewed'; summary: ManualDefectReviewedSummary })
  | (CaseOperationBase & { type: 'task_record_completed'; summary: TaskRecordSummary })
  | (CaseOperationBase & { type: RectificationOperationType; summary: RectificationOperationSummary })

/** 未知类型兜底：保留原始 summary，前端只显示“未知操作”，不伪造字段。 */
export interface UnknownCaseOperation extends CaseOperationBase {
  type: string
  summary: Record<string, unknown> | null
}

export type CaseOperation = KnownCaseOperation | UnknownCaseOperation

export interface CaseOperationList {
  items: CaseOperation[]
  /** 精确总数，可能大于 items 长度。 */
  total: number
  limit: number
  /** 可选回显的三坐标；若后端返回则前端校验与请求一致。 */
  institute_id?: string
  patient_id?: string
  visit_id?: string
}

export interface CaseOperationQuery {
  institute_id: string
  patient_id: string
  visit_id: string
  limit?: number
}

export interface RecordOperationApiResult<T> {
  success: boolean
  data?: T
  message?: string
  /** HTTP 状态码；网络异常时为 undefined。 */
  status?: number
  code?: string
}

const KNOWN_TYPES: ReadonlySet<string> = new Set<KnownCaseOperationType>([
  'qc_run_completed',
  'record_review',
  'manual_defect_created',
  'manual_defect_reviewed',
  'task_record_completed',
  'rectification_assigned',
  'rectification_submitted',
  'rectification_approved',
  'rectification_rejected',
  'rectification_urged',
  'rectification_urge_withdrawn',
])

export function isKnownCaseOperation(item: CaseOperation): item is KnownCaseOperation {
  return KNOWN_TYPES.has(item.type)
}

/**
 * 读取结构化错误 detail。与 manualDefectReviews.ts 同一模式：
 * 统一异常包装把 detail 放在 `error` 字段；直连 FastAPI 时位于 `detail`。
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
): Promise<RecordOperationApiResult<T>> {
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

/** 按三坐标读取单病例操作记录（按时间倒序，默认最近 100 条）。 */
export async function getCaseOperations(query: CaseOperationQuery) {
  return request<CaseOperationList>({
    method: 'GET',
    url: '/api/v1/record-operations/case',
    params: {
      institute_id: query.institute_id,
      patient_id: query.patient_id,
      visit_id: query.visit_id,
      limit: query.limit ?? 100,
    },
  }, '读取本病例操作记录失败')
}
