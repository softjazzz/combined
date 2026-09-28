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
    SaveOutlined: icon,
    ThunderboltOutlined: icon,
  }
})

import CreateTaskDrawer from '@/components/qc/CreateTaskDrawer.vue'
import type { TaskScene } from '@/api/tasks'

const selectStub = {
  props: ['value', 'options'],
  emits: ['update:value'],
  template: '<select :value="value" @change="$emit(\'update:value\', $event.target.value)"><option value="">请选择</option><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select>',
}

type DrawerVm = {
  canProceed: boolean
  currentStep: number
  formData: {
    task_name: string
    scene: TaskScene | null
    rule_set_key?: string
    assign_method: string
    assign_fallback?: 'by_ratio' | 'reject'
    deadline: ReturnType<typeof dayjs> | null
    description: string
    date_range: { start?: string; end?: string } | null
    department_filter: string[]
    sampling_method: 'all' | 'count' | 'percentage'
    sampling_config: { case_scope?: 'active'; group_by: string | null | undefined }
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
  handleSaveTemplate: () => void
}

function mountDrawer(props: Record<string, unknown> = {}) {
  return shallowMount(CreateTaskDrawer, {
    props: { open: true, ...props },
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
        'a-radio': { props: ['value', 'disabled'], template: '<label :data-value="value" :data-disabled="String(!!disabled)"><slot /></label>' },
        'a-radio-button': true,
        'a-radio-group': { template: '<div><slot /></div>' },
        'a-range-picker': true,
        'a-select': selectStub,
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
  if (scene === 'running') vm.formData.sampling_config.case_scope = 'active'
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
      expect.objectContaining({ task_name: '场景任务', scene, rule_set_key: `${scene}-rules`, assign_method: 'by_ratio' }),
    )
    expect(mocks.createTask.mock.calls[0][0]).not.toHaveProperty('description')
    expect(mocks.createTask.mock.calls[0][0]).not.toHaveProperty('assignee_config')
    expect(wrapper.emitted('created')).toHaveLength(1)
  })

  it('套用模板只回填可复用配置，任务名称和截止日期仍由本次填写', async () => {
    const wrapper = mountDrawer({
      initialTemplateConfig: {
        scene: 'final',
        rule_set_key: 'final-rules',
        date_range: { start: '2026-09-01', end: '2026-09-20' },
        department_filter: ['内科'],
        sampling_method: 'count',
        sampling_config: { total: 12, by_department: true },
        assign_method: 'by_department',
        assignee_config: {},
      },
    })
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.formData.task_name).toBe('')
    expect(vm.formData.deadline).toBeNull()
    expect(vm.formData.scene).toBe('final')
    expect(vm.formData.rule_set_key).toBe('final-rules')
    expect(vm.formData.department_filter).toEqual(['内科'])
    expect(vm.formData.sampling_method).toBe('count')
    expect(vm.formData.assign_method).toBe('by_department')
    expect(mocks.message.success).toHaveBeenCalledWith('模板配置已套用，请填写任务名称和截止日期')
  })

  it('保存当前配置时不携带任务名、期限、病例或人员身份', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '不应进入模板'
    vm.formData.deadline = dayjs('2026-10-01')
    vm.formData.department_filter = ['内科']
    await chooseRuleSet(vm, 'running')
    vm.handleSaveTemplate()

    const payload = wrapper.emitted('save-template')?.[0]?.[0] as Record<string, unknown>
    expect(payload).toMatchObject({
      scene: 'running',
      rule_set_key: 'running-rules',
      department_filter: ['内科'],
      sampling_config: { case_scope: 'active' },
      assign_method: 'by_ratio',
      assignee_config: {},
    })
    expect(payload).not.toHaveProperty('task_name')
    expect(payload).not.toHaveProperty('deadline')
    expect(payload).not.toHaveProperty('record_refs')
  })

  it('创建时只选择分配策略，不展示或提交虚构质控员', async () => {
    mocks.createTask.mockResolvedValue({ success: false, message: '测试停止' })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '分配策略任务'
    await chooseRuleSet(vm, 'running')
    vm.currentStep = 3
    await nextTick()

    expect(vm.formData.assign_method).toBe('by_ratio')
    expect(vm.canProceed).toBe(true)
    expect(wrapper.text()).toContain('抽样后分配质控员')
    expect(wrapper.text()).toContain('病历类型（暂不可用）')
    expect(wrapper.text()).not.toContain('王质控')

    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenCalledWith(expect.objectContaining({ assign_method: 'by_ratio' }))
    expect(mocks.createTask.mock.calls[0][0]).not.toHaveProperty('assignee_config')
  })

  it.each(['keep', 'by_type', 'by_record_type'] as const)('不可用分配策略 %s 即使被强制设置也不可创建', async (method) => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '无效分配任务'
    await chooseRuleSet(vm, 'running')
    vm.currentStep = 3
    vm.formData.assign_method = method
    await nextTick()

    expect(vm.canProceed).toBe(false)
    await vm.handleSubmit()
    expect(mocks.createTask).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalledWith('请选择可用的分配方式')
  })

  it('分配方式提供比例/原质控员/科室，病历类型禁用并说明原因', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    await chooseRuleSet(vm, 'running')
    vm.currentStep = 3
    await nextTick()
    const radios = wrapper.findAll('[data-testid="assign-method-group"] label')
    expect(radios.map((item) => [item.attributes('data-value'), item.attributes('data-disabled')])).toEqual([
      ['by_ratio', 'false'],
      ['by_original_reviewer', 'false'],
      ['by_department', 'false'],
      ['by_record_type', 'true'],
    ])
    expect(wrapper.get('[data-testid="assign-method-record-type-hint"]').text()).toContain('当前场景病历类型无区分，暂不可用')
    expect(wrapper.find('[data-testid="assign-fallback-group"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="assign-department-hint"]').exists()).toBe(false)
  })

  it('原质控员必须选择无原质控员时的处理方式，提交 assignee_config.fallback', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '原质控员任务'
    await chooseRuleSet(vm, 'final')
    vm.currentStep = 3
    vm.formData.assign_method = 'by_original_reviewer'
    await nextTick()

    expect(wrapper.find('[data-testid="assign-fallback-group"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="assign-fallback-required"]').text()).toContain('请选择')
    expect(vm.canProceed).toBe(false)
    await vm.handleSubmit()
    expect(mocks.createTask).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenCalledWith('请选择“无原质控员时”的处理方式')

    vm.formData.assign_fallback = 'reject'
    await nextTick()
    expect(vm.canProceed).toBe(true)
    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenCalledWith(expect.objectContaining({
      assign_method: 'by_original_reviewer',
      assignee_config: { fallback: 'reject' },
    }))
  })

  it('按科室提示账号科室匹配，提交不带 assignee_config', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '科室任务'
    await chooseRuleSet(vm, 'final')
    vm.currentStep = 3
    vm.formData.assign_method = 'by_department'
    vm.formData.assign_fallback = 'by_ratio'
    await nextTick()

    expect(wrapper.get('[data-testid="assign-department-hint"]').text())
      .toContain('受领人按其账号科室匹配病历科室，历史任务缺科室将无法分配')
    expect(vm.canProceed).toBe(true)
    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenCalledWith(expect.objectContaining({ assign_method: 'by_department' }))
    expect(mocks.createTask.mock.calls[0][0]).not.toHaveProperty('assignee_config')
  })

  it('422 method_unavailable 显示分配方式不可用及原因，保留表单', async () => {
    mocks.createTask.mockResolvedValue({
      success: false,
      status: 422,
      code: 'method_unavailable',
      message: '病历类型无可区分事实',
      errorDetail: { code: 'method_unavailable', message: '按病历类型分配暂不可用', reason: '病历类型无可区分事实' },
    })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '不可用任务'
    await chooseRuleSet(vm, 'final')
    await vm.handleSubmit()
    expect(mocks.message.error).toHaveBeenCalledWith('该分配方式当前不可用（病历类型无可区分事实）')
    expect(wrapper.emitted('created')).toBeUndefined()
  })

  it('比例抽样只提供科室分组；旧医生分组值不可继续或强制提交', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '分组校验任务'
    await chooseRuleSet(vm, 'running')
    vm.formData.sampling_method = 'percentage'
    vm.currentStep = 2
    await nextTick()

    expect(wrapper.text()).toContain('按科室')
    expect(wrapper.text()).not.toContain('按主治医生')
    expect(wrapper.findAll('option').map((option) => option.attributes('value'))).not.toContain('doctor_name')

    vm.formData.sampling_config.group_by = 'doctor_name'
    await nextTick()
    expect(vm.canProceed).toBe(false)
    vm.nextStep()
    expect(vm.currentStep).toBe(2)
    await vm.handleSubmit()
    expect(mocks.createTask).not.toHaveBeenCalled()
    expect(mocks.message.warning).toHaveBeenLastCalledWith('当前仅支持按科室分组或不分组抽样')
  })

  it('比例抽样允许科室或不分组；切换抽样方式不提交遗留医生分组', async () => {
    mocks.createTask.mockResolvedValue({ success: false, message: '测试停止' })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '合法分组任务'
    await chooseRuleSet(vm, 'running')
    vm.formData.sampling_method = 'percentage'
    vm.currentStep = 2

    for (const groupBy of ['department', null, undefined] as const) {
      vm.formData.sampling_config.group_by = groupBy
      await nextTick()
      expect(vm.canProceed).toBe(true)
      await vm.handleSubmit()
      expect(mocks.createTask.mock.calls.at(-1)?.[0].sampling_config.group_by).toBe(groupBy)
    }

    vm.formData.sampling_config.group_by = 'doctor_name'
    vm.formData.sampling_method = 'count'
    await vm.handleSubmit()
    expect(mocks.createTask.mock.calls.at(-1)?.[0].sampling_config).not.toHaveProperty('group_by')
    vm.formData.sampling_method = 'all'
    await vm.handleSubmit()
    expect(mocks.createTask.mock.calls.at(-1)?.[0].sampling_config).not.toHaveProperty('group_by')
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
    vm.formData.sampling_config.case_scope = 'active'
    await nextTick()
    expect(vm.canProceed).toBe(true)
    vm.formData.scene = 'final'
    await nextTick()
    expect(vm.formData.rule_set_key).toBeUndefined()
    expect(vm.formData.sampling_config.case_scope).toBeUndefined()
    expect(vm.canProceed).toBe(false)
  })

  it('运行场景须从界面显式选择当前在院，切终末后提交不带旧范围', async () => {
    mocks.createTask.mockResolvedValue({ success: false, message: '测试停止' })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    await flushPromises()
    vm.formData.task_name = '在院范围任务'
    await wrapper.find('[data-testid="task-scene-select"]').setValue('running')
    await nextTick()
    await wrapper.find('[data-testid="task-rule-set-select"]').setValue('running-rules')
    vm.currentStep = 1
    await nextTick()
    expect(wrapper.text()).toContain('出院未归档病历暂不可抽样')
    expect(vm.canProceed).toBe(false)
    await vm.handleSubmit()
    expect(mocks.createTask).not.toHaveBeenCalled()

    await wrapper.find('[data-testid="task-case-scope-select"]').setValue('active')
    expect(vm.canProceed).toBe(true)
    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenLastCalledWith(expect.objectContaining({
      scene: 'running', sampling_config: expect.objectContaining({ case_scope: 'active' }),
    }))

    vm.currentStep = 0
    await wrapper.find('[data-testid="task-scene-select"]').setValue('final')
    await nextTick()
    expect(vm.formData.sampling_config.case_scope).toBeUndefined()
    await wrapper.find('[data-testid="task-rule-set-select"]').setValue('final-rules')
    await vm.handleSubmit()
    expect(mocks.createTask.mock.calls.at(-1)?.[0].sampling_config).not.toHaveProperty('case_scope')
  })

  it('门急诊无匹配可用规则集时明确阻止创建', async () => {
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '门急诊任务'
    await flushPromises()
    vm.formData.scene = 'outpatient'
    await nextTick()

    expect(vm.matchingRuleSets).toHaveLength(0)
    expect(wrapper.text()).toContain('门急诊病历暂无可用的匹配规则集')
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

  it('当前在院入院起日允许恰好 180 天和今天，超界日期不创建草稿', async () => {
    mocks.createTask.mockResolvedValue({ success: false, message: '测试停止' })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '在院日期任务'
    await chooseRuleSet(vm, 'running')
    const today = dayjs(new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10))
    const earliest = today.subtract(180, 'day').format('YYYY-MM-DD')

    vm.formData.date_range = { start: earliest, end: today.format('YYYY-MM-DD') }
    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenCalledTimes(1)
    vm.formData.date_range = { start: today.format('YYYY-MM-DD') }
    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenCalledTimes(2)

    vm.formData.date_range = { start: today.subtract(181, 'day').format('YYYY-MM-DD') }
    await vm.handleSubmit()
    expect(mocks.message.warning).toHaveBeenLastCalledWith('入院日期范围最多 180 天')
    vm.formData.date_range = { start: today.add(1, 'day').format('YYYY-MM-DD') }
    await vm.handleSubmit()
    expect(mocks.message.warning).toHaveBeenLastCalledWith('入院开始日期不能晚于在院截止日期')
    expect(mocks.createTask).toHaveBeenCalledTimes(2)
  })

  it('当前在院拒绝逆序及无效日期，切换终末场景后沿用原有日期提交行为', async () => {
    mocks.createTask.mockResolvedValue({ success: false, message: '测试停止' })
    const wrapper = mountDrawer()
    const vm = vmOf(wrapper)
    vm.formData.task_name = '日期错误任务'
    await chooseRuleSet(vm, 'running')
    const today = dayjs(new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10))
    vm.formData.date_range = { start: today.format('YYYY-MM-DD'), end: today.subtract(1, 'day').format('YYYY-MM-DD') }
    await vm.handleSubmit()
    expect(mocks.message.warning).toHaveBeenLastCalledWith('日期范围起始时间不能晚于结束时间')
    vm.formData.date_range = { start: '2026-02-30', end: today.format('YYYY-MM-DD') }
    await vm.handleSubmit()
    expect(mocks.message.warning).toHaveBeenLastCalledWith('入院日期范围格式无效，请选择有效日期')
    expect(mocks.createTask).not.toHaveBeenCalled()

    vm.formData.scene = 'final'
    await nextTick()
    vm.formData.rule_set_key = 'final-rules'
    vm.formData.date_range = { start: '2026-02-30', end: today.format('YYYY-MM-DD') }
    await vm.handleSubmit()
    expect(mocks.createTask).toHaveBeenCalledWith(expect.objectContaining({
      scene: 'final', date_range: { start: '2026-02-30', end: today.format('YYYY-MM-DD') },
    }))
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
