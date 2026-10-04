import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { BusinessAgentChart } from '@/api/businessAgent'
import BusinessAgentChartView from '@/views/workstation-v4/components/BusinessAgentChart.vue'
import {
  axisMax,
  buildLine,
  chartLabel,
  numericCount,
} from '@/views/workstation-v4/components/businessAgentChart'

const line = (values: (number | null)[]): BusinessAgentChart => ({
  type: 'line',
  metric: '不合规规则结果条数',
  unit: '条',
  points: values.map((value, index) => ({ label: `${index + 7}月`, value })),
  caption: '各期为原值，不计算变化。',
})

const ranking: BusinessAgentChart = {
  type: 'bar',
  metric: '不合规次数',
  unit: '次',
  points: [
    { label: '入院后24小时内是否完成', value: 31, rule_id: 'R1' },
    { label: '手术记录24小时内完成', value: 24, rule_id: 'R2' },
  ],
  caption: '按正式不合规次数降序展示前 5 条规则，不计算占比。',
}

describe('助手图表', () => {
  it('纵轴上限只取整齐刻度，缺失值处断开折线且不补零', () => {
    expect(axisMax([])).toBe(5)
    expect(axisMax([42, 38])).toBe(50)
    const geometry = buildLine(line([42, null, 24, 30]))
    expect(geometry.points.map((point) => point.y === null)).toEqual([false, true, false, false])
    // 中间缺失：第一个点单独成段不画线，后两点连成一条。
    expect(geometry.segments).toHaveLength(1)
    expect(numericCount(line([42, null, 24]))).toBe(2)
  })

  it('折线图为带文字说明的图形，标出每期原值和最后一期', () => {
    const wrapper = mount(BusinessAgentChartView, { props: { chart: line([42, 38, 24]) } })
    const svg = wrapper.get('svg')
    expect(svg.attributes('role')).toBe('img')
    expect(svg.attributes('aria-label')).toBe(chartLabel(line([42, 38, 24])))
    expect(wrapper.text()).toContain('42')
    expect(wrapper.text()).toContain('24')
    expect(wrapper.findAll('circle')).toHaveLength(3)
    expect(wrapper.text()).toContain('不计算变化')
  })

  it('只有一个期间时不画趋势，只显示数值和说明', () => {
    const wrapper = mount(BusinessAgentChartView, { props: { chart: line([24, null]) } })
    expect(wrapper.find('svg').exists()).toBe(false)
    expect(wrapper.get('[data-testid="business-agent-chart-single"]').text()).toContain(
      '无法绘制趋势',
    )
    expect(wrapper.text()).toContain('24')
    expect(wrapper.text()).toContain('其余 1 个期间没有可显示的数据')
  })

  it('各期都没有数据时明确不按 0 处理', () => {
    const wrapper = mount(BusinessAgentChartView, { props: { chart: line([null, null]) } })
    expect(wrapper.text()).toContain('不按 0 处理')
  })

  it('排行用条形展示名称、次数和单位，不显示占比', () => {
    const wrapper = mount(BusinessAgentChartView, { props: { chart: ranking } })
    expect(wrapper.text()).toContain('入院后24小时内是否完成')
    expect(wrapper.text()).toContain('31')
    expect(wrapper.text()).not.toContain('%')
    const widths = wrapper.findAll('.bac__fill').map((node) => node.attributes('style'))
    expect(widths[0]).toContain('100%')
  })

  it('点击“数据”切换为与图一致的表格，缺失值显示未提供', async () => {
    const wrapper = mount(BusinessAgentChartView, { props: { chart: line([42, null, 24]) } })
    await wrapper.get('[data-testid="business-agent-chart-table-toggle"]').trigger('click')
    const table = wrapper.get('[data-testid="business-agent-chart-table"]')
    expect(table.text()).toContain('7月')
    expect(table.text()).toContain('42')
    expect(table.text()).toContain('未提供')
    expect(wrapper.find('svg').exists()).toBe(false)
  })
})
