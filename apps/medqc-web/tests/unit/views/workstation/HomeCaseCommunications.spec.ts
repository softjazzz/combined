import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, reactive } from 'vue'
import HomeCaseCommunications from '@/views/workstation/HomeCaseCommunications.vue'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  detail: vi.fn(),
  read: vi.fn(),
  query: {} as Record<string, string | string[]>,
}))
vi.mock('@/api/caseCommunications', () => ({
  getCommunicationInbox: mocks.list,
  getCommunication: mocks.detail,
  readCommunication: mocks.read,
}))
vi.mock('vue-router', () => ({ useRoute: () => route }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
const route = reactive({ query: mocks.query })
const auth = reactive({
  user: { id: 'doc', institute_id: 'H', department: '内科' },
  userRoles: ['doctor'],
})
const item = {
  id: 'event1',
  notification_id: 'n1',
  action: 'urge',
  content: '合成病历催办',
  department: '内科',
  visit_id: 'V',
  scene: 'final',
  root_job_id: 'J',
  envelope_id: 'E',
  rule_set_key: 'K',
  rule_set_version: '1',
  is_read: false,
  withdrawn: false,
  created_at: '2026-10-24T00:00:00Z',
}
const detail = () => ({ ...item, history: [item] })
const Drawer = defineComponent({
  props: { open: Boolean },
  emits: ['close'],
  template:
    '<div v-if="open"><slot/><button data-close @click="$emit(\'close\')">关闭</button></div>',
})
function make() {
  return mount(HomeCaseCommunications, {
    global: {
      stubs: {
        MqIcon: true,
        'a-drawer': Drawer,
        'router-link': { template: '<a><slot/></a>' },
        'a-button': { template: '<button><slot/></button>' },
        'a-spin': { template: '<div><slot/></div>' },
        'a-alert': { props: ['message'], template: '<p role="alert">{{message}}</p>' },
        'a-pagination': true,
        'a-descriptions': { template: '<div><slot/></div>' },
        'a-descriptions-item': { props: ['label'], template: '<div>{{label}}<slot/></div>' },
      },
    },
  })
}
beforeEach(() => {
  vi.clearAllMocks()
  route.query = {}
  auth.user.id = 'doc'
  auth.userRoles = ['doctor']
  mocks.list.mockResolvedValue({ items: [item], total: 1 })
  mocks.detail.mockResolvedValue(detail())
  mocks.read.mockResolvedValue({ ...detail(), is_read: true })
})
describe('医生病历沟通详情', () => {
  it('精确事件下钻核验详情后确认已读并显示冻结历史', async () => {
    route.query = { communication_id: 'event1' }
    const wrapper = make()
    await flushPromises()
    expect(mocks.detail).toHaveBeenCalledWith('event1')
    expect(mocks.read).toHaveBeenCalledWith('event1')
    expect(wrapper.text()).toContain('冻结结果')
    expect(wrapper.text()).toContain('操作历史')
    expect(wrapper.text()).toContain('J / E')
    expect(wrapper.text()).toContain('已读')
    wrapper.unmount()
  })
  it('详情越权失败时不发已读、不展示旧数据', async () => {
    route.query = { communication_id: 'forbidden' }
    mocks.detail.mockRejectedValueOnce(new Error('无权读取'))
    const wrapper = make()
    await flushPromises()
    expect(mocks.read).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('无权读取')
    expect(wrapper.text()).not.toContain('操作历史')
    wrapper.unmount()
  })
  it('已读写入失败保持未确认，刷新仅核对原事件', async () => {
    route.query = { communication_id: 'event1' }
    mocks.read.mockRejectedValueOnce(new Error('已读结果待核实'))
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('已读结果待核实')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '刷新核对')!
      .trigger('click')
    await flushPromises()
    expect(mocks.read).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('通知仍未读')
    wrapper.unmount()
  })
  it('数组或空的事件参数不猜测目标', async () => {
    route.query = { communication_id: ['event1', 'event2'] }
    const wrapper = make()
    await flushPromises()
    expect(mocks.detail).not.toHaveBeenCalled()
    route.query = { communication_id: '' }
    await flushPromises()
    expect(mocks.detail).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('切账号丢弃旧详情响应并重新授权', async () => {
    let resolve: ((value: ReturnType<typeof detail>) => void) | undefined
    mocks.detail.mockReturnValueOnce(
      new Promise((done) => {
        resolve = done
      }),
    )
    route.query = { communication_id: 'event1' }
    const wrapper = make()
    await flushPromises()
    auth.user.id = 'new-account'
    auth.userRoles = []
    await flushPromises()
    resolve!(detail())
    await flushPromises()
    expect(mocks.read).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('合成病历催办')
    wrapper.unmount()
  })
  it('撤回回执及原催办均在历史保留，展示精确原事件', async () => {
    route.query = { communication_id: 'withdraw1' }
    const withdrawal = {
      ...item,
      id: 'withdraw1',
      notification_id: 'n2',
      action: 'withdraw',
      related_event_id: 'event1',
      content: '撤回这一催办',
    }
    const response = { ...withdrawal, history: [withdrawal, { ...item, withdrawn: true }] }
    mocks.detail.mockResolvedValue(response)
    mocks.read.mockResolvedValue({ ...response, is_read: true })
    const wrapper = make()
    await flushPromises()
    expect(wrapper.text()).toContain('原催办：event1')
    expect(wrapper.text()).toContain('已撤回')
    wrapper.unmount()
  })
})
