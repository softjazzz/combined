import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn(), submit: vi.fn() }))
vi.mock('@/api/recordReviews', () => ({
  getTaskRecordReview: api.get,
  submitTaskRecordReview: api.submit,
}))

import TaskRecordReviewPanel from '@/components/qc/TaskRecordReviewPanel.vue'

const ButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  props: { disabled: Boolean },
  emits: ['click'],
  setup(props, { attrs, emit, slots }) {
    return () => h('button', { ...attrs, disabled: props.disabled, onClick: () => emit('click') }, slots.default?.())
  },
})

const ModalStub = defineComponent({
  name: 'AModal',
  props: { open: Boolean },
  emits: ['ok', 'cancel'],
  setup(props, { emit, slots }) {
    return () => props.open
      ? h('div', { 'data-testid': 'modal' }, [
          slots.default?.(),
          h('button', { 'data-testid': 'modal-ok', onClick: () => emit('ok') }, '提交'),
          h('button', { 'data-testid': 'modal-cancel', onClick: () => emit('cancel') }, '取消'),
        ])
      : null
  },
})

const TextareaStub = defineComponent({
  name: 'ATextarea',
  inheritAttrs: false,
  props: { value: String },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('textarea', {
      ...attrs,
      value: props.value,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLTextAreaElement).value),
    })
  },
})

const props = { taskId: 'task-a', taskRecordId: 'assoc-a', runNumber: 2, jobId: 'job-a', userId: 'qc-a' }

function entry(overrides: Record<string, unknown> = {}) {
  return {
    id: 'rv-1', request_id: 'req-old', task_id: 'task-a', task_record_id: 'assoc-a', run_number: 1,
    job_id: 'job-old', envelope_id: 'env-old', rule_set_key: 'lx0609', rule_set_version: 'v1',
    stage: 'initial', decision: 'doubtful', reason: '时间证据不足', reviewer_id: 'qc-a',
    created_at: '2026-09-25T08:00:00Z', ...overrides,
  }
}

