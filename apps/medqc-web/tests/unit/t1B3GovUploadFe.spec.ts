import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, effectScope, h, nextTick, reactive, type PropType } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { WORKSTATION_CONFIRMATION, type WorkstationConfirmOptions } from '@/components/layout/workstationConfirmation'

const hoisted = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
  routerReplace: vi.fn(),
  confirmCalls: [] as WorkstationConfirmOptions[],
  confirmNextDecision: true,
  clinicalSources: {
    options: vi.fn(),
    configuration: vi.fn(),
    save: vi.fn(),
    check: vi.fn(),
  },
  accountApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
  registrationApi: {
    list: vi.fn(),
    detail: vi.fn(),
    review: vi.fn(),
  },
  dailyQcService: {
    list: vi.fn(),
    options: vi.fn(),
    save: vi.fn(),
    history: vi.fn(),
  },
  llmEndpointService: {
    load: vi.fn(),
    save: vi.fn(),
  },
  frontpageApi: {
    getExtractionSettings: vi.fn(),
    updateExtractionSettings: vi.fn(),
    resetExtractionSettings: vi.fn(),
  },
  llmConfigService: {
    getDefaultSummary: vi.fn(),
    getProviders: vi.fn(),
    getModelsByProvider: vi.fn(),
    saveConfig: vi.fn(),
    testConfig: vi.fn(),
    addCustomModel: vi.fn(),
    deleteCustomModel: vi.fn(),
    resetDefaultSummary: vi.fn(),
    getLocalModelOptions: vi.fn(),
  },
  authFetch: vi.fn(),
  syncApi: {
    getStatus: vi.fn(),
    getStatistics: vi.fn(),
    getRuns: vi.fn(),
    triggerSync: vi.fn(),
    getDepartments: vi.fn(),
  },
}))

const mockAuthState = reactive({
  isAuthenticated: true,
  user: { id: 'actor-1', is_demo_account: false } as { id: string; is_demo_account?: boolean } | null,
  userRoles: ['admin'] as string[],
})

const mockRoute = reactive({
  query: {} as Record<string, string>,
})

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({ replace: hoisted.routerReplace }),
  onBeforeRouteLeave: vi.fn(),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => mockAuthState,
}))

vi.mock('ant-design-vue', () => ({
  message: hoisted.message,
  Modal: { confirm: vi.fn() },
}))

vi.mock('@/utils/auth-token', () => ({
  getAccessToken: () => 'test-token',
}))

vi.mock('@/api/clinicalSources', () => ({
  clinicalSourcesApi: hoisted.clinicalSources,
}))

vi.mock('@/api/accountManagement', () => ({
  listManagedAccounts: hoisted.accountApi.list,
  createManagedAccount: hoisted.accountApi.create,
  updateManagedAccount: hoisted.accountApi.update,
}))

vi.mock('@/api/accountRegistration', () => ({
  listRegistrations: hoisted.registrationApi.list,
  getRegistrationDetail: hoisted.registrationApi.detail,
  reviewRegistration: hoisted.registrationApi.review,
}))

vi.mock('@/services/dailyQcScheduleService', () => ({
  dailyQcScheduleService: hoisted.dailyQcService,
}))

vi.mock('@/services/llmEndpointService', () => ({
  llmEndpointService: hoisted.llmEndpointService,
}))

vi.mock('@/api/frontpage', () => ({
  frontpageApi: hoisted.frontpageApi,
}))

vi.mock('@/services/llmConfigService', () => ({
  llmConfigService: hoisted.llmConfigService,
}))

vi.mock('@/utils/auth-fetch', () => ({
  authFetch: hoisted.authFetch,
}))

vi.mock('@/api/sync', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/sync')>()
  return {
    ...actual,
    syncApi: {
      ...actual.syncApi,
      getStatus: hoisted.syncApi.getStatus,
      getStatistics: hoisted.syncApi.getStatistics,
      getRuns: hoisted.syncApi.getRuns,
      triggerSync: hoisted.syncApi.triggerSync,
      getDepartments: hoisted.syncApi.getDepartments,
    },
  }
})

import ExcelUploadView from '@/views/workstation-v4/frontpage/components/ExcelUploadView.vue'
import FieldMappingStep from '@/views/workstation-v4/frontpage/components/FieldMappingStep.vue'
import WorkstationV2View from '@/views/workstation-v4/WorkstationV2View.vue'
import DataSyncConfigPage from '@/views/workstation-v4/DataSyncConfigPage.vue'
import CDMDataView from '@/views/workstation-v4/CDMDataView.vue'
import AccountManagementPanel from '@/views/workstation-v4/components/system-config/AccountManagementPanel.vue'
import RegistrationReviewPanel from '@/views/workstation-v4/components/system-config/RegistrationReviewPanel.vue'
import DailyQcSchedulePanel from '@/views/workstation-v4/components/system-config/DailyQcSchedulePanel.vue'
import LLMEndpointSettings from '@/components/LLMEndpointSettings.vue'
import FrontpageExtractionSettingsPanel from '@/views/workstation-v4/components/system-config/FrontpageExtractionSettingsPanel.vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'
import { useDataSync } from '@/views/workstation-v4/composables/useDataSync'

