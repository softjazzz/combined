import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ create: vi.fn(), list: vi.fn() }))
vi.mock('@/api/tasks', () => ({
  createTaskManualDefect: api.create,
  getTaskManualDefects: api.list,
}))

import TaskManualDefectPanel from '@/components/qc/TaskManualDefectPanel.vue'

const ButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  props: { htmlType: String, disabled: Boolean },
  emits: ['click'],
  setup(props, { attrs, emit, slots }) {
    return () => h('button', {
      ...attrs,
      type: props.htmlType || 'button',
      disabled: props.disabled,
      onClick: () => emit('click'),
    }, slots.default?.())
  },
})

const InputStub = defineComponent({
  name: 'AInput',
  inheritAttrs: false,
  props: { value: String, disabled: Boolean },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('input', {
      ...attrs,
      value: props.value,
      disabled: props.disabled,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
    })
  },
})

const TextareaStub = defineComponent({
  name: 'ATextarea',
  inheritAttrs: false,
  props: { value: String, disabled: Boolean },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('textarea', {
      ...attrs,
      value: props.value,
      disabled: props.disabled,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLTextAreaElement).value),
    })
  },
})

const SelectStub = defineComponent({
  name: 'ASelect',
  props: { value: String, options: { type: Array, default: () => [] }, disabled: Boolean },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () => h('select', {
      id: 'manual-defect-severity',
      value: props.value,
      disabled: props.disabled,
      onChange: (event: Event) => emit('update:value', (event.target as HTMLSelectElement).value),
    }, (props.options as Array<{ value: string; label: string }>).map((option) =>
      h('option', { value: option.value }, option.label)))
  },
})

const props = {
  taskId: 'task-a', taskRecordId: 'association-a', runNumber: 2,
  jobId: 'job-a', userId: 'qc-a', eligible: true,
}

function page(items: Array<Record<string, unknown>> = [], total = items.length) {
  return { success: true, data: { items, total, limit: 50, offset: 0 } }
}

