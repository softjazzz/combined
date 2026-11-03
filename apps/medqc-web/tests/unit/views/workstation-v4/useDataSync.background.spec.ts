import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDataSync } from '@/views/workstation-v4/composables/useDataSync'

const { api, warning } = vi.hoisted(() => ({
  api: {
    getPgConfig: vi.fn(), getPgSyncTables: vi.fn(), getPgSyncTableGroups: vi.fn(),
    getStatus: vi.fn(), getStatistics: vi.fn(), getSyncPolicy: vi.fn(),
    getTemplates: vi.fn(), getRuns: vi.fn(), getDepartments: vi.fn(), updatePgConfig: vi.fn(),
  },
  warning: vi.fn(),
}))
vi.mock('@/api/sync', () => ({ syncApi: api }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ userRoles: ['sync_admin'] }) }))
vi.mock('ant-design-vue', () => ({ message: { warning, error: vi.fn() } }))

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('科室列表独立后台加载', () => {
  beforeEach(() => {
    useDataSync().resetState()
    vi.resetAllMocks()
    api.getPgConfig.mockResolvedValue({})
    api.getPgSyncTables.mockResolvedValue({ items: [] })
    api.getPgSyncTableGroups.mockResolvedValue({ items: [] })
    api.getStatus.mockResolvedValue({ pg_sync: {} })
    api.getStatistics.mockResolvedValue({})
    api.getSyncPolicy.mockResolvedValue({ scope: 'running', target_departments: ['合成科室'] })
    api.getTemplates.mockResolvedValue({ items: [] })
    api.getRuns.mockResolvedValue({ items: [], total: 0 })
  })
  afterEach(() => useDataSync().resetState())

  it('源科室未返回时页面初始化和其他配置已就绪', async () => {
    const source = deferred<string[]>()
    api.getDepartments.mockReturnValue(source.promise)
    const sync = useDataSync()
    let ready = false
    const initialization = sync.initialize().then(() => { ready = true })
    await flushPromises()
    try {
      expect(ready).toBe(true)
      expect(sync.state.isInitializing).toBe(false)
      expect(sync.state.departmentsLoading).toBe(true)
      expect(sync.state.policyForm.scope).toBe('running')
      expect(api.getRuns).toHaveBeenCalledTimes(1)
    } finally {
      source.resolve(['合成科室'])
      await initialization
      await flushPromises()
    }
    expect(sync.state.availableDepartments).toEqual(['合成科室'])
  })

  it('重复读取共享当前请求，不重复连接源库', async () => {
    const source = deferred<string[]>()
    api.getDepartments.mockReturnValue(source.promise)
    const sync = useDataSync()
    const first = sync.loadDepartments()
    const second = sync.loadDepartments()
    await flushPromises()
    const calls = api.getDepartments.mock.calls.length
    source.resolve(['合成科室'])
    await Promise.all([first, second])
    expect(calls).toBe(1)
    expect(sync.state.departmentsLoading).toBe(false)
  })

  it('后台失败无弹窗，不把已选科室改成全院；手动重试可恢复', async () => {
    api.getDepartments.mockRejectedValueOnce(new Error('synthetic source timeout'))
    const sync = useDataSync()
    sync.state.policyForm.target_departments = ['原选择']
    await sync.loadDepartments()
    expect(warning).not.toHaveBeenCalled()
    expect(sync.state.departmentsError).toContain('服务器')
    expect(sync.state.policyForm.target_departments).toEqual(['原选择'])
    api.getDepartments.mockResolvedValueOnce(['已恢复科室'])
    await sync.loadDepartments()
    expect(sync.state.departmentsError).toBeNull()
    expect(sync.state.availableDepartments).toEqual(['已恢复科室'])
    expect(api.getDepartments).toHaveBeenCalledTimes(2)
  })

  it('离开后取消请求，旧响应和finally不能覆盖新页面', async () => {
    const oldSource = deferred<string[]>()
    const newSource = deferred<string[]>()
    api.getDepartments.mockReturnValueOnce(oldSource.promise).mockReturnValueOnce(newSource.promise)
    const sync = useDataSync()
    const oldRead = sync.loadDepartments()
    await flushPromises()
    const oldSignal: AbortSignal | undefined = api.getDepartments.mock.calls[0]?.[0]
    sync.resetState()
    const newRead = sync.loadDepartments()
    await flushPromises()
    oldSource.resolve(['过期科室'])
    await oldRead
    expect(oldSignal?.aborted).toBe(true)
    expect(sync.state.availableDepartments).toEqual([])
    expect(sync.state.departmentsLoading).toBe(true)
    newSource.resolve(['当前科室'])
    await newRead
    expect(sync.state.availableDepartments).toEqual(['当前科室'])
    expect(sync.state.departmentsLoading).toBe(false)
  })

  it('保存新连接不等待科室；旧连接应答不能覆盖新连接科室', async () => {
    const oldSource = deferred<string[]>()
    const newSource = deferred<string[]>()
    api.getDepartments.mockReturnValueOnce(oldSource.promise).mockReturnValueOnce(newSource.promise)
    api.updatePgConfig.mockResolvedValue({ config: { default_institute_id: 'SYNTHETIC-A' } })
    const sync = useDataSync()
    sync.state.pgConnectionForm.default_institute_id = 'SYNTHETIC-A'
    const oldRead = sync.loadDepartments()
    await flushPromises()
    await sync.savePgConnection()
    await flushPromises()
    expect(sync.state.isSavingPgConnection).toBe(false)
    expect(api.getDepartments).toHaveBeenCalledTimes(2)
    oldSource.resolve(['旧源科室'])
    await oldRead
    expect(sync.state.departmentsLoading).toBe(true)
    newSource.resolve(['新源科室'])
    await flushPromises()
    expect(sync.state.availableDepartments).toEqual(['新源科室'])
  })

  it('离开页面后完成的旧保存不再启动科室连接', async () => {
    const saved = deferred<{ config: { default_institute_id: string } }>()
    api.updatePgConfig.mockReturnValueOnce(saved.promise)
    const sync = useDataSync()
    sync.state.pgConnectionForm.default_institute_id = 'SYNTHETIC-A'
    const save = sync.savePgConnection()
    sync.resetState()
    saved.resolve({ config: { default_institute_id: 'SYNTHETIC-A' } })
    await save
    expect(api.getDepartments).not.toHaveBeenCalled()
    expect(sync.state.pgConnectionForm.default_institute_id).toBe('')
  })
})
