import { flushPromises, shallowMount } from '@vue/test-utils'
import dayjs from 'dayjs'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createTask: vi.fn(),
  message: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@/api/tasks', () => ({ createTask: mocks.createTask }))
vi.mock('ant-design-vue', () => ({ message: mocks.message }))
vi.mock('@ant-design/icons-vue', () => {
  const icon = { template: '<span />' }
  return {
    CheckOutlined: icon,
    ClockCircleOutlined: icon,
    DatabaseOutlined: icon,
    NumberOutlined: icon,
    PercentageOutlined: icon,
    ThunderboltOutlined: icon,
  }
})

import CreateTaskDrawer from '@/components/qc/CreateTaskDrawer.vue'
import type { TaskScene } from '@/api/tasks'

type DrawerVm = {
  canProceed: boolean
  currentStep: number
  formData: {
    task_name: string
    scene: TaskScene | null
    deadline: ReturnType<typeof dayjs> | null
    description: string
    date_range: { start?: string; end?: string } | null
    department_filter: string[]
  }
  handleSubmit: () => Promise<void>
  nextStep: () => void
  rangeMode: 'date' | 'ids'
  recordIdsText: string
  sceneLabel: string
  submitting: boolean
}

function mountDrawer() {
  return shallowMount(CreateTaskDrawer, {
    props: { open: true },
    global: {
      stubs: {
        'a-alert': true,
        'a-button': true,
        'a-checkbox': true,
        'a-date-picker': true,
        'a-descriptions': { template: '<div><slot /></div>' },
        'a-descriptions-item': { template: '<div><slot /></div>' },
        'a-drawer': { template: '<div><slot /><slot name="footer" /></div>' },
        'a-form': { template: '<div><slot /></div>' },
        'a-form-item': { template: '<div><slot /></div>' },
        'a-input': true,
        'a-input-number': true,
        'a-radio': true,
        'a-radio-button': true,
        'a-radio-group': { template: '<div><slot /></div>' },
        'a-range-picker': true,
        'a-select': true,
        'a-slider': true,
        'a-step': true,
        'a-steps': { template: '<div><slot /></div>' },
        'a-textarea': true,
      },
    },
  })
}

function vmOf(wrapper: ReturnType<typeof mountDrawer>) {
  return wrapper.vm as unknown as DrawerVm
}

describe('CreateTaskDrawer 创建草稿边界', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createTask.mockResolvedValue({
      success: true,
      data: { id: 'task-1', task_name: '测试任务' },
    })
  })

  it.each([
    ['running', '运行病历'],
    ['final', '终末病历'],
    ['outpatient', '门急诊病历'],
  ] as const)('明确选择 %s 后显示确认场景并随草稿提交', async (scene, label) => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = ' 场景任务 '
    vm.formData.scene = scene
    await nextTick()

    expect(vm.canProceed).toBe(true)
    expect(vm.sceneLabel).toBe(label)
    expect(wrapper.text()).toContain(label)

    await vm.handleSubmit()

    expect(mocks.createTask).toHaveBeenCalledWith(
      expect.objectContaining({ task_name: '场景任务', scene }),
    )
    expect(mocks.createTask.mock.calls[0][0]).not.toHaveProperty('description')
    expect(wrapper.emitted('created')).toHaveLength(1)
  })

  it('未选择场景时步骤不可继续，强制提交也会拦截', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '未选场景任务'

    expect(vm.canProceed).toBe(false)
    vm.nextStep()
    expect(vm.currentStep).toBe(0)
    await vm.handleSubmit()

    expect(mocks.createTask).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalledWith('请选择质控场景')
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(wrapper.emitted('update:open')).toBeUndefined()
  })

  it('病案号模式为空时强制提交也会拦截，不能退化为全量范围', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '空病案号任务'
    vm.formData.scene = 'running'
    vm.rangeMode = 'ids'
    vm.recordIdsText = '  \n\n'

    await vm.handleSubmit()

    expect(mocks.createTask).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalledWith('请输入至少一个病案号')
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(wrapper.emitted('update:open')).toBeUndefined()
  })

  it('日期与病案号模式只提交当前范围，空日期不发送空字符串', async () => {
    mocks.createTask.mockResolvedValue({ success: false, message: '测试停止' })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '范围任务'
    vm.formData.scene = 'final'
    vm.formData.date_range = { start: '2026-09-01', end: '2026-09-30' }
    vm.formData.department_filter = ['内科']
    vm.recordIdsText = 'MR-OLD'

    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenLastCalledWith(
      expect.objectContaining({
        date_range: { start: '2026-09-01', end: '2026-09-30' },
        department_filter: ['内科'],
      }),
    )
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('record_ids')

    vm.rangeMode = 'ids'
    vm.recordIdsText = 'MR-001\n\nMR-002'
    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenLastCalledWith(
      expect.objectContaining({ record_ids: ['MR-001', 'MR-002'] }),
    )
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('date_range')
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('department_filter')

    vm.rangeMode = 'date'
    vm.formData.date_range = { start: '', end: '' }
    vm.formData.department_filter = []
    await vm.handleSubmit()
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('date_range')
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('record_ids')
  })

  it('截止日期统一提交 YYYY-MM-DD，后端失败时保留输入且不发成功事件', async () => {
    mocks.createTask.mockResolvedValue({ success: false, message: '后端拒绝创建' })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '保留输入任务'
    vm.formData.scene = 'outpatient'
    vm.formData.description = '仅留在表单中的备注'
    vm.formData.deadline = dayjs('2026-10-08T16:45:30')

    await vm.handleSubmit()

    expect(mocks.createTask).toHaveBeenCalledWith(
      expect.objectContaining({ deadline: '2026-10-08' }),
    )
    expect(mocks.createTask.mock.calls[0][0]).not.toHaveProperty('description')
    expect(vm.formData.task_name).toBe('保留输入任务')
    expect(vm.formData.scene).toBe('outpatient')
    expect(vm.formData.deadline?.format('YYYY-MM-DD')).toBe('2026-10-08')
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(wrapper.emitted('update:open')).toBeUndefined()
    expect(mocks.message.error).toHaveBeenCalledWith('后端拒绝创建')
  })

  it('后端声称成功但未返回任务时按失败处理并保留表单', async () => {
    mocks.createTask.mockResolvedValue({ success: true })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '缺失返回任务'
    vm.formData.scene = 'final'

    await vm.handleSubmit()

    expect(mocks.message.error).toHaveBeenCalledWith('创建失败')
    expect(vm.formData.task_name).toBe('缺失返回任务')
    expect(vm.formData.scene).toBe('final')
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(wrapper.emitted('update:open')).toBeUndefined()
  })

  it('提交处理中忽略重复提交', async () => {
    let resolveRequest!: (value: { success: false; message: string }) => void
    mocks.createTask.mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve
      }),
    )
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '防重复任务'
    vm.formData.scene = 'running'

    const firstSubmit = vm.handleSubmit()
    const secondSubmit = vm.handleSubmit()
    expect(vm.submitting).toBe(true)
    expect(mocks.createTask).toHaveBeenCalledTimes(1)

    resolveRequest({ success: false, message: '测试结束' })
    await Promise.all([firstSubmit, secondSubmit])
    await flushPromises()
    expect(vm.submitting).toBe(false)
  })
})
