import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import QcResultFeedbackControl from '@/views/workstation-v4/customer-sample-validation/QcResultFeedbackControl.vue'
import { useQcResultFeedback } from '@/views/workstation-v4/customer-sample-validation/useQcResultFeedback'

const { useAuthStoreMock, getFeedbackMock, saveFeedbackMock } = vi.hoisted(() => ({
  useAuthStoreMock: vi.fn(),
  getFeedbackMock: vi.fn(),
  saveFeedbackMock: vi.fn(),
}))

vi.mock('@/stores/auth', () => ({ useAuthStore: useAuthStoreMock }))
vi.mock('@/api/qc-result-feedback-demo', async () => {
  const actual = await vi.importActual<typeof import('@/api/qc-result-feedback-demo')>(
    '@/api/qc-result-feedback-demo',
  )
  return {
    ...actual,
    getQcResultFeedbackDemo: getFeedbackMock,
    saveQcResultFeedbackDemo: saveFeedbackMock,
  }
})

beforeEach(() => {
  vi.clearAllMocks()
  useAuthStoreMock.mockReturnValue({
    user: {
      id: 'admin-001',
      email: 'admin@medqc.com',
      is_demo_account: true,
    },
  })
  getFeedbackMock.mockResolvedValue({ success: true, data: {} })
  saveFeedbackMock.mockResolvedValue({
    success: true,
    data: {
      rule_id: 'LX0609-001',
      original_status: 'non_compliant',
      feedback_type: 'correct',
    },
  })
})

