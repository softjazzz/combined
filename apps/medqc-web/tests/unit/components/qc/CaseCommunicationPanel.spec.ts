import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import Panel from '@/components/qc/CaseCommunicationPanel.vue'
import { CommunicationError } from '@/api/caseCommunications'
const mocks = vi.hoisted(() => ({ candidates: vi.fn(), create: vi.fn() }))
const identity = reactive({ id: 'manager' })
vi.mock('@/api/caseCommunications', async (original) => ({ ...(await original<typeof import('@/api/caseCommunications')>()), getCommunicationCandidates: mocks.candidates, createCommunication: mocks.create }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ get user() { return { id: identity.id } } }) }))
const source = { institute_id: 'H', patient_id: 'P', visit_id: 'V', scene: 'running' as const, root_job_id: 'J', envelope_id: 'E' }
const candidates = { source, doctors: [{ id: 'D', name: '合成医生' }], items: [] }
const stubs = {
  'a-button': { props: ['disabled', 'htmlType'], template: '<button :disabled="disabled" :type="htmlType"><slot/></button>' },
  'a-modal': { props: ['open'], template: '<div v-if="open"><slot/></div>' },
  'a-alert': { props: ['message'], template: '<p>{{message}}</p>' },
  'a-spin': { template: '<div><slot/></div>' },
  'a-form-item': { template: '<div><slot/></div>' },
  'a-form': { emits: ['finish'], template: '<form @submit.prevent="$emit(\'finish\')"><slot/></form>' },
  'a-radio-group': { template: '<div><slot/></div>' }, 'a-radio-button': true,
  'a-select': { props: ['value', 'options'], emits: ['update:value'], template: '<select :value="value" @change="$emit(\'update:value\', $event.target.value)"><option value=""/><option v-for="item in options" :value="item.value">{{item.label}}</option></select>' },
  'a-textarea': { props: ['value'], emits: ['update:value'], template: '<textarea :value="value" @input="$emit(\'update:value\', $event.target.value)"/>' },
}
function make() { return mount(Panel, { props: { instituteId: 'H', patientId: 'P', visitId: 'V', scene: 'running', jobId: 'J' }, global: { stubs } }) }
async function ready(wrapper: ReturnType<typeof make>) { await wrapper.get('button').trigger('click'); await flushPromises(); await wrapper.get('select').setValue('D'); await wrapper.get('textarea').setValue('合成催办说明') }
beforeEach(() => { vi.clearAllMocks(); identity.id = 'manager'; mocks.candidates.mockResolvedValue(candidates); mocks.create.mockImplementation(async (data) => ({ ...data, id: 'event' })) })
describe('病例沟通', () => {
  it('冻结结果身份保存，成功仅刷新沟通历史', async () => {
    const wrapper = make(); await ready(wrapper); await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({ ...source, action: 'urge', recipient_id: 'D', content: '合成催办说明' }))
    expect(wrapper.emitted('saved')).toHaveLength(1); wrapper.unmount()
  })
  it('未知写入不能重复发送，按原请求回读确认', async () => {
    mocks.create.mockRejectedValue(new CommunicationError('连接中断'))
    const wrapper = make(); await ready(wrapper); await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('写入结果待核实'); expect(wrapper.emitted('saved')).toBeUndefined()
    await wrapper.get('form').trigger('submit'); expect(mocks.create).toHaveBeenCalledTimes(1)
    const saved = { ...mocks.create.mock.calls[0][0], id: 'event', is_read: false }
    mocks.candidates.mockResolvedValue({ ...candidates, items: [saved] })
    await wrapper.findAll('button').find(item => item.text() === '刷新核对')!.trigger('click'); await flushPromises()
    expect(wrapper.emitted('saved')).toHaveLength(1); expect(wrapper.text()).not.toContain('写入结果待核实'); wrapper.unmount()
  })
  it('畸形成功响应不宣称保存成功', async () => {
    mocks.create.mockResolvedValue({ id: 'event' })
    const wrapper = make(); await ready(wrapper); await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.emitted('saved')).toBeUndefined(); expect(wrapper.text()).toContain('待核实'); wrapper.unmount()
  })
  it('换病例丢弃迟到保存与迟到来源，不刷新新病例', async () => {
    let resolve!: (value: unknown) => void
    mocks.create.mockImplementation(() => new Promise(done => { resolve = done }))
    const wrapper = make(); await ready(wrapper); await wrapper.get('form').trigger('submit')
    const data = mocks.create.mock.calls[0][0]
    await wrapper.setProps({ patientId: 'P2', jobId: 'J2' }); resolve({ ...data, id: 'old' }); await flushPromises()
    expect(wrapper.emitted('saved')).toBeUndefined(); expect(wrapper.find('form').exists()).toBe(false); wrapper.unmount()
  })
  it('错轮来源关闭保存，撤回精确关联原催办不发起重跑', async () => {
    mocks.candidates.mockResolvedValueOnce({ ...candidates, source: { ...source, root_job_id: 'other' } })
    const wrapper = make(); await wrapper.get('button').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('来源已变化'); expect(mocks.create).not.toHaveBeenCalled()
    mocks.candidates.mockResolvedValue({ ...candidates, items: [{ ...source, id: 'urge1', action: 'urge', content: '合成旧催办', recipient_id: 'D', is_read: false, withdrawn: false }] })
    await wrapper.findAll('button').find(item => item.text() === '刷新核对')!.trigger('click'); await flushPromises()
    await wrapper.findAll('button').find(item => item.text() === '撤回催办')!.trigger('click'); await flushPromises()
    expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({ ...source, action: 'withdraw', related_event_id: 'urge1', recipient_id: 'D' })); wrapper.unmount()
  })
  it('切账号取消旧候选响应，不泄露受领人或历史', async () => {
    let resolve!: (value: unknown) => void
    mocks.candidates.mockImplementation(() => new Promise(done => { resolve = done }))
    const wrapper = make(); await wrapper.get('button').trigger('click'); identity.id = 'other'; await flushPromises()
    resolve(candidates); await flushPromises()
    expect(wrapper.find('select').exists()).toBe(false); expect(wrapper.text()).not.toContain('合成医生'); wrapper.unmount()
  })
})
