/**
 * 质控任务进度轮询的读取失败策略。
 *
 * - 任务不存在或无权限（403/404/410）：再读也不会变，立即停止。
 * - 结果无法安全展示（409）：后端在响应头 X-Batch-Job-Status 附带任务状态。
 *   任务已结束（完成/失败/取消）说明结果不会再变，立即停止并说明原因；
 *   任务仍在执行或自动补跑中，结果可能稍后可读，继续重试。
 * - 其余临时失败（网络、超时、5xx，或旧后端未附带状态的 409）：读取异常不代表后台执行终止，
 *   继续重试；连续失败达到上限后暂停自动刷新，交由用户手动刷新。
 */
export const MAX_CONSECUTIVE_READ_FAILURES = 12

const MISSING_JOB_STATUSES = new Set([403, 404, 410])
const ACTIVE_JOB_STATUSES = new Set([
  'queued',
  'pending',
  'processing',
  'running',
  'in_progress',
  'retrying',
])

export type PollReadFailureDecision = 'retry' | 'stop_terminal' | 'stop_exhausted'
export type TerminalBatchJobStatus = 'completed' | 'failed' | 'canceled'

export function resolveTerminalBatchJobStatus(
  jobStatus?: string,
): TerminalBatchJobStatus | undefined {
  const normalized = String(jobStatus || '')
    .trim()
    .toLowerCase()
  if (normalized === 'cancelled') return 'canceled'
  if (normalized === 'completed' || normalized === 'failed' || normalized === 'canceled') {
    return normalized
  }
  return undefined
}

export function decidePollReadFailure(
  httpStatus: number | undefined,
  consecutiveFailures: number,
  jobStatus?: string,
): PollReadFailureDecision {
  if (typeof httpStatus === 'number' && MISSING_JOB_STATUSES.has(httpStatus)) return 'stop_terminal'
  const normalizedJobStatus = String(jobStatus || '')
    .trim()
    .toLowerCase()
  if (httpStatus === 409 && normalizedJobStatus && !ACTIVE_JOB_STATUSES.has(normalizedJobStatus)) {
    return 'stop_terminal'
  }
  if (consecutiveFailures >= MAX_CONSECUTIVE_READ_FAILURES) return 'stop_exhausted'
  return 'retry'
}

export function pollReadFailureMessage(
  decision: Exclude<PollReadFailureDecision, 'retry'>,
  errorMessage: string,
): string {
  if (decision === 'stop_terminal') {
    return `任务结果暂无法展示，已停止自动刷新：${errorMessage}。可在任务历史中下载诊断包或重新质控。`
  }
  return `进度连续读取失败，已暂停自动刷新：${errorMessage}。请稍后手动刷新。`
}
