import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import DashboardView from './DashboardView.vue'
import type { DashboardStats } from '@/types/dashboard'

// Mock QCTrendChart component
vi.mock('@/components/charts/QCTrendChart.vue', () => ({
  default: {
    name: 'QCTrendChart',
    props: ['period', 'height', 'autoRefresh'],
    template: '<div data-testid="qc-trend-chart">Mock Chart</div>'
  }
}))

describe('DashboardView', () => {
  let wrapper: VueWrapper<any>

  const mockStats: DashboardStats = {
    totalRecords: 1247,
    pendingRecords: 23,
    analyzingRecords: 8,
    completedRecords: 1216,
    averageScore: 87.5,
    passRate: 94.2,
    todayUploads: 15,
    weeklyTrend: '+12.5%'
  }

  beforeEach(() => {
    vi.clearAllMocks()
    wrapper = mount(DashboardView, {
      global: {
        stubs: {
          'a-button': {
            template: '<button @click="$emit(\'click\')" :loading="loading"><slot /></button>',
            props: ['loading', 'type']
          },
          'a-select': {
            template: '<select @change="$emit(\'change\', $event.target.value)" :value="value"><slot /></select>',
            props: ['value', 'options']
          },
          'QCTrendChart': {
            template: '<div data-testid="qc-trend-chart">Mock Chart</div>',
            props: ['period', 'height', 'autoRefresh']
          }
        }
      }
    })
  })

  afterEach(() => {
    wrapper.unmount()
  })

  describe('组件初始化', () => {
    it('应该正确渲染组件', () => {
      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('[data-testid="dashboard-container"]').exists()).toBe(true)
    })

    it('应该显示用户问候语', () => {
      const greeting = wrapper.find('h1')
      expect(greeting.exists()).toBe(true)
      expect(greeting.text()).toContain('测试用户')
    })

    it('应该显示正确的统计数据', () => {
      const cards = wrapper.findAll('[data-testid="stat-card"]')
      expect(cards).toHaveLength(6)
      
      // 检查第一个卡片（总病案数）
      const firstCard = cards[0]
      expect(firstCard.text()).toContain('总病案数')
      expect(firstCard.text()).toContain('1,247')
    })
  })

  describe('统计卡片模块', () => {
    it('应该正确计算和显示统计数据', async () => {
      const vm = wrapper.vm
      expect(vm.stats.totalRecords).toBe(1247)
      expect(vm.stats.pendingRecords).toBe(23)
      expect(vm.stats.averageScore).toBe(87.5)
    })

    it('应该正确显示趋势指示器', () => {
      const trendIcons = wrapper.findAll('[data-testid="trend-icon"]')
      expect(trendIcons.length).toBeGreaterThan(0)
      
      // 检查趋势颜色
      const increaseTrend = wrapper.find('.text-green-500')
      expect(increaseTrend.exists()).toBe(true)
    })

    it('应该在悬浮时显示光晕效果', async () => {
      const card = wrapper.find('[data-testid="stat-card"]')
      await card.trigger('mouseenter')
      
      // 检查是否有悬浮效果类
      expect(card.classes()).toContain('group')
    })
  })

  describe('快捷操作模块', () => {
    it('应该渲染所有快捷操作按钮', () => {
      const actionButtons = wrapper.findAll('[data-testid="quick-action"]')
      expect(actionButtons).toHaveLength(4)
      
      const expectedActions = ['上传病案', '质控分析', '生成报告', '规则管理']
      actionButtons.forEach((button, index) => {
        expect(button.text()).toContain(expectedActions[index])
      })
    })

    it('应该正确处理快捷操作点击', async () => {
      const vm = wrapper.vm
      const handleQuickActionSpy = vi.spyOn(vm, 'handleQuickAction')
      
      const uploadButton = wrapper.find('[data-testid="quick-action-upload"]')
      await uploadButton.trigger('click')
      
      expect(handleQuickActionSpy).toHaveBeenCalledWith('upload')
    })
  })

  describe('质控趋势分析模块', () => {
    it('应该渲染图表组件', () => {
      const chart = wrapper.find('[data-testid="qc-trend-chart"]')
      expect(chart.exists()).toBe(true)
    })

    it('应该正确传递props给图表组件', () => {
      const chart = wrapper.findComponent({ name: 'QCTrendChart' })
      expect(chart.props('period')).toBe('month')
      expect(chart.props('height')).toBe(320)
      expect(chart.props('autoRefresh')).toBe(true)
    })

    it('应该响应时间段选择器变化', async () => {
      const vm = wrapper.vm
      const select = wrapper.find('[data-testid="period-select"]')
      
      await select.setValue('week')
      expect(vm.selectedPeriod).toBe('week')
    })
  })

  describe('数据刷新功能', () => {
    it('应该正确处理数据刷新', async () => {
      const vm = wrapper.vm
      const refreshButton = wrapper.find('[data-testid="refresh-button"]')
      
      expect(vm.refreshing).toBe(false)
      
      await refreshButton.trigger('click')
      expect(vm.refreshing).toBe(true)
      
      // 等待异步操作完成
      await new Promise(resolve => setTimeout(resolve, 1100))
      expect(vm.refreshing).toBe(false)
    })

    it('应该在刷新时显示加载状态', async () => {
      const vm = wrapper.vm
      vm.refreshing = true
      await nextTick()
      
      const refreshButton = wrapper.find('[data-testid="refresh-button"]')
      expect(refreshButton.attributes('loading')).toBeDefined()
    })
  })

  describe('响应式布局', () => {
    it('应该在不同屏幕尺寸下正确布局', () => {
      const container = wrapper.find('.grid')
      expect(container.classes()).toContain('grid-cols-1')
      expect(container.classes()).toContain('xl:grid-cols-6')
    })
  })

  describe('工具函数', () => {
    it('getGreeting应该根据时间返回正确问候语', () => {
      const vm = wrapper.vm
      
      // Mock不同时间
      vi.setSystemTime(new Date('2024-01-01 09:00:00'))
      expect(vm.getGreeting()).toBe('早上好')
      
      vi.setSystemTime(new Date('2024-01-01 14:00:00'))
      expect(vm.getGreeting()).toBe('下午好')
      
      vi.setSystemTime(new Date('2024-01-01 20:00:00'))
      expect(vm.getGreeting()).toBe('晚上好')
    })

    it('getTrendClass应该返回正确的CSS类', () => {
      const vm = wrapper.vm
      expect(vm.getTrendClass('increase')).toBe('text-green-500')
      expect(vm.getTrendClass('decrease')).toBe('text-red-500')
    })

    it('getTrendIcon应该返回正确的图标组件', () => {
      const vm = wrapper.vm
      expect(vm.getTrendIcon('increase')).toBeDefined()
      expect(vm.getTrendIcon('decrease')).toBeDefined()
    })
  })
})