function createMockConfirmation() {
  return {
    confirm(options: WorkstationConfirmOptions) {
      hoisted.confirmCalls.push(options)
      if (hoisted.confirmNextDecision) {
        void options.onOk?.()
      } else {
        void options.onCancel?.()
      }
    },
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const Slot = defineComponent({
  setup: (_, { slots }) => () => h('div', slots.default?.()),
})
const ButtonStub = defineComponent({
  props: { disabled: Boolean, loading: Boolean },
  setup: (props, { slots, attrs }) => () =>
    h('button', { ...attrs, disabled: props.disabled }, slots.default?.()),
})
const SelectStub = defineComponent({
  props: {
    value: { type: String, default: '' },
    options: {
      type: Array as PropType<Array<{ value: string; label: string }>>,
      default: undefined,
    },
    disabled: Boolean,
  },
  emits: ['update:value', 'change'],
  setup(props, { emit, slots, attrs }) {
    return () =>
      h(
        'select',
        {
          ...attrs,
          value: props.value,
          disabled: props.disabled,
          onChange: (event: Event) => {
            const value = (event.target as HTMLSelectElement).value
            emit('update:value', value)
            emit('change', value)
          },
        },
        props.options
          ? props.options.map((item) => h('option', { value: item.value }, item.label))
          : slots.default?.(),
      )
  },
})
const InputStub = defineComponent({
  props: { value: { type: String, default: '' }, disabled: Boolean },
  emits: ['update:value'],
  setup: (props, { emit, attrs }) => () =>
    h('input', {
      ...attrs,
      value: props.value,
      disabled: props.disabled,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
    }),
})
const AlertStub = defineComponent({
  props: { message: { type: String, default: '' }, description: { type: String, default: '' } },
  setup: (props) => () => h('div', { role: 'alert' }, `${props.message} ${props.description}`),
})

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetch).mockReset()
  hoisted.confirmCalls.length = 0
  hoisted.confirmNextDecision = true
  mockAuthState.isAuthenticated = true
  mockAuthState.user = { id: 'actor-1', is_demo_account: false }
  mockAuthState.userRoles = ['admin']
  mockRoute.query = {}
  window.sessionStorage.clear()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('Fix 1: /upload 202 异步契约、映射错误提取与分析结果透传', () => {
  it('ExcelUploadView 移除死返回按钮，202 自动轮询任务并拉取 /result 后进入映射，不再出现 undefined', async () => {
    vi.useFakeTimers()
    const statusCalls: string[] = []
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input)
      statusCalls.push(url)
      if (url.endsWith('/smart-upload')) {
        return {
          ok: true,
          status: 202,
          json: async () => ({
            success: true,
            task_id: 'task-202',
            file_id: 'abcd1234',
            filename: 'cases.xlsx',
            status: 'pending',
            progress: 10,
            status_url: '/api/v1/drg/smart-upload/tasks/task-202',
            result_url: '/api/v1/drg/smart-upload/tasks/task-202/result',
          }),
        } as Response
      }
      if (url.endsWith('/smart-upload/tasks/task-202')) {
        const pollCount = statusCalls.filter((u) => u.endsWith('/smart-upload/tasks/task-202')).length
        return {
          ok: true,
          status: 200,
          json: async () => ({
            task_id: 'task-202',
            status: pollCount === 1 ? 'running' : 'succeeded',
            progress: pollCount === 1 ? 50 : 100,
          }),
        } as Response
      }
      if (url.endsWith('/smart-upload/tasks/task-202/result')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            success: true,
            file_id: 'abcd1234',
            filename: 'cases.xlsx',
            row_count: 42,
            file_count: 2,
            columns: ['科室', '总费用'],
            sample_data: [{ 科室: '内科', 总费用: '1200' }],
          }),
        } as Response
      }
      throw new Error(`Unexpected url: ${url}`)
    })

    const wrapper = mount(ExcelUploadView, {
      global: {
        stubs: {
          MqIcon: true,
          FieldMappingStep: {
            props: ['fileId', 'rowCount', 'columns'],
            template: '<div data-testid="mapping-step">{{ fileId }}|{{ rowCount }}|{{ columns.join(",") }}</div>',
          },
        },
      },
    })

    expect(wrapper.find('.upload-back-btn').exists()).toBe(false)

    const file = new File(['dummy'], 'cases.xlsx', { type: 'application/vnd.ms-excel' })
    const inputEl = wrapper.get('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(inputEl, 'files', { value: [file], configurable: true })
    await wrapper.get('input[type="file"]').trigger('change')
    await wrapper.get('[data-testid="start-upload-btn"]').trigger('click')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()

    expect(wrapper.find('[data-testid="mapping-step"]').text()).toBe('abcd1234|42|科室,总费用')
    expect(hoisted.message.success).toHaveBeenCalledWith('文件上传成功！共 42 行数据，2 个文件')
    expect(String(hoisted.message.success.mock.calls[0][0])).not.toContain('undefined')
    wrapper.unmount()
  })

  it('ExcelUploadView 兼容 200 同步返回并支持上传中防重提与取消中止', async () => {
    const pendingUpload = deferred<Response>()
    let capturedSignal: AbortSignal | undefined
    vi.mocked(fetch).mockImplementationOnce((_input, init) => {
      capturedSignal = init?.signal as AbortSignal | undefined
      return pendingUpload.promise
    })

    const wrapper = mount(ExcelUploadView, {
      global: { stubs: { MqIcon: true, FieldMappingStep: true } },
    })

    const file = new File(['dummy'], 'sync.xlsx')
    const inputEl = wrapper.get('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(inputEl, 'files', { value: [file], configurable: true })
    await wrapper.get('input[type="file"]').trigger('change')

    await wrapper.get('[data-testid="start-upload-btn"]').trigger('click')
    await nextTick()
    expect(wrapper.find('[data-testid="cancel-upload-btn"]').exists()).toBe(true)

    await wrapper.get('[data-testid="cancel-upload-btn"]').trigger('click')
    await flushPromises()
    expect(capturedSignal?.aborted).toBe(true)
    expect(hoisted.message.info).toHaveBeenCalledWith('已取消上传')
    expect(hoisted.message.error).not.toHaveBeenCalled()

    // 取消后可重新上传并兼容 200 同步结果
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        file_id: 'sync0001',
        filename: 'sync.xlsx',
        row_count: 15,
        file_count: 1,
        columns: ['科室'],
        sample_data: [],
      }),
    } as Response)

    await wrapper.get('[data-testid="start-upload-btn"]').trigger('click')
    await flushPromises()
    expect(hoisted.message.success).toHaveBeenCalledWith('文件上传成功！共 15 行数据，1 个文件')
    wrapper.unmount()
  })

  it('FieldMappingStep 结构化提取 detail.error/missing_field_names 消除 [object Object] 且防重提', async () => {
    const confirmDeferred = deferred<Response>()
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/mapping-status/')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ ready: true, mappings: { 科室: 'department_name' }, confidence: 0.9 }),
        } as Response
      }
      if (url.includes('/mapping/fields')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            fields: {
              department_name: { name: '科室名称', description: '', required: true, category: 'base', aliases: [] },
            },
          }),
        } as Response
      }
      if (url.includes('/mapping/confirm')) {
        return confirmDeferred.promise
      }
      throw new Error(`Unexpected url: ${url}`)
    })

    const wrapper = mount(FieldMappingStep, {
      props: {
        fileId: 'abcd1234',
        fileName: 'cases.xlsx',
        rowCount: 10,
        columns: ['科室'],
        sampleData: [{ 科室: '内科' }],
      },
      global: {
        stubs: {
          'a-progress': true,
          'a-tag': Slot,
          'a-spin': true,
          'a-select': SelectStub,
          'a-select-option': true,
          'a-alert': AlertStub,
          'a-button': ButtonStub,
        },
      },
    })

    await flushPromises()
    const btn = wrapper.get('[data-testid="confirm-mapping-btn"]')
    await btn.trigger('click')
    await btn.trigger('click')

    const confirmCalls = vi.mocked(fetch).mock.calls.filter(([u]) => String(u).includes('/mapping/confirm'))
    expect(confirmCalls).toHaveLength(1)

    confirmDeferred.resolve({
      ok: false,
      status: 400,
      json: async () => ({
        detail: {
          success: false,
          error: '字段校验失败，请先完成必填字段映射',
          missing_field_names: ['总费用', 'DIP支付金额'],
        },
      }),
    } as Response)
    await flushPromises()

    expect(hoisted.message.error).toHaveBeenCalledWith(
      '字段校验失败，请先完成必填字段映射：缺少 总费用、DIP支付金额',
    )
    expect(String(hoisted.message.error.mock.calls[0][0])).not.toContain('[object Object]')
    wrapper.unmount()
  })

  it('WorkstationV2View handleAnalysisReady 保存并透传 charts/aiInsights/analysisResults', async () => {
    const wrapper = mount(WorkstationV2View, {
      props: { embedded: true, initialView: 'upload' },
      global: {
        stubs: {
          ExcelUploadView: {
            emits: ['analysis-ready'],
            template:
              '<button data-testid="emit-ready" @click="$emit(\'analysis-ready\', { charts: { c1: {} }, aiInsights: [\'亏损科室需关注\'], analysisResults: { overview: { total_cases: 12 } } })">ready</button>',
          },
          PostEventAnalysisView: { template: '<div data-testid="post-analysis-view" />' },
          CodingOptimizationDrawer: true,
          QCAlertPanel: true,
          'a-button': ButtonStub,
        },
      },
    })

    await wrapper.get('[data-testid="emit-ready"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="post-analysis-view"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="uploaded-analysis-summary"]').text()).toContain('亏损科室需关注')
    expect(wrapper.get('[data-testid="uploaded-analysis-summary"]').text()).toContain('12 条病例')
    expect(wrapper.emitted('analysis-ready')).toHaveLength(1)
    expect(window.sessionStorage.getItem('medqc:smart-upload-analysis-ready')).toContain('亏损科室需关注')
    wrapper.unmount()
  })
})

