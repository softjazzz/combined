import type {
  SichuanBatchIssueItem,
  SichuanBatchJob,
} from '@/views/workstation-v4/semantic-rules/types'
import { isBatchJobCancelable } from '@/views/workstation-v4/semantic-rules/utils/batchJobStatus'

export type BatchJobStatusChip = {
  key: string
  label: string
  value: number
  className: string
}

export type BatchJobLiveResult = {
  key: string
  ruleId: string
  statusLabel: string
  className: string
  text: string
}

export type BatchJobExecutionPhase = {
  label: string
  text: string
}

export type BatchJobPresentation = {
  normalizedStatus: string
  statusLabel: string
  statusClass: string
  statusTitle: string
  isRunning: boolean
  phaseText: string
  ruleSetText: string
  scopeText: string
  compactRuleIdsText: string
  recordCount: number
  completedRecordCount: number
  recordText: string
  recordProgressText: string
  resultCount: number
  expectedResultCount: number
  resultCountText: string
  resultProgressText: string
  progressPercent: number
  statusCounts: Record<string, number>
  statusChips: BatchJobStatusChip[]
  liveResultLines: BatchJobLiveResult[]
  liveExecutionPhase: BatchJobExecutionPhase | null
  overviewText: string
  issueSummaryText: string
  createdText: string
  updatedText: string
}

const STATUS_META: Array<{
  key: string
  label: string
  className: string
  attention: boolean
}> = [
  { key: 'technical_error', label: '技术异常', className: 'is-danger', attention: true },
  { key: 'non_compliant', label: '不合规', className: 'is-danger', attention: true },
  {
    key: 'ai_suggested_non_compliant',
    label: 'AI建议复核',
    className: 'is-review',
    attention: true,
  },
  { key: 'data_gap', label: '数据不足', className: 'is-warning', attention: true },
  { key: 'uncertain', label: 'AI判断', className: 'is-review', attention: true },
  { key: 'not_executed', label: '未执行', className: 'is-muted', attention: true },
  {
    key: 'ai_suggested_compliant',
    label: 'AI未见问题',
    className: 'is-success',
    attention: false,
  },
  { key: 'compliant', label: '合规', className: 'is-success', attention: false },
  { key: 'not_applicable', label: '不适用', className: 'is-muted', attention: false },
]

const ATTENTION_STATUSES = new Set(
  STATUS_META.filter((item) => item.attention).map((item) => item.key),
)

const STATUS_META_BY_KEY = new Map(STATUS_META.map((item) => [item.key, item]))

const EXECUTOR_LABELS: Record<string, string> = {
  surgery_presence: '手术记录',
  basic_timeliness: '病历时效',
  exam_lab: '检查检验',
  consultation_quality: '会诊记录',
  transfusion: '输血相关',
  tumor_pathology: '肿瘤与病理',
  course_quality: '病程质量',
  surgery_gate: '手术适用性',
  surgery_document: '手术文书',
  surgery_mdt: '术前讨论',
  extended_document: '扩展病历文书',
}

const BRIEF_BY_RULE_ID: Record<string, string> = {
  'LX0609-001': '入院记录未在24小时内完成',
  'LX0609-002': '首次病程记录时间超过8小时',
  'LX0609-003': '手术记录未在术后24小时内完成',
  'LX0609-005': '入院48小时内无主治医师首次查房记录',
  'LX0609-007': '病情稳定患者3天内无查房病程记录',
  'LX0609-008': '病重患者2天内无查房病程记录',
  'LX0609-009': '病危患者未每天记录查房病程',
  'LX0609-016': '首次病程与入院记录存在复制风险',
  'LX0609-017': '多次病程记录高度重复',
  'LX0609-018': '主诉不能导出第一诊断',
  'LX0609-020': '会诊后未记录会诊意见执行情况',
  'LX0609-021': '会诊申请目的不明确',
  'LX0609-022': '会诊意见不明确',
  'LX0609-023': '会诊执行记录不规范',
  'LX0609-041': '缺少输血知情同意书',
  'LX0609-049': '输血医嘱与收费不一致',
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function numeric(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function normalizeStatusCounts(value: unknown): Record<string, number> {
  const counts: Record<string, number> = {}
  if (Array.isArray(value)) {
    value.forEach((item) => {
      const record = asRecord(item)
      const key = String(record.key || record.status || '').trim()
      const count = numeric(record.count ?? record.value)
      if (key && count > 0) counts[key] = count
    })
    return counts
  }
  Object.entries(asRecord(value)).forEach(([key, value]) => {
    const count = numeric(value)
    if (count > 0) counts[key] = count
  })
  return counts
}

function resolveStatusCounts(job: SichuanBatchJob): Record<string, number> {
  const summary = asRecord(job.summary)
  const postprocessSummary = asRecord(summary.postprocess_summary)
  const resultAggregation = asRecord(summary.result_aggregation)
  const candidates = [
    summary.display_status_counts,
    summary.status_breakdown,
    postprocessSummary.display_status_counts,
    resultAggregation.status_breakdown,
  ]
  for (const candidate of candidates) {
    const counts = normalizeStatusCounts(candidate)
    if (Object.keys(counts).length) return counts
  }
  return {}
}

function normalizeRuleIds(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item).trim()).filter((item) => /^LX0609-\d+/u.test(item))
    : []
}

