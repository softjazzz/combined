import type { LocationQuery, LocationQueryRaw } from 'vue-router'

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

export interface AnalyticsDrilldown {
  ruleId: string
  scope: string
  completedFrom: string
  completedTo: string
  jobId: string
  resultStatus: string
  department: string
}

function queryText(query: LocationQuery, key: string): string {
  const value = query[key]
  const raw = Array.isArray(value) ? value[0] : value
  return typeof raw === 'string' ? raw.trim() : ''
}

/** 只有 source=analytics 且至少带一个统计参数时才视为统计下钻。 */
export function readAnalyticsDrilldown(query: LocationQuery): AnalyticsDrilldown | null {
  if (queryText(query, 'source') !== 'analytics') return null
  if (!ANALYTICS_DRILLDOWN_KEYS.some((key) => queryText(query, key))) return null
  return {
    ruleId: queryText(query, 'analytics_rule_id'),
    scope: queryText(query, 'analytics_scope'),
    completedFrom: queryText(query, 'analytics_completed_from'),
    completedTo: queryText(query, 'analytics_completed_to'),
    jobId: queryText(query, 'analytics_job_id'),
    resultStatus: queryText(query, 'analytics_result_status'),
    department: queryText(query, 'department'),
  }
}

/** 下钻参数的稳定签名：用于在同一页面内（返回/前进）检测下钻条件变化并重新加载。 */
export function analyticsDrilldownSignature(query: LocationQuery): string {
  return ANALYTICS_DRILLDOWN_KEYS.map((key) => queryText(query, key)).join('|')
}

/** 清除下钻后保留的查询：去掉 source 与全部统计参数，其余筛选保持不变。 */
export function withoutAnalyticsDrilldown(query: LocationQuery): LocationQueryRaw {
  const next: LocationQueryRaw = { ...query }
  delete next.source
  for (const key of ANALYTICS_DRILLDOWN_KEYS) delete next[key]
  return next
}

/** 返回统计页时还原统计页自己的筛选参数名。 */
export function analyticsStatsQuery(drilldown: AnalyticsDrilldown): LocationQueryRaw {
  return {
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
