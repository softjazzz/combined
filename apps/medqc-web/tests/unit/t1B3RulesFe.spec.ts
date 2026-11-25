/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import { defineComponent, h, reactive, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WORKSTATION_NAV, resolveBreadcrumb } from '@/components/layout/workstationNav'

const confirmedResultsOnlyRef = ref(false)

vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({
    confirmedResultsOnly: confirmedResultsOnlyRef,
  }),
}))

vi.mock('@/data/qcRuleCases', () => ({
  qcRuleCaseMap: {},
  buildCaseText: vi.fn(() => ''),
}))

const hoisted = vi.hoisted(() => ({
  route: {
    path: '/workstation-v5/rules',
    params: { ruleId: 'LX0609-09-01-02' } as Record<string, string>,
    query: {} as Record<string, unknown>,
  },
  routerPush: vi.fn(),
  routerReplace: vi.fn(() => Promise.resolve()),
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
  Modal: {
    confirm: vi.fn(),
  },
  apiGet: vi.fn(),
  apiGetCurrentUser: vi.fn(),
  fetchSemanticRulesFromBackend: vi.fn(),
  fetchSichuanRuleSetsFromBackend: vi.fn(),
  fetchRulePrompt: vi.fn(),
  saveRulePrompt: vi.fn(),
  executeSemanticRuleTest: vi.fn(),
  listSichuanWorkspaceBatchJobs: vi.fn(),
  createSichuanWorkspaceBatchJob: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  getSichuanWorkspaceBatchJobDebugSnapshot: vi.fn(),
  listWorkspaceDrafts: vi.fn(),
  updateWorkspaceDraft: vi.fn(),
  generateWorkspaceDraftPrompt: vi.fn(),
  runWorkspaceSingleTest: vi.fn(),
  getWorkspaceRecordFilters: vi.fn(),
  getWorkspaceRecords: vi.fn(),
  listWorkspaceBatchJobs: vi.fn(),
  getWorkspaceBatchJob: vi.fn(),
  createWorkspaceBatchJob: vi.fn(),
  getAdminRecordList: vi.fn(),
  getDepartmentList: vi.fn(),
  getRecordDetail: vi.fn(),
  getValidationRule: vi.fn(),
  listValidationRules: vi.fn(),
  saveCaseAnswer: vi.fn(),
  startValidationRun: vi.fn(),
  concludeRule: vi.fn(),
  createManualTestMedicalRecord: vi.fn(),
  getEditableMedicalRecordDocuments: vi.fn(),
  fetchSurgeryProcedureCatalog: vi.fn(),
}))

const reactiveRoute = reactive(hoisted.route)

vi.mock('vue-router', () => ({
  useRoute: () => reactiveRoute,
  useRouter: () => ({
    push: hoisted.routerPush,
    replace: hoisted.routerReplace,
  }),
  onBeforeRouteLeave: vi.fn(),
}))

vi.mock('ant-design-vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('ant-design-vue')>()
  return {
    ...actual,
    message: hoisted.message,
    Modal: hoisted.Modal,
  }
})

vi.mock('@/services/apiService', () => ({
  ApiService: {
    get: hoisted.apiGet,
    getCurrentUser: hoisted.apiGetCurrentUser,
  },
}))

vi.mock('@/views/workstation-v4/semantic-rules/service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/views/workstation-v4/semantic-rules/service')>()
  return {
    ...actual,
    fetchSemanticRulesFromBackend: hoisted.fetchSemanticRulesFromBackend,
    fetchSichuanRuleSetsFromBackend: hoisted.fetchSichuanRuleSetsFromBackend,
    fetchRulePrompt: hoisted.fetchRulePrompt,
    saveRulePrompt: hoisted.saveRulePrompt,
    executeSemanticRuleTest: hoisted.executeSemanticRuleTest,
  }
})

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  listSichuanWorkspaceBatchJobs: hoisted.listSichuanWorkspaceBatchJobs,
  createSichuanWorkspaceBatchJob: hoisted.createSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob: hoisted.getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot: hoisted.getSichuanWorkspaceBatchJobDebugSnapshot,
  cancelSichuanWorkspaceBatchJob: vi.fn(),
  retrySichuanWorkspaceBatchJob: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
}))

vi.mock('@/services/custom-rule-workspace-service', () => ({
  listWorkspaceDrafts: hoisted.listWorkspaceDrafts,
  createWorkspaceDraft: vi.fn(),
  updateWorkspaceDraft: hoisted.updateWorkspaceDraft,
  deleteWorkspaceDraft: vi.fn(),
  generateWorkspaceDraftPrompt: hoisted.generateWorkspaceDraftPrompt,
  publishWorkspaceDraft: vi.fn(),
  getWorkspaceRecordFilters: hoisted.getWorkspaceRecordFilters,
  getWorkspaceRecords: hoisted.getWorkspaceRecords,
  runWorkspaceSingleTest: hoisted.runWorkspaceSingleTest,
  createWorkspaceBatchJob: hoisted.createWorkspaceBatchJob,
  listWorkspaceBatchJobs: hoisted.listWorkspaceBatchJobs,
  getWorkspaceBatchJob: hoisted.getWorkspaceBatchJob,
  cancelWorkspaceBatchJob: vi.fn(),
  retryWorkspaceBatchJob: vi.fn(),
  exportWorkspaceBatchJob: vi.fn(),
}))

