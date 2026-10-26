import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export type StaffAnalysisPeriod = 'this_week' | 'last_week' | 'this_month'
export type StaffAnalysisScene = 'all' | 'running' | 'final'
export type StaffAnalysisUnavailableMetric =
  | 'appeal_approved_count'
  | 'appeal_rejected_count'
  | 'urged_defect_count'
  | 'confirmed_defect_count'
export type StaffAnalysisUnavailableReason =
  | 'scene_not_attributable'
  | 'filter_not_attributable'
  | 'source_unavailable'
  | 'snapshot_incomplete'
export type StaffAnalysisMetric =
  | 'record_review_count'
  | 'reviewed_case_count'
  | 'rechecked_case_count'
  | 'initial_count'
  | 'recheck_count'
  | 'manual_defect_created_count'
  | 'manual_review_approved_count'
  | 'manual_review_rejected_count'
  | 'appeal_approved_count'
  | 'appeal_rejected_count'
  | 'urged_defect_count'
  | 'confirmed_defect_count'

export interface StaffAnalysisFilters {
  period: StaffAnalysisPeriod
  scene: StaffAnalysisScene
  institute_id?: string
  department?: string
  task_id?: string
  start_date?: string
  end_date?: string
  as_of?: string
}

export interface StaffAnalysisAppliedFilters {
  period: StaffAnalysisPeriod
  scene: StaffAnalysisScene
  institute_id: string | null
  department: string | null
  task_id: string | null
  start_date: string | null
  end_date: string | null
  as_of: string
}

export interface StaffWorkCounts {
  record_review_count: number
  reviewed_case_count: number
  rechecked_case_count: number
  initial_count: number
  recheck_count: number
  manual_defect_created_count: number
  manual_review_approved_count: number
  manual_review_rejected_count: number
  appeal_approved_count: number | null
  appeal_rejected_count: number | null
  urged_defect_count: number | null
  confirmed_defect_count: number | null
}

export interface StaffDefectSnapshotCoverage {
  initial_review_count: number
  covered_initial_review_count: number
  missing_initial_review_count: number
  known_defect_count: number
}

export interface StaffWorkSummary extends StaffWorkCounts {
  defect_snapshot_coverage?: StaffDefectSnapshotCoverage
  active_staff_count: number
  record_reviewer_count: number
  avg_record_reviews_per_active_staff: number | null
  avg_reviewed_cases_per_reviewer: number | null
  avg_reviewed_cases_per_active_staff: number | null
  avg_rechecked_cases_per_active_staff: number | null
  avg_manual_defects_per_active_staff: number | null
  avg_rejected_defects_per_active_staff: number | null
}

export interface StaffWorkRow extends StaffWorkCounts {
  defect_snapshot_coverage?: StaffDefectSnapshotCoverage
  user_id: string
  name: string | null
  rank: number | null
}

export interface StaffAnalysisFilterOptions {
  departments: Array<{ institute_id: string; department_name: string }>
  tasks: Array<{ task_id: string; task_name: string | null }>
}

export interface StaffAnalysisReport {
  defect_snapshot_coverage?: StaffDefectSnapshotCoverage
  rank_metric?: StaffAnalysisMetric
  period: StaffAnalysisPeriod
  period_label: string
  range: { start: string; end: string }
  scene: StaffAnalysisScene
  filters: StaffAnalysisAppliedFilters
  filter_options: StaffAnalysisFilterOptions
  filter_options_unavailable_reason: string | null
  context_unavailable_count: number
  summary: StaffWorkSummary | null
  staff: StaffWorkRow[] | null
  unavailable_reason: string | null
  unavailable_metrics: Partial<
    Record<StaffAnalysisUnavailableMetric, StaffAnalysisUnavailableReason>
  >
}

export interface StaffAnalysisDetailItem {
  event_id: string
  event_type:
    | 'record_review'
    | 'manual_defect_created'
    | 'manual_review_approved'
    | 'manual_review_rejected'
    | 'appeal_approved'
    | 'appeal_rejected'
    | 'defect_urged'
    | 'initial_defect_confirmed'
  source?: 'auto' | 'manual'
  rule_id?: string | null
  job_id?: string
  envelope_id?: string
  rule_set_key?: string
  rule_set_version?: string
  scene?: string
  occurred_at: string
  institute_id: string | null
  patient_id: string | null
  visit_id: string | null
  task_id: string | null
  department: string | null
  stage: string | null
  decision: string | null
  defect_id: string | null
  appeal_id: string | null
}

export interface StaffAnalysisDetailsPage {
  known_total?: number
  total_complete?: boolean
  defect_snapshot_coverage?: StaffDefectSnapshotCoverage
  filters: StaffAnalysisAppliedFilters
  metric: StaffAnalysisMetric
  user_id: string
  items: StaffAnalysisDetailItem[] | null
  total: number | null
  page: number
  page_size: number
  unavailable_reason: string | null
}

