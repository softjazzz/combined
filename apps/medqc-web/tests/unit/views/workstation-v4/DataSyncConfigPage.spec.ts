import { mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'
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
    hasPreflightPass: ref(true),
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
        'a-select': { template: '<div class="select-stub"><slot /></div>' },
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

  it('在主执行区展示终末病历同步的科室和出院日期范围', () => {
    const wrapper = mountPage()

    expect(wrapper.text()).toContain('终末同步范围')
    expect(wrapper.text()).toContain('抽取科室')
    expect(wrapper.text()).toContain('出院开始日期')
    expect(wrapper.text()).toContain('出院结束日期')
    expect(wrapper.text()).toContain('不支持在院病历')
  })

  it('演示账号只看到简化同步向导并隐藏实施诊断信息', () => {
    mockUserRoles = ['admin', 'qc_manager']
    mockState.preflightResult = null

    const wrapper = mountPage()
    const text = wrapper.text()

    expect(text).toContain('终末病历同步设置')
    expect(text).toContain('检查病历范围')
    expect(text).toContain('开始同步')
    expect(text).toContain('出院开始日期')
    expect(text).toContain('出院结束日期')
    expect(text).not.toContain('clinical_data')
    expect(text).not.toContain('本地 CDM')
    expect(text).not.toContain('discharge_record')
    expect(text).not.toContain('表组预检表')
    expect(text).not.toContain('实施诊断模式')
  })

  it('实施账号可以看到高级配置和运行日志入口', () => {
    mockUserRoles = ['sync_admin']

    const wrapper = mountPage()
    const text = wrapper.text()

    expect(text).toContain('实施诊断模式')
    expect(text).toContain('展开高级配置与日志')
    expect(text).toContain('clinical_data')
    expect(text).toContain('表组预检表')
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

    expect(wrapper.text()).toContain('没有找到符合条件的出院病历，请检查科室名称或出院日期范围。')
    expect(wrapper.text()).not.toContain('预检通过')
  })
})