vi.mock('@/api/qcAdmin', () => ({
  getAdminRecordList: hoisted.getAdminRecordList,
  getDepartmentList: hoisted.getDepartmentList,
  getRecordDetail: hoisted.getRecordDetail,
}))

vi.mock('@/services/rule-validation-service', () => ({
  listValidationRules: hoisted.listValidationRules,
  getValidationRule: hoisted.getValidationRule,
  saveCaseAnswer: hoisted.saveCaseAnswer,
  startValidationRun: hoisted.startValidationRun,
  concludeRule: hoisted.concludeRule,
}))

vi.mock('@/services/manual-case-sample-service', () => ({
  createManualTestMedicalRecord: hoisted.createManualTestMedicalRecord,
  getEditableMedicalRecordDocuments: hoisted.getEditableMedicalRecordDocuments,
}))

vi.mock('@/views/workstation-v4/surgery-catalog/service', () => ({
  fetchSurgeryProcedureCatalog: hoisted.fetchSurgeryProcedureCatalog,
}))

import SemanticRulesWorkspace from '@/views/workstation-v4/semantic-rules/SemanticRulesWorkspace.vue'
import SemanticRulesTableSection from '@/views/workstation-v4/semantic-rules/components/SemanticRulesTableSection.vue'
import SemanticRuleDetailModal from '@/views/workstation-v4/semantic-rules/components/modals/SemanticRuleDetailModal.vue'
import SemanticRuleTestModal from '@/views/workstation-v4/semantic-rules/components/modals/SemanticRuleTestModal.vue'
import { useSemanticRulesWorkspace } from '@/views/workstation-v4/semantic-rules/composables/useSemanticRulesWorkspace'
import CodingRulesTab from '@/components/rules/CodingRulesTab.vue'
import FrontpageRulesTab from '@/components/rules/FrontpageRulesTab.vue'
import SettlementRulesTab from '@/components/rules/SettlementRulesTab.vue'
import CustomQCExperienceView from '@/views/workstation-v4/CustomQCExperienceView.vue'
import CustomRuleWorkspaceView from '@/views/rules/CustomRuleWorkspaceView.vue'
import RuleValidationListView from '@/views/workstation-v4/rule-validation/RuleValidationListView.vue'
import RuleValidationDetailView from '@/views/workstation-v4/rule-validation/RuleValidationDetailView.vue'
import RuleValidationNewCaseView from '@/views/workstation-v4/rule-validation/RuleValidationNewCaseView.vue'
import SurgeryProcedureCatalogView from '@/views/workstation-v4/components/SurgeryProcedureCatalogView.vue'
import WorkstationRulesView from '@/views/workstation-v4/WorkstationRulesView.vue'

