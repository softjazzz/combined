import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Drawer from '../ManualDefectWorkflowDrawer.vue'

const state = vi.hoisted(() => ({
  auth: { user: { id: 'reviewer', roles: ['qc_manager'] } },
  contexts: vi.fn(),
  count: vi.fn(),
  queue: vi.fn(),
  own: vi.fn(),
  create: vi.fn(),
  decide: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => state.auth }))
vi.mock('@/api/manualDefectWorkflow', () => ({
  getEntryContexts: state.contexts,
  getManualPendingCount: state.count,
  getManualReviewQueue: state.queue,
  getOwnManualEntries: state.own,
  createManualEntry: state.create,
  decideManualDefect: state.decide,
}))
const context = {
  task_id: 'task',
  task_record_id: 'record',
  task_name: '合成任务',
  institute_id: 'I',
  patient_id: 'P',
  visit_id: 'V',
  scene: 'running',
  run_number: 1,
  job_id: 'job',
  available: true,
  reason: null,
}
const item = {
  id: 'd1',
  task_id: 'task',
  task_record_id: 'record',
  run_number: 1,
  manual_created_by: 'creator',
  rule_name: '合成人工缺陷',
  description: '合成描述',
  manual_review_status: 'pending',
  institute_id: 'I',
  patient_id: 'P',
  visit_id: 'V',
}
const make = () =>
  mount(Drawer, {
    props: { open: true },
    global: {
      stubs: {
        'a-drawer': { props: ['open'], template: '<aside v-if="open"><slot /></aside>' },
        MqIcon: true,
      },
    },
  })
beforeEach(() => {
  vi.clearAllMocks()
  state.auth = reactive({ user: { id: 'reviewer', roles: ['qc_manager'] } })
  state.contexts.mockResolvedValue({ items: [context], page: 1, has_more: false })
  state.count.mockResolvedValue(1)
  state.own.mockResolvedValue({ items: [], total: 0 })
  state.queue.mockResolvedValue({ items: [item], total: 1 })
  state.create.mockResolvedValue({})
  state.decide.mockResolvedValue({})
})
describe('V5人工缺陷处理', () => {
  it('提交成功保持处理抽屉，刷新录入、待审数并通知报表刷新', async () => {
    const wrapper = make()
    await flushPromises()
    await wrapper.get('select').setValue('all')
    await wrapper.findAll('select')[1].setValue('record')
    await flushPromises()
    await wrapper.get('input').setValue('合成问题')
    await wrapper.get('textarea').setValue('合成描述')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(state.create).toHaveBeenCalledWith(
      expect.objectContaining({ task_id: 'task', task_record_id: 'record', run_number: 1 }),
    )
    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect(wrapper.text()).toContain('人工缺陷已保存')
    expect(wrapper.find('aside').exists()).toBe(true)
    wrapper.unmount()
  })
  it('未知提交结果固定原请求ID重试，不重复生成新请求', async () => {
    state.create.mockRejectedValueOnce(new Error('网络中断'))
    const wrapper = make()
    await flushPromises()
    await wrapper.findAll('select')[1].setValue('record')
    await flushPromises()
    await wrapper.get('input').setValue('合成问题')
    await wrapper.get('textarea').setValue('合成描述')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('提交结果待核对')
    expect(wrapper.emitted('changed')).toBeUndefined()
    const firstId = state.create.mock.calls[0][0].defect_id
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(state.create.mock.calls[1][0].defect_id).toBe(firstId)
    wrapper.unmount()
  })
  it('待审通过后刷新计数和列表，驳回无原因不可提交，不能自审', async () => {
    const wrapper = make()
    await flushPromises()
    await wrapper.findAll('[role="tab"]')[1].trigger('click')
    await flushPromises()
    expect(
      wrapper
        .findAll('button')
        .find((b) => b.text() === '驳回缺陷')!
        .attributes('disabled'),
    ).toBeDefined()
    state.count.mockResolvedValue(0)
    state.queue.mockResolvedValue({ items: [], total: 0 })
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '审核通过')!
      .trigger('click')
    await flushPromises()
    expect(state.decide).toHaveBeenCalledWith('d1', 'approved', '')
    expect(wrapper.text()).toContain('待审核 0')
    expect(wrapper.text()).toContain('没有匹配的人工缺陷')
    expect(wrapper.emitted('changed')).toHaveLength(1)
    wrapper.unmount()
    state.auth.user.id = 'creator'
    state.queue.mockResolvedValue({ items: [item], total: 1 })
    const self = make()
    await flushPromises()
    await self.findAll('[role="tab"]')[1].trigger('click')
    await flushPromises()
    expect(
      self
        .findAll('button')
        .find((b) => b.text() === '审核通过')!
        .attributes('disabled'),
    ).toBeDefined()
    self.unmount()
  })
  it('旧账号迟到的待办计数不能覆盖新账号', async () => {
    let finish!: (count: number) => void
    state.count.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const wrapper = make()
    await flushPromises()
    state.auth.user.id = 'another'
    state.count.mockResolvedValue(2)
    await flushPromises()
    finish(999)
    await flushPromises()
    expect(wrapper.text()).not.toContain('999')
    expect(wrapper.text()).toContain('待审核 2')
    wrapper.unmount()
  })
  it('审核回执失败保留未知状态，不发成功事件', async () => {
    state.decide.mockRejectedValue(new Error('回执待核对'))
    const wrapper = make()
    await flushPromises()
    await wrapper.findAll('[role="tab"]')[1].trigger('click')
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '审核通过')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('待审核 未知')
    expect(wrapper.emitted('changed')).toBeUndefined()
    wrapper.unmount()
  })
})
