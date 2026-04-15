import type { CustomRuleBatchJobStatus } from '@/types/custom-rule-workspace'

export function getBatchJobStatusText(status?: string): string {
  if (status === 'queued') return '排队中'
  if (status === 'running') return '执行中'
  if (status === 'completed') return '已完成'
  if (status === 'failed') return '已失败'
  if (status === 'canceled') return '已取消'
  return status || '未知'
}

export function getBatchJobStatusTagClass(status?: string): string {
  const normalized = String(status || '') as CustomRuleBatchJobStatus | string
  if (normalized === 'queued') return 'job-status job-status--queued'
  if (normalized === 'running') return 'job-status job-status--running'
  if (normalized === 'completed') return 'job-status job-status--completed'
  if (normalized === 'failed') return 'job-status job-status--failed'
  if (normalized === 'canceled') return 'job-status job-status--canceled'
  return 'job-status'
}
