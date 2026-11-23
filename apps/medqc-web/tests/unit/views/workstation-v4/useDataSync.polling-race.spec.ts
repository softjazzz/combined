import { flushPromises } from '@vue/test-utils'
import { effectScope, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useDataSync } from '@/views/workstation-v4/composables/useDataSync'

const { api } = vi.hoisted(() => ({
  api: {
    getStatus: vi.fn(),
    getStatistics: vi.fn(),
    getRuns: vi.fn(),
    triggerSync: vi.fn(),
    getDepartments: vi.fn(),
  },
}))

const mockAuthState = reactive({
  isAuthenticated: true,
  userRoles: ['admin', 'sync_admin'] as string[],
})

vi.mock('@/api/sync', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/sync')>()
  return {
    ...actual,
    syncApi: {
      ...actual.syncApi,
      getStatus: api.getStatus,
      getStatistics: api.getStatistics,
      getRuns: api.getRuns,
      triggerSync: api.triggerSync,
      getDepartments: api.getDepartments,
    },
  }
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthState,
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useDataSync 轮询竞态与卸载/切页/登出保护', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockAuthState.isAuthenticated = true
    mockAuthState.userRoles = ['admin', 'sync_admin']
    vi.resetAllMocks()
    api.getDepartments.mockResolvedValue([])
    api.getRuns.mockResolvedValue({ items: [], total: 0 })
    api.getStatistics.mockResolvedValue({ PENDING: 0, PARTIAL: 0, SYNCED: 10, STALE: 0, FAILED: 0 })
    useDataSync().resetState()
  })

  afterEach(() => {
    useDataSync().resetState()
    vi.useRealTimers()
  })

  it('卸载/切页时 triggerSync 仍在途：响应返回后绝不拉取状态或重新排程轮询', async () => {
    const triggerDeferred = deferred<{ success: boolean; status: string }>()
    api.triggerSync.mockReturnValueOnce(triggerDeferred.promise)
    api.getStatus.mockResolvedValue({ pg_sync: { is_running: true } })

    const sync = useDataSync()
    const runPromise = sync.executeSync('pg')

    // 切页/卸载瞬间 triggerSync 仍在途
    sync.resetState()

    // 迟到的 triggerSync 返回成功
    triggerDeferred.resolve({ success: true, status: 'running' })
    await runPromise
    await flushPromises()

    await vi.advanceTimersByTimeAsync(20_000)
    await flushPromises()

    expect(api.getStatus).not.toHaveBeenCalled()
    expect(api.getStatistics).not.toHaveBeenCalled()
    expect(api.getRuns).not.toHaveBeenCalled()
    expect(sync.state.isSyncing).toBe(false)
  })

  it('卸载/切页时 triggerSync 超时返回：绝不再转入轮询', async () => {
    const triggerDeferred = deferred<never>()
    api.triggerSync.mockReturnValueOnce(triggerDeferred.promise)
    api.getStatus.mockResolvedValue({ pg_sync: { is_running: true } })

    const sync = useDataSync()
    const runPromise = sync.executeSync('pg')

    // 卸载期间请求仍在途
    sync.resetState()

    const timeoutErr = Object.assign(new Error('timeout of 60000ms exceeded'), {
      code: 'ECONNABORTED',
    })
    triggerDeferred.reject(timeoutErr)
    await expect(runPromise).rejects.toThrow('timeout')
    await flushPromises()

    await vi.advanceTimersByTimeAsync(20_000)
    await flushPromises()

    expect(api.getStatus).not.toHaveBeenCalled()
    expect(api.getStatistics).not.toHaveBeenCalled()
  })

  it('轮询请求在途时发生卸载或切页（resetState / stopPolling）：请求返回后绝不再排程下一次轮询', async () => {
    const firstPollStatus = deferred<{ pg_sync: { is_running: boolean } }>()
    api.triggerSync.mockReturnValueOnce(new Promise(() => {}))
    api.getStatus.mockReturnValueOnce(firstPollStatus.promise)

    const sync = useDataSync()
    void sync.executeSync('pg')

    // 推进 2s 触发第一次轮询，此时 getStatus 在途（pollInFlight = true）
    await vi.advanceTimersByTimeAsync(2_000)
    expect(api.getStatus).toHaveBeenCalledTimes(1)

    // 切页/卸载在请求在途瞬间发生
    sync.resetState()

    // 在途请求随后返回 is_running=true
    firstPollStatus.resolve({ pg_sync: { is_running: true } })
    await flushPromises()

    // 再推进 20s，绝不能触发任何新的轮询
    await vi.advanceTimersByTimeAsync(20_000)
    await flushPromises()

    expect(api.getStatus).toHaveBeenCalledTimes(1)
    expect(api.getRuns).not.toHaveBeenCalled()
    expect(sync.state.isSyncing).toBe(false)
  })

  it('切页仅调用 stopPolling 且轮询请求在途：请求结束后绝不再排程也不覆盖历史', async () => {
    const inFlightStatus = deferred<{ pg_sync: { is_running: boolean } }>()
    api.triggerSync.mockReturnValueOnce(new Promise(() => {}))
    api.getStatus.mockReturnValueOnce(inFlightStatus.promise)

    const sync = useDataSync()
    void sync.executeSync('pg')

    await vi.advanceTimersByTimeAsync(2_000)
    expect(api.getStatus).toHaveBeenCalledTimes(1)

    // 切到其他页签停止轮询，而请求此时尚未返回
    sync.stopPolling()

    // 在途请求返回（即使返回 is_running=true 或 false）
    inFlightStatus.resolve({ pg_sync: { is_running: true } })
    await flushPromises()

    await vi.advanceTimersByTimeAsync(20_000)
    await flushPromises()

    expect(api.getStatus).toHaveBeenCalledTimes(1)
    expect(api.getRuns).not.toHaveBeenCalled()
  })

  it('登出（isAuthenticated 变为 false）时立即停止轮询，且在途响应不再续期', async () => {
    const inFlightStatus = deferred<{ pg_sync: { is_running: boolean } }>()
    api.triggerSync.mockReturnValueOnce(new Promise(() => {}))
    api.getStatus.mockReturnValueOnce(inFlightStatus.promise)

    const scope = effectScope()
    const sync = scope.run(() => useDataSync())!
    void sync.executeSync('pg')

    await vi.advanceTimersByTimeAsync(2_000)
    expect(api.getStatus).toHaveBeenCalledTimes(1)

    // 用户登出，会话结束
    mockAuthState.isAuthenticated = false
    await flushPromises()

    // 在途状态请求随后返回
    inFlightStatus.resolve({ pg_sync: { is_running: true } })
    await flushPromises()

    await vi.advanceTimersByTimeAsync(20_000)
    await flushPromises()

    expect(api.getStatus).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('轮询遇到 401 会话失效响应时立即停止后续轮询', async () => {
    api.triggerSync.mockReturnValueOnce(new Promise(() => {}))
    api.getStatus.mockRejectedValueOnce({ response: { status: 401 } })

    const sync = useDataSync()
    void sync.executeSync('pg')

    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()
    expect(api.getStatus).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(20_000)
    await flushPromises()
    expect(api.getStatus).toHaveBeenCalledTimes(1)
  })
})
