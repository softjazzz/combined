import { isAxiosError } from 'axios'
import { EXTENDED_REQUEST_TIMEOUT_MS, LONG_REQUEST_TIMEOUT_MS } from '@/config/requestTimeouts'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'

export type ReportScene = 'running' | 'final'
export type DefectSource = 'all' | 'auto' | 'manual'
export type ReportSheet = 'departments' | 'doctors' | 'records'

export interface RecordQualityFilters {
  scene: ReportScene
  department?: string
  doctor?: string
  completed_from?: string
  completed_to?: string
  defect_source?: DefectSource
}

export interface RecordDrilldownFilters extends RecordQualityFilters {
  rule_id?: string
  document?: string
  grade?: string
  has_defect?: boolean
  has_veto?: boolean
  defect_category?: string
  defect_type?: string
  unknown_classification?: 'defect_category' | 'defect_type'
  page?: number
  page_size?: number
}

export interface ReportMetrics {
  record_total: number
  qc_ready_total: number
  qc_unavailable_total?: number
  scored_total: number | null
  average_score: number | null
  top_grade_name?: string | null
  top_grade_rate: number | null
  review_approved_total: number | null
  reviewed_total?: number | null
  top_grade_total?: number | null
  grade_rates?: Record<string, number | null>
  defect_total?: number | null
  average_defect_total?: number | null
  review_state_counts?: Record<string, number> | null
  auto_defect_total: number | null
  records_with_auto_defect?: number | null
  manual_defect_total: number | null
  manual_defect_rejected_total?: number | null
  veto_defect_total: number | null
  veto_record_total?: number | null
  records_with_defect?: number | null
}

export interface ReportGroupRow extends ReportMetrics {
  name: string
}

export interface ReportDistributionItem {
  name: string
  defect_total: number
  rule_id?: string
  rule_name?: string
}

export interface RecordQualityReport {
  scope: RecordQualityFilters & {
    rule_set_key?: string
    scope_label?: string
    /** 统计口径：running 为当前在院，final 为已出院且有质控结果（口径 B） */
    scope_basis?: 'inpatient_with_qc_result' | 'discharged_with_qc_result'
    /** 终末归档是否经医院归档标记核验；未接入来源前为 unverified */
    archive_status?: 'unverified' | null
  }
  score_standard: {
    status: 'configured' | 'no_standard' | 'unavailable'
    standard_id: string | null
    standard_name: string | null
    standard_updated_at: string | null
  }
  source_status?: {
    review: 'available' | 'unavailable'
    manual_defect: 'available' | 'unavailable'
  }
  kpis: ReportMetrics
  grade_distribution: Array<{ grade: string | null; count: number }> | null
  score_distribution: Array<{ bucket: string; count: number }> | null
  defect_level_distribution: ReportDistributionItem[] | null
  document_distribution: ReportDistributionItem[] | null
  top_rules: ReportDistributionItem[] | null
  top_departments: ReportDistributionItem[] | null
  top_doctors: ReportDistributionItem[] | null
  top_documents: ReportDistributionItem[] | null
  top_categories?: ReportDistributionItem[] | null
  top_types?: ReportDistributionItem[] | null
  top_veto_rules?: ReportDistributionItem[] | null
  defect_type_distribution?: ReportDistributionItem[] | null
  veto_source?: 'auto'
  classification_unknown?: { defect_category: number | null; defect_type: number | null }
  department_rows: ReportGroupRow[]
  doctor_rows: ReportGroupRow[]
  unavailable_dimensions: Array<{ key: string; label: string; reason_code: string }>
}

export interface ReportCaseRow {
  institute_id: string
  patient_id: string
  visit_id: string
  patient_name: string
  department: string
  doctor: string
  completed_at: string
  score: number | null
  grade: string | null
  score_status: 'scored' | 'no_standard' | 'unavailable'
  veto_hit: boolean | null
  review_state: string | null
  auto_defect_total: number | null
  manual_defect_total: number | null
}

export interface RecordQualityRecordsPage {
  total: number
  page: number
  page_size: number
  items: ReportCaseRow[]
}

export interface RemediationFilters extends RecordQualityFilters {
  label?: string
  page?: number
  page_size?: number
}
export interface RemediationRow {
  institute_id: string
  patient_id: string
  visit_id: string
  scene: ReportScene
  target_kind: 'canonical_defect' | 'task_manual_defect'
  target_id: string
  target_label: string
  root_job_id: string
  envelope_id: string
  source_known: boolean
  source_reason?: 'not_current_round' | 'manual_source_missing' | null
  patient_name: string
  department: string
  doctor: string
  labels: string[]
  rectification_state: string
  rectification_id: string | null
  assignee_name: string | null
  submission_event_id: string | null
  submission_urge_ids: string[]
  current_urge_ids: string[]
  appeals: Array<{ id: string; status: string }>
  events: Array<{
    id: string
    version: number
    action: string
    new_status: string
    comment: string
    created_at: string
    related_event_id: string | null
  }>
}
export interface RecordRemediationAnalysis {
  scope: RecordQualityFilters
  contract_status: 'confirmed'
  assumptions: string[]
  labels: Array<{ key: string; label: string; defect_total: number; case_total: number }>
  state_counts: Record<string, number>
  total: number
  page: number
  page_size: number
  filter_label: string | null
  items: RemediationRow[]
}

export interface QualityReportResult<T> {
  success: boolean
  data?: T
  message?: string
  status?: number
  code?: string
}

const BASE = '/api/v1/quality-reports/record-quality'

function paramsOf(
  filters: RecordQualityFilters | RecordDrilldownFilters,
): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = { scene: filters.scene }
  for (const [key, value] of Object.entries(filters)) {
    if (key !== 'scene' && value !== undefined && value !== null && value !== '')
      params[key] = value
  }
  return params
}

