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
  if (String(job.status || '').trim().toLowerCase() !== 'failed') return false

  const summary = asRecord(job.summary)
  const retry = asRecord(summary.automatic_failed_rule_retry)
  return (
    retry.should_retry === true &&
    ACTIVE_AUTO_RETRY_STATUSES.has(String(retry.status || '').trim().toLowerCase())
  )
}
