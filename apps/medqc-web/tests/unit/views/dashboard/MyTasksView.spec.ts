import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getTaskList: vi.fn(),
  getTaskStats: vi.fn(),
  getTaskDetail: vi.fn(),
  getTaskProgress: vi.fn(),
  updateTask: vi.fn(),
  routerPush: vi.fn(),
  message: {
    error: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@/api/tasks', () => ({
  getTaskList: mocks.getTaskList,
  getTaskStats: mocks.getTaskStats,
  getTaskDetail: mocks.getTaskDetail,
  getTaskProgress: mocks.getTaskProgress,
  updateTask: mocks.updateTask,
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.routerPush }) }))
vi.mock('ant-design-vue', () => ({ message: mocks.message }))
vi.mock('@ant-design/icons-vue', () => {
  const icon = { template: '<span />' }
  return {
    BarChartOutlined: icon,
    CheckCircleOutlined: icon,
    ClockCircleOutlined: icon,
    EditOutlined: icon,
    EyeOutlined: icon,
    FilterOutlined: icon,
    PlayCircleOutlined: icon,
    ReloadOutlined: icon,
    SyncOutlined: icon,
    TrophyOutlined: icon,
  }
})

import MyTasksView from '@/views/dashboard/tasks/MyTasksView.vue'

const AButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.())
  },
})

const listResponse = {
  success: true,
  data: { items: [], total: 0, page: 1, page_size: 10, total_pages: 0 },
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve
  })
  return { promise, resolve }
}

function statsResponse(overrides: Record<string, unknown> = {}) {
  return {
    success: true,
    data: {
      total: 12,
      by_status: { assigned: 3, in_progress: 1, completed: 4 },
      draft: 8,
      in_progress: 1,
      completed: 4,
      cancelled: 0,
      ...overrides,
    },
  }
}

