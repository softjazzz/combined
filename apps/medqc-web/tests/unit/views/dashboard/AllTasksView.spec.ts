import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getTaskList: vi.fn(),
  getTaskStats: vi.fn(),
  deleteTask: vi.fn(),
  cancelTask: vi.fn(),
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
  deleteTask: mocks.deleteTask,
  cancelTask: mocks.cancelTask,
}))
vi.mock('ant-design-vue', () => ({ message: mocks.message }))
vi.mock('@ant-design/icons-vue', () => {
  const icon = { template: '<span />' }
  return {
    BarChartOutlined: icon,
    CheckCircleOutlined: icon,
    ClockCircleOutlined: icon,
    DeleteOutlined: icon,
    DownloadOutlined: icon,
    EditOutlined: icon,
    ExclamationCircleOutlined: icon,
    EyeOutlined: icon,
    FileOutlined: icon,
    PlusOutlined: icon,
    ProjectOutlined: icon,
    ReloadOutlined: icon,
    SearchOutlined: icon,
    SyncOutlined: icon,
    TeamOutlined: icon,
    UserAddOutlined: icon,
  }
})

import AllTasksView from '@/views/dashboard/tasks/AllTasksView.vue'

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

function listWith(taskName: string, scene: 'running' | 'final' | null = null) {
  return {
    success: true,
    data: {
      items: [
        {
          id: taskName,
          task_number: taskName,
          task_name: taskName,
          task_type: 'one_time',
          status: 'draft',
          progress: 0,
          total_records: 0,
          completed_records: 0,
          creator_id: 'creator',
          creator_name: '创建人',
          scene,
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

function statsResponse(total = 6) {
  return {
    success: true,
    data: {
      total,
      by_status: { draft: total },
      draft: total,
      in_progress: 0,
      completed: 0,
      cancelled: 0,
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

async function mountView() {
  const wrapper = shallowMount(AllTasksView, {
    global: {
      stubs: {
        'a-avatar': true,
        'a-button': AButtonStub,
        'a-input': true,
        'a-progress': true,
        'a-range-picker': true,
        'a-select': true,
        'a-table': true,
        'a-tag': true,
        CreateTaskDrawer: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('AllTasksView 场景口径', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getTaskList.mockResolvedValue(listResponse)
    mocks.getTaskStats.mockResolvedValue(statsResponse())
  })

  it('默认列表与统计覆盖全部场景，切换后使用同一场景范围', async () => {
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      tasks: Array<{ task_name: string }>
      taskStats: unknown
      handleSceneChange: (scene?: 'running') => void
    }

    expect(mocks.getTaskList).toHaveBeenCalledWith(expect.objectContaining({ scene: undefined }))
    expect(mocks.getTaskStats).toHaveBeenCalledWith(undefined)
    expect(wrapper.text()).toContain('草稿')
    expect(wrapper.text()).toContain('已取消')
    expect(wrapper.text()).not.toContain('待分配')
    expect(wrapper.text()).not.toContain('逾期任务')
    mocks.getTaskList.mockClear()
    mocks.getTaskStats.mockClear()

    vm.handleSceneChange('running')
    expect(vm.tasks).toEqual([])
    expect(vm.taskStats).toBeNull()
    await flushPromises()

    expect(mocks.getTaskList).toHaveBeenCalledWith(expect.objectContaining({ scene: 'running' }))
    expect(mocks.getTaskStats).toHaveBeenCalledWith({ scene: 'running' })
  })

  it('连续切换时晚到旧列表与统计不能覆盖新场景', async () => {
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      tasks: Array<{ task_name: string }>
      taskStats: { total: number } | null
      handleSceneChange: (scene?: 'running' | 'final') => void
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

    vm.handleSceneChange('running')
    await nextTick()
    vm.handleSceneChange('final')
    await nextTick()
    finalList.resolve(listWith('终末任务', 'final'))
    finalStats.resolve(statsResponse(2))
    await flushPromises()
    runningList.resolve(listWith('运行任务', 'running'))
    runningStats.resolve(statsResponse(9))
    await flushPromises()

    expect(vm.tasks[0]?.task_name).toBe('终末任务')
    expect(vm.taskStats?.total).toBe(2)
  })

  it('列表与统计失败均保持不可用状态并能在当前场景重试', async () => {
    mocks.getTaskList.mockResolvedValueOnce({ success: false, message: '列表服务不可用' })
    mocks.getTaskStats.mockResolvedValueOnce({ success: false, message: '统计服务不可用' })
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      selectedScene: 'outpatient' | undefined
      fetchTasks: () => Promise<void>
      fetchStats: () => Promise<void>
    }

    expect(wrapper.get('[data-testid="all-task-list-error"]').text()).toContain('列表服务不可用')
    expect(wrapper.get('[data-testid="all-task-stats-error"]').text()).toContain('统计服务不可用')
    vm.selectedScene = 'outpatient'
    mocks.getTaskList.mockResolvedValueOnce(listWith('门急诊任务'))
    mocks.getTaskStats.mockResolvedValueOnce(statsResponse(1))
    await Promise.all([vm.fetchTasks(), vm.fetchStats()])
    await flushPromises()

    expect(mocks.getTaskList).toHaveBeenLastCalledWith(
      expect.objectContaining({ scene: 'outpatient' }),
    )
    expect(mocks.getTaskStats).toHaveBeenLastCalledWith({ scene: 'outpatient' })
    expect(wrapper.find('[data-testid="all-task-list-error"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="all-task-stats-error"]').exists()).toBe(false)
  })

  it('历史 NULL 场景在列表和详情语义中显示为未标注', async () => {
    mocks.getTaskList.mockResolvedValueOnce(listWith('历史任务', null))
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      sceneLabel: (scene?: string | null) => string
      handleViewDetail: (record: { task_name: string; scene: null }) => void
    }

    expect(vm.sceneLabel(null)).toBe('未标注')
    vm.handleViewDetail({ task_name: '历史任务', scene: null })
    expect(mocks.message.info).toHaveBeenCalledWith('查看任务详情: 历史任务（未标注）')
  })
})
