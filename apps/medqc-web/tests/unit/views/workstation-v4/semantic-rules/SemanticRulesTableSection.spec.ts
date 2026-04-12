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

    const actionsText = wrapper.find('.table-actions').text()
    expect(actionsText).toContain('查看结果')
    expect(actionsText).toContain('评估')
    expect(wrapper.text()).toContain('开始质控评估')
    expect(wrapper.text()).toContain('自定义规则工作台')
  })
})
