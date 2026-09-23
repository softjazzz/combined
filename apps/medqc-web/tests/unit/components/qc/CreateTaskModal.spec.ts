import { flushPromises, shallowMount } from '@vue/test-utils'
import dayjs from 'dayjs'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createQCTaskAndSample: vi.fn(),
  getDepartmentList: vi.fn(),
  getTaskRuleSets: vi.fn(),
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
vi.mock('@/api/tasks', () => ({ getTaskRuleSets: mocks.getTaskRuleSets }))

import CreateTaskModal from '@/components/qc/CreateTaskModal.vue'

const selectStub = {
  props: ['value', 'options'],
  emits: ['update:value'],
  template: '<select :value="value" @change="$emit(\'update:value\', $event.target.value)"><option value="">请选择</option><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
}

type ModalVm = {
  form: {
    task_name: string
    rule_set_key: string | undefined
    case_scope: 'active' | undefined
    dateRange: [ReturnType<typeof dayjs>, ReturnType<typeof dayjs>] | null
    department_filter: string[]
    sampling_method: 'all' | 'count' | 'percentage'
    sampling_count: number
    sampling_pct: number
    deadline: ReturnType<typeof dayjs> | null
  }
  handleSubmit: () => Promise<void>
  submitting: boolean
  canSubmit: boolean
}

