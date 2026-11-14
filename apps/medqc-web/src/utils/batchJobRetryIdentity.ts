export interface BatchJobRetryLineage {
  source_job_id: string
  root_job_id: string
  source_attempt?: string
  attempt: number
}

/** 只有返回任务与本次重试来源一致，才允许切换详情与轮询。 */
export function retryTargetJobId(sourceId: string, job: {
  id: string
  retry_lineage?: BatchJobRetryLineage | null
}): string {
  if (!job.id?.trim()) throw new Error('重试响应缺少任务身份')
  if (job.id === sourceId && !job.retry_lineage) return sourceId // 非正式规则的旧接口兼容。
  const lineage = job.retry_lineage
  if (
    job.id === sourceId || !lineage || lineage.source_job_id !== sourceId ||
    !lineage.root_job_id?.trim() || !Number.isInteger(lineage.attempt) || lineage.attempt < 1
  ) throw new Error('重试任务关联不一致，已保留原任务视图')
  return job.id
}
