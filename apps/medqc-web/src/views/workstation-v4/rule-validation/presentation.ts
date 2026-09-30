import type {
  Comparison,
  CasePurpose,
  ExpectedStatus,
  SourceKind,
  ValidationRun,
  ValidationStage,
} from '@/services/rule-validation-service'

export type StatusTone = '' | 'info' | 'success' | 'warning' | 'danger'
export type Labeled = { label: string; tone: StatusTone }

export const STAGES: Record<ValidationStage, Labeled> = {
  preparing: { label: '待准备', tone: '' },
  ready_to_run: { label: '待运行', tone: 'info' },
  running: { label: '验证中', tone: 'info' },
  reviewing: { label: '待复核', tone: 'warning' },
  pending_conclusion: { label: '待结论', tone: 'warning' },
  pending_approval: { label: '待批准', tone: 'warning' },
  approved_pending_release: { label: '已批准待发布', tone: 'success' },
  released: { label: '已上线', tone: 'success' },
  rejected: { label: '验收不通过', tone: 'danger' },
}

export const EXPECTED_STATUSES: ExpectedStatus[] = ['compliant', 'non_compliant', 'not_applicable', 'data_gap']

export const STATUS: Record<ExpectedStatus, Labeled> = {
  compliant: { label: '合规', tone: 'success' },
  non_compliant: { label: '不合规', tone: 'danger' },
  not_applicable: { label: '不适用', tone: '' },
  data_gap: { label: '资料不足', tone: 'warning' },
}

export const COMPARISONS: Record<Comparison, Labeled> = {
  same: { label: '一致', tone: 'success' },
  different: { label: '不一致', tone: 'danger' },
  missing: { label: '缺少结果', tone: 'danger' },
  ambiguous: { label: '重复结果', tone: 'danger' },
  pending: { label: '等待完成', tone: 'info' },
  failed: { label: '执行失败', tone: 'danger' },
}

export const SOURCE_KINDS: Record<SourceKind, string> = { synthetic: '合成', real_copy: '真实副本' }
export const PURPOSES: Record<CasePurpose, string> = { development: '开发集', acceptance: '独立验收集' }

export function statusClass(tone: StatusTone): string {
  return tone ? `mq-status mq-status--${tone}` : 'mq-status'
}

/** 实际状态可能是规则合同之外的交付状态，未知值按原文展示。 */
export function statusLabel(value: string | null | undefined): Labeled {
  if (!value) return { label: '—', tone: '' }
  return STATUS[value as ExpectedStatus] ?? { label: value, tone: '' }
}

export function buildLabel(run: Pick<ValidationRun, 'build_kind' | 'execution_version'> | null | undefined): string {
  if (!run?.build_kind) return '版本未记录'
  if (run.build_kind !== 'release') return '开发版本'
  const impl = run.execution_version?.lx0609_task_runtime?.implementation
  return impl?.build_id ? `正式构建 ${impl.build_id}` : '正式构建'
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
