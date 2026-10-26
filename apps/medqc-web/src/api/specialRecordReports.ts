import { ApiService } from '@/services/apiService'
import { unwrapApiEnvelope } from '@/utils/api-envelope'

export const SPECIAL_RECORD_TYPES = [
  'death',
  'critical',
  'difficult',
  'consultation',
  'transfusion',
  'surgery',
  'surgery_ge3',
  'surgery_ge4',
] as const
export type SpecialRecordType = (typeof SPECIAL_RECORD_TYPES)[number]
export interface SpecialRecordFilters {
  institute_id: string
  department?: string
  discharged_from: string
  discharged_to: string
  record_type?: SpecialRecordType
  record_type_state?: 'positive' | 'negative' | 'unknown'
  grade?: string
  rule_id?: string
}
export interface SpecialTypeFact {
  state: 'positive' | 'negative' | 'unknown'
  reason_code: string | null
}
export interface SpecialReportRow {
  institute_id: string
  patient_id: string
  visit_id: string
  patient_name: string | null
  department: string | null
  discharged_at: string | null
  types: Record<SpecialRecordType, SpecialTypeFact>
  report_score_status: 'scored' | 'unknown'
  report_score: number | null
  report_grade: string | null
  reason_code: string | null
  standard_id: string | null
  standard_version_seq: number | null
  binding_version_seq: number | null
  historical_score: number | null
  historical_grade: string | null
  result_anchor: string | null
}
export interface SpecialReportRecords {
  total: number
  page: number
  page_size: number
  items: SpecialReportRow[]
  scope: SpecialRecordReport['scope']
  score_standard: SpecialRecordReport['score_standard']
}
export interface SpecialDefectRow {
  rule_id: string
  name: string
  severity: string | null
  category: string | null
  type: string | null
  document: string | null
  is_veto: boolean | null
  count: number
  ratio: number
}
export interface SpecialDefectsPage {
  total: number
  page: number
  page_size: number
  items: SpecialDefectRow[]
  scope: SpecialRecordReport['scope']
  score_standard: SpecialRecordReport['score_standard']
}
export interface SpecialSourceConfig {
  critical: { positive_codes: string[]; negative_codes: string[] }
  difficult: { positive_codes: string[]; negative_codes: string[] }
  surgery_level_codes: { '1': string[]; '2': string[]; '3': string[]; '4': string[] }
}
export interface SpecialConfigReceipt {
  institute_id: string
  version_seq: number
  config: SpecialSourceConfig
  sources: unknown
}
export interface SpecialRecordReport {
  scope: SpecialRecordFilters & {
    timezone: 'Asia/Shanghai'
    archive_status: 'unverified'
    result_source: string
    classification_version_seq: number
  }
  summary: {
    cohort_total: number
    record_total: number
    unavailable_result_total: number
    unknown_type_total: number
    graded_total: number
    ungraded_total: number
    grade_ratio_denominator: 'graded_total'
    known_result_total: number
    selected_unavailable_result_total: number
    defect_ratio_denominator: 'confirmed_auto_defect_total'
  }
  types: Array<{
    key: SpecialRecordType
    label: string
    count: number | null
    known_positive_total: number
    unknown_total: number
    status: 'known' | 'partial' | 'unknown'
  }>
  top_departments: Array<{ name: string; count: number }> | null
  grade_distribution: Array<{ grade: string; count: number; ratio: number }> | null
  top_defects: SpecialDefectRow[] | null
  score_standard: {
    status: 'no_standard' | 'configured' | 'unavailable'
    standard_id: string | null
    standard_version_seq: number | null
    binding_version_seq: number | null
    standard_name?: string | null
  }
}

const BASE = '/api/v1/quality-reports/special-records'
const object = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value)
const count = (value: unknown) =>
  typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
const nullableNumber = (value: unknown) =>
  value === null || (typeof value === 'number' && Number.isFinite(value))
