import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import DashboardView from './DashboardView.vue'

const requests = vi.hoisted(() => ({
  todo: vi.fn(),
  ranking: vi.fn(),
  task: vi.fn(),
  appeal: vi.fn(),
}))

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
  getTodoStats: requests.todo,
  getPerformanceRanking: requests.ranking,
}))
vi.mock('@/api/tasks', () => ({ getTaskTodoStats: requests.task }))
vi.mock('@/api/appeal', () => ({ getAppeals: requests.appeal }))

const todoProbe = defineComponent({
  props: { todoData: { type: Object, required: true } },
  setup(props) {
    return () => h('div', {
      'data-testid': 'todo-board',
      'data-todo': JSON.stringify(props.todoData),
    })
  },
})

const stubs = {
  QCTrendChart: { template: '<div data-testid="qc-trend-chart"></div>' },
  TodoBoard: todoProbe,
  PerformanceBoard: { template: '<div data-testid="perf-board"></div>' },
}

function boardData(wrapper: ReturnType<typeof mount>) {
  return JSON.parse(wrapper.get('[data-testid="todo-board"]').attributes('data-todo') || '{}')
}

describe('DashboardView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => ({ records: [] }) }))
    requests.todo.mockResolvedValue({ success: true, data: { overview: { total_records: 12, avg_score: 90, pass_rate: 80 } } })
    requests.ranking.mockResolvedValue({ success: true, data: {} })
    requests.task.mockResolvedValue({ success: true, data: { as_of: '2026-09-24T10:00:00Z', assigned: 0, in_progress: 0, due_soon: 0 } })
    requests.appeal.mockResolvedValue({ total: 0 })
  })

  afterEach(() => vi.unstubAllGlobals())

  it('应能稳定挂载并渲染页面主体', async () => {
    const wrapper = mount(DashboardView, {
      global: { stubs },
    })

    await flushPromises()
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.find('[data-testid="qc-trend-chart"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('应在默认场景下正常渲染快捷入口区域', async () => {
    const wrapper = mount(DashboardView, {
      global: { stubs },
    })

    await flushPromises()
    expect(wrapper.text()).toContain('上传病案')
    expect(wrapper.text()).toContain('智能质控')
    wrapper.unmount()
  })

  it('排名失败不遮蔽真实待办，刷新失败不保留旧计数', async () => {
    requests.ranking.mockRejectedValue(new Error('ranking unavailable'))
    requests.task.mockResolvedValueOnce({
      success: true,
      data: { as_of: '2026-09-24T10:00:00Z', assigned: 3, in_progress: 2, due_soon: 1 },
    }).mockResolvedValueOnce({ success: false, message: 'task unavailable' })
    requests.appeal.mockResolvedValueOnce({ total: 4 }).mockRejectedValueOnce(new Error('appeal unavailable'))

    const wrapper = mount(DashboardView, { global: { stubs } })
    await flushPromises()
    expect(boardData(wrapper)).toMatchObject({
      task_stats: { not_started: 3, in_progress: 2, countdown: 1, as_of: '2026-09-24T10:00:00Z' },
      defect_stats: { clinical_appeals: 4, pending_review: null },
      record_stats: { pending_review: null, pending_recheck: null },
    })

    const refresh = wrapper.findAll('button').find((button) => button.text().includes('刷新'))
    expect(refresh).toBeDefined()
    await refresh!.trigger('click')
    await flushPromises()
    expect(boardData(wrapper)).toMatchObject({
      task_stats: { not_started: null, in_progress: null, countdown: null },
      defect_stats: { clinical_appeals: null },
    })
    wrapper.unmount()
  })
})
