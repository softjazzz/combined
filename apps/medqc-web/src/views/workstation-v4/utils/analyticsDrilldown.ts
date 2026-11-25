import type { LocationQuery, LocationQueryRaw } from 'vue-router'
import { QC_RESULT_STATUS_LABELS } from './qcResultStatusLabels'

/** 统计分析下钻到病历池时携带的查询参数，与后端 /api/medical-records/workstation 的同名参数一致。 */
export const ANALYTICS_DRILLDOWN_KEYS = [
  'analytics_job_id',
  'analytics_completed_from',
  'analytics_completed_to',
  'analytics_rule_id',
  'analytics_result_status',
  'analytics_scope',
] as const

export const ANALYTICS_STATS_PATH = '/workstation-v5/stats'
export const ANALYTICS_WORKLIST_PATH = '/workstation-v5/worklist'
export const ANALYTICS_PROBLEM_RESULT_STATUSES = [
  'non_compliant',
  'data_gap',
  'uncertain',
] as const
export const ANALYTICS_PROBLEM_RESULT_STATUS_PARAM = ANALYTICS_PROBLEM_RESULT_STATUSES.join(',')

export interface AnalyticsDrilldown {
  ruleId: string
  /** 仅用于展示，来自 analytics_rule_name，不发给后端 */
  ruleName: string
  scope: string
  completedFrom: string
  completedTo: string
  jobId: string
  resultStatus: string
  department: string
}

type QueryLike = LocationQuery | Record<string, unknown>

function queryText(query: QueryLike, key: string): string {
  const value = query[key]
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' ? raw.trim() : ''
}

export function parseAnalyticsResultStatuses(
  status: unknown,
): string[] {
  const chunks = Array.isArray(status)
    ? status.flatMap((entry) => (typeof entry === 'string' ? entry.split(',') : []))
    : typeof status === 'string'
      ? status.split(',')
      : []
  const seen = new Set<string>()
  const statuses: string[] = []
  for (const chunk of chunks) {
    const normalized = chunk.trim()
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    statuses.push(normalized)
  }
  return statuses
}

export function normalizeAnalyticsResultStatus(status: unknown): string {
  return parseAnalyticsResultStatuses(status).join(',')
}

function drilldownKeyText(query: QueryLike, key: (typeof ANALYTICS_DRILLDOWN_KEYS)[number]): string {
  if (key === 'analytics_result_status') {
    return normalizeAnalyticsResultStatus(query[key])
  }
  return queryText(query, key)
}

/** 只有 source=analytics 且至少带一个统计参数时才视为统计下钻。 */
export function readAnalyticsDrilldown(query: QueryLike): AnalyticsDrilldown | null {
  if (queryText(query, 'source') !== 'analytics') return null
  if (!ANALYTICS_DRILLDOWN_KEYS.some((key) => drilldownKeyText(query, key))) return null
  return {
    ruleId: queryText(query, 'analytics_rule_id'),
    ruleName: queryText(query, 'analytics_rule_name'),
    scope: queryText(query, 'analytics_scope'),
    completedFrom: queryText(query, 'analytics_completed_from'),
    completedTo: queryText(query, 'analytics_completed_to'),
    jobId: queryText(query, 'analytics_job_id'),
    resultStatus: normalizeAnalyticsResultStatus(query.analytics_result_status),
    department: queryText(query, 'department'),
  }
}

/** 下钻参数的稳定签名：用于在同一页面内（返回/前进）检测下钻条件与科室变化并重新加载。 */
export function analyticsDrilldownSignature(query: QueryLike): string {
  return [
    ...ANALYTICS_DRILLDOWN_KEYS.map((key) => drilldownKeyText(query, key)),
    queryText(query, 'department'),
  ].join('|')
}

/** 清除下钻后保留的查询：去掉 source、department 与全部统计参数，其余筛选保持不变。 */
export function withoutAnalyticsDrilldown(query: LocationQuery): LocationQueryRaw {
  const next: LocationQueryRaw = { ...query }
  delete next.source
  delete next.department
  delete next.analytics_rule_name
  for (const key of ANALYTICS_DRILLDOWN_KEYS) delete next[key]
  return next
}

/** 返回统计页时还原统计页自己的筛选参数名。 */
export function analyticsStatsQuery(drilldown: AnalyticsDrilldown): LocationQueryRaw {
  const department = drilldown.department.trim()
  return {
    ...(department ? { view: 'department', department } : {}),
    completed_from: drilldown.completedFrom || undefined,
    completed_to: drilldown.completedTo || undefined,
    job_id: drilldown.jobId || undefined,
  }
}

export function analyticsScopeLabel(scope: string): string {
  if (scope === 'final') return '终末质控'
  if (scope === 'running') return '运行质控'
  return scope || '全部范围'
}

const ANALYTICS_RESULT_STATUS_LABELS: Record<string, string> = {
  ...QC_RESULT_STATUS_LABELS,
  compliant: '合规',
  not_applicable: '不适用',
  not_executed: '未执行',
}

const PROBLEM_STATUS_SET = new Set<string>(ANALYTICS_PROBLEM_RESULT_STATUSES)

export function analyticsResultStatusLabel(status: string): string {
  const statuses = parseAnalyticsResultStatuses(status)
  if (!statuses.length) return ''
  if (statuses.length === 1) {
    return ANALYTICS_RESULT_STATUS_LABELS[statuses[0]] || statuses[0]
  }
  if (
    statuses.length === PROBLEM_STATUS_SET.size &&
    statuses.every((item) => PROBLEM_STATUS_SET.has(item))
  ) {
    return '存在问题'
  }
  return statuses.map((item) => ANALYTICS_RESULT_STATUS_LABELS[item] || item).join(' / ')
}
