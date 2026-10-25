import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, reactive } from 'vue'
import { Button, Form } from 'ant-design-vue'
import CaseCommunicationPanel from '@/components/qc/CaseCommunicationPanel.vue'
import { CommunicationError } from '@/api/caseCommunications'

const mocks = vi.hoisted(() => ({ candidates: vi.fn(), create: vi.fn() }))
vi.mock('@/api/caseCommunications', async () => ({
  ...(await vi.importActual<typeof import('@/api/caseCommunications')>('@/api/caseCommunications')),
  getCommunicationCandidates: mocks.candidates,
  createCommunication: mocks.create,
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
const auth = reactive({
  user: { id: 'qc', institute_id: 'H', department: '内科' },
  userRoles: ['qc_manager'],
})
const source = {
  institute_id: 'H',
  patient_id: 'P',
  visit_id: 'V',
  scene: 'running',
  root_job_id: 'J',
  envelope_id: 'E',
  rule_set_key: 'K',
  rule_set_version: '1',
}
const original = {
  ...source,
  id: 'urge1',
  action: 'urge',
  recipient_id: 'doc',
  content: '原催办',
  notification_id: 'n1',
  is_read: false,
  withdrawn: false,
  created_at: '2026-10-24T00:00:00Z',
}
const candidates = () => ({ source, doctors: [{ id: 'doc', name: '合成医生' }], items: [] })
const Modal = defineComponent({
  props: { open: Boolean, zIndex: { type: Number, default: 0 } },
  template: '<div v-if="open"><slot/></div>',
})
function make(realForm = false) {
  return mount(CaseCommunicationPanel, {
    attachTo: realForm ? document.body : undefined,
    props: { instituteId: 'H', patientId: 'P', visitId: 'V', scene: 'running', jobId: 'J' },
    global: {
      components: realForm ? { AForm: Form, AButton: Button } : {},
      stubs: {
        MqIcon: true,
        'a-modal': Modal,
        'a-spin': { template: '<div><slot/></div>' },
        'a-button': realForm
          ? false
          : {
              props: ['disabled', 'htmlType'],
              template:
                '<button :disabled="disabled" :type="htmlType || \'button\'"><slot/></button>',
            },
        'a-form': realForm
          ? false
          : {
              emits: ['finish'],
              template: '<form @submit.prevent="$emit(\'finish\')"><slot/></form>',
            },
        'a-form-item': { template: '<div><slot/></div>' },
        'a-radio-group': { template: '<div><slot/></div>' },
        'a-radio-button': true,
        'a-select': {
          props: ['value', 'options', 'disabled'],
          emits: ['update:value'],
          template:
            '<select :disabled="disabled" :value="value" @change="$emit(\'update:value\', $event.target.value)"><option value=""/><option v-for="item in options" :key="item.value" :value="item.value">{{item.label}}</option></select>',
        },
        'a-textarea': {
          props: ['value', 'disabled'],
          emits: ['update:value'],
          template:
            '<textarea :disabled="disabled" :value="value" @input="$emit(\'update:value\', $event.target.value)"/>',
        },
        'a-alert': { props: ['message'], template: '<p role="alert">{{message}}</p>' },
      },
    },
  })
}
async function openAndFill(wrapper: ReturnType<typeof make>) {
  await wrapper.get('button').trigger('click')
  await flushPromises()
  await wrapper.get('select').setValue('doc')
  await wrapper.get('textarea').setValue('请核对病历记录')
}
beforeEach(() => {
  vi.clearAllMocks()
  auth.user.id = 'qc'
  auth.userRoles = ['qc_manager']
  mocks.candidates.mockResolvedValue(candidates())
  mocks.create.mockImplementation(async (data) => ({
    ...data,
    id: 'created',
    notification_id: 'notice',
  }))
})
describe('病历沟通', () => {
  it('真实Ant Form点击发送后调用API并刷新操作历史', async () => {
    const saved = { ...original, id: 'created', content: '请核对病历记录' }
    mocks.candidates
      .mockResolvedValueOnce(candidates())
      .mockResolvedValueOnce({ ...candidates(), items: [saved] })
    const wrapper = make(true)
    try {
      await openAndFill(wrapper)
      expect(wrapper.getComponent(Form).props('model')).toEqual({
        action: 'urge',
        recipient: 'doc',
        content: '请核对病历记录',
      })
      const submit = wrapper.get('button[type="submit"]')
      expect(submit.attributes('disabled')).toBeUndefined()
      await submit.trigger('click')
      await flushPromises()
      expect(mocks.create).toHaveBeenCalledOnce()
      expect(mocks.create).toHaveBeenCalledWith(
        expect.objectContaining({ ...source, content: '请核对病历记录', recipient_id: 'doc' }),
      )
      expect(mocks.candidates).toHaveBeenCalledTimes(2)
      expect(wrapper.get('.case-communication__history').text()).toContain('请核对病历记录')
      expect(wrapper.emitted('saved')).toHaveLength(1)
    } finally {
      wrapper.unmount()
    }
  })
  it('出院页面沿用服务端返回的运行保存结果场景，不按页面分类重判', async () => {
    const wrapper = make()
    await wrapper.setProps({ scene: 'final' })
    await openAndFill(wrapper)
    expect(mocks.candidates).toHaveBeenCalledWith({
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
      root_job_id: 'J',
    })
    expect(wrapper.text()).toContain('运行病历')
    expect(wrapper.text()).not.toContain('终末病历')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ ...source, scene: 'running' }),
    )
    expect(wrapper.emitted('saved')).toHaveLength(1)
    wrapper.unmount()
  })
  it('明确收件医生并携带完整冻结规则版本发送', async () => {
    const wrapper = make()
    await openAndFill(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({
        ...source,
        action: 'urge',
        recipient_id: 'doc',
        content: '请核对病历记录',
        request_id: expect.any(String),
      }),
    )
    expect(wrapper.emitted('saved')).toHaveLength(1)
    expect(wrapper.getComponent(Modal).props('zIndex')).toBe(1200)
    wrapper.unmount()
  })
  it('来源换轮或缺规则版本时拒绝发送', async () => {
    mocks.candidates.mockResolvedValue({
      ...candidates(),
      source: { ...source, rule_set_version: '' },
    })
    const wrapper = make()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('病历来源已变化')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(mocks.create).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('撤回携带原催办id及其收件人，不影响其他催办', async () => {
    mocks.candidates.mockResolvedValue({ ...candidates(), items: [original] })
    const wrapper = make()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    const withdraw = wrapper.findAll('button').find((item) => item.text() === '撤回本次催办')
    await withdraw!.trigger('click')
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'withdraw',
        related_event_id: 'urge1',
        recipient_id: 'doc',
        ...source,
      }),
    )
    wrapper.unmount()
  })
  it('未知写入结果禁止重复发送，只有精确请求历史可解锁', async () => {
    mocks.create.mockRejectedValueOnce(new CommunicationError('连接中断', 503))
    const wrapper = make()
    await openAndFill(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('写入结果待核实')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledTimes(1)
    const payload = mocks.create.mock.calls[0][0]
    mocks.candidates.mockResolvedValue({
      ...candidates(),
      items: [{ ...payload, id: 'created', notification_id: 'notice' }],
    })
    await wrapper
      .findAll('button')
      .find((item) => item.text() === '刷新核对')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).not.toContain('写入结果尚未确认')
    expect(wrapper.emitted('saved')).toHaveLength(1)
    wrapper.unmount()
  })
  it('未知写入不能被同request_id但不同内容的历史解锁', async () => {
    mocks.create.mockRejectedValueOnce(new CommunicationError('未知结果'))
    const wrapper = make()
    await openAndFill(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const payload = mocks.create.mock.calls[0][0]
    mocks.candidates.mockResolvedValue({
      ...candidates(),
      items: [{ ...payload, id: 'created', notification_id: 'notice', content: '不同内容' }],
    })
    await wrapper
      .findAll('button')
      .find((item) => item.text() === '刷新核对')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('写入结果尚未确认')
    expect(wrapper.emitted('saved')).toBeUndefined()
    wrapper.unmount()
  })
  it('切账号后旧候选响应不再显示', async () => {
    let resolve: ((value: ReturnType<typeof candidates>) => void) | undefined
    mocks.candidates.mockReturnValueOnce(
      new Promise((done) => {
        resolve = done
      }),
    )
    const wrapper = make()
    await wrapper.get('button').trigger('click')
    auth.user.id = 'qc2'
    await flushPromises()
    resolve!(candidates())
    await flushPromises()
    expect(wrapper.getComponent(Modal).props('open')).toBe(false)
    expect(wrapper.find('select').exists()).toBe(false)
    wrapper.unmount()
  })
})
