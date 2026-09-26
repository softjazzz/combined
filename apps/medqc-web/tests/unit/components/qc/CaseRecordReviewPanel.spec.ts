import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn(), submit: vi.fn() }))
vi.mock('@/api/recordReviews', () => ({
  getCaseRecordReview: api.get,
  submitCaseRecordReview: api.submit,
}))

import CaseRecordReviewPanel from '@/components/qc/CaseRecordReviewPanel.vue'
import { recordReviewStubs } from './recordReviewStubs'

const props = { instituteId: 'H1', patientId: 'P1', visitId: 'V1', jobId: 'job-a', userId: 'mgr-a' }

function entry(overrides: Record<string, unknown> = {}) {
  return {
    id: 'rv-1', request_id: 'req-old', review_context: 'task', task_id: 'task-a', task_record_id: 'assoc-a',
    run_number: 1, job_id: 'job-old', envelope_id: 'env-old', rule_set_key: 'lx0609', rule_set_version: 'v1',
    stage: 'initial', decision: 'doubtful', reason: '时间证据不足', reviewer_id: 'qc-a',
    created_at: '2026-09-25T08:00:00Z', ...overrides,
  }
}

function view(overrides: Record<string, unknown> = {}) {
  return {
    success: true,
    status: 200,
    data: {
      review_context: 'workspace', institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', rule_set_key: 'lx0609',
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
  return mount(CaseRecordReviewPanel, {
    props: { ...props, ...overrides },
    global: { stubs: recordReviewStubs },
  })
}

async function decide(wrapper: ReturnType<typeof mountPanel>, button: 'approve' | 'doubt', reason = '') {
  await wrapper.get(`[data-testid="record-review-${button}"]`).trigger('click')
  if (reason) await wrapper.get('#record-review-reason').setValue(reason)
  await wrapper.get('[data-testid="modal-ok"]').trigger('click')
  await flushPromises()
}

describe('CaseRecordReviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue(view())
  })

  it('以三坐标读取并渲染状态、不可审核原因与历史来源', async () => {
    api.get.mockResolvedValueOnce(view({
      state: 'pending_recheck', stage: 'recheck',
      history: [entry(), entry({ id: 'rv-2', review_context: 'workspace', task_id: null, task_record_id: null, run_number: null })],
    }))
    const wrapper = mountPanel()
    await flushPromises()
    expect(api.get).toHaveBeenCalledWith({ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' })
    expect(wrapper.find('[data-testid="case-record-review"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="record-review-state"]').text()).toBe('待复审')
    const items = wrapper.findAll('[data-testid="record-review-history-item"]').map((item) => item.text())
    expect(items[0]).toContain('来源：质控任务')
    expect(items[1]).toContain('来源：病历列表')
    wrapper.unmount()

    api.get.mockResolvedValueOnce(view({
      state: 'unavailable', stage: null, reason_code: 'result_not_run', can_submit: false,
      result: { job_id: null, envelope_id: null },
    }))
    const unavailable = mountPanel()
    await flushPromises()
    expect(unavailable.get('[data-testid="record-review-state"]').text()).toBe('不可审核')
    expect(unavailable.get('[data-testid="record-review-unavailable"]').text()).toContain('原因未知（result_not_run）')
    expect(unavailable.find('[data-testid="record-review-approve"]').exists()).toBe(false)
  })

  it('响应三坐标或结果 job 与当前病历不一致时拒绝展示', async () => {
    api.get.mockResolvedValueOnce(view({ visit_id: 'V2' }))
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.find('[data-testid="record-review-state"]').exists()).toBe(false)
    expect(wrapper.get('[role="alert"]').text()).toContain('身份校验失败')
    wrapper.unmount()

    api.get.mockResolvedValueOnce(view({ result: { job_id: 'job-other', envelope_id: 'env-a' } }))
    const mismatch = mountPanel()
    await flushPromises()
    expect(mismatch.find('[data-testid="record-review-approve"]').exists()).toBe(false)
  })

  it('缺少 job_id 时不可提交', async () => {
    api.get.mockResolvedValueOnce(view({ result: { job_id: null, envelope_id: 'env-a' } }))
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.get('[data-testid="record-review-approve"]').attributes('disabled')).toBeDefined()
  })

  it('存疑必须填写原因，空白原因不发请求', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    await decide(wrapper, 'doubt', '   ')
    expect(api.submit).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="modal"]').text()).toContain('请填写存疑原因')
  })

  it('提交三坐标与结果锚点，成功后以 GET 复核本请求编号再通知', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    api.submit.mockImplementationOnce((payload: { request_id: string }) => Promise.resolve({
      success: true, status: 200, data: { ...entry(), request_id: payload.request_id, state: 'doubtful', idempotent: false },
    }))
    api.get.mockImplementationOnce(() => {
      const requestId = api.submit.mock.calls[0][0].request_id as string
      return Promise.resolve(view({
        state: 'doubtful', can_submit: false,
        current: entry({ request_id: requestId, review_context: 'workspace', job_id: 'job-a', envelope_id: 'env-a' }),
        history: [entry({ request_id: requestId, review_context: 'workspace' })],
      }))
    })
    await decide(wrapper, 'doubt', '  入院时间缺失  ')

    expect(api.submit).toHaveBeenCalledWith({
      institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', job_id: 'job-a', envelope_id: 'env-a',
      decision: 'doubtful', reason: '入院时间缺失', request_id: expect.any(String),
    })
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="record-review-state"]').text()).toBe('审核存疑')
    expect(wrapper.get('[role="status"]').text()).toContain('已保存并确认')
    expect(wrapper.emitted('review-submitted')).toEqual([['doubtful']])
  })

  it('POST 成功但 GET 未见该决定时不乐观宣称成功、不通知列表', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    api.submit.mockImplementationOnce((payload: { request_id: string }) => Promise.resolve({
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
    ['result_unavailable', '不可用于审核'],
    ['unsupported_rule_set', '规则集不支持'],
  ])('409 %s 提示并刷新，后续使用新请求编号', async (code, text) => {
    const wrapper = mountPanel()
    await flushPromises()
    api.submit.mockResolvedValueOnce({ success: false, status: 409, code, message: '服务端原文' })
    await decide(wrapper, 'approve')
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[data-testid="record-review-error"]').text()).toContain(text)

    api.submit.mockResolvedValueOnce({ success: false, status: 409, code, message: '服务端原文' })
    await decide(wrapper, 'approve')
    expect(api.submit.mock.calls[1][0].request_id).not.toBe(api.submit.mock.calls[0][0].request_id)
  })

  it('503 或网络异常后重试沿用原请求编号', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    api.submit
      .mockResolvedValueOnce({ success: false, status: 503, message: '病历审核服务暂不可用' })
      .mockRejectedValueOnce(new Error('timeout'))
    await decide(wrapper, 'approve')
    expect(wrapper.get('[data-testid="record-review-error"]').text()).toContain('可重试')
    await decide(wrapper, 'approve')
    expect(api.submit.mock.calls[1][0].request_id).toBe(api.submit.mock.calls[0][0].request_id)
  })

  it('GET 403 时不展示面板也不报错，并通知父级', async () => {
    api.get.mockResolvedValueOnce({ success: false, status: 403, message: '没有病历审核权限' })
    const wrapper = mountPanel()
    await flushPromises()
    expect(wrapper.find('[data-testid="case-record-review"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('没有病历审核权限')
    expect(wrapper.emitted('forbidden')).toHaveLength(1)
  })

  it('切换病历后丢弃迟到的 GET 与 POST 响应', async () => {
    const lateGet = deferred<ReturnType<typeof view>>()
    api.get.mockImplementation((identity: { visit_id: string }) =>
      Promise.resolve(view({ visit_id: identity.visit_id })))
    api.get.mockReturnValueOnce(lateGet.promise)
    const wrapper = mountPanel()
    await wrapper.setProps({ visitId: 'V2' })
    await flushPromises()
    expect(wrapper.get('[data-testid="record-review-state"]').text()).toBe('待审核')
    lateGet.resolve(view({ state: 'approved' }))
    await flushPromises()
    expect(wrapper.get('[data-testid="record-review-state"]').text()).toBe('待审核')
    wrapper.unmount()

    api.get.mockReset().mockImplementation((identity: { visit_id: string }) =>
      Promise.resolve(view({ visit_id: identity.visit_id })))
    const latePost = deferred<{ success: boolean; status: number; data: object }>()
    api.submit.mockReturnValueOnce(latePost.promise)
    const second = mountPanel()
    await flushPromises()
    await decide(second, 'approve')
    await second.setProps({ visitId: 'V3' })
    await flushPromises()
    const getCalls = api.get.mock.calls.length
    latePost.resolve({ success: true, status: 200, data: {} })
    await flushPromises()
    expect(api.get.mock.calls.length).toBe(getCalls)
    expect(second.find('[role="status"]').exists()).toBe(false)
    expect(second.emitted('review-submitted')).toBeUndefined()
  })
})
