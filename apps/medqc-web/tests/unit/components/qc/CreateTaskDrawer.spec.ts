import { flushPromises, shallowMount } from '@vue/test-utils'
import dayjs from 'dayjs'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createTask: vi.fn(),
  getTaskRuleSets: vi.fn(),
  message: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('@/api/tasks', () => ({
  createTask: mocks.createTask,
  getTaskRuleSets: mocks.getTaskRuleSets,
}))
vi.mock('ant-design-vue', () => ({ message: mocks.message }))
vi.mock('@ant-design/icons-vue', () => {
  const icon = { template: '<span />' }
  return {
    CheckOutlined: icon,
    ClockCircleOutlined: icon,
    DatabaseOutlined: icon,
    NumberOutlined: icon,
    PercentageOutlined: icon,
    PlusOutlined: icon,
    DeleteOutlined: icon,
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
    rule_set_key?: string
    deadline: ReturnType<typeof dayjs> | null
    description: string
    date_range: { start?: string; end?: string } | null
    department_filter: string[]
  }
  handleSubmit: () => Promise<void>
  nextStep: () => void
  rangeMode: 'date' | 'refs'
  recordRefs: Array<{ institute_id: string; patient_id: string; visit_id: string }>
  recordRefsError: string
  addRecordRef: () => void
  removeRecordRef: (index: number) => void
  sceneLabel: string
  matchingRuleSets: Array<{ rule_set_key: string }>
  ruleSetsError: string
  submitting: boolean
}

function mountDrawer() {
  return shallowMount(CreateTaskDrawer, {
    props: { open: true },
    global: {
      stubs: {
        'a-alert': { props: ['message'], template: '<div>{{ message }}</div>' },
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

async function chooseRuleSet(vm: DrawerVm, scene: 'running' | 'final') {
  await flushPromises()
  vm.formData.scene = scene
  await nextTick()
  vm.formData.rule_set_key = `${scene}-rules`
  await nextTick()
}

describe('CreateTaskDrawer 创建草稿边界', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.createTask.mockResolvedValue({
      success: true,
      data: { id: 'task-1', task_name: '测试任务' },
    })
    mocks.getTaskRuleSets.mockResolvedValue({
      success: true,
      data: {
        items: [
          { rule_set_key: 'running-rules', rule_set_name: '运行规则', rule_set_version: 'v1', scope: 'running' },
          { rule_set_key: 'final-rules', rule_set_name: '终末规则', rule_set_version: 'v2', scope: 'final' },
        ],
      },
    })
  })

  it.each([
    ['running', '运行病历'],
    ['final', '终末病历'],
  ] as const)('明确选择 %s 规则集后显示确认场景并随草稿提交', async (scene, label) => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = ' 场景任务 '
    await chooseRuleSet(vm, scene)

    expect(vm.canProceed).toBe(true)
    expect(vm.sceneLabel).toBe(label)
    expect(wrapper.text()).toContain(label)

    await vm.handleSubmit()

    expect(mocks.createTask).toHaveBeenCalledWith(
      expect.objectContaining({ task_name: '场景任务', scene, rule_set_key: `${scene}-rules` }),
    )
    expect(mocks.createTask.mock.calls[0][0]).not.toHaveProperty('description')
    expect(wrapper.emitted('created')).toHaveLength(1)
  })

  it('未人工选择规则集不可继续，切换场景清除原选择', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '规则集任务'
    await flushPromises()
    vm.formData.scene = 'running'
    await nextTick()
    expect(vm.canProceed).toBe(false)
    await vm.handleSubmit()
    expect(mocks.message.warning).toHaveBeenCalledWith('请选择与质控场景匹配的规则集')

    vm.formData.rule_set_key = 'running-rules'
    await nextTick()
    expect(vm.canProceed).toBe(true)
    vm.formData.scene = 'final'
    await nextTick()
    expect(vm.formData.rule_set_key).toBeUndefined()
    expect(vm.canProceed).toBe(false)
  })

  it('门急诊无匹配已发布规则集时明确阻止创建', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '门急诊任务'
    await flushPromises()
    vm.formData.scene = 'outpatient'
    await nextTick()

    expect(vm.matchingRuleSets).toHaveLength(0)
    expect(wrapper.text()).toContain('门急诊病历暂无已发布的匹配规则集')
    expect(vm.canProceed).toBe(false)
    await vm.handleSubmit()
    expect(mocks.createTask).not.toHaveBeenCalled()
  })

  it('目录加载失败不能视为空目录或提交任务', async () => {
    mocks.getTaskRuleSets.mockResolvedValue({ success: false, message: '目录不可用' })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '失败任务'
    await flushPromises()
    vm.formData.scene = 'running'
    await nextTick()

    expect(vm.ruleSetsError).toBe('目录不可用')
    expect(wrapper.text()).toContain('目录不可用')
    expect(vm.canProceed).toBe(false)
    await vm.handleSubmit()
    expect(mocks.createTask).not.toHaveBeenCalled()
    expect(mocks.message.error).toHaveBeenCalledWith('目录不可用')
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

  it('指定病历为空时强制提交也会拦截，不能退化为全量范围', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '空坐标任务'
    await chooseRuleSet(vm, 'running')
    vm.rangeMode = 'refs'
    vm.currentStep = 1
    expect(vm.canProceed).toBe(false)

    await vm.handleSubmit()

    expect(mocks.createTask).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalledWith('请至少填写一条完整的病历坐标')
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(wrapper.emitted('update:open')).toBeUndefined()
  })

  it('残缺或重复三坐标均阻止下一步与强制提交', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '坐标校验任务'
    await chooseRuleSet(vm, 'running')
    vm.rangeMode = 'refs'
    vm.currentStep = 1
    vm.recordRefs[0] = { institute_id: 'H-1', patient_id: 'P-1', visit_id: '' }
    await nextTick()
    expect(vm.canProceed).toBe(false)
    await vm.handleSubmit()
    expect(mocks.message.warning).toHaveBeenCalledWith('每条病历均须填写机构 ID、患者 ID 和就诊 ID')
    expect(mocks.createTask).not.toHaveBeenCalled()

    vm.recordRefs[0].visit_id = 'V-1'
    vm.addRecordRef()
    vm.recordRefs[1] = { institute_id: ' H-1 ', patient_id: 'P-1', visit_id: 'V-1 ' }
    await nextTick()
    expect(vm.recordRefsError).toContain('重复')
    expect(vm.canProceed).toBe(false)
    await vm.handleSubmit()
    expect(mocks.createTask).not.toHaveBeenCalled()

    vm.removeRecordRef(1)
    await nextTick()
    expect(vm.canProceed).toBe(true)
    vm.removeRecordRef(0)
    expect(vm.recordRefs).toHaveLength(1)
  })

  it('日期与指定病历模式只提交当前范围，三坐标经去空格规范化', async () => {
    mocks.createTask.mockResolvedValue({ success: false, message: '测试停止' })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '范围任务'
    await chooseRuleSet(vm, 'final')
    vm.formData.date_range = { start: '2026-09-01', end: '2026-09-30' }
    vm.formData.department_filter = ['内科']
    vm.recordRefs[0] = { institute_id: 'H-OLD', patient_id: 'P-OLD', visit_id: 'V-OLD' }

    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenLastCalledWith(
      expect.objectContaining({
        date_range: { start: '2026-09-01', end: '2026-09-30' },
        department_filter: ['内科'],
      }),
    )
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('record_refs')

    vm.rangeMode = 'refs'
    vm.recordRefs[0] = { institute_id: ' H-1 ', patient_id: ' P-1 ', visit_id: ' V-1 ' }
    vm.addRecordRef()
    vm.recordRefs[1] = { institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-2' }
    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenLastCalledWith(
      expect.objectContaining({ record_refs: [
        { institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1' },
        { institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-2' },
      ] }),
    )
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('record_ids')
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('date_range')
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('department_filter')

    vm.rangeMode = 'date'
    vm.formData.date_range = { start: '', end: '' }
    vm.formData.department_filter = []
    await vm.handleSubmit()
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('date_range')
    expect(mocks.createTask.mock.calls.at(-1)?.[0]).not.toHaveProperty('record_refs')
  })

  it('截止日期统一提交 YYYY-MM-DD，后端失败时保留输入且不发成功事件', async () => {
    mocks.createTask.mockResolvedValue({ success: false, message: '后端拒绝创建' })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '保留输入任务'
    await chooseRuleSet(vm, 'final')
    vm.formData.description = '仅留在表单中的备注'
    vm.formData.deadline = dayjs('2026-10-08T16:45:30')

    await vm.handleSubmit()

    expect(mocks.createTask).toHaveBeenCalledWith(
      expect.objectContaining({ deadline: '2026-10-08' }),
    )
    expect(mocks.createTask.mock.calls[0][0]).not.toHaveProperty('description')
    expect(vm.formData.task_name).toBe('保留输入任务')
    expect(vm.formData.scene).toBe('final')
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
    await chooseRuleSet(vm, 'final')

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
    await chooseRuleSet(vm, 'running')

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
