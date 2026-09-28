import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getTaskList: vi.fn(),
  getTaskStats: vi.fn(),
  deleteTask: vi.fn(),
  cancelTask: vi.fn(),
  assignTask: vi.fn(),
  assignTasksBatch: vi.fn(),
  getTaskAssigneeOptions: vi.fn(),
  message: {
    error: vi.fn(),
    info: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))
const authState = vi.hoisted(() => ({ user: { id: 'creator' } as { id: string } | null }))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => authState }))

vi.mock('@/api/tasks', () => ({
  getTaskList: mocks.getTaskList,
  getTaskStats: mocks.getTaskStats,
  deleteTask: mocks.deleteTask,
  cancelTask: mocks.cancelTask,
  assignTask: mocks.assignTask,
  assignTasksBatch: mocks.assignTasksBatch,
  getTaskAssigneeOptions: mocks.getTaskAssigneeOptions,
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
import TaskAssignmentResult from '@/components/qc/TaskAssignmentResult.vue'
import TaskAnalysisDrawer from '@/components/qc/TaskAnalysisDrawer.vue'

const AButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  emits: ['click'],
  setup(_, { attrs, emit, slots }) {
    return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.())
  },
})

const TaskDetailDrawerStub = defineComponent({
  name: 'TaskDetailDrawer',
  props: {
    open: Boolean,
    taskId: String,
    tab: String,
  },
  emits: ['update:open'],
  template: '<div data-testid="task-detail-drawer-stub" />',
})

const ATableStub = defineComponent({
  name: 'ATable',
  props: {
    dataSource: { type: Array, default: () => [] },
    columns: { type: Array, default: () => [] },
    rowSelection: Object,
  },
  setup(props, { slots }) {
    return () => h('div', [
      h('button', {
        'data-testid': 'select-batch-tasks',
        onClick: () => {
          const selection = props.rowSelection as {
            onChange?: (keys: string[], rows: unknown[]) => void
            getCheckboxProps?: (row: unknown) => { disabled?: boolean }
          }
          const rows = props.dataSource.filter((row) => !selection?.getCheckboxProps?.(row)?.disabled)
          selection?.onChange?.(rows.map((row) => (row as { id: string }).id), rows)
        },
      }, '选择可批量任务'),
      ...props.dataSource.map((record) => h('div', { 'data-testid': 'task-row' },
        slots.bodyCell?.({ column: { key: 'action' }, record }))),
    ])
  },
})

const AModalStub = defineComponent({
  name: 'AModal',
  props: { open: Boolean, okButtonProps: Object },
  emits: ['ok', 'cancel'],
  setup(props, { slots, emit }) {
    return () => props.open ? h('div', { 'data-testid': 'assign-dialog' }, [
      slots.default?.(),
      h('button', { 'data-testid': 'assign-confirm', disabled: (props.okButtonProps as { disabled?: boolean })?.disabled, onClick: () => emit('ok') }, '确认分配'),
      h('button', { 'data-testid': 'assign-cancel', onClick: () => emit('cancel') }, '取消'),
    ]) : null
  },
})

const ASelectStub = defineComponent({
  name: 'ASelect',
  props: { mode: String, options: { type: Array, default: () => [] } },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () => props.mode === 'multiple' ? h('button', {
      'data-testid': 'select-first-assignee',
      onClick: () => emit('update:value', [(props.options[0] as { value: string }).value]),
    }, '选择质控员') : null
  },
})

const listResponse = {
  success: true,
  data: { items: [], total: 0, page: 1, page_size: 10, total_pages: 0 },
}