function setDemoUser(isDemo: boolean) {
  confirmedResultsOnlyRef.value = isDemo
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

const RouterLinkStub = defineComponent({
  props: ['to'],
  setup(props, { slots, attrs }) {
    return () => h('a', { ...attrs, 'data-to': JSON.stringify(props.to) }, slots.default?.())
  },
})

const AButtonStub = defineComponent({
  inheritAttrs: false,
  props: { disabled: Boolean, loading: Boolean },
  emits: ['click'],
  setup(props, { slots, attrs, emit }) {
    return () =>
      h(
        'button',
        {
          ...attrs,
          disabled: props.disabled,
          onClick: (e: MouseEvent) => {
            if (!props.disabled) emit('click', e)
          },
        },
        slots.default?.(),
      )
  },
})

const AModalStub = defineComponent({
  props: { open: Boolean },
  emits: ['update:open', 'cancel'],
  setup(props, { slots }) {
    return () => (props.open ? h('div', { class: 'a-modal-stub' }, slots.default?.()) : null)
  },
})

const AAlertStub = defineComponent({
  props: { message: String, description: String, type: String },
  setup(props, { attrs }) {
    return () =>
      h('div', { ...attrs, class: 'a-alert-stub' }, `${props.message || ''} ${props.description || ''}`)
  },
})

const passthrough = defineComponent({
  setup(_, { slots, attrs }) {
    return () => h('div', attrs, slots.default?.())
  },
})

const inputStub = defineComponent({
  props: ['value'],
  emits: ['update:value'],
  setup(props, { emit, attrs }) {
    return () =>
      h('input', {
        ...attrs,
        value: props.value,
        onInput: (e: Event) => emit('update:value', (e.target as HTMLInputElement).value),
      })
  },
})

const textareaStub = defineComponent({
  props: ['value'],
  emits: ['update:value'],
  setup(props, { emit, attrs }) {
    return () =>
      h('textarea', {
        ...attrs,
        value: props.value,
        onInput: (e: Event) => emit('update:value', (e.target as HTMLTextAreaElement).value),
      })
  },
})

beforeEach(() => {
  vi.clearAllMocks()
  setDemoUser(false)
  reactiveRoute.path = '/workstation-v5/rules'
  reactiveRoute.params = { ruleId: 'LX0609-09-01-02' }
  reactiveRoute.query = {}
  hoisted.apiGetCurrentUser.mockResolvedValue({
    success: true,
    data: { id: 'admin-1', roles: ['admin'], is_demo_account: false },
  })
  hoisted.fetchSichuanRuleSetsFromBackend.mockResolvedValue([])
  hoisted.fetchSemanticRulesFromBackend.mockResolvedValue({
    rules: [],
    stats: {
      total_rules: 0,
      rule_categories: [],
      complexity_distribution: {},
      defect_level_distribution: {},
    },
  })
  hoisted.listSichuanWorkspaceBatchJobs.mockResolvedValue({
    success: true,
    data: { items: [], total: 0 },
  })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('1. 语义规则 P0 阻断、并发竞态与演示隔离', () => {
  it('SemanticRulesWorkspace 挂载结果抽屉、切换规则集不重复发请求且挂载时不无谓调用 loadBatchJobs', async () => {
    const TableSectionStub = defineComponent({
      name: 'SemanticRulesTableSectionStub',
      emits: ['update:ruleSetKey', 'ruleSetChange'],
      template: '<div class="table-stub" />',
    })
    const wrapper = shallowMount(SemanticRulesWorkspace, {
      global: {
        stubs: {
          SemanticRulesTableSection: TableSectionStub,
          SemanticRulesBatchResultDrawer: {
            props: ['open'],
            template: '<div data-testid="mounted-batch-result-drawer" :data-open="String(open)" />',
          },
          SemanticRuleDetailModal: true,
          SemanticRuleTestModal: true,
          CustomQcBatchLaunchModal: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="mounted-batch-result-drawer"]').exists()).toBe(true)
    expect(hoisted.listSichuanWorkspaceBatchJobs).not.toHaveBeenCalled()
    expect(hoisted.fetchSemanticRulesFromBackend).toHaveBeenCalledTimes(1)

    // 模拟 TableSection 同时触发 update:ruleSetKey 与 ruleSetChange，仅应触发一次规则刷新
    const tableStub = wrapper.getComponent(TableSectionStub)
    tableStub.vm.$emit('update:ruleSetKey', 'luxian_0609_qc_v1')
    tableStub.vm.$emit('ruleSetChange', 'luxian_0609_qc_v1')
    await flushPromises()
    expect(hoisted.fetchSemanticRulesFromBackend).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('useSemanticRulesWorkspace 分离 promptError 与 currentPrompt，resetFilters 清除 releaseScope，且 loadPrompt 按序号防乱序覆盖', async () => {
    const firstPrompt = deferred<{ prompt: string; isDefaultPrompt: boolean }>()
    const secondPrompt = deferred<{ prompt: string; isDefaultPrompt: boolean }>()
    hoisted.fetchRulePrompt
      .mockReturnValueOnce(firstPrompt.promise)
      .mockReturnValueOnce(secondPrompt.promise)
      .mockRejectedValueOnce(new Error('后端超时'))

    const Host = defineComponent({
      setup() {
        return useSemanticRulesWorkspace()
      },
      render() {
        return h('div')
      },
    })
    const wrapper = mount(Host)
    await flushPromises()
    const vm = wrapper.vm as unknown as ReturnType<typeof useSemanticRulesWorkspace>

    vm.queryState.releaseScope = 'acceptance_only'
    vm.resetFilters()
    expect(vm.queryState.releaseScope).toBe('')

    const ruleA = { rule_id: 'SC-001', name: '规则A' } as any
    const ruleB = { rule_id: 'SC-002', name: '规则B' } as any

    const p1 = vm.openRuleDetail(ruleA)
    const p2 = vm.openRuleDetail(ruleB)
    secondPrompt.resolve({ prompt: 'PROMPT_B', isDefaultPrompt: false })
    await p2
    firstPrompt.resolve({ prompt: 'PROMPT_A_STALE', isDefaultPrompt: false })
    await p1

    expect(vm.currentPrompt).toBe('PROMPT_B')
    expect(vm.promptError).toBe('')

    // 失败时仅写 promptError，绝不污染 currentPrompt / editingPrompt
    await vm.openRuleDetail({ rule_id: 'SC-003', name: '规则C' } as any)
    expect(vm.promptError).toContain('后端超时')
    expect(vm.currentPrompt).toBe('')
    expect(vm.editingPrompt).toBe('')

    wrapper.unmount()
  })

  it('LX0609 规则禁用纯文本测试并引导至规则验收；未保存 Prompt 关闭前弹出二次确认', async () => {
    const lxRule = {
      rule_id: 'LX0609-01-01-01',
      rule_code: 'LX0609-01-01-01',
      name: '入院记录时效',
      description: '',
      category: '入院记录',
      complexity: '低复杂度',
      defect_level: '严重缺陷',
      score_deduction: 3,
      applicable_documents: ['admission_record'],
      medical_domain: '通用',
      requires_rag: false,
      requires_cot: false,
      primary_execution_rule_id: 'SC-002',
      mapped_rule_ids: ['SC-002'],
    }

    const tableWrapper = mount(SemanticRulesTableSection, {
      props: {
        loading: false,
        rules: [lxRule],
        total: 1,
        ruleSetKey: 'luxian_0609_qc_v1',
        ruleSetOptions: [],
        keywordInput: '',
        complexity: '',
        defectLevel: '',
        documentType: '',
        complexityOptions: [],
        defectOptions: [],
        documentOptions: [],
        pagination: { current: 1, pageSize: 10, total: 1 },
      },
      global: {
        stubs: {
          ProQueryBar: passthrough,
          ProStandardTable: defineComponent({
            props: ['columns', 'dataSource'],
            template: `<div><template v-for="c in columns" :key="c.key"><slot name="bodyCell" :column="c" :record="dataSource[0]" :index="0" /></template></div>`,
          }),
          'a-button': AButtonStub,
          'a-input': inputStub,
          'a-select': passthrough,
          'a-select-option': passthrough,
          RouterLink: RouterLinkStub,
        },
      },
    })
    const testBtn = tableWrapper.get('[data-testid="start-rule-test"]')
    expect(testBtn.attributes('disabled')).toBeDefined()
    await testBtn.trigger('click')
    expect(tableWrapper.emitted('startTest')).toBeUndefined()

    const detailLx = mount(SemanticRuleDetailModal, {
      props: {
        open: true,
        rule: lxRule,
        isAdmin: true,
        promptLoading: false,
        isEditingPrompt: false,
        currentPrompt: '',
        editingPrompt: '',
      },
      global: {
        stubs: {
          'a-modal': AModalStub,
          'a-alert': AAlertStub,
          'a-button': AButtonStub,
          'a-descriptions': passthrough,
          'a-descriptions-item': passthrough,
          RouterLink: RouterLinkStub,
        },
      },
    })
    expect(detailLx.find('[data-testid="lx0609-test-guide"]').exists()).toBe(true)
    expect(detailLx.get('[data-testid="detail-start-test"]').attributes('disabled')).toBeDefined()
    expect(detailLx.find('[data-testid="detail-go-rule-validation"]').exists()).toBe(true)

    // 未保存 Prompt 关闭前弹出二次确认
    const scRule = { ...lxRule, rule_id: 'SC-001', rule_code: 'SC-001' }
    const detailDirty = mount(SemanticRuleDetailModal, {
      props: {
        open: true,
        rule: scRule,
        isAdmin: true,
        promptLoading: false,
        isEditingPrompt: true,
        currentPrompt: '旧模板',
        editingPrompt: '新模板未保存',
      },
      global: {
        stubs: {
          'a-modal': AModalStub,
          'a-alert': AAlertStub,
          'a-button': AButtonStub,
          'a-textarea': textareaStub,
          'a-descriptions': passthrough,
          'a-descriptions-item': passthrough,
          RouterLink: RouterLinkStub,
        },
      },
    })
    const closeBtn = detailDirty.findAll('button').find((b) => b.text().trim() === '关闭')!
    await closeBtn.trigger('click')
    expect(hoisted.Modal.confirm).toHaveBeenCalledTimes(1)
    expect(detailDirty.emitted('update:open')).toBeUndefined()
  })

  it('演示账号在语义规则详情与测试弹窗中隐藏 Prompt 编辑区、执行映射、测试入口与内部调试信息', () => {
    setDemoUser(true)
    const lxRule = {
      rule_id: 'LX0609-01-01-01',
      rule_code: 'LX0609-01-01-01',
      name: '入院记录时效',
      description: '',
      category: '入院记录',
      complexity: '低复杂度',
      defect_level: '严重缺陷',
      score_deduction: 3,
      applicable_documents: ['admission_record'],
      medical_domain: '通用',
      requires_rag: false,
      requires_cot: false,
      primary_execution_rule_id: 'SC-002',
      mapped_rule_ids: ['SC-002'],
    }
    const detailWrapper = mount(SemanticRuleDetailModal, {
      props: {
        open: true,
        rule: lxRule,
        isAdmin: true,
        promptLoading: false,
        isEditingPrompt: false,
        currentPrompt: 'secret prompt',
        editingPrompt: '',
      },
      global: {
        stubs: {
          'a-modal': AModalStub,
          'a-alert': AAlertStub,
          'a-button': AButtonStub,
          'a-descriptions': passthrough,
          'a-descriptions-item': passthrough,
          RouterLink: RouterLinkStub,
        },
      },
    })
    expect(detailWrapper.find('[data-testid="rule-execution-mapping"]').exists()).toBe(false)
    expect(detailWrapper.find('[data-testid="rule-prompt-panel"]').exists()).toBe(false)
    expect(detailWrapper.find('[data-testid="detail-start-test"]').exists()).toBe(false)

    const testWrapper = mount(SemanticRuleTestModal, {
      props: {
        open: true,
        rule: { ...lxRule, rule_id: 'SC-001', rule_code: 'SC-001' },
        exampleType: 'negative',
        medicalText: '测试文本',
        loading: false,
        result: {
          is_compliant: false,
          confidence: 0.9,
          findings: '存在问题',
          evidence: '',
          suggestion: '',
          error_category: 'server_error',
          status_code: 500,
          trace_id: 'trace-secret-123',
          error_detail: 'internal traceback',
        },
      },
      global: {
        stubs: {
          'a-modal': AModalStub,
          'a-alert': AAlertStub,
          'a-button': AButtonStub,
          'a-textarea': textareaStub,
        },
      },
    })
    expect(testWrapper.find('[data-testid="rule-test-debug-info"]').exists()).toBe(false)
    expect(testWrapper.text()).not.toContain('trace-secret-123')
    expect(testWrapper.text()).not.toContain('internal traceback')
  })
})

describe('2. 三传统规则 Tab 只读目录与 CustomQCExperienceView 合同修复', () => {
  it.each([
    ['CodingRulesTab', CodingRulesTab],
    ['FrontpageRulesTab', FrontpageRulesTab],
    ['SettlementRulesTab', SettlementRulesTab],
  ])('%s 明确展示只读规则目录且不再包含假发布抽屉/假回滚时间轴', async (_, Component) => {
    hoisted.apiGet.mockResolvedValue({ success: true, data: { items: [] } })
    const wrapper = shallowMount(Component as any, {
      global: {
        stubs: {
          'a-alert': AAlertStub,
        },
      },
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="readonly-catalog-notice"]').text()).toContain('只读规则目录')
    expect(wrapper.html()).not.toContain('rules-coding-publish-drawer')
    expect(wrapper.html()).not.toContain('rules-coding-change-timeline')
    wrapper.unmount()
  })

  it('CustomQCExperienceView 不再把 visit_type 赋给 visit_id，跳转路径改为 /workstation-v5/rules，文案与落库一致', async () => {
    hoisted.getDepartmentList.mockResolvedValue({ success: true, data: [] })
    hoisted.getAdminRecordList.mockResolvedValue({
      success: true,
      data: {
        items: [
          {
            id: 'rec-1',
            task_id: 't-1',
            record_id: 'VISIT-2026-001',
            visit_type: 'inpatient',
            patient_name: '张三',
            department: '内科',
            status: 'completed',
            defect_count: 1,
            created_at: '2026-06-01',
          },
        ],
        total: 1,
        page: 1,
        page_size: 10,
      },
    })
    const wrapper = shallowMount(CustomQCExperienceView, {
      global: {
        stubs: {
          'a-card': passthrough,
          'a-tag': passthrough,
          'a-button': AButtonStub,
          'a-form': passthrough,
          'a-form-item': passthrough,
          'a-input': inputStub,
          'a-input-number': inputStub,
          'a-select': passthrough,
          'a-textarea': textareaStub,
          'a-alert': AAlertStub,
          'a-range-picker': passthrough,
          'a-table': passthrough,
          'a-empty': passthrough,
        },
      },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.records[0].visit_id).toBe('VISIT-2026-001')
    expect(vm.records[0].visit_id).not.toBe('inpatient')
    expect(wrapper.text()).toContain('试跑记录落库')
    expect(wrapper.text()).not.toContain('只读试跑')

    vm.jumpToRulesList()
    expect(hoisted.routerPush).toHaveBeenCalledWith('/workstation-v5/rules')
    wrapper.unmount()
  })
})

describe('3. CustomRuleWorkspaceView P0 死锁、三坐标单测、演示隔离、脏草稿与表头修复', () => {
  const emptyPromptDraft = {
    id: 'draft-new',
    rule_code: 'CUSTOM-002',
    name: '新规则草稿',
    description: '检查出院带药用法是否完整',
    source_requirement: '检查出院带药用法是否完整',
    prompt_template: '',
    document_type: 'discharge_record',
    severity: 'major',
    complexity: '中复杂度',
    scene: 'final',
    status: 'draft',
  }

  function setupWorkspaceMocks(drafts = [emptyPromptDraft]) {
    hoisted.listWorkspaceDrafts.mockResolvedValue({
      success: true,
      data: { items: drafts, total: drafts.length, page: 1, page_size: 8 },
    })
    hoisted.getWorkspaceRecordFilters.mockResolvedValue({
      success: true,
      data: { departments: [], doctors: [], date_bounds: { admission: { min: '', max: '' }, discharge: { min: '', max: '' } } },
    })
    hoisted.getWorkspaceRecords.mockResolvedValue({
      success: true,
      data: { items: [], total: 0, page: 1, page_size: 20 },
    })
    hoisted.listWorkspaceBatchJobs.mockResolvedValue({
      success: true,
      data: { items: [], total: 0, page: 1, page_size: 5 },
    })
  }

  const workspaceStubs = {
    'a-alert': AAlertStub,
    'a-button': AButtonStub,
    'a-drawer': passthrough,
    'a-empty': passthrough,
    'a-form': passthrough,
    'a-form-item': passthrough,
    'a-input': inputStub,
    'a-input-number': inputStub,
    'a-popconfirm': passthrough,
    'a-radio-button': passthrough,
    'a-radio-group': passthrough,
    'a-range-picker': passthrough,
    'a-select': passthrough,
    'a-switch': passthrough,
    'a-table': passthrough,
    'a-tag': passthrough,
    'a-textarea': textareaStub,
    'a-tooltip': passthrough,
  }

  it('空 prompt_template 新草稿可直接触发 AI 生成 Prompt（解除 P0 死锁），runSingleTest 补传三坐标且表头无英文 visit', async () => {
    setupWorkspaceMocks([emptyPromptDraft])
    hoisted.updateWorkspaceDraft.mockResolvedValue({
      success: true,
      data: emptyPromptDraft,
    })
    hoisted.generateWorkspaceDraftPrompt.mockResolvedValue({
      success: true,
      data: {
        draft: { ...emptyPromptDraft, prompt_template: '生成的模板' },
        prompt_result: { generation_mode: 'llm', summary: '摘要', check_points: ['检查点1'] },
      },
    })
    hoisted.runWorkspaceSingleTest.mockResolvedValue({
      success: true,
      data: { draft_id: 'draft-new', status: 'completed' },
    })

    const wrapper = shallowMount(CustomRuleWorkspaceView, { global: { stubs: workspaceStubs } })
    await flushPromises()
    const vm = wrapper.vm as any

    // 表头不再出现英文 visit
    expect(vm.recordColumns.map((c: any) => c.title)).toContain('住院号/就诊号')
    expect(vm.recordResultColumns.map((c: any) => c.title)).toContain('就诊号')
    expect(vm.failedResultColumns.map((c: any) => c.title)).toContain('失败原因')
    expect(vm.formatSafeFailureReason('Traceback (most recent call last): sqlalchemy Error')).toBe(
      '执行异常，请联系管理员排查',
    )

    // P0 死锁解除：空 prompt_template 草稿成功触发生成 Prompt
    await vm.generatePromptForDraft()
    expect(hoisted.updateWorkspaceDraft).toHaveBeenCalledTimes(1)
    expect(hoisted.generateWorkspaceDraftPrompt).toHaveBeenCalledWith('draft-new')
    expect(vm.editorForm.prompt_template).toBe('生成的模板')

    // 单病历试跑补传三坐标
    hoisted.updateWorkspaceDraft.mockResolvedValueOnce({
      success: true,
      data: { ...emptyPromptDraft, prompt_template: '生成的模板' },
    })
    await vm.runSingleTest({
      institute_id: 'HOSP-01',
      patient_id: 'PAT-01',
      visit_id: 'VISIT-01',
      record_id: 'VISIT-01',
      record_key: 'HOSP-01|PAT-01|VISIT-01',
      patient_name: '患者甲',
      department: '呼吸科',
      doctor: '李医生',
    })
    expect(hoisted.runWorkspaceSingleTest).toHaveBeenCalledWith(
      expect.objectContaining({
        draft_id: 'draft-new',
        records: [
          expect.objectContaining({
            institute_id: 'HOSP-01',
            patient_id: 'PAT-01',
            visit_id: 'VISIT-01',
          }),
        ],
      }),
    )

    // 脏草稿切换二次确认
    vm.editorForm.name = '已修改未保存的名称'
    vm.selectDraft({ ...emptyPromptDraft, id: 'draft-other', name: '另一草稿' })
    expect(hoisted.Modal.confirm).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('演示账号在 CustomRuleWorkspaceView 中隐藏 Prompt 编辑、试跑/创建按钮与失败明细，并阻断写调用', async () => {
    setDemoUser(true)
    setupWorkspaceMocks([emptyPromptDraft])
    const wrapper = shallowMount(CustomRuleWorkspaceView, { global: { stubs: workspaceStubs } })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(wrapper.find('[data-testid="custom-rule-demo-readonly"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="create-draft-btn"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="custom-rule-prompt-section"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="launch-batch-job-btn"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="custom-rule-failed-panel"]').exists()).toBe(false)

    await vm.generatePromptForDraft()
    await vm.runBatchJob()
    expect(hoisted.generateWorkspaceDraftPrompt).not.toHaveBeenCalled()
    expect(hoisted.createWorkspaceBatchJob).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('4. 规则验收孤儿病例修复、防重入锁、演示隔离与手术目录/规则总页同步', () => {
  it('RuleValidationNewCaseView 在 saveCaseAnswer 失败后重试续传已建 itemId，不重复新建孤儿病例', async () => {
    hoisted.getValidationRule.mockResolvedValue({
      success: true,
      data: {
        rule: {
          rule_id: 'LX0609-09-01-02',
          name: '抢救记录完整性',
          source_document: '抢救记录',
          release_scope: 'acceptance_only',
          policy_summary: '',
        },
        cases: [],
      },
    })
    hoisted.createManualTestMedicalRecord.mockResolvedValue({
      success: true,
      data: { item: { id: 'ct-once-only' } },
    })
    hoisted.saveCaseAnswer
      .mockResolvedValueOnce({ success: false, error: '保存预期网络抖动' })
      .mockResolvedValueOnce({ success: true, data: {} })

    const wrapper = mount(RuleValidationNewCaseView, {
      global: {
        stubs: {
          ASpin: passthrough,
          AAlert: AAlertStub,
          AModal: AModalStub,
          AInput: inputStub,
          ATextarea: textareaStub,
          ASelect: true,
          ARadioGroup: passthrough,
          ARadio: passthrough,
          ADatePicker: inputStub,
          RouterLink: RouterLinkStub,
        },
      },
    })
    await flushPromises()

    await wrapper.find('[aria-label="病例标题"]').setValue('防孤儿用例')
    await wrapper.find('[aria-label="科室"]').setValue('急诊科')
    await wrapper.find('[aria-label="文书1正文"]').setValue('抢救过程完整正文')
    await wrapper.find('[aria-label="人工预期依据"]').setValue('依据原文')

    // 第一次保存：创建病例成功，saveCaseAnswer 失败
    await wrapper.get('[data-testid="save-case"]').trigger('click')
    await flushPromises()
    expect(hoisted.createManualTestMedicalRecord).toHaveBeenCalledTimes(1)
    expect(hoisted.saveCaseAnswer).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('ct-once-only')

    // 第二次重试：复用 ct-once-only，不再重复调用 createManualTestMedicalRecord
    await wrapper.get('[data-testid="save-case"]').trigger('click')
    await flushPromises()
    expect(hoisted.createManualTestMedicalRecord).toHaveBeenCalledTimes(1)
    expect(hoisted.saveCaseAnswer).toHaveBeenCalledTimes(2)
    expect(hoisted.saveCaseAnswer).toHaveBeenLastCalledWith(
      'LX0609-09-01-02',
      'ct-once-only',
      expect.objectContaining({ revision: 0 }),
    )
    wrapper.unmount()
  })

  it('RuleValidationDetailView startRun/conclude 防重入，且演示账号隐藏写/运行/验收/批准入口', async () => {
    const startReq = deferred<{ success: true; data: { run_id: string; job_id: string } }>()
    const concludeReq = deferred<{ success: true; data: Record<string, unknown> }>()
    const detailData = {
      rule: {
        rule_id: 'LX0609-09-01-02',
        name: '抢救记录完整性',
        source_document: '抢救记录',
        release_scope: 'acceptance_only',
        policy_summary: '口径',
        impact: null,
      },
      stage: 'pending_conclusion',
      cases: [
        {
          item_id: 'c1',
          case_title: '用例1',
          record_ref: { institute_id: 'I', patient_id: 'P', visit_id: 'V' },
          source_kind: 'synthetic',
          evaluation_as_of_date: '2026-07-05',
          expected_status: 'compliant',
          human_reason: '依据',
          purpose: 'development',
          answer_revision: 1,
        },
      ],
      coverage: { counts: {}, gaps: [], acceptance_cases: 1 },
      runs: [
        {
          id: 'run-1',
          rule_id: 'LX0609-09-01-02',
          cases: [],
          regression_cases: [],
          scope_rule_ids: ['LX0609-09-01-02'],
          regression_gaps: [],
          impact: null,
          job_id: 'job-1',
          state: 'bound',
          execution_version: {},
          build_kind: 'release',
          created_by: 'u',
          created_at: '2026-07-05T10:00:00',
        },
      ],
      latest_run_rows: [],
      acceptance_blockers: [],
      regression_gaps: [],
      events: [],
    }
    hoisted.getValidationRule.mockResolvedValue({ success: true, data: detailData })
    hoisted.startValidationRun.mockReturnValue(startReq.promise)
    hoisted.concludeRule.mockReturnValue(concludeReq.promise)

    const stubs = {
      ASpin: passthrough,
      AAlert: AAlertStub,
      AModal: AModalStub,
      ADrawer: passthrough,
      AInput: inputStub,
      ATextarea: textareaStub,
      RouterLink: RouterLinkStub,
      CaseAnswerModal: true,
      CaseReviewDrawer: true,
      ApprovalModal: true,
    }
    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()
    const vm = wrapper.vm as any

    // 连续触发两次 startRun，仅发出 1 次请求
    const s1 = vm.startRun()
    const s2 = vm.startRun()
    expect(hoisted.startValidationRun).toHaveBeenCalledTimes(1)
    startReq.resolve({ success: true, data: { run_id: 'run-2', job_id: 'job-2' } })
    await Promise.all([s1, s2])

    // 连续触发两次 conclude，仅发出 1 次请求
    vm.conclusionNote = '确认通过'
    const c1 = vm.conclude('accepted')
    const c2 = vm.conclude('accepted')
    expect(hoisted.concludeRule).toHaveBeenCalledTimes(1)
    concludeReq.resolve({ success: true, data: {} })
    await Promise.all([c1, c2])
    wrapper.unmount()

    // 演示账号只读隔离
    setDemoUser(true)
    const demoWrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()
    expect(demoWrapper.find('[data-testid="rule-validation-demo-readonly"]').exists()).toBe(true)
    expect(demoWrapper.find('[data-testid="link-case"]').exists()).toBe(false)
    expect(demoWrapper.find('[data-testid="new-case"]').exists()).toBe(false)
    expect(demoWrapper.find('[data-testid="start-run"]').exists()).toBe(false)
    expect(demoWrapper.find('[data-testid="rule-validation-conclusion-form"]').exists()).toBe(false)
    demoWrapper.unmount()
  })

  it('RuleValidationListView 演示只读隔离与 URL 同步；WorkstationRulesView 切走语义 Tab 清理 ruleSetKey 且默认面包屑一致', async () => {
    setDemoUser(true)
    hoisted.listValidationRules.mockResolvedValue({ success: true, data: { items: [] } })
    const listWrapper = mount(RuleValidationListView, {
      global: {
        stubs: {
          ASpin: passthrough,
          AAlert: AAlertStub,
          AInput: inputStub,
          RouterLink: RouterLinkStub,
        },
      },
    })
    await flushPromises()
    expect(listWrapper.find('[data-testid="rule-validation-list-demo-readonly"]').exists()).toBe(true)
    expect(listWrapper.text()).not.toContain('luxian_0609_qc_v1')
    listWrapper.unmount()

    // 默认面包屑与默认 Tab 一致（语义规则）
    expect(
      resolveBreadcrumb(WORKSTATION_NAV, {
        path: '/workstation-v5/rules',
        query: {},
        meta: {},
      }),
    ).toEqual(['规则', '质控规则', '语义规则'])

    // 切走语义 Tab 清理 ruleSetKey
    reactiveRoute.query = { tab: 'semantic', ruleSetKey: 'luxian_0609_qc_v1', releaseScope: 'acceptance_only' }
    const rulesWrapper = shallowMount(WorkstationRulesView, {
      global: {
        stubs: {
          CodingRulesTab: true,
          FrontpageRulesTab: true,
          SettlementRulesTab: true,
          WorkstationSemanticRulesView: true,
        },
      },
    })
    await flushPromises()
    const codingTabBtn = rulesWrapper.findAll('button').find((b) => b.text().trim() === '编码规则')!
    await codingTabBtn.trigger('click')
    expect(hoisted.routerReplace).toHaveBeenLastCalledWith({
      query: { tab: 'coding' },
    })
    rulesWrapper.unmount()
  })

  it('SurgeryProcedureCatalogView 透传 AbortSignal + skipErrorToast 并与 URL 双向同步', async () => {
    reactiveRoute.query = { keyword: '血肿', category: '手术', level: '四级' }
    const pendingCatalog = deferred<any>()
    hoisted.fetchSurgeryProcedureCatalog.mockReturnValueOnce(pendingCatalog.promise)

    const wrapper = mount(SurgeryProcedureCatalogView, {
      global: {
        stubs: {
          ATable: passthrough,
          'a-table': passthrough,
          AButton: AButtonStub,
          'a-button': AButtonStub,
          AInput: inputStub,
          'a-input': inputStub,
          ASelect: passthrough,
          'a-select': passthrough,
          ASelectOption: passthrough,
          'a-select-option': passthrough,
          AEmpty: passthrough,
          'a-empty': passthrough,
        },
      },
    })
    await flushPromises()
    expect(hoisted.fetchSurgeryProcedureCatalog).toHaveBeenCalledWith(
      expect.objectContaining({ keyword: '血肿', category: '手术', effectiveLevel: '四级' }),
      expect.objectContaining({ signal: expect.any(AbortSignal), skipErrorToast: true }),
    )
    const signal = hoisted.fetchSurgeryProcedureCatalog.mock.calls[0][1].signal as AbortSignal
    expect(signal.aborted).toBe(false)
    wrapper.unmount()
    expect(signal.aborted).toBe(true)
  })
})
