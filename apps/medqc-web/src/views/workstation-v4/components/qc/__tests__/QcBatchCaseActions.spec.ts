import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import QcBatchCaseActions from '../QcBatchCaseActions.vue'
import { approveBatchCase, prepareBatchCase } from '@/api/batchCaseActions'
import { CommunicationError, createCommunication } from '@/api/caseCommunications'

vi.mock('@/api/batchCaseActions', () => ({ prepareBatchCase: vi.fn(), approveBatchCase: vi.fn() }))
vi.mock('ant-design-vue', () => ({ Modal: { template: '<div><slot /></div>' } }))
vi.mock('@/api/caseCommunications', () => ({
  createCommunication: vi.fn(),
  CommunicationError: class extends Error { constructor(message: string, public status?: number) { super(message) } get unknown() { return this.status === undefined || this.status >= 500 } },
}))
const identity = { institute_id: 'I', patient_id: 'P', visit_id: 'V' }
const prepared = {
  review: { can_submit: true },
  source: { ...identity, scene: 'running', root_job_id: 'J', envelope_id: 'E' },
  doctors: [],
}
const prepareMock = vi.mocked(prepareBatchCase)
function mountControl() {
  return mount(QcBatchCaseActions, { props: { recordRefs: [identity], actorKey: 'one', carePhase: 'inpatient', allowed: true }, global: { stubs: { Modal: { template: '<div><slot /></div>' } } } })
}
beforeEach(() => {
  vi.clearAllMocks()
  prepareMock.mockResolvedValue(prepared as Awaited<ReturnType<typeof prepareBatchCase>>)
})
describe('病历批量动作', () => {
  it('确认前不写入，确认使用冻结集合和版本，无医生也允许通过', async () => {
    const wrapper = mountControl()
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()
    expect(approveBatchCase).not.toHaveBeenCalled()
    await wrapper.setProps({ recordRefs: [{ ...identity, visit_id: 'OTHER' }] })
    await wrapper.findAll('button')[2].trigger('click')
    await flushPromises()
    expect(approveBatchCase).toHaveBeenCalledWith(expect.objectContaining({ ...identity, job_id: 'J', envelope_id: 'E', scene: 'running' }))
    expect(wrapper.text()).toContain('审核通过已保存')
    expect(wrapper.emitted('completed')).toHaveLength(1)
  })
  it('准备失败逐例显示，不进入提交集合', async () => {
    prepareMock.mockRejectedValueOnce(new Error('跨机构不可访问'))
    const wrapper = mountControl()
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('跨机构不可访问')
    expect(wrapper.findAll('button')[2].attributes('disabled')).toBeDefined()
    expect(approveBatchCase).not.toHaveBeenCalled()
  })
  it('未知POST只发送一次并保留未知回执', async () => {
    vi.mocked(approveBatchCase).mockRejectedValueOnce(new CommunicationError('网络中断'))
    const wrapper = mountControl()
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()
    await wrapper.findAll('button')[2].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('结果未知，请核对')
    expect(approveBatchCase).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('button')[2].attributes('disabled')).toBeDefined()
  })
  it('账户切换后停止派发后续病例', async () => {
    let finish: (() => void) | undefined
    vi.mocked(approveBatchCase).mockImplementationOnce(() => new Promise(resolve => { finish = () => resolve({} as Awaited<ReturnType<typeof approveBatchCase>>) }))
    const wrapper = mountControl()
    await wrapper.setProps({ recordRefs: [identity, { ...identity, visit_id: 'SECOND' }] })
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()
    await wrapper.findAll('button')[2].trigger('click')
    await wrapper.setProps({ actorKey: 'two' })
    finish?.()
    await flushPromises()
    expect(approveBatchCase).toHaveBeenCalledTimes(1)
  })
  it('没有接收医生时催办失败，不提交审核或缺陷催办', async () => {
    const wrapper = mountControl()
    await wrapper.findAll('button')[1].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('没有可接收催办的医生')
    expect(createCommunication).not.toHaveBeenCalled()
    expect(approveBatchCase).not.toHaveBeenCalled()
  })
  it('催办确认后仅提交冻结病历来源和所选医生', async () => {
    prepareMock.mockResolvedValueOnce({ ...prepared, doctors: [{ id: 'D', name: '医生' }] } as Awaited<ReturnType<typeof prepareBatchCase>>)
    const wrapper = mountControl()
    await wrapper.findAll('button')[1].trigger('click')
    await flushPromises()
    expect(createCommunication).not.toHaveBeenCalled()
    await wrapper.find('select').setValue('D')
    await wrapper.findAll('button')[2].trigger('click')
    await flushPromises()
    expect(createCommunication).toHaveBeenCalledWith(expect.objectContaining({ ...prepared.source, action: 'urge', recipient_id: 'D' }))
    expect(approveBatchCase).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('病历催办已发送')
  })
})
