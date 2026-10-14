/**
 * 首页质控 V2 接口（/api/v1/frontpage-qc）。
 * 确定性规则，不调用模型；后端口径见 docs/frontpage-qc-v2/。
 */
import { ApiService } from '@/services/apiService'

export type FrontpageQcDataScope = 'home' | 'all'
export type FrontpageQcGrade = 'excellent' | 'qualified' | 'unqualified'
export type FrontpageQcIssueFilter = '' | 'fail' | 'hint' | 'data_gap' | 'clean' | 'unchecked'
export type FrontpageQcRunStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'completed_with_errors'
  | 'failed'
  | 'cancelled'
export type FrontpageQcSeverity = 'deduct' | 'required' | 'hint'
export type FrontpageQcVerdict = 'fail' | 'data_gap'
export type FrontpageQcReviewStatus = 'pending' | 'confirmed' | 'false_alarm'
export type FrontpageQcSection = 'patient' | 'hospitalization' | 'diagnosis' | 'cost'

export interface FrontpageQcRef {
  institute_id: string
  patient_id: string
  visit_id: string
}

export interface FrontpageQcRun {
  id: string
  status: FrontpageQcRunStatus
  ruleset_version: string
  filters: Record<string, unknown>
  total_records: number
  processed_records: number
  success_count: number
  failed_count: number
  issue_records: number
  data_gap_records: number
  failed_records: Array<FrontpageQcRef & { error: string; message: string }>
  error_message: string | null
  cancel_requested: boolean
  created_by: string
  created_at: string | null
  started_at: string | null
  finished_at: string | null
  updated_at: string | null
}

export interface FrontpageQcResultSummary {
  id: string
  run_id: string
  record_key: string
  department: string
  discharge_date: string
  score: number
  grade: FrontpageQcGrade
  fail_count: number
  hint_count: number
  required_missing_count: number
  data_gap_count: number
  scorable_ratio: number
  completeness_rate: number | null
  ruleset_version: string
  created_at: string | null
}

export interface FrontpageQcRecordItem extends FrontpageQcRef {
  record_key: string
  patient_name: string
  inpat_no: string
  mr_no: string
  department: string
  doctor: string
  discharge_date: string
  result: FrontpageQcResultSummary | null
}

export interface FrontpageQcDetail {
  field: string
  value: string
  expected: string
  item_index: number | null
}

export interface FrontpageQcFinding {
  id: string
  rule_id: string
  rule_name: string
  group: 'completeness' | 'specification' | 'logic'
  section: FrontpageQcSection
  severity: FrontpageQcSeverity
  score_item: string | null
  verdict: FrontpageQcVerdict
  problem: string
  reason: string
  details: FrontpageQcDetail[]
  deduction: number
  review_status: FrontpageQcReviewStatus
  review_note: string
  reviewed_by: string
  reviewed_at: string | null
}

export interface FrontpageQcItemScore {
  key: string
  label: string
  section: FrontpageQcSection
  klass: string
  status: 'evaluated' | 'data_gap' | 'not_applicable'
  deduction: number
  max_points: number
}

export interface FrontpageQcResultDetail extends FrontpageQcResultSummary {
  item_scores: FrontpageQcItemScore[]
  rule_verdicts: Record<string, string>
  notes: string[]
  findings: FrontpageQcFinding[]
}

export interface FrontpageQcRecordDetail {
  record: Omit<FrontpageQcRecordItem, 'result'>
  result: FrontpageQcResultDetail | null
  stale: boolean
  frontpage: {
    basic: Record<string, string>
    discharge_diagnoses: Array<Record<string, unknown>>
    outpatient_diagnoses: Array<Record<string, unknown>>
    pathology_diagnoses: Array<Record<string, unknown>>
    surgeries: Array<Record<string, unknown>>
    cost: Record<string, string> | null
  }
}

export interface FrontpageQcRuleRank {
  rule_id: string
  rule_name: string
  severity: FrontpageQcSeverity | ''
  group: string
  section: string
  records: number
  rate: number | null
}

export interface FrontpageQcAnalytics {
  summary: {
    records: number
    avg_score: number | null
    grades: Record<FrontpageQcGrade, number>
    issue_records: number
    hint_records: number
    data_gap_records: number
  }
  indicators: Array<{ key: string; label: string; numerator: number; denominator: number; rate: number | null }>
  top_rules: FrontpageQcRuleRank[]
  top_hints: FrontpageQcRuleRank[]
  top_data_gaps: FrontpageQcRuleRank[]
  departments: Array<{
    department: string
    records: number
    avg_score: number
    excellent_rate: number | null
    issue_records: number
  }>
}

export interface FrontpageQcScopeFilters {
  data_scope?: FrontpageQcDataScope
  department?: string
  start_date?: string
  end_date?: string
  keyword?: string
}

/** 从结果分析下钻：fail 取该规则判为问题（含提示）的病历，data_gap 取资料不足的病历 */
export interface FrontpageQcRuleFilter {
  rule_id?: string
  rule_verdict?: 'fail' | 'data_gap'
}

export interface FrontpageQcListQuery extends FrontpageQcScopeFilters, FrontpageQcRuleFilter {
  grade?: FrontpageQcGrade | ''
  issue?: FrontpageQcIssueFilter
  page?: number
  page_size?: number
}

const BASE = '/api/v1/frontpage-qc'

