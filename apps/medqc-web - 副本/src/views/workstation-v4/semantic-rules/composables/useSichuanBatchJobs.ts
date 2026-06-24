import { computed, reactive, ref } from 'vue'
import type { Dayjs } from 'dayjs'
import { message, notification } from 'ant-design-vue'
import type { WorkspaceScope } from '@/types/custom-rule-workspace'
import type {
  SichuanBatchJobDebugSnapshot,
  SichuanBatchJob,
  SichuanBatchJobQuery,
  SichuanBatchJobStatus,
} from '@/views/workstation-v4/semantic-rules/types'
import {
  cancelSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot,
  listSichuanWorkspaceBatchJobs,
  retrySichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'

type DateRangeValue = [Dayjs, Dayjs] | null

interface BatchJobQueryState {
  keyword: string
  status: SichuanBatchJobStatus | undefined
  scope: WorkspaceScope | undefined
  executor_type: 'program' | 'llm' | undefined
  cache_hit: 'hit' | 'miss' | undefined
  dateRange: DateRangeValue
}

const BATCH_JOB_POLL_INTERVAL_MS = 3000
const DEBUG_SNAPSHOT_POLL_EVERY_N_TICKS = 3

export function useSichuanBatchJobs() {
  const batchJobLoading = ref(false)
  const batchJobDetailLoading = ref(false)
  const batchJobDebugLoading = ref(false)
  const cancellingBatchJobId = ref('')
  const retryingBatchJobId = ref('')
  const batchJobs = ref<SichuanBatchJob[]>([])
  const batchJobDetail = ref<SichuanBatchJob | null>(null)
  const batchJobDebugSnapshot = ref<SichuanBatchJobDebugSnapshot | null>(null)

  const batchJobPagination = reactive({
    current: 1,
    pageSize: 5,
    total: 0,
  })

  const batchJobQuery = reactive<BatchJobQueryState>({
    keyword: '',
    status: undefined,
    scope: undefined,
    executor_type: undefined,
    cache_hit: undefined,
    dateRange: null,
  })

  const batchJobStatusOptions = [
    { label: '排队中', value: 'queued' },
    { label: '执行中', value: 'running' },
    { label: '已完成', value: 'completed' },
    { label: '已失败', value: 'failed' },
    { label: '已停止', value: 'canceled' },
  ]
  const batchJobScopeOptions: Array<{ label: string; value: WorkspaceScope }> = [
    { label: '终末病历', value: 'final' },
    { label: '运行病历', value: 'running' },
    { label: '全量病历', value: 'all' },
  ]

  const activeBatchJob = computed(() => batchJobDetail.value)

  let batchJobPollTimer: ReturnType<typeof setInterval> | number | null = null
  let batchJobPollTick = 0
  const lastObservedJobStatus = reactive<Record<string, string>>({})

  async function loadBatchJobs() {
    batchJobLoading.value = true
    try {
      const requestQuery: SichuanBatchJobQuery = {
        status: batchJobQuery.status,
        scope: batchJobQuery.scope,
        q: batchJobQuery.keyword || undefined,
        executor_type: batchJobQuery.executor_type,
        cache_hit: batchJobQuery.cache_hit,
        created_start_date: batchJobQuery.dateRange?.[0]?.format('YYYY-MM-DD'),
        created_end_date: batchJobQuery.dateRange?.[1]?.format('YYYY-MM-DD'),
        page: batchJobPagination.current,
        page_size: batchJobPagination.pageSize,
      }
      const response = await listSichuanWorkspaceBatchJobs(requestQuery)
      if (!response.success || !response.data)
        throw new Error(response.message || '获取批量任务失败')
      batchJobs.value = response.data.items
      batchJobPagination.total = response.data.total
      if (batchJobDetail.value) {
        const latest = response.data.items.find((item) => item.id === batchJobDetail.value?.id)
        if (latest) {
          batchJobDetail.value = {
            ...batchJobDetail.value,
            ...latest,
          }
        }
      }
    } catch (error: any) {
      message.error(error?.message || '获取批量任务失败')
    } finally {
      batchJobLoading.value = false
    }
  }

  function handleBatchJobTableChange(pagination: { current?: number; pageSize?: number }) {
    batchJobPagination.current = pagination.current || 1
    batchJobPagination.pageSize = pagination.pageSize || 5
    void loadBatchJobs()
  }

  function searchBatchJobs() {
    batchJobPagination.current = 1
    void loadBatchJobs()
  }

  function stopBatchJobPolling() {
    if (batchJobPollTimer !== null) {
      window.clearInterval(batchJobPollTimer)
      batchJobPollTimer = null
    }
    batchJobPollTick = 0
  }

  function startBatchJobPolling(jobId: string) {
    stopBatchJobPolling()
    batchJobPollTick = 0
    batchJobPollTimer = window.setInterval(async () => {
      batchJobPollTick += 1
      const shouldRefreshDebugSnapshot =
        !batchJobDebugSnapshot.value || batchJobPollTick % DEBUG_SNAPSHOT_POLL_EVERY_N_TICKS === 0
      const current = await fetchBatchJobDetail(jobId, {
        includeDebugSnapshot: shouldRefreshDebugSnapshot,
      })
      await loadBatchJobs()
      if (!current || !['queued', 'running'].includes(current.status)) {
        stopBatchJobPolling()
      }
    }, BATCH_JOB_POLL_INTERVAL_MS)
  }

  async function fetchBatchJobDebugSnapshot(
    jobId: string,
    options?: { ruleJobId?: string; itemLimit?: number },
  ) {
    batchJobDebugLoading.value = true
    try {
      const response = await getSichuanWorkspaceBatchJobDebugSnapshot(jobId, {
        rule_job_id: options?.ruleJobId,
        item_limit: options?.itemLimit,
      })
      if (!response.success || !response.data) {
        throw new Error(response.message || '获取任务调试快照失败')
      }
      batchJobDebugSnapshot.value = response.data
      return response.data
    } catch (error: any) {
      message.error(error?.message || '获取任务调试快照失败')
      return null
    } finally {
      batchJobDebugLoading.value = false
    }
  }

  async function fetchBatchJobDetail(jobId: string, options?: { includeDebugSnapshot?: boolean }) {
    batchJobDetailLoading.value = true
    try {
      const response = await getSichuanWorkspaceBatchJob(jobId)
      if (!response.success || !response.data)
        throw new Error(response.message || '获取任务详情失败')
      const previousStatus = lastObservedJobStatus[jobId] || batchJobDetail.value?.status || ''
      batchJobDetail.value = response.data
      lastObservedJobStatus[jobId] = response.data.status
      maybeNotifyBatchJobTerminalStatus(response.data, previousStatus)
      if (options?.includeDebugSnapshot) {
        await fetchBatchJobDebugSnapshot(jobId)
      }
      return response.data
    } catch (error: any) {
      message.error(error?.message || '获取任务详情失败')
      return null
    } finally {
      batchJobDetailLoading.value = false
    }
  }

  async function executeCancelBatchJob(jobId: string) {
    if (!jobId || cancellingBatchJobId.value) return
    cancellingBatchJobId.value = jobId
    try {
      const response = await cancelSichuanWorkspaceBatchJob(jobId)
      if (!response.success || !response.data) {
        throw new Error(response.message || '停止批量任务失败')
      }
      if (batchJobDetail.value?.id === response.data.id) {
        batchJobDetail.value = response.data
      }
      await loadBatchJobs()
      await fetchBatchJobDetail(jobId)
      stopBatchJobPolling()
      message.success('批量任务已停止')
    } catch (error: any) {
      message.error(error?.message || '停止批量任务失败')
    } finally {
      cancellingBatchJobId.value = ''
    }
  }

  async function executeRetryBatchJob(jobId: string) {
    if (!jobId || retryingBatchJobId.value) return
    retryingBatchJobId.value = jobId
    try {
      const response = await retrySichuanWorkspaceBatchJob(jobId)
      if (!response.success || !response.data) {
        throw new Error(response.message || '重试批量任务失败')
      }
      if (batchJobDetail.value?.id === response.data.id) {
        batchJobDetail.value = response.data
      }
      await loadBatchJobs()
      await fetchBatchJobDetail(jobId, { includeDebugSnapshot: true })
      startBatchJobPolling(jobId)
      message.success('批量任务已重新入队')
    } catch (error: any) {
      message.error(error?.message || '重试批量任务失败')
    } finally {
      retryingBatchJobId.value = ''
    }
  }

  async function exportBatchJobReport(format: 'xlsx' | 'csv' = 'xlsx') {
    if (!activeBatchJob.value) {
      message.info('请先选择一个批量任务')
      return
    }
    const response = await exportSichuanWorkspaceBatchJob({
      job_id: activeBatchJob.value.id,
      format,
    })
    if (!response.success || !response.data) {
      message.error(response.message || '导出任务报告失败')
      return
    }
    const blob = response.data
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `sichuan-rules-${activeBatchJob.value.id}.${format}`
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    window.URL.revokeObjectURL(url)
    message.success('任务报告已开始下载')
  }

  function resetBatchJobs() {
    batchJobPagination.current = 1
    batchJobDetail.value = null
    batchJobDebugSnapshot.value = null
    stopBatchJobPolling()
  }

  function prependBatchJob(job: SichuanBatchJob) {
    batchJobPagination.current = 1
    lastObservedJobStatus[job.id] = job.status
    const nextItems = [job, ...batchJobs.value.filter((item) => item.id !== job.id)]
    batchJobs.value = nextItems.slice(0, batchJobPagination.pageSize)
    batchJobPagination.total += 1
  }

  function maybeNotifyBatchJobTerminalStatus(job: SichuanBatchJob, previousStatus?: string) {
    const currentStatus = String(job.status || '')
      .trim()
      .toLowerCase()
    const previous = String(previousStatus || '')
      .trim()
      .toLowerCase()
    if (!['completed', 'failed', 'canceled'].includes(currentStatus)) return
    if (!['queued', 'running'].includes(previous)) return
    const issueCount = Number(job.summary?.issue_records ?? job.issue_records ?? 0)
    const uncertainCount = Number(job.summary?.uncertain_records ?? 0)
    const title =
      currentStatus === 'completed'
        ? '批量质控已完成'
        : currentStatus === 'failed'
          ? '批量质控执行失败'
          : '批量质控已取消'
    const description =
      currentStatus === 'completed'
        ? `任务“${job.rule_name || job.rule_code}”已完成。命中问题 ${issueCount} 条，待复核 ${uncertainCount} 条，可直接回到抽屉查看结果。`
        : currentStatus === 'failed'
          ? `任务“${job.rule_name || job.rule_code}”执行失败。请回到抽屉查看失败原因并决定是否重试。`
          : `任务“${job.rule_name || job.rule_code}”已被停止，不会继续产生新的结果。`
    const notify =
      currentStatus === 'completed'
        ? notification.success
        : currentStatus === 'failed'
          ? notification.error
          : notification.warning
    notify({
      key: `sichuan-batch-job-${job.id}-${currentStatus}`,
      message: title,
      description,
      duration: currentStatus === 'completed' ? 5.5 : 7,
      placement: 'topRight',
    })
  }

  return {
    batchJobLoading,
    batchJobDetailLoading,
    batchJobDebugLoading,
    cancellingBatchJobId,
    retryingBatchJobId,
    batchJobs,
    batchJobDetail,
    batchJobDebugSnapshot,
    activeBatchJob,
    batchJobPagination,
    batchJobQuery,
    batchJobStatusOptions,
    batchJobScopeOptions,
    loadBatchJobs,
    handleBatchJobTableChange,
    searchBatchJobs,
    stopBatchJobPolling,
    startBatchJobPolling,
    fetchBatchJobDetail,
    fetchBatchJobDebugSnapshot,
    executeCancelBatchJob,
    executeRetryBatchJob,
    exportBatchJobReport,
    resetBatchJobs,
    prependBatchJob,
  }
}
