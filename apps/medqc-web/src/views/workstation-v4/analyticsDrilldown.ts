/**
 * 统计页/首页到病历列表的下钻上下文。
 *
 * 该上下文只有一条资料链：URL 参数 → `usePatientRecords` → 后端
 * `/api/medical-records/workstation` 的 `analytics_*` 查询项。
 * 页面不得自行拼装或猜测参数，避免下钻范围在不同入口下口径不一致。
 */

export const ANALYTICS_DRILLDOWN_QUERY_KEYS = [
  'source',
  'analytics_scope',
  'analytics_result_status',
  'analytics_job_id',
  'analytics_completed_from',
  'analytics_completed_to',
  'analytics_rule_id',
] as const

export const ANALYTICS_RESULT_STATUS_LABELS: Record<string, string> = {
  non_compliant: '确定问题',
  data_gap: '资料待核实',
  uncertain: '待判断',
  compliant: '合规',
  not_applicable: '不适用',
  not_executed: '未执行',
  technical_error: '技术异常',
}

export interface AnalyticsDrilldown {
  scope: string
  resultStatus: string
  ruleId: string
  jobId: string
  completedFrom: string
  completedTo: string
}

/**
 * 退出下钻必须回到病历池的显式路由；只清 query 会让 `/workstation-v5`
 * 的入口判定回退成首页，用户会丢失当前列表视图。
 */
export const ANALYTICS_DRILLDOWN_RESET_PATH = '/workstation-v5/worklist'

function readValue(source: unknown): string {
  if (Array.isArray(source)) return String(source[0] ?? '').trim()
  if (source === null || source === undefined) return ''
  return String(source).trim()
}

function toSearchParams(input: string | URLSearchParams): URLSearchParams {
  return typeof input === 'string' ? new URLSearchParams(input) : input
}

/** 解析下钻上下文；没有任何 `analytics_*` 参数时返回 `null`，表示未处于下钻状态。 */
export function parseAnalyticsDrilldown(
  input: string | URLSearchParams,
): AnalyticsDrilldown | null {
  const params = toSearchParams(input)
  const hasDrilldown = ANALYTICS_DRILLDOWN_QUERY_KEYS.some(
    (key) => key !== 'source' && readValue(params.get(key)) !== '',
  )
  if (!hasDrilldown) return null
  return {
    scope: readValue(params.get('analytics_scope')),
    resultStatus: readValue(params.get('analytics_result_status')),
    ruleId: readValue(params.get('analytics_rule_id')),
    jobId: readValue(params.get('analytics_job_id')),
    completedFrom: readValue(params.get('analytics_completed_from')),
    completedTo: readValue(params.get('analytics_completed_to')),
  }
}

/** 路由 query 形式的下钻判定，用于入口分流，不读取其它启动参数。 */
export function parseAnalyticsDrilldownFromQuery(
  query: Record<string, unknown>,
): AnalyticsDrilldown | null {
  const params = new URLSearchParams()
  for (const key of ANALYTICS_DRILLDOWN_QUERY_KEYS) {
    const value = readValue(query[key])
    if (value !== '') params.set(key, value)
  }
  return parseAnalyticsDrilldown(params)
}

export function hasAnalyticsDrilldownQuery(query: Record<string, unknown>): boolean {
  return parseAnalyticsDrilldownFromQuery(query) !== null
}

/** 去掉下钻参数，保留其余查询条件；返回新的 search（不含 `?`）。 */
export function stripAnalyticsDrilldown(search: string | URLSearchParams): string {
  const params = new URLSearchParams(toSearchParams(search).toString())
  for (const key of ANALYTICS_DRILLDOWN_QUERY_KEYS) {
    params.delete(key)
  }
  return params.toString()
}

/** 去掉下钻参数后的路由 query，供 `router.replace` 使用。 */
export function stripAnalyticsDrilldownQuery(
  query: Record<string, unknown>,
): Record<string, string> {
  const result: Record<string, string> = {}
  for (const [key, value] of Object.entries(query)) {
    const text = readValue(value)
    if (text !== '') result[key] = text
  }
  for (const key of ANALYTICS_DRILLDOWN_QUERY_KEYS) {
    delete result[key]
  }
  return result
}

/** 退出下钻的目标地址。 */
export function resolveAnalyticsDrilldownResetLocation(query: Record<string, unknown>): {
  path: string
  query: Record<string, string>
} {
  return {
    path: ANALYTICS_DRILLDOWN_RESET_PATH,
    query: stripAnalyticsDrilldownQuery(query),
  }
}

/** 生成可读的下钻范围标签，空值不占位。 */
export function describeAnalyticsDrilldown(drilldown: AnalyticsDrilldown): string[] {
  const parts: string[] = []
  if (drilldown.scope === 'final') parts.push('结果范围：最终结果')
  else if (drilldown.scope) parts.push(`结果范围：${drilldown.scope}`)
  if (drilldown.resultStatus) {
    const label = ANALYTICS_RESULT_STATUS_LABELS[drilldown.resultStatus] || drilldown.resultStatus
    parts.push(`结果状态：${label}`)
  }
  if (drilldown.ruleId) parts.push(`质控点：${drilldown.ruleId}`)
  if (drilldown.jobId) parts.push(`质控任务：${drilldown.jobId}`)
  if (drilldown.completedFrom || drilldown.completedTo) {
    parts.push(
      `质控完成：${drilldown.completedFrom || '不限'} 至 ${drilldown.completedTo || '不限'}`,
    )
  }
  return parts
}
