/**
 * V5 运行/终末病历列表的筛选快照与 URL query 映射。
 *
 * 合同第 4 节：URL query 是当前筛选的唯一来源；快捷筛选、应用模板、重置都等同于写入 query。
 * 快照键与筛选模板 filters 白名单同名，模板可直接保存/应用；页码与分页大小不进入快照。
 */

import type { LocationQuery, LocationQueryRaw } from 'vue-router'
import type { FilterTemplateFilters } from '@/api/filterTemplates'
import type { RecordScoreFilterStatus } from '@/api/filterTemplates'
import { ANALYTICS_DRILLDOWN_QUERY_KEYS } from '../analyticsDrilldown'
import type { RecordLatestReviewState } from '../types'

/** 本页暴露的筛选项；date_field 与 inpatient_sort 由页面固定，不参与模板。 */
export type RecordFilterSnapshot = Pick<
  FilterTemplateFilters,
  | 'dept'
  | 'doctor'
  | 'keyword'
  | 'start_date'
  | 'end_date'
  | 'review_state'
  | 'standard_id'
  | 'score_status'
  | 'grade'
  | 'score_min'
  | 'score_max'
  | 'result_view'
  | 'defect_source'
  | 'defect_workflow'
  | 'has_defect'
>

/** 审核状态固定顺序，保证同一组合的 query 与签名稳定。 */
export const REVIEW_STATE_VALUES: readonly RecordLatestReviewState[] = [
  'pending_review',
  'pending_recheck',
  'approved',
  'doubtful',
]

/** 快照键 → URL query 键；科室沿用既有下钻参数名 department。 */
const QUERY_KEY_BY_FIELD = {
  dept: 'department',
  doctor: 'doctor',
  keyword: 'keyword',
  start_date: 'start_date',
  end_date: 'end_date',
  review_state: 'review_state',
  standard_id: 'standard_id',
  score_status: 'score_status',
  grade: 'grade',
  score_min: 'score_min',
  score_max: 'score_max',
  result_view: 'result_view',
  defect_source: 'defect_source',
  defect_workflow: 'defect_workflow',
  has_defect: 'has_defect',
} as const satisfies Record<keyof RecordFilterSnapshot, string>

export const RECORD_FILTER_QUERY_KEYS: readonly string[] = Object.values(QUERY_KEY_BY_FIELD)

/**
 * 仅前端使用的 URL 标记：审核角色显式选择“全部”时写入 `review_scope=all`，
 * 使刷新后仍视为“URL 显式给出范围”而不套系统默认。不进入快照、模板或后端请求。
 */
export const REVIEW_SCOPE_QUERY_KEY = 'review_scope'
export const REVIEW_SCOPE_ALL = 'all'

/**
 * 写 query 时对 review_scope 标记的处理：
 * - true：写入（仅当快照无审核状态时有效）；false：移除；undefined：沿用当前 query 中的标记。
 */
export type ReviewScopeAllIntent = boolean | undefined

const TEXT_FIELDS = [
  'dept',
  'doctor',
  'keyword',
  'start_date',
  'end_date',
  'standard_id',
  'grade',
] as const
const SCORE_STATUS_VALUES: readonly RecordScoreFilterStatus[] = [
  'scored',
  'no_standard',
  'unavailable',
]
const NUMBER_FIELDS = ['score_min', 'score_max'] as const
const RESULT_VIEW_VALUES = ['records', 'defects'] as const
const DEFECT_SOURCE_VALUES = ['all', 'auto', 'manual'] as const

function isReviewState(value: unknown): value is RecordLatestReviewState {
  return typeof value === 'string' && (REVIEW_STATE_VALUES as readonly string[]).includes(value)
}

function firstQueryText(value: LocationQuery[string] | undefined): string {
  const first = Array.isArray(value) ? value[0] : value
  return typeof first === 'string' ? first.trim() : ''
}

/** 去空白、丢弃空值、审核状态去重并按固定顺序排列。 */
export function normalizeRecordFilter(snapshot: RecordFilterSnapshot): RecordFilterSnapshot {
  const normalized: RecordFilterSnapshot = {}
  for (const field of TEXT_FIELDS) {
    const text = String(snapshot[field] ?? '').trim()
    if (text) normalized[field] = text
  }
  const states = new Set((snapshot.review_state ?? []).filter(isReviewState))
  const reviewState = REVIEW_STATE_VALUES.filter((state) => states.has(state))
  if (reviewState.length > 0) normalized.review_state = reviewState
  if (SCORE_STATUS_VALUES.includes(snapshot.score_status as RecordScoreFilterStatus)) {
    normalized.score_status = snapshot.score_status
  }
  for (const field of NUMBER_FIELDS) {
    const value = Number(snapshot[field])
    if (snapshot[field] !== undefined && snapshot[field] !== null && Number.isFinite(value)) {
      normalized[field] = value
    }
  }
  if (snapshot.result_view && RESULT_VIEW_VALUES.includes(snapshot.result_view)) {
    normalized.result_view = snapshot.result_view
  }
  if (snapshot.defect_source && DEFECT_SOURCE_VALUES.includes(snapshot.defect_source)) {
    normalized.defect_source = snapshot.defect_source
  }
  if (typeof snapshot.has_defect === 'boolean') normalized.has_defect = snapshot.has_defect
  if (
    normalized.result_view === 'defects' &&
    (snapshot.defect_workflow === 'clinical_appeal' ||
      snapshot.defect_workflow === 'pending_rectification')
  ) {
    normalized.defect_workflow = snapshot.defect_workflow
  }
  return normalized
}

