import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import dayjs from 'dayjs'

const mocks = vi.hoisted(() => ({
  getTaskEdit: vi.fn(),
  updateTaskDraftConfiguration: vi.fn(),
  updateTaskMetadata: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  confirm: vi.fn(),
}))
const authState = vi.hoisted(() => ({ user: { id: 'u-1' } as { id: string } | null }))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => authState }))
vi.mock('@/api/taskEdits', () => ({
  getTaskEdit: mocks.getTaskEdit,
  updateTaskDraftConfiguration: mocks.updateTaskDraftConfiguration,
  updateTaskMetadata: mocks.updateTaskMetadata,
}))
vi.mock('ant-design-vue', () => ({
  Modal: { confirm: mocks.confirm },
  message: mocks.message,
}))
vi.mock('@ant-design/icons-vue', () => {
  const icon = { template: '<span />' }
  return { DeleteOutlined: icon, PlusOutlined: icon, ReloadOutlined: icon, SaveOutlined: icon }
})

import TaskEditDrawer from '@/components/qc/TaskEditDrawer.vue'
import type { TaskEditDetail } from '@/api/taskEdits'

const detail: TaskEditDetail = {
  id: 'task-1',
  task_number: 'QC-001',
  task_name: '原任务',
  task_type: 'one_time',
  status: 'draft',
  scene: 'running',
  rule_set_key: 'luxian-0609',
  rule_set_version: 'v1',
  deadline: '2026-10-10',
  date_range: { start: '2026-09-01', end: '2026-09-30' },
  department_filter: ['内科'],
  record_refs: [],
  sampling_method: 'count',
  sampling_config: { case_scope: 'active', total: 20, by_department: true },
  assign_method: 'by_original_reviewer',
  assignee_config: { fallback: 'by_ratio' },
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
  updated_at: '2026-09-27T10:00:00Z',
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function mountDrawer(props: Record<string, unknown> = {}) {
  return shallowMount(TaskEditDrawer, {
    props: { open: true, taskId: 'task-1', ...props },
    global: {
      stubs: {
        'a-alert': {
          props: ['message'],
          template: '<div><span>{{ message }}</span><slot name="action" /></div>',
        },
        'a-button': {
          emits: ['click'],
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
        'a-checkbox': true,
        'a-date-picker': true,
        'a-descriptions': { template: '<div><slot /></div>' },
        'a-descriptions-item': { template: '<div><slot /></div>' },
        'a-drawer': { template: '<div><slot /><slot name="footer" /></div>' },
        'a-form': { template: '<form><slot /></form>' },
        'a-form-item': { template: '<div><slot /></div>' },
        'a-input': true,
        'a-input-number': true,
        'a-radio': { template: '<label><slot /></label>' },
        'a-radio-group': { template: '<div><slot /></div>' },
        'a-range-picker': true,
        'a-select': true,
        'a-slider': true,
        'a-spin': { template: '<div><slot /></div>' },
        'a-tag': { template: '<span><slot /></span>' },
      },
    },
  })
}

describe('TaskEditDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.user = { id: 'u-1' }
    mocks.getTaskEdit.mockResolvedValue({ success: true, data: detail })
    mocks.updateTaskDraftConfiguration.mockResolvedValue({
      success: true,
      data: { ...detail, task_name: '新任务', configuration_version: 4 },
    })
    mocks.updateTaskMetadata.mockResolvedValue({
      success: true,
      data: { ...detail, task_name: '新任务', configuration_version: 4 },
    })
    mocks.confirm.mockImplementation((options: { onOk?: () => unknown }) => options.onOk?.())
  })

  it('仅改变临床医生也走完整配置编辑并保留机构引用', async () => {
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      clinicalDoctors: import('@/api/tasks').TaskClinicalDoctorRef[]
      confirmSave: () => void
    }
    vm.clinicalDoctors = [{ institute_id: ' SYN-I ', physician_name: ' 张医师 ' }]
    vm.confirmSave()
    await flushPromises()
    expect(mocks.updateTaskDraftConfiguration).toHaveBeenCalledWith(
      'task-1',
      expect.objectContaining({
        sampling_config: {
          case_scope: 'active',
          total: 20,
          by_department: true,
          clinical_doctors: [{ institute_id: 'SYN-I', physician_name: '张医师' }],
        },
      }),
    )
    expect(mocks.updateTaskMetadata).not.toHaveBeenCalled()
  })

  it('仅改变评分上下界也走完整配置编辑并保存标准引用', async () => {
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      scoreFilter: import('@/api/tasks').TaskScoreFilter
      confirmSave: () => void
    }
    vm.scoreFilter = { standard_id: 'SYN-S', score_min: 0, score_max: 80 }
    vm.confirmSave()
    await flushPromises()
    expect(mocks.updateTaskDraftConfiguration).toHaveBeenCalledWith(
      'task-1',
      expect.objectContaining({
        sampling_config: {
          case_scope: 'active',
          total: 20,
          by_department: true,
          score_filter: { standard_id: 'SYN-S', score_min: 0, score_max: 80 },
        },
      }),
    )
    expect(mocks.updateTaskMetadata).not.toHaveBeenCalled()
  })

  it('加载真实详情，冻结场景与规则集，只编辑后端允许字段', async () => {
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      detail: TaskEditDetail | null
      form: { task_name: string; scene: string; rule_set_key: string }
      canEdit: (field: string) => boolean
    }
    expect(mocks.getTaskEdit).toHaveBeenCalledWith('task-1')
    expect(vm.form).toMatchObject({
      task_name: '原任务',
      scene: 'running',
      rule_set_key: 'luxian-0609',
    })
    expect(vm.canEdit('task_name')).toBe(true)
    expect(vm.canEdit('scene')).toBe(false)
    expect(wrapper.text()).toContain('QC-001')
  })

  it('详情读取失败不填充假默认值，也不能提交', async () => {
    mocks.getTaskEdit.mockResolvedValue({ success: false, status: 403, message: '无权编辑任务' })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as { detail: TaskEditDetail | null; confirmSave: () => void }
    expect(vm.detail).toBeNull()
    expect(wrapper.text()).toContain('无权编辑任务')
    vm.confirmSave()
    expect(mocks.confirm).not.toHaveBeenCalled()
  })

  it('草稿全量保存真实范围、三坐标、抽样和分配配置，不发送冻结字段', async () => {
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      form: Record<string, any>
      rangeMode: 'date' | 'refs'
      recordRefs: Array<{ institute_id: string; patient_id: string; visit_id: string }>
      confirmSave: () => void
    }
    vm.form.task_name = '  新任务  '
    vm.form.deadline = dayjs('2026-10-20')
    vm.form.sampling_method = 'percentage'
    vm.form.percentage = 15
    vm.form.group_by = 'department'
    vm.form.assign_method = 'by_original_reviewer'
    vm.form.fallback = 'reject'
    vm.rangeMode = 'refs'
    vm.recordRefs.splice(0, vm.recordRefs.length, {
      institute_id: ' H-1 ',
      patient_id: ' P-1 ',
      visit_id: ' V-1 ',
    })
    vm.confirmSave()
    await flushPromises()

    expect(mocks.updateTaskDraftConfiguration).toHaveBeenCalledWith(
      'task-1',
      expect.objectContaining({
        configuration_version: 3,
        task_name: '新任务',
        deadline: '2026-10-20',
        date_range: null,
        department_filter: [],
        record_refs: [{ institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1' }],
        sampling_method: 'all',
        sampling_config: { case_scope: 'active' },
        assign_method: 'by_original_reviewer',
        assignee_config: { fallback: 'reject' },
      }),
    )
    const sent = mocks.updateTaskDraftConfiguration.mock.calls[0][1]
    expect(sent).not.toHaveProperty('scene')
    expect(sent).not.toHaveProperty('rule_set_key')
    expect(sent).not.toHaveProperty('rule_set_version')
    expect(sent).not.toHaveProperty('record_ids')
    expect(sent).not.toHaveProperty('description')
    expect(wrapper.emitted('saved')?.[0]).toEqual(['task-1'])
  })

  it('每科室比例编辑保留上限并只提交该方式参数', async () => {
    mocks.getTaskEdit.mockResolvedValue({
      success: true,
      data: {
        ...detail,
        sampling_method: 'department_ratio',
        sampling_config: { case_scope: 'active', percentage: 25, max_per_group: 5 },
      },
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as { form: { max_per_group: number }; confirmSave: () => void }
    expect(vm.form.max_per_group).toBe(5)
    vm.form.max_per_group = 3
    vm.confirmSave()
    await flushPromises()
    expect(mocks.updateTaskDraftConfiguration).toHaveBeenCalledWith(
      'task-1',
      expect.objectContaining({
        sampling_method: 'department_ratio',
        sampling_config: { case_scope: 'active', percentage: 25, max_per_group: 3 },
      }),
    )
    wrapper.unmount()
  })

  it('终末指定病例修改规划仍保留出院窗口与三坐标且禁止抽样', async () => {
    const refs = [{ institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1' }]
    const window = { start: '2026-09-01', end: '2026-09-15' }
    mocks.getTaskEdit.mockResolvedValue({
      success: true,
      data: {
        ...detail,
        scene: 'final',
        date_range: window,
        department_filter: [],
        record_refs: refs,
        sampling_config: { case_scope: 'discharged', total: 20 },
      },
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      form: {
        total: number
        dateRange: [ReturnType<typeof dayjs>, ReturnType<typeof dayjs>] | null
      }
      confirmSave: () => void
    }
    expect(wrapper.find('[data-testid="task-edit-refs-discharge-range"]').exists()).toBe(true)
    vm.form.total = 5
    vm.confirmSave()
    await flushPromises()
    expect(mocks.updateTaskDraftConfiguration).toHaveBeenCalledWith(
      'task-1',
      expect.objectContaining({
        date_range: window,
        record_refs: refs,
        department_filter: [],
        sampling_config: { case_scope: 'discharged' },
      }),
    )
    wrapper.unmount()
  })

  it('终末指定病例清空出院窗口时阻止保存', async () => {
    mocks.getTaskEdit.mockResolvedValue({
      success: true,
      data: {
        ...detail,
        scene: 'final',
        department_filter: [],
        record_refs: [{ institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1' }],
        sampling_config: { case_scope: 'discharged', total: 20 },
      },
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      form: { dateRange: null }
      dateRangeTouched: boolean
      confirmSave: () => void
    }
    vm.form.dateRange = null
    vm.dateRangeTouched = true
    vm.confirmSave()
    await flushPromises()
    expect(mocks.message.warning).toHaveBeenCalledWith('终末任务必须选择出院开始日期和结束日期')
    expect(mocks.updateTaskDraftConfiguration).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('sampling/assigned/in_progress 状态只用 PATCH 更新名称或截止日期', async () => {
    const metadataOnly = {
      ...detail,
      status: 'sampling',
      editable_fields: ['task_name', 'deadline'],
    } as TaskEditDetail
    mocks.getTaskEdit.mockResolvedValue({ success: true, data: metadataOnly })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as { form: Record<string, any>; confirmSave: () => void }
    vm.form.task_name = '新任务'
    vm.form.deadline = null
    vm.confirmSave()
    await flushPromises()
    expect(mocks.updateTaskMetadata).toHaveBeenCalledWith('task-1', {
      configuration_version: 3,
      task_name: '新任务',
      deadline: null,
    })
    expect(mocks.updateTaskDraftConfiguration).not.toHaveBeenCalled()
  })

  it('截止日期清空后选回原日，只改名称仍不截断历史时间', async () => {
    const precise = {
      ...detail,
      deadline: '2026-10-10T16:45:30+08:00',
      date_range: {
        start: '2026-09-01T00:00:00+08:00',
        end: '2026-09-30T23:59:59+08:00',
      },
    }
    mocks.getTaskEdit.mockResolvedValue({ success: true, data: precise })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      form: { task_name: string; deadline: ReturnType<typeof dayjs> | null }
      deadlineTouched: boolean
      confirmSave: () => void
    }
    vm.form.deadline = null
    vm.deadlineTouched = true
    vm.form.deadline = dayjs('2026-10-10')
    vm.form.task_name = '仅改名称'
    vm.confirmSave()
    await flushPromises()
    expect(mocks.updateTaskMetadata).toHaveBeenCalledWith('task-1', {
      configuration_version: 3,
      task_name: '仅改名称',
    })
    expect(mocks.updateTaskDraftConfiguration).not.toHaveBeenCalled()

    const metadata = {
      ...precise,
      status: 'assigned',
      editable_fields: ['task_name', 'deadline'],
    } as TaskEditDetail
    mocks.getTaskEdit.mockResolvedValue({ success: true, data: metadata })
    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true })
    await flushPromises()
    const current = wrapper.vm as unknown as {
      form: { task_name: string }
      confirmSave: () => void
    }
    current.form.task_name = '元数据改名'
    current.confirmSave()
    await flushPromises()
    expect(mocks.updateTaskMetadata).toHaveBeenLastCalledWith('task-1', {
      configuration_version: 3,
      task_name: '元数据改名',
    })
  })

  it('相同日期范围选回后修改规划，PUT 原样保留时区截止时间和范围', async () => {
    const precise = {
      ...detail,
      deadline: '2026-10-10T00:30:00+08:00',
      date_range: {
        start: '2026-09-01T00:00:00+08:00',
        end: '2026-09-30T23:59:59+08:00',
      },
      sampling_config: {
        ...detail.sampling_config,
        extension_owner: 'preserve-me',
      },
    }
    mocks.getTaskEdit.mockResolvedValue({ success: true, data: precise })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      form: {
        percentage: number
        sampling_method: string
        dateRange: [ReturnType<typeof dayjs>, ReturnType<typeof dayjs>] | null
      }
      dateRangeTouched: boolean
      confirmSave: () => void
    }
    vm.form.dateRange = null
    vm.dateRangeTouched = true
    vm.form.dateRange = [dayjs('2026-09-01'), dayjs('2026-09-30')]
    vm.form.sampling_method = 'percentage'
    vm.form.percentage = 12
    vm.confirmSave()
    await flushPromises()
    expect(mocks.updateTaskDraftConfiguration).toHaveBeenCalledWith(
      'task-1',
      expect.objectContaining({
        deadline: precise.deadline,
        date_range: precise.date_range,
        sampling_config: expect.objectContaining({
          percentage: 12,
          extension_owner: 'preserve-me',
        }),
      }),
    )
  })

  it('确认框打开后切换任务，不把旧载荷写入新任务', async () => {
    let confirmOptions: { onOk?: () => unknown } | undefined
    mocks.confirm.mockImplementationOnce((options: { onOk?: () => unknown }) => {
      confirmOptions = options
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as { form: { task_name: string }; confirmSave: () => void }
    vm.form.task_name = '旧任务修改'
    vm.confirmSave()
    await wrapper.setProps({ taskId: 'task-2' })
    await confirmOptions?.onOk?.()
    expect(mocks.updateTaskDraftConfiguration).not.toHaveBeenCalled()
    expect(mocks.updateTaskMetadata).not.toHaveBeenCalled()
  })

  it('网络、5xx 或坏 200 后锁定重复写，必须成功刷新详情才解锁', async () => {
    mocks.updateTaskMetadata.mockResolvedValueOnce({
      success: false,
      uncertain: true,
      message: '任务保存结果未知',
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      form: Record<string, any>
      confirmSave: () => void
      refresh: () => Promise<void>
      refreshRequired: boolean
    }
    vm.form.task_name = '第一次写入'
    vm.confirmSave()
    await flushPromises()
    expect(vm.refreshRequired).toBe(true)
    vm.confirmSave()
    expect(mocks.updateTaskMetadata).toHaveBeenCalledTimes(1)

    mocks.getTaskEdit.mockResolvedValueOnce({
      success: true,
      data: { ...detail, configuration_version: 4 },
    })
    await vm.refresh()
    expect(vm.refreshRequired).toBe(false)
  })

  it('任务、账号、关闭和卸载均使晚到详情失效', async () => {
    const pending = deferred<{ success: boolean; data: TaskEditDetail }>()
    mocks.getTaskEdit.mockReturnValueOnce(pending.promise)
    const wrapper = mountDrawer()
    mocks.getTaskEdit.mockResolvedValueOnce({ success: true, data: { ...detail, id: 'task-2' } })
    await wrapper.setProps({ taskId: 'task-2' })
    pending.resolve({ success: true, data: detail })
    await flushPromises()
    const vm = wrapper.vm as unknown as { detail: TaskEditDetail | null }
    expect(vm.detail?.id).toBe('task-2')

    const accountPending = deferred<{ success: boolean; data: TaskEditDetail }>()
    mocks.getTaskEdit.mockReturnValueOnce(accountPending.promise)
    authState.user = { id: 'u-2' }
    await wrapper.setProps({ open: false })
    accountPending.resolve({ success: true, data: { ...detail, id: 'task-2' } })
    await flushPromises()
    expect(vm.detail).toBeNull()
    wrapper.unmount()
  })
})
