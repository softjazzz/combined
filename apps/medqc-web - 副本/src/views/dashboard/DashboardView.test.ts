import { describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DashboardView from './DashboardView.vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {} }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: {
      display_name: '测试用户',
      email: 'tester@medqc.com',
    },
  }),
}))

vi.mock('@/api/dashboard', () => ({
  getTodoStats: vi.fn().mockResolvedValue({ success: true, data: {} }),
  getPerformanceRanking: vi.fn().mockResolvedValue({ success: true, data: {} }),
}))

describe('DashboardView', () => {
  it('应能稳定挂载并渲染页面主体', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        stubs: {
          QCTrendChart: { template: '<div data-testid="qc-trend-chart"></div>' },
          TodoBoard: { template: '<div data-testid="todo-board"></div>' },
          PerformanceBoard: { template: '<div data-testid="perf-board"></div>' },
        },
      },
    })

    await flushPromises()
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('[data-testid="qc-trend-chart"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('应在默认场景下正常渲染快捷入口区域', async () => {
    const wrapper = mount(DashboardView, {
      global: {
        stubs: {
          QCTrendChart: { template: '<div />' },
          TodoBoard: { template: '<div />' },
          PerformanceBoard: { template: '<div />' },
        },
      },
    })

    await flushPromises()
    expect(wrapper.text()).toContain('上传病案')
    expect(wrapper.text()).toContain('智能质控')
    wrapper.unmount()
  })
})