function selectedRuleIds(job: SichuanBatchJob): string[] {
  const filters = asRecord(job.filters)
  const fromFilters = normalizeRuleIds(
    filters.scoped_customer_rule_ids || filters.selected_rule_ids || filters.rule_ids,
  )
  if (fromFilters.length) return fromFilters
  return normalizeRuleIds(job.draft_ids || job.draft_id)
}

function resolveRecordCount(job: SichuanBatchJob): number {
  const summary = asRecord(job.summary)
  const filters = asRecord(job.filters)
  const selectedRecordIds = Array.isArray(filters.selected_record_ids)
    ? filters.selected_record_ids
    : []
  return numeric(
    summary.total_records ||
      filters.dedup_record_count ||
      job.total_records ||
      job.record_ids?.length ||
      selectedRecordIds.length,
  )
}

function resolveCompletedRecordCount(job: SichuanBatchJob): number {
  const summary = asRecord(job.summary)
  return numeric(summary.success_count || summary.completed_records || job.success_count)
}

function resolveCustomerRuleCount(job: SichuanBatchJob, ruleIds: string[]): number {
  const summary = asRecord(job.summary)
  return numeric(job.customer_rule_count || summary.customer_rule_count || ruleIds.length)
}

function resolveIssueStatus(item: SichuanBatchIssueItem): string {
  return String(item.canonical_status || item.display_status || item.status || '')
    .trim()
    .toLowerCase()
}

function resolveLiveResultText(item: SichuanBatchIssueItem, ruleId: string): string {
  return String(
    item.conclusion ||
      item.findings ||
      item.rule_name ||
      BRIEF_BY_RULE_ID[ruleId] ||
      '已回写质控结果',
  ).trim()
}

function resolveLiveResultLines(job: SichuanBatchJob): BatchJobLiveResult[] {
  const items = Array.isArray(job.items) ? job.items : []
  const lines = items
    .slice(-6)
    .reverse()
    .map((item, index) => {
      const ruleId = String(item.qc_point_id || item.rule_code || item.rule_id || '').trim()
      const status = resolveIssueStatus(item)
      const statusMeta = STATUS_META_BY_KEY.get(status)
      const text = resolveLiveResultText(item, ruleId)
      if (!text) return null
      return {
        key: `${ruleId || 'result'}|${status || 'unknown'}|${text}|${index}`,
        ruleId: ruleId || '质控结果',
        statusLabel: statusMeta?.label || '结果已回写',
        className: statusMeta?.className || 'is-muted',
        text,
      }
    })
    .filter((item): item is BatchJobLiveResult => Boolean(item))
  return lines
}

function resolveLiveExecutionPhase(job: SichuanBatchJob): BatchJobExecutionPhase | null {
  const summary = asRecord(job.summary)
  const streamState = asRecord(summary.stream_state)
  if (String(streamState.kind || '').trim() !== 'native_executor_phase') return null
  const executorKey = String(streamState.executor_key || '').trim()
  const executorLabel = EXECUTOR_LABELS[executorKey] || '质控规则组'
  const event = String(streamState.event || '').trim().toLowerCase()
  const completedBatches = numeric(streamState.completed_batches)
  const totalBatches = numeric(streamState.total_batches)
  const countText = totalBatches > 0 ? `（${completedBatches} / ${totalBatches}）` : ''
  if (event === 'started') {
    return { label: '执行动态', text: `正在核对${executorLabel}${countText}` }
  }
  if (event === 'completed') {
    return { label: '执行动态', text: `${executorLabel}已完成${countText}，正在继续下一规则组` }
  }
  if (event === 'failed') {
    return { label: '执行动态', text: `${executorLabel}未完成，正在安全处理本次任务` }
  }
  return null
}

