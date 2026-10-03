import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getTaskList: vi.fn(),
  getTaskStats: vi.fn(),
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

const ASegmentedStub = defineComponent({
  name: 'ASegmented',
  props: { value: String, options: Array },
  emits: ['change'],
  setup(props, { emit }) {
    return () => h('div', (props.options as Array<{ label: string; value: string }> || []).map((option) =>
      h('button', {
        'data-testid': `${option.value}-tasks-tab`,
        'aria-pressed': props.value === option.value,
        onClick: () => emit('change', option.value),
      }, option.label),
    ))
  },
})

const TaskDetailDrawerStub = defineComponent({
  name: 'TaskDetailDrawer',
  props: {
    open: Boolean,
    taskId: String,
    tab: String,
    focusTaskRecordId: { type: String, default: null },
    focusRunNumber: { type: Number, default: null },
  },
  emits: ['update:open', 'task-updated'],
  template: '<div data-testid="task-detail-drawer-stub" />',
})

const ProStandardTableStub = defineComponent({
  name: 'ProStandardTable',
  props: { dataSource: Array, columns: Array },
  emits: ['change'],
  setup(props, { slots }) {
    return () => h('div', (props.dataSource || []).map((record) =>
      h('div', { 'data-testid': 'task-row' }, [
        slots.bodyCell?.({ column: { key: 'action' }, record }),
        ...['qcStatus', 'approvedRecords', 'assignedToMe', 'qcAssignees', 'actualCompletedAt'].map((key) =>
          h('span', { 'data-testid': `task-${key}` }, slots.bodyCell?.({ column: { key }, record })),
        ),
      ]),
    ))
  },
})

const listResponse = {
  success: true,
  data: { items: [], total: 0, page: 1, page_size: 10, total_pages: 0 },
}

