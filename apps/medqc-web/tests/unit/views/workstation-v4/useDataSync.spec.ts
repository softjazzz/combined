import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDataSync } from '@/views/workstation-v4/composables/useDataSync'

let mockUserRoles: string[] = []
const { mockGetSyncPolicy, mockPreflight } = vi.hoisted(() => ({
  mockGetSyncPolicy: vi.fn(),
  mockPreflight: vi.fn(),
}))

vi.mock('@/api/sync', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/sync')>()
  return {
    ...actual,
    syncApi: {
      ...actual.syncApi,
      getSyncPolicy: mockGetSyncPolicy,
      preflight: mockPreflight,
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
})
