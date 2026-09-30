import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SemanticRulesTableSection from '@/views/workstation-v4/semantic-rules/components/SemanticRulesTableSection.vue'
import type { SemanticRuleItem } from '@/views/workstation-v4/semantic-rules/types'

const ProQueryBarStub = {
  template: `
    <div class="query-bar-stub">
      <slot name="filters" />
      <slot name="actions" />
    </div>
  `,
}

const ProStandardTableStub = {
  props: {
    columns: {
      type: Array,
      default: () => [],
    },
    dataSource: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['change'],
  template: `
    <div class="table-stub">
      <template v-for="column in columns" :key="column.key">
        <slot
          name="bodyCell"
          :column="column"
          :record="(dataSource && dataSource[0]) || {}"
          :index="0"
        />
      </template>
    </div>
  `,
}

describe('SemanticRulesTableSection', () => {
  it('行级操作应保持“查看结果”主按钮和“评估”次按钮', () => {
    const demoRule: SemanticRuleItem = {
      rule_id: 'SC-001',
      rule_code: 'SC-001',
      name: '入院记录完成时效性检查',
      description: '入院记录应在患者入院后 24 小时内完成',
      category: '入院记录',
      complexity: '低复杂度',
      defect_level: '严重缺陷',
      score_deduction: 3,
      applicable_documents: ['admission_record'],
      medical_domain: '通用',
      requires_rag: false,
      requires_cot: false,
    }

    const wrapper = mount(SemanticRulesTableSection, {
      props: {
        loading: false,
        rules: [demoRule],
        total: 1,
        ruleSetKey: '',
        ruleSetOptions: [
          {
            rule_set_key: '',
            rule_set_name: 'SC 全病历质控规则',
            rule_set_version: '当前版本',
            scope: 'all',
            rule_ids: [],
            rule_count: 1,
          },
        ],
        keywordInput: '',
        complexity: '',
        defectLevel: '',
        documentType: '',
        complexityOptions: ['低复杂度', '中复杂度'],
        defectOptions: ['严重缺陷', '一般缺陷'],
        documentOptions: ['admission_record'],
        pagination: {
          current: 1,
          pageSize: 20,
          total: 1,
        },
      },
      global: {
        stubs: {
          ProQueryBar: ProQueryBarStub,
          ProStandardTable: ProStandardTableStub,
          SearchOutlined: {
            template: '<span class="icon-search" />',
          },
          'a-button': {
            template: '<button><slot /></button>',
          },
          'a-input': {
            template: '<input />',
          },
          'a-select': {
            template: '<select><slot /></select>',
          },
          'a-select-option': {
            template: '<option><slot /></option>',
          },
        },
      },
    })

    const actionsText = wrapper.find('.rule-inline-actions').text()
    expect(actionsText).toContain('查看结果')
    expect(actionsText).toContain('评估')
    expect(wrapper.text()).toContain('开始质控评估')
    expect(wrapper.text()).toContain('自定义规则工作台')
  })

  it('泸县规则列表应与 SC 规则保持相同的简洁信息层级', () => {
    const wrapper = mount(SemanticRulesTableSection, {
      props: {
        loading: false,
        rules: [
          {
            rule_id: 'LX0609-01-01-01',
            rule_code: 'LX0609-01-01-01',
            name: '入院记录：入院后24小时内是否完成',
            description: '入院记录时效性核对',
            category: '入院记录',
            complexity: '低复杂度',
            defect_level: '严重缺陷',
            score_deduction: 3,
            applicable_documents: ['admission_record'],
            medical_domain: '通用',
            requires_rag: false,
            requires_cot: false,
            implementation_status: 'ready',
            dependency_type: 'single_document',
            data_status: 'data_pending',
            primary_execution_rule_id: 'SC-002',
            mapped_rule_ids: ['SC-002'],
          },
        ],
        total: 1,
        ruleSetKey: 'luxian_0609_qc_v1',
        ruleSetOptions: [],
        keywordInput: '',
        complexity: '',
        defectLevel: '',
        documentType: '',
        complexityOptions: [],
        defectOptions: [],
        documentOptions: [],
        pagination: { current: 1, pageSize: 20, total: 1 },
      },
      global: {
        stubs: {
          ProQueryBar: ProQueryBarStub,
          ProStandardTable: ProStandardTableStub,
          'a-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
        },
      },
    })

    expect(wrapper.text()).toContain('LX0609-01-01-01')
    expect(wrapper.text()).toContain('入院记录：入院后24小时内是否完成')
    expect(wrapper.text()).not.toContain('可执行')
    expect(wrapper.text()).not.toContain('单文书')
    expect(wrapper.text()).not.toContain('数据待补')
    expect(wrapper.text()).not.toContain('主执行 SC-002')
    expect(wrapper.text()).not.toContain('映射规则：SC-002')
  })

  function mountLuxian(rule: Partial<SemanticRuleItem>) {
    return mount(SemanticRulesTableSection, {
      props: {
        loading: false,
        rules: [
          {
            rule_id: 'LX0609-06-01-01',
            rule_code: 'LX0609-06-01-01',
            name: '医嘱与病程一致性',
            description: '',
            category: 'CT/MRI检查记录',
            complexity: '中复杂度',
            defect_level: '一般缺陷',
            score_deduction: 1,
            applicable_documents: ['exam_report'],
            medical_domain: '通用',
            requires_rag: false,
            requires_cot: false,
            ...rule,
          },
        ],
        total: 1,
        ruleSetKey: 'luxian_0609_qc_v1',
        ruleSetOptions: [],
        keywordInput: '',
        complexity: '',
        defectLevel: '',
        documentType: '',
        releaseScope: '',
        complexityOptions: [],
        defectOptions: [],
        documentOptions: [],
        pagination: { current: 1, pageSize: 20, total: 1 },
      },
      global: {
        stubs: {
          ProQueryBar: ProQueryBarStub,
          ProStandardTable: ProStandardTableStub,
          RouterLink: { props: ['to'], template: '<a :data-to="JSON.stringify(to)"><slot /></a>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
        },
      },
    })
  }

  it('泸县待验收规则显示“待验收”并可跳转到规则验收详情', () => {
    const wrapper = mountLuxian({ release_scope: 'acceptance_only' })
    expect(wrapper.find('[data-testid="release-scope"]').text()).toBe('待验收')
    expect(wrapper.find('select[aria-label="发布范围"]').exists()).toBe(true)
    const link = wrapper.find('[data-testid="go-rule-validation"]')
    expect(link.text()).toBe('去验收')
    expect(JSON.parse(link.attributes('data-to')!)).toEqual({
      name: 'WorkstationV4RuleValidationDetail',
      params: { ruleId: 'LX0609-06-01-01' },
    })
  })

  it('已上线规则显示“已上线”，不提供去验收入口；无发布范围的规则集不显示该列', () => {
    const released = mountLuxian({ release_scope: 'default' })
    expect(released.find('[data-testid="release-scope"]').text()).toBe('已上线')
    expect(released.find('[data-testid="go-rule-validation"]').exists()).toBe(false)

    const sc = mountLuxian({ rule_id: 'SC-001', rule_code: 'SC-001', release_scope: undefined })
    expect(sc.find('[data-testid="release-scope"]').exists()).toBe(false)
    expect(sc.find('select[aria-label="发布范围"]').exists()).toBe(false)
  })
})