async function mountView() {
  const wrapper = shallowMount(MyTasksView, {
    global: {
      stubs: {
        'a-button': AButtonStub,
        'a-drawer': true,
        'a-input-search': true,
        'a-progress': true,
        'a-range-picker': true,
        'a-select': true,
        'a-tag': true,
        ProQueryBar: { template: '<div><slot name="filters"/><slot name="actions"/></div>' },
        ProStandardTable: true,
        ProTableToolbar: { template: '<div><slot/></div>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('MyTasksView 我的任务口径', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getTaskList.mockResolvedValue(listResponse)
    mocks.getTaskStats.mockResolvedValue(statsResponse())
  })

  it('统计与列表都请求 received，待处理展示 assigned 而非 draft', async () => {
    const wrapper = await mountView()

    expect(mocks.getTaskList).toHaveBeenCalledWith(expect.objectContaining({ tab: 'received' }))
    expect(mocks.getTaskStats).toHaveBeenCalledWith({ tab: 'received' })
    expect(wrapper.get('[data-testid="pending-task-count"]').text()).toBe('3')
    expect(wrapper.get('[data-testid="pending-task-action"]').text()).toContain('未开始任务')
  })

  it.each([
    ['未开始任务', 'pending-task-action'],
    ['已完成任务', 'completed-task-action'],
  ])('统计成功且%s为零时提示空态且不再请求列表', async (_title, testId) => {
    mocks.getTaskStats.mockResolvedValue(
      statsResponse({
        by_status: { assigned: 0, in_progress: 1, completed: 0 },
        completed: 0,
      }),
    )
    const wrapper = await mountView()
    mocks.getTaskList.mockClear()

    await wrapper.get(`[data-testid="${testId}"]`).trigger('click')
    await flushPromises()

    expect(mocks.getTaskList).not.toHaveBeenCalled()
    expect(mocks.message.info).toHaveBeenCalledWith('没有待处理的事项')
  })

  it('已有零值统计刷新期间不使用旧值判断空态', async () => {
    mocks.getTaskStats.mockResolvedValueOnce(
      statsResponse({ by_status: { assigned: 0 }, completed: 0 }),
    )
    const wrapper = await mountView()
    mocks.getTaskStats.mockReturnValueOnce(new Promise(() => undefined))

    await wrapper.get('[data-testid="refresh-task-list"]').trigger('click')
    mocks.getTaskList.mockClear()
    await wrapper.get('[data-testid="pending-task-action"]').trigger('click')

    expect(mocks.getTaskList).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalledWith('任务统计正在加载，请稍后重试')
    expect(mocks.message.info).not.toHaveBeenCalledWith('没有待处理的事项')
  })

  it('旧请求先完成时不提前结束较新请求的加载态', async () => {
    const firstRequest = deferred<ReturnType<typeof statsResponse>>()
    const secondRequest = deferred<ReturnType<typeof statsResponse>>()
    mocks.getTaskStats
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)
    const wrapper = await mountView()

    await wrapper.get('[data-testid="refresh-task-list"]').trigger('click')
    firstRequest.resolve(statsResponse({ by_status: { assigned: 0 } }))
    await flushPromises()
    mocks.getTaskList.mockClear()

    expect(wrapper.get('[data-testid="pending-task-count"]').text()).toBe('加载中')
    await wrapper.get('[data-testid="pending-task-action"]').trigger('click')
    expect(mocks.getTaskList).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalledWith('任务统计正在加载，请稍后重试')

    secondRequest.resolve(statsResponse({ by_status: { assigned: 2 } }))
    await flushPromises()
    expect(wrapper.get('[data-testid="pending-task-count"]').text()).toBe('2')
  })

  it('晚到的旧失败不覆盖较新请求的成功统计', async () => {
    const firstRequest = deferred<{ success: false; message: string }>()
    const secondRequest = deferred<ReturnType<typeof statsResponse>>()
    mocks.getTaskStats
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(secondRequest.promise)
    const wrapper = await mountView()

    await wrapper.get('[data-testid="refresh-task-list"]').trigger('click')
    secondRequest.resolve(statsResponse({ by_status: { assigned: 5 } }))
    await flushPromises()
    expect(wrapper.get('[data-testid="pending-task-count"]').text()).toBe('5')

    firstRequest.resolve({ success: false, message: '旧请求失败' })
    await flushPromises()
    expect(wrapper.get('[data-testid="pending-task-count"]').text()).toBe('5')
    expect(wrapper.find('[data-testid="task-stats-error"]').exists()).toBe(false)
  })

  it('快捷状态筛选清除旧关键词和日期并回到第一页', async () => {
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      searchKeyword: string
      dateRange: unknown
      pagination: { current: number }
    }
    vm.searchKeyword = '旧关键词'
    vm.dateRange = [{}, {}]
    vm.pagination.current = 3
    mocks.getTaskList.mockClear()

    await wrapper.get('[data-testid="pending-task-action"]').trigger('click')
    await flushPromises()

    expect(mocks.getTaskList).toHaveBeenCalledWith(
      expect.objectContaining({
        tab: 'received',
        status: 'assigned',
        keyword: undefined,
        page: 1,
      }),
    )
    expect(vm.dateRange).toBeNull()
  })

  it('统计失败时展示不可用且可重试恢复，不将失败伪装为零值', async () => {
    mocks.getTaskStats.mockResolvedValueOnce({ success: false, message: '服务暂不可用' })
    const wrapper = await mountView()

    expect(wrapper.get('[data-testid="pending-task-count"]').text()).toBe('不可用')
    expect(wrapper.get('[data-testid="task-stats-error"]').text()).toContain('服务暂不可用')
    mocks.getTaskList.mockClear()
    await wrapper.get('[data-testid="pending-task-action"]').trigger('click')
    expect(mocks.getTaskList).not.toHaveBeenCalled()
    expect(mocks.message.info).not.toHaveBeenCalledWith('没有待处理的事项')

    mocks.getTaskStats.mockResolvedValueOnce(statsResponse({ by_status: { assigned: 2 } }))
    await wrapper.get('[data-testid="retry-task-stats"]').trigger('click')
    await flushPromises()

    expect(mocks.getTaskStats).toHaveBeenLastCalledWith({ tab: 'received' })
    expect(wrapper.get('[data-testid="pending-task-count"]').text()).toBe('2')
    expect(wrapper.find('[data-testid="task-stats-error"]').exists()).toBe(false)
  })
})
