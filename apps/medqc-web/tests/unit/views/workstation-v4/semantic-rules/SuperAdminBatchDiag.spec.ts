/* eslint-disable vue/one-component-per-file */
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { ApiService } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import { UserRole } from '@/types/auth'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import SemanticRulesWorkspace from '@/views/workstation-v4/semantic-rules/SemanticRulesWorkspace.vue'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'

const {
  getRecordIdentitiesMock,
  getResultTraceMock,
  evaluateRuleForVisitMock,
  reviewBatchJobMock,
  workspaceBatchJobDetailRef,
  workspaceConfirmedOnlyRef,
} = vi.hoisted(() => ({
  getRecordIdentitiesMock: vi.fn(),
  getResultTraceMock: vi.fn(),
  evaluateRuleForVisitMock: vi.fn(),
  reviewBatchJobMock: vi.fn(),
  workspaceBatchJobDetailRef: { current: null as any },
  workspaceConfirmedOnlyRef: { current: null as any },
}))

vi.mock('@/services/sichuan-rule-workspace-service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/sichuan-rule-workspace-service')>()),
  getSichuanWorkspaceBatchJobRecordIdentities: (...args: unknown[]) =>
    getRecordIdentitiesMock(...args),
  getSichuanWorkspaceBatchJobResultTrace: (...args: unknown[]) => getResultTraceMock(...args),
  evaluateSichuanRuleForVisit: (...args: unknown[]) => evaluateRuleForVisitMock(...args),
  reviewSichuanWorkspaceBatchJob: (...args: unknown[]) => reviewBatchJobMock(...args),
}))

vi.mock('@/views/workstation-v4/semantic-rules/composables/useSemanticRulesWorkspace', () => ({
  useSemanticRulesWorkspace: () => {
    const detail = ref<SichuanBatchJob | null>({
      id: 'ws-job-1',
      rule_code: 'LX0609',
      rule_name: '泸县0609任务',
      rule_set_key: 'luxian_0609_qc_v1',
      scope: 'final',
      status: 'completed',
      summary: {
        total_records: 1,
        success_count: 1,
        failed_count: 0,
        issue_records: 0,
        compliant_records: 1,
        total_tokens: 0,
        total_processing_time: 1,
      },
      items: [],
      rule_results: [],
    })
    const confirmedOnly = ref(false)
    workspaceBatchJobDetailRef.current = detail
    workspaceConfirmedOnlyRef.current = confirmedOnly
    return {
      loading: ref(false),
      queryState: {
        ruleSetKey: 'luxian_0609_qc_v1',
        keyword: '',
        complexity: '',
        defectLevel: '',
        documentType: '',
        releaseScope: '',
        page: 1,
        pageSize: 10,
      },
      ruleSetOptions: ref([]),
      handleRuleSetChange: vi.fn(),
      keywordInput: ref(''),
      filteredRules: ref([]),
      tableRules: ref([]),
      tablePagination: ref({ current: 1, pageSize: 10, total: 0 }),
      complexityOptions: ref([]),
      defectOptions: ref([]),
      documentOptions: ref([]),
      handleTableChange: vi.fn(),
      showRuleDetail: ref(false),
      selectedRule: ref(null),
      openRuleDetail: vi.fn(),
      closeRuleDetail: vi.fn(),
      isAdmin: ref(true),
      confirmedResultsOnly: confirmedOnly,
      promptLoading: ref(false),
      promptError: ref(''),
      isEditingPrompt: ref(false),
      currentPrompt: ref(''),
      editingPrompt: ref(''),
      startEditPrompt: vi.fn(),
      cancelEditPrompt: vi.fn(),
      savePromptChanges: vi.fn(),
      showRuleTest: ref(false),
      testingRule: ref(null),
      testMedicalText: ref(''),
      testLoading: ref(false),
      testExampleType: ref('negative'),
      testResult: ref(null),
      startRuleTest: vi.fn(),
      switchExampleType: vi.fn(),
      closeRuleTest: vi.fn(),
      executeRuleTestAction: vi.fn(),
      goCustomWorkspace: vi.fn(),
      batchLaunchModalOpen: ref(false),
      batchLaunchFiltersLoading: ref(false),
      batchLaunchDepartmentOptions: ref([]),
      batchLaunchDoctorOptions: ref([]),
      batchLaunchFilters: {
        scope: 'final',
        date_field: 'discharge',
        keyword: '',
      },
      handleBatchLaunchScopeChange: vi.fn(),
      handleBatchLaunchDepartmentChange: vi.fn(),
      openBatchLaunchModal: vi.fn(),
      confirmBatchLaunch: vi.fn(),
      testingBatch: ref(false),
      batchJobScopeOptions: [],
      batchJobDetail: detail,
      batchJobDetailLoading: ref(false),
      batchJobDebugSnapshot: ref(null),
      batchJobDebugLoading: ref(false),
      cancellingBatchJobId: ref(''),
      resultDrawerOpen: ref(true),
      closeBatchJobDrawer: vi.fn(),
      fetchBatchJobDebugSnapshot: vi.fn(),
      executeCancelBatchJob: vi.fn(),
      exportBatchJobReport: vi.fn(),
      formatDateTime: vi.fn(),
    }
  },
}))

