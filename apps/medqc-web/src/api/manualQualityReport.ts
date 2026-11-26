import { isAxiosError } from 'axios'
import { EXTENDED_REQUEST_TIMEOUT_MS, LONG_REQUEST_TIMEOUT_MS } from '@/config/requestTimeouts'
import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, unwrapApiEnvelope } from '@/utils/api-envelope'

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
  root_job_id: string | null
  envelope_id: string | null
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
          'root_job_id',
          'envelope_id',
        ].every((key) => nullableText(item[key])) &&
        (item.run_number === null || (integer(item.run_number) && item.run_number > 0)) &&
        (item.scene === null ||
          ['running', 'final', 'outpatient_emergency'].includes(String(item.scene))) &&
        typeof item.source_verified === 'boolean' &&
        (!item.source_verified || (text(item.root_job_id) && text(item.envelope_id))) &&
        reviewStates.includes(String(item.review_status)) &&
        rectificationStates.includes(String(item.rectification_status)),
    )
  )
    return fail()
}
function isAbortError(error: unknown): boolean {
  if (isAxiosError(error) && error.code === 'ERR_CANCELED') return true
  return error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError')
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

async function extractBlobErrorMessage(value: unknown): Promise<string | undefined> {
  if (!(value instanceof Blob) || value.size === 0) return undefined
  try {
    const raw = (await readBlobText(value)).trim()
    if (!raw) return undefined
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return undefined
    for (const key of ['detail', 'error', 'message'] as const) {
      const candidate = (parsed as Record<string, unknown>)[key]
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
  } catch {
    return undefined
  }
  return undefined
}

export async function getManualQualityReport(
  filters: ManualReportFilters,
  page = 1,
  signal?: AbortSignal,
) {
  const response = await ApiService.requestRaw<unknown>({
    url: base,
    method: 'GET',
    params: { ...filters, page, page_size: 20 },
    skipErrorToast: true,
    timeout: EXTENDED_REQUEST_TIMEOUT_MS,
    ...(signal ? { signal } : {}),
  })
  const report = unwrapApiEnvelope<unknown>(response.data)
  assertReport(report, page)
  return report
}
export async function exportManualQualityReport(
  filters: ManualReportFilters,
  signal?: AbortSignal,
) {
  try {
    const response = await ApiService.requestRaw<Blob>({
      url: `${base}/export`,
      method: 'GET',
      params: filters,
      responseType: 'blob',
      skipErrorToast: true,
      timeout: LONG_REQUEST_TIMEOUT_MS,
      ...(signal ? { signal } : {}),
    })
    return response.data
  } catch (error) {
    if (isAbortError(error)) throw error
    const body = isAxiosError(error) ? error.response?.data : undefined
    const blobMessage = await extractBlobErrorMessage(body)
    if (blobMessage) throw new Error(blobMessage)
    throw new Error(extractApiErrorMessageFromError(error, '导出人工质控报表失败'))
  }
}