function listWith(taskName: string, scene: 'running' | 'final' | null = null, status = 'draft') {
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
          total_records: 0,
          completed_records: 0,
          creator_id: 'creator',
          creator_name: '创建人',
          assign_method: 'by_ratio',
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

function listWithMany(names: string[]) {
  const response = listWith(names[0] || '任务', 'running', 'sampling')
  const base = response.data.items[0]
  response.data.items = names.map((name) => ({ ...base, id: name, task_number: name, task_name: name }))
  response.data.total = names.length
  return response
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
        'a-modal': AModalStub,
        'a-progress': true,
        'a-radio': true,
        'a-radio-group': true,
        'a-range-picker': true,
        'a-select': ASelectStub,
        'a-table': ATableStub,
        'a-tag': true,
        CreateTaskDrawer: true,
        TaskDetailDrawer: TaskDetailDrawerStub,
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
    mocks.getTaskAssigneeOptions.mockResolvedValue({ success: true, data: [] })
    mocks.assignTask.mockResolvedValue({ success: true, data: { total_assigned: 1 } })
    mocks.assignTasksBatch.mockResolvedValue({
      success: true,
      data: { total: 1, success_count: 1, failed_count: 0, atomic: false, items: [] },
    })
    authState.user = { id: 'creator' }
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

  it('任务行分析打开所选任务，并仅允许回到同一任务详情', async () => {
    mocks.getTaskList.mockResolvedValue(listWith('分析任务'))
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-row-analysis"]').trigger('click')
    const drawer = wrapper.findComponent(TaskAnalysisDrawer)
    expect(drawer.props()).toMatchObject({ open: true, taskId: '分析任务' })
    drawer.vm.$emit('view-detail', '其他任务')
    await nextTick()
    expect(wrapper.findComponent(TaskDetailDrawerStub).props('open')).toBe(false)
    drawer.vm.$emit('view-detail', '分析任务')
    await nextTick()
    expect(drawer.props('open')).toBe(false)
    expect(wrapper.findComponent(TaskDetailDrawerStub).props()).toMatchObject({
      open: true, taskId: '分析任务', tab: 'all',
    })
  })

  it('顶部分析选择在列表变化后拒绝陈旧任务', async () => {
    mocks.getTaskList.mockResolvedValue(listWith('当前任务'))
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      analysisSelection: string | undefined
      handleTaskAnalysis: () => void
      confirmAnalysisSelection: () => void
    }
    vm.handleTaskAnalysis()
    vm.analysisSelection = '已移出列表'
    vm.confirmAnalysisSelection()
    await nextTick()
    expect(wrapper.findComponent(TaskAnalysisDrawer).props('open')).toBe(false)
    expect(mocks.message.warning).toHaveBeenCalledWith('任务列表已变化，请重新选择任务')
    vm.analysisSelection = '当前任务'
    vm.confirmAnalysisSelection()
    await nextTick()
    expect(wrapper.findComponent(TaskAnalysisDrawer).props()).toMatchObject({ open: true, taskId: '当前任务' })
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

  it('历史 NULL 场景在列表显示为未标注，详情以 all 范围打开共享抽屉', async () => {
    mocks.getTaskList.mockResolvedValueOnce(listWith('历史任务', null))
    const wrapper = await mountView()
    const vm = wrapper.vm as unknown as {
      sceneLabel: (scene?: string | null) => string
      handleViewDetail: (record: { id: string; task_name: string; scene: null }) => void
    }

    expect(vm.sceneLabel(null)).toBe('未标注')
    vm.handleViewDetail({ id: 'task/with long id', task_name: '历史任务', scene: null })
    await nextTick()

    expect(wrapper.getComponent(TaskDetailDrawerStub).props()).toMatchObject({
      open: true,
      taskId: 'task/with long id',
      tab: 'all',
    })
  })

  it('单条抽样中任务从表格打开分配；空目录禁用确认，失败可重试', async () => {
    mocks.getTaskList.mockResolvedValueOnce(listWith('抽样任务', 'running', 'sampling'))
    mocks.getTaskAssigneeOptions.mockResolvedValueOnce({ success: false, message: '目录故障' })
      .mockResolvedValueOnce({ success: true, data: [] })
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="assign-error"]').text()).toContain('目录故障')
    await wrapper.get('[data-testid="assign-error"] button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="assign-empty"]').text()).toContain('暂无可分配的质控员')
    expect(wrapper.get('[data-testid="assign-confirm"]').attributes('disabled')).toBeDefined()
    expect(mocks.assignTask).not.toHaveBeenCalled()
  })

  it('仅创建人、比例分配、抽样中且身份已就绪时显示入口', async () => {
    mocks.getTaskList.mockResolvedValueOnce(listWith('抽样任务', 'running', 'sampling'))
    authState.user = null
    let wrapper = await mountView()
    expect(wrapper.get('[data-testid="task-row"]').text()).not.toContain('分配')
    wrapper.unmount()

    authState.user = { id: 'other' }
    mocks.getTaskList.mockResolvedValueOnce(listWith('抽样任务', 'running', 'sampling'))
    wrapper = await mountView()
    expect(wrapper.get('[data-testid="task-row"]').text()).not.toContain('分配')
    wrapper.unmount()

    authState.user = { id: 'creator' }
    const wrongMethod = listWith('抽样任务', 'running', 'sampling')
    wrongMethod.data.items[0].assign_method = 'keep'
    mocks.getTaskList.mockResolvedValueOnce(wrongMethod)
    wrapper = await mountView()
    expect(wrapper.get('[data-testid="task-row"]').text()).not.toContain('分配')
    wrapper.unmount()
  })

  it('切换/关闭弹窗时忽略旧目录响应', async () => {
    mocks.getTaskList.mockResolvedValueOnce(listWith('抽样任务', 'running', 'sampling'))
    const old = deferred<{ success: boolean; data: Array<{ user_id: string; user_name: string }> }>()
    mocks.getTaskAssigneeOptions.mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce({ success: true, data: [] })
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await wrapper.get('[data-testid="assign-cancel"]').trigger('click')
    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await flushPromises()
    old.resolve({ success: true, data: [{ user_id: 'stale', user_name: '旧人员' }] })
    await flushPromises()
    expect(wrapper.find('[data-testid="assign-empty"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('旧人员')
  })

  it('确认只发送真实候选；双击不重复写，成功后重读列表统计和已开详情', async () => {
    mocks.getTaskList.mockResolvedValueOnce(listWith('抽样任务', 'running', 'sampling'))
    mocks.getTaskAssigneeOptions.mockResolvedValueOnce({ success: true, data: [{ user_id: 'qc-1', user_name: '质控员甲', department: '质控科' }] })
    const pending = deferred<{ success: boolean; data: { total_assigned: number } }>()
    mocks.assignTask.mockReturnValueOnce(pending.promise)
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await flushPromises()
    const vm = wrapper.vm as unknown as { handleViewDetail: (record: { id: string }) => void }
    await wrapper.get('[data-testid="assign-candidates"]').trigger('click')
    vm.handleViewDetail({ id: '抽样任务' })
    await nextTick()
    const initialDrawer = wrapper.getComponent(TaskDetailDrawerStub).element
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    expect(mocks.assignTask).toHaveBeenCalledTimes(1)
    expect(mocks.assignTask).toHaveBeenCalledWith('抽样任务', {
      method: 'by_ratio', assignees: [{ user_id: 'qc-1', user_name: '质控员甲', department: '质控科' }],
    })
    pending.resolve({ success: true, data: { total_assigned: 1 } })
    await flushPromises()
    expect(mocks.getTaskList).toHaveBeenCalledTimes(2)
    expect(mocks.getTaskStats).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="assign-dialog"]').exists()).toBe(false)
    expect(wrapper.getComponent(TaskDetailDrawerStub).element).not.toBe(initialDrawer)
  })

  it('409/503 和未知结果均不乐观关闭，也不自动重试写入', async () => {
    mocks.getTaskList.mockResolvedValue(listWith('抽样任务', 'running', 'sampling'))
    mocks.getTaskAssigneeOptions.mockResolvedValue({ success: true, data: [{ user_id: 'qc-1', user_name: '质控员甲' }] })
    mocks.assignTask.mockResolvedValueOnce({ success: false, message: '任务已变化（409）' })
      .mockResolvedValueOnce({ success: false, message: '服务不可用（503）' })
      .mockRejectedValueOnce(new Error('timeout'))
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="assign-candidates"]').trigger('click')
    await nextTick()
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="assign-submit-error"]').text()).toContain('409')
    expect(wrapper.get('[data-testid="assign-confirm"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    expect(mocks.assignTask).toHaveBeenCalledTimes(1)
    expect(mocks.getTaskList).toHaveBeenCalledTimes(1)
    expect(mocks.getTaskStats).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="assign-cancel"]').trigger('click')
    await flushPromises()
    expect(mocks.getTaskList).toHaveBeenCalledTimes(2)
    expect(mocks.getTaskStats).toHaveBeenCalledTimes(2)

    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="assign-candidates"]').trigger('click')
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="assign-submit-error"]').text()).toContain('503')
    await wrapper.get('[data-testid="assign-cancel"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="assign-candidates"]').trigger('click')
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="assign-submit-error"]').text()).toContain('结果未知')
    expect(wrapper.get('[data-testid="assign-confirm"]').attributes('disabled')).toBeDefined()
    expect(mocks.assignTask).toHaveBeenCalledTimes(3)
  })

  it('失败后关闭需等列表刷新成功才允许重新打开', async () => {
    mocks.getTaskList.mockResolvedValueOnce(listWith('抽样任务', 'running', 'sampling'))
    mocks.getTaskAssigneeOptions.mockResolvedValue({ success: true, data: [{ user_id: 'qc-1', user_name: '质控员甲' }] })
    mocks.assignTask.mockResolvedValueOnce({ success: false, message: '任务已变化' })
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="assign-candidates"]').trigger('click')
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await flushPromises()
    const pending = deferred<ReturnType<typeof listWith>>()
    mocks.getTaskList.mockReturnValueOnce(pending.promise)
    await wrapper.get('[data-testid="assign-cancel"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="task-row"]').exists()).toBe(false)
    expect(mocks.getTaskAssigneeOptions).toHaveBeenCalledTimes(1)
    pending.resolve(listWith('抽样任务', 'running', 'sampling'))
    await flushPromises()
    expect(wrapper.get('[data-testid="task-row"]').text()).toContain('分配')
  })

  it('原质控员任务按保存的 fallback 提交，成功后展示每人数量与来源分布', async () => {
    const list = listWith('原质控员任务', 'final', 'sampling')
    Object.assign(list.data.items[0], { assign_method: 'by_original_reviewer', assignee_config: { fallback: 'by_ratio' } })
    mocks.getTaskList.mockResolvedValue(list)
    mocks.getTaskAssigneeOptions.mockResolvedValueOnce({ success: true, data: [{ user_id: 'qc-1', user_name: '质控员甲' }] })
    const assignResult = {
      total_assigned: 3,
      assignment_details: [{ user_id: 'qc-1', user_name: '质控员甲', count: 3, reason_counts: { original_reviewer: 2, ratio_fallback: 1 } }],
    }
    mocks.assignTask.mockResolvedValueOnce({ success: true, data: assignResult })
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="assign-method-label"]').text()).toContain('原质控员')
    await wrapper.get('[data-testid="assign-candidates"]').trigger('click')
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await flushPromises()
    expect(mocks.assignTask).toHaveBeenCalledWith('原质控员任务', {
      method: 'by_original_reviewer', fallback: 'by_ratio', assignees: [{ user_id: 'qc-1', user_name: '质控员甲' }],
    })
    const result = wrapper.getComponent(TaskAssignmentResult)
    expect(result.props('result')).toEqual(assignResult)
    expect(result.props('taskName')).toBe('原质控员任务')
  })

  it('原质控员任务缺少保存的 fallback 时须在分配时显式选择', async () => {
    const list = listWith('待选处理', 'final', 'sampling')
    Object.assign(list.data.items[0], { assign_method: 'by_original_reviewer' })
    mocks.getTaskList.mockResolvedValue(list)
    mocks.getTaskAssigneeOptions.mockResolvedValueOnce({ success: true, data: [{ user_id: 'qc-1', user_name: '质控员甲' }] })
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="assign-candidates"]').trigger('click')
    await nextTick()
    expect(wrapper.get('[data-testid="assign-confirm"]').attributes('disabled')).toBeDefined()
    const vm = wrapper.vm as unknown as { assignFallback: string }
    vm.assignFallback = 'reject'
    await nextTick()
    expect(wrapper.get('[data-testid="assign-confirm"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await flushPromises()
    expect(mocks.assignTask).toHaveBeenCalledWith('待选处理', expect.objectContaining({ method: 'by_original_reviewer', fallback: 'reject' }))
  })

  it.each([
    [{ code: 'department_unassigned', departments: ['内科', '外科'] }, '以下科室没有对应科室的受领人：内科、外科'],
    [{ code: 'department_missing' }, '存在缺少科室的病历'],
    [{ code: 'original_reviewer_unmatched', unmatched_count: 5 }, '有 5 条病历无原质控员'],
  ])('409 策略业务码 %o 给出明确提示且不锁定重试', async (detail, text) => {
    const isDepartment = detail.code.startsWith('department')
    const list = listWith('科室任务', 'final', 'sampling')
    Object.assign(list.data.items[0], { assign_method: isDepartment ? 'by_department' : 'by_original_reviewer', assignee_config: { fallback: 'reject' } })
    mocks.getTaskList.mockResolvedValue(list)
    mocks.getTaskAssigneeOptions.mockResolvedValueOnce({ success: true, data: [{ user_id: 'qc-1', user_name: '质控员甲', department: '内科' }] })
    mocks.assignTask.mockResolvedValueOnce({ success: false, status: 409, code: detail.code, errorDetail: detail, message: '冲突' })
    const wrapper = await mountView()
    await wrapper.get('[data-testid="task-row-assign"]').trigger('click')
    await flushPromises()
    if (isDepartment) {
      expect(wrapper.get('[data-testid="assign-department-hint"]').text()).toContain('按其账号科室匹配病历科室')
    }
    await wrapper.get('[data-testid="assign-candidates"]').trigger('click')
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="assign-submit-error"]').text()).toContain(text)
    expect(wrapper.get('[data-testid="assign-confirm"]').attributes('disabled')).toBeUndefined()
    expect(mocks.getTaskList).toHaveBeenCalledTimes(1)
    expect(wrapper.findComponent(TaskAssignmentResult).exists()).toBe(false)
  })

  it('批量分配逐项提交策略，只清成功项并保留失败项重试', async () => {
    const list = listWithMany(['比例任务', '科室任务'])
    list.data.items[1].assign_method = 'by_department'
    mocks.getTaskList.mockResolvedValue(list)
    mocks.getTaskAssigneeOptions.mockResolvedValue({
      success: true, data: [{ user_id: 'qc-1', user_name: '质控员甲', department: '内科' }],
    })
    mocks.assignTasksBatch
      .mockResolvedValueOnce({
        success: true,
        message: '部分完成',
        data: {
          total: 2, success_count: 1, failed_count: 1, atomic: false,
          items: [
            { task_id: '比例任务', success: true, result: { total_assigned: 2 } },
            { task_id: '科室任务', success: false, status: 409, message: '儿科没有受领人' },
          ],
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          total: 1, success_count: 1, failed_count: 0, atomic: false,
          items: [{ task_id: '科室任务', success: true, result: { total_assigned: 1 } }],
        },
      })
    const wrapper = await mountView()

    await wrapper.get('[data-testid="select-batch-tasks"]').trigger('click')
    await nextTick()
    expect(wrapper.get('[data-testid="batch-assign-button"]').text()).toContain('2')
    await wrapper.get('[data-testid="batch-assign-button"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="batch-assign-contract"]').text()).toContain('独立提交')
    await wrapper.get('[data-testid="assign-candidates"]').trigger('click')
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await flushPromises()

    expect(mocks.assignTasksBatch).toHaveBeenNthCalledWith(1, {
      tasks: [
        { task_id: '比例任务', method: 'by_ratio' },
        { task_id: '科室任务', method: 'by_department' },
      ],
      assignees: [{ user_id: 'qc-1', user_name: '质控员甲', department: '内科' }],
    })
    expect(wrapper.get('[data-testid="assign-submit-error"]').text()).toContain('儿科没有受领人')
    const vm = wrapper.vm as unknown as { selectedBatchTaskIds: string[]; batchAssigningTasks: Array<{ id: string }> }
    expect(vm.selectedBatchTaskIds).toEqual(['科室任务'])
    expect(vm.batchAssigningTasks.map((task) => task.id)).toEqual(['科室任务'])

    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await flushPromises()
    expect(mocks.assignTasksBatch).toHaveBeenNthCalledWith(2, expect.objectContaining({
      tasks: [{ task_id: '科室任务', method: 'by_department' }],
    }))
    expect(wrapper.find('[data-testid="assign-dialog"]').exists()).toBe(false)
    expect(vm.selectedBatchTaskIds).toEqual([])
  })

  it('批量响应未知时锁定再次写入，关闭刷新后清理服务端已完成项', async () => {
    mocks.getTaskList
      .mockResolvedValueOnce(listWithMany(['任务一']))
      .mockResolvedValueOnce(listWith('任务一', 'running', 'assigned'))
    mocks.getTaskAssigneeOptions.mockResolvedValue({
      success: true, data: [{ user_id: 'qc-1', user_name: '质控员甲' }],
    })
    mocks.assignTasksBatch.mockResolvedValueOnce({ success: false, message: '网关超时' })
    const wrapper = await mountView()
    await wrapper.get('[data-testid="select-batch-tasks"]').trigger('click')
    await wrapper.get('[data-testid="batch-assign-button"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="assign-candidates"]').trigger('click')
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      assignSubmitting: boolean
      assignRecoveryRequired: boolean
      selectedBatchTaskIds: string[]
    }
    expect(vm.assignSubmitting).toBe(false)
    expect(vm.assignRecoveryRequired).toBe(true)
    expect(wrapper.get('[data-testid="assign-confirm"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="assign-confirm"]').trigger('click')
    expect(mocks.assignTasksBatch).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="assign-cancel"]').trigger('click')
    await flushPromises()
    expect(mocks.getTaskList).toHaveBeenCalledTimes(2)
    expect(vm.assignRecoveryRequired).toBe(false)
    expect(vm.selectedBatchTaskIds).toEqual([])
  })
})