const ADrawerStub = defineComponent({
  name: 'ADrawerStub',
  props: { open: Boolean },
  setup(props, { slots }) {
    return () => (props.open ? h('div', { class: 'a-drawer-stub' }, slots.default?.()) : null)
  },
})

const AButtonStub = defineComponent({
  name: 'AButtonStub',
  emits: ['click'],
  setup(_, { slots, emit, attrs }) {
    return () =>
      h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.())
  },
})

const ARadioGroupStub = defineComponent({
  name: 'ARadioGroupStub',
  props: { value: String },
  emits: ['update:value'],
  setup(_, { slots, emit }) {
    return () =>
      h('div', { class: 'a-radio-group-stub' }, [
        h(
          'button',
          { class: 'switch-business', onClick: () => emit('update:value', 'business') },
          '业务视图',
        ),
        h(
          'button',
          { class: 'switch-advanced', onClick: () => emit('update:value', 'advanced') },
          '高级视图',
        ),
        slots.default?.(),
      ])
  },
})

const ATableStub = defineComponent({
  name: 'ATableStub',
  props: {
    columns: { type: Array, default: () => [] },
    dataSource: { type: Array, default: () => [] },
  },
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        { class: 'a-table-stub' },
        (props.dataSource as any[]).map((record, rowIdx) =>
          h(
            'div',
            { key: rowIdx, class: 'a-table-row-stub' },
            (props.columns as any[]).map((column) =>
              h(
                'div',
                { key: column.key, 'data-col-key': column.key },
                slots.bodyCell ? slots.bodyCell({ column, record }) : null,
              ),
            ),
          ),
        ),
      )
  },
})

const passthrough = (name: string) =>
  defineComponent({
    name,
    setup(_, { slots }) {
      return () => h('div', slots.default?.())
    },
  })

const stubs = {
  'a-drawer': ADrawerStub,
  'a-button': AButtonStub,
  'a-radio-group': ARadioGroupStub,
  'a-radio-button': passthrough('ARadioButton'),
  'a-table': ATableStub,
  'a-dropdown': passthrough('ADropdown'),
  'a-menu': passthrough('AMenu'),
  'a-menu-item': passthrough('AMenuItem'),
  'a-tag': passthrough('ATag'),
  'a-progress': passthrough('AProgress'),
  'a-spin': passthrough('ASpin'),
  'a-empty': passthrough('AEmpty'),
  'a-switch': passthrough('ASwitch'),
  'a-input': passthrough('AInput'),
  'a-select': passthrough('ASelect'),
  'a-collapse': passthrough('ACollapse'),
  'a-collapse-panel': passthrough('ACollapsePanel'),
  'a-modal': passthrough('AModal'),
  BatchResultOverview: passthrough('BatchResultOverview'),
  BatchResultTraceModal: passthrough('BatchResultTraceModal'),
  CustomerQcResultDetailCard: passthrough('CustomerQcResultDetailCard'),
  QCRecordCompareWorkbench: passthrough('QCRecordCompareWorkbench'),
  BatchRecordReviewPanel: passthrough('BatchRecordReviewPanel'),
  TopIssueRulesCard: passthrough('TopIssueRulesCard'),
  QcRemediationSuggestion: passthrough('QcRemediationSuggestion'),
  MqIcon: passthrough('MqIcon'),
  RecordViewCloseIcon: passthrough('RecordViewCloseIcon'),
}