describe('QcResultFeedbackControl', () => {
  it('准确反馈可以直接提交', async () => {
    const wrapper = mount(QcResultFeedbackControl)

    await wrapper.get('[data-testid="qc-result-feedback-correct"]').trigger('click')

    expect(wrapper.emitted('submit')).toEqual([[{ feedback_type: 'correct' }]])
  })

  it('有误反馈必须填写期望结果、问题类型和说明', async () => {
    const wrapper = mount(QcResultFeedbackControl)

    await wrapper.get('[data-testid="qc-result-feedback-incorrect"]').trigger('click')
    const submit = wrapper.get('[data-testid="qc-result-feedback-submit"]')
    expect((submit.element as HTMLButtonElement).disabled).toBe(true)

    await wrapper.get('[data-testid="qc-result-feedback-expected-status"]').setValue('data_gap')
    await wrapper.get('[data-testid="qc-result-feedback-error-category"]').setValue('wrong_status')
    await wrapper
      .get('[data-testid="qc-result-feedback-comment"]')
      .setValue('本次没有进行该项检查。')

    expect((submit.element as HTMLButtonElement).disabled).toBe(false)
    await wrapper.get('[data-testid="qc-result-feedback-form"]').trigger('submit')
    expect(wrapper.emitted('submit')).toEqual([
      [
        {
          feedback_type: 'incorrect',
          expected_status: 'data_gap',
          error_category: 'wrong_status',
          comment: '本次没有进行该项检查。',
        },
      ],
    ])
  })

  it('补充说明只要求说明文本，不显示开发处理语义', async () => {
    const wrapper = mount(QcResultFeedbackControl)

    await wrapper.get('[data-testid="qc-result-feedback-note"]').trigger('click')
    await wrapper
      .get('[data-testid="qc-result-feedback-comment"]')
      .setValue('建议核对当前病历的检查范围。')
    await wrapper.get('[data-testid="qc-result-feedback-form"]').trigger('submit')

    expect(wrapper.emitted('submit')).toEqual([
      [
        {
          feedback_type: 'note',
          comment: '建议核对当前病历的检查范围。',
        },
      ],
    ])
    expect(wrapper.text()).not.toContain('待处理')
    expect(wrapper.text()).not.toContain('开发者')
  })

  it('已有反馈显示当前账号的反馈并允许修改', async () => {
    const wrapper = mount(QcResultFeedbackControl, {
      props: {
        feedback: {
          rule_id: 'LX0609-001',
          original_status: 'non_compliant',
          feedback_type: 'incorrect',
          expected_status: 'not_applicable',
          comment: '本次未进行该项检查。',
        },
      },
    })

    expect(wrapper.text()).toContain('你的反馈')
    expect(wrapper.text()).toContain('结果有误')
    expect(wrapper.text()).toContain('本次未进行该项检查。')
    await wrapper.get('[data-testid="qc-result-feedback-edit"]').trigger('click')
    expect(wrapper.find('[data-testid="qc-result-feedback-form"]').exists()).toBe(true)
  })

  it('有误反馈保存成功后回到当前反馈摘要', async () => {
    const wrapper = mount(QcResultFeedbackControl)
    await wrapper.get('[data-testid="qc-result-feedback-incorrect"]').trigger('click')
    await wrapper.get('[data-testid="qc-result-feedback-expected-status"]').setValue('data_gap')
    await wrapper.get('[data-testid="qc-result-feedback-error-category"]').setValue('wrong_status')
    await wrapper.get('[data-testid="qc-result-feedback-comment"]').setValue('本次没有该项检查。')
    await wrapper.get('[data-testid="qc-result-feedback-form"]').trigger('submit')

    await wrapper.setProps({
      feedback: {
        rule_id: 'LX0609-001',
        original_status: 'non_compliant',
        feedback_type: 'incorrect',
        expected_status: 'data_gap',
        error_category: 'wrong_status',
        comment: '本次没有该项检查。',
      },
    })

    expect(wrapper.find('[data-testid="qc-result-feedback-form"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="qc-result-feedback-submitted"]').text()).toContain(
      '结果有误',
    )
  })

  it('补充说明保存成功后回到当前反馈摘要，保存失败保留表单', async () => {
    const wrapper = mount(QcResultFeedbackControl)
    await wrapper.get('[data-testid="qc-result-feedback-note"]').trigger('click')
    await wrapper.get('[data-testid="qc-result-feedback-comment"]').setValue('建议补充核对范围。')
    await wrapper.get('[data-testid="qc-result-feedback-form"]').trigger('submit')

    await wrapper.setProps({
      feedback: {
        rule_id: 'LX0609-001',
        original_status: 'non_compliant',
        feedback_type: 'note',
        comment: '建议补充核对范围。',
      },
    })
    expect(wrapper.find('[data-testid="qc-result-feedback-form"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="qc-result-feedback-submitted"]').text()).toContain(
      '补充说明',
    )

    await wrapper.get('[data-testid="qc-result-feedback-edit"]').trigger('click')
    await wrapper.setProps({ errorMessage: '反馈暂时无法保存，质控结果仍可正常查看。' })
    expect(wrapper.find('[data-testid="qc-result-feedback-form"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="qc-result-feedback-error"]').text()).toContain(
      '反馈暂时无法保存',
    )
  })
})

describe('useQcResultFeedback', () => {
  it('只为精确演示账号加载一次病历反馈，错误不回显用户说明', async () => {
    getFeedbackMock.mockResolvedValue({
      success: false,
      message: '保存失败：13800138000',
    })
    const host = defineComponent({
      setup() {
        return useQcResultFeedback('job-demo', 'rec-demo')
      },
      render() {
        return h('div', this.error)
      },
    })

    const wrapper = mount(host)
    await flushPromises()
    expect(getFeedbackMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).not.toContain('13800138000')
    expect(wrapper.text()).toContain('反馈暂时无法使用')
    wrapper.unmount()
  })

  it('非演示账号不加载也不提供反馈能力', async () => {
    useAuthStoreMock.mockReturnValue({
      user: { id: 'user-002', email: 'qc@example.com', is_demo_account: true },
    })
    const host = defineComponent({
      setup() {
        return useQcResultFeedback('job-demo', 'rec-demo')
      },
      render() {
        return h('div', this.isEnabled ? 'enabled' : 'disabled')
      },
    })

    const wrapper = mount(host)
    await flushPromises()
    expect(getFeedbackMock).not.toHaveBeenCalled()
    expect(wrapper.text()).toBe('disabled')
    wrapper.unmount()
  })
})