describe('Fix 2: qc_manager 系统配置默认 Tab 与 /data 安全降级', () => {
  it('DataSyncConfigPage 对 qc_manager 隐藏 dataSync 并默认落到 frontpageExtraction，切 Tab 双向同步 URL，兼容 super_admin', async () => {
    mockAuthState.userRoles = ['qc_manager']
    mockRoute.query = {}
    const wrapper = mount(DataSyncConfigPage, {
      global: {
        stubs: {
          ClinicalSourceSettingsPanel: true,
          DataPipelineSettingsPanel: true,
          FrontpageExtractionSettingsPanel: { template: '<div data-testid="fp-panel" />' },
          AccountManagementPanel: { template: '<div data-testid="acct-panel" />' },
          LLMApiConfig: { template: '<div data-testid="llm-panel" />' },
          DailyQcSchedulePanel: true,
          QcRuntimeSettingsPanel: true,
          LlmPerformanceObservabilityPanel: true,
          ConnectionStudio: true,
          SyncRunPanel: true,
          'a-modal': true,
        },
      },
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="system-config-tabs"]').attributes('data-active-key')).toBe(
      'frontpageExtraction',
    )
    expect(wrapper.find('[data-testid="fp-panel"]').exists()).toBe(true)
    wrapper.unmount()

    mockAuthState.userRoles = ['super_admin']
    mockRoute.query = {}
    const superWrapper = mount(DataSyncConfigPage, {
      global: {
        stubs: {
          ClinicalSourceSettingsPanel: true,
          DataPipelineSettingsPanel: true,
          FrontpageExtractionSettingsPanel: true,
          AccountManagementPanel: { template: '<div data-testid="acct-panel" />' },
          LLMApiConfig: true,
          DailyQcSchedulePanel: true,
          QcRuntimeSettingsPanel: true,
          LlmPerformanceObservabilityPanel: true,
          ConnectionStudio: true,
          SyncRunPanel: true,
          'a-modal': true,
        },
      },
    })
    await flushPromises()
    expect(superWrapper.find('[data-testid="account-management-tab"]').exists()).toBe(true)
    await superWrapper.get('[data-testid="account-management-tab"]').trigger('click')
    await flushPromises()
    expect(hoisted.routerReplace).toHaveBeenCalledWith({ query: { tab: 'accounts' } })
    expect(superWrapper.find('[data-testid="acct-panel"]').exists()).toBe(true)
    superWrapper.unmount()
  })

  it('CDMDataView 对 qc_manager 按角色跳过 /schema 安全降级为只读预览，且 loadTableData/openRecordModal 传递来源头与过滤参数', async () => {
    hoisted.clinicalSources.options.mockResolvedValue({
      default_source: 'legacy_pg',
      sources: [{ id: 'legacy_pg', enabled: true, name: '传统库' }],
    })
    mockAuthState.userRoles = ['qc_manager']

    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/stats')) return { ok: true, status: 200, json: async () => ({ total_records: 5 }) } as Response
      if (url.endsWith('/list')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [{ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', name: '张测试', mr_no: 'MR01' }],
          }),
        } as Response
      }
      if (url.endsWith('/departments')) return { ok: true, status: 200, json: async () => ['内科'] } as Response
      if (url.includes('/frontpage/')) {
        return { ok: true, status: 200, json: async () => ({ name: '张测试', diagnoses: [] }) } as Response
      }
      throw new Error(`Unexpected request for qc_manager: ${url}`)
    })

    const qcWrapper = mount(CDMDataView, {
      global: {
        stubs: {
          'a-button': ButtonStub,
          'a-alert': AlertStub,
          'a-tag': Slot,
          'a-modal': { props: ['open'], template: '<div v-if="open"><slot /></div>' },
          'a-spin': true,
          'a-badge': true,
          'a-tabs': Slot,
          'a-tab-pane': Slot,
        },
      },
    })
    await flushPromises()
    expect(vi.mocked(fetch).mock.calls.some(([u]) => String(u).includes('/schema'))).toBe(false)
    expect(qcWrapper.find('[data-testid="cdm-readonly-panel"]').exists()).toBe(true)
    expect(qcWrapper.text()).toContain('张测试')
    qcWrapper.unmount()

    // admin 可浏览表数据并翻页、打开表数据弹窗传过滤参数并处理单表非 200
    vi.mocked(fetch).mockReset()
    mockAuthState.userRoles = ['admin']
    vi.mocked(fetch).mockImplementation(async (input) => {
      const url = String(input)
      if (url.endsWith('/stats')) return { ok: true, status: 200, json: async () => ({ total_records: 5 }) } as Response
      if (url.endsWith('/list')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            items: [{ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', name: '张测试', mr_no: 'MR01' }],
          }),
        } as Response
      }
      if (url.endsWith('/departments')) return { ok: true, status: 200, json: async () => ['内科'] } as Response
      if (url.endsWith('/schema')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            total_tables: 1,
            tables: [{ name: 'mr', label: '病案首页', column_count: 1, columns: [{ name: 'mr_no', type: 'text' }] }],
          }),
        } as Response
      }
      if (url.includes('/frontpage/')) {
        return { ok: true, status: 200, json: async () => ({ name: '张测试', diagnoses: [] }) } as Response
      }
      if (url.includes('/table-data/qc_result')) {
        return { ok: false, status: 500, json: async () => ({ detail: 'boom' }) } as Response
      }
      if (url.includes('/table-data/')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            columns: ['institute_id', 'patient_id', 'visit_id'],
            items: [{ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' }],
            total: 120,
            page: url.includes('page=2') ? 2 : 1,
            page_size: 50,
          }),
        } as Response
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const adminWrapper = mount(CDMDataView, {
      global: {
        stubs: {
          'a-button': ButtonStub,
          'a-alert': AlertStub,
          'a-tag': Slot,
          'a-modal': { props: ['open'], template: '<div v-if="open" data-testid="record-modal"><slot /></div>' },
          'a-spin': true,
          'a-badge': true,
          'a-tabs': Slot,
          'a-tab-pane': Slot,
        },
      },
    })
    await flushPromises()
    await adminWrapper.findAll('.toggle-btn')[1].trigger('click')
    await flushPromises()
    await adminWrapper.get('[data-testid="table-page-next"]').trigger('click')
    await flushPromises()

    const page2Call = vi.mocked(fetch).mock.calls.find(([u]) => String(u).includes('/table-data/mr?page=2'))
    expect(page2Call).toBeDefined()
    expect((page2Call?.[1]?.headers as Record<string, string>)?.['X-Clinical-Source']).toBe('legacy_pg')

    await adminWrapper.get('[data-testid="pt-table-data-btn"]').trigger('click')
    await flushPromises()
    const modalCall = vi.mocked(fetch).mock.calls.find(([u]) =>
      String(u).includes('/table-data/mr?') && String(u).includes('patient_id=P1') && String(u).includes('visit_id=V1'),
    )
    expect(modalCall).toBeDefined()
    expect(adminWrapper.get('[data-testid="record-modal"]').text()).toContain('部分原始表读取失败')
    adminWrapper.unmount()
  })
})

