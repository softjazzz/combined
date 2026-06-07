import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SemanticRulesOverviewPanels from '@/views/workstation-v4/semantic-rules/components/SemanticRulesOverviewPanels.vue'

describe('SemanticRulesOverviewPanels', () => {
  it('应仅渲染双栏分析并保留总览右上三操作', () => {
    const wrapper = mount(SemanticRulesOverviewPanels, {
      props: {
        loading: false,
        kpiCards: [
          { key: 'total', label: '总规则', value: '179', desc: '规则总量', tone: 'brand' },
          { key: 'critical', label: '严重缺陷', value: '76', desc: '高风险规则', tone: 'danger' },
          {
            key: 'density',
            label: '风险密度',
            value: '42%',
            desc: '严重缺陷占比',
            tone: 'warning',
          },
          { key: 'sync', label: '最近同步', value: '18:34', desc: '数据更新时间', tone: 'safe' },
        ],
        criticalDefectCount: 76,
        majorDefectCount: 84,
        minorDefectCount: 19,
        riskDensity: '42%',
        topCategories: [
          { name: '病程记录', count: 67 },
          { name: '手术相关记录', count: 36 },
          { name: '入院记录', count: 29 },
        ],
        getDefectRate: (count: number) => count,
        getCategoryRatio: (count: number) => `${count}%`,
      },
      global: {
        stubs: {
          'a-button': {
            template: '<button><slot /></button>',
          },
        },
      },
    })

    expect(wrapper.findAll('.analysis-panel')).toHaveLength(2)
    expect(wrapper.text()).toContain('风险分布')
    expect(wrapper.text()).toContain('分类覆盖 Top3')
    expect(wrapper.text()).not.toContain('规则复杂度结构')

    const overviewActions = wrapper.findAll('.overview-actions button').map((node) => node.text())
    expect(overviewActions).toEqual(['查询', '重置', '刷新'])
  })
})
