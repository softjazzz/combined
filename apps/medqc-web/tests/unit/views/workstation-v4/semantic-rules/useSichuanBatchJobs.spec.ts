import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import type {
  SichuanBatchJob,
  SichuanBatchJobDebugSnapshot,
} from '@/views/workstation-v4/semantic-rules/types'

const {
  cancelSichuanWorkspaceBatchJobMock,
  exportSichuanWorkspaceBatchJobMock,
  getSichuanWorkspaceBatchJobMock,
  getSichuanWorkspaceBatchJobDebugSnapshotMock,
  listSichuanWorkspaceBatchJobsMock,
  retrySichuanWorkspaceBatchJobMock,
  messageErrorMock,
  messageInfoMock,
  messageSuccessMock,
  notificationErrorMock,
} = vi.hoisted(() => ({
  cancelSichuanWorkspaceBatchJobMock: vi.fn(),
  exportSichuanWorkspaceBatchJobMock: vi.fn(),
  getSichuanWorkspaceBatchJobMock: vi.fn(),
  getSichuanWorkspaceBatchJobDebugSnapshotMock: vi.fn(),
  listSichuanWorkspaceBatchJobsMock: vi.fn(),
  retrySichuanWorkspaceBatchJobMock: vi.fn(),
  messageErrorMock: vi.fn(),
  messageInfoMock: vi.fn(),
  messageSuccessMock: vi.fn(),
  notificationErrorMock: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: messageSuccessMock,
    error: messageErrorMock,
    info: messageInfoMock,
    warning: vi.fn(),
  },
  notification: {
    success: vi.fn(),
    error: notificationErrorMock,
    warning: vi.fn(),
  },
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  cancelSichuanWorkspaceBatchJob: cancelSichuanWorkspaceBatchJobMock,
  exportSichuanWorkspaceBatchJob: exportSichuanWorkspaceBatchJobMock,
  getSichuanWorkspaceBatchJob: getSichuanWorkspaceBatchJobMock,
  getSichuanWorkspaceBatchJobDebugSnapshot: getSichuanWorkspaceBatchJobDebugSnapshotMock,
  listSichuanWorkspaceBatchJobs: listSichuanWorkspaceBatchJobsMock,
  retrySichuanWorkspaceBatchJob: retrySichuanWorkspaceBatchJobMock,
}))

import { useSichuanBatchJobs } from '@/views/workstation-v4/semantic-rules/composables/useSichuanBatchJobs'

