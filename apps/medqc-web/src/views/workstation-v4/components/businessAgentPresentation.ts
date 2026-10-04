import type { BusinessAgentReference, BusinessAgentTurn } from '@/api/businessAgent'

// 仅由本轮实际返回的来源类型推出步骤名称，不编造未发生的执行过程。
const STEP_LABELS: Partial<Record<BusinessAgentReference['kind'], string>> = {
  saved_result: '读取保存结果',
  rule: '核对规则目录',
  guideline: '检索规范原文',
  statistics: '查询正式统计',
  record: '下钻病例',
  draft: '起草并校验',
  action: '生成操作预览',
  evidence: '读取业务资料',
}

export function turnSummary(turn: BusinessAgentTurn): string {
  const seconds = `${(turn.elapsed_ms / 1000).toFixed(1)} 秒`
  if (turn.status === 'stopped') return `已停止 · ${turn.tool_calls} 次查询 · ${seconds}`
  if (turn.status === 'failed') return `部分步骤失败 · ${turn.tool_calls} 次查询 · ${seconds}`
  const labels = [
    ...new Set(turn.references.map((reference) => STEP_LABELS[reference.kind]).filter(Boolean)),
  ]
  const steps = labels.length ? ` · ${labels.join('、')}` : ''
  return `已完成 ${turn.tool_calls} 次查询${steps} · ${seconds}`
}

export function statusTone(status: string): string {
  if (status === 'non_compliant' || status === 'technical_error') return 'mq-status--danger'
  if (status === 'data_gap' || status === 'needs_review' || status === 'uncertain')
    return 'mq-status--warning'
  if (status === 'compliant') return 'mq-status--success'
  return ''
}

export type FollowupIntent =
  | { label: string; kind: 'ask'; message: string }
  | { label: string; kind: 'draft' | 'explain' | 'rule'; reference: BusinessAgentReference }

// 追问建议按本轮来源类型套用固定模板，不额外调用模型；最多三条。
export function followupIntents(
  turn: BusinessAgentTurn,
  view: 'doctor' | 'manager',
): FollowupIntent[] {
  if (turn.status !== 'completed') return []
  const intents: FollowupIntent[] = []
  const issues = turn.references.filter((reference) => reference.kind === 'saved_result')
  const firstProblem = issues.find((reference) => reference.status === 'non_compliant')
  const firstGap = issues.find((reference) => reference.status === 'data_gap')
  if (firstProblem?.rule_id)
    intents.push({
      label: `第 ${firstProblem.position || 1} 条要求从哪里来？`,
      kind: 'rule',
      reference: firstProblem,
    })
  if (firstGap)
    intents.push({ label: '资料不足是漏写还是没同步？', kind: 'explain', reference: firstGap })
  if (firstProblem && view === 'doctor')
    intents.push({
      label: `帮我写第 ${firstProblem.position || 1} 条的补充`,
      kind: 'draft',
      reference: firstProblem,
    })
  if (turn.references.some((reference) => reference.kind === 'statistics') && view === 'manager') {
    intents.push({
      label: '列出这些问题对应的病例',
      kind: 'ask',
      message: '列出这些问题对应的病例',
    })
    intents.push({
      label: '生成质量会议报告草稿',
      kind: 'ask',
      message: '基于当前统计生成一份科室质量分析报告草稿',
    })
  }
  return intents.slice(0, 3)
}
