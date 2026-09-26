import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/recordOperations', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/recordOperations')>()
  return { ...actual, getCaseOperations: api.get }
})

import CaseOperationTimeline from '@/components/qc/CaseOperationTimeline.vue'

const props = { instituteId: 'H1', patientId: 'P1', visitId: 'V1' }

function op(type: string, summary: Record<string, unknown> | null, overrides: Record<string, unknown> = {}) {
  return {
    id: `${type}:1`, type, occurred_at: '2026-09-27T08:00:00Z',
    actor_id: 'u-1', actor_name: '张质控', summary, ...overrides,
  }
}

function ok(items: unknown[], total = items.length, extra: Record<string, unknown> = {}) {
  return { success: true, status: 200, data: { items, total, limit: 100, ...extra } }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function texts(wrapper: VueWrapper, testId: string) {
  return wrapper.findAll(`[data-testid="${testId}"]`).map((node) => node.text())
}

describe('CaseOperationTimeline', () => {
  beforeEach(() => api.get.mockReset())

  it('按三坐标读取并渲染各类型中文名与摘要', async () => {
    api.get.mockResolvedValueOnce(ok([
      op('qc_run_completed', { job_id: 'job-1', rule_set_version: 'v1', result_count: 49, task_id: 'task-a', task_run_number: 2 }),
      op('record_review', { review_context: 'task', stage: 'recheck', decision: 'doubtful', reason: '诊断依据不足', job_id: 'job-1', task_id: 'task-a' }, { id: 'r1' }),
      op('record_review', { review_context: 'workspace', stage: 'initial', decision: 'approved', reason: null }, { id: 'r2' }),
      op('manual_defect_created', { defect_id: 'd1', rule_name: '主诉能导出第一诊断', task_id: 'task-a', run_number: 1 }),
      op('manual_defect_reviewed', { defect_id: 'd1', decision: 'rejected', reason: '证据不足' }),
      op('task_record_started', { task_id: 'task-a', task_record_id: 'tr1', completed_run_number: null }),
      op('task_record_completed', { task_id: 'task-a', task_record_id: 'tr1', completed_run_number: 1 }),
      op('future_event', { secret: 'x' }),
    ]))
    const wrapper = mount(CaseOperationTimeline, { props })
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith({ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' })
    expect(texts(wrapper, 'case-operation-type')).toEqual([
      '质控运行完成', '病历审核', '病历审核', '人工缺陷创建', '人工缺陷审核', '未知操作', '完成任务病历', '未知操作',
    ])
    const rows = wrapper.findAll('[data-testid="case-operation-item"]')
    const summaries = rows.map((node) => node.text())
    expect(summaries[0]).toContain('结果 49 条')
    expect(summaries[0]).toContain('任务 task-a')
    expect(summaries[0]).toContain('第 2 次运行')
    expect(summaries[1]).toContain('阶段 复审')
    expect(summaries[1]).toContain('结论 存疑')
    expect(summaries[1]).toContain('原因 诊断依据不足')
    expect(summaries[1]).toContain('来源 任务')
    expect(summaries[2]).toContain('阶段 初审')
    expect(summaries[2]).toContain('结论 通过')
    expect(summaries[2]).toContain('来源 病历列表')
    expect(summaries[2]).not.toContain('原因')
    expect(summaries[3]).toContain('规则 主诉能导出第一诊断')
    expect(summaries[4]).toContain('结论 驳回')
    expect(summaries[4]).toContain('原因 证据不足')
    expect(summaries[5]).not.toContain('完成第')
    expect(summaries[6]).toContain('完成第 1 次运行')
    // 未知类型不展示摘要，不伪造字段。
    expect(summaries[7]).not.toContain('secret')
    expect(rows[7].find('[data-testid="case-operation-summary"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="case-operations-total"]').text()).toBe('共 8 条')
    expect(wrapper.find('[data-testid="case-operations-truncated"]').exists()).toBe(false)
  })

  it('映射外的枚举值显示未知，而非伪造结论', async () => {
    api.get.mockResolvedValueOnce(ok([op('record_review', { stage: 'third', decision: 'maybe' })]))
    const wrapper = mount(CaseOperationTimeline, { props })
    await flushPromises()
    const summary = wrapper.get('[data-testid="case-operation-summary"]').text()
    expect(summary).toContain('阶段 未知')
    expect(summary).toContain('结论 未知')
    expect(summary).not.toContain('通过')
  })

  it('操作人优先显示名，缺失时回退 id，均缺失显示未知', async () => {
    api.get.mockResolvedValueOnce(ok([
      op('record_review', {}, { id: 'a' }),
      op('record_review', {}, { id: 'b', actor_name: null, actor_id: 'user-42' }),
      op('record_review', {}, { id: 'c', actor_name: '  ', actor_id: null }),
    ]))
    const wrapper = mount(CaseOperationTimeline, { props })
    await flushPromises()
    expect(texts(wrapper, 'case-operation-actor')).toEqual(['张质控', 'user-42', '操作人未知'])
  })

  it('空列表显示暂无操作记录', async () => {
    api.get.mockResolvedValueOnce(ok([]))
    const wrapper = mount(CaseOperationTimeline, { props })
    await flushPromises()
    expect(wrapper.find('[data-testid="case-operations-empty"]').exists()).toBe(true)
  })

  it('total 大于 items 时提示仅显示最近 N 条', async () => {
    api.get.mockResolvedValueOnce(ok([op('record_review', {})], 230))
    const wrapper = mount(CaseOperationTimeline, { props })
    await flushPromises()
    expect(wrapper.get('[data-testid="case-operations-truncated"]').text()).toBe('仅显示最近 1 条，共 230 条')
  })

  it('403 时整块隐藏并通知父级', async () => {
    api.get.mockResolvedValueOnce({ success: false, status: 403, message: '没有权限' })
    const wrapper = mount(CaseOperationTimeline, { props })
    await flushPromises()
    expect(wrapper.find('[data-testid="case-operations"]').exists()).toBe(false)
    expect(wrapper.emitted('forbidden')).toHaveLength(1)
  })

  it('读取失败显示可重试且不显示为无记录，重试后恢复', async () => {
    api.get
      .mockResolvedValueOnce({ success: false, status: 503, message: '操作记录暂不可用' })
      .mockResolvedValueOnce(ok([op('record_review', {})]))
    const wrapper = mount(CaseOperationTimeline, { props })
    await flushPromises()
    expect(wrapper.get('[data-testid="case-operations-error"]').text()).toContain('操作记录暂不可用')
    expect(wrapper.find('[data-testid="case-operations-empty"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="case-operations-total"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('暂无')

    await wrapper.get('[data-testid="case-operations-retry"]').trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('[data-testid="case-operation-item"]')).toHaveLength(1)
  })

  it.each([
    ['顶层回显三坐标', ok([op('record_review', {})], 1, { visit_id: 'V-other' })],
    ['条目回显三坐标', ok([op('record_review', {}, { patient_id: 'P-other' })])],
    ['total 小于条目数', ok([op('record_review', {}), op('record_review', {}, { id: 'r2' })], 1)],
  ])('%s与当前病例不一致时拒绝展示', async (_label, payload) => {
    api.get.mockResolvedValueOnce(payload)
    const wrapper = mount(CaseOperationTimeline, { props })
    await flushPromises()
    expect(wrapper.find('[data-testid="case-operation-item"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="case-operations-error"]').text()).toContain('不一致')
  })

  it('切换三坐标后丢弃上一病例的迟到响应', async () => {
    const first = deferred<ReturnType<typeof ok>>()
    const second = deferred<ReturnType<typeof ok>>()
    api.get.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise)
    const wrapper = mount(CaseOperationTimeline, { props })
    await flushPromises()
    await wrapper.setProps({ visitId: 'V2' })
    await flushPromises()
    expect(api.get).toHaveBeenLastCalledWith({ institute_id: 'H1', patient_id: 'P1', visit_id: 'V2' })

    second.resolve(ok([op('manual_defect_created', { rule_name: '第二病例规则' })]))
    await flushPromises()
    first.resolve(ok([op('manual_defect_created', { rule_name: '第一病例规则' })]))
    await flushPromises()

    expect(wrapper.text()).toContain('第二病例规则')
    expect(wrapper.text()).not.toContain('第一病例规则')
    expect(wrapper.findAll('[data-testid="case-operation-item"]')).toHaveLength(1)
  })
})
