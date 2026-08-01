import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import LuxianRuleScopePanel from '@/views/workstation-v4/customer-sample-validation/LuxianRuleScopePanel.vue'

const families = [
  {
    key: 'basic_timeliness',
    name: '基础时限',
    description: '覆盖入院、首次病程等时限要求。',
    ruleIds: ['LX0609-001', 'LX0609-002'],
    rules: [
      {
        ruleId: 'LX0609-001',
        name: '入院记录时限',
        description: '入院后24小时内完成',
        requiredDocumentsLabel: '入院记录',
      },
      {
        ruleId: 'LX0609-002',
        name: '首次病程时限',
        description: '入院后8小时内完成',
        requiredDocumentsLabel: '首次病程记录',
      },
    ],
  },
  {
    key: 'consultation_quality',
    name: '会诊质量',
    description: '覆盖会诊申请和执行记录。',
    ruleIds: ['LX0609-020'],
    rules: [
      {
        ruleId: 'LX0609-020',
        name: '会诊执行记录',
        description: '会诊后记录执行情况',
        requiredDocumentsLabel: '会诊记录',
      },
    ],
  },
]

const stubs = {
  'a-button': {
    template: '<button><slot /></button>',
    props: ['size'],
  },
}

function mountPanel(overrides: Partial<InstanceType<typeof LuxianRuleScopePanel>['$props']> = {}) {
  return mount(LuxianRuleScopePanel, {
    attrs: {
      id: 'customer-sample-luxian-scope',
      'data-customer-guide': 'lx0609-scope',
      class: 'is-guide-active',
    },
    props: {
      families,
      selectedRuleIds: ['LX0609-001'],
      expandedFamilyKeys: ['basic_timeliness'],
      helperText: '已限定本次质控范围。',
      modeText: '当前将运行：1 个质控族 · 1 个质控点',
      allRuleIds: ['LX0609-001', 'LX0609-002', 'LX0609-020'],
      selectedFamilyCount: 1,
      allRulesSelected: false,
      ...overrides,
    },
    global: { stubs },
  })
}

describe('LuxianRuleScopePanel', () => {
  it('原样展示质控范围、选择统计和展开规则', () => {
    const wrapper = mountPanel()

    expect(wrapper.attributes('id')).toBe('customer-sample-luxian-scope')
    expect(wrapper.attributes('data-customer-guide')).toBe('lx0609-scope')
    expect(wrapper.classes()).toContain('is-guide-active')
    expect(wrapper.text()).toContain('泸县0609质控点范围')
    expect(wrapper.text()).toContain('已限定本次质控范围。')
    expect(wrapper.text()).toContain('当前将运行：1 个质控族 · 1 个质控点')
    expect(wrapper.text()).toContain('2 个质控族')
    expect(wrapper.text()).toContain('3 个质控点')
    expect(wrapper.text()).toContain('1 个质控族已选')
    expect(wrapper.text()).toContain('1 个质控点将运行')
    expect(wrapper.text()).toContain('已选 1/2')
    expect(wrapper.find('input.luxian-rule-checkbox[value="LX0609-001"]').exists()).toBe(true)
    expect(wrapper.find('input.luxian-rule-checkbox[value="LX0609-020"]').exists()).toBe(false)
  })

  it('只通过事件把选择和展开操作交给父页面', async () => {
    const wrapper = mountPanel()
    const basicFamily = wrapper
      .findAll('.customer-sample-luxian-rule-group')
      .find((node) => node.text().includes('基础时限'))!
    const consultationFamily = wrapper
      .findAll('.customer-sample-luxian-rule-group')
      .find((node) => node.text().includes('会诊质量'))!

    await wrapper
      .findAll('button')
      .find((node) => node.text() === '全选2个质控族')!
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '清空勾选')!
      .trigger('click')
    await basicFamily
      .findAll('button')
      .find((node) => node.text() === '选择本组')!
      .trigger('click')
    await consultationFamily
      .findAll('button')
      .find((node) => node.text() === '查看质控点')!
      .trigger('click')
    await basicFamily.get('input[value="LX0609-002"]').setValue(true)

    expect(wrapper.emitted('select-all')).toHaveLength(1)
    expect(wrapper.emitted('clear')).toHaveLength(1)
    expect(wrapper.emitted('toggle-family')).toEqual([[['LX0609-001', 'LX0609-002']]])
    expect(wrapper.emitted('toggle-expanded')).toEqual([['consultation_quality']])
    expect(wrapper.emitted('toggle-rule')).toEqual([['LX0609-002']])
  })

  it('全选状态保留原有取消文案，并以全量作为运行数量', () => {
    const wrapper = mountPanel({
      selectedRuleIds: ['LX0609-001', 'LX0609-002', 'LX0609-020'],
      selectedFamilyCount: 2,
      allRulesSelected: true,
      modeText: '当前将运行：全部 3 个质控点',
    })

    expect(wrapper.text()).toContain('当前将运行：全部 3 个质控点')
    expect(wrapper.text()).toContain('取消全部勾选')
    expect(wrapper.text()).not.toContain('清空勾选')
    expect(wrapper.text()).toContain('3 个质控点将运行')
  })
})