describe('Fix 3: super_admin 权限与账号管理子视图 URL 同步', () => {
  it('AccountManagementPanel 与 RegistrationReviewPanel 均兼容 super_admin 并双向同步 section', async () => {
    mockAuthState.userRoles = ['super_admin']
    mockRoute.query = { tab: 'accounts' }
    hoisted.accountApi.list.mockResolvedValue({
      items: [
        {
          id: 'u1',
          username: 'root',
          email: 'root@example.com',
          display_name: '超管账号',
          institute_id: null,
          department: null,
          roles: ['super_admin'],
          is_active: true,
          created_at: null,
          updated_at: null,
          last_login_at: null,
        },
      ],
      total: 1,
      actor_id: 'actor-1',
      managed_institute_id: null,
      page: 1,
      page_size: 20,
    })
    hoisted.registrationApi.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })

    const acctWrapper = mount(AccountManagementPanel, {
      global: {
        stubs: {
          AModal: { props: ['open'], template: '<aside v-if="open"><slot /></aside>' },
          RegistrationReviewPanel: { template: '<div data-testid="reg-review-stub" />' },
        },
      },
    })
    await flushPromises()
    expect(hoisted.accountApi.list).toHaveBeenCalledTimes(1)
    expect(acctWrapper.text()).toContain('超级管理员')
    expect(acctWrapper.text()).not.toContain('仅系统管理员可管理账号')

    await acctWrapper.get('[data-testid="accounts-section-registrations"]').trigger('click')
    await flushPromises()
    expect(hoisted.routerReplace).toHaveBeenCalledWith({
      query: { tab: 'accounts', section: 'registrations' },
    })
    expect(acctWrapper.find('[data-testid="reg-review-stub"]').exists()).toBe(true)
    acctWrapper.unmount()

    const regWrapper = mount(RegistrationReviewPanel, {
      global: {
        stubs: { AModal: { props: ['open'], template: '<aside v-if="open"><slot /></aside>' } },
      },
    })
    await flushPromises()
    expect(hoisted.registrationApi.list).toHaveBeenCalledTimes(1)
    expect(regWrapper.text()).not.toContain('仅持久系统管理员可审批')
    regWrapper.unmount()
  })
})

