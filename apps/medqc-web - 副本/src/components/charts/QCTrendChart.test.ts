import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import QCTrendChart from './QCTrendChart.vue'

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    template: '<div class="mock-v-chart" />',
    props: ['option', 'autoresize'],
  },
}))

describe('QCTrendChart', () => {
  it('应正常渲染图表容器', () => {
    const wrapper = mount(QCTrendChart, {
      props: { period: 'month' },
    })
    expect(wrapper.find('.chart').exists()).toBe(true)
    expect(wrapper.find('.mock-v-chart').exists()).toBe(true)
    wrapper.unmount()
  })

  it('应传递 autoresize=true 给图表组件', () => {
    const wrapper = mount(QCTrendChart, {
      props: { period: 'month' },
    })
    const chart = wrapper.findComponent({ name: 'VChart' })
    expect(chart.exists()).toBe(true)
    expect(chart.props('autoresize')).toBe(true)
    wrapper.unmount()
  })

  it('应接收 period/height/autoRefresh props 并保持组件可渲染', () => {
    const wrapper = mount(QCTrendChart, {
      props: {
        period: 'week',
        height: 420,
        autoRefresh: true,
      },
    })
    expect(wrapper.find('.chart').exists()).toBe(true)
    wrapper.unmount()
  })
})
