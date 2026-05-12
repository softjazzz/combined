const CANCELABLE_BATCH_JOB_STATUSES = new Set([
  'queued',
  'pending',
  'processing',
  'running',
  'in_progress',
])

export function isBatchJobCancelable(status?: string | null): boolean {
  return CANCELABLE_BATCH_JOB_STATUSES.has(
    String(status || '')
      .trim()
      .toLowerCase(),
  )
}
