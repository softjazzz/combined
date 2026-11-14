import { computed, getCurrentInstance, onBeforeUnmount, reactive, ref } from 'vue'
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
import { isBatchJobPollingActive } from '@/views/workstation-v4/semantic-rules/utils/batchJobStatus'
import { retryTargetJobId } from '@/utils/batchJobRetryIdentity'
import {
  decidePollReadFailure,
  pollReadFailureMessage,
} from '@/views/workstation-v4/customer-sample-validation/batchJobPollReadPolicy'

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
const MAX_BATCH_JOB_POLL_INTERVAL_MS = 30000
const DEBUG_SNAPSHOT_POLL_EVERY_N_TICKS = 3
const HTML_EXPORT_MISMATCH_MESSAGE =
  '后端未返回 HTML 明细文件，请确认客户机后端已更新到支持 HTML 导出的版本。'

type BatchJobDetailResponse = Awaited<ReturnType<typeof getSichuanWorkspaceBatchJob>>

function errorHttpStatus(error: unknown): number | undefined {
  const status = (error as { response?: { status?: unknown } } | null)?.response?.status
  return typeof status === 'number' ? status : undefined
}

function errorJobStatus(error: unknown): string | undefined {
  const value = (error as { response?: { headers?: Record<string, unknown> } } | null)?.response
    ?.headers?.['x-batch-job-status']
  return typeof value === 'string' && value.trim() ? value.trim().toLowerCase() : undefined
}

function readFailureMessage(error: unknown): string {
  return error instanceof Error && error.message ? error.message : '获取任务详情失败'
}

function retryPollInterval(consecutiveFailures: number): number {
  return Math.min(
    MAX_BATCH_JOB_POLL_INTERVAL_MS,
    BATCH_JOB_POLL_INTERVAL_MS * 2 ** Math.max(1, consecutiveFailures),
  )
}

