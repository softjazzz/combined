import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { useRoute } from 'vue-router'
import DashboardView from './DashboardView.vue'
import type { PerformanceData } from '@/api/dashboard'

const requests = vi.hoisted(() => ({
  todo: vi.fn(),
  ranking: vi.fn(),
  task: vi.fn(),
  appeal: vi.fn(),
}))

vi.mock('vue-router', async () => {
  const { reactive } = await vi.importActual<typeof import('vue')>('vue')
  const route = reactive({ query: {} as Record<string, string> })
  return {
    useRouter: () => ({ push: vi.fn() }),
    useRoute: () => route,
  }
})

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

const perfProbe = defineComponent({
  name: 'PerformanceBoard',
  props: {
    period: { type: String, required: true },
    status: { type: String, required: true },
    data: { type: Object, default: null },
    errorMessage: { type: String, default: '' },
  },
  emits: ['period-change', 'retry'],
  setup(props) {
    return () => h('div', {
      'data-testid': 'perf-board',
      'data-period': props.period,
      'data-status': props.status,
      'data-perf': JSON.stringify(props.data),
    })
  },
})

const stubs = {
  QCTrendChart: { template: '<div data-testid="qc-trend-chart"></div>' },
  TodoBoard: todoProbe,
  PerformanceBoard: perfProbe,
}

function perfData(period: PerformanceData['period'], count: number, scene: PerformanceData['scene'] = 'all'): PerformanceData {
  return {
    period,
    period_label: period,
    range: { start: '2026-09-21T00:00:00+08:00', end: '2026-09-27T12:00:00+08:00' },
    scene,
    defect_ranking: [{ user_id: 'u1', name: null, count, approved_count: 0, rejected_count: 0, rank: 1 }],
    record_ranking: [],
    unavailable_reason: null,
  }
}

function perfState(wrapper: ReturnType<typeof mount>) {
  const board = wrapper.get('[data-testid="perf-board"]')
  return {
    period: board.attributes('data-period'),
    status: board.attributes('data-status'),
    data: JSON.parse(board.attributes('data-perf') || 'null') as PerformanceData | null,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => { resolve = r })
  return { promise, resolve }
}

function boardData(wrapper: ReturnType<typeof mount>) {
  return JSON.parse(wrapper.get('[data-testid="todo-board"]').attributes('data-todo') || '{}')
}

describe('DashboardView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ json: async () => ({ records: [] }) }))
    requests.todo.mockResolvedValue({ success: true, data: { overview: { total_records: 12, avg_score: 90, pass_rate: 80 } } })
    ;(useRoute() as unknown as { query: Record<string, string> }).query = {}
    requests.ranking.mockResolvedValue({ success: true, data: perfData('this_week', 1) })
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

  it('透传服务端审核待办精确计数，非法值保持 null 而非 0', async () => {
    requests.todo.mockResolvedValueOnce({ success: true, data: {
      overview: { total_records: 12, avg_score: 90, pass_rate: 80 },
      defect_stats: { clinical_appeals: null, pending_review: 3, urged: null },
      record_stats: { pending_review: 2, pending_recheck: -1, total: 12 },
    } })
    const wrapper = mount(DashboardView, { global: { stubs } })
    await flushPromises()
    expect(boardData(wrapper)).toMatchObject({
      defect_stats: { pending_review: 3 },
      record_stats: { pending_review: 2, pending_recheck: null },
    })
    expect(wrapper.get('[data-testid="todo-board"]').attributes('scene')).toBe('all')
    wrapper.unmount()
  })

  it('周期切换按所选 period 与当前场景请求排名', async () => {
    const wrapper = mount(DashboardView, { global: { stubs } })
    await flushPromises()
    expect(requests.ranking).toHaveBeenLastCalledWith('this_week', 'all')
    requests.ranking.mockResolvedValueOnce({ success: true, data: perfData('last_week', 4) })
    wrapper.findComponent(perfProbe).vm.$emit('period-change', 'last_week')
    await flushPromises()
    expect(requests.ranking).toHaveBeenLastCalledWith('last_week', 'all')
    expect(perfState(wrapper)).toMatchObject({ period: 'last_week', status: 'ready' })
    expect(perfState(wrapper).data?.defect_ranking?.[0].count).toBe(4)
    wrapper.unmount()
  })

  it('排名请求失败显示错误态且不保留旧数据，重试后恢复', async () => {
    const wrapper = mount(DashboardView, { global: { stubs } })
    await flushPromises()
    requests.ranking.mockResolvedValueOnce({ success: false, message: '服务暂不可用' })
    wrapper.findComponent(perfProbe).vm.$emit('period-change', 'this_month')
    await flushPromises()
    expect(perfState(wrapper)).toMatchObject({ status: 'error', data: null })
    expect(wrapper.findComponent(perfProbe).props('errorMessage')).toBe('服务暂不可用')

    requests.ranking.mockResolvedValueOnce({ success: true, data: perfData('this_month', 8) })
    wrapper.findComponent(perfProbe).vm.$emit('retry')
    await flushPromises()
    expect(requests.ranking).toHaveBeenLastCalledWith('this_month', 'all')
    expect(perfState(wrapper).status).toBe('ready')
    expect(perfState(wrapper).data?.defect_ranking?.[0].count).toBe(8)
    wrapper.unmount()
  })

  it('请求抛出异常时同样进入错误态', async () => {
    requests.ranking.mockRejectedValue(new Error('network'))
    const wrapper = mount(DashboardView, { global: { stubs } })
    await flushPromises()
    expect(perfState(wrapper)).toMatchObject({ status: 'error', data: null })
    wrapper.unmount()
  })

  it('切换周期后丢弃迟到的旧周期响应', async () => {
    const wrapper = mount(DashboardView, { global: { stubs } })
    await flushPromises()
    const slow = deferred<{ success: boolean; data: PerformanceData }>()
    const fast = deferred<{ success: boolean; data: PerformanceData }>()
    requests.ranking.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)
    const board = wrapper.findComponent(perfProbe)
    board.vm.$emit('period-change', 'last_week')
    board.vm.$emit('period-change', 'this_month')
    fast.resolve({ success: true, data: perfData('this_month', 30) })
    await flushPromises()
    slow.resolve({ success: true, data: perfData('last_week', 99) })
    await flushPromises()
    expect(perfState(wrapper)).toMatchObject({ period: 'this_month', status: 'ready' })
    expect(perfState(wrapper).data?.defect_ranking?.[0].count).toBe(30)
    wrapper.unmount()
  })

  it('切换场景后丢弃迟到的旧场景响应', async () => {
    const slow = deferred<{ success: boolean; data: PerformanceData }>()
    requests.ranking.mockReturnValueOnce(slow.promise)
    const wrapper = mount(DashboardView, { global: { stubs } })
    await flushPromises()
    // 首屏排名尚未返回时页面已完成加载，场景切换触发新请求
    const route = useRoute() as unknown as { query: Record<string, string> }
    requests.ranking.mockResolvedValueOnce({ success: true, data: {
      ...perfData('this_week', 0, 'running'),
      defect_ranking: null,
      record_ranking: null,
      unavailable_reason: 'scene_not_attributable',
    } })
    route.query = { scene: 'running' }
    await flushPromises()
    expect(requests.ranking).toHaveBeenLastCalledWith('this_week', 'running')
    slow.resolve({ success: true, data: perfData('this_week', 77) })
    await flushPromises()
    expect(perfState(wrapper).data).toMatchObject({ scene: 'running', defect_ranking: null, unavailable_reason: 'scene_not_attributable' })
    wrapper.unmount()
  })
})
