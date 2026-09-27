import { flushPromises, mount } from '@vue/test-utils'
import { computed, reactive, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DataSyncConfigPage from '@/views/workstation-v4/DataSyncConfigPage.vue'

const { mockRunPreflight, mockMessageWarning } = vi.hoisted(() => ({
  mockRunPreflight: vi.fn(),
  mockMessageWarning: vi.fn(),
}))

const mockState = reactive({
  pgSyncState: {} as Record<string, any>,
  preflightResult: null as Record<string, any> | null,
  isSyncing: false,
  isTestingAll: false,
  isPreflighting: false,
  isSavingPolicy: false,
  departmentsLoading: false,
  availableDepartments: ['神经内科', '普通外科'],
  stats: { connectedCount: 0, lastSyncTime: '' },
  pgSyncTables: [],
  selectedTableGroups: [],
  pgTableGroups: [],
  policyForm: {
    scope: 'final',
    start_date: '2026-06-01',
    end_date: '2026-06-30',
    target_departments: ['*'],
  },
  currentRunLog: [],
  runHistory: [],
  loadErrors: {},
  connectionTesting: {},
  templateApplying: false,
})

let mockUserRoles = ['admin', 'qc_manager']

const mockAuthStore = {
  get userRoles() {
    return mockUserRoles
  },
  user: {
    is_demo_account: false,
  },
}

const mockRoute = reactive({ query: {} as Record<string, string> })

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: mockMessageWarning,
    info: vi.fn(),
  },
  Modal: {
    confirm: vi.fn(),
  },
}))

