import { supabase } from '@/lib/supabase'
import { functionsGet, functionsPost } from '@/services/functionsClient'
import { evalExpression, renderMessage } from '@health-qc/rule-engine'

export interface Pagination {
  page?: number
  pageSize?: number
}

export interface DashboardStats {
  totalViolations: number
  bySeverity: Record<string, number>
  byRuleType: Record<string, number>
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  // 优先走 Edge Function（绕过 RLS，使用服务端聚合）
  try {
    const data = await functionsGet('/statistics/dashboard')
    return {
      totalViolations: Number(data?.kpis?.todayViolations ?? 0),
      bySeverity: (data?.kpis?.severityBreakdown as any) || {},
      byRuleType: {}
    }
  } catch {}

  // 回退：RPC（若已创建）
  try {
    const { data, error } = await supabase.rpc('get_rule_statistics', {})
    if (!error && data) {
      return {
        totalViolations: Number(data.total_violations || 0),
        bySeverity: (data.by_severity as any) || {},
        byRuleType: (data.by_rule_type as any) || {}
      }
    }
  } catch {}

  // 回退：从视图聚合（若视图不存在则返回默认值）
  try {
    const { data, error } = await supabase.from('yibao_rule_statistics').select('*')
    if (!error && Array.isArray(data)) {
      const byRuleType: Record<string, number> = {}
      let total = 0
      data.forEach((row: any) => {
        byRuleType[row.rule_type] = Number(row.hits || 0)
        total += Number(row.hits || 0)
      })
      return { totalViolations: total, bySeverity: {}, byRuleType }
    }
  } catch {}

  return { totalViolations: 0, bySeverity: {}, byRuleType: {} }
}

export interface RuleHit {
  ruleId: number
  code: string
  name: string
  severity: 'info' | 'warn' | 'block'
  messages: string[]
}

export async function evaluateRulesByDbContext(
  context: any,
  eventType: string = 'drug_order'
): Promise<{ hits: RuleHit[] }> {
  // 优先走 Edge Function
  try {
    const resp = await functionsPost('/evaluate-rule', { event: eventType, context, record: false })
    const hits: RuleHit[] = (resp?.hits || []).map((h: any) => ({
      ruleId: 0,
      code: h.ruleCode,
      name: h.message,
      severity: h.severity,
      messages: [h.message].filter(Boolean)
    }))
    return { hits }
  } catch {}

  // 回退：直接查表并在前端评估
  // 读取启用的规则
  const { data: rules } = await supabase
    .from('yibao_rules')
    .select('id, code, name, severity')
    .eq('enabled', true)

  if (!Array.isArray(rules) || rules.length === 0) return { hits: [] }

  const hits: RuleHit[] = []

  for (const rule of rules) {
    // 读取条件
    const { data: conds } = await supabase
      .from('yibao_rule_conditions')
      .select('priority, expression_json')
      .eq('rule_id', rule.id)
      .order('priority', { ascending: true })

    // 读取动作（消息模板）
    const { data: actions } = await supabase
      .from('yibao_rule_actions')
      .select('action_type, message_template')
      .eq('rule_id', rule.id)

    const matched = Array.isArray(conds) && conds.every((c: any) => evalExpression(context, c.expression_json))
    if (matched) {
      const messages = (Array.isArray(actions) ? actions : [])
        .map((a: any) => renderMessage(a.message_template || '', context))
        .filter(Boolean)
      hits.push({
        ruleId: rule.id,
        code: rule.code,
        name: rule.name,
        severity: (rule.severity as any) || 'warn',
        messages
      })
    }
  }

  return { hits }
}

