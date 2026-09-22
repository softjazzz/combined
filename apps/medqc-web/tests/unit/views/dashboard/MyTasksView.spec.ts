import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getTaskList: vi.fn(),
  getTaskStats: vi.fn(),
  getTaskDetail: vi.fn(),
  getTaskProgress: vi.fn(),
  updateTask: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  message: {
    error: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

type TestQuery = Record<string, string | string[] | undefined>

const routeState = vi.hoisted(() => ({ query: {} as TestQuery }))
const activeRoute = vi.hoisted(() => ({
  current: null as null | { query: TestQuery },
}))

vi.mock('@/api/tasks', () => ({
  getTaskList: mocks.getTaskList,
  getTaskStats: mocks.getTaskStats,
  getTaskDetail: mocks.getTaskDetail,
  getTaskProgress: mocks.getTaskProgress,
  updateTask: mocks.updateTask,
}))

vi.mock('vue-router', async () => {
  const { reactive, nextTick } = await import('vue')
  return {
    useRoute: () => {
      const route = reactive({ query: { ...routeState.query } })
      activeRoute.current = route
      return route
    },
    useRouter: () => ({
      push: mocks.routerPush,
      replace: mocks.routerReplace.mockImplementation(
        async ({ query }: { query: TestQuery }) => {
          if (activeRoute.current) activeRoute.current.query = { ...query }
          await nextTick()
        },
      ),
    }),
  }
})
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

function listWith(taskName: string) {
  return {
    success: true,
    data: {
      items: [
        {
          id: taskName,
          task_number: taskName,
          task_name: taskName,
          task_type: 'one_time',
          status: 'assigned',
          progress: 0,
          total_records: 1,
          completed_records: 0,
          creator_id: 'creator',
          creator_name: '创建人',
          created_at: '2026-09-22T00:00:00Z',
          updated_at: '2026-09-22T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
      total_pages: 1,
    },
  }
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
    routeState.query = {}
    activeRoute.current = null
    mocks.getTaskList.mockResolvedValue(listResponse)
    mocks.getTaskStats.mockResolvedValue(statsResponse())
  })

  it('从首页待办查询恢复范围并在分页请求中保留同一 as_of', async () => {
    routeState.query = { todo: 'due_soon', as_of: '2026-09-22T07:30:00+00:00' }
    const wrapper = await mountView()

    expect(wrapper.get('[data-testid="task-todo-scope"]').text()).toContain('24 小时内到期')
    expect(mocks.getTaskList).toHaveBeenLastCalledWith(
      expect.objectContaining({
        tab: 'received',
        todo: 'due_soon',
        as_of: '2026-09-22T07:30:00+00:00',
        page: 1,
      }),
    )

    mocks.getTaskList.mockClear()
    wrapper.getComponent({ name: 'ProStandardTable' }).vm.$emit('change', {
      current: 2,
      pageSize: 10,
    })
    await flushPromises()
    expect(mocks.getTaskList).toHaveBeenCalledWith(
      expect.objectContaining({ todo: 'due_soon', as_of: '2026-09-22T07:30:00+00:00', page: 2 }),
    )
  })

  it('浏览器切换待办 query 时清除旧筛选并从第一页加载新范围', async () => {
    routeState.query = { todo: 'assigned', as_of: '2026-09-22T07:30:00+00:00' }
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      searchKeyword: string
      selectedStatus: string | undefined
      dateRange: unknown
      pagination: { current: number }
    }
    vm.searchKeyword = '旧关键词'
    vm.selectedStatus = 'completed'
    vm.dateRange = [{}, {}]
    vm.pagination.current = 3
    mocks.getTaskList.mockClear()

    activeRoute.current!.query = {
      todo: 'in_progress',
      as_of: '2026-09-22T08:00:00+00:00',
    }
    await nextTick()
    await flushPromises()

    expect(mocks.getTaskList).toHaveBeenCalledWith(
      expect.objectContaining({
        todo: 'in_progress',
        as_of: '2026-09-22T08:00:00+00:00',
        keyword: undefined,
        status: undefined,
        page: 1,
      }),
    )
    expect(vm.dateRange).toBeNull()
  })

  it.each([
    { title: '未知 todo', query: { todo: 'unknown', as_of: '2026-09-22T07:30:00+00:00' } },
    { title: '数组 todo', query: { todo: ['assigned'], as_of: '2026-09-22T07:30:00+00:00' } },
    { title: '孤立 as_of', query: { as_of: '2026-09-22T07:30:00+00:00' } },
    { title: '空 as_of', query: { todo: 'due_soon', as_of: '' } },
    { title: '数组 as_of', query: { todo: 'due_soon', as_of: ['2026-09-22T07:30:00+00:00'] } },
    { title: '无时区 as_of', query: { todo: 'due_soon', as_of: '2026-09-22T07:30:00' } },
  ])('$title 明确报链接无效且不按全部任务请求', async ({ query }) => {
    routeState.query = query
    const wrapper = await mountView()

    expect(wrapper.get('[data-testid="task-todo-invalid"]').text()).toContain('待办链接无效')
    expect(mocks.getTaskList).not.toHaveBeenCalled()
  })

  it('清除待办范围保留无关 query 并加载普通 received 列表', async () => {
    routeState.query = {
      todo: 'assigned',
      as_of: '2026-09-22T07:30:00+00:00',
      source: 'bookmark',
    }
    const wrapper = await mountView()
    mocks.getTaskList.mockClear()

    await wrapper.get('[data-testid="clear-task-todo"]').trigger('click')
    await flushPromises()

    expect(mocks.routerReplace).toHaveBeenCalledWith({ query: { source: 'bookmark' } })
    expect(mocks.getTaskList).toHaveBeenCalledWith(
      expect.objectContaining({ tab: 'received', todo: undefined, as_of: undefined, page: 1 }),
    )
  })

  it('原快捷项退出旧待办范围后再按状态筛选', async () => {
    routeState.query = { todo: 'due_soon', as_of: '2026-09-22T07:30:00+00:00' }
    const wrapper = await mountView()
    mocks.getTaskList.mockClear()

    await wrapper.get('[data-testid="completed-task-action"]').trigger('click')
    await flushPromises()

    expect(mocks.routerReplace).toHaveBeenCalledWith({ query: {} })
    expect(mocks.getTaskList).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'completed', todo: undefined, as_of: undefined }),
    )
  })

  it('重置筛选同时清除待办 query', async () => {
    routeState.query = { todo: 'assigned', as_of: '2026-09-22T07:30:00+00:00' }
    const wrapper = await mountView()
    mocks.getTaskList.mockClear()

    const resetButton = wrapper.findAll('button').find((button) => button.text().includes('重置'))
    expect(resetButton).toBeDefined()
    await resetButton!.trigger('click')
    await flushPromises()

    expect(mocks.routerReplace).toHaveBeenCalledWith({ query: {} })
    expect(mocks.getTaskList).toHaveBeenCalledWith(
      expect.objectContaining({ todo: undefined, as_of: undefined, page: 1 }),
    )
  })

  it('列表失败清空旧行和总数，并可在同一待办范围重试恢复', async () => {
    routeState.query = { todo: 'assigned', as_of: '2026-09-22T07:30:00+00:00' }
    mocks.getTaskList.mockResolvedValueOnce(listWith('旧任务'))
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      tasks: Array<{ task_name: string }>
      pagination: { total: number }
    }
    expect(vm.tasks[0]?.task_name).toBe('旧任务')

    mocks.getTaskList.mockResolvedValueOnce({ success: false, message: '列表服务不可用' })
    await wrapper.get('[data-testid="refresh-task-list"]').trigger('click')
    await flushPromises()
    expect(vm.tasks).toEqual([])
    expect(vm.pagination.total).toBe(0)
    expect(wrapper.get('[data-testid="task-list-error"]').text()).toContain('列表服务不可用')
    expect(wrapper.find('[data-testid="task-todo-scope"]').exists()).toBe(true)

    const retryRequest = deferred<ReturnType<typeof listWith>>()
    mocks.getTaskList.mockReturnValueOnce(retryRequest.promise)
    await wrapper.get('[data-testid="retry-task-list"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="task-list-error"]').exists()).toBe(false)

    retryRequest.resolve(listWith('恢复任务'))
    await flushPromises()
    expect(vm.tasks[0]?.task_name).toBe('恢复任务')
  })

  it('旧列表响应晚到时不覆盖浏览器切换后的新待办范围', async () => {
    routeState.query = { todo: 'assigned', as_of: '2026-09-22T07:30:00+00:00' }
    const first = deferred<ReturnType<typeof listWith>>()
    const second = deferred<ReturnType<typeof listWith>>()
    mocks.getTaskList.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as { tasks: Array<{ task_name: string }> }

    activeRoute.current!.query = {
      todo: 'in_progress',
      as_of: '2026-09-22T08:00:00+00:00',
    }
    await nextTick()
    second.resolve(listWith('新范围任务'))
    await flushPromises()
    expect(vm.tasks[0]?.task_name).toBe('新范围任务')

    first.resolve(listWith('旧范围任务'))
    await flushPromises()
    expect(vm.tasks[0]?.task_name).toBe('新范围任务')
  })

  it('旧列表失败晚到时不覆盖新范围成功结果和错误状态', async () => {
    routeState.query = { todo: 'assigned', as_of: '2026-09-22T07:30:00+00:00' }
    const first = deferred<{ success: false; message: string }>()
    const second = deferred<ReturnType<typeof listWith>>()
    mocks.getTaskList.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as { tasks: Array<{ task_name: string }> }

    activeRoute.current!.query = {
      todo: 'in_progress',
      as_of: '2026-09-22T08:00:00+00:00',
    }
    await nextTick()
    second.resolve(listWith('新范围任务'))
    await flushPromises()

    first.resolve({ success: false, message: '旧范围失败' })
    await flushPromises()
    expect(vm.tasks[0]?.task_name).toBe('新范围任务')
    expect(wrapper.find('[data-testid="task-list-error"]').exists()).toBe(false)
  })

  it('清除范围等待路由完成时立即作废旧列表请求', async () => {
    routeState.query = { todo: 'assigned', as_of: '2026-09-22T07:30:00+00:00' }
    const oldRequest = deferred<ReturnType<typeof listWith>>()
    const routeReplace = deferred<void>()
    mocks.getTaskList
      .mockReturnValueOnce(oldRequest.promise)
      .mockResolvedValueOnce(listWith('普通列表任务'))
    mocks.routerReplace.mockImplementationOnce(async ({ query }: { query: TestQuery }) => {
      await routeReplace.promise
      if (activeRoute.current) activeRoute.current.query = { ...query }
      await nextTick()
    })
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as { tasks: Array<{ task_name: string }> }

    await wrapper.get('[data-testid="clear-task-todo"]').trigger('click')
    oldRequest.resolve(listWith('旧待办任务'))
    await flushPromises()
    expect(vm.tasks).toEqual([])

    routeReplace.resolve(undefined)
    await flushPromises()
    expect(vm.tasks[0]?.task_name).toBe('普通列表任务')
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