function defect(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id, task_id: 'task-a', task_record_id: 'association-a', run_number: 2,
    rule_name: '现病史不完整', description: '缺少关键症状', severity: 'warning',
    suggestion: null, evidence: null, manual_review_status: 'pending',
    created_at: '2026-09-25T00:00:00Z', ...overrides,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function mountPanel(overrides: Partial<typeof props> = {}) {
  return mount(TaskManualDefectPanel, {
    props: { ...props, ...overrides },
    global: { stubs: {
      'a-button': ButtonStub,
      'a-input': InputStub,
      'a-textarea': TextareaStub,
      'a-select': SelectStub,
      'a-tag': { template: '<span><slot /></span>' },
      RotateCw: true,
    } },
  })
}

async function fillRequired(wrapper: ReturnType<typeof mountPanel>) {
  await wrapper.get('#manual-defect-rule').setValue('  现病史不完整  ')
  await wrapper.get('#manual-defect-description').setValue('  缺少关键症状  ')
}

describe('TaskManualDefectPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.list.mockResolvedValue(page())
    api.create.mockResolvedValue({ success: true, data: {} })
  })

  it('仅 eligible 的任务病历展示表单，必填校验不发请求', async () => {
    const unavailable = mountPanel({ eligible: false })
    await flushPromises()
    expect(unavailable.find('[data-testid="manual-defect-submit"]').exists()).toBe(false)
    unavailable.unmount()

    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[role="alert"]').text()).toContain('请填写问题名称和问题描述')
    expect(api.create).not.toHaveBeenCalled()
  })

  it('POST 后必须通过精确 GET 找到同一编号才确认成功', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await fillRequired(wrapper)
    api.list.mockImplementationOnce(() => {
      const id = api.create.mock.calls[0][2].defect_id as string
      return Promise.resolve(page([defect(id)]))
    })
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(api.create).toHaveBeenCalledWith('task-a', 'association-a', expect.objectContaining({
      defect_id: expect.any(String), run_number: 2,
      rule_name: '现病史不完整', description: '缺少关键症状', severity: 'warning',
    }))
    expect(api.list).toHaveBeenLastCalledWith('task-a', 'association-a', 50, 0)
    expect(wrapper.get('[role="status"]').text()).toContain('已保存并确认')
    expect(wrapper.emitted('defect-created')).toHaveLength(1)
  })

  it('POST 网络结果不确定且 GET 失败时不乐观成功，重试沿用原编号', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await fillRequired(wrapper)
    api.create.mockRejectedValueOnce(new Error('timeout')).mockResolvedValueOnce({ success: true, data: {} })
    api.list.mockRejectedValueOnce(new Error('list unavailable')).mockImplementationOnce(() => {
      const id = api.create.mock.calls[0][2].defect_id as string
      return Promise.resolve(page([defect(id)]))
    })

    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.emitted('defect-created')).toBeUndefined()
    expect(wrapper.get('[role="alert"]').text()).toContain('无法确认提交状态')
    expect(wrapper.get('[data-testid="manual-defect-submit"]').text()).toContain('重试提交')

    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(api.create).toHaveBeenCalledTimes(2)
    expect(api.create.mock.calls[1][2].defect_id).toBe(api.create.mock.calls[0][2].defect_id)
    expect(wrapper.get('[role="status"]').text()).toContain('已保存并确认')
  })

  it('切换任务、病历、运行或用户后丢弃迟到提交响应', async () => {
    for (const change of [
      { taskId: 'task-b' }, { taskRecordId: 'association-b' },
      { runNumber: 3 }, { userId: 'qc-b' }, { jobId: 'job-b' },
    ]) {
      const pending = deferred<{ success: boolean; data: object }>()
      api.create.mockReset().mockReturnValue(pending.promise)
      api.list.mockReset().mockResolvedValue(page())
      const wrapper = mountPanel()
      await flushPromises()
      await fillRequired(wrapper)
      await wrapper.get('form').trigger('submit')
      expect(api.create).toHaveBeenCalledTimes(1)
      await wrapper.setProps(change)
      await flushPromises()
      pending.resolve({ success: true, data: {} })
      await flushPromises()
      expect(wrapper.find('[role="status"]').exists()).toBe(false)
      expect(wrapper.emitted('defect-created')).toBeUndefined()
      expect(wrapper.findAll('[data-testid="manual-defect-item"]')).toHaveLength(0)
      wrapper.unmount()
    }
  })

  it('拒绝混入其他任务坐标的列表，加载更多沿用精确任务病历路径和 offset', async () => {
    api.list.mockResolvedValueOnce(page([defect('own-1')], 2))
      .mockResolvedValueOnce(page([defect('own-2')], 2))
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text().includes('加载更多'))!.trigger('click')
    await flushPromises()
    expect(api.list).toHaveBeenNthCalledWith(2, 'task-a', 'association-a', 50, 1)
    expect(wrapper.findAll('[data-testid="manual-defect-item"]')).toHaveLength(2)
    wrapper.unmount()

    api.list.mockReset().mockResolvedValue(page([defect('foreign', { task_record_id: 'association-b' })]))
    const mixed = mountPanel()
    await flushPromises()
    expect(mixed.find('[data-testid="manual-defect-item"]').exists()).toBe(false)
    expect(mixed.get('[role="alert"]').text()).toContain('身份校验')
  })

  it('加载更多在途时刷新，迟到分页不得锁死后续加载或混入旧数据', async () => {
    const stalePage = deferred<ReturnType<typeof page>>()
    api.list.mockReset()
      .mockResolvedValueOnce(page([defect('old-first', { rule_name: '旧首页' })], 3))
      .mockReturnValueOnce(stalePage.promise)
      .mockResolvedValueOnce(page([defect('fresh-first', { rule_name: '新首页' })], 2))
      .mockResolvedValueOnce(page([defect('fresh-second', { rule_name: '新次页' })], 2))
    const wrapper = mountPanel()
    await flushPromises()

    const more = () => wrapper.findAll('button').find((button) => button.text().includes('加载更多'))!
    await more().trigger('click')
    expect(api.list).toHaveBeenNthCalledWith(2, 'task-a', 'association-a', 50, 1)
    await wrapper.get('[data-testid="manual-defect-refresh"]').trigger('click')
    await flushPromises()
    stalePage.resolve(page([defect('old-second', { rule_name: '旧次页' })], 3))
    await flushPromises()

    await more().trigger('click')
    await flushPromises()
    expect(api.list).toHaveBeenCalledTimes(4)
    expect(api.list).toHaveBeenNthCalledWith(4, 'task-a', 'association-a', 50, 1)
    expect(wrapper.findAll('[data-testid="manual-defect-item"] strong').map((item) => item.text()))
      .toEqual(['新首页', '新次页'])
    expect(wrapper.findAll('button').some((button) => button.text().includes('加载更多'))).toBe(false)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('同任务病历可读取上一轮人工缺陷，但不能据此确认当前轮次提交', async () => {
    api.list.mockResolvedValueOnce(page([defect('old', { run_number: 1 })]))
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-testid="manual-defect-item"]')).toHaveLength(1)

    await fillRequired(wrapper)
    api.list.mockImplementationOnce(() => {
      const id = api.create.mock.calls[0][2].defect_id as string
      return Promise.resolve(page([defect(id, { run_number: 1 })]))
    })
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.emitted('defect-created')).toBeUndefined()
    expect(wrapper.get('[role="alert"]').text()).toContain('未查到本次提交')
  })

  it('POST 等待时刷新或翻页，不得使提交按钮永久 loading', async () => {
    for (const listAction of ['refresh', 'more'] as const) {
      const pending = deferred<{ success: boolean; data: object }>()
      api.create.mockReset().mockReturnValue(pending.promise)
      api.list.mockReset().mockResolvedValue(page([defect('existing')], 2))
      const wrapper = mountPanel()
      await flushPromises()
      await fillRequired(wrapper)
      await wrapper.get('form').trigger('submit')
      expect(wrapper.get('[data-testid="manual-defect-submit"]').attributes('loading')).toBe('true')

      if (listAction === 'refresh') {
        await wrapper.get('[data-testid="manual-defect-refresh"]').trigger('click')
      } else {
        await wrapper.findAll('button').find((button) => button.text().includes('加载更多'))!.trigger('click')
      }
      await flushPromises()
      pending.resolve({ success: true, data: {} })
      await flushPromises()
      expect(wrapper.get('[data-testid="manual-defect-submit"]').attributes('loading')).toBe('false')
      wrapper.unmount()
    }
  })

  it('每条人工缺陷以标签展示审核状态，未知值显示为未知', async () => {
    api.list.mockResolvedValueOnce(page([
      defect('d-1'), defect('d-2', { manual_review_status: 'approved' }),
      defect('d-3', { manual_review_status: 'rejected' }), defect('d-4', { manual_review_status: 'weird' }),
    ]))
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.findAll('[data-testid="manual-defect-review-status"]').map((tag) => tag.text()))
      .toEqual(['待审核', '已通过', '已驳回', '未知'])
  })
})

