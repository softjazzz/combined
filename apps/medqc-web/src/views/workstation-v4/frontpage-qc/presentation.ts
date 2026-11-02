/** 首页质控 V2 页面展示：文案、色调与分组，不含业务判定。 */
import type {
  FrontpageQcFinding,
  FrontpageQcGrade,
  FrontpageQcReviewStatus,
  FrontpageQcRun,
  FrontpageQcRunStatus,
  FrontpageQcSection,
  FrontpageQcSeverity,
} from '@/services/frontpage-qc-v2-service'

export type StatusTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral'

export const GRADE_LABELS: Record<FrontpageQcGrade, string> = {
  excellent: '优秀',
  qualified: '合格',
  unqualified: '不合格',
}

export const GRADE_TONES: Record<FrontpageQcGrade, StatusTone> = {
  excellent: 'success',
  qualified: 'warning',
  unqualified: 'danger',
}

export const SECTION_LABELS: Record<FrontpageQcSection, string> = {
  patient: '患者信息',
  hospitalization: '住院信息',
  diagnosis: '诊疗信息',
  cost: '费用信息',
}

export const SECTION_ORDER: FrontpageQcSection[] = ['patient', 'hospitalization', 'diagnosis', 'cost']

export const SEVERITY_LABELS: Record<FrontpageQcSeverity, string> = {
  deduct: '扣分',
  required: '必填缺项',
  hint: '提示',
}

export const REVIEW_LABELS: Record<FrontpageQcReviewStatus, string> = {
  pending: '待复核',
  confirmed: '已确认',
  false_alarm: '误报',
}

export const RUN_STATUS_LABELS: Record<FrontpageQcRunStatus, string> = {
  queued: '排队中',
  running: '质控中',
  completed: '已完成',
  completed_with_errors: '部分完成',
  failed: '失败',
  cancelled: '已取消',
}

export function runTone(status: FrontpageQcRunStatus): StatusTone {
  if (status === 'completed') return 'success'
  if (status === 'completed_with_errors' || status === 'cancelled') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

export function runProgressPercent(run: Pick<FrontpageQcRun, 'processed_records' | 'total_records'>): number {
  if (!run.total_records) return 0
  return Math.min(100, Math.round((run.processed_records / run.total_records) * 100))
}

export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return '—'
  return Number.isInteger(score) ? String(score) : score.toFixed(1)
}

export function formatPercent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return '—'
  return `${Math.round(rate * 1000) / 10}%`
}

export function formatDateTime(value: string | null | undefined): string {
  const text = String(value || '').trim()
  if (!text) return '—'
  const date = new Date(text)
  if (Number.isNaN(date.getTime())) return text.slice(0, 16)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export interface FindingGroups {
  /** 扣分与必填缺项，按首页四部分分组 */
  sections: Array<{ section: FrontpageQcSection; label: string; findings: FrontpageQcFinding[] }>
  hints: FrontpageQcFinding[]
  dataGaps: FrontpageQcFinding[]
}

export function groupFindings(findings: FrontpageQcFinding[]): FindingGroups {
  const failing = findings.filter((f) => f.verdict === 'fail' && f.severity !== 'hint')
  const bySection = SECTION_ORDER.map((section) => ({
    section,
    label: SECTION_LABELS[section],
    findings: failing
      .filter((f) => f.section === section)
      .sort((a, b) => b.deduction - a.deduction || a.rule_id.localeCompare(b.rule_id)),
  })).filter((group) => group.findings.length > 0)
  return {
    sections: bySection,
    hints: findings.filter((f) => f.verdict === 'fail' && f.severity === 'hint'),
    dataGaps: findings.filter((f) => f.verdict === 'data_gap'),
  }
}

export function detailValueText(value: string | null | undefined): string {
  const text = String(value ?? '').trim()
  return text ? `“${text}”` : '未填写'
}

/** 资料不足按原因汇总，供“资料不足”折叠区展示 */
export function summarizeDataGaps(findings: FrontpageQcFinding[]): Array<{ reason: string; rules: string[] }> {
  const map = new Map<string, string[]>()
  for (const finding of findings) {
    const reason = finding.reason || '资料不足'
    const list = map.get(reason) ?? []
    list.push(finding.rule_name)
    map.set(reason, list)
  }
  return [...map.entries()].map(([reason, rules]) => ({ reason, rules }))
}