async function normalizeExportBlob(blob: Blob, format: 'xlsx' | 'csv' | 'html'): Promise<Blob> {
  if (format !== 'html') return blob
  const contentType = String(blob.type || '').toLowerCase()
  if (
    contentType.includes('spreadsheet') ||
    contentType.includes('officedocument') ||
    contentType.includes('zip')
  ) {
    throw new Error(HTML_EXPORT_MISMATCH_MESSAGE)
  }
  if (blob.size <= 0) {
    return new Blob([], { type: 'text/html;charset=utf-8' })
  }
  const preview = await blob.slice(0, 96).text()
  if (/^\s*PK/u.test(preview) || preview.includes('[Content_Types].xml')) {
    throw new Error(HTML_EXPORT_MISMATCH_MESSAGE)
  }
  const text = await blob.text()
  return new Blob([text.startsWith('\ufeff') ? text : `\ufeff${text}`], {
    type: 'text/html;charset=utf-8',
  })
}

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
  let batchJobPollSession = 0
  let batchJobPollInFlightSession: number | null = null
  let batchJobPollReadFailures = 0
  let batchJobPollIntervalMs = BATCH_JOB_POLL_INTERVAL_MS
  let batchJobDetailRequestSequence = 0
  let latestBatchJobDetailRequest = 0
  let batchJobDebugRequestSequence = 0
  let latestBatchJobDebugRequest = 0
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
    batchJobPollSession += 1
    if (batchJobPollTimer !== null) {
      window.clearInterval(batchJobPollTimer)
      batchJobPollTimer = null
    }
    batchJobPollTick = 0
    batchJobPollReadFailures = 0
    batchJobPollIntervalMs = BATCH_JOB_POLL_INTERVAL_MS
  }

  function scheduleBatchJobPolling(jobId: string, session: number, intervalMs: number) {
    if (session !== batchJobPollSession) return
    if (batchJobPollTimer !== null) window.clearInterval(batchJobPollTimer)
    batchJobPollIntervalMs = intervalMs
    batchJobPollTimer = window.setInterval(async () => {
      if (session !== batchJobPollSession) return
      if (batchJobPollInFlightSession === session) return
      batchJobPollInFlightSession = session
      try {
        batchJobPollTick += 1
        const shouldRefreshDebugSnapshot =
          !batchJobDebugSnapshot.value || batchJobPollTick % DEBUG_SNAPSHOT_POLL_EVERY_N_TICKS === 0
        const { response, requestId } = await requestBatchJobDetail(jobId)
        if (
          session !== batchJobPollSession ||
          requestId !== latestBatchJobDetailRequest
        ) {
          return
        }
        await loadBatchJobs()
        if (
          session !== batchJobPollSession ||
          requestId !== latestBatchJobDetailRequest
        ) {
          return
        }

        if (!response.success || !response.data) {
          batchJobPollReadFailures += 1
          const decision =
            response.status === 401
              ? 'stop_terminal'
              : decidePollReadFailure(
                  response.status,
                  batchJobPollReadFailures,
                  response.jobStatus,
                )
          if (decision === 'retry') {
            scheduleBatchJobPolling(
              jobId,
              session,
              retryPollInterval(batchJobPollReadFailures),
            )
            return
          }
          message.error({
            key: `batch-job-read-${jobId}`,
            content: pollReadFailureMessage(
              decision,
              String(response.message || '获取任务详情失败').trim(),
            ),
            duration: 8,
          })
          stopBatchJobPolling()
          return
        }

        batchJobPollReadFailures = 0
        applyBatchJobDetail(response.data)
        if (shouldRefreshDebugSnapshot) {
          await fetchBatchJobDebugSnapshot(jobId, {
            acceptResult: () => session === batchJobPollSession,
          })
        }
        if (session !== batchJobPollSession) return
        if (!isBatchJobPollingActive(response.data)) {
          stopBatchJobPolling()
        } else if (batchJobPollIntervalMs !== BATCH_JOB_POLL_INTERVAL_MS) {
          scheduleBatchJobPolling(jobId, session, BATCH_JOB_POLL_INTERVAL_MS)
        }
      } finally {
        if (batchJobPollInFlightSession === session) {
          batchJobPollInFlightSession = null
        }
      }
    }, intervalMs)
  }

  function startBatchJobPolling(jobId: string) {
    stopBatchJobPolling()
    const session = batchJobPollSession
    scheduleBatchJobPolling(jobId, session, BATCH_JOB_POLL_INTERVAL_MS)
  }

  async function requestBatchJobDetail(jobId: string): Promise<{
    response: BatchJobDetailResponse
    requestId: number
  }> {
    const requestId = ++batchJobDetailRequestSequence
    latestBatchJobDetailRequest = requestId
    batchJobDetailLoading.value = true
    try {
      const response = await getSichuanWorkspaceBatchJob(jobId)
      if (response.success && response.data?.id !== jobId) {
        throw new Error('任务详情身份不一致，已拒绝展示')
      }
      return {
        response,
        requestId,
      }
    } catch (error) {
      return {
        response: {
          success: false,
          message: readFailureMessage(error),
          status: errorHttpStatus(error),
          jobStatus: errorJobStatus(error),
        },
        requestId,
      }
    } finally {
      if (requestId === latestBatchJobDetailRequest) {
        batchJobDetailLoading.value = false
      }
    }
  }

  function applyBatchJobDetail(job: SichuanBatchJob) {
    const previousStatus = lastObservedJobStatus[job.id] || batchJobDetail.value?.status || ''
    batchJobDetail.value = job
    lastObservedJobStatus[job.id] = job.status
    maybeNotifyBatchJobTerminalStatus(job, previousStatus)
  }

  async function fetchBatchJobDebugSnapshot(
    jobId: string,
    options?: { ruleJobId?: string; itemLimit?: number; acceptResult?: () => boolean },
  ) {
    const requestId = ++batchJobDebugRequestSequence
    latestBatchJobDebugRequest = requestId
    const canAcceptResult = () =>
      requestId === latestBatchJobDebugRequest &&
      (!options?.acceptResult || options.acceptResult())
    batchJobDebugLoading.value = true
    try {
      const response = await getSichuanWorkspaceBatchJobDebugSnapshot(jobId, {
        rule_job_id: options?.ruleJobId,
        item_limit: options?.itemLimit,
      })
      if (!response.success || !response.data) {
        throw new Error(response.message || '获取任务调试快照失败')
      }
      if (response.data.job_id !== jobId) throw new Error('任务调试快照身份不一致')
      if (!canAcceptResult()) return null
      batchJobDebugSnapshot.value = response.data
      return response.data
    } catch (error: any) {
      if (canAcceptResult()) {
        message.error(error?.message || '获取任务调试快照失败')
      }
      return null
    } finally {
      if (requestId === latestBatchJobDebugRequest) {
        batchJobDebugLoading.value = false
      }
    }
  }

  async function fetchBatchJobDetail(jobId: string, options?: { includeDebugSnapshot?: boolean }) {
    const { response, requestId } = await requestBatchJobDetail(jobId)
    if (requestId !== latestBatchJobDetailRequest) return null
    if (!response.success || !response.data) {
      message.error(response.message || '获取任务详情失败')
      return null
    }
    applyBatchJobDetail(response.data)
    if (options?.includeDebugSnapshot) {
      await fetchBatchJobDebugSnapshot(jobId, {
        acceptResult: () =>
          requestId === latestBatchJobDetailRequest && batchJobDetail.value?.id === jobId,
      })
    }
    return response.data
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
    stopBatchJobPolling()
    const retrySession = batchJobPollSession
    try {
      const response = await retrySichuanWorkspaceBatchJob(jobId)
      if (retrySession !== batchJobPollSession) return
      if (!response.success || !response.data) {
        throw new Error(response.message || '重试批量任务失败')
      }
      const targetId = retryTargetJobId(jobId, response.data)
      latestBatchJobDetailRequest = ++batchJobDetailRequestSequence
      latestBatchJobDebugRequest = ++batchJobDebugRequestSequence
      batchJobDetail.value = response.data
      batchJobDebugSnapshot.value = null
      await loadBatchJobs()
      if (retrySession !== batchJobPollSession) return
      await fetchBatchJobDetail(targetId, { includeDebugSnapshot: true })
      if (retrySession !== batchJobPollSession) return
      startBatchJobPolling(targetId)
      message.success(
        targetId !== jobId ? '已创建独立重试任务，原任务与结果保留' : response.data.summary?.execution_status === 'partial_failed'
          ? '失败项已重新入队，已有有效结果将继续保留'
          : '批量任务已重新入队',
      )
    } catch (error: any) {
      message.error(error?.message || '重试批量任务失败')
    } finally {
      retryingBatchJobId.value = ''
    }
  }

  async function exportBatchJobReport(format: 'xlsx' | 'csv' | 'html' = 'html') {
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
    let blob: Blob
    try {
      blob = await normalizeExportBlob(response.data, format)
    } catch (error: any) {
      message.error(error?.message || '导出任务报告失败')
      return
    }
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
    latestBatchJobDetailRequest = ++batchJobDetailRequestSequence
    latestBatchJobDebugRequest = ++batchJobDebugRequestSequence
    batchJobDetailLoading.value = false
    batchJobDebugLoading.value = false
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
    if (isBatchJobPollingActive(job)) return
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
        ? `任务“${job.rule_name || job.rule_code}”已完成。命中问题 ${issueCount} 条，AI判断 ${uncertainCount} 条，可直接回到抽屉查看结果。`
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

  if (getCurrentInstance()) {
    onBeforeUnmount(resetBatchJobs)
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
