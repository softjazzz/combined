/**
 * 质控记录列表的客户视图展示模型（2026-10-23 改版）。
 *
 * 只做装配：状态、进度、计数沿用 buildBatchJobPresentation；这里把结果计数归并为客户口径
 * （问题 / 需补资料 / 合格 / 不适用 / 未完成判定），与批量结果抽屉一致，不重判任何结论。
 */
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'
import { buildBatchJobPresentation } from './batchJobPresentation'

export type TaskHistoryTone = 'info' | 'success' | 'warning' | 'danger' | 'neutral'

export type TaskHistoryCounts = {
  issue: number
  dataGap: number
  compliant: number
  notApplicable: number
  pending: number
}

export type TaskHistoryRow = {
  id: string
  title: string
  statusLabel: string
  statusTone: TaskHistoryTone
  isRunning: boolean
  isCompleted: boolean
  // 已完成或部分未完成：已有结果可导出、可复核。
  canExport: boolean
  metaText: string
  dateKey: string
  timeText: string
  progressPercent: number
  progressText: string
  counts: TaskHistoryCounts
  countTotal: number
  noticeText: string
}

export type TaskHistoryGroup = { key: string; label: string; rows: TaskHistoryRow[] }

// 显示状态 → 客户口径；未列出的（技术异常、AI 判断、未执行等）归入“未完成判定”。
const COUNT_BUCKETS: Record<string, keyof TaskHistoryCounts> = {
  non_compliant: 'issue',
  ai_suggested_non_compliant: 'issue',
  data_gap: 'dataGap',
  data_quality_gap: 'dataGap',
  compliant: 'compliant',
  ai_suggested_compliant: 'compliant',
  not_applicable: 'notApplicable',
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function localDate(value?: string | null): Date | null {
  const text = String(value || '').trim()
  if (!text) return null
  const date = new Date(text)
  return Number.isNaN(date.getTime()) ? null : date
}

function dateKeyOf(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** 任务名去掉末尾的“(68条规则)”，范围另在元信息里写明。 */
export function cleanTaskTitle(name: string): string {
  const text = String(name || '')
    .replace(/\s*[（(]\s*\d+\s*条规则\s*[)）]\s*$/u, '')
    .trim()
  return text || '质控任务'
}

function resolveCounts(statusCounts: Record<string, number>): TaskHistoryCounts {
  const counts: TaskHistoryCounts = {
    issue: 0,
    dataGap: 0,
    compliant: 0,
    notApplicable: 0,
    pending: 0,
  }
  for (const [status, value] of Object.entries(statusCounts)) {
    const amount = Number(value) || 0
    if (amount <= 0) continue
    counts[COUNT_BUCKETS[status] || 'pending'] += amount
  }
  return counts
}

function resolveTone(status: string, isRunning: boolean, partialFailure: boolean): TaskHistoryTone {
  if (isRunning || status === 'queued') return 'info'
  if (partialFailure) return 'warning'
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  return 'neutral'
}

export function buildTaskHistoryRow(job: SichuanBatchJob): TaskHistoryRow {
  const base = buildBatchJobPresentation(job)
  const summary = (job.summary || {}) as Record<string, unknown>
  const status = base.normalizedStatus
  const partialFailure = status === 'failed' && summary.execution_status === 'partial_failed'
  const counts = resolveCounts(base.statusCounts)
  const countTotal = Object.values(counts).reduce((total, value) => total + value, 0)
  const created = localDate(job.created_at)
  const ruleCount = Number(job.customer_rule_count || summary.customer_rule_count || 0)
  const scopeText =
    base.scopeText.startsWith('选定') || ruleCount <= 0
      ? base.scopeText
      : `全量 ${ruleCount} 个质控点`
  const metaParts = [
    created ? `${pad(created.getHours())}:${pad(created.getMinutes())} 发起` : '',
    base.recordCount > 0 ? `${base.recordCount} 份病历` : '',
    scopeText,
  ].filter(Boolean)
  const failedRuleCount = Number(summary.failed_rule_count || 0)
  let noticeText = ''
  if (partialFailure) {
    noticeText = `${failedRuleCount || '部分'} 项质控未执行完，已完成结果可查看`
  } else if (status === 'failed' && !base.isRunning) {
    noticeText = '本次未形成可交付的结果，可查看原因后重新发起'
  } else if (status === 'canceled') {
    noticeText = '任务已取消，已返回的结果仍可查看'
  } else if (!base.isRunning && status === 'completed' && countTotal === 0) {
    noticeText = '暂无结果摘要，可打开查看'
  }
  const completed = Math.min(base.completedRecordCount, base.recordCount)
  return {
    id: job.id,
    title: cleanTaskTitle(String(job.rule_name || base.ruleSetText)),
    statusLabel: partialFailure ? '部分未完成' : base.statusLabel,
    statusTone: resolveTone(status, base.isRunning, partialFailure),
    isRunning: base.isRunning || status === 'queued',
    isCompleted: status === 'completed',
    canExport: status === 'completed' || partialFailure,
    metaText: metaParts.join(' · '),
    dateKey: created ? dateKeyOf(created) : '',
    timeText: created ? `${pad(created.getHours())}:${pad(created.getMinutes())}` : '',
    progressPercent: base.progressPercent,
    progressText:
      base.recordCount > 0
        ? `已完成 ${completed} / ${base.recordCount} 份 · ${base.progressPercent}%`
        : status === 'queued'
          ? '排队中，等待执行'
          : `进度 ${base.progressPercent}%`,
    counts,
    countTotal,
    noticeText,
  }
}

/** 按发起日期分组：今天 / 昨天 / M月D日；无日期的放最后。 */
export function groupTaskHistoryRows(rows: TaskHistoryRow[], now = new Date()): TaskHistoryGroup[] {
  const today = dateKeyOf(now)
  const yesterdayDate = new Date(now)
  yesterdayDate.setDate(now.getDate() - 1)
  const yesterday = dateKeyOf(yesterdayDate)
  const groups: TaskHistoryGroup[] = []
  for (const row of rows) {
    const key = row.dateKey || 'unknown'
    let group = groups.find((item) => item.key === key)
    if (!group) {
      const [, month, day] = key.split('-')
      const dateText = month && day ? `${Number(month)}月${Number(day)}日` : ''
      const label =
        key === today
          ? `今天 · ${dateText}`
          : key === yesterday
            ? `昨天 · ${dateText}`
            : dateText || '发起时间未知'
      group = { key, label, rows: [] }
      groups.push(group)
    }
    group.rows.push(row)
  }
  return groups
}

/** 结果比例条：只画有数量的分段，宽度按结果总数计算。 */
export function countSegments(row: TaskHistoryRow) {
  const total = Math.max(1, row.countTotal)
  return (
    [
      ['issue', 'is-danger'],
      ['dataGap', 'is-warning'],
      ['compliant', 'is-success'],
      ['notApplicable', 'is-muted'],
      ['pending', 'is-muted'],
    ] as Array<[keyof TaskHistoryCounts, string]>
  )
    .filter(([key]) => row.counts[key] > 0)
    .map(([key, className]) => ({
      key,
      className,
      width: Math.max(1, Math.round((row.counts[key] / total) * 100)),
    }))
}