function resolveIssueSummaryText(job: SichuanBatchJob): string {
  const summary = asRecord(job.summary)
  const compactSummaries = Array.isArray(summary.history_issue_summaries)
    ? summary.history_issue_summaries
    : []
  const compactLines = compactSummaries
    .slice(0, 4)
    .map((item) => {
      const record = asRecord(item)
      const ruleId = String(record.rule_id || '').trim()
      const text = String(record.text || BRIEF_BY_RULE_ID[ruleId] || '').trim()
      return ruleId && text ? `${ruleId} ${text}` : text
    })
    .filter(Boolean)
  if (compactLines.length) return `问题点：${compactLines.join('；')}`

  const itemLines = (job.items || [])
    .filter((item) => ATTENTION_STATUSES.has(resolveIssueStatus(item)))
    .slice(0, 4)
    .map((item) => {
      const ruleId = String(item.qc_point_id || item.rule_code || item.rule_id || '').trim()
      const text = String(item.findings || item.rule_name || BRIEF_BY_RULE_ID[ruleId] || '').trim()
      return ruleId && text ? `${ruleId} ${text}` : text
    })
    .filter(Boolean)
  return itemLines.length ? `问题点：${itemLines.join('；')}` : ''
}

export function getBatchJobStatusText(status?: string | null): string {
  const normalized = String(status || '')
    .trim()
    .toLowerCase()
  if (normalized === 'completed') return '已完成'
  if (normalized === 'running') return '执行中'
  if (normalized === 'queued') return '排队中'
  if (normalized === 'failed') return '执行失败'
  if (normalized === 'canceled') return '已取消'
  return '状态待返回'
}

export function getBatchJobStatusClass(status?: string | null): string {
  const normalized = String(status || '')
    .trim()
    .toLowerCase()
  if (normalized === 'completed') return 'is-success'
  if (normalized === 'failed') return 'is-danger'
  if (normalized === 'running' || normalized === 'queued') return 'is-running'
  return 'is-muted'
}

