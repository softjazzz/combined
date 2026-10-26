import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import { errorCode, type QualityReportResult } from '@/api/qualityReports'

/** 病案首页统计分析（PRD 第 47 项）：编码 = coding_qc，非编码 = frontpage_formal_qc。 */
export type FrontpageSourceKey = 'frontpage_formal_qc' | 'coding_qc'
export type FrontpageSourceFilter = 'all' | 'frontpage' | 'coding'
export type FrontpageSheet = 'departments' | 'records'

export interface FrontpageQualityFilters {
  department?: string
  doctor?: string
  analyzed_from?: string
  analyzed_to?: string
}

export interface FrontpageDrilldownFilters extends FrontpageQualityFilters {
  source?: FrontpageSourceFilter
  rule_code?: string
  problem_only?: boolean
  page?: number
  page_size?: number
}

export interface FrontpageMetrics {
  case_total: number
  problem_case_total: number
  problem_rate: number | null
  frontpage_case_total: number
  coding_case_total: number
  noncoding_defect_total: number
  coding_defect_total: number
  noncoding_problem_case_total: number
  coding_problem_case_total: number
}

export interface FrontpageSourceSummary {
  source_key: FrontpageSourceKey
  label: string
  severity_distribution: { severity: string; defect_total: number }[]
  category_distribution: { category: string; defect_total: number }[]
  top_rules: { rule_code: string; rule_name: string; defect_total: number }[]
}

export interface FrontpageDepartmentRow extends FrontpageMetrics {
  department: string
}

export interface FrontpageQualityReport {
  scope: FrontpageQualityFilters & { sources: FrontpageSourceKey[] }
  kpis: FrontpageMetrics
  sources: FrontpageSourceSummary[]
  department_rows: FrontpageDepartmentRow[]
}

export interface FrontpageCaseRow {
  institute_id: string
  patient_id: string
  visit_id: string
  patient_name: string
  department: string
  doctor: string
  frontpage_analysis_date: string | null
  /** null 表示该来源没有质控结果（显示“未质控”），不是 0 */
  frontpage_defect_total: number | null
  coding_analysis_date: string | null
  coding_defect_total: number | null
}

export interface FrontpageRecordsPage {
  total: number
  page: number
  page_size: number
  items: FrontpageCaseRow[]
}

const BASE = '/api/v1/quality-reports/frontpage-quality'

function paramsOf(
  filters: FrontpageQualityFilters | FrontpageDrilldownFilters,
): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {}
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') params[key] = value
  }
  return params
}

function failure<T>(error: unknown, fallback: string): QualityReportResult<T> {
  return {
    success: false,
    status: isAxiosError(error) ? error.response?.status : undefined,
    code: errorCode(error),
    message: extractApiErrorMessageFromError(error, fallback),
  }
}

async function read<T>(
  url: string,
  filters: FrontpageQualityFilters | FrontpageDrilldownFilters,
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
    return failure<T>(error, '病案首页统计暂不可用')
  }
}

export function getFrontpageQualityReport(filters: FrontpageQualityFilters) {
  return read<FrontpageQualityReport>(BASE, filters)
}

export function getFrontpageQualityRecords(filters: FrontpageDrilldownFilters) {
  return read<FrontpageRecordsPage>(`${BASE}/records`, filters)
}

export async function exportFrontpageQualityReport(
  filters: FrontpageDrilldownFilters,
  sheet: FrontpageSheet,
): Promise<QualityReportResult<Blob>> {
  try {
    const response = await ApiService.getRaw<Blob>(
      `${BASE}/export`,
      { ...paramsOf(filters), sheet },
      { responseType: 'blob' },
    )
    return { success: true, data: response.data, status: response.status }
  } catch (error) {
    return failure<Blob>(error, '导出病案首页统计失败')
  }
}
