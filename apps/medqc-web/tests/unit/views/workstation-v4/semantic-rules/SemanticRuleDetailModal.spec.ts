import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SemanticRuleDetailModal from '@/views/workstation-v4/semantic-rules/components/modals/SemanticRuleDetailModal.vue'
import type { SemanticRuleItem } from '@/views/workstation-v4/semantic-rules/types'

const modalStubs = {
  'a-modal': { template: '<section class="modal-stub"><slot /></section>' },
  'a-descriptions': { template: '<section><slot /></section>' },
  'a-descriptions-item': {
    props: { label: { type: String, default: '' } },
    template: '<div><span>{{ label }}</span><slot /></div>',
  },
  'a-button': { template: '<button><slot /></button>' },
  'a-textarea': { template: '<textarea />' },
}

function makeRule(overrides: Partial<SemanticRuleItem> = {}): SemanticRuleItem {
  return {
    rule_id: 'LX0609-03-01-01',
    rule_code: 'LX0609-03-01-01',
    name: '会诊意见及执行情况记录',
    description: '旧包装器描述，不得展示给客户。',
    category: '会诊记录',
    complexity: '中复杂度',
    defect_level: '一般缺陷',
    score_deduction: 2,
    applicable_documents: ['consultation_record'],
    medical_domain: '通用',
    requires_rag: false,
    requires_cot: false,
    customer_text: '旧客户说明，不得展示给客户。',
    trigger_condition: '旧触发条件，不得展示。',
    non_trigger_condition: '旧不触发条件，不得展示。',
    dependency_type: 'cross_document',
    data_status: 'ready',
    implementation_status: 'formal_ready',
    positive_example: {
      title: '旧正例，不得展示。',
      summary: '旧正例摘要。',
      sections: [],
    },
    negative_example: {
      title: '旧反例，不得展示。',
      summary: '旧反例摘要。',
      sections: [],
    },
    primary_execution_rule_id: 'SC-020',
    mapped_rule_ids: ['SC-020', 'CL-020'],
    customer_policy: {
      source_document: '后续病程记录',
      qc_point: '会诊意见及执行情况记录',
      summary: '资料完整但后续病程未记录会诊意见及具体执行情况时，判定不合规。',
      sources: ['sichuan_2023_standard', 'customer_confirmed', 'unrecognized_source'],
    },
    ...overrides,
  }
}

function mountDetail(rule: SemanticRuleItem) {
  return mount(SemanticRuleDetailModal, {
    props: {
      open: true,
      rule,
      isAdmin: true,
      promptLoading: false,
      isEditingPrompt: false,
      currentPrompt: '旧只读模板，不得展示。',
      editingPrompt: '',
    },
    global: { stubs: modalStubs },
  })
}

describe('SemanticRuleDetailModal', () => {
  it('LX详情只展示总表客户政策，并将执行映射降为辅助信息', () => {
    const wrapper = mountDetail(makeRule())
    const text = wrapper.text()

    expect(text).toContain('后续病程记录：会诊意见及执行情况记录')
    expect(text).toContain('资料完整但后续病程未记录会诊意见及具体执行情况时，判定不合规。')
    expect(text).toContain('四川省住院病历评定标准')
    expect(text).toContain('客户确认口径')
    expect(text).toContain('未识别政策来源')
    expect(text).toContain('执行映射（实现信息）')
    expect(text).toContain('SC-020 · 主执行')
    expect(text).toContain('CL-020')

    expect(text).not.toContain('旧包装器描述，不得展示给客户。')
    expect(text).not.toContain('旧客户说明，不得展示给客户。')
    expect(text).not.toContain('旧触发条件，不得展示。')
    expect(text).not.toContain('旧不触发条件，不得展示。')
    expect(text).not.toContain('旧正例，不得展示。')
    expect(text).not.toContain('旧反例，不得展示。')
    expect(text).not.toContain('旧只读模板，不得展示。')
    expect(text).not.toContain('执行依赖')
    expect(text).not.toContain('数据状态')
    expect(text).not.toContain('分类')
    expect(text).not.toContain('复杂度')
    expect(text).not.toContain('缺陷级别')
    expect(text).not.toContain('扣分')
    expect(text).not.toContain('适用文书')
  })

  it('LX规则缺少完整政策对象时不回退旧客户说明', () => {
    const wrapper = mountDetail(makeRule({ customer_policy: undefined }))
    const text = wrapper.text()

    expect(text).toContain('规则口径暂未同步')
    expect(text).not.toContain('旧客户说明，不得展示给客户。')
    expect(text).not.toContain('旧包装器描述，不得展示给客户。')
  })

  it('SC规则保留既有标题、描述和管理员模板展示', () => {
    const wrapper = mountDetail(
      makeRule({
        rule_id: 'SC-020',
        rule_code: 'SC-020',
        name: 'SC会诊记录检查',
        description: 'SC既有规则说明。',
        customer_policy: undefined,
      }),
    )
    const text = wrapper.text()

    expect(text).toContain('SC会诊记录检查')
    expect(text).toContain('SC既有规则说明。')
    expect(text).toContain('分类')
    expect(text).toContain('复杂度')
    expect(text).toContain('缺陷级别')
    expect(text).toContain('扣分')
    expect(text).toContain('适用文书')
    expect(text).toContain('检查模板管理')
    expect(text).toContain('旧只读模板，不得展示。')
    expect(text).not.toContain('客户规则口径')
  })
})
