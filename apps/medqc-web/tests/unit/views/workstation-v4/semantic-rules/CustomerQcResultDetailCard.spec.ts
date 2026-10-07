import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CustomerQcResultDetailCard from '@/views/workstation-v4/semantic-rules/components/CustomerQcResultDetailCard.vue'

describe('CustomerQcResultDetailCard', () => {
  it('以固定层级展示结论、明细、规则要求、实际值和来源，建议交由父层统一展示', () => {
    const wrapper = mount(CustomerQcResultDetailCard, {
      props: {
        model: {
          isEnhanced: true,
          conclusion: '主诉长度超过20字，不符合本质控点要求。',
          detail: '主诉长度超过20字上限。',
          requirement: '主诉应能导出第一诊断，且主诉长度应不超过20字。',
          actualValue: '主诉长度：21字；已取得第一诊断。',
          evidenceSource: '入院记录—主诉',
          suggestion: '请补充诊断指向的症状、部位、性质及持续时间。',
        },
      },
    })

    expect(wrapper.text()).toContain('质控结论')
    expect(wrapper.text()).toContain('判定明细')
    expect(wrapper.text()).toContain('规则要求')
    expect(wrapper.text()).toContain('实际值')
    expect(wrapper.text()).toContain('证据来源')
    expect(wrapper.text()).toContain('主诉长度：21字')
    expect(wrapper.text()).not.toContain('请补充诊断指向的症状、部位、性质及持续时间。')
  })

  it('不渲染空字段，避免以占位符伪造事实', () => {
    const wrapper = mount(CustomerQcResultDetailCard, {
      props: {
        model: {
          isEnhanced: true,
          conclusion: '现有数据不足。',
          detail: '未取得可用于核对的主诉或第一诊断。',
          requirement: '',
          actualValue: '',
          evidenceSource: '入院记录',
          suggestion: '请补充资料。',
        },
      },
    })

    expect(wrapper.text()).not.toContain('规则要求')
    expect(wrapper.text()).not.toContain('实际值')
    expect(wrapper.text()).toContain('证据来源')
  })
})
