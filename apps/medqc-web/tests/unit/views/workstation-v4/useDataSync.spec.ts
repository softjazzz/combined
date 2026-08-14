import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDataSync } from '@/views/workstation-v4/composables/useDataSync'

let mockUserRoles: string[] = []
const { mockGetSyncPolicy, mockPreflight, mockUpdatePgConfig } = vi.hoisted(() => ({
  mockGetSyncPolicy: vi.fn(),
  mockPreflight: vi.fn(),
  mockUpdatePgConfig: vi.fn(),
}))

vi.mock('@/api/sync', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/sync')>()
  return {
    ...actual,
    syncApi: {
      ...actual.syncApi,
      getSyncPolicy: mockGetSyncPolicy,
      preflight: mockPreflight,
      updatePgConfig: mockUpdatePgConfig,
    },
  }
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get userRoles() {
      return mockUserRoles
    },
  }),
}))

describe('useDataSync 系统配置权限', () => {
  beforeEach(() => {
    mockUserRoles = []
    mockGetSyncPolicy.mockReset()
    mockPreflight.mockReset()
    mockUpdatePgConfig.mockReset()
    useDataSync().resetState()
  })

  it.each(['admin', 'sync_admin', 'super_admin'])('%s 可以修改同步配置', (role) => {
    mockUserRoles = [role]

    const { isReadonly } = useDataSync()

    expect(isReadonly.value).toBe(false)
  })

  it.each(['qc_manager', 'doctor'])('%s 只能读取同步配置', (role) => {
    mockUserRoles = [role]

    const { isReadonly } = useDataSync()

    expect(isReadonly.value).toBe(true)
  })

  it('在院同步预检保留 running 场景和截止日期', async () => {
    mockUserRoles = ['admin']
    mockPreflight.mockResolvedValue({
      source: 'pg',
      executable: true,
      blockers: [],
      warnings: [],
      estimated_impact: 1,
    })
    const { state, runPreflight } = useDataSync()
    state.policyForm.scope = 'running'
    state.policyForm.start_date = ''
    state.policyForm.end_date = '2026-07-31'
    state.policyForm.target_departments = ['重症医学科(ICU)']

    await runPreflight('pg')

    expect(mockPreflight).toHaveBeenCalledWith(
      expect.objectContaining({
        scene: 'running',
        date_window: { start: undefined, end: '2026-07-31' },
        target_departments: ['重症医学科(ICU)'],
      }),
    )
  })

  it('全院同步预检显式发送全院范围而不是省略科室参数', async () => {
    mockUserRoles = ['admin']
    mockPreflight.mockResolvedValue({
      source: 'pg',
      executable: true,
      blockers: [],
      warnings: [],
      estimated_impact: 42,
    })
    const { state, runPreflight } = useDataSync()
    state.policyForm.scope = 'final'
    state.policyForm.start_date = '2026-08-07'
    state.policyForm.end_date = '2026-08-13'
    state.policyForm.target_departments = ['*']

    await runPreflight('pg')

    expect(mockPreflight).toHaveBeenCalledWith(
      expect.objectContaining({
        scene: 'final',
        target_departments: ['*'],
      }),
    )
  })

  it('重新加载已保存的在院同步策略时不降级为终末病历', async () => {
    mockGetSyncPolicy.mockResolvedValue({
      scope: 'running',
      target_departments: ['*'],
      start_date: null,
      end_date: '2026-07-31',
      schedule: { mode: 'interval', minutes: 30 },
      night_window: { start: '22:00', end: '06:00' },
    })
    const { loadSyncPolicy, state } = useDataSync()

    await loadSyncPolicy()

    expect(state.policyForm.scope).toBe('running')
    expect(state.policyForm.start_date).toBe('')
    expect(state.policyForm.end_date).toBe('2026-07-31')
  })

  it('保存源库配置时持久化本院稳定机构标识', async () => {
    mockUserRoles = ['sync_admin']
    mockUpdatePgConfig.mockImplementation(async (payload) => ({
      config: payload,
      connection: { connected: true },
    }))
    const { state, savePgConnection } = useDataSync()
    state.pgConnectionForm.default_institute_id = ' HOSPITAL-A '

    await savePgConnection()

    expect(mockUpdatePgConfig).toHaveBeenCalledWith(
      expect.objectContaining({ default_institute_id: 'HOSPITAL-A' }),
    )
    expect(state.pgConnectionForm.default_institute_id).toBe('HOSPITAL-A')
  })

  it('系统占位机构号不能保存为正式同步配置', async () => {
    mockUserRoles = ['sync_admin']
    const { state, savePgConnection } = useDataSync()
    state.pgConnectionForm.default_institute_id = 'LOCAL-HOSPITAL'

    await expect(savePgConnection()).rejects.toThrow('稳定的机构标识')

    expect(mockUpdatePgConfig).not.toHaveBeenCalled()
  })
})
