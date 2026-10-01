import { flushPromises, mount } from '@vue/test-utils'
import { describe, beforeEach, it, expect, vi } from 'vitest'
import { defineComponent } from 'vue'
import CaseRectificationCreate from '@/components/qc/CaseRectificationCreate.vue'

const mocks = vi.hoisted(() => ({ candidates: vi.fn(), create: vi.fn(), success: vi.fn() }))
vi.mock('@/api/defectRectifications', () => ({
  getRectificationCandidates: mocks.candidates,
  createRectification: mocks.create,
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { id: 'q1', roles: ['qc_manager'] } }),
}))
vi.mock('ant-design-vue', () => ({ message: { success: mocks.success } }))
const Select = defineComponent({
  props: ['value', 'options'],
  emits: ['update:value'],
  template:
    '<select :value="value" @change="$emit(\'update:value\', $event.target.value)"><option value="">请选择</option><option v-for="item in options" :key="item.value" :value="item.value">{{item.label}}</option></select>',
})
const Modal = defineComponent({
  props: ['open'],
  emits: ['ok'],
  template:
    '<div v-if="open"><slot/><button data-testid="save" @click="$emit(\'ok\')">保存</button></div>',
})
const props = { instituteId: 'H1', patientId: 'P1', visitId: 'V1', jobId: 'J1' }
const target = {
  target_kind: 'canonical_defect',
  target_id: 'R1',
  scene: 'running',
  root_job_id: 'J1',
  envelope_id: 'E1',
  label: '缺陷一',
}
function make() {
  return mount(CaseRectificationCreate, {
    props,
    global: {
      stubs: {
        'a-modal': Modal,
        'a-select': Select,
        'a-spin': { template: '<div><slot/></div>' },
        'a-button': { template: '<button><slot/></button>' },
        'a-form': { template: '<div><slot/></div>' },
        'a-form-item': { template: '<div><slot/></div>' },
        'a-textarea': {
          props: ['value'],
          emits: ['update:value'],
          template:
            '<textarea :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
        },
        'a-alert': { props: ['message'], template: '<p>{{message}}</p>' },
      },
    },
  })
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.candidates.mockResolvedValue({ targets: [target], doctors: [{ id: 'd1', name: '医生一' }] })
  mocks.create.mockResolvedValue({ id: 'rect1' })
})
describe('病例缺陷整改派发', () => {
  it('真实候选冻结来源后提交，不发送展示label', async () => {
    const wrapper = make()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    await wrapper.findAll('select')[0].setValue('0')
    await wrapper.findAll('select')[1].setValue('d1')
    await wrapper.get('textarea').setValue('请补齐病历记录并提交整改说明')
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledWith({
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      target_kind: 'canonical_defect',
      target_id: 'R1',
      scene: 'running',
      root_job_id: 'J1',
      envelope_id: 'E1',
      assignee_id: 'd1',
      requirement: '请补齐病历记录并提交整改说明',
    })
    expect(mocks.success).toHaveBeenCalledOnce()
    wrapper.unmount()
  })
  it('结果不明时阻止重复写入', async () => {
    mocks.create.mockRejectedValue(new Error('写入结果待核对'))
    const wrapper = make()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    await wrapper.findAll('select')[0].setValue('0')
    await wrapper.findAll('select')[1].setValue('d1')
    await wrapper.get('textarea').setValue('请补齐病历记录并提交整改说明')
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="save"]').trigger('click')
    await flushPromises()
    expect(mocks.create).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('写入结果待核对')
    wrapper.unmount()
  })
  it('切换病例丢弃迟到候选', async () => {
    let resolve!: (value: unknown) => void
    mocks.candidates.mockReturnValue(
      new Promise((next) => {
        resolve = next
      }),
    )
    const wrapper = make()
    await wrapper.get('button').trigger('click')
    await wrapper.setProps({ visitId: 'V2' })
    resolve({ targets: [target], doctors: [{ id: 'd1', name: '医生一' }] })
    await flushPromises()
    expect(wrapper.find('select').exists()).toBe(false)
    expect(mocks.create).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