export class FrontpageQcRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload?: unknown,
  ) {
    super(message)
    this.name = 'FrontpageQcRequestError'
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/** 后端错误格式：{ success:false, error: detail }，detail 可能是字符串或 { message, run } */
function toRequestError(error: unknown, fallback: string): FrontpageQcRequestError {
  const response = isObject(error) && isObject(error.response) ? error.response : null
  const status = response && typeof response.status === 'number' ? response.status : 0
  const body = response && isObject(response.data) ? response.data : null
  const detail = body ? (body.error ?? body.detail ?? body.message) : null
  let message = fallback
  if (typeof detail === 'string' && detail.trim()) message = detail
  else if (isObject(detail) && typeof detail.message === 'string') message = detail.message
  else if (status === 0 && isObject(error) && typeof error.message === 'string') message = fallback
  return new FrontpageQcRequestError(message, status, detail)
}

function unwrap<T>(value: unknown, fallback: string): T {
  if (isObject(value) && 'success' in value) {
    if (value.success === false) {
      throw new FrontpageQcRequestError(
        typeof value.error === 'string' ? value.error : fallback,
        200,
        value,
      )
    }
    return value.data as T
  }
  return value as T
}

function cleanParams(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  )
}

async function get<T>(url: string, params: Record<string, unknown>, fallback: string): Promise<T> {
  try {
    const response = await ApiService.getRaw(url, cleanParams(params))
    return unwrap<T>(response.data, fallback)
  } catch (error) {
    if (error instanceof FrontpageQcRequestError) throw error
    throw toRequestError(error, fallback)
  }
}

async function post<T>(url: string, body: unknown, fallback: string): Promise<T> {
  try {
    const response = await ApiService.postRaw(url, body)
    return unwrap<T>(response.data, fallback)
  } catch (error) {
    if (error instanceof FrontpageQcRequestError) throw error
    throw toRequestError(error, fallback)
  }
}

export function getFrontpageQcFilters(params: { data_scope?: FrontpageQcDataScope } = {}) {
  return get<{ departments: string[]; date_bounds: Record<string, unknown>; home_institute: string }>(
    `${BASE}/filters`, { ...params }, '读取筛选项失败',
  )
}

export function listFrontpageQcRecords(query: FrontpageQcListQuery) {
  return get<{ items: FrontpageQcRecordItem[]; total: number; page: number; page_size: number }>(
    `${BASE}/records`,
    { ...query },
    '读取首页质控结果失败',
  )
}

export function getFrontpageQcRecord(ref: FrontpageQcRef) {
  return get<FrontpageQcRecordDetail>(`${BASE}/record`, { ...ref }, '读取首页质控详情失败')
}

export function createFrontpageQcRun(
  body: { record_refs: FrontpageQcRef[] } | FrontpageQcScopeFilters,
) {
  return post<FrontpageQcRun>(`${BASE}/runs`, body, '创建首页质控任务失败')
}

export function getFrontpageQcRun(runId: string) {
  return get<FrontpageQcRun>(`${BASE}/runs/${encodeURIComponent(runId)}`, {}, '读取任务进度失败')
}

export function listActiveFrontpageQcRuns() {
  return get<{ items: FrontpageQcRun[] }>(`${BASE}/runs`, { active: true }, '读取进行中的任务失败')
}

export function cancelFrontpageQcRun(runId: string) {
  return post<FrontpageQcRun>(`${BASE}/runs/${encodeURIComponent(runId)}/cancel`, {}, '取消任务失败')
}

export function reviewFrontpageQcFinding(
  findingId: string,
  body: { status: FrontpageQcReviewStatus; note: string },
) {
  return post<FrontpageQcFinding>(
    `${BASE}/findings/${encodeURIComponent(findingId)}/review`,
    body,
    '保存复核失败',
  )
}

export function getFrontpageQcAnalytics(filters: FrontpageQcScopeFilters) {
  return get<FrontpageQcAnalytics>(`${BASE}/analytics`, { ...filters }, '读取首页质控统计失败')
}

/** 用 FileReader 读取 Blob：Blob.text() 在较旧浏览器上不可用 */
function readBlobText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '')
    reader.onerror = () => reject(reader.error ?? new Error('读取响应失败'))
    reader.readAsText(blob, 'UTF-8')
  })
}

export async function exportFrontpageQcRecords(
  body:
    | { record_refs: FrontpageQcRef[] }
    | (FrontpageQcScopeFilters & FrontpageQcRuleFilter & { grade?: string; issue?: string }),
): Promise<Blob> {
  try {
    const response = await ApiService.postRaw<Blob>(`${BASE}/records/export`, body, {
      responseType: 'blob',
    })
    return response.data
  } catch (error) {
    // 导出失败时响应体是 Blob，需要转回 JSON 才能读到原因
    const response = isObject(error) && isObject(error.response) ? error.response : null
    if (response && response.data instanceof Blob) {
      try {
        const parsed: unknown = JSON.parse(await readBlobText(response.data))
        throw toRequestError({ response: { ...response, data: parsed } }, '导出失败')
      } catch (parseError) {
        if (parseError instanceof FrontpageQcRequestError) throw parseError
      }
    }
    throw toRequestError(error, '导出失败')
  }
}

export const FRONTPAGE_QC_ACTIVE_STATUSES: FrontpageQcRunStatus[] = ['queued', 'running']

export function isFrontpageQcRunActive(run: Pick<FrontpageQcRun, 'status'> | null | undefined) {
  return Boolean(run && FRONTPAGE_QC_ACTIVE_STATUSES.includes(run.status))
}
