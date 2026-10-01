import { isAxiosError } from 'axios'
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
  contract_status: 'assumed_unconfirmed'
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

async function read<T>(
  url: string,
  filters: RecordQualityFilters | RecordDrilldownFilters,
): Promise<QualityReportResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>({
      method: 'GET',
      url,
      params: paramsOf(filters),
    })
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
      code: errorCode(error),
      message: extractApiErrorMessageFromError(error, '病历质量报表暂不可用'),
    }
  }
}

export function getRecordQualityReport(filters: RecordQualityFilters) {
  return read<RecordQualityReport>(BASE, filters)
}

export function getRecordQualityRecords(filters: RecordDrilldownFilters) {
  return read<RecordQualityRecordsPage>(`${BASE}/records`, filters)
}

export function getRecordRemediationAnalysis(filters: RemediationFilters) {
  return read<RecordRemediationAnalysis>(`${BASE}/remediations`, filters)
}

export async function exportRecordRemediationAnalysis(
  filters: RemediationFilters,
): Promise<QualityReportResult<Blob>> {
  try {
    const response = await ApiService.getRaw<Blob>(
      `${BASE}/remediations/export`,
      paramsOf(filters),
      { responseType: 'blob' },
    )
    return { success: true, data: response.data, status: response.status }
  } catch (error) {
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      message: extractApiErrorMessageFromError(error, '导出整改分析失败'),
    }
  }
}

export async function exportRecordQualityReport(
  filters: RecordDrilldownFilters,
  sheet: ReportSheet,
): Promise<QualityReportResult<Blob>> {
  try {
    const response = await ApiService.getRaw<Blob>(
      `${BASE}/export`,
      { ...paramsOf(filters), sheet },
      { responseType: 'blob' },
    )
    return { success: true, data: response.data, status: response.status }
  } catch (error) {
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      code: errorCode(error),
      message: extractApiErrorMessageFromError(error, '导出病历质量报表失败'),
    }
  }
}
