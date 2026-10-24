import { ApiService } from '@/services/apiService'
import { unwrapApiEnvelope } from '@/utils/api-envelope'

export type ManualScene = 'all' | 'running' | 'final'
export type ReviewStatus = 'pending' | 'approved' | 'rejected'
export interface EntryContext {
  task_id: string
  task_record_id: string
  task_name: string
  institute_id: string
  patient_id: string
  visit_id: string
  scene: 'running' | 'final'
  run_number: number | null
  job_id: string | null
  available: boolean
  reason: string | null
}
export interface EntryPayload {
  defect_id: string
  task_id: string
  task_record_id: string
  run_number: number
  rule_name: string
  description: string
  severity: 'info' | 'warning' | 'error' | 'critical'
  suggestion?: string
  evidence?: string
}
export interface ManualItem {
  id: string
  rule_name: string | null
  description: string | null
  manual_review_status: ReviewStatus
  task_id: string | null
  task_record_id: string | null
  run_number: number | null
  manual_created_by?: string | null
  institute_id?: string | null
  patient_id?: string | null
  visit_id?: string | null
  created_at?: string
}
const base = '/api/v1/manual-defects'
const object = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string' && !!v.trim()
const number = (v: unknown): v is number => Number.isSafeInteger(v) && Number(v) >= 0
const nullableText = (v: unknown): v is string | null => v === null || text(v)
const nullableRun = (v: unknown): v is number | null => v === null || (number(v) && v > 0)
function assert(value: unknown): asserts value {
  if (!value) throw new Error('人工缺陷回执不完整，请刷新核对')
}
async function request(path: string, method: 'GET' | 'POST', params?: object, data?: object) {
  const response = await ApiService.requestRaw<unknown>({ url: base + path, method, params, data })
  return unwrapApiEnvelope<unknown>(response.data)
}
function items(
  value: unknown,
): asserts value is Record<string, unknown> & { items: ManualItem[]; total: number } {
  assert(object(value) && Array.isArray(value.items) && number(value.total))
  assert(
    value.items.every(
      (row: unknown) =>
        object(row) &&
        text(row.id) &&
        ['pending', 'approved', 'rejected'].includes(String(row.manual_review_status)) &&
        (row.rule_name === null || text(row.rule_name)) &&
        (row.description === null || text(row.description)),
    ),
  )
  assert(value.total >= value.items.length)
}
export async function getEntryContexts(scene: ManualScene, page = 1) {
  const result = await request('/entry-contexts', 'GET', { scene, page })
  assert(
    object(result) &&
      Array.isArray(result.items) &&
      result.page === page &&
      typeof result.has_more === 'boolean',
  )
  const entries: EntryContext[] = result.items.map((row: unknown) => {
    assert(
      object(row) &&
        text(row.task_id) &&
        text(row.task_record_id) &&
        text(row.task_name) &&
        text(row.institute_id) &&
        text(row.patient_id) &&
        text(row.visit_id) &&
        (row.scene === 'running' || row.scene === 'final') &&
        nullableRun(row.run_number) &&
        nullableText(row.job_id) &&
        nullableText(row.reason) &&
        typeof row.available === 'boolean' &&
        (!row.available || (number(row.run_number) && row.run_number > 0 && text(row.job_id))),
    )
    return {
      task_id: row.task_id,
      task_record_id: row.task_record_id,
      task_name: row.task_name,
      institute_id: row.institute_id,
      patient_id: row.patient_id,
      visit_id: row.visit_id,
      scene: row.scene,
      run_number: row.run_number,
      job_id: row.job_id,
      available: row.available,
      reason: row.reason,
    }
  })
  return { items: entries, page, has_more: result.has_more }
}
export async function getOwnManualEntries(context: EntryContext, offset = 0) {
  const result = await request(
    `/entries/${encodeURIComponent(context.task_id)}/${encodeURIComponent(context.task_record_id)}`,
    'GET',
    { offset },
  )
  items(result)
  assert(
    result.items.every(
      (row) => row.task_id === context.task_id && row.task_record_id === context.task_record_id,
    ),
  )
  return result
}
export async function createManualEntry(payload: EntryPayload) {
  const result = await request('', 'POST', undefined, payload)
  assert(
    object(result) &&
      result.id === payload.defect_id &&
      result.task_id === payload.task_id &&
      result.task_record_id === payload.task_record_id &&
      result.run_number === payload.run_number &&
      ['pending', 'approved', 'rejected'].includes(String(result.manual_review_status)),
  )
  return result
}
export async function getManualReviewQueue(
  scene: ManualScene,
  review_status: ReviewStatus,
  page = 1,
) {
  const result = await request('', 'GET', { scene, review_status, page })
  items(result)
  assert(
    object(result) &&
      result.page === page &&
      result.scene === scene &&
      result.items.every((row) => row.manual_review_status === review_status),
  )
  return result
}
export async function getManualPendingCount(scene: ManualScene) {
  const result = await request('/pending-count', 'GET', { scene })
  assert(object(result) && number(result.total) && result.scene === scene)
  return result.total
}
export async function decideManualDefect(
  id: string,
  decision: 'approved' | 'rejected',
  reason: string,
) {
  const result = await request(`/${encodeURIComponent(id)}/review`, 'POST', undefined, {
    decision,
    reason: reason || null,
    expected_status: 'pending',
  })
  assert(
    object(result) &&
      result.id === id &&
      result.manual_review_status === decision &&
      result.previous_status === 'pending' &&
      text(result.history_id),
  )
  return result
}
