/**
 * 质控记录列表的客户视图展示模型（2026-10-23 改版）。
 *
 * 只做装配：状态与进度沿用 buildBatchJobPresentation。列表走后端概览接口（view=overview），
 * 不读取、也不展示任何结果计数或结论；结果在“查看结果”抽屉里看。
 */
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'
import { buildBatchJobPresentation } from './batchJobPresentation'

export type TaskHistoryTone = 'info' | 'success' | 'warning' | 'danger' | 'neutral'

export type TaskHistoryRow = {
  id: string
  title: string
  statusLabel: string
  statusTone: TaskHistoryTone
  isRunning: boolean
  isCompleted: boolean
  // 已完成或未全部完成但已有结果：可导出、可复核。
  canExport: boolean
  metaText: string
  dateKey: string
  timeText: string
  progressPercent: number
  progressText: string
  // 非执行中任务的一句话说明：完成时间与用时，或失败、取消的提示。
  detailText: string
  detailTone: 'muted' | 'warning'
}

export type TaskHistoryGroup = { key: string; label: string; rows: TaskHistoryRow[] }

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

function clockText(date: Date) {
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** 用时：不足 1 分钟按秒，不足 1 小时按“分 秒”，否则按“小时 分”。 */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  if (total < 60) return `${total} 秒`
  if (total < 3600) {
    const rest = total % 60
    return rest ? `${Math.floor(total / 60)} 分 ${rest} 秒` : `${total / 60} 分钟`
  }
  const minutes = Math.floor((total % 3600) / 60)
  return minutes ? `${Math.floor(total / 3600)} 小时 ${minutes} 分` : `${total / 3600} 小时`
}

/** 任务名去掉末尾的“(68条规则)”，范围另在元信息里写明。 */
export function cleanTaskTitle(name: string): string {
  const text = String(name || '')
    .replace(/\s*[（(]\s*\d+\s*条规则\s*[)）]\s*$/u, '')
    .trim()
  return text || '质控任务'
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
  // 概览接口只告知“失败任务是否已有结果”；完整详情接口仍可给出 partial_failed。
  const partialFailure =
    status === 'failed' &&
    !base.isRunning &&
    (summary.execution_status === 'partial_failed' || job.has_results === true)
  const created = localDate(job.created_at)
  const finished = localDate(job.finished_at)
  const started = localDate(job.started_at) || created
  const ruleCount = Number(job.customer_rule_count || summary.customer_rule_count || 0)
  const scopeText =
    base.scopeText.startsWith('选定') || ruleCount <= 0
      ? base.scopeText
      : `全量 ${ruleCount} 个质控点`
  const metaParts = [
    created ? `${clockText(created)} 发起` : '',
    base.recordCount > 0 ? `${base.recordCount} 份病历` : '',
    scopeText,
  ].filter(Boolean)

  let detailText = ''
  let detailTone: TaskHistoryRow['detailTone'] = 'muted'
  if (status === 'failed' && !base.isRunning) {
    detailText = '未全部完成，可打开查看原因和已有结果'
    detailTone = 'warning'
  } else if (status === 'canceled') {
    detailText = '任务已取消，已返回的结果仍可查看'
  } else if (status === 'completed') {
    const seconds =
      finished && started ? (finished.getTime() - started.getTime()) / 1000 : Number.NaN
    detailText = [
      finished ? `${clockText(finished)} 完成` : '已完成',
      Number.isFinite(seconds) && seconds >= 0 ? `用时 ${formatDuration(seconds)}` : '',
    ]
      .filter(Boolean)
      .join(' · ')
  }

  const completed = Math.min(base.completedRecordCount, base.recordCount)
  return {
    id: job.id,
    title: cleanTaskTitle(String(job.rule_name || base.ruleSetText)),
    statusLabel: status === 'failed' && !base.isRunning ? '未全部完成' : base.statusLabel,
    statusTone: resolveTone(status, base.isRunning, status === 'failed'),
    isRunning: base.isRunning || status === 'queued',
    isCompleted: status === 'completed',
    canExport: status === 'completed' || partialFailure,
    metaText: metaParts.join(' · '),
    dateKey: created ? dateKeyOf(created) : '',
    timeText: created ? clockText(created) : '',
    progressPercent: base.progressPercent,
    progressText:
      base.recordCount > 0
        ? `已完成 ${completed} / ${base.recordCount} 份 · ${base.progressPercent}%`
        : status === 'queued'
          ? '排队中，等待执行'
          : `进度 ${base.progressPercent}%`,
    detailText,
    detailTone,
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
