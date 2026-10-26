import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MessageCenter from '@/views/workstation/MessageCenter.vue'

const api = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), push: vi.fn() }))
vi.mock('@/services/apiService', () => ({
  ApiService: { get: api.get, put: api.put, isAuthenticated: () => true },
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { id: 'manager' }, userRoles: ['qc_manager'] }),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: api.push }) }))

const notice = {
  id: 'N',
  title: '医生提交了整改',
  content: '本次整改说明完整保留，不截断正文。',
  created_at: '2026-10-25T12:00:00Z',
  is_read: false,
  type: 'remediation',
  interaction_target: { kind: 'rectification', id: 'R' },
}
const stubs = {
  'a-tooltip': { template: '<span><slot /></span>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-select': { props: ['options', 'value'], template: '<select aria-label="消息类型" />' },
  'a-spin': { template: '<div><slot /></div>' },
  'a-alert': { template: '<div><slot /></div>' },
  'a-pagination': true,
}
beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue({ success: true, data: { items: [notice], total: 1, unread_count: 5 } })
  api.put.mockResolvedValue({ success: true })
})
describe('V7.1消息中心展示与操作', () => {
  it('状态切换位于页头，类型筛选归入列表，计数仍为服务端口径', async () => {
    const wrapper = mount(MessageCenter, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('header [aria-label="消息阅读状态"]').exists()).toBe(true)
    expect(wrapper.find('.message-center__list-pane [aria-label="消息类型"]').exists()).toBe(true)
    expect(wrapper.get('.message-center__total').text()).toBe('1 条')
    expect(wrapper.get('header .mq-status').text()).toBe('未读 5')
    expect(wrapper.get('.message-center__body').text()).toBe(notice.content)
    wrapper.unmount()
  })
  it('列表预览不写回执，正文精确处理仍沿原接口与目标', async () => {
    const wrapper = mount(MessageCenter, { global: { stubs } })
    await flushPromises()
    await wrapper.get('.message-center__row').trigger('click')
    expect(api.put).not.toHaveBeenCalled()
    expect(wrapper.classes()).toContain('message-center--reading')
    await wrapper.get('.message-center__back').trigger('click')
    expect(wrapper.classes()).not.toContain('message-center--reading')
    await wrapper.get('.message-center__detail-actions button').trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledWith('/api/v1/notifications/N/read')
    expect(api.push).toHaveBeenCalledWith({
      path: '/workstation-v5/feedback',
      query: { rectification_id: 'R' },
    })
    wrapper.unmount()
  })
})
