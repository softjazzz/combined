const CANCELABLE_BATCH_JOB_STATUSES = new Set([
  'queued',
  'pending',
  'processing',
  'running',
  'in_progress',
])

const ACTIVE_AUTO_RETRY_STATUSES = new Set(['queued', 'running'])

type BatchJobPollingState = {
  status?: string | null
  summary?: unknown
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

export function isBatchJobCancelable(status?: string | null): boolean {
  return CANCELABLE_BATCH_JOB_STATUSES.has(
    String(status || '')
      .trim()
      .toLowerCase(),
  )
}

export function isBatchJobPollingActive(job?: BatchJobPollingState | null): boolean {
  if (!job) return false
  if (isBatchJobCancelable(job.status)) return true
  if (
    String(job.status || '')
      .trim()
      .toLowerCase() !== 'failed'
  )
    return false

  const summary = asRecord(job.summary)
  const retry = asRecord(summary.automatic_failed_rule_retry)
  return (
    retry.should_retry === true &&
    ACTIVE_AUTO_RETRY_STATUSES.has(
      String(retry.status || '')
        .trim()
        .toLowerCase(),
    )
  )
}

export function isBatchJobFinished(job?: BatchJobPollingState | null): boolean {
  return (
    ['completed', 'failed', 'canceled', 'cancelled'].includes(
      String(job?.status || '')
        .trim()
        .toLowerCase(),
    ) && !isBatchJobPollingActive(job)
  )
}

/** 只转述后台自动补跑计划，不从失败原因或规则编号推断重试策略。 */
export function getBatchJobRetryMessage(job?: BatchJobPollingState | null): string {
  if (
    String(job?.status || '')
      .trim()
      .toLowerCase() !== 'failed'
  )
    return ''
  const retry = asRecord(asRecord(job?.summary).automatic_failed_rule_retry)
  const status = String(retry.status || '')
    .trim()
    .toLowerCase()
  if (isBatchJobPollingActive(job)) {
    return status === 'queued'
      ? '失败项已排队等待自动补跑，已保存的结果不会被覆盖。'
      : '系统正在自动补跑失败项，已保存的结果不会被覆盖。'
  }
  if (status === 'planned') {
    return '失败项补跑计划尚未进入执行队列，任务仍为失败状态；已保存的结果不会被覆盖，请查看失败原因。'
  }
  if (status === 'enqueue_failed') {
    return '失败项自动补跑未能进入执行队列，任务仍为失败状态；已保存的结果不会被覆盖，请查看失败原因。'
  }
  if (status === 'interrupted') {
    return '自动补跑已中断，已保存结果保留；任务仍为失败状态，请查看失败原因。'
  }
  if (status === 'exhausted') return '自动补跑次数已用尽，剩余失败项尚未恢复，请查看失败原因。'
  if (status === 'not_retryable') return '后台判定本次失败不适合自动补跑，请查看失败原因。'
  if (status === 'completed') return '自动补跑已结束，任务仍有失败项，请查看失败原因。'
  return '后台未确认自动补跑计划，请查看失败原因。'
}
