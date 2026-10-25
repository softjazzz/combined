import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
  push: vi.fn(),
  error: vi.fn(),
  auth: { user: { id: 'manager' }, userRoles: ['qc_manager'] },
}))
vi.mock('@/services/apiService', () => ({
  ApiService: { get: mocks.get, put: mocks.put, isAuthenticated: () => true },
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('ant-design-vue', () => ({ message: { error: mocks.error } }))

import {
  useMessageCenter,
  messageActionLabel,
  messageTypeLabel,
} from '@/views/workstation/useMessageCenter'
import {
  canUseMessageCenter,
  canUseReminderPanel,
  notificationLocation,
} from '@/views/workstation/notificationNavigation'

const notice = {
  id: 'N',
  title: '运行质控结果已就绪',
  content: '已保存',
  created_at: '2026-10-25T12:00:00Z',
  is_read: false,
  type: 'qc_result_ready',
  interaction_target: { kind: 'qc_result_ready', id: 'N' },
}
const response = (items: unknown[] = [notice], total = items.length, unread = 23) => ({
  success: true,
  data: { items, total, unread_count: unread },
})

async function setup() {
  let state!: ReturnType<typeof useMessageCenter>
  const wrapper = mount(
    defineComponent({
      setup() {
        state = useMessageCenter()
        return () => h('div')
      },
    }),
  )
  await flushPromises()
  return { state, wrapper }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.auth = reactive({ user: { id: 'manager' }, userRoles: ['qc_manager'] })
  mocks.get.mockResolvedValue(response())
  mocks.put.mockResolvedValue({ success: true })
  mocks.push.mockResolvedValue(undefined)
})

describe('主管独立消息中心', () => {
  it('只读取通知，不预加载病历池；分页和全量未读来自服务端', async () => {
    const { state, wrapper } = await setup()
    expect(state.unread.value).toBe(23)
    expect(mocks.get).toHaveBeenCalledWith('/api/v1/notifications', {
      page: 1,
      page_size: 20,
      type: undefined,
      is_read: false,
    })
    state.page.value = 2
    await state.load()
    expect(mocks.get.mock.lastCall?.[1].page).toBe(2)
    expect(mocks.get.mock.calls.every(([url]) => url === '/api/v1/notifications')).toBe(true)
    wrapper.unmount()
  })

  it('选择预览不自动已读，明确处理后先保存回执再精确下钻', async () => {
    const { state, wrapper } = await setup()
    const item = state.items.value[0]
    state.select(item)
    expect(mocks.put).not.toHaveBeenCalled()
    mocks.get.mockResolvedValue(response([], 0, 0))
    await state.open(item)
    expect(mocks.put).toHaveBeenCalledWith('/api/v1/notifications/N/read')
    expect(mocks.push).toHaveBeenCalledWith({
      path: '/workstation-v5/qc-result',
      query: { notification_id: 'N' },
    })
    expect(mocks.put.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.push.mock.invocationCallOrder[0],
    )
    expect(state.unread.value).toBe(0)
    wrapper.unmount()
  })

  it('已读保存失败保留未读，不导航、不假减计数', async () => {
    const { state, wrapper } = await setup()
    mocks.put.mockResolvedValue({ success: false })
    await state.open(state.items.value[0])
    expect(state.items.value[0].is_read).toBe(false)
    expect(state.unread.value).toBe(23)
    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.error).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('状态和类型过滤交给服务端，切换时回第一页', async () => {
    const { state, wrapper } = await setup()
    state.page.value = 3
    state.status.value = 'all'
    state.type.value = 'remediation'
    await flushPromises()
    expect(mocks.get.mock.lastCall?.[1]).toEqual({
      page: 1,
      page_size: 20,
      type: 'remediation',
      is_read: undefined,
    })
    state.status.value = 'read'
    await flushPromises()
    expect(mocks.get.mock.lastCall?.[1].is_read).toBe(true)
    wrapper.unmount()
  })

  it('标记当前最后一页后重新核对页码与计数', async () => {
    const { state, wrapper } = await setup()
    state.page.value = 2
    mocks.get.mockResolvedValue(response([], 0, 0))
    await state.markRead(state.items.value[0])
    expect(state.page.value).toBe(1)
    expect(state.total.value).toBe(0)
    expect(state.unread.value).toBe(0)
    wrapper.unmount()
  })

  it('全部已读使用原授权回执接口，不仅改当前页', async () => {
    const { state, wrapper } = await setup()
    mocks.get.mockResolvedValue(response([], 0, 0))
    await state.markAllRead()
    expect(mocks.put).toHaveBeenCalledWith('/api/v1/notifications/read-all')
    expect(state.unread.value).toBe(0)
    wrapper.unmount()
  })

  it('空页与总数矛盾时显示错误，不重复请求同一页', async () => {
    const { state, wrapper } = await setup()
    state.page.value = 2
    mocks.get.mockResolvedValue(response([], 40, 3))
    await state.load()
    expect(mocks.get).toHaveBeenCalledTimes(2)
    expect(state.error.value).toBe('消息分页信息不一致，请刷新核对')
    expect(state.loading.value).toBe(false)
    wrapper.unmount()
  })

  it('刷新失败保留上次信息并禁止对过期视图操作', async () => {
    const { state, wrapper } = await setup()
    mocks.get.mockRejectedValue(new Error('隔离验收读取失败'))
    await state.load()
    expect(state.error.value).toBe('隔离验收读取失败')
    expect(state.items.value).toHaveLength(1)
    await state.open(state.items.value[0])
    expect(mocks.put).not.toHaveBeenCalled()
    expect(mocks.push).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('迟到的上一筛选应答不能覆盖当前筛选', async () => {
    const { state, wrapper } = await setup()
    let finish!: (value: unknown) => void
    mocks.get
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finish = resolve
        }),
      )
      .mockResolvedValue(response([{ ...notice, id: 'NEW' }], 1, 4))
    const old = state.load()
    state.type.value = 'remediation'
    await flushPromises()
    finish(response([{ ...notice, id: 'OLD' }], 1, 30))
    await old
    expect(state.items.value[0].id).toBe('NEW')
    expect(state.unread.value).toBe(4)
    wrapper.unmount()
  })

  it('账号切换隔离列表与迟到回执，不把原账号消息下钻到新会话', async () => {
    const { state, wrapper } = await setup()
    let finish!: (value: unknown) => void
    mocks.put.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    const old = state.open(state.items.value[0])
    mocks.get.mockResolvedValue(response([], 0, 0))
    mocks.auth.user.id = 'another-manager'
    await flushPromises()
    finish({ success: true })
    await old
    expect(state.items.value).toEqual([])
    expect(mocks.push).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('未知身份不得制造本地消息ID或按同号就诊回退', async () => {
    mocks.get.mockResolvedValue(response([{ title: '无真实身份' }]))
    const { state, wrapper } = await setup()
    expect(state.error.value).toContain('消息身份不完整')
    expect(state.items.value).toEqual([])
    wrapper.unmount()
  })

  it('旧DRG/批量摘要仍可阅读，不编造精确处理对象或任务完成事实', async () => {
    mocks.get.mockResolvedValue(
      response([
        {
          ...notice,
          id: 'legacy',
          interaction_target: undefined,
          record_id: 'same-visit',
          type: 'frontpage_batch_summary',
        },
      ]),
    )
    const { state, wrapper } = await setup()
    const item = state.items.value[0]
    expect(messageTypeLabel(item)).toBe('批量摘要')
    expect(messageActionLabel(item)).toBe('')
    await state.open(item)
    expect(mocks.push).not.toHaveBeenCalled()
    expect(mocks.put).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('主管与普通质控员有消息入口，医生仍用原入口', () => {
    expect(canUseMessageCenter(['qc_manager'])).toBe(true)
    expect(canUseMessageCenter(['qc_staff'])).toBe(true)
    expect(canUseMessageCenter(['doctor'])).toBe(false)
  })

  it('管理员不提供浮动提醒，主管与医生保持原提醒资格', () => {
    for (const role of ['admin', 'sync_admin', 'super_admin']) {
      expect(canUseReminderPanel([role])).toBe(false)
      expect(canUseReminderPanel([role, 'doctor'])).toBe(false)
      expect(canUseMessageCenter([role])).toBe(true)
    }
    expect(canUseReminderPanel(['qc_manager'])).toBe(true)
    expect(canUseReminderPanel(['qc_staff'])).toBe(true)
    expect(canUseReminderPanel(['doctor'])).toBe(true)
  })

  it.each([
    ['rectification', '/workstation-v5/feedback', { rectification_id: 'id' }],
    ['modern_appeal', '/workstation-v5/feedback', { appeal_id: 'id' }],
    ['case_communication', '/workstation-v5/case-communications', { communication_id: 'id' }],
    [
      'account_registration',
      '/workstation-v5/system-config',
      { tab: 'accounts', registration_id: 'id' },
    ],
    ['account_registration_result', '/auth/register', { mode: 'status' }],
    ['qc_result_ready', '/workstation-v5/qc-result', { notification_id: 'id' }],
  ] as const)('%s沿用原对象授权入口', (kind, path, query) => {
    expect(notificationLocation({ kind, id: 'id' })).toEqual({ path, query })
  })
})