vi.mock('@/views/workstation-v4/composables/useDataSync', () => ({
  useDataSync: () => ({
    state: mockState,
    isReadonly: ref(false),
    hasPreflightPass: computed(() => Boolean(mockState.preflightResult?.executable)),
    initialize: vi.fn().mockResolvedValue(undefined),
    resetState: vi.fn(),
    testAllConnections: vi.fn(),
    runPreflight: mockRunPreflight,
    executeSync: vi.fn(),
    savePolicy: vi.fn(),
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthStore,
}))

function mountPage() {
  return mount(DataSyncConfigPage, {
    global: {
      stubs: {
        'a-tabs': {
          props: ['activeKey'],
          template:
            '<div data-testid="system-config-tabs" :data-active-key="activeKey"><slot /></div>',
        },
        'a-tab-pane': { template: '<section><slot /></section>' },
        'a-tooltip': { template: '<span><slot /></span>' },
        'a-button': { template: '<button><slot /></button>' },
        'a-tag': { template: '<span><slot /></span>' },
        'a-progress': { template: '<div class="progress-stub" />' },
        'a-modal': { template: '<div><slot /></div>' },
        'a-select': {
          props: ['value', 'options', 'disabled'],
          template: '<div class="select-stub"><slot /></div>',
        },
        'a-option': { template: '<option><slot /></option>' },
        'a-input': { template: '<input />' },
        'a-input-password': { template: '<input />' },
        'a-date-picker': {
          props: ['locale', 'placeholder'],
          template:
            '<input class="date-picker-stub" :data-locale="locale?.lang?.placeholder" :placeholder="placeholder" />',
        },
        'a-empty': { template: '<div />' },
        ConnectionStudio: { template: '<div />' },
        SyncRunPanel: { template: '<div />' },
        FrontpageExtractionSettingsPanel: { template: '<div />' },
        LLMApiConfig: { template: '<div />' },
        LlmPerformanceObservabilityPanel: { template: '<div />' },
      },
    },
  })
}

describe('DataSyncConfigPage visit progress', () => {
  beforeEach(() => {
    mockRunPreflight.mockReset()
    mockMessageWarning.mockReset()
    mockUserRoles = ['admin', 'qc_manager']
    mockAuthStore.user.is_demo_account = false
    mockRoute.query = {}
    mockState.policyForm.scope = 'final'
    mockState.isSyncing = false
    mockState.preflightResult = { estimated_impact: 20 }
    mockState.pgSyncState = {
      is_running: false,
      last_sync_status: 'partial',
      progress: {
        status: 'partial',
        stage: 'completed',
        tables_total: 8,
        tables_done: 8,
        rows_pulled_total: 120,
        rows_upserted_total: 100,
        eligible_visit_count: 20,
        visit_progress: {
          total: 20,
          completed: 3,
          remaining: 17,
          missing_mr: 17,
          detail_only: 2,
          basis: 'mr_visible',
          label: '病历池可见进度',
        },
      },
    }
  })

  it('重新打开页面时不把上一次同步结果当作本次进度', async () => {
    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('可进入病历池')
    expect(wrapper.text()).toContain('资料类别进度')
    expect(wrapper.text()).toContain('0 / 20 份')
    expect(wrapper.text()).not.toContain('3 / 20 份')
    expect(wrapper.text()).not.toContain('有 2 份病历明细已同步但病历池暂不可见')
    expect(wrapper.get('[data-testid="sync-progress-status"]').classes()).not.toContain(
      'mq-status--warning',
    )
  })

  it('未重新检查范围时本次同步计数全部从零开始', async () => {
    mockState.preflightResult = null

    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('本次候选')
    expect(wrapper.text()).toContain('0 / 0 份')
    expect(wrapper.text()).not.toContain('3 / 20 份')
  })

  it('高级账号将表名和行数收纳在默认折叠的同步详情中', () => {
    mockUserRoles = ['sync_admin']
    mockState.pgSyncState = {
      is_running: false,
      last_sync_status: 'success',
      progress: {
        status: 'success',
        stage: 'completed',
        tables_total: 8,
        tables_done: 8,
        rows_pulled_total: 120,
        rows_upserted_total: 100,
        eligible_visit_count: 20,
      },
    }

    const wrapper = mountPage()

    const details = wrapper.get('[data-testid="sync-technical-details"]')
    expect(details.attributes('open')).toBeUndefined()
    expect(wrapper.text()).toContain('资料类别进度')
    expect(details.text()).toContain('当前资料表')
    expect(wrapper.text()).toContain('已拉取行数')
    expect(wrapper.text()).toContain('0 / 20 份')
  })

  it('使用客户语言展示病例范围与Bundle刷新阶段', async () => {
    mockState.isSyncing = true
    mockState.pgSyncState = {
      is_running: true,
      last_sync_status: 'running',
      progress: {
        status: 'running',
        stage: 'scope_resolution',
        current_table: 'mr',
        tables_total: 8,
        tables_done: 0,
        eligible_visit_count: 0,
      },
    }
    const wrapper = mountPage()
    expect(wrapper.text()).toContain('正在确定病历范围')
    expect(wrapper.text()).not.toContain('正在同步数据：mr')

    mockState.pgSyncState.progress.stage = 'bundle_refresh'
    mockState.pgSyncState.progress.current_table = ''
    mockState.pgSyncState.progress.bundle_progress = {
      total: 20,
      completed: 7,
      remaining: 13,
    }
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('正在刷新病历资料视图')
    expect(wrapper.text()).toContain('病历资料视图')
    expect(wrapper.text()).toContain('7 / 20 份')
  })

  it('按用户任务顺序展示三步单页同步引导', () => {
    const wrapper = mountPage()

    expect(wrapper.text()).toContain('选择病历类型')
    expect(wrapper.text()).toContain('设置同步范围')
    expect(wrapper.text()).toContain('检查结果')
    expect(wrapper.text()).toContain('抽取科室')
    expect(wrapper.text()).toContain('出院开始日期')
    expect(wrapper.text()).toContain('出院结束日期')
    expect(wrapper.findAll('[data-testid^="sync-scene-"]')).toHaveLength(3)
    expect(wrapper.get('[data-testid="sync-scene-final"]').classes()).toContain('is-active')
    expect(wrapper.findAll('[data-testid="check-record-scope-action"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('mr_no 不是同步条件')
    expect(wrapper.text()).not.toContain('配置摘要')
    expect(wrapper.text()).not.toContain('安全说明')
  })

  it('在院范围不展示历史日期选择器并说明按当前时刻判断', async () => {
    mockState.policyForm.scope = 'running'

    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('当前在院统计时间')
    expect(wrapper.text()).toContain('以执行检查时的医院当前时间为准')
    expect(wrapper.text()).not.toContain('入院开始日期')
    expect(wrapper.text()).not.toContain('在院截止日期')
    expect(wrapper.text()).not.toContain('出院开始日期')
    expect(wrapper.text()).not.toContain('出院结束日期')
    const datePickers = wrapper.findAll('.date-picker-stub')
    expect(datePickers).toHaveLength(0)
    mockState.policyForm.scope = 'final'
  })

  it('合并范围只展示出院日期范围并保留中文日期选择器', async () => {
    mockState.policyForm.scope = 'both'

    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('当前在院 + 期间出院病历')
    expect(wrapper.text()).toContain('出院开始日期')
    expect(wrapper.text()).toContain('出院结束日期')
    const datePickers = wrapper.findAll('.date-picker-stub')
    expect(datePickers).toHaveLength(2)
    expect(datePickers.every((picker) => picker.attributes('data-locale') === '请选择日期')).toBe(
      true,
    )
    mockState.policyForm.scope = 'final'
  })

  it('点击病历类型卡片直接更新同步范围', async () => {
    const wrapper = mountPage()

    await wrapper.get('[data-testid="sync-scene-running"]').trigger('click')

    expect(mockState.policyForm.scope).toBe('running')
    expect(wrapper.text()).toContain('当前在院统计时间')
    mockState.policyForm.scope = 'final'
  })

  it('只有检查通过后才展示确认和正式同步操作', async () => {
    mockState.preflightResult = {
      estimated_impact: 12,
      executable: false,
      blockers: ['源库住院登记不可用'],
      warnings: [],
    }
    const wrapper = mountPage()
    expect(wrapper.text()).not.toContain('我已确认同步 12 份病历')

    mockState.preflightResult.executable = true
    mockState.preflightResult.blockers = []
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('我已确认同步 12 份病历')
    expect(wrapper.text()).toContain('开始同步')
  })

  it('执行同步前在页面内弹窗展示范围摘要，取消后不执行', async () => {
    mockUserRoles = ['sync_admin']
    mockState.preflightResult = {
      source: 'pg',
      estimated_impact: 12,
      executable: true,
      blockers: [],
      warnings: [],
    }
    const wrapper = mountPage()
    expect(wrapper.find('.sync-confirm').exists()).toBe(false)

    await wrapper.get('.sync-actions__confirm input').setValue(true)
    const executeButton = wrapper
      .findAll('button')
      .find((button) => button.text() === '确认执行同步')
    await executeButton?.trigger('click')
    await flushPromises()

    const dialog = wrapper.get('.sync-confirm')
    expect(dialog.text()).toContain('执行前确认')
    expect(dialog.text()).toContain('找到可同步病历 12 份')
    expect(dialog.text()).toContain('已出院病历')
    expect(dialog.text()).toContain('2026-06-01 ~ 2026-06-30')

    const cancelButton = dialog.findAll('button').find((button) => button.text() === '取消')
    await cancelButton?.trigger('click')
    await flushPromises()
    expect(wrapper.find('.sync-confirm').exists()).toBe(false)
  })

  it('演示账号只看到简化同步向导并隐藏实施诊断信息', () => {
    mockUserRoles = ['admin', 'qc_manager']
    mockState.preflightResult = null

    const wrapper = mountPage()
    const text = wrapper.text()

    expect(text).toContain('病历数据同步设置')
    expect(text).toContain('检查病历范围')
    expect(text).not.toContain('我已确认同步')
    expect(text).toContain('出院开始日期')
    expect(text).toContain('出院结束日期')
    expect(text).not.toContain('clinical_data')
    expect(text).not.toContain('本地 CDM')
    expect(text).not.toContain('discharge_record')
    expect(text).not.toContain('表组预检表')
    expect(text).not.toContain('实施诊断模式')
  })

  it('实施账号可以展开高级配置和运行日志', async () => {
    mockUserRoles = ['sync_admin']

    const wrapper = mountPage()
    expect(wrapper.text()).toContain('高级设置与运行记录')
    expect(wrapper.text()).not.toContain('clinical_data')

    await wrapper.get('[data-testid="advanced-sync-toggle"]').trigger('click')

    expect(wrapper.text()).toContain('clinical_data')
    expect(wrapper.text()).toContain('表组预检')
  })

  it.each([
    { role: 'qc_manager', frontpage: true, llm: false, observability: false },
    { role: 'admin', frontpage: true, llm: true, observability: true },
    { role: 'sync_admin', frontpage: true, llm: true, observability: true },
    { role: 'super_admin', frontpage: true, llm: true, observability: true },
    { role: 'doctor', frontpage: false, llm: false, observability: false },
  ])('按 $role 的后端角色合同展示系统配置页签', ({ role, frontpage, llm, observability }) => {
    mockUserRoles = [role]

    const wrapper = mountPage()

    expect(wrapper.find('[data-testid="frontpage-config-tab"]').exists()).toBe(frontpage)
    expect(wrapper.find('[data-testid="llm-config-tab"]').exists()).toBe(llm)
    expect(wrapper.find('[data-testid="llm-observability-tab"]').exists()).toBe(observability)
  })

  it('演示账号不显示模型性能页签', () => {
    mockUserRoles = ['admin']
    mockAuthStore.user.is_demo_account = true

    const wrapper = mountPage()

    expect(wrapper.find('[data-testid="llm-observability-tab"]').exists()).toBe(false)
  })

  it('内置同步管理员即使带演示标记仍显示模型性能页签', () => {
    mockUserRoles = ['sync_admin']
    mockAuthStore.user.is_demo_account = true

    const wrapper = mountPage()

    expect(wrapper.find('[data-testid="llm-observability-tab"]').exists()).toBe(true)
  })

  it('管理员通过 tab 查询参数可直接打开模型性能页签', async () => {
    mockUserRoles = ['admin']
    mockRoute.query = { tab: 'llmObservability' }

    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.get('[data-testid="system-config-tabs"]').attributes('data-active-key')).toBe(
      'llmObservability',
    )
  })

  it('0 条候选病历时展示客户化 warning 口径', () => {
    mockUserRoles = ['admin', 'qc_manager']
    mockState.preflightResult = {
      estimated_impact: 0,
      executable: false,
      blockers: [],
      warnings: [],
    }

    const wrapper = mountPage()

    expect(wrapper.text()).toContain('没有找到符合条件的已出院病历，请检查科室名称或出院日期范围。')
    expect(wrapper.text()).not.toContain('预检通过')
  })

  it('范围解析失败时只提示阻断原因，不误报为零候选病历', async () => {
    mockRunPreflight.mockResolvedValue({
      estimated_impact: 0,
      executable: false,
      blockers: ['候选病历范围解析失败，请检查日期、科室和源库住院登记配置'],
      warnings: [],
    })

    const wrapper = mountPage()
    await wrapper.get('[data-testid="check-record-scope-action"]').trigger('click')

    expect(mockMessageWarning).toHaveBeenCalledWith(
      '检查未通过：候选病历范围解析失败，请检查日期、科室和源库住院登记配置',
    )
    expect(mockMessageWarning).not.toHaveBeenCalledWith(
      '没有找到符合条件的已出院病历，请检查科室名称或出院日期范围。',
    )
  })
})
