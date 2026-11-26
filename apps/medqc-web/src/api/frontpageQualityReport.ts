import { isAxiosError } from 'axios'
import { EXTENDED_REQUEST_TIMEOUT_MS, LONG_REQUEST_TIMEOUT_MS } from '@/config/requestTimeouts'
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

function failure<T>(error: unknown, fallback: string): QualityReportResult<T> {
  const body = isAxiosError(error) ? error.response?.data : undefined
  return {
    success: false,
    status: isAxiosError(error) ? error.response?.status : undefined,
    code: errorCode(error),
    message: extractNestedMessage(body) || extractApiErrorMessageFromError(error, fallback),
  }
}

async function read<T>(
  url: string,
  filters: FrontpageQualityFilters | FrontpageDrilldownFilters,
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
    return failure<T>(error, '病案首页统计暂不可用')
  }
}

export function getFrontpageQualityReport(
  filters: FrontpageQualityFilters,
  signal?: AbortSignal,
) {
  return read<FrontpageQualityReport>(BASE, filters, signal)
}

export function getFrontpageQualityRecords(
  filters: FrontpageDrilldownFilters,
  signal?: AbortSignal,
) {
  return read<FrontpageRecordsPage>(`${BASE}/records`, filters, signal)
}

export async function exportFrontpageQualityReport(
  filters: FrontpageDrilldownFilters,
  sheet: FrontpageSheet,
  signal?: AbortSignal,
): Promise<QualityReportResult<Blob>> {
  try {
    const response = await ApiService.getRaw<Blob>(
      `${BASE}/export`,
      { ...paramsOf(filters), sheet },
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
        extractApiErrorMessageFromError(error, '导出病案首页统计失败'),
    }
  }
}