function mountModal() {
  return shallowMount(CreateTaskModal, {
    props: { visible: true, scene: 'running' },
    global: {
      stubs: {
        'a-modal': { template: '<div><slot /></div>' },
        'a-input': true,
        'a-range-picker': true,
        'a-select': selectStub,
        'a-alert': true,
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
        'a-alert': true,
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
    mocks.getTaskRuleSets.mockResolvedValue({
      success: true,
      data: { items: [{ rule_set_key: 'running-v1', rule_set_name: '运行病历规则集', rule_set_version: 'v1', scope: 'running' }] },
    })
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
    await flushPromises()
    expect(wrapper.text()).toContain('入院日期范围')
    vm.form.task_name = ' 运行任务 '
    vm.form.rule_set_key = 'running-v1'
    await wrapper.find('[data-testid="legacy-task-case-scope-select"]').setValue('active')
    vm.form.sampling_method = 'count'
    vm.form.sampling_count = 8
    vm.form.deadline = dayjs('2026-10-09T15:30:00')

    await vm.handleSubmit()

    expect(mocks.createQCTaskAndSample).toHaveBeenCalledWith(
      expect.objectContaining({
        task_name: '运行任务',
        scene: 'running',
        rule_set_key: 'running-v1',
        sampling_config: { total: 8, case_scope: 'active' },
        deadline: '2026-10-09',
      }),
    )
    expect(wrapper.emitted('created')?.[0]?.[0]).toEqual(
      expect.objectContaining({ sampled: true }),
    )
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  it('当前在院日期范围允许 180 天边界与今天，拒绝更早或未来的起日', async () => {
    mocks.createQCTaskAndSample.mockResolvedValue({ success: false, message: '测试停止' })
    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    await flushPromises()
    vm.form.task_name = '在院日期任务'
    vm.form.rule_set_key = 'running-v1'
    vm.form.case_scope = 'active'
    const today = dayjs(new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10))

    vm.form.dateRange = [today.subtract(180, 'day'), today]
    await vm.handleSubmit()
    expect(mocks.createQCTaskAndSample).toHaveBeenCalledTimes(1)
    vm.form.dateRange = [today, today]
    await vm.handleSubmit()
    expect(mocks.createQCTaskAndSample).toHaveBeenCalledTimes(2)

    vm.form.dateRange = [today.subtract(181, 'day'), today]
    await vm.handleSubmit()
    expect(mocks.message.warning).toHaveBeenLastCalledWith('入院日期范围最多 180 天')
    vm.form.dateRange = [today.add(1, 'day'), today.add(1, 'day')]
    await vm.handleSubmit()
    expect(mocks.message.warning).toHaveBeenLastCalledWith('入院开始日期不能晚于在院截止日期')
    expect(mocks.createQCTaskAndSample).toHaveBeenCalledTimes(2)
  })

  it('当前在院拒绝逆序及无效日期，切换终末后不应用在院限制', async () => {
    mocks.createQCTaskAndSample.mockResolvedValue({ success: false, message: '测试停止' })
    mocks.getTaskRuleSets.mockResolvedValue({ success: true, data: { items: [
      { rule_set_key: 'running-v1', rule_set_name: '运行', rule_set_version: 'v1', scope: 'running' },
      { rule_set_key: 'final-v1', rule_set_name: '终末', rule_set_version: 'v1', scope: 'final' },
    ] } })
    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    await flushPromises()
    vm.form.task_name = '日期错误任务'
    vm.form.rule_set_key = 'running-v1'
    vm.form.case_scope = 'active'
    const today = dayjs(new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10))
    vm.form.dateRange = [today, today.subtract(1, 'day')]
    await vm.handleSubmit()
    expect(mocks.message.warning).toHaveBeenLastCalledWith('日期范围起始时间不能晚于结束时间')
    vm.form.dateRange = [dayjs('not-a-date'), today]
    await vm.handleSubmit()
    expect(mocks.message.warning).toHaveBeenLastCalledWith('入院日期范围格式无效，请选择有效日期')
    expect(mocks.createQCTaskAndSample).not.toHaveBeenCalled()

    await wrapper.setProps({ scene: 'final' })
    await flushPromises()
    vm.form.rule_set_key = 'final-v1'
    vm.form.dateRange = [dayjs('2026-02-20'), dayjs('2026-03-20')]
    await vm.handleSubmit()
    expect(mocks.createQCTaskAndSample).toHaveBeenCalledWith(expect.objectContaining({
      scene: 'final', date_range: { start: '2026-02-20', end: '2026-03-20' },
    }))
  })

  it('创建失败时保留输入，不关闭也不发 created', async () => {
    mocks.createQCTaskAndSample.mockResolvedValue({ success: false, message: '创建接口拒绝' })
    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    await flushPromises()
    vm.form.task_name = '保留的任务'
    vm.form.rule_set_key = 'running-v1'
    vm.form.case_scope = 'active'

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
              'a-alert': true,
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
    await flushPromises()
    vm.form.task_name = '只建成草稿'
    vm.form.rule_set_key = 'running-v1'
    vm.form.case_scope = 'active'

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
    await flushPromises()
    vm.form.task_name = '防重复任务'
    vm.form.rule_set_key = 'running-v1'
    vm.form.case_scope = 'active'

    const first = vm.handleSubmit()
    const second = vm.handleSubmit()
    expect(vm.submitting).toBe(true)
    expect(mocks.createQCTaskAndSample).toHaveBeenCalledTimes(1)

    resolveRequest({ success: false, message: '测试结束' })
    await Promise.all([first, second])
    await flushPromises()
    expect(vm.submitting).toBe(false)
  })

  it('目录失败、空目录和场景不匹配时均不能创建', async () => {
    for (const catalog of [
      { success: false, message: '目录不可用' },
      { success: true, data: { items: [] } },
      { success: true, data: { items: [{ rule_set_key: 'final-v1', rule_set_name: '终末', rule_set_version: 'v1', scope: 'final' }] } },
    ]) {
      mocks.getTaskRuleSets.mockResolvedValueOnce(catalog)
      const wrapper = mountModal()
      const vm = vmOf(wrapper)
      await flushPromises()
      vm.form.task_name = '不能创建'
      vm.form.rule_set_key = 'final-v1'
      expect(vm.canSubmit).toBe(false)
      await vm.handleSubmit()
      expect(mocks.createQCTaskAndSample).not.toHaveBeenCalled()
      wrapper.unmount()
    }
  })

  it('目录可用但未显式选择规则集时不能创建', async () => {
    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    await flushPromises()
    vm.form.task_name = '待选择规则集'
    expect(vm.canSubmit).toBe(false)
    await vm.handleSubmit()
    expect(mocks.createQCTaskAndSample).not.toHaveBeenCalled()
  })

  it('切换场景清除旧规则集，并忽略先前请求的过期响应', async () => {
    mocks.createQCTaskAndSample.mockResolvedValue({ success: false, message: '测试创建失败' })
    let resolveOld!: (value: unknown) => void
    mocks.getTaskRuleSets.mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve }))
    mocks.getTaskRuleSets.mockResolvedValueOnce({
      success: true,
      data: { items: [{ rule_set_key: 'final-v1', rule_set_name: '终末', rule_set_version: 'v1', scope: 'final' }] },
    })
    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    vm.form.task_name = '切换测试'
    vm.form.rule_set_key = 'running-v1'
    vm.form.case_scope = 'active'
    await wrapper.setProps({ scene: 'final' })
    await flushPromises()
    expect(vm.form.rule_set_key).toBeUndefined()
    expect(vm.form.case_scope).toBeUndefined()
    vm.form.rule_set_key = 'final-v1'
    expect(vm.canSubmit).toBe(true)
    resolveOld({ success: true, data: { items: [{ rule_set_key: 'running-v1', rule_set_name: '运行', rule_set_version: 'v1', scope: 'running' }] } })
    await flushPromises()
    expect(vm.canSubmit).toBe(true)
    await vm.handleSubmit()
    expect(mocks.createQCTaskAndSample).toHaveBeenCalledWith(expect.objectContaining({ scene: 'final', rule_set_key: 'final-v1' }))
    expect(mocks.createQCTaskAndSample.mock.calls[0][0].sampling_config).toBeUndefined()

    mocks.getTaskRuleSets.mockResolvedValueOnce({
      success: true,
      data: { items: [{ rule_set_key: 'outpatient-v1', rule_set_name: '门急诊', rule_set_version: 'v1', scope: 'outpatient' }] },
    })
    await wrapper.setProps({ scene: 'outpatient' })
    await flushPromises()
    vm.form.rule_set_key = 'outpatient-v1'
    vm.form.case_scope = 'active'
    await vm.handleSubmit()
    expect(mocks.createQCTaskAndSample).toHaveBeenLastCalledWith(expect.objectContaining({
      scene: 'outpatient', rule_set_key: 'outpatient-v1',
    }))
    expect(mocks.createQCTaskAndSample.mock.calls.at(-1)?.[0].sampling_config).toBeUndefined()
  })

  it('运行场景未通过界面选择当前在院时不可提交', async () => {
    const wrapper = mountModal()
    const vm = vmOf(wrapper)
    await flushPromises()
    vm.form.task_name = '在院任务'
    await wrapper.find('[data-testid="legacy-task-rule-set-select"]').setValue('running-v1')
    expect(vm.canSubmit).toBe(false)
    await vm.handleSubmit()
    expect(mocks.createQCTaskAndSample).not.toHaveBeenCalled()
    await wrapper.find('[data-testid="legacy-task-case-scope-select"]').setValue('active')
    expect(vm.canSubmit).toBe(true)
    mocks.createQCTaskAndSample.mockResolvedValue({ success: false, message: '测试停止' })
    await vm.handleSubmit()
    expect(mocks.createQCTaskAndSample).toHaveBeenCalledWith(expect.objectContaining({
      scene: 'running', sampling_config: { case_scope: 'active' },
    }))
  })
})