const nullableText = (value: unknown) => value === null || typeof value === 'string'
const nullableVersion = (value: unknown) => value === null || (count(value) && Number(value) > 0)
function validMeta(value: Record<string, unknown>) {
  return (
    object(value.scope) &&
    count(value.scope.classification_version_seq) &&
    value.scope.timezone === 'Asia/Shanghai' &&
    typeof value.scope.institute_id === 'string' &&
    object(value.score_standard) &&
    ['no_standard', 'configured', 'unavailable'].includes(String(value.score_standard.status)) &&
    nullableText(value.score_standard.standard_id) &&
    nullableVersion(value.score_standard.standard_version_seq) &&
    (value.score_standard.binding_version_seq === null ||
      count(value.score_standard.binding_version_seq))
  )
}
export function sameSpecialReportVersions(
  left: Pick<SpecialRecordReport, 'scope' | 'score_standard'>,
  right: Pick<SpecialRecordReport, 'scope' | 'score_standard'>,
) {
  return (
    left.scope.classification_version_seq === right.scope.classification_version_seq &&
    left.scope.institute_id === right.scope.institute_id &&
    left.score_standard.standard_id === right.score_standard.standard_id &&
    left.score_standard.standard_version_seq === right.score_standard.standard_version_seq &&
    left.score_standard.binding_version_seq === right.score_standard.binding_version_seq
  )
}
function defectRow(value: unknown) {
  return (
    object(value) &&
    typeof value.rule_id === 'string' &&
    !!value.rule_id &&
    typeof value.name === 'string' &&
    ['severity', 'category', 'type', 'document'].every((key) => nullableText(value[key])) &&
    (value.is_veto === null || typeof value.is_veto === 'boolean') &&
    count(value.count) &&
    typeof value.ratio === 'number' &&
    value.ratio >= 0 &&
    value.ratio <= 1
  )
}
function params(filters: SpecialRecordFilters) {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== ''),
  )
}
function invalid(): never {
  throw new Error('特殊病历报表回执不完整，请重试')
}
function assertReport(value: unknown): asserts value is SpecialRecordReport {
  if (
    !object(value) ||
    !validMeta(value) ||
    !object(value.scope) ||
    value.scope.timezone !== 'Asia/Shanghai' ||
    !object(value.summary) ||
    ![
      'cohort_total',
      'record_total',
      'unavailable_result_total',
      'unknown_type_total',
      'graded_total',
      'ungraded_total',
      'known_result_total',
      'selected_unavailable_result_total',
    ].every((key) =>
      count(value.summary && object(value.summary) ? value.summary[key] : undefined),
    ) ||
    value.summary.grade_ratio_denominator !== 'graded_total' ||
    value.summary.defect_ratio_denominator !== 'confirmed_auto_defect_total' ||
    !Array.isArray(value.types) ||
    value.types.length !== 8 ||
    !value.types.every(
      (item, index) =>
        object(item) &&
        item.key === SPECIAL_RECORD_TYPES[index] &&
        typeof item.label === 'string' &&
        (item.count === null || count(item.count)) &&
        count(item.known_positive_total) &&
        count(item.unknown_total) &&
        ['known', 'partial', 'unknown'].includes(String(item.status)),
    ) ||
    !object(value.score_standard) ||
    !['no_standard', 'configured', 'unavailable'].includes(String(value.score_standard.status)) ||
    !nullableText(value.score_standard.standard_id) ||
    !nullableVersion(value.score_standard.standard_version_seq) ||
    !(
      value.score_standard.binding_version_seq === null ||
      count(value.score_standard.binding_version_seq)
    )
  )
    invalid()
  for (const [key, limit] of [
    ['top_departments', 5],
    ['grade_distribution', 100],
    ['top_defects', 10],
  ] as const) {
    const rows = value[key]
    if (
      rows !== null &&
      (!Array.isArray(rows) ||
        rows.length > limit ||
        !rows.every(
          (row) =>
            object(row) &&
            count(row.count) &&
            (key === 'top_departments'
              ? typeof row.name === 'string'
              : key === 'top_defects'
                ? defectRow(row)
                : typeof row.grade === 'string' &&
                  typeof row.ratio === 'number' &&
                  row.ratio >= 0 &&
                  row.ratio <= 1),
        ))
    )
      invalid()
  }
}
function assertRecords(
  value: unknown,
  page: number,
  instituteId: string,
): asserts value is SpecialReportRecords {
  if (
    !object(value) ||
    !validMeta(value) ||
    !count(value.total) ||
    value.page !== page ||
    value.page_size !== 20 ||
    !Array.isArray(value.items) ||
    value.items.length > 20 ||
    !value.items.every(
      (row) =>
        object(row) &&
        ['institute_id', 'patient_id', 'visit_id'].every(
          (key) => typeof row[key] === 'string' && !!row[key],
        ) &&
        row.institute_id === instituteId &&
        nullableText(row.patient_name) &&
        nullableText(row.department) &&
        nullableText(row.discharged_at) &&
        object(row.types) &&
        SPECIAL_RECORD_TYPES.every((key) => {
          const fact = object(row.types) ? row.types[key] : undefined
          return (
            object(fact) &&
            ['positive', 'negative', 'unknown'].includes(String(fact.state)) &&
            nullableText(fact.reason_code)
          )
        }) &&
        ['scored', 'unknown'].includes(String(row.report_score_status)) &&
        nullableNumber(row.report_score) &&
        nullableText(row.report_grade) &&
        (row.report_score_status === 'scored'
          ? typeof row.report_score === 'number'
          : row.report_score === null && row.report_grade === null) &&
        nullableText(row.standard_id) &&
        nullableVersion(row.standard_version_seq) &&
        nullableText(row.reason_code) &&
        (row.binding_version_seq === null || count(row.binding_version_seq)) &&
        nullableNumber(row.historical_score) &&
        nullableText(row.historical_grade),
    )
  )
    invalid()
}
export async function getSpecialRecordReport(
  filters: SpecialRecordFilters,
): Promise<SpecialRecordReport> {
  const response = await ApiService.requestRaw<unknown>({
    method: 'GET',
    url: BASE,
    params: params(filters),
  })
  const value = unwrapApiEnvelope<unknown>(response.data)
  assertReport(value)
  if (value.scope.institute_id !== filters.institute_id) invalid()
  return value
}
export async function getSpecialReportRecords(
  filters: SpecialRecordFilters,
  page = 1,
): Promise<SpecialReportRecords> {
  const response = await ApiService.requestRaw<unknown>({
    method: 'GET',
    url: `${BASE}/records`,
    params: { ...params(filters), page, page_size: 20 },
  })
  const value = unwrapApiEnvelope<unknown>(response.data)
  assertRecords(value, page, filters.institute_id)
  return value
}
export async function getSpecialReportDefects(
  filters: SpecialRecordFilters,
  page = 1,
): Promise<SpecialDefectsPage> {
  const response = await ApiService.requestRaw<unknown>({
    method: 'GET',
    url: `${BASE}/defects`,
    params: { ...params(filters), page, page_size: 20 },
  })
  const value = unwrapApiEnvelope<unknown>(response.data)
  if (
    !object(value) ||
    !validMeta(value) ||
    !count(value.total) ||
    value.page !== page ||
    value.page_size !== 20 ||
    !Array.isArray(value.items) ||
    value.items.length > 20 ||
    !value.items.every(defectRow)
  )
    invalid()
  return value as unknown as SpecialDefectsPage
}
export async function exportSpecialRecordReport(
  filters: SpecialRecordFilters,
  kind: 'records' | 'defects' | 'summary' = 'summary',
  expected?: Pick<SpecialRecordReport, 'scope' | 'score_standard'>,
): Promise<Blob> {
  const response = await ApiService.requestRaw<Blob>({
    method: 'GET',
    url: `${BASE}/export`,
    params: { ...params(filters), kind },
    responseType: 'blob',
  })
  if (!(response.data instanceof Blob) || !response.data.size)
    throw new Error('导出文件不可用，请重试')
  if (expected) {
    const refs = {
      'x-special-classification-version': expected.scope.classification_version_seq,
      'x-special-standard-id': expected.score_standard.standard_id,
      'x-special-standard-version': expected.score_standard.standard_version_seq,
      'x-special-binding-version': expected.score_standard.binding_version_seq,
    }
    if (
      !Object.entries(refs).every(
        ([key, value]) => String(response.headers?.[key] ?? '') === String(value ?? ''),
      )
    ) {
      throw new Error('机构分类或评分标准版本已变化，请刷新报表后重新下载')
    }
  }
  return response.data
}
function assertConfig(value: unknown): asserts value is SpecialConfigReceipt {
  if (
    !object(value) ||
    typeof value.institute_id !== 'string' ||
    !count(value.version_seq) ||
    !object(value.config)
  )
    invalid()
  for (const key of ['critical', 'difficult'] as const) {
    const group = value.config[key]
    if (
      !object(group) ||
      !['positive_codes', 'negative_codes'].every(
        (name) =>
          Array.isArray(group[name]) && group[name].every((code) => typeof code === 'string'),
      )
    )
      invalid()
  }
  const levels = value.config.surgery_level_codes
  if (
    !object(levels) ||
    !['1', '2', '3', '4'].every(
      (key) => Array.isArray(levels[key]) && levels[key].every((code) => typeof code === 'string'),
    )
  )
    invalid()
}
export async function getSpecialSourceConfig(instituteId: string): Promise<SpecialConfigReceipt> {
  const response = await ApiService.requestRaw<unknown>({
    method: 'GET',
    url: `${BASE}/config`,
    params: { institute_id: instituteId },
  })
  const value = unwrapApiEnvelope<unknown>(response.data)
  assertConfig(value)
  if (value.institute_id !== instituteId) invalid()
  return value
}
export async function saveSpecialSourceConfig(
  instituteId: string,
  version: number,
  config: SpecialSourceConfig,
): Promise<SpecialConfigReceipt> {
  const response = await ApiService.requestRaw<unknown>({
    method: 'PUT',
    url: `${BASE}/config`,
    params: { institute_id: instituteId },
    data: { version_seq: version, config },
  })
  const value = unwrapApiEnvelope<unknown>(response.data)
  assertConfig(value)
  if (value.institute_id !== instituteId) invalid()
  return value
}
