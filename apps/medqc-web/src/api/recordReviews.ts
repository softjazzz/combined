import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, unwrapApiEnvelope } from '@/utils/api-envelope'

export type ReviewState = 'pending_review' | 'pending_recheck' | 'approved' | 'doubtful'
export type ReviewDecision = 'approved' | 'doubtful'
export interface RecordReviewSource {
  institute_id: string
  patient_id: string
  visit_id: string
  scene: 'running' | 'final'
  root_job_id: string
  envelope_id: string
  rule_set_key: string
  rule_set_version: string
}
export interface RecordReview extends RecordReviewSource {
  id: string
  request_id: string
  stage: 'initial' | 'recheck'
  decision: ReviewDecision
  reason: string | null
  reviewer_id: string
  created_at: string
  case_department: string | null
}
export interface RecordReviewItem extends RecordReviewSource {
  state: ReviewState
  stage: 'initial' | 'recheck'
  review_id: string | null
  case_department: string | null
}
export interface RecordReviewDetail extends RecordReviewSource {
  state: ReviewState
  stage: 'initial' | 'recheck'
  current_review: RecordReview | null
  case_department: string | null
  history: RecordReview[]
  can_submit: boolean
}
export interface RecordReviewList {
  items: RecordReviewItem[]
  total: number
  pending_count: number
  initial_count: number
  recheck_count: number
}
const base = '/api/v1/record-reviews'
const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
const text = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length > 0
const nullableText = (value: unknown) => value === null || typeof value === 'string'
const stage = (value: unknown) => value === 'initial' || value === 'recheck'
const states: ReviewState[] = ['pending_review', 'pending_recheck', 'approved', 'doubtful']
const sourceKeys: Array<keyof RecordReviewSource> = [
  'institute_id',
  'patient_id',
  'visit_id',
  'scene',
  'root_job_id',
  'envelope_id',
  'rule_set_key',
  'rule_set_version',
]
function matchesSource(actual: RecordReviewSource, expected: RecordReviewSource) {
  return sourceKeys.every((key) => actual[key] === expected[key])
}
function source(value: unknown): value is RecordReviewSource {
  return (
    object(value) &&
    [
      'institute_id',
      'patient_id',
      'visit_id',
      'root_job_id',
      'envelope_id',
      'rule_set_key',
      'rule_set_version',
    ].every((key) => text(value[key])) &&
    (value.scene === 'running' || value.scene === 'final')
  )
}
function review(value: unknown): value is RecordReview {
  return (
    source(value) &&
    object(value) &&
    ['id', 'request_id', 'reviewer_id', 'created_at'].every((key) => text(value[key])) &&
    stage(value.stage) &&
    (value.decision === 'approved' || value.decision === 'doubtful') &&
    nullableText(value.reason) &&
    nullableText(value.case_department)
  )
}
function item(value: unknown): value is RecordReviewItem {
  return (
    source(value) &&
    object(value) &&
    states.some((state) => state === value.state) &&
    stage(value.stage) &&
    nullableText(value.review_id) &&
    nullableText(value.case_department)
  )
}
function detail(value: unknown): RecordReviewDetail {
  if (
    !source(value) ||
    !object(value) ||
    !states.some((state) => state === value.state) ||
    !stage(value.stage) ||
    !nullableText(value.case_department) ||
    !Array.isArray(value.history) ||
    !value.history.every(review) ||
    typeof value.can_submit !== 'boolean'
  )
    throw new Error('审核来源或历史无效，请刷新核对')
  let currentReview: RecordReview | null
  if (value.current_review === null) currentReview = null
  else if (review(value.current_review)) currentReview = value.current_review
  else
    throw new Error('审核来源或历史无效，请刷新核对')
  if (
    value.can_submit &&
    (currentReview !== null ||
      !['pending_review', 'pending_recheck'].includes(String(value.state)))
  )
    throw new Error('审核状态无效，请刷新核对')
  if (
    currentReview !== null &&
    (!matchesSource(currentReview, value) ||
      currentReview.decision !== value.state ||
      currentReview.stage !== value.stage)
  )
    throw new Error('审核决定与来源不一致，请刷新核对')
  if (
    value.history.some(
      (row) =>
        row.institute_id !== value.institute_id ||
        row.patient_id !== value.patient_id ||
        row.visit_id !== value.visit_id ||
        row.rule_set_key !== value.rule_set_key,
    )
  )
    throw new Error('审核历史病例不一致，请刷新核对')
  return value as unknown as RecordReviewDetail
}
async function request(config: Parameters<typeof ApiService.requestRaw>[0]): Promise<unknown> {
  try {
    const response = await ApiService.requestRaw<unknown>(config)
    return unwrapApiEnvelope<unknown>(response.data)
  } catch (error) {
    throw new Error(extractApiErrorMessageFromError(error, '审核服务暂不可用，请刷新核对'))
  }
}
export async function listRecordReviews(
  state: ReviewState | 'open' | 'history' = 'open',
  scene?: 'running' | 'final',
  page = 1,
): Promise<RecordReviewList> {
  const value = await request({
    url: base,
    method: 'GET',
    params: { state, scene, page, page_size: 10 },
  })
  if (
    !object(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(item) ||
    !['total', 'pending_count', 'initial_count', 'recheck_count'].every(
      (key) => Number.isSafeInteger(value[key]) && Number(value[key]) >= 0,
    ) ||
    value.pending_count !== Number(value.initial_count) + Number(value.recheck_count)
  )
    throw new Error('审核待办数据无效，请刷新核对')
  return {
    items: value.items,
    total: Number(value.total),
    pending_count: Number(value.pending_count),
    initial_count: Number(value.initial_count),
    recheck_count: Number(value.recheck_count),
  }
}
export async function getRecordReviewCurrent(
  source: RecordReviewSource,
): Promise<RecordReviewDetail> {
  const value = detail(await request({ url: `${base}/current`, method: 'GET', params: source }))
  if (!matchesSource(value, source)) throw new Error('审核结果与请求来源不一致，请刷新核对')
  return value
}
export async function getRecordReviewHistory(id: string): Promise<RecordReviewDetail> {
  const value = detail(await request({ url: `${base}/${encodeURIComponent(id)}`, method: 'GET' }))
  if (value.current_review?.id !== id || value.can_submit)
    throw new Error('审核历史与请求事件不一致，请刷新核对')
  return value
}
export async function submitRecordReview(
  source: RecordReviewSource,
  expectedState: ReviewState,
  decision: ReviewDecision,
  reason: string,
  requestId: string,
): Promise<RecordReview> {
  const value = await request({
    url: base,
    method: 'POST',
    data: { source, expected_state: expectedState, decision, reason, request_id: requestId },
  })
  if (!review(value)) throw new Error('审核回执无效，请刷新核对')
  if (
    !matchesSource(value, source) ||
    value.request_id !== requestId ||
    value.decision !== decision ||
    value.reason !== (reason.trim() || null) ||
    value.stage !== (expectedState === 'pending_recheck' ? 'recheck' : 'initial')
  )
    throw new Error('审核回执与提交内容不一致，请刷新核对')
  return value
}
