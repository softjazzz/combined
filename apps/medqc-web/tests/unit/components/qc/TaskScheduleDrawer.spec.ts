import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import dayjs, { type Dayjs } from 'dayjs'

const mocks = vi.hoisted(() => ({
  getTaskList: vi.fn(),
  getTaskEdit: vi.fn(),
  listTaskSchedules: vi.fn(),
  createTaskSchedule: vi.fn(),
  getTaskSchedule: vi.fn(),
  pauseTaskSchedule: vi.fn(),
  resumeTaskSchedule: vi.fn(),
  cancelTaskSchedule: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  confirm: vi.fn(),
}))
const authState = vi.hoisted(() => ({ user: { id: 'u-1' } as { id: string } | null }))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => authState }))
vi.mock('@/api/tasks', () => ({ getTaskList: mocks.getTaskList }))
vi.mock('@/api/taskEdits', () => ({ getTaskEdit: mocks.getTaskEdit }))
vi.mock('@/api/taskSchedules', () => ({
  listTaskSchedules: mocks.listTaskSchedules,
  createTaskSchedule: mocks.createTaskSchedule,
  getTaskSchedule: mocks.getTaskSchedule,
  pauseTaskSchedule: mocks.pauseTaskSchedule,
  resumeTaskSchedule: mocks.resumeTaskSchedule,
  cancelTaskSchedule: mocks.cancelTaskSchedule,
}))
vi.mock('ant-design-vue', () => ({
  Modal: { confirm: mocks.confirm },
  message: mocks.message,
}))
vi.mock('@ant-design/icons-vue', () => {
  const icon = { template: '<span />' }
  return {
    HistoryOutlined: icon,
    PlayCircleOutlined: icon,
    PlusOutlined: icon,
    ReloadOutlined: icon,
  }
})

import TaskScheduleDrawer from '@/components/qc/TaskScheduleDrawer.vue'
import type { TaskEditDetail } from '@/api/taskEdits'
import type { TaskItem } from '@/api/tasks'
import type { TaskScheduleResponse } from '@/api/taskSchedules'

const sourceTask: TaskItem = {
  id: 'task-1',
  task_number: 'QC-001',
  task_name: '每日运行质控',
  task_type: 'one_time',
  status: 'draft',
  progress: 0,
  total_records: 0,
  completed_records: 0,
  creator_id: 'u-1',
  creator_name: '管理员',
  scene: 'running',
  rule_set_key: 'luxian-0609',
  rule_set_version: 'v1',
  sampling_method: 'count',
  sampling_config: { case_scope: 'active', total: 20 },
  assign_method: 'by_ratio',
  assignee_config: null,
  created_at: '2026-09-28T08:00:00+08:00',
  updated_at: '2026-09-28T08:00:00+08:00',
}

const sourceDetail: TaskEditDetail = {
  id: 'task-1',
  task_number: 'QC-001',
  task_name: '每日运行质控',
  task_type: 'one_time',
  status: 'draft',
  scene: 'running',
  rule_set_key: 'luxian-0609',
  rule_set_version: 'v1',
  deadline: null,
  date_range: null,
  department_filter: ['内科'],
  record_refs: [],
  sampling_method: 'count',
  sampling_config: { case_scope: 'active', total: 20 },
  assign_method: 'by_ratio',
  assignee_config: null,
  configuration_version: 3,
  editable_fields: [
    'task_name',
    'deadline',
    'date_range',
    'department_filter',
    'record_refs',
    'sampling_method',
    'sampling_config',
    'assign_method',
    'assignee_config',
  ],
  updated_at: '2026-09-28T08:00:00+08:00',
}

