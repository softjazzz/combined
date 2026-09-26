import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/api/manualDefectReviews', () => ({ getCaseManualDefects: api.get }))

import CaseManualDefectPanel from '@/components/qc/CaseManualDefectPanel.vue'

const props = { instituteId: 'H1', patientId: 'P1', visitId: 'V1' }

function item(overrides: Record<string, unknown> = {}) {
  return {
    id: 'md-1', institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', task_id: 'task-a',
    task_record_id: 'assoc-a', run_number: 1, rule_code: 'LX0609-018', rule_name: '主诉能导出第一诊断',
    description: '主诉与第一诊断不符', severity: 'warning', location: '入院记录', suggestion: null,
    manual_review_status: 'pending', manual_created_by: 'qc-a', created_at: '2026-09-25T08:00:00Z',
    ...overrides,
  }
}

function ok(items: unknown[], total = items.length) {
  return { success: true, status: 200, data: { items, total } }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('CaseManualDefectPanel', () => {
  beforeEach(() => api.get.mockReset())

  it('按三坐标读取并渲染条目与审核状态标签（含未知）', async () => {
    api.get.mockResolvedValueOnce(ok([
      item(),
      item({ id: 'md-2', manual_review_status: 'approved' }),
      item({ id: 'md-3', manual_review_status: 'rejected' }),
      item({ id: 'md-4', manual_review_status: 'weird', description: null }),
    ]))
    const wrapper = mount(CaseManualDefectPanel, { props })
    await flushPromises()

    expect(api.get).toHaveBeenCalledWith({ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' })
    expect(wrapper.findAll('[data-testid="case-manual-defect-item"]')).toHaveLength(4)
    expect(wrapper.findAll('[data-testid="case-manual-defect-status"]').map((node) => node.text()))
      .toEqual(['待审核', '已通过', '已驳回', '未知'])
    expect(wrapper.text()).toContain('主诉能导出第一诊断')
    expect(wrapper.get('[data-testid="case-manual-defects-total"]').text()).toBe('共 4 条')
    expect(wrapper.find('[data-testid="case-manual-defects-truncated"]').exists()).toBe(false)
  })

  it('total 大于 items 时提示仅显示最近条目', async () => {
    api.get.mockResolvedValueOnce(ok([item()], 230))
    const wrapper = mount(CaseManualDefectPanel, { props })
    await flushPromises()
    expect(wrapper.get('[data-testid="case-manual-defects-truncated"]').text()).toBe('仅显示最近 1 条，共 230 条')
  })

  it('403 时整块隐藏并通知父级', async () => {
    api.get.mockResolvedValueOnce({ success: false, status: 403, message: '没有权限' })
    const wrapper = mount(CaseManualDefectPanel, { props })
    await flushPromises()
    expect(wrapper.find('[data-testid="case-manual-defects"]').exists()).toBe(false)
    expect(wrapper.emitted('forbidden')).toHaveLength(1)
  })

  it('读取失败显示可重试且不显示 0 条，重试后恢复', async () => {
    api.get
      .mockResolvedValueOnce({ success: false, status: 503, message: '服务暂不可用' })
      .mockResolvedValueOnce(ok([item()]))
    const wrapper = mount(CaseManualDefectPanel, { props })
    await flushPromises()
    expect(wrapper.get('[data-testid="case-manual-defects-error"]').text()).toContain('服务暂不可用')
    expect(wrapper.find('[data-testid="case-manual-defects-total"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('0 条')

    await wrapper.get('[data-testid="case-manual-defects-retry"]').trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('[data-testid="case-manual-defect-item"]')).toHaveLength(1)
  })

  it('返回条目三坐标与当前病例不一致时停止展示', async () => {
    api.get.mockResolvedValueOnce(ok([item({ visit_id: 'V-other' })]))
    const wrapper = mount(CaseManualDefectPanel, { props })
    await flushPromises()
    expect(wrapper.find('[data-testid="case-manual-defect-item"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="case-manual-defects-error"]').text()).toContain('不一致')
  })

  it('切换三坐标后丢弃上一病例的迟到响应', async () => {
    const first = deferred<ReturnType<typeof ok>>()
    const second = deferred<ReturnType<typeof ok>>()
    api.get.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise)
    const wrapper = mount(CaseManualDefectPanel, { props })
    await flushPromises()
    await wrapper.setProps({ visitId: 'V2' })
    await flushPromises()

    second.resolve(ok([item({ id: 'md-v2', visit_id: 'V2', rule_name: '第二病例缺陷' })]))
    await flushPromises()
    first.resolve(ok([item({ rule_name: '第一病例缺陷' })]))
    await flushPromises()

    expect(wrapper.text()).toContain('第二病例缺陷')
    expect(wrapper.text()).not.toContain('第一病例缺陷')
    expect(wrapper.findAll('[data-testid="case-manual-defect-item"]')).toHaveLength(1)
  })
})
