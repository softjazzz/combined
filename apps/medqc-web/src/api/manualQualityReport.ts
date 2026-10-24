import { ApiService } from '@/services/apiService'
import { unwrapApiEnvelope } from '@/utils/api-envelope'

export interface ManualReportFilters {
  start_date: string
  end_date: string
  institute_id?: string
  department?: string
  creator_id?: string
  task_id?: string
  scene: 'all' | 'running' | 'final' | 'outpatient_emergency'
}
export interface ManualReportRow {
  id: string
  institute_id: string | null
  patient_id: string | null
  visit_id: string | null
  department: string | null
  creator_id: string | null
  creator_name: string
  scene: string | null
  task_id: string | null
  task_name: string | null
  task_record_id: string | null
  run_number: number | null
  rule_name: string | null
  created_at: string
  review_status: string
  rectification_status: string
  source_verified: boolean
}
export interface ManualReport {
  as_of: string
  timezone: string
  assumption: string
  filters: ManualReportFilters
  summary: {
    entered: number
    review: Record<string, number>
    rectification: Record<string, number>
  }
  filter_options: {
    institutes: string[]
    departments: Array<{ institute_id: string; department: string }>
    creators: Array<{ id: string; name: string }>
    tasks: Array<{ id: string; name: string }>
  }
  items: ManualReportRow[]
  total: number
  page: number
  page_size: number
}
const base = '/api/v1/manual-quality-reports'
const reviewStates = ['pending', 'approved', 'rejected', 'unknown']
const rectificationStates = [
  'pending',
  'submitted',
  'approved',
  'rejected',
  'unassigned',
  'unknown',
]
function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
function integer(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}
function text(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}
function nullableText(value: unknown) {
  return value === null || text(value)
}
function buckets(value: unknown, keys: string[], total: number) {
  return (
    object(value) &&
    keys.every((key) => integer(value[key])) &&
    keys.reduce((sum, key) => sum + Number(value[key]), 0) === total
  )
}
function assertReport(value: unknown, page: number): asserts value is ManualReport {
  const fail = () => {
    throw new Error('人工质控报表回执不完整，请刷新核对')
  }
  if (
    !object(value) ||
    !object(value.summary) ||
    !object(value.filter_options) ||
    !object(value.filters)
  )
    return fail()
  const summary = value.summary,
    options = value.filter_options
  if (
    !integer(summary.entered) ||
    !buckets(summary.review, reviewStates, summary.entered) ||
    !buckets(summary.rectification, rectificationStates, summary.entered)
  )
    return fail()
  if (
    !integer(value.total) ||
    value.total !== summary.entered ||
    value.page !== page ||
    !integer(value.page_size) ||
    value.page_size < 1 ||
    value.page_size > 100 ||
    !Array.isArray(value.items) ||
    value.items.length > value.page_size ||
    value.items.length > value.total
  )
    return fail()
  if (
    !text(value.assumption) ||
    !text(value.as_of) ||
    !Number.isFinite(Date.parse(value.as_of)) ||
    !value.as_of.endsWith('Z') ||
    value.timezone !== 'Asia/Shanghai'
  )
    return fail()
  if (
    !Array.isArray(options.institutes) ||
    !options.institutes.every(text) ||
    !Array.isArray(options.departments) ||
    !options.departments.every(
      (item) => object(item) && text(item.institute_id) && text(item.department),
    )
  )
    return fail()
  for (const key of ['creators', 'tasks']) {
    const rows = options[key]
    if (
      !Array.isArray(rows) ||
      !rows.every((item) => object(item) && text(item.id) && text(item.name))
    )
      return fail()
  }
  if (
    !value.items.every(
      (item) =>
        object(item) &&
        text(item.id) &&
        text(item.creator_name) &&
        text(item.created_at) &&
        Number.isFinite(Date.parse(item.created_at)) &&
        [
          'institute_id',
          'patient_id',
          'visit_id',
          'department',
          'creator_id',
          'task_id',
          'task_name',
          'task_record_id',
          'rule_name',
        ].every((key) => nullableText(item[key])) &&
        (item.run_number === null || (integer(item.run_number) && item.run_number > 0)) &&
        (item.scene === null ||
          ['running', 'final', 'outpatient_emergency'].includes(String(item.scene))) &&
        typeof item.source_verified === 'boolean' &&
        reviewStates.includes(String(item.review_status)) &&
        rectificationStates.includes(String(item.rectification_status)),
    )
  )
    return fail()
}
export async function getManualQualityReport(filters: ManualReportFilters, page = 1) {
  const response = await ApiService.requestRaw<unknown>({
    url: base,
    method: 'GET',
    params: { ...filters, page, page_size: 20 },
  })
  const report = unwrapApiEnvelope<unknown>(response.data)
  assertReport(report, page)
  return report
}
export async function exportManualQualityReport(filters: ManualReportFilters) {
  const response = await ApiService.requestRaw<Blob>({
    url: `${base}/export`,
    method: 'GET',
    params: filters,
    responseType: 'blob',
  })
  return response.data
}