const schedule: TaskScheduleResponse = {
  id: 'schedule-1',
  source_task_id: 'task-1',
  owner_id: 'u-1',
  name: '每日运行质控',
  scene: 'running',
  rule_set_key: 'luxian-0609',
  rule_set_version: 'v1',
  task_config: {
    date_range: null,
    department_filter: ['内科'],
    sampling_method: 'count',
    sampling_config: { case_scope: 'active', total: 20 },
    assign_method: 'by_ratio',
    assignee_config: {},
  },
  timing_config: {
    kind: 'daily',
    timezone: 'Asia/Shanghai',
    time: '09:00',
    start_date: '2026-10-01',
    end_date: null,
  },
  state: 'active',
  next_fire_at: '2026-10-01T09:00:00+08:00',
  last_fire_at: null,
  version: 1,
  created_at: '2026-09-28T09:00:00+08:00',
  updated_at: '2026-09-28T09:00:00+08:00',
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function mountDrawer(props: Record<string, unknown> = {}) {
  return shallowMount(TaskScheduleDrawer, {
    props: { open: true, sourceTaskId: 'task-1', ...props },
    global: {
      stubs: {
        TaskScheduleRunsDrawer: true,
        'a-alert': {
          props: ['message'],
          template: '<div>{{ message }}<slot name="action" /></div>',
        },
        'a-button': {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
        'a-checkbox-group': true,
        'a-date-picker': true,
        'a-descriptions': { template: '<dl><slot /></dl>' },
        'a-descriptions-item': { template: '<div><slot /></div>' },
        'a-drawer': { template: '<div><slot /></div>' },
        'a-empty': true,
        'a-form': { template: '<form><slot /></form>' },
        'a-form-item': { template: '<div><slot /></div>' },
        'a-input-number': true,
        'a-pagination': true,
        'a-radio-button': { template: '<label><slot /></label>' },
        'a-radio-group': { template: '<div><slot /></div>' },
        'a-segmented': true,
        'a-select': true,
        'a-spin': { template: '<div><slot /></div>' },
        'a-tag': { template: '<span><slot /></span>' },
        'a-time-picker': true,
        'a-tooltip': { template: '<span><slot /></span>' },
      },
    },
  })
}

describe('TaskScheduleDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    vi.stubGlobal('crypto', { randomUUID: () => 'create-request-1' })
    authState.user = { id: 'u-1' }
    mocks.getTaskList.mockResolvedValue({
      success: true,
      data: { items: [sourceTask], total: 1, page: 1, page_size: 100 },
    })
    mocks.getTaskEdit.mockResolvedValue({ success: true, data: sourceDetail })
    mocks.listTaskSchedules.mockResolvedValue({
      success: true,
      data: { items: [schedule], total: 1, page: 1, page_size: 20 },
    })
    mocks.createTaskSchedule.mockResolvedValue({ success: true, data: schedule })
    mocks.getTaskSchedule.mockResolvedValue({ success: true, data: schedule })
    mocks.pauseTaskSchedule.mockResolvedValue({
      success: true,
      data: { ...schedule, state: 'paused', version: 2 },
    })
    mocks.resumeTaskSchedule.mockResolvedValue({ success: true, data: { ...schedule, version: 2 } })
    mocks.cancelTaskSchedule.mockResolvedValue({
      success: true,
      data: { ...schedule, state: 'cancelled', version: 2 },
    })
    mocks.confirm.mockImplementation((options: { onOk?: () => unknown }) => options.onOk?.())
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('创建只引用已核实源草稿和版本，不重拼抽样或分配配置', async () => {
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      timingKind: 'once' | 'daily' | 'weekly'
      startDate: Dayjs | null
      endDate: Dayjs | null
      executionTime: Dayjs | null
      weekdays: number[]
      confirmCreate: () => void
    }
    vm.timingKind = 'weekly'
    vm.startDate = dayjs('2026-10-01')
    vm.endDate = dayjs('2026-12-31')
    vm.executionTime = dayjs().hour(9).minute(5)
    vm.weekdays = [5, 1, 3, 3]
    vm.confirmCreate()
    await flushPromises()
    expect(mocks.createTaskSchedule).toHaveBeenCalledWith(
      {
        source_task_id: 'task-1',
        source_configuration_version: 3,
        timing_config: {
          kind: 'weekly',
          timezone: 'Asia/Shanghai',
          time: '09:05',
          start_date: '2026-10-01',
          end_date: '2026-12-31',
          weekdays: [1, 3, 5],
        },
      },
      expect.any(String),
    )
    const payload = mocks.createTaskSchedule.mock.calls[0][0]
    expect(payload).not.toHaveProperty('task_config')
    expect(payload).not.toHaveProperty('sampling_config')
    expect(payload).not.toHaveProperty('assign_method')
  })

  it('终末草稿在原抽屉创建月计划并显示上一完整周期口径', async () => {
    const finalTask = {
      ...sourceTask,
      id: 'task-final',
      task_name: '终末病历月度抽查',
      scene: 'final' as const,
      rule_set_key: 'sc_content_launch_a_v1',
      rule_set_version: '2026-04-24',
      sampling_config: { case_scope: 'discharged', total: 20 },
    }
    const finalDetail = {
      ...sourceDetail,
      id: finalTask.id,
      task_name: finalTask.task_name,
      scene: finalTask.scene,
      rule_set_key: finalTask.rule_set_key,
      rule_set_version: finalTask.rule_set_version,
      sampling_config: finalTask.sampling_config,
      deadline: null,
      date_range: { start: '2026-09-01', end: '2026-09-30' },
      record_refs: [],
      configuration_version: 3,
      editable_fields: sourceDetail.editable_fields,
      updated_at: sourceDetail.updated_at,
    } satisfies TaskEditDetail
    mocks.getTaskList.mockResolvedValue({
      success: true,
      data: { items: [finalTask], total: 1, page: 1, page_size: 100 },
    })
    mocks.getTaskEdit.mockResolvedValue({ success: true, data: finalDetail })
    const wrapper = mountDrawer({ sourceTaskId: 'task-final' })
    await flushPromises()
    expect(wrapper.text()).toContain('上一完整自然周期')
    expect(wrapper.text()).toContain('归档状态未核验')
    const vm = wrapper.vm as unknown as {
      timingKind: 'once' | 'daily' | 'weekly' | 'monthly'
      startDate: Dayjs | null
      executionTime: Dayjs | null
      monthDay: number
      confirmCreate: () => void
    }
    expect(vm.timingKind).toBe('daily')
    vm.timingKind = 'monthly'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('当月不足该日时，在当月最后一日执行')
    vm.startDate = dayjs('2026-10-01')
    vm.executionTime = dayjs().hour(8).minute(30)
    vm.monthDay = 1
    vm.confirmCreate()
    await flushPromises()
    expect(mocks.createTaskSchedule).toHaveBeenCalledWith(
      {
        source_task_id: 'task-final',
        source_configuration_version: 3,
        timing_config: {
          kind: 'monthly',
          timezone: 'Asia/Shanghai',
          time: '08:30',
          start_date: '2026-10-01',
          end_date: null,
          day: 1,
        },
      },
      expect.any(String),
    )
  })

  it('源草稿详情失败或不完整时不使用默认配置创建', async () => {
    mocks.getTaskEdit.mockResolvedValue({ success: false, message: '源任务无权访问' })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      sourceDetail: TaskEditDetail | null
      sourceDetailError: string
      confirmCreate: () => void
    }
    expect(vm.sourceDetail).toBeNull()
    expect(vm.sourceDetailError).toBe('源任务无权访问')
    vm.confirmCreate()
    expect(mocks.createTaskSchedule).not.toHaveBeenCalled()
  })

  it('会话存储不可用时失败关闭，不发起无法保护幂等性的创建请求', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked')
    })
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new DOMException('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked')
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      onceDate: Dayjs | null
      confirmCreate: () => void
    }
    vm.onceDate = dayjs('2026-10-01')
    vm.confirmCreate()
    await flushPromises()
    expect(mocks.createTaskSchedule).not.toHaveBeenCalled()
    expect(mocks.message.error).toHaveBeenCalledWith('无法保存安全请求编号，未发起计划创建')
  })

  it('状态动作携带 CAS 版本，确认后账号变化不会写入', async () => {
    let confirmOptions: { onOk?: () => unknown } | undefined
    mocks.confirm.mockImplementationOnce((options: { onOk?: () => unknown }) => {
      confirmOptions = options
    })
    const wrapper = mountDrawer({ sourceTaskId: null })
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      confirmAction: (item: TaskScheduleResponse, action: 'pause') => void
    }
    vm.confirmAction(schedule, 'pause')
    authState.user = { id: 'u-2' }
    await wrapper.vm.$nextTick()
    await confirmOptions?.onOk?.()
    expect(mocks.pauseTaskSchedule).not.toHaveBeenCalled()

    authState.user = { id: 'u-1' }
    await wrapper.vm.$nextTick()
    mocks.confirm.mockImplementationOnce((options: { onOk?: () => unknown }) => options.onOk?.())
    vm.confirmAction(schedule, 'pause')
    await flushPromises()
    expect(mocks.pauseTaskSchedule).toHaveBeenCalledWith('schedule-1', { version: 1 })
  })

  it('网络或坏回执后锁定同一源草稿，列表未确认前不能重复创建', async () => {
    mocks.createTaskSchedule.mockResolvedValue({
      success: false,
      uncertain: true,
      message: '结果未知',
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      timingKind: 'once'
      onceDate: Dayjs | null
      executionTime: Dayjs | null
      sourceLockedByUnknownResult: boolean
      confirmCreate: () => void
    }
    vm.onceDate = dayjs('2026-10-01')
    vm.executionTime = dayjs().hour(9).minute(0)
    vm.confirmCreate()
    await flushPromises()
    expect(vm.sourceLockedByUnknownResult).toBe(true)
    vm.confirmCreate()
    expect(mocks.createTaskSchedule).toHaveBeenCalledTimes(1)
    wrapper.unmount()

    const restored = mountDrawer()
    await flushPromises()
    const restoredVm = restored.vm as unknown as { reconcileUnknownCreate: () => Promise<void> }
    await restoredVm.reconcileUnknownCreate()
    expect(mocks.createTaskSchedule.mock.calls.map((call) => call[1])).toEqual([
      'create-request-1',
      'create-request-1',
    ])
  })

  it('待核实创建按账号与源草稿隔离，切回原账号仍恢复原锁', async () => {
    mocks.createTaskSchedule.mockResolvedValue({
      success: false,
      uncertain: true,
      message: '结果未知',
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      onceDate: Dayjs | null
      confirmCreate: () => void
    }
    vm.onceDate = dayjs('2026-10-01')
    vm.confirmCreate()
    await flushPromises()
    wrapper.unmount()

    authState.user = { id: 'u-2' }
    const otherActor = mountDrawer()
    await flushPromises()
    expect(
      (otherActor.vm as unknown as { sourceLockedByUnknownResult: boolean })
        .sourceLockedByUnknownResult,
    ).toBe(false)
    otherActor.unmount()

    authState.user = { id: 'u-1' }
    const originalActor = mountDrawer()
    await flushPromises()
    expect(
      (originalActor.vm as unknown as { sourceLockedByUnknownResult: boolean })
        .sourceLockedByUnknownResult,
    ).toBe(true)
  })

  it('确定的 request_conflict 清除旧请求号，允许重新确认创建', async () => {
    mocks.createTaskSchedule.mockResolvedValue({
      success: false,
      uncertain: false,
      code: 'request_conflict',
      message: '请求编号已绑定其他载荷',
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      onceDate: Dayjs | null
      sourceLockedByUnknownResult: boolean
      confirmCreate: () => void
    }
    vm.onceDate = dayjs('2026-10-01')
    vm.confirmCreate()
    await flushPromises()
    expect(vm.sourceLockedByUnknownResult).toBe(false)
    vm.confirmCreate()
    await flushPromises()
    expect(mocks.createTaskSchedule).toHaveBeenCalledTimes(2)
  })

  it('未知创建使用原请求号核对成功后退出等待并回到列表', async () => {
    mocks.createTaskSchedule
      .mockResolvedValueOnce({ success: false, uncertain: true, message: '结果未知' })
      .mockResolvedValueOnce({ success: true, data: schedule })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      onceDate: Dayjs | null
      viewMode: 'list' | 'create'
      reconcilingCreate: boolean
      confirmCreate: () => void
      reconcileUnknownCreate: () => Promise<void>
    }
    vm.onceDate = dayjs('2026-10-01')
    vm.confirmCreate()
    await flushPromises()
    await vm.reconcileUnknownCreate()
    expect(vm.reconcilingCreate).toBe(false)
    expect(vm.viewMode).toBe('list')
    expect(wrapper.emitted('changed')?.at(-1)).toEqual(['schedule-1'])
  })

  it('创建请求期间切换源任务，原请求仍按存储键收口且释放提交状态', async () => {
    const pending = deferred<{ success: boolean; data: TaskScheduleResponse }>()
    mocks.createTaskSchedule.mockReturnValueOnce(pending.promise)
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      onceDate: Dayjs | null
      creating: boolean
      confirmCreate: () => void
      handleSourceChange: (taskId: string) => void
    }
    vm.onceDate = dayjs('2026-10-01')
    vm.confirmCreate()
    await wrapper.vm.$nextTick()
    expect(vm.creating).toBe(true)
    mocks.getTaskEdit.mockResolvedValueOnce({
      success: true,
      data: { ...sourceDetail, id: 'task-2' },
    })
    vm.handleSourceChange('task-2')
    pending.resolve({ success: true, data: schedule })
    await flushPromises()
    expect(vm.creating).toBe(false)
    expect(mocks.createTaskSchedule).toHaveBeenCalledTimes(1)
  })
})