export function formatBatchJobDateTime(value?: string | Date | null): string {
  if (!value) return '未返回时间'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (number: number) => String(number).padStart(2, '0')
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function buildBatchJobPresentation(job: SichuanBatchJob): BatchJobPresentation {
  const summary = asRecord(job.summary)
  const progress = asRecord(job.progress)
  const normalizedStatus = String(job.status || '')
    .trim()
    .toLowerCase()
  const isRunning = isBatchJobCancelable(job.status)
  const ruleIds = selectedRuleIds(job)
  const customerRuleCount = resolveCustomerRuleCount(job, ruleIds)
  const recordCount = resolveRecordCount(job)
  const completedRecordCount = resolveCompletedRecordCount(job)
  const statusCounts = resolveStatusCounts(job)
  const statusChips = STATUS_META.map(({ key, label, className }) => ({
    key,
    label,
    className,
    value: numeric(statusCounts[key]),
  })).filter((item) => item.value > 0)
  const resultCountFromStatuses = Object.values(statusCounts).reduce(
    (total, value) => total + numeric(value),
    0,
  )
  const resultCount =
    resultCountFromStatuses > 0
      ? resultCountFromStatuses
      : numeric(summary.total_results || job.items?.length)
  const expectedResultCount =
    recordCount > 0 && customerRuleCount > 0 ? recordCount * customerRuleCount : 0
  const directProgress = numeric(summary.progress_percent || progress.progress_percent)
  const streamRuleIndex = numeric(progress.rule_index)
  const streamRuleCount = numeric(progress.rule_count)
  const progressPercent =
    directProgress > 0
      ? Math.min(100, Math.max(0, Math.round(directProgress)))
      : recordCount > 0 && completedRecordCount > 0
        ? Math.min(100, Math.round((completedRecordCount / recordCount) * 100))
        : streamRuleCount > 0 && streamRuleIndex > 0
          ? Math.min(100, Math.round((streamRuleIndex / streamRuleCount) * 100))
        : expectedResultCount > 0 && resultCount > 0
          ? Math.min(100, Math.round((resultCount / expectedResultCount) * 100))
          : 0

  const statusLabel = getBatchJobStatusText(job.status)
  const statusClass = getBatchJobStatusClass(job.status)
  const ruleSetText = String(
    job.rule_set_name || summary.rule_set_name || job.rule_name || '质控任务',
  )
  const scopeText = ruleIds.length
    ? `选定 ${ruleIds.length} 个质控点`
    : customerRuleCount > 0
      ? `全量规则 · ${customerRuleCount} 个客户质控点`
      : '质控范围未返回'
  const compactRuleIdsText = ruleIds.length
    ? `${customerRuleCount || ruleIds.length} 个 LX0609 质控点：${ruleIds.slice(0, 3).join('、')}${ruleIds.length > 3 ? ` +${ruleIds.length - 3}` : ''}`
    : customerRuleCount > 0
      ? `${customerRuleCount} 个客户质控点`
      : '未返回质控点范围'
  const recordText = recordCount > 0 ? `${recordCount} 份病历` : '病历数未返回'
  const recordProgressText =
    recordCount > 0
      ? `病历进度：已完成 ${Math.min(completedRecordCount, recordCount)} / ${recordCount} 份`
      : '病历进度：未返回'
  const resultCountText = resultCount > 0 ? `${resultCount} 条结果` : '结果数待返回'
  const resultProgressText =
    isRunning && resultCount <= 0
      ? '结果回写：等待结果'
      : expectedResultCount > 0
        ? `结果回写：${resultCount} / ${expectedResultCount} 条`
        : resultCount > 0
          ? `结果回写：已返回 ${resultCount} 条`
          : '结果回写：等待结果'

  let phaseText = '任务状态待返回。'
  if (normalizedStatus === 'queued') phaseText = '等待后台领取任务，请勿重复发起。'
  else if (normalizedStatus === 'failed') phaseText = job.error_message || '本次任务执行失败。'
  else if (normalizedStatus === 'canceled') phaseText = '本次任务已取消，已返回结果仍可查看。'
  else if (normalizedStatus === 'completed') phaseText = '任务已完成，可查看结果或导出明细。'
  else if (normalizedStatus === 'running' && resultCount > 0) {
    phaseText = `规则执行中，已返回 ${resultCount} 条结果。`
  } else if (normalizedStatus === 'running' && progressPercent > 0) {
    phaseText = `规则执行中，当前进度 ${progressPercent}%。`
  } else if (normalizedStatus === 'running') phaseText = '病历准备完成，正在执行规则。'

  const attentionChips = statusChips.filter((chip) => ATTENTION_STATUSES.has(chip.key))
  let overviewText = '暂无结果摘要'
  if (normalizedStatus === 'failed') overviewText = job.error_message || '任务失败'
  else if (isRunning) {
    overviewText =
      progressPercent > 0 ? `任务执行中，已完成 ${progressPercent}%` : '任务执行中，等待结果回写'
  } else if (attentionChips.length) {
    overviewText = `发现需关注结果：${attentionChips.map((chip) => `${chip.label} ${chip.value}`).join('，')}`
  } else {
    const compliantSummary = statusChips.filter((chip) =>
      ['compliant', 'ai_suggested_compliant', 'not_applicable'].includes(chip.key),
    )
    if (compliantSummary.length) {
      overviewText = compliantSummary.map((chip) => `${chip.label} ${chip.value}`).join('，')
    }
  }

  return {
    normalizedStatus,
    statusLabel,
    statusClass,
    statusTitle: isRunning ? '正在执行质控' : '最近质控任务',
    isRunning,
    phaseText,
    ruleSetText,
    scopeText,
    compactRuleIdsText,
    recordCount,
    completedRecordCount,
    recordText,
    recordProgressText,
    resultCount,
    expectedResultCount,
    resultCountText,
    resultProgressText,
    progressPercent,
    statusCounts,
    statusChips,
    liveResultLines: resolveLiveResultLines(job),
    liveExecutionPhase: resolveLiveExecutionPhase(job),
    overviewText,
    issueSummaryText: resolveIssueSummaryText(job),
    createdText: formatBatchJobDateTime(job.created_at),
    updatedText: formatBatchJobDateTime(job.updated_at || job.finished_at || job.created_at),
  }
}
