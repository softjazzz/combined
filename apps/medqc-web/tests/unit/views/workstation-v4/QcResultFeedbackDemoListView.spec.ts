import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  user: {
    id: 'admin-001',
    email: 'admin@medqc.com',
    is_demo_account: true,
  },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: mocks.user }),
}))

vi.mock('@/api/qc-result-feedback-demo', () => ({
  listQcResultFeedbackDemo: mocks.list,
}))

import QcResultFeedbackDemoListView from '@/views/workstation-v4/QcResultFeedbackDemoListView.vue'

describe('QcResultFeedbackDemoListView', () => {
  beforeEach(() => {
    mocks.user.id = 'admin-001'
    mocks.user.email = 'admin@medqc.com'
    mocks.user.is_demo_account = true
    mocks.list.mockClear()
    mocks.list.mockResolvedValue({
      success: true,
      data: [
        {
          id: 'feedback-1',
          rule_id: 'LX0609-06-01-05',
          rule_name: 'CT/MRI阳性结果分析',
          original_status: 'non_compliant',
          feedback_type: 'incorrect',
          comment: '需复核时间窗。',
          updated_at: '2026-08-18T08:00:00+00:00',
          patient_name: '冯丽平',
          record_number: '208790',
          visit_id: '208790-合成检验v1',
          department: '重症医学科（ICU）',
        },
        {
          id: 'feedback-2',
          rule_id: 'LX0609-01-01-01',
          original_status: 'compliant',
          feedback_type: 'correct',
          updated_at: '2026-08-18T07:00:00+00:00',
        },
      ],
    })
  })

  it('汇总反馈时明确展示病历和质控点上下文', async () => {
    const wrapper = mount(QcResultFeedbackDemoListView)
    await flushPromises()

    expect(mocks.list).toHaveBeenCalledWith()
    expect(wrapper.text()).toContain('全部反馈')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('LX0609-06-01-05')
    expect(wrapper.text()).toContain('CT/MRI阳性结果分析')
    expect(wrapper.text()).toContain('冯丽平')
    expect(wrapper.text()).toContain('208790')
    expect(wrapper.text()).toContain('重症医学科（ICU）')
    expect(wrapper.text()).toContain('结果有误')
    expect(wrapper.text()).toContain('需复核时间窗。')
    expect(wrapper.text()).not.toContain('rec_')
  })

  it('非演示账号不读取汇总反馈', async () => {
    mocks.user.is_demo_account = false
    const wrapper = mount(QcResultFeedbackDemoListView)
    await flushPromises()

    expect(mocks.list).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('此页面仅对演示账号开放。')
  })

  it('按反馈类型筛选并保留病历与规则上下文，不重复请求接口', async () => {
    const wrapper = mount(QcResultFeedbackDemoListView)
    await flushPromises()
    await wrapper.get('[data-testid="feedback-filter-incorrect"]').trigger('click')
    expect(wrapper.findAll('[data-testid="feedback-row"]')).toHaveLength(1)
    expect(wrapper.get('[data-testid="feedback-row"]').text()).toContain('CT/MRI阳性结果分析')
    expect(wrapper.text()).toContain('1 条记录')
    expect(mocks.list).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="feedback-filter-correct"]').trigger('click')
    expect(wrapper.findAll('[data-testid="feedback-row"]')).toHaveLength(1)
    expect(wrapper.get('[data-testid="feedback-row"]').text()).toContain('LX0609-01-01-01')
  })

  it('搜索病历或科室，无匹配时明确提示', async () => {
    const wrapper = mount(QcResultFeedbackDemoListView)
    await flushPromises()
    const input = wrapper.get('input[aria-label="搜索反馈"]')
    await input.setValue('208790')
    expect(wrapper.findAll('[data-testid="feedback-row"]')).toHaveLength(1)
    await input.setValue('不存在的科室')
    expect(wrapper.findAll('[data-testid="feedback-row"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('没有符合条件的反馈记录。')
  })

  it('点击才展开完整说明与期望结果，保留换行和北京时间', async () => {
    const comment = '第一行复核意见\n第二行详细说明'
    mocks.list.mockResolvedValueOnce({ success: true, data: [{
      id: 'expanded', rule_id: 'LX0609-06-01-05', original_status: 'non_compliant',
      feedback_type: 'incorrect', expected_status: 'compliant', error_category: 'wrong_evidence',
      comment, created_at: '2026-08-18T08:00:00Z', updated_at: '2026-08-18T09:00:00Z',
    }] })
    const wrapper = mount(QcResultFeedbackDemoListView)
    await flushPromises()
    expect(wrapper.find('.feedback-demo-detail').exists()).toBe(false)
    expect(wrapper.get('.feedback-demo-date').text()).toBe('2026-08-18')
    const button = wrapper.get('.feedback-demo-open')
    await button.trigger('click')
    const detail = wrapper.get('.feedback-demo-detail')
    expect(detail.text()).toContain('期望结果合规')
    expect(detail.text()).toContain('引用依据有误')
    expect(detail.get('.feedback-demo-comment p').text()).toBe(comment)
    expect(detail.text()).toContain('2026-08-18 16:00')
    expect(detail.text()).toContain('2026-08-18 17:00')
    expect(button.attributes('aria-expanded')).toBe('true')
    await button.trigger('click')
    expect(wrapper.find('.feedback-demo-detail').exists()).toBe(false)
    expect(mocks.list).toHaveBeenCalledTimes(1)
  })

  it('接口读取失败时不渲染反馈记录', async () => {
    mocks.list.mockResolvedValueOnce({ success: false, message: '暂时无法读取' })
    const wrapper = mount(QcResultFeedbackDemoListView)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('暂时无法读取')
    expect(wrapper.findAll('[data-testid="feedback-row"]')).toHaveLength(0)
  })
})
