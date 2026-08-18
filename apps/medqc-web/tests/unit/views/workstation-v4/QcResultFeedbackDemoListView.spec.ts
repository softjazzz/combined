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
    mocks.list.mockResolvedValue({
      success: true,
      data: [
        {
          id: 'feedback-1',
          rule_id: 'LX0609-012',
          original_status: 'non_compliant',
          feedback_type: 'incorrect',
          comment: '需复核时间窗。',
          updated_at: '2026-08-18T08:00:00+00:00',
        },
        {
          id: 'feedback-2',
          rule_id: 'LX0609-001',
          original_status: 'compliant',
          feedback_type: 'correct',
          updated_at: '2026-08-18T07:00:00+00:00',
        },
      ],
    })
  })

  it('汇总演示账号跨病历的全部反馈，并隐藏病历身份', async () => {
    const wrapper = mount(QcResultFeedbackDemoListView)
    await flushPromises()

    expect(mocks.list).toHaveBeenCalledWith()
    expect(wrapper.text()).toContain('全部反馈')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('LX0609-012')
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
})
