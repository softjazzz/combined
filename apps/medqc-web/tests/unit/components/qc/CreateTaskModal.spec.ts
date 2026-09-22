import { flushPromises, shallowMount } from '@vue/test-utils'
import dayjs from 'dayjs'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createQCTaskAndSample: vi.fn(),
  getDepartmentList: vi.fn(),
  message: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@/api/qcAdmin', () => ({
  createQCTaskAndSample: mocks.createQCTaskAndSample,
  getDepartmentList: mocks.getDepartmentList,
}))
vi.mock('ant-design-vue', () => ({ message: mocks.message }))

import CreateTaskModal from '@/components/qc/CreateTaskModal.vue'

type ModalVm = {
  form: {
    task_name: string
    dateRange: [ReturnType<typeof dayjs>, ReturnType<typeof dayjs>] | null
    department_filter: string[]
    sampling_method: 'all' | 'count' | 'percentage'
    sampling_count: number
    sampling_pct: number
    deadline: ReturnType<typeof dayjs> | null
  }
  handleSubmit: () => Promise<void>
  submitting: boolean
}

function mountModal() {
  return shallowMount(CreateTaskModal, {
    props: { visible: true, scene: 'running' },
    global: {
      stubs: {
        'a-modal': { template: '<div><slot /></div>' },
        'a-input': true,
        'a-range-picker': true,
        'a-select': true,
        'a-radio-button': true,
        'a-radio-group': { template: '<div><slot /></div>' },
        'a-input-number': true,
        'a-slider': true,
        'a-date-picker': true,
      },
    },
  })
}

function mountModalWithoutScene() {
  return shallowMount(CreateTaskModal, {
    // @ts-expect-error 验证 JavaScript 调用方漏传必填 scene 时的运行时保护
    props: { visible: true },
    global: {
      stubs: {
        'a-modal': { template: '<div><slot /></div>' },
        'a-input': true,
        'a-range-picker': true,
        'a-select': true,
        'a-radio-button': true,
        'a-radio-group': { template: '<div><slot /></div>' },
        'a-input-number': true,
        'a-slider': true,
        'a-date-picker': true,
      },
    },
  })
}

function vmOf(wrapper: ReturnType<typeof mountModal>) {
  return wrapper.vm as unknown as ModalVm
}

describe('CreateTaskModal 运行病历创建链路', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getDepartmentList.mockResolvedValue({ success: true, data: [] })
  })

  it('提交固定场景、total 抽样数量以及 YYYY-MM-DD 截止日期', async () => {
    mocks.createQCTaskAndSample.mockResolvedValue({
      success: true,
      data: {
        task_id: 'task-1',
        task_number: 'QC-001',
        sampled: true,
        sampled_count: 8,
      },
    })
    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    expect(wrapper.text()).toContain('入院日期范围')
    vm.form.task_name = ' 运行任务 '
    vm.form.sampling_method = 'count'
    vm.form.sampling_count = 8
    vm.form.deadline = dayjs('2026-10-09T15:30:00')

    await vm.handleSubmit()

    expect(mocks.createQCTaskAndSample).toHaveBeenCalledWith(
      expect.objectContaining({
        task_name: '运行任务',
        scene: 'running',
        sampling_config: { total: 8 },
        deadline: '2026-10-09',
      }),
    )
    expect(wrapper.emitted('created')?.[0]?.[0]).toEqual(
      expect.objectContaining({ sampled: true }),
    )
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  it('创建失败时保留输入，不关闭也不发 created', async () => {
    mocks.createQCTaskAndSample.mockResolvedValue({ success: false, message: '创建接口拒绝' })
    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    vm.form.task_name = '保留的任务'

    await vm.handleSubmit()

    expect(mocks.message.error).toHaveBeenCalledWith('创建接口拒绝')
    expect(vm.form.task_name).toBe('保留的任务')
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(wrapper.emitted('update:visible')).toBeUndefined()
  })

  it.each([
    ['漏传场景', () => mountModalWithoutScene()],
    [
      '非法场景',
      () =>
        shallowMount(CreateTaskModal, {
          props: { visible: true, scene: 'legacy' as never },
          global: {
            stubs: {
              'a-modal': { template: '<div><slot /></div>' },
              'a-input': true,
              'a-range-picker': true,
              'a-select': true,
              'a-radio-button': true,
              'a-radio-group': { template: '<div><slot /></div>' },
              'a-input-number': true,
              'a-slider': true,
              'a-date-picker': true,
            },
          },
        }),
    ],
  ])('%s 时在请求前阻断', async (_case, factory) => {
    const wrapper = factory()
    const vm = vmOf(wrapper as ReturnType<typeof mountModal>)
    vm.form.task_name = '不应提交的任务'

    await vm.handleSubmit()

    expect(mocks.createQCTaskAndSample).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalledWith('请选择有效的质控场景')
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(wrapper.emitted('update:visible')).toBeUndefined()
  })

  it('抽样失败时提示草稿已创建，携带 sampled=false 后关闭并重置', async () => {
    const draft = {
      task_id: 'task-2',
      task_number: 'QC-002',
      sampled: false,
      sampled_count: 0,
    }
    mocks.createQCTaskAndSample.mockResolvedValue({
      success: false,
      data: draft,
      message: '场景候选尚未接通',
    })
    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    vm.form.task_name = '只建成草稿'

    await vm.handleSubmit()

    expect(mocks.message.warning).toHaveBeenCalledWith(
      '任务已创建，抽样未完成：场景候选尚未接通',
    )
    expect(mocks.message.success).not.toHaveBeenCalled()
    expect(wrapper.emitted('created')).toEqual([[draft]])
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
    expect(vm.form.task_name).toBe('')
  })

  it('提交处理中忽略重复提交', async () => {
    let resolveRequest!: (value: { success: false; message: string }) => void
    mocks.createQCTaskAndSample.mockReturnValue(
      new Promise((resolve) => {
        resolveRequest = resolve
      }),
    )
    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    vm.form.task_name = '防重复任务'

    const first = vm.handleSubmit()
    const second = vm.handleSubmit()
    expect(vm.submitting).toBe(true)
    expect(mocks.createQCTaskAndSample).toHaveBeenCalledTimes(1)

    resolveRequest({ success: false, message: '测试结束' })
    await Promise.all([first, second])
    await flushPromises()
    expect(vm.submitting).toBe(false)
  })
})
