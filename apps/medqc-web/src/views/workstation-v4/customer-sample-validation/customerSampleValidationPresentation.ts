import type { ManualSamplePoolRecord, ManualSampleValidationRuleSet } from './types'

export function coverageLabel(value: string): string {
  if (value === 'llm_intrinsic') return '内涵验证'
  if (value === 'programmatic') return '程序规则'
  if (value === 'unsupported') return '未纳入'
  return value || '-'
}

export function validationModeLabel(value: string): string {
  if (value === 'formal_fast_screen_full') return '正式84条质控'
  if (value === 'programmatic') return '硬门槛程序规则'
  if (value === 'sc') return 'SC 样本规则'
  return '客户样本复现'
}

export function ruleSetScopeLabel(value?: string): string {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
  if (normalized === 'final') return '终末病历'
  if (normalized === 'running') return '运行中病历'
  if (normalized === 'all') return '运行中/终末'
  return value || '-'
}

export function coverageStatusText(ruleSet?: ManualSampleValidationRuleSet): string {
  if (!ruleSet) return '-'
  const explicitStatus = String(ruleSet.coverage_status || '').trim()
  if (explicitStatus) return explicitStatus
  const summaryText = Object.entries(ruleSet.coverage_summary || {})
    .filter(([, value]) => Number.isFinite(Number(value)))
    .map(([label, value]) => `${label} ${value}`)
    .join(' / ')
  if (summaryText) return summaryText
  if (ruleSet.advanced) return '高级验证模式'
  return '已纳入主验证规则集'
}

export function matchStatusLabel(value: string): string {
  if (value === 'matched') return '已关联病历'
  if (value === 'ambiguous') return '待人工确认'
  if (value === 'unmatched') return '未找到病历'
  return value || '-'
}

export function matchStatusHint(value: string): string {
  if (value === 'matched') return '已定位到真实病历，可继续同步文书。'
  if (value === 'ambiguous') return '同号命中多次住院，请先确认归属病历。'
  if (value === 'unmatched') return '请核对住院号、姓名或日期后重新匹配。'
  return '请先完成病历匹配。'
}

export function bundleStatusLabel(value: string): string {
  if (value === 'ready') return '已就绪'
  if (value === 'missing') return '待同步'
  if (value === 'pending') return '准备中'
  return value || '-'
}

export function bundleStatusHint(value: string): string {
  if (value === 'ready') return '可以查看病历并开始样本验证。'
  if (value === 'pending') return '正在刷新文书和 bundle，请稍后再看。'
  if (value === 'missing') return '下一步执行“同步样本病历”。'
  return '请先完成病历同步。'
}

export function summarizeRuleScopes(ruleIds: string[]): string {
  const scopes: string[] = []
  const pushScope = (label: string) => {
    if (!scopes.includes(label)) scopes.push(label)
  }
  const rules = new Set((ruleIds || []).map((item) => String(item || '').trim()).filter(Boolean))
  for (const ruleId of rules) {
    if (ruleId.startsWith('CL-')) {
      pushScope('客户专项规则包')
      continue
    }
    const num = Number.parseInt(ruleId.replace('SC-', ''), 10)
    if (Number.isNaN(num)) continue
    if (num <= 20) pushScope('入院记录')
    else if (num <= 27) pushScope('首次病程')
    else if (
      num <= 49 ||
      num === 70 ||
      num === 73 ||
      num === 74 ||
      num === 79 ||
      num === 143 ||
      num === 146
    )
      pushScope('日常病程')
    else if (num <= 60) pushScope('查房讨论')
    else if (num <= 76) pushScope('交接会诊')
    else if (num <= 115) pushScope('手术麻醉')
    else if (num <= 127) pushScope('出院记录')
    else if (num <= 136) pushScope('知情同意')
    else if (num <= 140) pushScope('检查检验')
  }
  return scopes.join(' / ') || '-'
}

export function formatDateTime(value?: string): string {
  if (!value) return '-'
  const text = value.trim()
  const normalized = text.includes('T') ? text : text.replace(' ', 'T')
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  const date = new Date(hasTimezone ? normalized : `${normalized}Z`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

export function resolveRecordHospitalizationBadge(record: ManualSamplePoolRecord): {
  status: 'active' | 'discharged' | 'unknown'
  label: string
  title: string
} {
  const status = String(record.hospitalization_status || '').toLowerCase()
  if (status === 'active') return { status: 'active', label: '在院', title: '当前仍在院' }
  if (status === 'discharged') {
    const dischargeTime = String(record.discharge_time || '').trim()
    return {
      status: 'discharged',
      label: '已出院',
      title: dischargeTime ? `已出院 · ${formatDateTime(dischargeTime)}` : '已出院',
    }
  }
  return { status: 'unknown', label: '状态待同步', title: '尚未同步到可信的住院状态' }
}

export function getBatchJobStatusText(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return '已完成'
  if (normalized === 'running') return '执行中'
  if (normalized === 'failed') return '失败'
  if (normalized === 'canceled') return '已取消'
  return '排队中'
}

export function getBatchJobStatusTagClass(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  if (normalized === 'running') return 'border-blue-200 bg-blue-50 text-[#0057b8]'
  if (normalized === 'failed') return 'border-rose-200 bg-rose-50 text-rose-700'
  if (normalized === 'canceled') return 'border-slate-200 bg-slate-100 text-slate-600'
  return 'border-amber-200 bg-amber-50 text-amber-700'
}

export function syncJobStatusText(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return '已完成'
  if (normalized === 'running') return '执行中'
  if (normalized === 'failed') return '失败'
  return '排队中'
}

export function syncJobStatusColor(status?: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') return 'success'
  if (normalized === 'running') return 'processing'
  if (normalized === 'failed') return 'error'
  return 'default'
}
