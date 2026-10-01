import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import Home from '@/views/workstation/HomeCaseCommunications.vue'
const mocks = vi.hoisted(() => ({ inbox: vi.fn(), read: vi.fn(), detail: vi.fn() }))
const identity = reactive({ id: 'D' })
vi.mock('@/api/caseCommunications', () => ({ getCommunicationInbox: mocks.inbox, readCommunication: mocks.read, getCommunication: mocks.detail }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ get user() { return { id: identity.id } }, userRoles: ['doctor'] }) }))
const item = { id: 'event', institute_id: 'H', patient_id: 'P', visit_id: 'V', scene: 'final', root_job_id: 'J', envelope_id: 'E', action: 'opinion', department: '内科', content: '合成意见', is_read: false }
const page = { items: [item], page: 1, page_size: 20, total: 21, has_more: true }
function make() { return mount(Home, { global: { stubs: {
  'a-button': { props: ['disabled'], template: '<button :disabled="disabled"><slot/></button>' },
  'a-spin': { template: '<div><slot/></div>' }, 'a-alert': { props: ['message'], template: '<p>{{message}}</p>' },
  'a-modal': { props: ['open'], emits: ['cancel'], template: '<div v-if="open"><button class="close" @click="$emit(\'cancel\')">关闭</button><slot/></div>' },
} } }) }
beforeEach(() => { vi.clearAllMocks(); identity.id = 'D'; mocks.inbox.mockResolvedValue(page); mocks.read.mockResolvedValue({ ...item, is_read: true }); mocks.detail.mockResolvedValue({ ...item, is_read: true }) })
describe('医生站内沟通', () => {
  it('加载更多读取真实下一页并保留前页，尾页停止', async () => {
    const wrapper = make(); await flushPromises()
    mocks.inbox.mockResolvedValue({ ...page, items: [{ ...item, id: 'tail', content: '第21条' }], page: 2, has_more: false })
    await wrapper.findAll('button').find(button => button.text() === '加载更多')!.trigger('click'); await flushPromises()
    expect(mocks.inbox).toHaveBeenLastCalledWith(2); expect(wrapper.findAll('li')).toHaveLength(2)
    expect(wrapper.text()).toContain('第21条'); expect(wrapper.text()).not.toContain('加载更多'); wrapper.unmount()
  })
  it('仅权威已读响应更新，未知结果回读核实', async () => {
    mocks.read.mockRejectedValue(new Error('连接中断'))
    const wrapper = make(); await flushPromises(); await wrapper.get('li button').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('已读状态待核实'); expect(wrapper.text()).toContain('连接中断')
    await wrapper.findAll('button').find(button => button.text() === '刷新核对')!.trigger('click'); await flushPromises()
    expect(mocks.detail).toHaveBeenCalledWith('event')
    expect(wrapper.text()).toContain('已读'); expect(wrapper.text()).not.toContain('连接中断'); wrapper.unmount()
  })
  it('关闭消息后迟到已读响应不重新打开', async () => {
    let resolve!: (value: unknown) => void
    mocks.read.mockImplementation(() => new Promise(done => { resolve = done }))
    const wrapper = make(); await flushPromises(); await wrapper.get('li button').trigger('click'); await wrapper.get('.close').trigger('click')
    resolve({ ...item, is_read: true }); await flushPromises()
    expect(wrapper.find('.close').exists()).toBe(false); expect(wrapper.get('li').text()).toContain('未读'); wrapper.unmount()
  })
  it('读取故障不能显示暂无消息', async () => {
    mocks.inbox.mockRejectedValue(new Error('来源不可用'))
    const wrapper = make(); await flushPromises()
    expect(wrapper.text()).toContain('来源不可用'); expect(wrapper.text()).not.toContain('暂无病例沟通'); wrapper.unmount()
  })
  it('切账号清空已选消息并丢弃前账号迟到已读', async () => {
    let resolve!: (value: unknown) => void
    mocks.read.mockImplementation(() => new Promise(done => { resolve = done }))
    const wrapper = make(); await flushPromises(); await wrapper.get('li button').trigger('click')
    mocks.inbox.mockResolvedValue({ ...page, items: [], has_more: false }); identity.id = 'D2'; await flushPromises()
    resolve({ ...item, is_read: true }); await flushPromises()
    expect(wrapper.find('.close').exists()).toBe(false); expect(wrapper.text()).not.toContain('合成意见'); wrapper.unmount()
  })
})