describe('useSichuanBatchJobs', () => {
  const baseJob: SichuanBatchJob = {
    id: 'job-1',
    rule_code: 'SC-001',
    rule_name: '入院记录检查',
    scope: 'final',
    status: 'running',
    summary: {
      total_records: 10,
      success_count: 7,
      failed_count: 3,
      issue_records: 2,
      compliant_records: 8,
      total_tokens: 1200,
      total_processing_time: 35,
      executor_breakdown: {
        program: 4,
        llm: 6,
      },
      cache_breakdown: {
        hit: 2,
        miss: 8,
      },
      current_rule: {
        rule_job_id: 'rule-job-1',
        rule_code: 'SC-001',
        rule_name: '入院记录检查',
        progress: {
          completed: 3,
        },
      },
    },
    rule_results: [],
  }

  const debugSnapshot: SichuanBatchJobDebugSnapshot = {
    job_id: 'job-1',
    status: 'running',
    scope: 'final',
    execution_mode: 'batch',
    rule_count: 1,
    filtered_rule_count: 1,
    summary: baseJob.summary,
    current_rule: {
      rule_job_id: 'rule-job-1',
      rule_code: 'SC-001',
      rule_name: '入院记录检查',
      progress: {
        completed: 3,
        current_stage: 'llm',
      },
    },
    rules: [
      {
        rule_job_id: 'rule-job-1',
        rule_code: 'SC-001',
        rule_name: '入院记录检查',
        status: 'running',
        progress: {
          completed: 3,
        },
        debug: {
          trace_id: 'trace-1',
          cache_key: 'cache-key-1',
        },
      },
    ],
    recent_items: [],
    recent_failed_records: [],
  }

  const batchJobResponse = {
    success: true,
    data: baseJob,
  }

  const debugResponse = {
    success: true,
    data: debugSnapshot,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    getSichuanWorkspaceBatchJobMock.mockResolvedValue(batchJobResponse)
    getSichuanWorkspaceBatchJobDebugSnapshotMock.mockResolvedValue(debugResponse)
    listSichuanWorkspaceBatchJobsMock.mockResolvedValue({
      success: true,
      data: {
        items: [baseJob],
        total: 1,
        page: 1,
        page_size: 5,
      },
    })
    retrySichuanWorkspaceBatchJobMock.mockResolvedValue(batchJobResponse)
    cancelSichuanWorkspaceBatchJobMock.mockResolvedValue(batchJobResponse)
    exportSichuanWorkspaceBatchJobMock.mockResolvedValue({
      success: true,
      data: new Blob(['ok']),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetchBatchJobDetail 开启 debug 快照时应同步拉取任务详情与调试快照', async () => {
    const { fetchBatchJobDetail, batchJobDetail, batchJobDebugSnapshot } = useSichuanBatchJobs()

    const result = await fetchBatchJobDetail('job-1', { includeDebugSnapshot: true })

    expect(getSichuanWorkspaceBatchJobMock).toHaveBeenCalledWith('job-1')
    expect(getSichuanWorkspaceBatchJobDebugSnapshotMock).toHaveBeenCalledWith('job-1', {
      rule_job_id: undefined,
      item_limit: undefined,
    })
    expect(result).toEqual(baseJob)
    expect(batchJobDetail.value).toEqual(baseJob)
    expect(batchJobDebugSnapshot.value).toEqual(debugSnapshot)
  })

  it('executeRetryBatchJob 应重新入队并刷新详情与调试快照', async () => {
    const fakeTimer = {} as ReturnType<typeof window.setInterval>
    const setIntervalSpy = vi.spyOn(window, 'setInterval').mockReturnValue(fakeTimer)

    const { executeRetryBatchJob, retryingBatchJobId, batchJobDetail, batchJobDebugSnapshot } =
      useSichuanBatchJobs()

    await executeRetryBatchJob('job-1')

    expect(retrySichuanWorkspaceBatchJobMock).toHaveBeenCalledWith('job-1')
    expect(listSichuanWorkspaceBatchJobsMock).toHaveBeenCalled()
    expect(getSichuanWorkspaceBatchJobMock).toHaveBeenCalledWith('job-1')
    expect(getSichuanWorkspaceBatchJobDebugSnapshotMock).toHaveBeenCalledWith('job-1', {
      rule_job_id: undefined,
      item_limit: undefined,
    })
    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 3000)
    expect(retryingBatchJobId.value).toBe('')
    expect(batchJobDetail.value).toEqual(baseJob)
    expect(batchJobDebugSnapshot.value).toEqual(debugSnapshot)
    expect(messageSuccessMock).toHaveBeenCalledWith('批量任务已重新入队')
  })

  it('resetBatchJobs 应清理详情、调试快照并停止轮询', () => {
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => {})
    const fakeTimer = {} as ReturnType<typeof window.setInterval>
    const setIntervalSpy = vi.spyOn(window, 'setInterval').mockReturnValue(fakeTimer)

    const { batchJobDetail, batchJobDebugSnapshot, startBatchJobPolling, resetBatchJobs } =
      useSichuanBatchJobs()

    batchJobDetail.value = baseJob
    batchJobDebugSnapshot.value = debugSnapshot

    startBatchJobPolling('job-1')
    resetBatchJobs()

    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 3000)
    expect(clearIntervalSpy).toHaveBeenCalledWith(fakeTimer)
    expect(batchJobDetail.value).toBeNull()
    expect(batchJobDebugSnapshot.value).toBeNull()
  })

  it('自动补跑排队的短暂 failed 状态不停止轮询也不发送失败通知', async () => {
    const clearIntervalSpy = vi.spyOn(window, 'clearInterval').mockImplementation(() => {})
    const fakeTimer = {} as ReturnType<typeof window.setInterval>
    let pollCallback: (() => Promise<void>) | undefined
    vi.spyOn(window, 'setInterval').mockImplementation((callback) => {
      pollCallback = callback as () => Promise<void>
      return fakeTimer
    })
    const retryQueuedJob: SichuanBatchJob = {
      ...baseJob,
      status: 'failed',
      summary: {
        ...baseJob.summary!,
        execution_status: 'partial_failed',
        automatic_failed_rule_retry: { status: 'queued', should_retry: true },
      },
    }
    getSichuanWorkspaceBatchJobMock.mockResolvedValue({ success: true, data: retryQueuedJob })

    const { prependBatchJob, startBatchJobPolling } = useSichuanBatchJobs()
    prependBatchJob(baseJob)
    startBatchJobPolling('job-1')
    await pollCallback?.()

    expect(clearIntervalSpy).not.toHaveBeenCalledWith(fakeTimer)
    expect(notificationErrorMock).not.toHaveBeenCalled()
  })
})
