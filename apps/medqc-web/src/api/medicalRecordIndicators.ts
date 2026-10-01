import { isAxiosError } from 'axios'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, normalizeApiSuccess } from '@/utils/api-envelope'
import { errorCode, type QualityReportResult } from './qualityReports'

export type IndicatorDimension = 'department' | 'doctor'
export type IndicatorState = 'compliant' | 'non_compliant' | 'not_applicable' | 'unknown'

export interface IndicatorFilters {
  department?: string
  doctor?: string
  discharged_from?: string
  discharged_to?: string
}

export interface MedicalRecordIndicator {
  code: string
  name: string
  formula: string
  numerator: string
  denominator: string
  data_source: string
  availability: 'partial' | 'blocked'
  blocker?: string | null
  cohort_total: number
  eligible_total: number
  numerator_total: number
  not_applicable_total: number
  unknown_total: number
  verified_subset_rate: number | null
  official_rate: number | null
  calculation_status: 'partial' | 'blocked' | 'unavailable'
}

export interface MedicalRecordIndicatorReport {
  scope: IndicatorFilters & {
    basis: 'discharged_case_cohort'
    description: string
    archive_status: 'unverified'
  }
  summary: {
    indicator_total: number
    partial_total: number
    blocked_total: number
    cohort_total: number
  }
  indicators: MedicalRecordIndicator[]
}

export interface IndicatorBreakdown {
  indicator: MedicalRecordIndicator
  dimension: IndicatorDimension
  items: Array<MedicalRecordIndicator & { name: string }>
}

export interface IndicatorCase {
  institute_id: string
  patient_id: string
  visit_id: string
  patient_name: string
  department: string
  doctor: string
  indicator_code: string
  indicator_name: string
  state: IndicatorState
  source_value: string | null
  qc_completed_at: string | null
}

export interface IndicatorCasesPage {
  total: number
  page: number
  page_size: number
  items: IndicatorCase[]
}

const BASE = '/api/v1/quality-reports/medical-record-indicators'

function paramsOf(values: object): Record<string, string | number> {
  const params: Record<string, string | number> = {}
  for (const [key, value] of Object.entries(values)) {
    if (typeof value === 'string' && value) params[key] = value
    else if (typeof value === 'number') params[key] = value
  }
  return params
}

async function read<T>(url: string, params: object): Promise<QualityReportResult<T>> {
  try {
    const response = await ApiService.requestRaw<T>({
      method: 'GET',
      url,
      params: paramsOf(params),
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
      message: extractApiErrorMessageFromError(error, '病案管理指标报表暂不可用'),
    }
  }
}

export function getMedicalRecordIndicators(filters: IndicatorFilters) {
  return read<MedicalRecordIndicatorReport>(BASE, filters)
}

export function getMedicalRecordIndicatorBreakdown(
  filters: IndicatorFilters,
  indicatorCode: string,
  dimension: IndicatorDimension,
) {
  return read<IndicatorBreakdown>(`${BASE}/breakdown`, {
    ...filters,
    indicator_code: indicatorCode,
    dimension,
  })
}

export function getMedicalRecordIndicatorCases(
  filters: IndicatorFilters,
  indicatorCode: string,
  state?: IndicatorState,
  page = 1,
) {
  return read<IndicatorCasesPage>(`${BASE}/cases`, {
    ...filters,
    indicator_code: indicatorCode,
    state,
    page,
    page_size: 20,
  })
}

export async function exportMedicalRecordIndicators(
  filters: IndicatorFilters,
): Promise<QualityReportResult<Blob>> {
  try {
    const response = await ApiService.getRaw<Blob>(
      `${BASE}/export`,
      { ...paramsOf(filters), kind: 'indicators' },
      { responseType: 'blob' },
    )
    return { success: true, data: response.data, status: response.status }
  } catch (error) {
    return {
      success: false,
      status: isAxiosError(error) ? error.response?.status : undefined,
      code: errorCode(error),
      message: extractApiErrorMessageFromError(error, '导出病案管理指标失败'),
    }
  }
}