export async function listViolations(
  params: Pagination & { severity?: string; ruleCode?: string; visitId?: string }
) {
  // 优先走 Edge Function（避免 RLS 受限）
  try {
    const page = params.page || 1
    const limit = params.pageSize || 10
    const qs = new URLSearchParams()
    qs.set('page', String(page))
    qs.set('limit', String(limit))
    if (params.severity) qs.set('severity', params.severity)
    if (params.ruleCode) qs.set('rule_code', params.ruleCode)
    if (params.visitId) qs.set('visit_id', params.visitId)
    const resp = await functionsGet(`/violations?${qs.toString()}`)
    const rows = resp?.data || []
    const total = resp?.pagination?.total ?? rows.length
    return { rows, total }
  } catch {}

  // 回退：直接读取表
  const page = params.page || 1
  const pageSize = params.pageSize || 10
  let query = supabase
    .from('yibao_violations')
    .select('*', { count: 'exact' })
    .order('created_at', { ascending: false })
  if (params.severity) query = query.eq('severity', params.severity)
  if (params.visitId) query = query.eq('visit_id', params.visitId)

  if (params.ruleCode) {
    try {
      const { data: ruleByCode } = await supabase
        .from('yibao_rules')
        .select('id')
        .eq('code', params.ruleCode)
        .limit(1)
        .maybeSingle()
      const ruleId = (ruleByCode as any)?.id
      if (!ruleId) return { rows: [], total: 0 }
      query = query.eq('rule_id', ruleId)
    } catch {
      return { rows: [], total: 0 }
    }
  }
  const start = (page - 1) * pageSize
  const end = start + pageSize - 1
  const { data, count } = await query.range(start, end)
  return { rows: data || [], total: count || 0 }
}

export async function listAuditTasks(params: Pagination) {
  const page = params.page || 1
  const pageSize = params.pageSize || 10
  const start = (page - 1) * pageSize
  const end = start + pageSize - 1
  const { data, count } = await supabase
    .from('yibao_audit_tasks')
    .select('*', { count: 'exact' })
    .order('created_at', { ascending: false })
    .range(start, end)
  return { rows: data || [], total: count || 0 }
}

export async function toggleRuleEnabled(id: number, enabled: boolean) {
  // 优先 Edge Function，避免 RLS 限制
  try {
    const resp = await functionsPost('/rules?action=toggle', { id, enabled })
    if (resp?.success) return resp.data
  } catch {}

  // 回退：直接更新（若当前会话具备权限）
  const { data, error } = await supabase.from('yibao_rules').update({ enabled }).eq('id', id).select('*').maybeSingle()
  if (error) throw error
  return data
}

export async function saveRule(payload: {
  rule: any
  conditions: Array<{ priority?: number; expression_json: any }>
  actions: Array<{ action_type: string; message_template: string }>
  triggers?: Array<{ event_type: string; priority?: number }>
}) {
  try {
    const resp = await functionsPost('/rules?action=save', payload)
    if (resp?.success) return resp.data
    throw new Error(resp?.error || '保存失败')
  } catch (e) {
    throw e
  }
}

// Dashboard: Trends & Top Rules
export interface TrendItem { date: string; block: number; warn: number; info: number; total: number }
export async function fetchViolationTrends(days: number = 30): Promise<TrendItem[]> {
  const data = await functionsGet(`/statistics/trends?days=${days}`)
  const arr = Array.isArray(data?.trends) ? data.trends : []
  return arr.map((t: any) => ({
    date: t.date,
    block: Number(t.block || 0),
    warn: Number(t.warn || 0),
    info: Number(t.info || 0),
    total: Number(t.block || 0) + Number(t.warn || 0) + Number(t.info || 0)
  }))
}

export interface RuleTopItem {
  ruleId: number; code: string; name: string; ruleType: string;
  totalViolations: number; blockCount: number; warnCount: number; infoCount: number
}
export async function fetchTopRules(limit: number = 10): Promise<RuleTopItem[]> {
  const data = await functionsGet('/statistics/rules')
  const arr: RuleTopItem[] = Array.isArray(data?.rules) ? data.rules : []
  return arr.slice(0, limit)
}

export async function fetchRulesOverview(): Promise<{ total: number; enabled: number; bySeverity: { info: number; warn: number; block: number } }> {
  const { data: totalList } = await supabase.from('yibao_rules').select('id, severity, enabled')
  const total = Array.isArray(totalList) ? totalList.length : 0
  const enabled = Array.isArray(totalList) ? totalList.filter(r => (r as any).enabled).length : 0
  const bySeverity = { info: 0, warn: 0, block: 0 }
  if (Array.isArray(totalList)) totalList.forEach((r: any) => { if (bySeverity[r.severity as 'info'|'warn'|'block'] !== undefined) bySeverity[r.severity as 'info'|'warn'|'block']++ })
  return { total, enabled, bySeverity }
}