function listWith(taskName: string, status = 'assigned') {
  return {
    success: true,
    data: {
      items: [
        {
          id: taskName,
          task_number: taskName,
          task_name: taskName,
          task_type: 'one_time',
          status,
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
        'a-input-search': true,
        'a-progress': true,
        'a-range-picker': true,
        'a-segmented': ASegmentedStub,
        'a-select': true,
        'a-tag': true,
        ProQueryBar: { template: '<div><slot name="filters"/><slot name="actions"/></div>' },
        ProStandardTable: ProStandardTableStub,
        ProTableToolbar: { template: '<div><slot/></div>' },
        TaskDetailDrawer: TaskDetailDrawerStub,
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

  it('任务列表覆盖手册字段并且审核通过数不取任务完成数', async () => {
    routeState.query = { tab: 'created' }
    const response = listWith('列表任务', 'completed')
    mocks.getTaskList.mockResolvedValue({ ...response, data: { ...response.data, items: [{
      ...response.data.items[0], completed_records: 7, approved_records: 0, assigned_to_me: 2,
      qc_assignees: [{ id: 'qc-1', name: '质控员甲' }], qc_run_statuses: ['failed'],
      actual_completed_at: '2026-10-01T00:00:00Z',
    }] } })
    const wrapper = await mountView()
    const columns = wrapper.getComponent(ProStandardTableStub).props('columns') as Array<{ title: string }>
    expect(columns.map((column) => column.title)).toEqual(expect.arrayContaining([
      '任务名称', '任务类型', '质控状态', '任务状态', '进度', '病历数量', '分配给我的',
      '审核通过病历数', '创建人', '质控员', '创建时间', '期望完成时间', '实际完成时间',
    ]))
    expect(wrapper.get('[data-testid="task-approvedRecords"]').text()).toBe('0')
    expect(wrapper.get('[data-testid="task-qcStatus"]').text()).toBe('失败')
    expect(wrapper.get('[data-testid="task-qcAssignees"]').text()).toBe('质控员甲')
  })

  it('缺失审核与运行回执显示未知，未完成任务不伪造完成时间', async () => {
    routeState.query = { tab: 'created' }
    mocks.getTaskList.mockResolvedValue(listWith('未知任务', 'in_progress'))
    const wrapper = await mountView()
    expect(wrapper.get('[data-testid="task-approvedRecords"]').text()).toBe('未知')
    expect(wrapper.get('[data-testid="task-qcStatus"]').text()).toBe('未知')
    expect(wrapper.get('[data-testid="task-actualCompletedAt"]').text()).toBe('未完成')
  })

  it('我收到保持原有已完成列，不展示创建列表的新统计字段', async () => {
    const wrapper = await mountView()
    const columns = wrapper.getComponent(ProStandardTableStub).props('columns') as Array<{ title: string }>
    expect(columns.map((column) => column.title)).toContain('已完成')
    expect(columns.map((column) => column.title)).not.toContain('审核通过病历数')
  })

  it('草稿不显示开始入口，快捷开始也不会提交草稿', async () => {
    mocks.getTaskList.mockResolvedValue(listWith('草稿任务', 'draft'))
    const wrapper = await mountView()

    expect(wrapper.get('[data-testid="task-row"]').text()).not.toContain('开始')
    await wrapper.get('[data-testid="start-task-action"]').trigger('click')

    expect(mocks.updateTask).not.toHaveBeenCalled()
    expect(mocks.message.info).toHaveBeenCalledWith('暂无待处理任务')
  })

  it('已分配任务只提交一次，成功后刷新列表和统计', async () => {
    mocks.getTaskList.mockResolvedValue(listWith('已分配任务'))
    const request = deferred<{ success: boolean; data: { id: string; status: string } }>()
    mocks.updateTask.mockReturnValue(request.promise)
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as { handleStartWork: (record: unknown) => Promise<void>; tasks: unknown[] }
    const first = vm.handleStartWork(vm.tasks[0])
    await nextTick()
    expect(wrapper.get('[data-testid="task-row"]').text()).toContain('开始')
    expect(wrapper.get('[data-testid="task-row"] button').attributes('disabled')).toBeDefined()
    await vm.handleStartWork(vm.tasks[0])

    expect(mocks.updateTask).toHaveBeenCalledTimes(1)
    expect(mocks.updateTask).toHaveBeenCalledWith('已分配任务', { status: 'in_progress' })
    mocks.getTaskList.mockClear()
    mocks.getTaskStats.mockClear()
    request.resolve({ success: true, data: { id: '已分配任务', status: 'in_progress' } })
    await first

    expect(mocks.getTaskList).toHaveBeenCalledTimes(1)
    expect(mocks.getTaskStats).toHaveBeenCalledTimes(1)
    expect(mocks.message.success).toHaveBeenCalledWith('任务「已分配任务」已开始')
  })

  it('开始结果未知时不自动重试并刷新服务端状态供核对', async () => {
    mocks.getTaskList.mockResolvedValue(listWith('待核对任务'))
    mocks.updateTask.mockResolvedValue({ success: false, message: '网络超时' })
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as { handleStartWork: (record: unknown) => Promise<void>; tasks: unknown[] }
    mocks.getTaskList.mockClear()
    mocks.getTaskStats.mockClear()

    await vm.handleStartWork(vm.tasks[0])

    expect(mocks.updateTask).toHaveBeenCalledTimes(1)
    expect(mocks.getTaskList).toHaveBeenCalledTimes(1)
    expect(mocks.getTaskStats).toHaveBeenCalledTimes(1)
    expect(mocks.message.error).toHaveBeenCalledWith('网络超时，请核对刷新后的任务状态')
  })

  it.each([
    ['空体', undefined],
    ['错状态', { id: '待核对任务', status: 'assigned' }],
    ['错任务', { id: '其他任务', status: 'in_progress' }],
  ])('2xx %s 不宣称已开始，只刷新服务端状态', async (_label, data) => {
    mocks.getTaskList.mockResolvedValue(listWith('待核对任务'))
    mocks.updateTask.mockResolvedValue({ success: true, data })
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as { handleStartWork: (record: unknown) => Promise<void>; tasks: unknown[] }
    mocks.getTaskList.mockClear()
    mocks.getTaskStats.mockClear()

    await vm.handleStartWork(vm.tasks[0])

    expect(mocks.message.success).not.toHaveBeenCalled()
    expect(mocks.message.error).toHaveBeenCalledWith('操作结果未确认，请核对刷新后的任务状态')
    expect(mocks.getTaskList).toHaveBeenCalledTimes(1)
    expect(mocks.getTaskStats).toHaveBeenCalledTimes(1)
    expect(mocks.updateTask).toHaveBeenCalledTimes(1)
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

  it('首页场景待办下钻后列表与统计保持同一范围', async () => {
    routeState.query = {
      todo: 'assigned',
      as_of: '2026-09-22T07:30:00+00:00',
      scene: 'final',
    }
    const wrapper = await mountView()

    expect(wrapper.get('[data-testid="task-todo-scope"]').text()).toContain('终末')
    expect(mocks.getTaskList).toHaveBeenCalledWith(
      expect.objectContaining({
        tab: 'received',
        todo: 'assigned',
        as_of: '2026-09-22T07:30:00+00:00',
        scene: 'final',
      }),
    )
    expect(mocks.getTaskStats).toHaveBeenCalledWith({ tab: 'received', scene: 'final' })
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
    { title: '未知 scene', query: { scene: 'ward' } },
    { title: '空 scene', query: { scene: '' } },
    { title: '数组 scene', query: { scene: ['running'] } },
  ])('$title 明确报链接无效且不按全部任务请求', async ({ query }) => {
    routeState.query = query
    const wrapper = await mountView()

    expect(wrapper.get('[data-testid="task-todo-invalid"]').text()).toContain('任务范围链接无效')
    expect(mocks.getTaskList).not.toHaveBeenCalled()
    if ('scene' in query) expect(mocks.getTaskStats).not.toHaveBeenCalled()
  })

  it('清除非法场景范围时保留无关 query 并恢复普通列表与统计', async () => {
    routeState.query = { scene: 'ward', source: 'bookmark' }
    const wrapper = await mountView()
    mocks.getTaskList.mockClear()
    mocks.getTaskStats.mockClear()

    const clearButton = wrapper
      .get('[data-testid="task-todo-invalid"]')
      .findAll('button')
      .find((button) => button.text().includes('清除无效范围'))
    expect(clearButton).toBeDefined()
    await clearButton!.trigger('click')
    await flushPromises()

    expect(mocks.routerReplace).toHaveBeenCalledWith({ query: { source: 'bookmark' } })
    expect(mocks.getTaskList).toHaveBeenCalledWith(
      expect.objectContaining({ tab: 'received', scene: undefined, page: 1 }),
    )
    expect(mocks.getTaskStats).toHaveBeenCalledWith({ tab: 'received' })
  })

  it('清除待办范围保留无关 query 并加载普通 received 列表', async () => {
    routeState.query = {
      todo: 'assigned',
      as_of: '2026-09-22T07:30:00+00:00',
      scene: 'running',
      source: 'bookmark',
    }
    const wrapper = await mountView()
    mocks.getTaskList.mockClear()

    await wrapper.get('[data-testid="clear-task-todo"]').trigger('click')
    await flushPromises()

    expect(mocks.routerReplace).toHaveBeenCalledWith({
      query: { scene: 'running', source: 'bookmark' },
    })
    expect(mocks.getTaskList).toHaveBeenCalledWith(
      expect.objectContaining({
        tab: 'received',
        todo: undefined,
        as_of: undefined,
        scene: 'running',
        page: 1,
      }),
    )
  })

  it('场景切换立即清空旧数据并以新场景刷新列表和统计', async () => {
    mocks.getTaskList.mockResolvedValueOnce(listWith('旧任务'))
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      tasks: Array<{ task_name: string }>
      taskStats: unknown
      handleSceneChange: (scene?: 'running' | 'final') => Promise<void>
    }
    expect(vm.tasks[0]?.task_name).toBe('旧任务')
    mocks.getTaskList.mockClear()
    mocks.getTaskStats.mockClear()

    const nextList = deferred<ReturnType<typeof listWith>>()
    const nextStats = deferred<ReturnType<typeof statsResponse>>()
    mocks.getTaskList.mockReturnValueOnce(nextList.promise)
    mocks.getTaskStats.mockReturnValueOnce(nextStats.promise)
    const changing = vm.handleSceneChange('running')
    await changing

    expect(vm.tasks).toEqual([])
    expect(vm.taskStats).toBeNull()
    expect(mocks.getTaskList).toHaveBeenCalledWith(expect.objectContaining({ scene: 'running' }))
    expect(mocks.getTaskStats).toHaveBeenCalledWith({ tab: 'received', scene: 'running' })

    nextList.resolve(listWith('运行任务'))
    nextStats.resolve(statsResponse({ total: 1 }))
    await changing
    await flushPromises()
    expect(vm.tasks[0]?.task_name).toBe('运行任务')
  })

  it('连续切换场景时晚到旧列表和统计都不能覆盖新范围', async () => {
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      tasks: Array<{ task_name: string }>
      taskStats: { total: number } | null
      handleSceneChange: (scene?: 'running' | 'final') => Promise<void>
    }
    const runningList = deferred<ReturnType<typeof listWith>>()
    const finalList = deferred<ReturnType<typeof listWith>>()
    const runningStats = deferred<ReturnType<typeof statsResponse>>()
    const finalStats = deferred<ReturnType<typeof statsResponse>>()
    mocks.getTaskList
      .mockReturnValueOnce(runningList.promise)
      .mockReturnValueOnce(finalList.promise)
    mocks.getTaskStats
      .mockReturnValueOnce(runningStats.promise)
      .mockReturnValueOnce(finalStats.promise)

    const runningChange = vm.handleSceneChange('running')
    await runningChange
    const finalChange = vm.handleSceneChange('final')
    await finalChange
    finalList.resolve(listWith('终末任务'))
    finalStats.resolve(statsResponse({ total: 2 }))
    await flushPromises()
    runningList.resolve(listWith('运行任务'))
    runningStats.resolve(statsResponse({ total: 9 }))
    await flushPromises()

    expect(vm.tasks[0]?.task_name).toBe('终末任务')
    expect(vm.taskStats?.total).toBe(2)
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

  it('抽屉确认本人最后一条病历完成后，原范围刷新列表和统计而不乐观保留旧待办', async () => {
    routeState.query = { todo: 'in_progress', as_of: '2026-09-22T07:30:00+00:00', scene: 'final' }
    mocks.getTaskList.mockResolvedValueOnce(listWith('task-1', 'in_progress')).mockResolvedValueOnce(listResponse)
    mocks.getTaskStats.mockResolvedValueOnce(statsResponse({ in_progress: 1, completed: 4 }))
      .mockResolvedValueOnce(statsResponse({ in_progress: 0, completed: 5 }))
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      handleViewDetail: (record: { id: string }) => void
      tasks: Array<{ id: string }>
      pagination: { current: number; total: number }
      selectedStatus: string
      searchKeyword: string
      taskStats: { completed: number } | null
    }
    vm.pagination.current = 3
    vm.selectedStatus = 'in_progress'
    vm.searchKeyword = '病案'
    vm.handleViewDetail({ id: 'task-1' })
    await nextTick()
    expect(vm.tasks).toHaveLength(1)

    wrapper.getComponent(TaskDetailDrawerStub).vm.$emit('task-updated', 'task-1')
    await flushPromises()

    expect(mocks.getTaskList).toHaveBeenLastCalledWith(expect.objectContaining({
      tab: 'received', todo: 'in_progress', as_of: '2026-09-22T07:30:00+00:00',
      scene: 'final', status: 'in_progress', keyword: '病案', page: 3,
    }))
    expect(mocks.getTaskStats).toHaveBeenLastCalledWith({ tab: 'received', scene: 'final' })
    expect(vm.tasks).toEqual([])
    expect(vm.pagination.current).toBe(3)
    expect(vm.pagination.total).toBe(0)
    expect(vm.taskStats?.completed).toBe(5)
    expect(wrapper.getComponent(TaskDetailDrawerStub).props()).toMatchObject({ open: true, taskId: 'task-1', tab: 'received' })
    expect(activeRoute.current?.query).toMatchObject({ todo: 'in_progress', scene: 'final' })
  })

  it('关闭抽屉或切换任务的迟到完成事件不刷新列表统计', async () => {
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as { handleViewDetail: (record: { id: string }) => void }
    const drawer = wrapper.getComponent(TaskDetailDrawerStub)
    mocks.getTaskList.mockClear()
    mocks.getTaskStats.mockClear()

    drawer.vm.$emit('task-updated', 'task-1')
    await flushPromises()
    expect(mocks.getTaskList).not.toHaveBeenCalled()
    expect(mocks.getTaskStats).not.toHaveBeenCalled()

    vm.handleViewDetail({ id: 'task-2' })
    await nextTick()
    drawer.vm.$emit('task-updated', 'task-1')
    await flushPromises()
    expect(mocks.getTaskList).not.toHaveBeenCalled()
    expect(mocks.getTaskStats).not.toHaveBeenCalled()

    drawer.vm.$emit('update:open', false)
    await nextTick()
    drawer.vm.$emit('task-updated', 'task-2')
    await flushPromises()
    expect(mocks.getTaskList).not.toHaveBeenCalled()
    expect(mocks.getTaskStats).not.toHaveBeenCalled()
  })

  it('创建页即使打开同 id 任务详情，也忽略受领页迟到的完成事件', async () => {
    routeState.query = { tab: 'created' }
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as { handleViewDetail: (record: { id: string }) => void }
    vm.handleViewDetail({ id: 'task-1' })
    await nextTick()
    mocks.getTaskList.mockClear()
    mocks.getTaskStats.mockClear()

    wrapper.getComponent(TaskDetailDrawerStub).vm.$emit('task-updated', 'task-1')
    await flushPromises()
    expect(mocks.getTaskList).not.toHaveBeenCalled()
    expect(mocks.getTaskStats).not.toHaveBeenCalled()
  })

  it('创建任务 URL 恢复列表、统计、详情同一范围，草稿卡正确下钻', async () => {
    routeState.query = { tab: 'created', scene: 'final' }
    mocks.getTaskList.mockResolvedValue(listWith('我创建的草稿', 'draft'))
    mocks.getTaskStats.mockResolvedValue(statsResponse({ by_status: { draft: 2 }, draft: 2 }))
    const wrapper = await mountView()

    expect(wrapper.get('[data-testid="created-tasks-tab"]').attributes('aria-pressed')).toBe('true')
    expect(mocks.getTaskList).toHaveBeenCalledWith(expect.objectContaining({ tab: 'created', scene: 'final', todo: undefined, as_of: undefined }))
    expect(mocks.getTaskStats).toHaveBeenCalledWith({ tab: 'created', scene: 'final' })
    expect(wrapper.get('[data-testid="pending-task-count"]').text()).toBe('2')
    expect(wrapper.get('[data-testid="pending-task-action"]').text()).toContain('草稿任务')
    expect(wrapper.find('[data-testid="start-task-action"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="task-row"]').text()).not.toContain('开始')

    await wrapper.get('[data-testid="pending-task-action"]').trigger('click')
    await flushPromises()
    expect(mocks.getTaskList).toHaveBeenLastCalledWith(expect.objectContaining({ tab: 'created', status: 'draft', scene: 'final' }))
    const vm = wrapper.vm as unknown as { handleViewDetail: (record: { id: string }) => void }
    vm.handleViewDetail({ id: 'created-task' })
    await nextTick()
    expect(wrapper.getComponent(TaskDetailDrawerStub).props()).toMatchObject({ open: true, taskId: 'created-task', tab: 'created' })
  })

  it('模式切换清除待办基准、关闭旧详情并阻止旧列表和统计回填', async () => {
    routeState.query = { todo: 'assigned', as_of: '2026-09-22T07:30:00+00:00', source: 'bookmark' }
    const oldList = deferred<ReturnType<typeof listWith>>()
    const oldStats = deferred<ReturnType<typeof statsResponse>>()
    mocks.getTaskList.mockReturnValueOnce(oldList.promise).mockResolvedValueOnce(listWith('创建任务', 'draft'))
    mocks.getTaskStats.mockReturnValueOnce(oldStats.promise).mockResolvedValueOnce(statsResponse({ total: 1, by_status: { draft: 1 } }))
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as { handleViewDetail: (record: { id: string }) => void; tasks: Array<{ task_name: string }>; taskStats: { total: number } | null }
    vm.handleViewDetail({ id: 'received-task' })
    await wrapper.get('[data-testid="created-tasks-tab"]').trigger('click')
    await flushPromises()

    expect(mocks.routerReplace).toHaveBeenCalledWith({ query: { source: 'bookmark', tab: 'created' } })
    expect(mocks.getTaskList).toHaveBeenLastCalledWith(expect.objectContaining({ tab: 'created', todo: undefined, as_of: undefined }))
    expect(mocks.getTaskStats).toHaveBeenLastCalledWith({ tab: 'created' })
    expect(wrapper.getComponent(TaskDetailDrawerStub).props()).toMatchObject({ open: false, taskId: null, tab: 'created' })
    oldList.resolve(listWith('旧受领任务'))
    oldStats.resolve(statsResponse({ total: 99 }))
    await flushPromises()
    expect(vm.tasks[0]?.task_name).toBe('创建任务')
    expect(vm.taskStats?.total).toBe(1)
  })

  it('浏览器返回 received 时刷新范围并恢复受领操作', async () => {
    routeState.query = { tab: 'created' }
    mocks.getTaskList.mockResolvedValue(listWith('任务', 'assigned'))
    const wrapper = await mountView()
    expect(wrapper.get('[data-testid="task-row"]').text()).not.toContain('开始')
    activeRoute.current!.query = {}
    await nextTick()
    await flushPromises()
    expect(mocks.getTaskList).toHaveBeenLastCalledWith(expect.objectContaining({ tab: 'received' }))
    expect(mocks.getTaskStats).toHaveBeenLastCalledWith({ tab: 'received' })
    expect(wrapper.get('[data-testid="task-row"]').text()).toContain('开始')
  })

  it.each([
    { tab: 'all' },
    { tab: '' },
    { tab: ['created'] },
    { tab: 'created', todo: 'assigned', as_of: '2026-09-22T07:30:00+00:00' },
  ])('非法或冲突 tab 不请求列表统计，也不回退 all：%j', async (query) => {
    routeState.query = query
    const wrapper = await mountView()
    expect(wrapper.find('[data-testid="task-todo-invalid"]').exists()).toBe(true)
    expect(mocks.getTaskList).not.toHaveBeenCalled()
    expect(mocks.getTaskStats).not.toHaveBeenCalled()
  })

  it('有效创建范围变成非法待办链接时清空旧统计，恢复后重新加载', async () => {
    routeState.query = { tab: 'created' }
    mocks.getTaskStats.mockResolvedValue(statsResponse({ total: 2, by_status: { draft: 2 } }))
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as { taskStats: { total: number } | null }
    expect(vm.taskStats?.total).toBe(2)

    activeRoute.current!.query = { tab: 'created', todo: 'assigned' }
    await nextTick()
    await flushPromises()
    expect(wrapper.find('[data-testid="task-todo-invalid"]').exists()).toBe(true)
    expect(vm.taskStats).toBeNull()
    expect(mocks.getTaskStats).toHaveBeenCalledTimes(1)

    activeRoute.current!.query = { tab: 'created' }
    await nextTick()
    await flushPromises()
    expect(mocks.getTaskStats).toHaveBeenCalledTimes(2)
    expect(vm.taskStats?.total).toBe(2)
  })

  it('非法 tab 清理后仅恢复 received，不请求 all', async () => {
    routeState.query = { tab: 'all', source: 'bookmark' }
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-todo-invalid"] button').trigger('click')
    await flushPromises()
    expect(mocks.routerReplace).toHaveBeenCalledWith({ query: { source: 'bookmark' } })
    expect(mocks.getTaskList).toHaveBeenCalledWith(expect.objectContaining({ tab: 'received' }))
    expect(mocks.getTaskStats).toHaveBeenCalledWith({ tab: 'received' })
    expect(mocks.getTaskList).not.toHaveBeenCalledWith(expect.objectContaining({ tab: 'all' }))
  })

  it.each(['assigned', 'in_progress'])('created 模式的 %s 行不呈现受领动作', async (status) => {
    routeState.query = { tab: 'created' }
    mocks.getTaskList.mockResolvedValue(listWith('创建任务', status))
    const wrapper = await mountView()
    const row = wrapper.get('[data-testid="task-row"]')
    expect(row.text()).not.toContain('开始')
    expect(row.text()).not.toContain('继续')
    expect(row.text()).toContain('详情')
  })

  it('查看任务详情时以 received 范围打开共享抽屉', async () => {
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      handleViewDetail: (record: { id: string }) => void
    }

    vm.handleViewDetail({ id: 'task/with long id' })
    await nextTick()

    expect(wrapper.getComponent(TaskDetailDrawerStub).props()).toMatchObject({
      open: true,
      taskId: 'task/with long id',
      tab: 'received',
    })
  })

  it('继续进行中任务时打开该任务受领详情，不跳入全院病历池', async () => {
    mocks.getTaskList.mockResolvedValue(listWith('任务-A', 'in_progress'))
    const wrapper = await mountView()
    const continueButton = wrapper.get('[data-testid="task-row"]').findAll('button')
      .find((button) => button.text().includes('继续'))

    expect(continueButton).toBeDefined()
    await continueButton!.trigger('click')
    await nextTick()

    expect(wrapper.getComponent(TaskDetailDrawerStub).props()).toMatchObject({
      open: true,
      taskId: '任务-A',
      tab: 'received',
    })
    expect(mocks.routerPush).not.toHaveBeenCalled()
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

  it.each(['initial', 'recheck'])('终末审核下钻实际消费任务定位并保留场景与阶段 %s，确认后刷新列表统计', async (stage) => {
    routeState.query = { scene: 'final', stage, task_id: 'task-9', task_record_id: 'assoc-9', run_number: '3' }
    const wrapper = await mountView()
    const drawer = wrapper.getComponent(TaskDetailDrawerStub)
    expect(drawer.props()).toMatchObject({ open: true, taskId: 'task-9', tab: 'received',
      focusTaskRecordId: 'assoc-9', focusRunNumber: 3 })
    expect(mocks.getTaskList).toHaveBeenLastCalledWith(expect.objectContaining({ tab: 'received', scene: 'final' }))
    expect(mocks.getTaskStats).toHaveBeenLastCalledWith({ tab: 'received', scene: 'final' })
    expect(activeRoute.current?.query).toEqual({ scene: 'final', stage })
    mocks.getTaskList.mockClear()
    mocks.getTaskStats.mockClear()
    drawer.vm.$emit('task-updated', 'task-9')
    await flushPromises()
    expect(mocks.getTaskList).toHaveBeenCalledWith(expect.objectContaining({ tab: 'received', scene: 'final' }))
    expect(mocks.getTaskStats).toHaveBeenCalledWith({ tab: 'received', scene: 'final' })
  })

  it('待办下钻 query 打开指定任务并定位病历与运行，消费后移除且不改动 todo/scene 范围', async () => {
    routeState.query = { scene: 'running', task_id: 'task-9', task_record_id: 'assoc-9', run_number: '3' }
    const wrapper = await mountView()

    expect(wrapper.getComponent(TaskDetailDrawerStub).props()).toMatchObject({
      open: true, taskId: 'task-9', tab: 'received', focusTaskRecordId: 'assoc-9', focusRunNumber: 3,
    })
    expect(mocks.routerReplace).toHaveBeenCalledWith({ query: { scene: 'running' } })
    expect(mocks.getTaskList).toHaveBeenCalledTimes(1)
    expect(mocks.getTaskList).toHaveBeenCalledWith(expect.objectContaining({ tab: 'received', scene: 'running' }))

    // 用户手动查看其他任务时不再沿用下钻定位
    const vm = wrapper.vm as unknown as { handleViewDetail: (record: { id: string }) => void }
    vm.handleViewDetail({ id: 'task-other' })
    await nextTick()
    expect(wrapper.getComponent(TaskDetailDrawerStub).props()).toMatchObject({
      taskId: 'task-other', focusTaskRecordId: null, focusRunNumber: null,
    })
  })

  it('创建视图或非法运行序号下不按下钻定位打开受领详情', async () => {
    routeState.query = { tab: 'created', task_id: 'task-9', task_record_id: 'assoc-9' }
    const created = await mountView()
    expect(created.getComponent(TaskDetailDrawerStub).props('open')).toBe(false)
    expect(mocks.routerReplace).toHaveBeenCalledWith({ query: { tab: 'created' } })
    created.unmount()

    routeState.query = { task_id: 'task-9', run_number: 'abc' }
    const invalidRun = await mountView()
    expect(invalidRun.getComponent(TaskDetailDrawerStub).props()).toMatchObject({
      open: true, taskId: 'task-9', focusTaskRecordId: null, focusRunNumber: null,
    })
  })
})

