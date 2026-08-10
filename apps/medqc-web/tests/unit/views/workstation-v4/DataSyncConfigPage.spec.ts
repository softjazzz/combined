import { mount } from '@vue/test-utils'
import { computed, reactive, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DataSyncConfigPage from '@/views/workstation-v4/DataSyncConfigPage.vue'

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
}

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
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
    runPreflight: vi.fn(),
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
        'a-tabs': { template: '<div><slot /></div>' },
        'a-tab-pane': { template: '<section><slot /></section>' },
        'a-tooltip': { template: '<span><slot /></span>' },
        'a-button': { template: '<button><slot /></button>' },
        'a-tag': { template: '<span><slot /></span>' },
        'a-progress': { template: '<div class="progress-stub" />' },
        'a-select': {
          props: ['value', 'options', 'disabled'],
          template: '<div class="select-stub"><slot /></div>',
        },
        'a-option': { template: '<option><slot /></option>' },
        'a-input': { template: '<input />' },
        'a-input-password': { template: '<input />' },
        'a-date-picker': { template: '<input />' },
        'a-empty': { template: '<div />' },
        ConnectionStudio: { template: '<div />' },
        SyncRunPanel: { template: '<div />' },
        FrontpageExtractionSettingsPanel: { template: '<div />' },
        LLMApiConfig: { template: '<div />' },
      },
    },
  })
}

describe('DataSyncConfigPage visit progress', () => {
  beforeEach(() => {
    mockUserRoles = ['admin', 'qc_manager']
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

  it('展示病历池可见口径的病历级进度', () => {
    const wrapper = mountPage()

    expect(wrapper.text()).toContain('病历进度')
    expect(wrapper.text()).toContain('3 / 20 份')
    expect(wrapper.text()).toContain('有 2 份病历明细已同步但病历池暂不可见')
  })

  it('没有 visit_progress 时仍可展示原有表级和行数进度', () => {
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

    expect(wrapper.text()).toContain('表进度')
    expect(wrapper.text()).toContain('已拉取行数')
    expect(wrapper.text()).toContain('0 / 20 份')
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

  it('在院范围只展示截止日期，不伪装成出院日期区间', async () => {
    mockState.policyForm.scope = 'running'

    const wrapper = mountPage()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('在院截止日期')
    expect(wrapper.text()).not.toContain('出院开始日期')
    expect(wrapper.text()).not.toContain('出院结束日期')
    mockState.policyForm.scope = 'final'
  })

  it('点击病历类型卡片直接更新同步范围', async () => {
    const wrapper = mountPage()

    await wrapper.get('[data-testid="sync-scene-running"]').trigger('click')

    expect(mockState.policyForm.scope).toBe('running')
    expect(wrapper.text()).toContain('在院截止日期')
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
    { role: 'qc_manager', frontpage: true, llm: false },
    { role: 'admin', frontpage: true, llm: true },
    { role: 'sync_admin', frontpage: true, llm: true },
    { role: 'super_admin', frontpage: true, llm: true },
    { role: 'doctor', frontpage: false, llm: false },
  ])('按 $role 的后端角色合同展示系统配置页签', ({ role, frontpage, llm }) => {
    mockUserRoles = [role]

    const wrapper = mountPage()

    expect(wrapper.find('[data-testid="frontpage-config-tab"]').exists()).toBe(frontpage)
    expect(wrapper.find('[data-testid="llm-config-tab"]').exists()).toBe(llm)
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
})