/** 报表接口统一错误码解析（detail.code 或 error.code），供各报表 API 复用。 */
export function errorCode(error: unknown): string | undefined {
  if (!isAxiosError(error)) return undefined
  const body: unknown = error.response?.data
  if (!body || typeof body !== 'object') return undefined
  for (const key of ['detail', 'error'] as const) {
    const detail = (body as Record<string, unknown>)[key]
    if (
      detail &&
      typeof detail === 'object' &&
      typeof (detail as Record<string, unknown>).code === 'string'
    ) {
      return (detail as { code: string }).code
    }
  }
  return undefined
}

/** 解析后端嵌套错误对象或 Blob JSON 错误载荷（兼容 detail/error/message 及 code）。 */
function extractNestedMessage(body: unknown): string | undefined {
  if (!body || typeof body !== 'object' || body instanceof Blob) return undefined
  const record = body as Record<string, unknown>
  for (const key of ['detail', 'error', 'message'] as const) {
    const candidate = record[key]
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
    if (Array.isArray(candidate)) {
      for (const item of candidate) {
        if (item && typeof item === 'object') {
          const msg =
            (item as Record<string, unknown>).msg ?? (item as Record<string, unknown>).message
          if (typeof msg === 'string' && msg.trim()) return msg.trim()
        }
      }
    }
    if (candidate && typeof candidate === 'object') {
      const obj = candidate as Record<string, unknown>
      const msg = obj.message ?? obj.detail ?? obj.msg
      if (typeof msg === 'string' && msg.trim()) return msg.trim()
    }
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

async function parseBlobError(value: unknown): Promise<{ message?: string; code?: string }> {
  if (!(value instanceof Blob) || value.size === 0) return {}
  try {
    const raw = (await readBlobText(value)).trim()
    if (!raw) return {}
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return {}
    const record = parsed as Record<string, unknown>
    let code: string | undefined
    for (const key of ['detail', 'error'] as const) {
      const detail = record[key]
      if (
        detail &&
        typeof detail === 'object' &&
        typeof (detail as Record<string, unknown>).code === 'string'
      ) {
        code = (detail as { code: string }).code
        break
      }
    }
    if (!code && typeof record.code === 'string' && record.code.trim()) code = record.code.trim()
    return { message: extractNestedMessage(record), code }
  } catch {
    return {}
  }
}

async function read<T>(
  url: string,
  filters: RecordQualityFilters | RecordDrilldownFilters,
  signal?: AbortSignal,
): Promise<QualityReportResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>({
      method: 'GET',
      url,
      params: paramsOf(filters),
      skipErrorToast: true,
      timeout: EXTENDED_REQUEST_TIMEOUT_MS,
      ...(signal ? { signal } : {}),
    })
    const result = normalizeApiSuccess<T>(response.data)
    return {
      success: result.success,
      data: result.data,
      message: result.message,
      status: response.status,
    }
  } catch (error) {
    const nested = isAxiosError(error) ? extractNestedMessage(error.response?.data) : undefined
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      code: errorCode(error),
      message: nested || extractApiErrorMessageFromError(error, '病历质量报表暂不可用'),
    }
  }
}

export function getRecordQualityReport(filters: RecordQualityFilters, signal?: AbortSignal) {
  return read<RecordQualityReport>(BASE, filters, signal)
}

export function getRecordQualityRecords(filters: RecordDrilldownFilters, signal?: AbortSignal) {
  return read<RecordQualityRecordsPage>(`${BASE}/records`, filters, signal)
}

export function getRecordRemediationAnalysis(filters: RemediationFilters, signal?: AbortSignal) {
  return read<RecordRemediationAnalysis>(`${BASE}/remediations`, filters, signal)
}

export async function exportRecordRemediationAnalysis(
  filters: RemediationFilters,
  signal?: AbortSignal,
): Promise<QualityReportResult<Blob>> {
  try {
    const response = await ApiService.getRaw<Blob>(
      `${BASE}/remediations/export`,
      paramsOf(filters),
      {
        responseType: 'blob',
        skipErrorToast: true,
        timeout: LONG_REQUEST_TIMEOUT_MS,
        ...(signal ? { signal } : {}),
      },
    )
    return { success: true, data: response.data, status: response.status }
  } catch (error) {
    const body = isAxiosError(error) ? error.response?.data : undefined
    const blobErr = await parseBlobError(body)
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      code: blobErr.code || errorCode(error),
      message:
        blobErr.message ||
        extractNestedMessage(body) ||
        extractApiErrorMessageFromError(error, '导出整改分析失败'),
    }
  }
}

export async function exportRecordQualityReport(
  filters: RecordDrilldownFilters,
  sheet: ReportSheet,
  columns?: string[],
  signal?: AbortSignal,
): Promise<QualityReportResult<Blob>> {
  try {
    const response = await ApiService.getRaw<Blob>(
      `${BASE}/export`,
      { ...paramsOf(filters), sheet, ...(columns ? { columns: JSON.stringify(columns) } : {}) },
      {
        responseType: 'blob',
        skipErrorToast: true,
        timeout: LONG_REQUEST_TIMEOUT_MS,
        ...(signal ? { signal } : {}),
      },
    )
    return { success: true, data: response.data, status: response.status }
  } catch (error) {
    const body = isAxiosError(error) ? error.response?.data : undefined
    const blobErr = await parseBlobError(body)
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      code: blobErr.code || errorCode(error),
      message:
        blobErr.message ||
        extractNestedMessage(body) ||
        extractApiErrorMessageFromError(error, '导出病历质量报表失败'),
    }
  }
}