/** 从 URL query 解析筛选；非法审核状态值被忽略，不猜测。 */
export function parseRecordFilterQuery(query: LocationQuery): RecordFilterSnapshot {
  const snapshot: RecordFilterSnapshot = {}
  for (const field of TEXT_FIELDS) {
    const text = firstQueryText(query[QUERY_KEY_BY_FIELD[field]])
    if (text) snapshot[field] = text
  }
  const reviewText = firstQueryText(query[QUERY_KEY_BY_FIELD.review_state])
  if (reviewText) {
    snapshot.review_state = reviewText
      .split(',')
      .map((item) => item.trim()) as RecordLatestReviewState[]
  }
  const scoreStatus = firstQueryText(query[QUERY_KEY_BY_FIELD.score_status])
  if (scoreStatus) snapshot.score_status = scoreStatus as RecordScoreFilterStatus
  for (const field of NUMBER_FIELDS) {
    const text = firstQueryText(query[QUERY_KEY_BY_FIELD[field]])
    if (text) snapshot[field] = Number(text)
  }
  const resultView = firstQueryText(query[QUERY_KEY_BY_FIELD.result_view])
  if (resultView === 'records' || resultView === 'defects') snapshot.result_view = resultView
  const defectSource = firstQueryText(query[QUERY_KEY_BY_FIELD.defect_source])
  if (defectSource === 'all' || defectSource === 'auto' || defectSource === 'manual') {
    snapshot.defect_source = defectSource
  }
  const hasDefect = firstQueryText(query[QUERY_KEY_BY_FIELD.has_defect])
  const workflow = firstQueryText(query[QUERY_KEY_BY_FIELD.defect_workflow])
  if (workflow === 'clinical_appeal' || workflow === 'pending_rectification') {
    snapshot.defect_workflow = workflow
  }
  if (hasDefect === 'true' || hasDefect === 'false') snapshot.has_defect = hasDefect === 'true'
  return normalizeRecordFilter(snapshot)
}

export function recordFilterSignature(snapshot: RecordFilterSnapshot): string {
  const normalized = normalizeRecordFilter(snapshot)
  return JSON.stringify([
    ...TEXT_FIELDS.map((field) => normalized[field] ?? ''),
    (normalized.review_state ?? []).join(','),
    normalized.score_status ?? '',
    ...NUMBER_FIELDS.map((field) => normalized[field] ?? ''),
    normalized.result_view ?? '',
    normalized.defect_source ?? '',
    normalized.defect_workflow ?? '',
    normalized.has_defect === undefined ? '' : String(normalized.has_defect),
  ])
}

export function isSameRecordFilter(
  left: RecordFilterSnapshot,
  right: RecordFilterSnapshot,
): boolean {
  return recordFilterSignature(left) === recordFilterSignature(right)
}

export function isEmptyRecordFilter(snapshot: RecordFilterSnapshot): boolean {
  return Object.keys(normalizeRecordFilter(snapshot)).length === 0
}

/** 用新筛选替换 query 中的筛选键，保留下钻、record_key 等非筛选参数。 */
export function mergeRecordFilterQuery(
  current: LocationQuery,
  snapshot: RecordFilterSnapshot,
  reviewScopeAll?: ReviewScopeAllIntent,
): LocationQueryRaw {
  const next: LocationQueryRaw = {}
  for (const [key, value] of Object.entries(current)) {
    if (!RECORD_FILTER_QUERY_KEYS.includes(key) && key !== REVIEW_SCOPE_QUERY_KEY) {
      next[key] = value
    }
  }
  const normalized = normalizeRecordFilter(snapshot)
  for (const field of TEXT_FIELDS) {
    const text = normalized[field]
    if (text) next[QUERY_KEY_BY_FIELD[field]] = text
  }
  if (normalized.review_state) {
    next[QUERY_KEY_BY_FIELD.review_state] = normalized.review_state.join(',')
  }
  if (normalized.score_status) {
    next[QUERY_KEY_BY_FIELD.score_status] = normalized.score_status
  }
  for (const field of NUMBER_FIELDS) {
    const value = normalized[field]
    if (value !== undefined) next[QUERY_KEY_BY_FIELD[field]] = String(value)
  }
  if (normalized.result_view) {
    next[QUERY_KEY_BY_FIELD.result_view] = normalized.result_view
  }
  if (normalized.defect_source) {
    next[QUERY_KEY_BY_FIELD.defect_source] = normalized.defect_source
  }
  if (normalized.has_defect !== undefined) {
    next[QUERY_KEY_BY_FIELD.has_defect] = String(normalized.has_defect)
  }
  if (normalized.defect_workflow)
    next[QUERY_KEY_BY_FIELD.defect_workflow] = normalized.defect_workflow
  const keepScopeAll =
    reviewScopeAll ?? firstQueryText(current[REVIEW_SCOPE_QUERY_KEY]) === REVIEW_SCOPE_ALL
  if (keepScopeAll && !normalized.review_state) {
    next[REVIEW_SCOPE_QUERY_KEY] = REVIEW_SCOPE_ALL
  }
  return next
}

/**
 * URL 是否已显式给出列表范围：筛选键、三坐标定位（record_key）或统计下钻参数。
 * 显式时以 URL 为准，不再套用系统默认或默认模板。
 */
export function hasExplicitRecordQuery(query: LocationQuery): boolean {
  const keys = [...RECORD_FILTER_QUERY_KEYS, 'record_key', ...ANALYTICS_DRILLDOWN_QUERY_KEYS]
  if (firstQueryText(query[REVIEW_SCOPE_QUERY_KEY]) === REVIEW_SCOPE_ALL) return true
  return keys.some((key) => firstQueryText(query[key]) !== '')
}