describe('Fix 4: 保存失败不死锁、只读文案修正、恢复默认确认与脏草稿保护', () => {
  it('DailyQcSchedulePanel 保存失败后修改字段清空提交错误并可重试保存成功', async () => {
    mockAuthState.userRoles = ['admin']
    hoisted.dailyQcService.list.mockResolvedValue({
      items: [],
      scheduler_enabled: false,
      local_process_active: false,
    })
    hoisted.dailyQcService.options.mockResolvedValue({
      institutes: ['A'],
      departments: ['ICU'],
      rule_sets: [{ key: 'luxian_0609_qc_v1', name: '正式规则', scope: 'all' }],
    })
    hoisted.dailyQcService.save
      .mockRejectedValueOnce(new Error('network glitch'))
      .mockResolvedValueOnce({ id: 'p1' })

    const ModalStub = defineComponent({
      props: { open: Boolean, okButtonProps: { type: Object, default: () => ({}) } },
      emits: ['ok'],
      setup: (props, { slots, emit }) => () =>
        props.open
          ? h('div', [
              slots.default?.(),
              h(
                'button',
                {
                  'data-testid': 'modal-ok',
                  disabled: props.okButtonProps.disabled,
                  onClick: () => emit('ok'),
                },
                '确定',
              ),
            ])
          : null,
    })

    const wrapper = mount(DailyQcSchedulePanel, {
      global: {
        stubs: {
          'a-space': Slot,
          'a-tag': Slot,
          'a-form': Slot,
          'a-form-item': Slot,
          'a-input-number': true,
          'a-button': ButtonStub,
          'a-modal': ModalStub,
          'a-select': SelectStub,
          'a-input': InputStub,
          'a-switch': true,
          'a-alert': AlertStub,
          'a-drawer': true,
          'a-empty': true,
        },
      },
    })
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text() === '新增计划')?.trigger('click')
    await flushPromises()
    await wrapper.get('input[data-testid="schedule-name"]').setValue('计划1')

    await wrapper.get('[data-testid="modal-ok"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('保存失败')
    expect((wrapper.get('[data-testid="modal-ok"]').element as HTMLButtonElement).disabled).toBe(false)

    await wrapper.get('input[data-testid="schedule-name"]').setValue('计划1-重试')
    await flushPromises()
    expect(wrapper.text()).not.toContain('保存失败')

    await wrapper.get('[data-testid="modal-ok"]').trigger('click')
    await flushPromises()
    expect(hoisted.dailyQcService.save).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('LLMEndpointSettings 非冲突提交失败不永久置灰，修改字段可清空错误并重试保存', async () => {
    mockAuthState.userRoles = ['super_admin']
    const baseView = {
      version: 1,
      editable: true,
      audit: [],
      providers: [
        {
          provider_code: 'ollama',
          name: '本地服务',
          source: 'saved' as const,
          endpoint: 'http://old.test/v1',
          enabled: true,
          key_configured: false,
        },
      ],
    }
    hoisted.llmEndpointService.load.mockResolvedValue(baseView)
    hoisted.llmEndpointService.save
      .mockRejectedValueOnce(new Error('请检查服务地址、启用状态和密钥操作。'))
      .mockResolvedValueOnce({ ...baseView, version: 2 })

    const DrawerStub = defineComponent({
      props: { open: Boolean },
      setup: (p, { slots }) => () => (p.open ? h('aside', slots.default?.()) : null),
    })

    const wrapper = mount(LLMEndpointSettings, {
      global: {
        stubs: {
          'a-drawer': DrawerStub,
          'a-button': ButtonStub,
          'a-form': Slot,
          'a-form-item': Slot,
          'a-input': InputStub,
          'a-input-password': InputStub,
          'a-switch': true,
          'a-checkbox': true,
          'a-select': SelectStub,
          'a-alert': AlertStub,
        },
      },
    })
    await wrapper.get('[data-testid="endpoint-open"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="endpoint-save"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('请检查服务地址')
    expect((wrapper.get('[data-testid="endpoint-save"]').element as HTMLButtonElement).disabled).toBe(false)

    await wrapper.findAll('input')[0].setValue('http://fixed.test/v1')
    await flushPromises()
    expect(wrapper.text()).not.toContain('请检查服务地址')

    await wrapper.get('[data-testid="endpoint-save"]').trigger('click')
    await flushPromises()
    expect(hoisted.llmEndpointService.save).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('FrontpageExtractionSettingsPanel 修正只读提示文案且恢复默认需二次确认', async () => {
    const sampleSettings = {
      source: 'file',
      settings: {
        sql_prefill_enabled: true,
        llm_backfill_enabled: true,
        allow_force_llm_regenerate: true,
        include_demo_records: false,
        auto_hide_demo_when_real_data: true,
        demo_hide_threshold: 1,
        stream_progress_enabled: true,
        default_preview_tab: 'preview' as const,
      },
    }
    hoisted.frontpageApi.getExtractionSettings.mockResolvedValue(sampleSettings)
    hoisted.frontpageApi.resetExtractionSettings.mockResolvedValue(sampleSettings)

    mockAuthState.userRoles = ['doctor']
    const readonlyWrapper = mount(FrontpageExtractionSettingsPanel, {
      global: {
        provide: { [WORKSTATION_CONFIRMATION as symbol]: createMockConfirmation() },
        stubs: {
          'a-alert': AlertStub,
          'a-button': ButtonStub,
          'a-switch': true,
          'a-input-number': true,
          'a-select': true,
        },
      },
    })
    await flushPromises()
    expect(readonlyWrapper.text()).not.toContain('当前为只读模式（qc_manager）')
    readonlyWrapper.unmount()

    mockAuthState.userRoles = ['admin']
    const mgrWrapper = mount(FrontpageExtractionSettingsPanel, {
      global: {
        provide: { [WORKSTATION_CONFIRMATION as symbol]: createMockConfirmation() },
        stubs: {
          'a-alert': AlertStub,
          'a-button': ButtonStub,
          'a-switch': true,
          'a-input-number': true,
          'a-select': true,
        },
      },
    })
    await flushPromises()
    hoisted.confirmNextDecision = false
    await mgrWrapper.get('[data-testid="frontpage-settings-reset"]').trigger('click')
    await flushPromises()
    expect(hoisted.confirmCalls).toHaveLength(1)
    expect(hoisted.frontpageApi.resetExtractionSettings).not.toHaveBeenCalled()

    hoisted.confirmNextDecision = true
    await mgrWrapper.get('[data-testid="frontpage-settings-reset"]').trigger('click')
    await flushPromises()
    expect(hoisted.frontpageApi.resetExtractionSettings).toHaveBeenCalledTimes(1)
    mgrWrapper.unmount()
  })

  it('LLMApiConfig 恢复默认需二次确认，且脏草稿在系统配置切 Tab 时弹窗拦截', async () => {
    mockAuthState.userRoles = ['admin']
    mockRoute.query = { tab: 'llmConfig' }
    hoisted.llmConfigService.getDefaultSummary.mockResolvedValue({
      provider_code: 'alibaba',
      model_code: 'm1',
      custom_parameters: { temperature: 0.2, top_p: 0.9, max_tokens: 4000 },
      source: 'database',
      readonly: false,
    })
    hoisted.llmConfigService.getProviders.mockResolvedValue([
      { provider_code: 'alibaba', provider_name: '阿里云' },
    ])
    hoisted.llmConfigService.getLocalModelOptions.mockResolvedValue([])
    hoisted.llmConfigService.getModelsByProvider.mockResolvedValue([
      { model_code: 'm1', model_name: 'Model 1' },
      { model_code: 'm2', model_name: 'Model 2' },
    ])
    hoisted.llmConfigService.resetDefaultSummary.mockResolvedValue({
      provider_code: 'alibaba',
      model_code: 'm1',
      custom_parameters: { temperature: 0.2, top_p: 0.9, max_tokens: 4000 },
      source: 'env',
      readonly: false,
    })
    hoisted.authFetch.mockResolvedValue({ ok: true, status: 200 })

    const pageWrapper = mount(DataSyncConfigPage, {
      global: {
        provide: { [WORKSTATION_CONFIRMATION as symbol]: createMockConfirmation() },
        stubs: {
          ClinicalSourceSettingsPanel: true,
          DataPipelineSettingsPanel: true,
          FrontpageExtractionSettingsPanel: true,
          AccountManagementPanel: { template: '<div data-testid="acct-panel" />' },
          DailyQcSchedulePanel: true,
          QcRuntimeSettingsPanel: true,
          LlmPerformanceObservabilityPanel: true,
          ConnectionStudio: true,
          SyncRunPanel: true,
          LLMEndpointSettings: true,
          LLMTaskRoleSettings: true,
          'a-modal': true,
          'a-alert': AlertStub,
          'a-button': ButtonStub,
          'a-select': SelectStub,
          'a-select-option': { props: ['value'], template: '<option :value="value"><slot /></option>' },
          'a-segmented': true,
          'a-slider': true,
          'a-input': InputStub,
          'a-input-number': true,
        },
      },
    })
    await flushPromises()

    // 恢复默认需二次确认
    hoisted.confirmNextDecision = false
    await pageWrapper.get('[data-testid="llm-reset-default"]').trigger('click')
    await flushPromises()
    expect(hoisted.llmConfigService.resetDefaultSummary).not.toHaveBeenCalled()

    // 修改模型产生脏草稿 -> 切 Tab 被取消则留在 llmConfig
    await pageWrapper.get('#llm-default-model').setValue('m2')
    await flushPromises()
    hoisted.confirmNextDecision = false
    await pageWrapper.get('[data-testid="account-management-tab"]').trigger('click')
    await flushPromises()
    expect(pageWrapper.get('[data-testid="system-config-tabs"]').attributes('data-active-key')).toBe(
      'llmConfig',
    )

    // 确认放弃修改 -> 成功切到 accounts
    hoisted.confirmNextDecision = true
    await pageWrapper.get('[data-testid="account-management-tab"]').trigger('click')
    await flushPromises()
    expect(pageWrapper.get('[data-testid="system-config-tabs"]').attributes('data-active-key')).toBe(
      'accounts',
    )
    pageWrapper.unmount()
  })
})

describe('Fix 5: useDataSync 卸载清理、指数退避上限与延后判终态', () => {
  it('onScopeDispose 自动停止轮询，不再泄漏定时器', async () => {
    vi.useFakeTimers()
    hoisted.syncApi.triggerSync.mockReturnValueOnce(new Promise(() => {}))
    hoisted.syncApi.getStatus.mockResolvedValue({ pg_sync: { is_running: true } })
    hoisted.syncApi.getStatistics.mockResolvedValue({ PENDING: 0, PARTIAL: 0, SYNCED: 1, STALE: 0, FAILED: 0 })

    const scope = effectScope()
    const sync = scope.run(() => useDataSync())!
    sync.resetState()
    void sync.executeSync('pg')

    await vi.advanceTimersByTimeAsync(2_000)
    expect(hoisted.syncApi.getStatus).toHaveBeenCalledTimes(1)

    scope.stop()
    await vi.advanceTimersByTimeAsync(20_000)
    expect(hoisted.syncApi.getStatus).toHaveBeenCalledTimes(1)
    sync.resetState()
  })

  it('轮询连续报错执行指数退避并在达到最大重试次数后停止', async () => {
    vi.useFakeTimers()
    hoisted.syncApi.triggerSync.mockReturnValueOnce(new Promise(() => {}))
    hoisted.syncApi.getStatus.mockRejectedValue(new Error('network down'))

    const scope = effectScope()
    const sync = scope.run(() => useDataSync())!
    sync.resetState()
    void sync.executeSync('pg')

    // 2s -> fail 1 (next 4s)
    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()
    expect(hoisted.syncApi.getStatus).toHaveBeenCalledTimes(1)

    // 2s later still hasn't retried (backoff is 4s)
    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()
    expect(hoisted.syncApi.getStatus).toHaveBeenCalledTimes(1)

    // +2s (total 4s) -> fail 2 (next 8s)
    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()
    expect(hoisted.syncApi.getStatus).toHaveBeenCalledTimes(2)

    // +8s -> fail 3 (next 16s), +16s -> fail 4 (next 30s), +30s -> fail 5 (stops!)
    await vi.advanceTimersByTimeAsync(8_000 + 16_000 + 30_000)
    await flushPromises()
    expect(hoisted.syncApi.getStatus).toHaveBeenCalledTimes(5)
    expect(sync.state.isSyncing).toBe(false)

    // 再推进 120s 不再继续无限重试
    await vi.advanceTimersByTimeAsync(120_000)
    await flushPromises()
    expect(hoisted.syncApi.getStatus).toHaveBeenCalledTimes(5)

    scope.stop()
    sync.resetState()
  })

  it('triggerSync 在途时首次 poll 返回 is_running=false 不误判终态，确认 running 后再结束', async () => {
    vi.useFakeTimers()
    const triggerDef = deferred<{ success: boolean; status: string }>()
    hoisted.syncApi.triggerSync.mockReturnValueOnce(triggerDef.promise)
    hoisted.syncApi.getStatistics.mockResolvedValue({ PENDING: 0, PARTIAL: 0, SYNCED: 5, STALE: 0, FAILED: 0 })
    hoisted.syncApi.getRuns.mockResolvedValue({ items: [], total: 0 })
    hoisted.syncApi.getStatus
      .mockResolvedValueOnce({ pg_sync: { is_running: false } })
      .mockResolvedValueOnce({ pg_sync: { is_running: true } })
      .mockResolvedValueOnce({ pg_sync: { is_running: false } })

    const scope = effectScope()
    const sync = scope.run(() => useDataSync())!
    sync.resetState()
    void sync.executeSync('pg')

    // 2s: 尚未进入 running，不应误判结束
    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()
    expect(sync.state.isSyncing).toBe(true)
    expect(hoisted.syncApi.getRuns).not.toHaveBeenCalled()

    // 4s: 确认 running
    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()
    expect(sync.state.isSyncing).toBe(true)

    // 6s: running -> false，真正判终态并拉历史
    await vi.advanceTimersByTimeAsync(2_000)
    await flushPromises()
    expect(sync.state.isSyncing).toBe(false)
    expect(hoisted.syncApi.getRuns).toHaveBeenCalledTimes(1)

    scope.stop()
    sync.resetState()
  })
})
