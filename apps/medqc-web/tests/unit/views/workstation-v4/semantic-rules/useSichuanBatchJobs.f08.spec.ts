import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

const {
  getBatchJobMock,
  getDebugSnapshotMock,
  listBatchJobsMock,
  messageErrorMock,
  notificationSuccessMock,
} = vi.hoisted(() => ({
  getBatchJobMock: vi.fn(),
  getDebugSnapshotMock: vi.fn(),
  listBatchJobsMock: vi.fn(),
  messageErrorMock: vi.fn(),
  notificationSuccessMock: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: messageErrorMock,
    info: vi.fn(),
    warning: vi.fn(),
  },
  notification: {
    success: notificationSuccessMock,
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  cancelSichuanWorkspaceBatchJob: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
  getSichuanWorkspaceBatchJob: getBatchJobMock,
  getSichuanWorkspaceBatchJobDebugSnapshot: getDebugSnapshotMock,
  listSichuanWorkspaceBatchJobs: listBatchJobsMock,
  retrySichuanWorkspaceBatchJob: vi.fn(),
}))

import { useSichuanBatchJobs } from '@/views/workstation-v4/semantic-rules/composables/useSichuanBatchJobs'

function job(id: string, status: SichuanBatchJob['status'] = 'running'): SichuanBatchJob {
  return {
    id,
    rule_code: `RULE-${id}`,
    rule_name: `固定任务 ${id}`,
    scope: 'final',
    status,
    summary: {
      total_records: 1,
      success_count: status === 'completed' ? 1 : 0,
      failed_count: 0,
      issue_records: 0,
      compliant_records: status === 'completed' ? 1 : 0,
      total_tokens: 0,
      total_processing_time: 0,
      progress_percent: status === 'completed' ? 100 : 40,
    },
    rule_results: [],
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

describe('useSichuanBatchJobs F08 临时读取失败恢复', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listBatchJobsMock.mockResolvedValue({
      success: true,
      data: { items: [], total: 0, page: 1, page_size: 5 },
    })
    getDebugSnapshotMock.mockResolvedValue({
      success: true,
      data: {
        job_id: 'job-a',
        status: 'running',
        scope: 'final',
        execution_mode: 'batch',
        rule_count: 1,
        filtered_rule_count: 1,
        rules: [],
        recent_items: [],
        recent_failed_records: [],
      },
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('running→503→completed：保留最近状态并在退避后恢复轮询', async () => {
    vi.useFakeTimers()
    const intervalSpy = vi.spyOn(window, 'setInterval')
    getBatchJobMock
      .mockResolvedValueOnce({ success: true, data: job('job-a') })
      .mockResolvedValueOnce({ success: false, status: 503, message: '固定503' })
      .mockResolvedValueOnce({ success: true, data: job('job-a', 'completed') })

    const { batchJobDetail, fetchBatchJobDetail, startBatchJobPolling } = useSichuanBatchJobs()
    await fetchBatchJobDetail('job-a')
    startBatchJobPolling('job-a')

    await vi.advanceTimersByTimeAsync(3000)
    expect(batchJobDetail.value?.status).toBe('running')
    expect(getBatchJobMock).toHaveBeenCalledTimes(2)
    expect(vi.getTimerCount()).toBe(1)
    expect(intervalSpy.mock.calls.map((call) => call[1])).toEqual([3000, 6000])

    await vi.advanceTimersByTimeAsync(5999)
    expect(getBatchJobMock).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(1)

    expect(getBatchJobMock).toHaveBeenCalledTimes(3)
    expect(batchJobDetail.value?.status).toBe('completed')
    expect(vi.getTimerCount()).toBe(0)
    expect(notificationSuccessMock).toHaveBeenCalledTimes(1)
  })

  it('持续临时失败按6/12/24/30秒有界退避，达到上限后停止', async () => {
    vi.useFakeTimers()
    const intervalSpy = vi.spyOn(window, 'setInterval')
    getBatchJobMock
      .mockResolvedValueOnce({ success: true, data: job('job-a') })
      .mockResolvedValue({ success: false, status: 503, message: '固定持续503' })

    const { batchJobDetail, fetchBatchJobDetail, startBatchJobPolling } = useSichuanBatchJobs()
    await fetchBatchJobDetail('job-a')
    startBatchJobPolling('job-a')

    for (let index = 0; index < 12; index += 1) {
      await vi.advanceTimersToNextTimerAsync()
    }

    const delays = intervalSpy.mock.calls.map((call) => Number(call[1]))
    expect(delays.slice(0, 5)).toEqual([3000, 6000, 12000, 24000, 30000])
    expect(Math.max(...delays)).toBe(30000)
    expect(getBatchJobMock).toHaveBeenCalledTimes(13)
    expect(batchJobDetail.value?.status).toBe('running')
    expect(vi.getTimerCount()).toBe(0)
    expect(messageErrorMock).toHaveBeenCalledTimes(1)
    expect(messageErrorMock.mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({ content: expect.stringContaining('已暂停自动刷新') }),
    )
  })

  it.each([401, 403, 404])('HTTP %s 明确失败立即停止轮询', async (status) => {
    vi.useFakeTimers()
    getBatchJobMock
      .mockResolvedValueOnce({ success: true, data: job('job-a') })
      .mockResolvedValueOnce({ success: false, status, message: `固定${status}` })

    const { batchJobDetail, fetchBatchJobDetail, startBatchJobPolling } = useSichuanBatchJobs()
    await fetchBatchJobDetail('job-a')
    startBatchJobPolling('job-a')
    await vi.advanceTimersByTimeAsync(3000)

    expect(getBatchJobMock).toHaveBeenCalledTimes(2)
    expect(batchJobDetail.value?.status).toBe('running')
    expect(vi.getTimerCount()).toBe(0)
    expect(messageErrorMock).toHaveBeenCalledTimes(1)
  })

  it('读取到任务终态后更新页面并停止轮询', async () => {
    vi.useFakeTimers()
    getBatchJobMock
      .mockResolvedValueOnce({ success: true, data: job('job-a') })
      .mockResolvedValueOnce({ success: true, data: job('job-a', 'completed') })

    const { batchJobDetail, fetchBatchJobDetail, startBatchJobPolling } = useSichuanBatchJobs()
    await fetchBatchJobDetail('job-a')
    startBatchJobPolling('job-a')
    await vi.advanceTimersByTimeAsync(3000)

    expect(batchJobDetail.value?.status).toBe('completed')
    expect(vi.getTimerCount()).toBe(0)
  })

  it('组件卸载时取消轮询，不再发起详情请求', async () => {
    vi.useFakeTimers()
    let startPolling: ((jobId: string) => void) | undefined
    const wrapper = mount(
      defineComponent({
        setup() {
          const jobs = useSichuanBatchJobs()
          startPolling = jobs.startBatchJobPolling
          return () => h('div')
        },
      }),
    )

    startPolling?.('job-a')
    expect(vi.getTimerCount()).toBe(1)
    wrapper.unmount()
    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(9000)
    expect(getBatchJobMock).not.toHaveBeenCalled()
  })

  it('切换任务后旧响应不覆盖新任务，旧finally不关闭新请求loading', async () => {
    const intervalCallbacks: Array<() => Promise<void>> = []
    vi.spyOn(window, 'setInterval').mockImplementation((callback) => {
      intervalCallbacks.push(callback as () => Promise<void>)
      return intervalCallbacks.length
    })
    vi.spyOn(window, 'clearInterval').mockImplementation(() => undefined)
    const oldResponse = deferred<{ success: true; data: SichuanBatchJob }>()
    const newResponse = deferred<{ success: true; data: SichuanBatchJob }>()
    getBatchJobMock
      .mockImplementationOnce(() => oldResponse.promise)
      .mockImplementationOnce(() => newResponse.promise)

    const {
      batchJobDetail,
      batchJobDetailLoading,
      fetchBatchJobDetail,
      startBatchJobPolling,
      stopBatchJobPolling,
    } = useSichuanBatchJobs()
    startBatchJobPolling('job-old')
    const oldPoll = intervalCallbacks[0]?.()
    const newFetch = fetchBatchJobDetail('job-new')
    startBatchJobPolling('job-new')

    oldResponse.resolve({ success: true, data: job('job-old', 'completed') })
    await oldPoll
    expect(batchJobDetail.value).toBeNull()
    expect(batchJobDetailLoading.value).toBe(true)

    newResponse.resolve({ success: true, data: job('job-new') })
    await newFetch
    expect(batchJobDetail.value?.id).toBe('job-new')
    expect(batchJobDetail.value?.status).toBe('running')
    expect(batchJobDetailLoading.value).toBe(false)
    stopBatchJobPolling()
  })

  it('轮询等待列表刷新时的新详情请求使旧轮询结果失效', async () => {
    const intervalCallbacks: Array<() => Promise<void>> = []
    vi.spyOn(window, 'setInterval').mockImplementation((callback) => {
      intervalCallbacks.push(callback as () => Promise<void>)
      return intervalCallbacks.length
    })
    vi.spyOn(window, 'clearInterval').mockImplementation(() => undefined)
    const listResponse = deferred<{
      success: true
      data: { items: SichuanBatchJob[]; total: number; page: number; page_size: number }
    }>()
    const newResponse = deferred<{ success: true; data: SichuanBatchJob }>()
    getBatchJobMock
      .mockResolvedValueOnce({ success: true, data: job('job-old') })
      .mockImplementationOnce(() => newResponse.promise)
    listBatchJobsMock.mockImplementationOnce(() => listResponse.promise)

    const {
      batchJobDetail,
      batchJobDetailLoading,
      fetchBatchJobDetail,
      startBatchJobPolling,
      stopBatchJobPolling,
    } = useSichuanBatchJobs()
    startBatchJobPolling('job-old')
    const oldPoll = intervalCallbacks[0]?.()
    await flushPromises()
    expect(listBatchJobsMock).toHaveBeenCalledTimes(1)

    const newFetch = fetchBatchJobDetail('job-new')
    listResponse.resolve({ success: true, data: { items: [], total: 0, page: 1, page_size: 5 } })
    await oldPoll
    expect(batchJobDetail.value).toBeNull()
    expect(batchJobDetailLoading.value).toBe(true)

    newResponse.resolve({ success: true, data: job('job-new') })
    await newFetch
    expect(batchJobDetail.value?.id).toBe('job-new')
    expect(batchJobDetailLoading.value).toBe(false)
    stopBatchJobPolling()
  })

  it('过期debug失败不弹错且不清除当前debug loading', async () => {
    const oldDebug = deferred<never>()
    const newDebug = deferred<{ success: true; data: Record<string, unknown> }>()
    getDebugSnapshotMock
      .mockImplementationOnce(() => oldDebug.promise)
      .mockImplementationOnce(() => newDebug.promise)
    const { batchJobDebugLoading, batchJobDebugSnapshot, fetchBatchJobDebugSnapshot } =
      useSichuanBatchJobs()

    const oldRequest = fetchBatchJobDebugSnapshot('job-old')
    const newRequest = fetchBatchJobDebugSnapshot('job-new')
    oldDebug.reject(new Error('旧请求失败'))
    await oldRequest
    expect(messageErrorMock).not.toHaveBeenCalled()
    expect(batchJobDebugLoading.value).toBe(true)

    newDebug.resolve({
      success: true,
      data: {
        job_id: 'job-new',
        status: 'running',
        scope: 'final',
        execution_mode: 'batch',
        rule_count: 1,
        filtered_rule_count: 1,
        rules: [],
        recent_items: [],
        recent_failed_records: [],
      },
    })
    await newRequest
    expect(batchJobDebugSnapshot.value?.job_id).toBe('job-new')
    expect(batchJobDebugLoading.value).toBe(false)
  })
})