function view(overrides: Record<string, unknown> = {}) {
  return {
    success: true,
    status: 200,
    data: {
      task_id: 'task-a', task_record_id: 'assoc-a', run_number: 2,
      state: 'pending_review', stage: 'initial', reason_code: null, can_submit: true,
      current: null, history: [], result: { job_id: 'job-a', envelope_id: 'env-a' },
      ...overrides,
    },
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function mountPanel(overrides: Partial<typeof props> = {}) {
  return mount(TaskRecordReviewPanel, {
    props: { ...props, ...overrides },
    global: { stubs: {
      'a-button': ButtonStub,
      'a-modal': ModalStub,
      'a-textarea': TextareaStub,
      'a-tag': { template: '<span><slot /></span>' },
      RotateCw: true,
    } },
  })
}

async function decide(wrapper: ReturnType<typeof mountPanel>, button: 'approve' | 'doubt', reason = '') {
  await wrapper.get(`[data-testid="record-review-${button}"]`).trigger('click')
  if (reason) await wrapper.get('#record-review-reason').setValue(reason)
  await wrapper.get('[data-testid="modal-ok"]').trigger('click')
  await flushPromises()
}

describe('TaskRecordReviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue(view())
  })

  it('按服务端状态渲染标签、不可审核原因与历史决定', async () => {
    api.get.mockResolvedValueOnce(view({
      state: 'pending_recheck', stage: 'recheck', history: [entry()],
    }))
    const wrapper = mountPanel()
    await flushPromises()
    expect(api.get).toHaveBeenCalledWith('task-a', 'assoc-a', 2)
    expect(wrapper.get('[data-testid="record-review-state"]').text()).toBe('待复审')
    const history = wrapper.get('[data-testid="record-review-history-item"]').text()
    expect(history).toContain('初审')
    expect(history).toContain('存疑')
    expect(history).toContain('时间证据不足')
    expect(history).toContain('审核人 qc-a')
    wrapper.unmount()

    api.get.mockResolvedValueOnce(view({ state: 'unavailable', stage: null, reason_code: 'envelope_ambiguous', can_submit: false }))
    const unavailable = mountPanel()
    await flushPromises()
    expect(unavailable.get('[data-testid="record-review-state"]').text()).toBe('不可审核')
    expect(unavailable.get('[data-testid="record-review-unavailable"]').text()).toContain('质控结果对象不唯一')
    expect(unavailable.find('[data-testid="record-review-approve"]').exists()).toBe(false)
    unavailable.unmount()

    api.get.mockResolvedValueOnce(view({ state: 'approved', current: entry({ decision: 'approved', reason: null }), can_submit: false }))
    const approved = mountPanel()
    await flushPromises()
    expect(approved.get('[data-testid="record-review-state"]').text()).toBe('审核通过')
    expect(approved.find('[data-testid="record-review-approve"]').exists()).toBe(false)
  })

  it('can_submit 为 false 时按钮禁用', async () => {
    api.get.mockResolvedValueOnce(view({ can_submit: false }))
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.get('[data-testid="record-review-approve"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="record-review-doubt"]').attributes('disabled')).toBeDefined()
  })

  it('存疑必须填写原因，空白原因不发请求', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await decide(wrapper, 'doubt', '   ')
    expect(api.submit).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="modal"]').text()).toContain('请填写存疑原因')
  })

  it('提交成功后以 GET 复核本请求编号再显示成功', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    api.submit.mockImplementationOnce((_t: string, _r: string, payload: { request_id: string }) => Promise.resolve({
      success: true, status: 200, data: { ...entry(), request_id: payload.request_id, state: 'doubtful', idempotent: false },
    }))
    api.get.mockImplementationOnce(() => {
      const requestId = api.submit.mock.calls[0][2].request_id as string
      return Promise.resolve(view({
        state: 'doubtful', can_submit: false,
        current: entry({ request_id: requestId, run_number: 2, job_id: 'job-a', envelope_id: 'env-a' }),
        history: [entry({ request_id: requestId })],
      }))
    })
    await decide(wrapper, 'doubt', '  入院时间缺失  ')

    expect(api.submit).toHaveBeenCalledWith('task-a', 'assoc-a', {
      run_number: 2, decision: 'doubtful', reason: '入院时间缺失',
      request_id: expect.any(String), envelope_id: 'env-a',
    })
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="record-review-state"]').text()).toBe('审核存疑')
    expect(wrapper.get('[role="status"]').text()).toContain('已保存并确认')
    expect(wrapper.emitted('review-submitted')).toEqual([['doubtful']])
  })

  it('POST 成功但 GET 未见该决定时不乐观宣称成功', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    api.submit.mockImplementationOnce((_t: string, _r: string, payload: { request_id: string }) => Promise.resolve({
      success: true, status: 200, data: { ...entry(), request_id: payload.request_id, state: 'approved', idempotent: false },
    }))
    await decide(wrapper, 'approve')
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="record-review-error"]').text()).toContain('状态未确认')
    expect(wrapper.emitted('review-submitted')).toBeUndefined()
  })

  it.each([
    ['result_changed', '质控结果已被替换'],
    ['already_decided', '该结果已有审核决定'],
    ['idempotency_conflict', '请求编号冲突'],
    ['state_conflict', '不允许审核'],
    ['result_unavailable', '不可用于审核'],
    ['unsupported_rule_set', '规则集不支持'],
  ])('409 %s 提示并刷新，后续使用新请求编号', async (code, text) => {
    const wrapper = mountPanel()
    await flushPromises()
    api.submit.mockResolvedValueOnce({ success: false, status: 409, code, message: '服务端原文' })
    await decide(wrapper, 'approve')
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="record-review-error"]').text()).toContain(text)
    expect(wrapper.get('[data-testid="record-review-approve"]').attributes('disabled')).toBeUndefined()

    api.submit.mockResolvedValueOnce({ success: false, status: 409, code, message: '服务端原文' })
    await decide(wrapper, 'approve')
    expect(api.submit.mock.calls[1][2].request_id).not.toBe(api.submit.mock.calls[0][2].request_id)
  })

  it('网络异常或 503 时按钮恢复可用，重试沿用原请求编号', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    api.submit
      .mockResolvedValueOnce({ success: false, status: 503, message: '病历审核服务暂不可用' })
      .mockRejectedValueOnce(new Error('timeout'))
    await decide(wrapper, 'approve')
    expect(wrapper.get('[data-testid="record-review-error"]').text()).toContain('可重试')
    expect(wrapper.get('[data-testid="record-review-approve"]').attributes('disabled')).toBeUndefined()

    await decide(wrapper, 'approve')
    expect(wrapper.get('[data-testid="record-review-error"]').text()).toContain('网络异常')
    expect(wrapper.get('[data-testid="record-review-approve"]').attributes('disabled')).toBeUndefined()
    expect(api.submit.mock.calls[1][2].request_id).toBe(api.submit.mock.calls[0][2].request_id)
  })

  it('切换病历或运行后丢弃迟到的 GET 与 POST 响应', async () => {
    const lateGet = deferred<ReturnType<typeof view>>()
    api.get.mockImplementation((_t: string, taskRecordId: string, runNumber: number) =>
      Promise.resolve(view({ task_record_id: taskRecordId, run_number: runNumber })))
    api.get.mockReturnValueOnce(lateGet.promise)
    const wrapper = mountPanel()
    await wrapper.setProps({ taskRecordId: 'assoc-b' })
    await flushPromises()
    expect(wrapper.get('[data-testid="record-review-state"]').text()).toBe('待审核')
    lateGet.resolve(view({ state: 'approved' }))
    await flushPromises()
    expect(wrapper.get('[data-testid="record-review-state"]').text()).toBe('待审核')
    wrapper.unmount()

    api.get.mockReset().mockImplementation((_t: string, taskRecordId: string, runNumber: number) =>
      Promise.resolve(view({ task_record_id: taskRecordId, run_number: runNumber })))
    const latePost = deferred<{ success: boolean; status: number; data: object }>()
    api.submit.mockReturnValueOnce(latePost.promise)
    const second = mountPanel()
    await flushPromises()
    await decide(second, 'approve')
    await second.setProps({ runNumber: 3 })
    await flushPromises()
    const getCalls = api.get.mock.calls.length
    latePost.resolve({ success: true, status: 200, data: {} })
    await flushPromises()
    expect(api.get.mock.calls.length).toBe(getCalls)
    expect(second.find('[role="status"]').exists()).toBe(false)
    expect(second.emitted('review-submitted')).toBeUndefined()
  })
})