function buildLuxianSingleRecordJob(): SichuanBatchJob {
  return {
    id: 'job-lx-sa',
    rule_code: 'LX0609',
    rule_name: '泸县0609质控',
    rule_set_key: 'luxian_0609_qc_v1',
    scope: 'final',
    status: 'completed',
    total_records: 1,
    summary: {
      total_records: 1,
      success_count: 1,
      failed_count: 0,
      issue_records: 1,
      compliant_records: 0,
      total_tokens: 0,
      total_processing_time: 1,
      rule_set_key: 'luxian_0609_qc_v1',
    },
    items: [
      {
        rule_id: 'LX0609-01-01-01',
        rule_code: 'LX0609-01-01-01',
        rule_name: '入院记录24小时内完成',
        record_ref: 'rec_aaaaaaaaaaaaaaaaaaaaaaaa',
        status: 'non_compliant',
        is_compliant: false,
        findings: '入院记录超过24小时完成',
        evidence: '',
        suggestion: '请按规范补充入院记录',
        confidence: 0.95,
      },
    ],
    rule_results: [],
  }
}

describe('Super-Admin Batch 1 Diagnostics & Drawer Actions', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
    vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({
      success: true,
      data: {
        id: 'sa-1',
        email: 'sa@test.local',
        roles: [UserRole.ADMIN, 'super_admin' as UserRole],
        is_demo_account: false,
      } as any,
    })
    await useAuthStore().initialize()
    getRecordIdentitiesMock.mockResolvedValue({
      success: true,
      data: {
        items: [
          {
            record_ref: 'rec_aaaaaaaaaaaaaaaaaaaaaaaa',
            sequence: 1,
            inpatient_no: 'MR-001',
            department: '心内科',
            doctor: '张医生',
            admission_date: '2026-09-01',
            discharge_date: '2026-09-05',
            institute_id: 'H1',
            patient_id: 'P1',
            visit_id: 'V1',
          },
        ],
      },
    })
    getResultTraceMock.mockResolvedValue({
      success: true,
      data: {
        job_id: 'job-lx-sa',
        final_result: { record_ref: 'rec_aaaaaaaaaaaaaaaaaaaaaaaa', status: 'non_compliant' },
      },
    })
    evaluateRuleForVisitMock.mockResolvedValue({
      success: true,
      data: { status: 'non_compliant', findings: '复核确认超期' },
    })
  })

  it('unblocks 诊断追踪 in both business and advanced views with record_ref, and falls back to /record-identities coordinates for 深度复核', async () => {
    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: {
        open: true,
        batchJobDetail: buildLuxianSingleRecordJob(),
        batchJobDetailLoading: false,
        close: vi.fn(),
        exportBatchJobReport: vi.fn(),
        getBatchJobStatusTagClass: vi.fn(() => ''),
        getBatchJobStatusText: vi.fn(() => '已完成'),
        formatDateTime: vi.fn(() => '2026-09-05 10:00:00'),
      },
      global: { stubs },
    })
    await flushPromises()

    // 1. Business view: 诊断追踪 & 深度复核 are both visible and clickable
    const businessButtons = wrapper.findAll('button')
    const traceBtn = businessButtons.find((btn) => btn.text().trim() === '诊断追踪')
    const deepReviewBtn = businessButtons.find((btn) => btn.text().trim() === '深度复核')
    expect(traceBtn).toBeTruthy()
    expect(deepReviewBtn).toBeTruthy()

    await traceBtn!.trigger('click')
    await flushPromises()
    expect(getResultTraceMock).toHaveBeenCalledWith('job-lx-sa', {
      record_ref: 'rec_aaaaaaaaaaaaaaaaaaaaaaaa',
      record_id: undefined,
      visit_id: undefined,
      rule_id: 'LX0609-01-01-01',
    })

    await deepReviewBtn!.trigger('click')
    await flushPromises()
    expect(evaluateRuleForVisitMock).toHaveBeenCalledWith({
      rule_id: 'LX0609-01-01-01',
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      source_schema: 'cdm',
      bundle_schema: 'public',
      force_refresh_bundle: false,
    })

    // 2. Advanced view table has dedicated actions column with 诊断追踪 & 深度复核
    await wrapper.get('.switch-advanced').trigger('click')
    await flushPromises()
    const advTraceBtn = wrapper.find('[data-testid="advanced-issue-trace-btn"]')
    const advDeepBtn = wrapper.find('[data-testid="advanced-issue-deep-review-btn"]')
    expect(advTraceBtn.exists()).toBe(true)
    expect(advDeepBtn.exists()).toBe(true)

    getResultTraceMock.mockClear()
    await advTraceBtn.trigger('click')
    await flushPromises()
    expect(getResultTraceMock).toHaveBeenCalledWith('job-lx-sa', {
      record_ref: 'rec_aaaaaaaaaaaaaaaaaaaaaaaa',
      record_id: undefined,
      visit_id: undefined,
      rule_id: 'LX0609-01-01-01',
    })
  })

  it('hides both 诊断追踪 and 深度复核 for restricted demo accounts (confirmedResultsOnly)', async () => {
    setActivePinia(createPinia())
    vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
    vi.spyOn(ApiService, 'getCurrentUser').mockResolvedValue({
      success: true,
      data: {
        id: 'demo-1',
        email: 'demo@test.local',
        roles: [UserRole.QC_MANAGER],
        is_demo_account: true,
      } as any,
    })
    await useAuthStore().initialize()

    const wrapper = mount(SemanticRulesBatchResultDrawer, {
      props: {
        open: true,
        batchJobDetail: buildLuxianSingleRecordJob(),
        batchJobDetailLoading: false,
        close: vi.fn(),
        exportBatchJobReport: vi.fn(),
        getBatchJobStatusTagClass: vi.fn(() => ''),
        getBatchJobStatusText: vi.fn(() => '已完成'),
        formatDateTime: vi.fn(() => '2026-09-05 10:00:00'),
      },
      global: { stubs },
    })
    await flushPromises()

    const texts = wrapper.findAll('button').map((btn) => btn.text().trim())
    expect(texts).not.toContain('诊断追踪')
    expect(texts).not.toContain('深度复核')
  })

  it('wires review-batch-job-result in SemanticRulesWorkspace and updates batchJobDetail', async () => {
    const updatedJob: SichuanBatchJob = {
      id: 'ws-job-1',
      rule_code: 'LX0609',
      rule_name: '泸县0609任务',
      rule_set_key: 'luxian_0609_qc_v1',
      scope: 'final',
      status: 'completed',
      summary: {
        total_records: 1,
        success_count: 1,
        failed_count: 0,
        issue_records: 0,
        compliant_records: 1,
        total_tokens: 0,
        total_processing_time: 1,
        review_report: {
          scope: 'luxian_0609_qc_v1',
          summary: { total_findings: 2 },
          findings: [],
        },
      },
      items: [],
      rule_results: [],
    }
    reviewBatchJobMock.mockResolvedValue({
      success: true,
      data: {
        job: updatedJob,
        review_report: {
          scope: 'luxian_0609_qc_v1',
          summary: { total_findings: 2 },
          findings: [],
        },
      },
    })

    let capturedReview: (() => Promise<void> | void) | undefined
    mount(SemanticRulesWorkspace, {
      global: {
        stubs: {
          SemanticRulesTableSection: passthrough('SemanticRulesTableSection'),
          SemanticRuleDetailModal: passthrough('SemanticRuleDetailModal'),
          SemanticRuleTestModal: passthrough('SemanticRuleTestModal'),
          CustomQcBatchLaunchModal: passthrough('CustomQcBatchLaunchModal'),
          SemanticRulesBatchResultDrawer: defineComponent({
            name: 'SemanticRulesBatchResultDrawer',
            props: {
              reviewBatchJobResult: Function,
            },
            setup(props) {
              capturedReview = props.reviewBatchJobResult as typeof capturedReview
              return () => h('div', { 'data-testid': 'drawer-stub' })
            },
          }),
        },
      },
    })

    expect(typeof capturedReview).toBe('function')
    await capturedReview?.()
    await flushPromises()

    expect(reviewBatchJobMock).toHaveBeenCalledWith('ws-job-1')
    expect(workspaceBatchJobDetailRef.current.value?.summary?.review_report?.summary?.total_findings).toBe(2)
  })
})
