import { flushPromises, mount } from '@vue/test-utils'
import { computed, reactive, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DataSyncConfigPage from '@/views/workstation-v4/DataSyncConfigPage.vue'

const { mockRunPreflight, mockMessageWarning, mockLoadDepartments, mockInitialize } = vi.hoisted(() => ({
  mockRunPreflight: vi.fn(),
  mockMessageWarning: vi.fn(),
  mockLoadDepartments: vi.fn(),
  mockInitialize: vi.fn(),
}))

const mockState = reactive({
  pgSyncState: {} as Record<string, any>,
  preflightResult: null as Record<string, any> | null,
  isSyncing: false,
  isTestingAll: false,
  isPreflighting: false,
  isSavingPolicy: false,
  departmentsLoading: false,
  departmentsError: null as string | null,
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

vi.mock('@/views/workstation-v4/components/system-config/ClinicalSourceSettingsPanel.vue', () => ({
  default: { template: '<div data-testid="clinical-source-settings" />' },
}))

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
    initialize: mockInitialize,
    loadDepartments: mockLoadDepartments,
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
        AccountManagementPanel: { template: '<div data-testid="real-accounts-panel" />' },
        QcRuntimeSettingsPanel: { template: '<div data-testid="qc-runtime-panel" />' },
        DataPipelineSettingsPanel: {
          emits: ['selection', 'ready'],
          mounted() {
            this.$emit('selection', 'legacy_pg')
            this.$emit('ready', true)
          },
          template: '<div data-testid="pipeline-settings-panel"><button data-testid="choose-independent" @click="$emit(\'selection\', \'independent_cdm\')">独立链路</button><button data-testid="pipeline-load-failed" @click="$emit(\'ready\', false)">配置失败</button></div>',
        },
        DailyQcSchedulePanel: { template: '<div data-testid="daily-schedule-panel" />' },
      },
    },
  })
}

describe('DataSyncConfigPage visit progress', () => {
  it('系统管理员可直接进入质控运行设置', async () => {
    mockUserRoles = ['sync_admin']
    mockRoute.query = { tab: 'qcRuntime' }
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[data-testid="qc-runtime-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="qc-runtime-panel"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('演示账号不能通过链接进入质控运行设置', async () => {
    mockUserRoles = ['admin']
    mockAuthStore.user.is_demo_account = true
    mockRoute.query = { tab: 'qcRuntime' }
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[data-testid="qc-runtime-tab"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="qc-runtime-panel"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('独立链路隐藏旧PG执行与诊断入口，配置失败也不误显示旧默认', async () => {
    mockUserRoles = ['sync_admin']
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).not.toContain('高级设置与运行记录')
    await wrapper.get('[data-testid="choose-independent"]').trigger('click')
    expect(wrapper.find('[data-testid="check-record-scope-action"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('高级设置与运行记录')
    await wrapper.get('[data-testid="pipeline-load-failed"]').trigger('click')
    expect(wrapper.text()).not.toContain('病历数据同步设置')
    wrapper.unmount()
  })

  it('每日质控页签可直达且不初始化数据同步，非管理员不能直达', async () => {
    mockInitialize.mockClear()
    mockUserRoles = ['sync_admin']
    mockRoute.query = { tab: 'dailyQc' }
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[data-testid="daily-schedule-panel"]').exists()).toBe(true)
    expect(mockInitialize).not.toHaveBeenCalled()
    wrapper.unmount()
    mockUserRoles = ['doctor']
    const denied = mountPage()
    await flushPromises()
    expect(denied.find('[data-testid="daily-schedule-panel"]').exists()).toBe(false)
    denied.unmount()
  })
  it('管理员可在V5系统配置进入真实账号管理，不跳旧版页面', async () => {
    mockUserRoles = ['admin']
    mockRoute.query = { tab: 'accounts' }
    const wrapper = mountPage()
    await flushPromises()
    await flushPromises()
    expect(wrapper.find('[data-testid="account-management-tab"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="real-accounts-panel"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('非管理员不显示账号管理，不能通过查询参数打开', async () => {
    mockUserRoles = ['qc_manager']
    mockRoute.query = { tab: 'accounts' }
    const wrapper = mountPage()
    await flushPromises()
    await flushPromises()
    expect(wrapper.find('[data-testid="account-management-tab"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="real-accounts-panel"]').exists()).toBe(false)
    wrapper.unmount()
  })
  beforeEach(() => {
    mockInitialize.mockReset()
    mockRunPreflight.mockReset()
    mockMessageWarning.mockReset()
    mockLoadDepartments.mockReset()
    mockState.departmentsLoading = false
    mockState.departmentsError = null
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

  it('旧PG同步被固定停用，后台科室和旧任务状态不能触发初始化', async () => {
    mockState.departmentsLoading = true
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('[data-testid="check-record-scope-action"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('病历数据同步设置')
    expect(wrapper.text()).not.toContain('高级设置与运行记录')
    expect(mockInitialize).not.toHaveBeenCalled()
    expect(mockLoadDepartments).not.toHaveBeenCalled()
    expect(mockRunPreflight).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