export interface StaffAnalysisResult<T = StaffAnalysisReport> {
  success: boolean
  data?: T
  message?: string
  status?: number
}

const BASE = '/api/v1/quality-reports/staff-work'
const CSV_CONTENT_TYPE = /^text\/csv(?:\s*;|$)/i

function paramsOf(filters: StaffAnalysisFilters): Record<string, string> {
  const params: Record<string, string> = { period: filters.period, scene: filters.scene }
  for (const key of [
    'institute_id',
    'department',
    'task_id',
    'start_date',
    'end_date',
    'as_of',
  ] as const) {
    const value = filters[key]
    if (value) params[key] = value
  }
  return params
}

async function read<T>(
  url: string,
  params: Record<string, string | number>,
): Promise<StaffAnalysisResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>({ method: 'GET', url, params })
    const result = normalizeApiSuccess<T>(response.data)
    return {
      success: result.success,
      data: result.data,
      message: result.message,
      status: response.status,
    }
  } catch (error) {
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      message: extractApiErrorMessageFromError(error, '质控员工作分析暂不可用'),
    }
  }
}

export function getStaffAnalysis(
  filters: StaffAnalysisFilters,
  rankMetric?: StaffAnalysisMetric,
): Promise<StaffAnalysisResult> {
  return read<StaffAnalysisReport>(BASE, {
    ...paramsOf(filters),
    ...(rankMetric ? { rank_metric: rankMetric } : {}),
  })
}

export function getStaffAnalysisDetails(
  userId: string,
  filters: StaffAnalysisFilters,
  metric: StaffAnalysisMetric,
  page = 1,
  pageSize = 20,
): Promise<StaffAnalysisResult<StaffAnalysisDetailsPage>> {
  return read<StaffAnalysisDetailsPage>(`${BASE}/${encodeURIComponent(userId)}/details`, {
    ...paramsOf(filters),
    metric,
    page,
    page_size: pageSize,
  })
}

export async function exportStaffAnalysis(
  filters: StaffAnalysisFilters,
  rankMetric?: StaffAnalysisMetric,
): Promise<StaffAnalysisResult<Blob>> {
  try {
    const response = await ApiService.requestRaw<Blob>({
      method: 'GET',
      url: `${BASE}/export`,
      params: { ...paramsOf(filters), ...(rankMetric ? { rank_metric: rankMetric } : {}) },
      responseType: 'blob',
    })
    const contentType = headerValue(response.headers, 'content-type')
    if (
      response.status !== 200 ||
      !(response.data instanceof Blob) ||
      response.data.size === 0 ||
      !CSV_CONTENT_TYPE.test(contentType)
    ) {
      return {
        success: false,
        status: response.status,
        message:
          (await messageFromBlob(response.data)) || '服务端未返回有效的质控员工作分析 CSV 文件',
      }
    }
    return { success: true, data: response.data, status: response.status }
  } catch (error) {
    const body = isAxiosError(error) ? error.response?.data : undefined
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      message:
        (await messageFromBlob(body)) ||
        extractApiErrorMessageFromError(error, '导出质控员工作分析失败'),
    }
  }
}

function headerValue(headers: unknown, name: string): string {
  if (!headers || typeof headers !== 'object') return ''
  const getter = Reflect.get(headers, 'get')
  if (typeof getter === 'function') {
    const value: unknown = Reflect.apply(getter, headers, [name])
    if (typeof value === 'string') return value
  }
  const target = name.toLowerCase()
  for (const [key, value] of Object.entries(headers as Record<string, unknown>)) {
    if (key.toLowerCase() === target && typeof value === 'string') return value
  }
  return ''
}

async function messageFromBlob(value: unknown): Promise<string | undefined> {
  if (!(value instanceof Blob) || value.size === 0) return undefined
  try {
    const parsed: unknown = JSON.parse(await readBlobText(value))
    if (!parsed || typeof parsed !== 'object') return undefined
    for (const key of ['detail', 'error', 'message'] as const) {
      const candidate = (parsed as Record<string, unknown>)[key]
      if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
      if (candidate && typeof candidate === 'object') {
        const message = (candidate as Record<string, unknown>).message
        if (typeof message === 'string' && message.trim()) return message.trim()
      }
    }
  } catch {
    return undefined
  }
  return undefined
}

async function readBlobText(blob: Blob): Promise<string> {
  const text = Reflect.get(blob, 'text')
  if (typeof text === 'function') return String(await Reflect.apply(text, blob, []))
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () =>
      typeof reader.result === 'string'
        ? resolve(reader.result)
        : reject(new Error('Blob读取结果不是文本'))
    reader.onerror = () => reject(reader.error || new Error('Blob读取失败'))
    reader.onabort = () => reject(new Error('Blob读取已中止'))
    reader.readAsText(blob, 'utf-8')
  })
}
