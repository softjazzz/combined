/* eslint-disable vue/one-component-per-file */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import CustomerSampleValidationView from '@/views/workstation-v4/CustomerSampleValidationView.vue'

let latestBatchResultDrawerProps: Record<string, unknown> | null = null
let latestRecordResultComparisonDrawerProps: Record<string, unknown> | null = null
const CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY = 'medqc_customer_sample_validation_guide_seen_v1'

enableAutoUnmount(afterEach)

const {
  message,
  Modal,
  listManualSamplePools,
  getSheet2ExactReviewAcceptancePackage,
  getLatestManualSamplePoolSyncJob,
  getManualSamplePoolSyncJob,
  getManualSamplePoolRecords,
  getEditableMedicalRecordDocuments,
  importManualSamplePoolByUpload,
  createManualTestMedicalRecord,
  exportLuxian0609EvaluationReport,
  listLuxian0609CustomerRules,
  listManualSampleValidationRuleSets,
  matchManualSamplePool,
  runManualSamplePool,
  syncManualSamplePoolRecords,
  getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot,
  listSichuanWorkspaceBatchJobs,
  exportSichuanWorkspaceBatchJob,
  reviewSichuanWorkspaceBatchJob,
  cancelSichuanWorkspaceBatchJob,
  getDefaultLLMConfigSummary,
  routeQuery,
  routerPush,
  routerReplace,
  writeFile,
  bookNew,
  aoaToSheet,
  bookAppendSheet,
} = vi.hoisted(() => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    loading: vi.fn(),
    destroy: vi.fn(),
  },
  Modal: {
    confirm: vi.fn(({ onOk }: { onOk?: () => unknown }) => onOk?.()),
  },
  listManualSamplePools: vi.fn(),
  getSheet2ExactReviewAcceptancePackage: vi.fn(),
  getLatestManualSamplePoolSyncJob: vi.fn(),
  getManualSamplePoolSyncJob: vi.fn(),
  getManualSamplePoolRecords: vi.fn(),
  getEditableMedicalRecordDocuments: vi.fn(),
  importManualSamplePoolByUpload: vi.fn(),
  createManualTestMedicalRecord: vi.fn(),
  exportLuxian0609EvaluationReport: vi.fn(),
  listLuxian0609CustomerRules: vi.fn(),
  listManualSampleValidationRuleSets: vi.fn(),
  matchManualSamplePool: vi.fn(),
  runManualSamplePool: vi.fn(),
  syncManualSamplePoolRecords: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  getSichuanWorkspaceBatchJobDebugSnapshot: vi.fn(),
  listSichuanWorkspaceBatchJobs: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
  reviewSichuanWorkspaceBatchJob: vi.fn(),
  cancelSichuanWorkspaceBatchJob: vi.fn(),
  getDefaultLLMConfigSummary: vi.fn(),
  routeQuery: {} as Record<string, unknown>,
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  writeFile: vi.fn(),
  bookNew: vi.fn(() => ({ sheets: [] })),
  aoaToSheet: vi.fn(() => ({})),
  bookAppendSheet: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message,
  Modal,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: routeQuery,
  }),
  useRouter: () => ({
    push: routerPush,
    replace: routerReplace,
  }),
}))

vi.mock('@/services/manual-case-sample-service', () => ({
  listManualSamplePools,
  getSheet2ExactReviewAcceptancePackage,
  getLatestManualSamplePoolSyncJob,
  getManualSamplePoolSyncJob,
  getManualSamplePoolRecords,
  getEditableMedicalRecordDocuments,
  importManualSamplePoolByUpload,
  createManualTestMedicalRecord,
  exportLuxian0609EvaluationReport,
  listLuxian0609CustomerRules,
  listManualSampleValidationRuleSets,
  matchManualSamplePool,
  runManualSamplePool,
  syncManualSamplePoolRecords,
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJobDebugSnapshot,
  listSichuanWorkspaceBatchJobs,
  exportSichuanWorkspaceBatchJob,
  reviewSichuanWorkspaceBatchJob,
  cancelSichuanWorkspaceBatchJob,
}))

vi.mock('@/services/llmConfigService', () => ({
  llmConfigService: {
    getDefaultSummary: getDefaultLLMConfigSummary,
  },
}))

vi.mock('xlsx', () => ({
  utils: {
    book_new: bookNew,
    aoa_to_sheet: aoaToSheet,
    book_append_sheet: bookAppendSheet,
  },
  writeFile,
}))

vi.mock('@ant-design/icons-vue', () => ({
  InboxOutlined: defineComponent({
    name: 'InboxOutlinedStub',
    setup() {
      return () => h('span', { class: 'inbox-icon-stub' })
    },
  }),
}))

function slotNodes(slot?: () => unknown) {
  const nodes = slot?.()
  if (!nodes) return []
  return Array.isArray(nodes) ? nodes.flat().filter(Boolean) : [nodes]
}

const AButtonStub = defineComponent({
  name: 'AButtonStub',
  props: {
    disabled: Boolean,
    loading: Boolean,
  },
  emits: ['click'],
  setup(props, { slots, emit, attrs }) {
    return () =>
      h(
        'button',
        {
          ...attrs,
          disabled: props.disabled,
          onClick: () => {
            if (!props.disabled) emit('click')
          },
        },
        slots.default?.(),
      )
  },
})

const ATagStub = defineComponent({
  name: 'ATagStub',
  setup(_, { slots }) {
    return () => h('span', { class: 'a-tag-stub' }, slots.default?.())
  },
})

const ACardStub = defineComponent({
  name: 'ACardStub',
  setup(_, { slots }) {
    return () => h('div', { class: 'a-card-stub' }, slots.default?.())
  },
})

const ASpinStub = defineComponent({
  name: 'ASpinStub',
  setup(_, { slots }) {
    return () => h('div', { class: 'a-spin-stub' }, slots.default?.())
  },
})

const ASelectStub = defineComponent({
  name: 'ASelectStub',
  props: {
    value: {
      type: [String, Number],
      default: undefined,
    },
    options: {
      type: Array,
      default: () => [],
    },
    placeholder: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value', 'change'],
  setup(props, { emit, attrs }) {
    return () =>
      h(
        'select',
        {
          ...attrs,
          'data-placeholder': props.placeholder,
          value: props.value as string | number | undefined,
          onChange: (event: Event) => {
            const target = event.target as HTMLSelectElement
            const selected = target.value
            const matched = (props.options as Array<{ value: string | number }>).find(
              (item) => String(item.value) === selected,
            )
            const nextValue = matched ? matched.value : selected
            emit('update:value', nextValue)
            emit('change', nextValue)
          },
        },
        (props.options as Array<{ label: string; value: string | number }>).map((option) =>
          h('option', { value: option.value }, option.label),
        ),
      )
  },
})

const ASegmentedStub = defineComponent({
  name: 'ASegmentedStub',
  props: {
    value: {
      type: [String, Number],
      default: undefined,
    },
    options: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['update:value', 'change'],
  setup(props, { emit, attrs }) {
    return () =>
      h(
        'div',
        { ...attrs, class: ['a-segmented-stub', attrs.class] },
        (props.options as Array<{ label: string; value: string | number }>).map((option) =>
          h(
            'button',
            {
              type: 'button',
              class: option.value === props.value ? 'is-active' : '',
              onClick: () => {
                emit('update:value', option.value)
                emit('change', option.value)
              },
            },
            option.label,
          ),
        ),
      )
  },
})

const ADropdownStub = defineComponent({
  name: 'ADropdownStub',
  setup(_, { slots }) {
    return () =>
      h('div', { class: 'a-dropdown-stub' }, [
        ...slotNodes(slots.default),
        h('div', { class: 'a-dropdown-overlay-stub' }, slotNodes(slots.overlay)),
      ])
  },
})

const AMenuStub = defineComponent({
  name: 'AMenuStub',
  setup(_, { slots }) {
    return () => h('div', { class: 'a-menu-stub' }, slotNodes(slots.default))
  },
})

const AMenuItemStub = defineComponent({
  name: 'AMenuItemStub',
  props: {
    disabled: Boolean,
  },
  emits: ['click'],
  setup(props, { slots, emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          disabled: props.disabled,
          onClick: () => {
            if (!props.disabled) emit('click')
          },
        },
        slots.default?.(),
      )
  },
})

const ASubMenuStub = defineComponent({
  name: 'ASubMenuStub',
  props: {
    title: {
      type: String,
      default: '',
    },
  },
  setup(props, { slots }) {
    return () =>
      h('div', { class: 'a-sub-menu-stub' }, [
        h('div', { class: 'a-sub-menu-title' }, props.title),
        ...slotNodes(slots.default),
      ])
  },
})

const AMenuDividerStub = defineComponent({
  name: 'AMenuDividerStub',
  setup() {
    return () => h('hr')
  },
})

const ACollapseStub = defineComponent({
  name: 'ACollapseStub',
  setup(_, { slots }) {
    return () => h('div', { class: 'a-collapse-stub' }, slotNodes(slots.default))
  },
})

const ACollapsePanelStub = defineComponent({
  name: 'ACollapsePanelStub',
  props: {
    header: {
      type: String,
      default: '',
    },
  },
  setup(props, { slots }) {
    return () =>
      h('section', { class: 'a-collapse-panel-stub' }, [
        h('button', { type: 'button', class: 'collapse-header' }, props.header),
        ...slotNodes(slots.default),
      ])
  },
})

const AInputStub = defineComponent({
  name: 'AInputStub',
  props: {
    value: {
      type: String,
      default: '',
    },
    size: {
      type: String,
      default: undefined,
    },
    placeholder: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value', 'press-enter'],
  setup(props, { emit, attrs }) {
    return () =>
      h('input', {
        ...attrs,
        placeholder: props.placeholder,
        value: props.value,
        onInput: (event: Event) => {
          const target = event.target as HTMLInputElement
          emit('update:value', target.value)
        },
        onKeydown: (event: KeyboardEvent) => {
          if (event.key === 'Enter') emit('press-enter')
        },
      })
  },
})

const ATextareaStub = defineComponent({
  name: 'ATextareaStub',
  props: {
    value: {
      type: String,
      default: '',
    },
    size: {
      type: String,
      default: undefined,
    },
  },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () =>
      h('textarea', {
        value: props.value,
        onInput: (event: Event) =>
          emit('update:value', (event.target as HTMLTextAreaElement).value),
      })
  },
})

const ASwitchStub = defineComponent({
  name: 'ASwitchStub',
  props: {
    checked: Boolean,
  },
  emits: ['update:checked'],
  setup(props, { emit }) {
    return () =>
      h('input', {
        type: 'checkbox',
        checked: props.checked,
        onChange: (event: Event) =>
          emit('update:checked', (event.target as HTMLInputElement).checked),
      })
  },
})

const ATableStub = defineComponent({
  name: 'ATableStub',
  props: {
    columns: {
      type: Array,
      default: () => [],
    },
    dataSource: {
      type: Array,
      default: () => [],
    },
    rowSelection: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props, { attrs }) {
    const toggle = (recordId: string, checked: boolean) => {
      const selectedKeys = Array.isArray((props.rowSelection as any).selectedRowKeys)
        ? [...(props.rowSelection as any).selectedRowKeys]
        : []
      const nextKeys = checked
        ? Array.from(new Set([...selectedKeys, recordId]))
        : selectedKeys.filter((key: string) => key !== recordId)
      ;(props.rowSelection as any).onChange?.(nextKeys)
    }

    return () => {
      const dataSource =
        (props.dataSource as Array<any>) ||
        ((attrs['data-source'] || attrs.dataSource || []) as Array<any>)
      return h(
        'div',
        { class: 'a-table-stub' },
        dataSource.map((record) =>
          h('div', { class: 'record-row', 'data-record-id': record.id }, [
            h('label', [
              h('input', {
                type: 'checkbox',
                class: 'record-checkbox',
                checked: ((props.rowSelection as any).selectedRowKeys || []).includes(record.id),
                onChange: (event: Event) =>
                  toggle(record.id, (event.target as HTMLInputElement).checked),
              }),
              h('span', { class: 'record-name' }, record.patient_name || record.mr_no || record.id),
            ]),
            h(
              'div',
              { class: 'record-actions' },
              (props.columns as Array<any>)
                .filter((column) => typeof column?.customRender === 'function')
                .map((column, index) =>
                  h('div', { class: `column-${index}` }, [
                    column.customRender({ record, value: record[column.dataIndex] }),
                  ]),
                ),
            ),
          ]),
        ),
      )
    }
  },
})

const AModalStub = defineComponent({
  name: 'AModalStub',
  props: {
    open: Boolean,
  },
  emits: ['update:open', 'ok', 'cancel'],
  setup(props, { slots, emit }) {
    return () =>
      props.open
        ? h('div', { class: 'a-modal-stub' }, [
            h('div', { class: 'modal-body' }, slots.default?.()),
            h('button', { class: 'modal-ok', onClick: () => emit('ok') }, '开始导入'),
            h('button', { class: 'modal-cancel', onClick: () => emit('cancel') }, '取消'),
          ])
        : null
  },
})

const AUploadDraggerStub = defineComponent({
  name: 'AUploadDraggerStub',
  props: {
    beforeUpload: {
      type: Function,
      default: undefined,
    },
  },
  setup(props, { slots }) {
    return () =>
      h('div', { class: 'a-upload-dragger-stub' }, [
        slots.default?.(),
        h(
          'button',
          {
            class: 'upload-trigger',
            onClick: () =>
              props.beforeUpload?.({
                uid: 'file-1',
                name: 'demo.xlsx',
                size: 12,
                type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
              }),
          },
          'mock-upload',
        ),
      ])
  },
})

const ADrawerStub = defineComponent({
  name: 'ADrawerStub',
  props: {
    open: Boolean,
  },
  emits: ['close'],
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        {
          class: 'a-drawer-stub',
          'data-open': props.open ? 'true' : 'false',
          style: props.open ? '' : 'display:none;',
        },
        props.open ? slotNodes(slots.default) : [],
      )
  },
})

const QCReviewDrawerStub = defineComponent({
  name: 'QCReviewDrawerStub',
  props: {
    visible: Boolean,
  },
  setup(props) {
    return () =>
      h('div', {
        class: 'qc-review-drawer-stub',
        'data-open': props.visible ? 'true' : 'false',
        style: props.visible ? '' : 'display:none;',
      })
  },
})

const SemanticRulesBatchResultDrawerStub = defineComponent({
  name: 'SemanticRulesBatchResultDrawerStub',
  props: {
    open: Boolean,
    focusVisitId: {
      type: String,
      default: '',
    },
    focusInstituteId: {
      type: String,
      default: '',
    },
    focusPatientId: {
      type: String,
      default: '',
    },
    focusRecordId: {
      type: String,
      default: '',
    },
    focusRecordRef: {
      type: String,
      default: '',
    },
    focusRecordLabel: {
      type: String,
      default: '',
    },
    batchJobDetail: {
      type: Object,
      default: null,
    },
    batchJobDebugSnapshot: {
      type: Object,
      default: null,
    },
    batchJobDebugLoading: Boolean,
    fetchBatchJobDebugSnapshot: {
      type: Function,
      default: undefined,
    },
    enableRecordComparison: {
      type: Boolean,
      default: false,
    },
    defaultRecordComparison: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    latestBatchResultDrawerProps = props as unknown as Record<string, unknown>
    return () =>
      h('div', {
        class: 'batch-result-drawer-stub',
        'data-open': props.open ? 'true' : 'false',
        style: props.open ? '' : 'display:none;',
      })
  },
})

const QCRecordResultComparisonDrawerStub = defineComponent({
  name: 'QCRecordResultComparisonDrawerStub',
  props: {
    open: Boolean,
    focus: {
      type: Object,
      default: null,
    },
  },
  setup(props) {
    latestRecordResultComparisonDrawerProps = props as unknown as Record<string, unknown>
    return () =>
      h('div', {
        class: 'record-result-comparison-drawer-stub',
        'data-open': props.open ? 'true' : 'false',
      })
  },
})

function buildPool(overrides: Record<string, unknown> = {}) {
  return {
    id: 'pool-1',
    name: '手工问题样本池-首轮验证',
    source_file: 'D:/docs/demo.xlsx',
    source_sheet: 'Sheet2',
    scene: 'running',
    created_by: 'tester',
    total_items: 2,
    llm_intrinsic_items: 2,
    programmatic_items: 0,
    unsupported_items: 0,
    matched_items: 2,
    ambiguous_items: 0,
    unmatched_items: 0,
    ready_items: 2,
    latest_job_id: 'job-1',
    latest_job_status: 'completed',
    ...overrides,
  }
}

function buildRecord(overrides: Record<string, unknown> = {}) {
  return {
    id: 'V001',
    matched_institute_id: 'H1',
    matched_patient_id: 'P001',
    matched_visit_id: 'V001',
    patient_name: '张三',
    mr_no: '2248248',
    department: '普外科',
    admission_time: '2026-06-18T07:02:00+08:00',
    discharge_time: '2026-06-26T08:31:00+08:00',
    match_status: 'matched',
    sync_status: 'synced',
    bundle_status: 'ready',
    coverage_types: ['llm_intrinsic'],
    candidate_rule_ids: ['SC-026'],
    issue_count: 1,
    issue_preview: ['首次病程记录鉴别诊断不全面'],
    issue_preview_text: '首次病程记录鉴别诊断不全面',
    sample_item_ids: ['item-1'],
    sample_items: [],
    ...overrides,
  }
}

function buildRunIdentity(
  visitId: string,
  options: { instituteId?: string; patientId?: string; sampleItemId?: string } = {},
) {
  return {
    sample_item_ids: [options.sampleItemId || 'item-1'],
    record_refs: [
      {
        institute_id: options.instituteId || 'H1',
        patient_id: options.patientId || 'P001',
        visit_id: visitId,
      },
    ],
  }
}

function buildExactReviewAcceptance() {
  return {
    generated_at: '2026-05-03',
    total_rows: 283,
    status_breakdown: {
      exact_confirmed: 139,
      blocked_with_reason: 119,
      skip: 25,
      needs_exact_review: 0,
    },
    explanations: {
      exact_confirmed: '已找到与人工问题核心锚点一致的证据链，可在客户样本验证页稳定复现。',
      blocked_with_reason: '不是未完成，而是“已复核，但当前规则/证据链不能精确复现人工问题原文”。',
      skip: '当前缺原始文书或关键正文，按既定口径归入 skip，不再继续伪造证据链。',
      acceptance_note:
        'Sheet2 精确复核已完成清零；blocked_with_reason 是已复核待增强，不是遗留未处理。',
    },
    blocked_reason_breakdown: {
      规则不支持: 23,
      证据链不足: 37,
      人工问题原文不可判: 59,
    },
    blocked_backlog_breakdown: [
      {
        category: '可补规则',
        count: 23,
        definition: '规则能力缺口',
        next_action: '补主规则',
        blocked_reason_types: { 规则不支持: 23 },
        top_issue_families: [{ issue_family: '首次病程诊断依据/鉴别诊断/诊疗计划缺陷', count: 10 }],
        top_primary_rules: [{ primary_rule_id: 'SC-023', count: 10 }],
        sample_rows: [],
      },
    ],
    blocked_rows: [],
    archive_summary: {
      archive_dir: 'apps/medqc-web/docs/0418/QC/archive/sheet2-exact-review-temp-2026-05-03',
      archived_file_count: 137,
    },
  }
}

function buildRuleSets() {
  return [
    {
      rule_set_key: 'luxian_0609_qc_v1',
      rule_set_name: '泸县0609质控点验证 v1',
      rule_set_version: '2026-06-09',
      scope: 'running',
      rule_ids: ['SC-002', 'CL-081'],
      rule_count: 59,
      validation_mode: 'customer',
      advanced: false,
      display_group: 'main',
      coverage_summary: {
        已达正式口径: 6,
        证据待补强: 10,
        跨文书待完善: 14,
        跨表联查待接入: 15,
        待实现规则: 4,
      },
      coverage_status:
        '正式上线闸门未通过：通过 3 项，失败 6 项，未验证 0 项；当前 6 条达到 formal_ready，其余规则仍需补证据、跨文书或跨表执行链路。',
      artifact_freshness: {
        status: 'stale',
        current_git_head: 'head-current',
        artifact_git_heads: ['head-old'],
        artifact_hash_mismatches: ['release_gate'],
        bound_artifact_count: 3,
      },
      release_gate_summary: {
        release_ready: false,
        passed_checks: 3,
        failed_checks: 6,
        unverified_checks: 0,
        blocking_count: 6,
      },
      evaluation_summary: {
        rule_count: 49,
        rules_with_all_case_types: 0,
        rules_missing_case_types: 49,
        hit_count: 0,
        manual_confirmed_correct_count: 0,
        false_positive_count: 0,
        false_negative_count: 0,
        unknown_count: 0,
        evidence_missing_count: 0,
        launch_status: { not_ready: 49 },
      },
      work_package_summary: {
        package_count: 49,
        phase_counts: {
          阶段3样本验证集建设: 6,
          阶段2证据链补强: 10,
          阶段2跨文书执行链路: 14,
          阶段2跨表数据联查: 15,
          阶段2新增规则实现: 4,
        },
        priority_counts: { P0: 14, P1: 22, P2: 13 },
      },
      page_closure_summary: {
        page_verified: false,
        capability_count: 8,
        passed_capabilities: 4,
        partial_capabilities: 4,
        failed_capabilities: 0,
        blocking_count: 4,
        status_counts: { pass: 4, partial: 4 },
      },
    },
    {
      rule_set_key: 'sc_content_full_v1',
      rule_set_name: 'SC 内涵质控全量 v1',
      rule_set_version: '2026-04-20',
      scope: 'final',
      rule_ids: ['SC-001'],
      rule_count: 84,
      validation_mode: 'formal_fast_screen_full',
      advanced: false,
      display_group: 'main',
      coverage_status: 'SC146 中 84 条内涵规则全量基线',
    },
    {
      rule_set_key: 'sc_sample_running_v1',
      rule_set_name: 'SC 样本规则模式',
      rule_set_version: 'running-batch-1',
      scope: 'running',
      rule_count: 0,
      validation_mode: 'sc',
      advanced: true,
      display_group: 'advanced',
    },
    {
      rule_set_key: 'sample_programmatic_gate_v1',
      rule_set_name: '样本硬门槛程序规则包 v1',
      rule_set_version: '2026-04-27',
      scope: 'running',
      rule_count: 17,
      validation_mode: 'programmatic',
      advanced: true,
      display_group: 'advanced',
    },
    {
      rule_set_key: 'customer_luxian_full_v1',
      rule_set_name: '客户专项规则包 v1（历史）',
      rule_set_version: '2026-04-30',
      scope: 'running',
      rule_count: 0,
      validation_mode: 'customer',
      advanced: true,
      display_group: 'advanced',
    },
  ]
}

const luxian0609RuleNames: Record<string, string> = {
  'LX0609-01-01-01': '入院记录：入院后24小时内是否完成',
  'LX0609-01-02-01': '首次病程：入院后 8 小时内无首次病程记录',
  'LX0609-04-02-01': '手术记录：手术后24小时内是否完成',
  'LX0609-09-01-01': '抢救记录：抢救结束后6小时内是否完成',
  'LX0609-02-01-01': '上级医生查房记录：入院后 48 小时内无主治医师首次查房记录',
  'LX0609-02-01-02': '上级医生查房记录：入院后 72小时内无最高级别首次查房记录',
  'LX0609-02-01-03': '查房记录：病情稳定患者3天内无查房病程记录',
  'LX0609-02-01-04': '查房记录：病重患者2天内无查房病程记录',
  'LX0609-02-01-05': '查房记录：病危患者未每天记录查房病程',
  'LX0609-06-01-02': 'CT/MRI 检查记录：CT/MRI检查前有无病程记录',
  'LX0609-06-01-04': 'CT/MRI 检查记录：影像报告出具后24小时内未记录',
  'LX0609-06-01-05': 'CT/MRI 检查记录：阳性结果未进行分析',
  'LX0609-06-02-03': '病理检查：病理检查结果在手术记录、病程中未记录',
  'LX0609-06-03-03': '细菌培养记录：细菌培养结果在病程中未记录',
  'LX0609-06-03-04': '细菌培养结果无分析：阳性菌在病程记录中无分析',
  'LX0609-12-01-01': '不合理复制病历：首次病程记录病例特点与入院记录完全相同',
  'LX0609-12-01-02': '不合理复制病历：2次以上病程记录完全相同',
  'LX0609-01-01-02': '主诉能导出第一诊断：主诉书写不规范或不能导出第一诊断',
  'LX0609-06-02-02': '病理检查：取材情况未在病程记录/手术记录中记录',
  'LX0609-03-01-01': '会诊记录：有会诊记录单无请会诊执行记录',
  'LX0609-03-01-02': '会诊记录：会诊申请单会诊目的不明确',
  'LX0609-03-01-03': '会诊记录：会诊记录单会诊意见不明确',
  'LX0609-03-01-04': '会诊记录：请会诊执行记录不规范',
  'LX0609-04-02-03': '手术记录：恶性肿瘤手术记录未书写淋巴结清扫情况',
  'LX0609-04-02-04': '手术记录：未记录植入物名称、规格及数量',
  'LX0609-05-02-01': '恶性肿瘤化学治疗记录：病程化疗记录与医嘱不一致',
  'LX0609-08-01-04': '出院记录：恶性肿瘤患者缺少出院后治疗计划',
  'LX0609-05-01-01': '抗菌药物使用记录：预防使用抗菌药物时间超过规定',
  'LX0609-04-01-01': '术前小结：无术前小结',
  'LX0609-04-02-02': '手术记录：无手术记录',
  'LX0609-04-02-05': '手术记录：手术记录非手术者签字',
  'LX0609-04-03-01': '手术安全核查表：无手术安全核查表',
  'LX0609-11-01-01': '手术知情同意书：无手术知情同意书',
  'LX0609-11-02-01': '麻醉知情同意书：无麻醉知情同意书',
  'LX0609-11-02-02': '麻醉知情同意书：填写不规范',
  'LX0609-04-04-01': '麻醉访视：无麻醉术前/术后访视记录',
  'LX0609-04-04-02': '麻醉访视：记录填写不规范',
  'LX0609-04-04-03': '麻醉记录单：无麻醉记录单',
  'LX0609-04-01-02': '术前讨论记录：无术前讨论或术者未参加',
  'LX0609-04-01-03': '术前多学科讨论记录：四级手术术前讨论未多学科讨论',
  'LX0609-11-03-01': '输血知情同意书：无输血知情同意书',
  'LX0609-11-03-02': '输血知情同意书：填写或签名不完整',
  'LX0609-07-01-01': '输血前辅助检查：输血前常规检查不完整',
  'LX0609-07-01-02': '输血前评估：无输血前评估记录或记录不完整',
  'LX0609-07-02-01': '输血记录：无输血病程记录',
  'LX0609-07-02-02': '输血记录：输血病程记录不完整或不规范',
  'LX0609-07-03-01': '输血后评价：无输血后评价',
  'LX0609-07-04-01': '输血记录：术中输血相关内容记录不一致',
  'LX0609-07-04-02': '输血医嘱：输血医嘱与收费不一致',
}

function buildLuxian0609Rules() {
  return Object.entries(luxian0609RuleNames).map(([ruleId, ruleName], index) => {
    return {
      rule_id: ruleId,
      rule_code: ruleId,
      name: ruleName || `${ruleId} 质控点`,
      description: ruleName || `${ruleId} 质控点`,
      required_documents_label: '病程记录',
      mapped_rule_ids: [`SC-${String(index + 1).padStart(3, '0')}`],
      primary_execution_rule_id: `SC-${String(index + 1).padStart(3, '0')}`,
    }
  })
}

function expectedCompactLocalTime(value: string): string {
  const normalized = value.includes('T') ? value : value.replace(' ', 'T')
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  const date = new Date(hasTimezone ? normalized : `${normalized}Z`)
  const parts = new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const getPart = (type: string) => parts.find((part) => part.type === type)?.value || ''
  return `${getPart('year')}-${getPart('month')}-${getPart('day')} ${getPart('hour')}:${getPart('minute')}`
}

async function mountView() {
  const wrapper = mount(CustomerSampleValidationView, {
    global: {
      stubs: {
        AButton: AButtonStub,
        ATag: ATagStub,
        ACard: ACardStub,
        ASpin: ASpinStub,
        ASelect: ASelectStub,
        ASegmented: ASegmentedStub,
        ADropdown: ADropdownStub,
        AMenu: AMenuStub,
        AMenuItem: AMenuItemStub,
        ASubMenu: ASubMenuStub,
        AMenuDivider: AMenuDividerStub,
        ACollapse: ACollapseStub,
        ACollapsePanel: ACollapsePanelStub,
        AInput: AInputStub,
        ATextarea: ATextareaStub,
        ASwitch: ASwitchStub,
        ATable: ATableStub,
        AModal: AModalStub,
        AUploadDragger: AUploadDraggerStub,
        ADrawer: ADrawerStub,
        QCReviewDrawer: QCReviewDrawerStub,
        SemanticRulesBatchResultDrawer: SemanticRulesBatchResultDrawerStub,
        QCRecordResultComparisonDrawer: QCRecordResultComparisonDrawerStub,
        'q-c-review-drawer': QCReviewDrawerStub,
        'semantic-rules-batch-result-drawer': SemanticRulesBatchResultDrawerStub,
        'q-c-record-result-comparison-drawer': QCRecordResultComparisonDrawerStub,
        'a-button': AButtonStub,
        'a-tag': ATagStub,
        'a-card': ACardStub,
        'a-spin': ASpinStub,
        'a-select': ASelectStub,
        'a-select-option': defineComponent({
          name: 'ASelectOptionStub',
          props: {
            value: {
              type: [String, Number],
              default: undefined,
            },
          },
          setup(_, { slots }) {
            return () => h('option', slotNodes(slots.default))
          },
        }),
        'a-segmented': ASegmentedStub,
        'a-dropdown': ADropdownStub,
        'a-menu': AMenuStub,
        'a-menu-item': AMenuItemStub,
        'a-sub-menu': ASubMenuStub,
        'a-menu-divider': AMenuDividerStub,
        'a-collapse': ACollapseStub,
        'a-collapse-panel': ACollapsePanelStub,
        'a-input': AInputStub,
        'a-textarea': ATextareaStub,
        'a-switch': ASwitchStub,
        'a-table': ATableStub,
        'a-modal': AModalStub,
        'a-upload-dragger': AUploadDraggerStub,
        'a-drawer': ADrawerStub,
      },
    },
  })
  await flushPromises()
  await nextTick()
  await flushPromises()
  await nextTick()
  return wrapper
}

async function selectRuleSet(wrapper: ReturnType<typeof mount>, ruleSetKey: string) {
  const button = wrapper.find(`[data-rule-set-key="${ruleSetKey}"]`)
  expect(button.exists()).toBe(true)
  await button.trigger('click')
  await flushPromises()
}

async function expandLuxianFamily(wrapper: ReturnType<typeof mount>, familyName: string) {
  const family = wrapper
    .findAll('.customer-sample-luxian-rule-group')
    .find((node) => node.text().includes(familyName))
  expect(family).toBeTruthy()
  const expandButton = family!.findAll('button').find((node) => node.text() === '查看质控点')
  if (expandButton) {
    await expandButton.trigger('click')
    await nextTick()
  }
}

describe('CustomerSampleValidationView', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    latestBatchResultDrawerProps = null
    latestRecordResultComparisonDrawerProps = null
    Object.keys(routeQuery).forEach((key) => delete routeQuery[key])
    window.localStorage.clear()
    window.localStorage.setItem(CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY, 'true')
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:luxian-0609-report'),
      revokeObjectURL: vi.fn(),
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    getDefaultLLMConfigSummary.mockResolvedValue({
      execution_concurrency: {
        max_parallel_records: 16,
        family_max_concurrency: 4,
        http_max_concurrency: 40,
      },
    })
    listManualSamplePools.mockResolvedValue({
      success: true,
      data: { items: [buildPool()], total: 1, page: 1, page_size: 50 },
    })
    getSheet2ExactReviewAcceptancePackage.mockResolvedValue({
      success: true,
      data: buildExactReviewAcceptance(),
    })
    listManualSampleValidationRuleSets.mockResolvedValue({
      success: true,
      data: { items: buildRuleSets() },
    })
    listLuxian0609CustomerRules.mockResolvedValue({
      success: true,
      data: {
        rule_set_key: 'luxian_0609_qc_v1',
        total_rules: 49,
        rules: buildLuxian0609Rules(),
      },
    })
    getLatestManualSamplePoolSyncJob.mockResolvedValue({ success: true, data: null })
    getManualSamplePoolSyncJob.mockResolvedValue({
      success: true,
      data: {
        id: 'sync-job-1',
        pool_id: 'pool-1',
        status: 'completed',
        summary: { progress: { step_label: '同步完成', total_candidates: 2, eligible_visits: 2 } },
      },
    })
    listSichuanWorkspaceBatchJobs.mockResolvedValue({
      success: true,
      data: {
        items: [
          {
            id: 'job-history-1',
            rule_code: 'LX0609',
            rule_name: '泸县0609质控点验证',
            scope: 'running',
            status: 'completed',
            rule_set_key: 'luxian_0609_qc_v1',
            rule_set_name: '泸县0609质控点验证 v1',
            customer_rule_count: 3,
            execution_rule_count: 4,
            record_ids: ['V001'],
            created_at: '2026-06-30T10:30:00Z',
            filters: {
              selected_rule_ids: ['LX0609-01-01-01', 'LX0609-01-02-01', 'LX0609-02-01-01'],
            },
            summary: {
              total_records: 1,
              success_count: 1,
              failed_count: 0,
              issue_records: 1,
              compliant_records: 0,
              total_tokens: 0,
              total_processing_time: 0,
              display_status_counts: {
                non_compliant: 2,
                data_gap: 1,
              },
            },
            items: [
              {
                rule_code: 'LX0609-01-02-01',
                rule_name: '首次病程：入院后 8 小时内无首次病程记录',
                record_id: 'V001',
                status: 'non_compliant',
                is_compliant: false,
                findings: '首次病程记录未在入院后8小时内完成。',
              },
              {
                rule_code: 'LX0609-01-01-02',
                rule_name: '主诉能导出第一诊断',
                record_id: 'V001',
                status: 'non_compliant',
                is_compliant: false,
                findings: '主诉不能导出第一诊断。',
              },
              {
                rule_code: 'LX0609-02-01-01',
                rule_name: '上级医生查房记录',
                record_id: 'V001',
                status: 'data_gap',
                is_compliant: false,
                findings: '缺少主治医师首次查房记录时间，需人工复核。',
              },
            ],
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    getManualSamplePoolRecords.mockResolvedValue({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord(),
          buildRecord({
            id: 'V002',
            matched_visit_id: 'V002',
            mr_no: '2249001',
            patient_name: '李四',
          }),
        ],
        total: 2,
        page: 1,
        page_size: 20,
      },
    })
    getEditableMedicalRecordDocuments.mockResolvedValue({
      success: true,
      data: {
        visit_id: 'V001',
        documents: [
          {
            key: 'admission-1',
            document_type: '入院记录',
            title: '入院记录',
            record_time: '2026-06-01T09:00:00',
            submit_time: '2026-06-01T09:10:00',
            content: '患者因腹痛入院，完善相关检查后收入普通外科。',
            doctor_name: '陈医师',
            enabled: true,
          },
          {
            key: 'course-empty-time',
            document_type: '日常病程记录',
            title: '日常病程记录',
            record_time: '',
            submit_time: '',
            content: '患者入院后继续完善检查，治疗方案待上级医师查房后调整。',
            doctor_name: '陈医师',
            enabled: true,
          },
          {
            key: 'long-order-1',
            document_type: 'inpat_drug_order',
            title: '长期医嘱',
            record_time: '2026-06-01T10:00:00',
            submit_time: '',
            content: '长期医嘱：大活络胶囊 0.25g*60粒 口服 Tid。',
            doctor_name: '陈医师',
            enabled: true,
          },
          {
            key: 'long-order-2',
            document_type: 'inpat_drug_order',
            title: '长期医嘱',
            record_time: '2026-06-03T08:00:00',
            submit_time: '',
            content: '长期医嘱：奥美拉唑肠溶胶囊 20mg 口服 Qd。',
            doctor_name: '陈医师',
            enabled: true,
          },
          {
            key: 'temp-order-1',
            document_type: 'temporary_order',
            title: '临时医嘱',
            record_time: '',
            submit_time: '',
            order_start_time: '2026-06-02T16:30:00',
            order_stop_time: '',
            content: '临时医嘱：头孢曲松 2g 静滴 qd，开立医师陈医师。',
            doctor_name: '陈医师',
            enabled: true,
          },
          {
            key: 'fragment-long-order',
            document_type: 'temporary_order',
            title: '临时医嘱',
            record_time: '',
            submit_time: '',
            content: '长期\n护理\nII级护理\n新开',
            doctor_name: '陈医师',
            enabled: true,
          },
          {
            key: 'fragment-temp-order',
            document_type: 'temporary_order',
            title: '临时医嘱',
            record_time: '',
            submit_time: '',
            content: '临时\n用药\n氨溴索注射液 30mg 静滴\n新开',
            doctor_name: '陈医师',
            enabled: true,
          },
        ],
      },
    })
    createManualTestMedicalRecord.mockResolvedValue({
      success: true,
      data: {
        pool: buildPool({ id: 'customer-created-test-records-v1', name: '客户自建测试病历' }),
        item: {
          id: 'ct-edit-copy',
          pool_id: 'customer-created-test-records-v1',
          row_no: 1,
          department: '普外科',
          patient_name: '张三',
          mr_no: 'CUSTOMER_TEST_EDIT_COPY',
          visit_id: 'CUSTOMER_TEST_EDIT_COPY',
          manual_issue_text: '源病历编辑副本',
          normalized_issue_text: '源病历编辑副本',
          doctor_name: '测试医师',
          qc_user: 'tester',
          coverage_type: 'llm_intrinsic',
          issue_category: '客户自建测试病历',
          expected_scene: 'running',
          candidate_rule_ids: ['LX0609-01-01-01'],
          include_in_batch_1: true,
          matched_institute_id: 'H1',
          matched_patient_id: 'P_EDIT_COPY',
          matched_visit_id: 'CUSTOMER_TEST_EDIT_COPY',
          match_status: 'matched',
          sync_status: 'synced',
          bundle_status: 'ready',
        },
        visit_id: 'CUSTOMER_TEST_EDIT_COPY',
        mr_no: 'CUSTOMER_TEST_EDIT_COPY',
        patient_id: 'P_EDIT_COPY',
        inserted_tables: { mr: 1 },
        bundle_status: 'ready',
      },
    })
    runManualSamplePool.mockResolvedValue({
      success: true,
      data: {
        pool_id: 'pool-1',
        job_id: 'job-2',
        sample_item_count: 1,
        selected_record_count: 1,
        record_count: 1,
        rule_count: 5,
        record_ids: ['V001'],
        rule_ids: ['SC-023'],
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
        rule_set_name: '泸县0609质控点验证 v1',
      },
    })
    syncManualSamplePoolRecords.mockResolvedValue({
      success: true,
      data: { job_id: 'sync-job-1', pool_id: 'pool-1', status: 'queued' },
    })
    importManualSamplePoolByUpload.mockResolvedValue({
      success: true,
      data: { id: 'pool-2', name: '第二轮', imported_rows: 2 },
    })
    matchManualSamplePool.mockResolvedValue({
      success: true,
      data: {
        pool_id: 'pool-1',
        matched: 2,
        ambiguous: 0,
        unmatched: 0,
      },
    })
    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { id: 'job-2', status: 'completed' },
    })
    getSichuanWorkspaceBatchJobDebugSnapshot.mockResolvedValue({
      success: true,
      data: {
        job_id: 'job-2',
        status: 'completed',
        scope: 'running',
        execution_mode: 'native',
        rules: [],
        recent_items: [],
        recent_failed_records: [],
      },
    })
    exportSichuanWorkspaceBatchJob.mockResolvedValue({ success: true, data: new Blob() })
    reviewSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: {
        job: {
          id: 'job-history-1',
          rule_code: 'LX0609',
          rule_name: '泸县0609质控点验证',
          scope: 'running',
          status: 'completed',
          rule_set_key: 'luxian_0609_qc_v1',
          rule_set_name: '泸县0609质控点验证 v1',
          customer_rule_count: 3,
          execution_rule_count: 4,
          record_ids: ['V001'],
          created_at: '2026-06-30T10:30:00Z',
          filters: {
            selected_rule_ids: ['LX0609-01-01-01', 'LX0609-01-02-01', 'LX0609-02-01-01'],
          },
          summary: {
            total_records: 1,
            success_count: 1,
            failed_count: 0,
            issue_records: 1,
            compliant_records: 0,
            total_tokens: 0,
            total_processing_time: 0,
            review_report: {
              review_status: 'completed',
              summary: { total_findings: 1, p0: 0, p1: 1, p2: 0 },
              findings: [
                {
                  id: 'review-1',
                  rule_id: 'LX0609-03-01-01',
                  severity: 'P1',
                  suggested_status: 'not_applicable',
                  customer_message: '当前病历未见会诊文书证据，本项不宜作为会诊执行问题展示。',
                },
              ],
            },
          },
          items: [],
        },
        review_report: {
          review_status: 'completed',
          summary: { total_findings: 1, p0: 0, p1: 1, p2: 0 },
          findings: [],
        },
      },
    })
    exportLuxian0609EvaluationReport.mockResolvedValue({
      success: true,
      data: new Blob(['report']),
    })
  })

  it('待验收规则不被全选或族选择带入，但可以逐条勾选', async () => {
    const rules = buildLuxian0609Rules()
    const acceptanceId = rules[0].rule_id
    listLuxian0609CustomerRules.mockResolvedValue({
      success: true,
      data: {
        rules: rules.map((rule) => ({
          ...rule,
          release_scope: rule.rule_id === acceptanceId ? 'acceptance_only' : 'default',
        })),
      },
    })
    const wrapper = await mountView()
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((node) => node.text().includes('全选8个质控族'))!
      .trigger('click')
    await nextTick()
    const group = wrapper.findAll('.customer-sample-luxian-rule-group')[0]
    const expand = group.findAll('button').find((node) => node.text().includes('查看质控点'))
    if (expand) await expand.trigger('click')
    await nextTick()
    const input = wrapper.find(`input.luxian-rule-checkbox[value="${acceptanceId}"]`)
    expect(input.exists()).toBe(true)
    expect((input.element as HTMLInputElement).checked).toBe(false)
    expect(group.text()).toContain('待验收')
    // 取消/重选本组均不自动勾选待验收项。
    await group
      .findAll('button')
      .find((node) => node.text().includes('取消本组'))!
      .trigger('click')
    await group
      .findAll('button')
      .find((node) => node.text().includes('选择本组'))!
      .trigger('click')
    expect((input.element as HTMLInputElement).checked).toBe(false)
    await input.setValue(true)
    expect((input.element as HTMLInputElement).checked).toBe(true)
    expect(wrapper.text()).toContain('待验收 1 条')
  })

  it('病历池明确标注在院、已出院和状态待同步病例', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord({
            hospitalization_status: 'active',
          }),
          buildRecord({
            id: 'V002',
            matched_visit_id: 'V002',
            patient_name: '李四',
            hospitalization_status: 'discharged',
            discharge_time: '2026-07-30T15:20:00+08:00',
          }),
          buildRecord({
            id: 'V003',
            matched_visit_id: 'V003',
            patient_name: '王五',
            hospitalization_status: '',
          }),
        ],
        total: 3,
        page: 1,
        page_size: 20,
      },
    })

    const wrapper = await mountView()

    const badges = wrapper.findAll('.customer-sample-hospitalization-badge')
    expect(badges.map((badge) => badge.text())).toEqual(['在院', '已出院', '状态待同步'])
    expect(badges[0].classes()).toContain('is-active')
    expect(badges[1].classes()).toContain('is-discharged')
    expect(badges[1].attributes('title')).toContain('2026')
    expect(badges[1].attributes('style')).toContain('display: inline-flex')
    expect(badges[1].attributes('style')).toContain('border-radius: 999px')
    expect(badges[2].classes()).toContain('is-unknown')
    expect(wrapper.find('.customer-sample-patient-summary').attributes('style')).toContain(
      'gap: 8px',
    )
  })

  it('样本池名称已包含数量时不应重复追加数量', async () => {
    listManualSamplePools.mockResolvedValueOnce({
      success: true,
      data: {
        items: [
          buildPool({
            id: 'luxian-0609-0426-syn-v2',
            name: '泸县0609真实结构合成样本v2（30）',
            total_items: 30,
            matched_items: 30,
            ready_items: 30,
          }),
        ],
        total: 1,
        page: 1,
        page_size: 50,
      },
    })

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('泸县0609真实结构合成样本v2（30）')
    expect(wrapper.text()).not.toContain('泸县0609真实结构合成样本v2（30）（30）')
  })

  it('页面初始化不应默认加载旧 Sheet2 验收包', async () => {
    await mountView()

    expect(getSheet2ExactReviewAcceptancePackage).not.toHaveBeenCalled()
  })

  it('提供显式质控记录入口并跳转到独立历史页', async () => {
    const wrapper = await mountView()
    await flushPromises()

    const historyButton = wrapper.find('.customer-sample-task-history-action')
    expect(historyButton.exists()).toBe(true)
    expect(historyButton.text()).toContain('查看质控记录')
    await historyButton.trigger('click')
    await flushPromises()

    expect(routerPush).toHaveBeenCalledWith({
      name: 'WorkstationV4CustomerSampleValidationTasks',
    })
    expect(listSichuanWorkspaceBatchJobs).not.toHaveBeenCalled()
    expect(wrapper.find('.customer-sample-task-center').exists()).toBe(false)
  })

  it('从更多操作菜单进入手术分级目录', async () => {
    const wrapper = await mountView()
    const catalogEntry = wrapper
      .findAll('button')
      .find((item) => item.text().trim() === '手术分级目录')

    expect(catalogEntry).toBeTruthy()
    await catalogEntry!.trigger('click')
    await flushPromises()

    expect(routerPush).toHaveBeenCalledWith({ name: 'WorkstationV4SurgeryProcedureCatalog' })
  })

  it('主任务状态条应识别压缩任务里的数组型状态分布', async () => {
    getSichuanWorkspaceBatchJob.mockResolvedValueOnce({
      success: true,
      data: {
        id: 'job-compact-aggregation',
        rule_code: 'LX0609',
        rule_name: '泸县0609质控点验证',
        scope: 'running',
        status: 'completed',
        rule_set_key: 'luxian_0609_qc_v1',
        rule_set_name: '泸县0609质控点验证 v1',
        customer_rule_count: 6,
        execution_rule_count: 6,
        record_ids: ['V001'],
        created_at: '2026-07-05T15:34:38Z',
        filters: {
          selected_rule_ids: [
            'LX0609-02-01-03',
            'LX0609-02-01-04',
            'LX0609-02-01-05',
            'LX0609-12-01-01',
            'LX0609-12-01-02',
            'LX0609-01-01-02',
          ],
        },
        summary: {
          total_records: 1,
          success_count: 1,
          failed_count: 0,
          issue_records: 1,
          compliant_records: 0,
          total_tokens: 0,
          total_processing_time: 0,
          result_aggregation: {
            cluster_count: 0,
            duplicate_hits: 0,
            clusters: [],
            status_breakdown: [
              { key: 'not_applicable', count: 2 },
              { key: 'compliant', count: 1 },
              { key: 'uncertain', count: 1 },
              { key: 'ai_suggested_non_compliant', count: 1 },
              { key: 'data_gap', count: 1 },
            ],
          },
        },
        items: [],
        rule_results: [],
      },
    })

    const wrapper = await mountView()
    await flushPromises()

    const statusBar = wrapper.find('[data-testid="customer-sample-qc-task-status"]')
    expect(statusBar.exists()).toBe(true)
    expect(statusBar.text()).toContain('结果回写：6 / 6 条')
    expect(statusBar.text()).toContain('数据不足')
    expect(statusBar.text()).toContain('AI判断')
    expect(statusBar.text()).toContain('AI建议复核')
    expect(statusBar.text()).toContain('不适用')
    expect(statusBar.text()).not.toContain('结果回写：0 / 6 条')
    expect(statusBar.text().indexOf('AI建议复核')).toBeLessThan(statusBar.text().indexOf('合规'))
    expect(statusBar.text().indexOf('合规')).toBeLessThan(statusBar.text().indexOf('不适用'))
  })

  it('导出 HTML 时如果后端返回 Excel 二进制，不应保存成乱码 HTML', async () => {
    exportSichuanWorkspaceBatchJob.mockResolvedValueOnce({
      success: true,
      data: new Blob(['PK\x03\x04docProps/app.xml'], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      }),
    })
    const wrapper = await mountView()
    await flushPromises()

    const exportHtmlButton = wrapper.find('[data-testid="qc-task-export"]')
    expect(exportHtmlButton.exists()).toBe(true)
    await exportHtmlButton.trigger('click')
    await flushPromises()

    expect(exportSichuanWorkspaceBatchJob).toHaveBeenCalledWith({
      job_id: 'job-2',
      format: 'html',
    })
    expect(message.error).toHaveBeenCalledWith(
      '后端未返回 HTML 明细文件，请确认客户机后端已更新到支持 HTML 导出的版本。',
    )
    expect(message.success).not.toHaveBeenCalledWith('HTML 质控明细已开始下载')
  })

  it('根据样本池最近任务恢复主状态条并在无历史面板时自动刷新到终态', async () => {
    vi.useFakeTimers()
    getSichuanWorkspaceBatchJob
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'job-1',
          rule_code: 'LX0609',
          rule_name: '泸县0609质控点验证',
          scope: 'running',
          status: 'running',
          rule_set_key: 'luxian_0609_qc_v1',
          rule_set_name: '泸县0609质控点验证 v1',
          customer_rule_count: 49,
          record_ids: ['V001'],
          created_at: '2026-07-02T13:59:35Z',
          filters: {
            selected_rule_ids: ['LX0609-01-01-01', 'LX0609-01-02-01', 'LX0609-09-01-01'],
          },
          summary: {
            display_status_counts: {
              non_compliant: 3,
              data_gap: 1,
            },
          },
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'job-1',
          rule_code: 'LX0609',
          rule_name: '泸县0609质控点验证',
          scope: 'running',
          status: 'completed',
          rule_set_key: 'luxian_0609_qc_v1',
          rule_set_name: '泸县0609质控点验证 v1',
          customer_rule_count: 49,
          record_ids: ['V001'],
          created_at: '2026-07-02T13:59:35Z',
          filters: {
            selected_rule_ids: ['LX0609-01-01-01', 'LX0609-01-02-01', 'LX0609-09-01-01'],
          },
          summary: {
            display_status_counts: {
              non_compliant: 3,
              data_gap: 1,
            },
          },
        },
      })

    const wrapper = await mountView()
    await flushPromises()

    const statusBar = wrapper.find('[data-testid="customer-sample-qc-task-status"]')
    expect(getSichuanWorkspaceBatchJob).toHaveBeenNthCalledWith(1, 'job-1')
    expect(statusBar.exists()).toBe(true)
    expect(statusBar.text()).toContain('正在执行质控')
    expect(statusBar.text()).toContain('执行中')
    expect(wrapper.find('.customer-sample-task-center').exists()).toBe(false)

    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()

    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(2)
    expect(getSichuanWorkspaceBatchJob).toHaveBeenNthCalledWith(2, 'job-1')
    expect(statusBar.text()).toContain('最近质控任务')
    expect(statusBar.text()).toContain('已完成')
    expect(statusBar.text()).not.toContain('执行中')
  })

  it('任务详情读取失败时保留执行状态并继续轮询恢复', async () => {
    vi.useFakeTimers()
    listManualSamplePools.mockResolvedValue({
      success: true,
      data: {
        items: [buildPool({ latest_job_id: 'job-contract-error', latest_job_status: 'running' })],
        total: 1,
        page: 1,
        page_size: 50,
      },
    })
    getSichuanWorkspaceBatchJob
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'job-contract-error',
          rule_code: 'LX0609',
          rule_name: '泸县0609质控点验证',
          scope: 'running',
          status: 'running',
          rule_set_key: 'luxian_0609_qc_v1',
          rule_set_name: '泸县0609质控点验证 v1',
          created_at: '2026-08-17T02:43:20Z',
        },
      })
      .mockResolvedValueOnce({
        success: false,
        message: '历史质控结果交付合同不完整，无法安全展示',
      })

    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { id: 'job-contract-error', status: 'running' },
    })
    const wrapper = await mountView()
    await flushPromises()

    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    await vi.advanceTimersByTimeAsync(10000)
    await flushPromises()

    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledTimes(4)
    // 未附带任务状态的读取失败视为临时失败：静默重试，不中断轮询
    expect(message.error).not.toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining('已停止自动刷新') }),
    )
    expect(wrapper.text()).not.toContain('执行失败')
  })

  it('任务已结束但结果无法展示（409 + 已结束状态）时停止轮询并说明原因', async () => {
    vi.useFakeTimers()
    listManualSamplePools.mockResolvedValue({
      success: true,
      data: {
        items: [buildPool({ latest_job_id: 'job-1', latest_job_status: 'running' })],
        total: 1,
        page: 1,
        page_size: 50,
      },
    })
    getSichuanWorkspaceBatchJob
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'job-1',
          rule_code: 'LX0609',
          rule_name: '泸县0609质控点验证',
          scope: 'running',
          status: 'running',
          rule_set_key: 'luxian_0609_qc_v1',
          created_at: '2026-10-13T02:43:20Z',
        },
      })
      .mockResolvedValue({
        success: false,
        status: 409,
        jobStatus: 'failed',
        message: '历史质控结果交付合同不完整，无法安全展示',
      })

    const wrapper = await mountView()
    await flushPromises()
    const statusBar = wrapper.find('[data-testid="customer-sample-qc-task-status"]')
    expect(statusBar.text()).toContain('执行中')
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    const callsAfterStop = getSichuanWorkspaceBatchJob.mock.calls.length
    await vi.advanceTimersByTimeAsync(30000)
    await flushPromises()

    expect(getSichuanWorkspaceBatchJob.mock.calls.length).toBe(callsAfterStop)
    expect(message.error).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining('已停止自动刷新') }),
    )
    expect(
      (wrapper.vm as unknown as { currentQcTask?: { id?: string; status?: string } }).currentQcTask,
    ).toMatchObject({ id: 'job-1', status: 'failed' })
    const settledStatusBar = wrapper.find('[data-testid="customer-sample-qc-task-status"]')
    expect(settledStatusBar.text()).toContain('失败')
    expect(settledStatusBar.text()).not.toContain('执行中')
  })

  it('任务仍在执行时的 409 继续重试，连续失败达到上限后暂停自动刷新', async () => {
    vi.useFakeTimers()
    listManualSamplePools.mockResolvedValue({
      success: true,
      data: {
        items: [buildPool({ latest_job_id: 'job-running-409', latest_job_status: 'running' })],
        total: 1,
        page: 1,
        page_size: 50,
      },
    })
    getSichuanWorkspaceBatchJob
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'job-running-409',
          rule_code: 'LX0609',
          rule_name: '泸县0609质控点验证',
          scope: 'running',
          status: 'running',
          rule_set_key: 'luxian_0609_qc_v1',
          created_at: '2026-10-13T02:43:20Z',
        },
      })
      .mockResolvedValue({
        success: false,
        status: 409,
        jobStatus: 'running',
        message: '批量质控 Canonical 结果不完整，无法安全展示',
      })

    await mountView()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(5000 * 11)
    await flushPromises()
    expect(message.error).not.toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining('已暂停自动刷新') }),
    )

    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    const callsAfterStop = getSichuanWorkspaceBatchJob.mock.calls.length
    await vi.advanceTimersByTimeAsync(30000)
    await flushPromises()

    expect(getSichuanWorkspaceBatchJob.mock.calls.length).toBe(callsAfterStop)
    expect(message.error).toHaveBeenCalledWith(
      expect.objectContaining({ content: expect.stringContaining('已暂停自动刷新') }),
    )
  })

  it('默认选中泸县0609规则集并弱化内部覆盖标签', async () => {
    const wrapper = await mountView()

    expect(getSheet2ExactReviewAcceptancePackage).not.toHaveBeenCalled()
    expect(listManualSampleValidationRuleSets).toHaveBeenCalled()
    expect(wrapper.text()).toContain('验证规则集')
    expect(wrapper.text()).toContain('泸县0609质控点验证 v1')
    expect(wrapper.text()).toContain('59')
    expect(wrapper.text()).toContain('场景 运行中病历')
    expect(wrapper.text()).toContain('规则数 59 条')
    expect(wrapper.text()).toContain('内部覆盖详情')
    expect(wrapper.text()).toContain('验收工件')
    expect(wrapper.text()).toContain('需刷新')
    expect(wrapper.text()).toContain('基础时限5 条')
    expect(wrapper.text()).toContain('手术麻醉14 条')
    expect(wrapper.text()).toContain('全选8个质控族')
    expect(wrapper.text()).toContain('8个质控族')
    expect(wrapper.text()).toContain('49 个质控点')
    expect(wrapper.text()).toContain('查看质控点')
    expect(wrapper.text()).not.toContain('LX0609-11-03-01')
    expect(wrapper.text()).not.toContain('LX0609-07-04-02')
    expect(wrapper.text()).not.toContain('闸门未过 3/9')
    expect(wrapper.text()).not.toContain('证据待补强 10')

    await expandLuxianFamily(wrapper, '输血')

    expect(wrapper.text()).toContain('LX0609-07-04-02')
    expect(wrapper.text()).toContain('输血医嘱：输血医嘱与收费不一致')

    const internalButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('内部覆盖详情'))
    expect(internalButton).toBeTruthy()
    await internalButton!.trigger('click')
    await flushPromises()
    await nextTick()

    expect(getSheet2ExactReviewAcceptancePackage).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('客户验收口径与规则增强诊断')
  })

  it('演示导览参数进入页面时自动展示并可关闭记忆', async () => {
    routeQuery.tour = '1'
    window.localStorage.removeItem(CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY)

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('客户演示主流程')
    expect(wrapper.text()).toContain('先选择样本池')
    expect(wrapper.text()).toContain('客户自建测试病历用于现场演示')

    const nextButton = wrapper.find('.customer-sample-guide-next')
    expect(nextButton.exists()).toBe(true)
    await nextButton.trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('确认验证规则集')

    await nextButton.trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('限定 LX0609 质控点范围')

    const dismissButton = wrapper.find('.customer-sample-guide-dismiss')
    expect(dismissButton.exists()).toBe(true)
    await dismissButton.trigger('click')
    await nextTick()

    expect(window.localStorage.getItem(CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY)).toBe('true')
    expect(wrapper.text()).not.toContain('客户演示主流程')
  })

  it('首次进入且无演示参数时不自动弹出导览', async () => {
    window.localStorage.removeItem(CUSTOMER_SAMPLE_GUIDE_STORAGE_KEY)

    const wrapper = await mountView()

    expect(wrapper.text()).not.toContain('客户演示主流程')
    expect(wrapper.find('.customer-sample-guide-next').exists()).toBe(false)
  })

  it('可从工具栏重新打开导览并进入创建测试病历', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).not.toContain('客户演示主流程')
    const guideButton = wrapper.findAll('button').find((node) => node.text().includes('功能导览'))
    expect(guideButton).toBeTruthy()
    await guideButton!.trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('客户演示主流程')
    const startButton = wrapper.find('.customer-sample-guide-start')
    expect(startButton.exists()).toBe(true)
    await startButton.trigger('click')

    expect(routerPush).toHaveBeenCalledWith({ name: 'WorkstationV4SyntheticCaseNew' })
  })

  it('规则集目录接口失败时使用内置 fallback', async () => {
    listManualSampleValidationRuleSets.mockResolvedValueOnce({
      success: false,
      message: 'rule sets unavailable',
    })

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('泸县0609质控点验证 v1')
    expect(wrapper.text()).toContain('Luxian0916 质控点 v1')
    expect(wrapper.text()).toContain('SC 内涵质控全量 v1')
    expect(wrapper.text()).toContain('内置目录')
  })

  it('Luxian0916 需主动选择，并且提交时不携带 LX0609 专属范围参数', async () => {
    const wrapper = await mountView()

    const defaultCard = wrapper.find('[data-rule-set-key="luxian_0609_qc_v1"]')
    const luxian0916Card = wrapper.find('[data-rule-set-key="luxian_0916_qc_v1"]')
    expect(defaultCard.classes()).toContain('is-selected')
    expect(luxian0916Card.exists()).toBe(true)
    expect(luxian0916Card.classes()).not.toContain('is-selected')

    await luxian0916Card.trigger('click')
    await flushPromises()
    expect(luxian0916Card.classes()).toContain('is-selected')

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)
    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0916质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        ...buildRunIdentity('V001'),
        max_parallel_records: 16,
        validation_mode: 'customer',
        rule_set_key: 'luxian_0916_qc_v1',
      },
      { timeout: 90000 },
    )
    const submittedPayload = runManualSamplePool.mock.calls[0][1] as Record<string, unknown>
    expect(submittedPayload).not.toHaveProperty('selected_rule_ids')
    expect(submittedPayload).not.toHaveProperty('group_by_luxian_family')
  })

  it('可从更多操作导出泸县0609专项评估报告', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('导出报告')
    expect(
      wrapper
        .find('.a-dropdown-overlay-stub')
        .findAll('button')
        .filter((node) => node.text() === '创建测试病历'),
    ).toHaveLength(0)
    const exportItem = wrapper
      .findAll('button')
      .find((node) => node.text().includes('Markdown 评估报告'))
    expect(exportItem).toBeTruthy()
    await exportItem!.trigger('click')
    await flushPromises()

    expect(exportLuxian0609EvaluationReport).toHaveBeenCalledWith('md')
    expect(message.success).toHaveBeenCalledWith('泸县0609质控点评估报告已导出')
  })

  it('按病历勾选并透传并发病历数', async () => {
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const selectElements = wrapper.findAll('select')
    const parallelSelect = selectElements.find((node) =>
      node.findAll('option').some((option) => option.text() === '4'),
    )
    expect(parallelSelect).toBeTruthy()
    await parallelSelect!.setValue('2')

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        ...buildRunIdentity('V001'),
        max_parallel_records: 2,
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
      },
      { timeout: 90000 },
    )
    expect(message.success).toHaveBeenCalled()
  })

  it('首次运行采用模型设置中的病历并发', async () => {
    getDefaultLLMConfigSummary.mockResolvedValueOnce({
      execution_concurrency: {
        max_parallel_records: 12,
        family_max_concurrency: 3,
        http_max_concurrency: 24,
      },
    })
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        ...buildRunIdentity('V001'),
        max_parallel_records: 12,
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
      },
      { timeout: 90000 },
    )
  })

  it('同一 visit 的不同三坐标病例可同时精确提交', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord({ id: 'row-a', matched_visit_id: 'V-SHARED', sample_item_ids: ['item-a'] }),
          buildRecord({
            id: 'row-b',
            matched_institute_id: 'H2',
            matched_patient_id: 'P002',
            matched_visit_id: 'V-SHARED',
            sample_item_ids: ['item-b'],
          }),
        ],
        total: 2,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()
    for (const checkbox of wrapper.findAll('input.record-checkbox')) {
      await checkbox.setValue(true)
    }

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      expect.objectContaining({
        sample_item_ids: ['item-a', 'item-b'],
        record_refs: [
          { institute_id: 'H1', patient_id: 'P001', visit_id: 'V-SHARED' },
          { institute_id: 'H2', patient_id: 'P002', visit_id: 'V-SHARED' },
        ],
      }),
      { timeout: 90000 },
    )
  })

  it('两个选择项映射同一三坐标时失败关闭且不调用运行接口', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord({ id: 'row-a', sample_item_ids: ['item-a'] }),
          buildRecord({ id: 'row-b', sample_item_ids: ['item-b'] }),
        ],
        total: 2,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()
    for (const checkbox of wrapper.findAll('input.record-checkbox')) {
      await checkbox.setValue(true)
    }

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).not.toHaveBeenCalled()
    expect(message.warning).toHaveBeenCalledWith(expect.stringContaining('三坐标'))
  })

  it('将最近任务与选中病历操作合并为唯一工作底栏，并保留全部主操作', async () => {
    const wrapper = await mountView()

    const scrollArea = wrapper.get('.customer-sample-scroll')
    expect(scrollArea.classes()).not.toContain('pb-5')
    expect(scrollArea.classes()).toContain('has-work-dock')

    const taskOnlyDock = wrapper.get('[data-testid="customer-sample-work-dock"]')
    expect(taskOnlyDock.find('[data-testid="customer-sample-qc-task-status"]').exists()).toBe(true)
    expect(taskOnlyDock.text()).not.toContain('已选择 1 份病历')
    expect(wrapper.find('.customer-sample-recent-task-dock').exists()).toBe(false)
    expect(wrapper.find('.customer-sample-selection-run-bar').exists()).toBe(false)

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)
    await nextTick()

    const workDock = wrapper.get('[data-testid="customer-sample-work-dock"]')
    expect(workDock.findAll('[data-testid="customer-sample-qc-task-status"]')).toHaveLength(1)
    expect(workDock.text()).toContain('已选择 1 份病历')
    expect(workDock.text()).toContain('可质控 1 份')
    expect(workDock.text()).toContain('当前范围：全量0609')
    expect(workDock.text()).toContain('开始质控')
    expect(workDock.find('.customer-sample-work-dock__divider').exists()).toBe(true)
    expect(scrollArea.classes()).toContain('has-work-dock')
    expect(wrapper.find('.customer-sample-recent-task-dock').exists()).toBe(false)
    expect(wrapper.find('.customer-sample-selection-run-bar').exists()).toBe(false)

    const clearButton = workDock.findAll('button').find((node) => node.text() === '清空选择')
    expect(clearButton).toBeTruthy()
    await clearButton!.trigger('click')
    await nextTick()

    expect(
      wrapper
        .get('[data-testid="customer-sample-work-dock"]')
        .find('.customer-sample-work-dock__selection')
        .exists(),
    ).toBe(false)
    expect((recordCheckboxes[0].element as HTMLInputElement).checked).toBe(false)
  })

  it('无最近任务但选中病历时仍显示唯一工作底栏和开始质控操作', async () => {
    getSichuanWorkspaceBatchJob.mockResolvedValueOnce({
      success: false,
      message: '当前没有可恢复的质控任务',
    })
    listManualSamplePools.mockResolvedValueOnce({
      success: true,
      data: {
        items: [buildPool({ latest_job_id: '', latest_job_status: '' })],
        total: 1,
        page: 1,
        page_size: 50,
      },
    })

    const wrapper = await mountView()
    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)
    await nextTick()

    const workDock = wrapper.get('[data-testid="customer-sample-work-dock"]')
    expect(workDock.find('[data-testid="customer-sample-qc-task-status"]').exists()).toBe(false)
    expect(workDock.find('.customer-sample-work-dock__selection').exists()).toBe(true)
    expect(workDock.text()).toContain('开始质控')
    expect(wrapper.get('.customer-sample-scroll').classes()).toContain('has-work-dock')
  })

  it('客户样本复现模式未选择病历时提示先选择病历', async () => {
    const wrapper = await mountView()

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('请先选择病历'))
    expect(runButton).toBeTruthy()
    expect(runButton!.attributes('disabled')).toBeUndefined()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.warning).toHaveBeenCalledWith('请先选择要质控的病历')
    expect(runManualSamplePool).not.toHaveBeenCalled()
  })

  it('点击同步样本病历后展示紧凑同步状态条', async () => {
    getManualSamplePoolSyncJob
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-1',
          pool_id: 'pool-1',
          status: 'running',
          summary: {
            progress: {
              step_label: '正在同步',
              total_candidates: 2,
              eligible_visits: 2,
              record_progress: {
                total: 2,
                completed: 1,
                remaining: 1,
                missing_mr: 1,
              },
            },
          },
        },
      })
      .mockResolvedValue({
        success: true,
        data: {
          id: 'sync-job-1',
          pool_id: 'pool-1',
          status: 'completed',
          summary: {
            progress: { step_label: '同步完成', total_candidates: 2, eligible_visits: 2 },
          },
        },
      })
    const wrapper = await mountView()

    const syncButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('同步样本病历'))
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    expect(syncManualSamplePoolRecords).toHaveBeenCalledWith('pool-1', {
      only_intrinsic: true,
      include_in_batch_1: true,
    })
    expect(wrapper.text()).toContain('正在同步')
    expect(wrapper.text()).toContain('病历 1/2')
    expect(wrapper.text()).toContain('查看详情')
    expect(wrapper.text()).not.toContain('样本病历同步进度')
  })

  it('同步任务轮询时应更新进度并在完成后刷新列表', async () => {
    vi.useFakeTimers()
    getManualSamplePoolSyncJob
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-1',
          pool_id: 'pool-1',
          status: 'running',
          summary: {
            progress: {
              phase: 'primary_visibility',
              primary_visible: false,
              step_label: '正在同步病历文书',
              total_candidates: 3,
              eligible_visits: 2,
              record_progress: {
                total: 2,
                completed: 1,
                remaining: 1,
                missing_mr: 1,
              },
              processed_tables: 1,
              total_tables: 3,
            },
          },
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-1',
          pool_id: 'pool-1',
          status: 'running',
          summary: {
            progress: {
              phase: 'detail_sync',
              primary_visible: true,
              step_label: '继续同步病历文书',
              total_candidates: 3,
              eligible_visits: 2,
              record_progress: {
                total: 2,
                completed: 2,
                remaining: 0,
                missing_mr: 0,
              },
              processed_tables: 2,
              total_tables: 3,
            },
          },
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-1',
          pool_id: 'pool-1',
          status: 'running',
          summary: {
            progress: {
              phase: 'detail_sync',
              primary_visible: true,
              step_label: '继续同步病历文书',
              total_candidates: 3,
              eligible_visits: 2,
              record_progress: {
                total: 2,
                completed: 2,
                remaining: 0,
                missing_mr: 0,
              },
              processed_tables: 2,
              total_tables: 3,
            },
          },
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-1',
          pool_id: 'pool-1',
          status: 'completed',
          summary: {
            progress: {
              step_label: '同步完成',
              total_candidates: 3,
              eligible_visits: 2,
              record_progress: {
                total: 2,
                completed: 2,
                remaining: 0,
                missing_mr: 0,
              },
              processed_tables: 3,
              total_tables: 3,
            },
          },
        },
      })

    const wrapper = await mountView()

    const initialPoolCalls = listManualSamplePools.mock.calls.length
    const initialRecordCalls = getManualSamplePoolRecords.mock.calls.length

    const syncButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('同步样本病历'))
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('表 1/3')
    expect(wrapper.text()).toContain('病历 1/2')
    expect(wrapper.text()).toContain('正在同步病历基本信息')

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(wrapper.text()).toContain('表 2/3')
    expect(wrapper.text()).toContain('病历 2/2')
    expect(wrapper.text()).toContain('病历已进入样本池，文书整理中')
    const primaryVisiblePoolCalls = listManualSamplePools.mock.calls.length
    const primaryVisibleRecordCalls = getManualSamplePoolRecords.mock.calls.length
    expect(primaryVisiblePoolCalls).toBeGreaterThan(initialPoolCalls)
    expect(primaryVisibleRecordCalls).toBeGreaterThan(initialRecordCalls)

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(getManualSamplePoolSyncJob).toHaveBeenCalledTimes(3)
    expect(listManualSamplePools.mock.calls.length).toBe(primaryVisiblePoolCalls)
    expect(getManualSamplePoolRecords.mock.calls.length).toBe(primaryVisibleRecordCalls)

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(getManualSamplePoolSyncJob).toHaveBeenCalledTimes(4)
    expect(listManualSamplePools.mock.calls.length).toBeGreaterThan(initialPoolCalls)
    expect(getManualSamplePoolRecords.mock.calls.length).toBeGreaterThan(initialRecordCalls)
  })

  it('主记录可见后刷新一次并在后续失败时保留病例列表', async () => {
    vi.useFakeTimers()
    getManualSamplePoolSyncJob
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-primary-failed',
          pool_id: 'pool-1',
          status: 'running',
          summary: {
            progress: {
              phase: 'primary_visibility',
              primary_visible: false,
              total_candidates: 1,
              eligible_visits: 1,
            },
          },
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-primary-failed',
          pool_id: 'pool-1',
          status: 'running',
          summary: {
            progress: {
              phase: 'primary_visible',
              primary_visible: true,
              total_candidates: 1,
              eligible_visits: 1,
            },
          },
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          id: 'sync-job-primary-failed',
          pool_id: 'pool-1',
          status: 'failed',
          error_message:
            'relation "mr" does not exist; SQLSTATE 42P01; PG source 192.168.140.160:16016',
          summary: {
            progress: {
              phase: 'detail_sync',
              primary_visible: true,
              total_candidates: 1,
              eligible_visits: 1,
            },
          },
        },
      })

    const wrapper = await mountView()
    const recordCountBeforeSync = wrapper.findAll('input.record-checkbox').length
    const syncButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('同步样本病历'))
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()
    const recordCallsAfterPrimaryVisible = getManualSamplePoolRecords.mock.calls.length
    expect(wrapper.text()).toContain('病历已进入样本池，文书整理中')

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(getManualSamplePoolRecords.mock.calls.length).toBe(recordCallsAfterPrimaryVisible)
    expect(wrapper.findAll('input.record-checkbox')).toHaveLength(recordCountBeforeSync)
    expect(wrapper.text()).toContain('医院数据源缺少本次同步所需的病历资料')
    expect(wrapper.text()).not.toContain('192.168.140.160')
    expect(wrapper.text()).not.toContain('16016')
    expect(wrapper.text()).not.toContain('relation "mr"')
    expect(wrapper.text()).not.toContain('SQLSTATE')
    expect(wrapper.text()).not.toContain('PG source')
  })

  it('最近同步任务完成但未匹配源库病历时保留诊断提示', async () => {
    getLatestManualSamplePoolSyncJob.mockResolvedValue({
      success: true,
      data: {
        id: 'sync-job-empty',
        pool_id: 'pool-1',
        status: 'completed',
        summary: {
          progress: {
            step_label: '同步完成',
            total_candidates: 3,
            eligible_visits: 0,
            record_progress: {
              total: 0,
              completed: 0,
              remaining: 0,
              missing_mr: 0,
            },
            processed_tables: 0,
            total_tables: 12,
            matched: 0,
            ambiguous: 1,
            unmatched: 2,
            total_rows_pulled: 0,
            total_rows_upserted: 0,
          },
          eligible_visits: 0,
          matched: 0,
          ambiguous: 1,
          unmatched: 2,
          total_rows_pulled: 0,
          total_rows_upserted: 0,
        },
      },
    })

    const wrapper = await mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('未匹配到可同步病历')
    const detailButton = wrapper.findAll('button').find((node) => node.text().includes('查看详情'))
    expect(detailButton).toBeTruthy()
    await detailButton!.trigger('click')
    await flushPromises()

    const drawerText = wrapper.find('.a-drawer-stub').text()
    expect(drawerText).toContain('未匹配到可同步病历')
    expect(drawerText).toContain('0 份')
    expect(drawerText).toContain('待确认 1 份，未找到 2 份')
    expect(drawerText).toContain('0/0')
  })

  it('同步连接失败时不向客户展示源库地址和端口', async () => {
    getLatestManualSamplePoolSyncJob.mockResolvedValue({
      success: true,
      data: {
        id: 'sync-job-failed',
        pool_id: 'pool-1',
        status: 'failed',
        error_message:
          'connection to server at "192.168.140.160", port 16016 failed: timeout expired',
        summary: {
          progress: {
            processed_tables: 0,
            total_tables: 50,
          },
        },
      },
    })

    const wrapper = await mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('暂时无法连接医院数据源')
    expect(wrapper.text()).toContain('重试')
    expect(wrapper.text()).not.toContain('192.168.140.160')
    expect(wrapper.text()).not.toContain('16016')

    const detailButton = wrapper.findAll('button').find((node) => node.text().includes('查看详情'))
    expect(detailButton).toBeTruthy()
    await detailButton!.trigger('click')
    await flushPromises()

    const drawerText = wrapper.find('.a-drawer-stub').text()
    expect(drawerText).toContain('暂时无法连接医院数据源')
    expect(drawerText).not.toContain('192.168.140.160')
    expect(drawerText).not.toContain('16016')
  })

  it('支持下载以就诊ID为主的客户样本导入模板', async () => {
    const wrapper = await mountView()

    const importButton = wrapper.findAll('button').find((node) => node.text().includes('导入模板'))
    expect(importButton).toBeTruthy()
    await importButton!.trigger('click')
    await flushPromises()

    const downloadButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('下载模板'))
    expect(downloadButton).toBeTruthy()
    await downloadButton!.trigger('click')
    await flushPromises()

    expect(writeFile).toHaveBeenCalled()
    const args = writeFile.mock.calls[0]
    expect(args[1]).toBe('客户样本导入模板.xlsx')
    expect(aoaToSheet).toHaveBeenCalledWith([
      ['就诊ID', '住院流水号', '病案号', '患者姓名', '备注'],
      ['1870471', 'IP0000135258', '362948', '蒲云鹏', '示例：优先填写就诊ID'],
      ['1430048', '', '', '', '没有住院流水号/病案号时，可只填就诊ID'],
    ])
    expect(aoaToSheet).toHaveBeenCalledWith([
      ['字段', '是否必填', '说明'],
      ['就诊ID', '推荐必填', '最可靠的匹配字段，对应源库 visit_id。'],
      ['住院流水号', '可选', '对应源库 inpat_no，例如 IP0000135258。'],
      ['病案号', '可选', '对应源库 mr_no，例如 362948。'],
      ['患者姓名', '可选', '只用于辅助确认，不作为唯一匹配键。'],
      ['备注', '可选', '客户自定义来源或批次说明。'],
    ])
    expect(bookAppendSheet).toHaveBeenCalledWith(expect.anything(), expect.anything(), '样本ID')
    expect(bookAppendSheet).toHaveBeenCalledWith(expect.anything(), expect.anything(), '填写说明')
  })

  it('导入模板上传提示不再要求只填写住院号', async () => {
    const wrapper = await mountView()

    const importButton = wrapper.findAll('button').find((node) => node.text().includes('导入模板'))
    expect(importButton).toBeTruthy()
    await importButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('优先填写就诊ID，可补充住院流水号、病案号和患者姓名。')
    expect(wrapper.text()).not.toContain('模板只需填写住院号')
  })

  it('导入模板成功后应切换到新样本池并刷新病历池', async () => {
    listManualSamplePools
      .mockResolvedValueOnce({
        success: true,
        data: { items: [buildPool()], total: 1, page: 1, page_size: 50 },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          items: [
            buildPool(),
            {
              ...buildPool(),
              id: 'pool-2',
              name: '第二轮样本池',
              latest_job_id: undefined,
              latest_job_status: undefined,
            },
          ],
          total: 2,
          page: 1,
          page_size: 50,
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          items: [
            buildPool(),
            {
              ...buildPool(),
              id: 'pool-2',
              name: '第二轮样本池',
              latest_job_id: undefined,
              latest_job_status: undefined,
            },
          ],
          total: 2,
          page: 1,
          page_size: 50,
        },
      })
    getManualSamplePoolRecords
      .mockResolvedValueOnce({
        success: true,
        data: {
          pool: buildPool(),
          items: [buildRecord()],
          total: 1,
          page: 1,
          page_size: 20,
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          pool: {
            ...buildPool(),
            id: 'pool-2',
            name: '第二轮样本池',
            latest_job_id: undefined,
            latest_job_status: undefined,
          },
          items: [
            buildRecord({
              id: 'V010',
              matched_visit_id: 'V010',
              mr_no: '300001',
              patient_name: '新患者',
            }),
          ],
          total: 1,
          page: 1,
          page_size: 20,
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          pool: {
            ...buildPool(),
            id: 'pool-2',
            name: '第二轮样本池',
            latest_job_id: undefined,
            latest_job_status: undefined,
          },
          items: [
            buildRecord({
              id: 'V010',
              matched_visit_id: 'V010',
              mr_no: '300001',
              patient_name: '新患者',
            }),
          ],
          total: 1,
          page: 1,
          page_size: 20,
        },
      })

    const wrapper = await mountView()

    const importButton = wrapper.findAll('button').find((node) => node.text().includes('导入模板'))
    expect(importButton).toBeTruthy()
    await importButton!.trigger('click')
    await flushPromises()

    const inputs = wrapper.findAll('input')
    const poolNameInput = inputs.find((node) =>
      node.attributes('placeholder')?.includes('手工问题样本池'),
    )
    expect(poolNameInput).toBeTruthy()
    await poolNameInput!.setValue('第二轮样本池')

    const uploadTrigger = wrapper.find('button.upload-trigger')
    expect(uploadTrigger.exists()).toBe(true)
    await uploadTrigger.trigger('click')
    await flushPromises()

    const confirmButton = wrapper.find('button.modal-ok')
    await confirmButton.trigger('click')
    await flushPromises()

    expect(importManualSamplePoolByUpload).toHaveBeenCalledWith({
      pool_name: '第二轮样本池',
      description: '',
      scene: 'running',
      file: expect.objectContaining({
        name: 'demo.xlsx',
      }),
    })
    expect(message.success).toHaveBeenCalledWith('导入成功，共写入 2 条样本，正在匹配源库病历')
    expect(matchManualSamplePool).toHaveBeenCalledWith('pool-2')
    expect(wrapper.text()).toContain('导入样本 ID 结果')
    expect(wrapper.text()).toContain('已读取 2 条 ID')
    expect(wrapper.text()).toContain('匹配 2 份，待确认 0 份，未找到 0 份')
    expect(wrapper.text()).toContain('当前样本池')
    expect(wrapper.text()).toContain('第二轮样本池')
    expect(wrapper.text()).toContain('新患者')
  })

  it('导入模板后若没有匹配到病历应显示明确警告并禁用同步', async () => {
    matchManualSamplePool.mockResolvedValueOnce({
      success: true,
      data: {
        pool_id: 'pool-2',
        matched: 0,
        ambiguous: 0,
        unmatched: 2,
      },
    })

    const wrapper = await mountView()

    const importButton = wrapper.findAll('button').find((node) => node.text().includes('导入模板'))
    expect(importButton).toBeTruthy()
    await importButton!.trigger('click')
    await flushPromises()

    const poolNameInput = wrapper
      .findAll('input')
      .find((node) => node.attributes('placeholder')?.includes('手工问题样本池'))
    expect(poolNameInput).toBeTruthy()
    await poolNameInput!.setValue('第二轮样本池')

    const uploadTrigger = wrapper.find('button.upload-trigger')
    await uploadTrigger.trigger('click')
    await flushPromises()

    await wrapper.find('button.modal-ok').trigger('click')
    await flushPromises()

    expect(message.warning).toHaveBeenCalledWith(
      '匹配 0 份，待人工确认 0 份，未找到 2 份。未匹配到病历，请检查 ID 类型或医院数据源配置。',
    )
    const syncButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('开始同步匹配到的病历'))
    expect(syncButton?.attributes('disabled')).toBeDefined()
  })

  it('点击查看病历后打开只读文书工作台', async () => {
    const wrapper = await mountView()
    const documentResponse = await getEditableMedicalRecordDocuments()
    getEditableMedicalRecordDocuments.mockResolvedValue({
      ...documentResponse,
      data: {
        ...documentResponse.data,
        // 模拟接口首先返回医嘱，首次打开仍应选中入院记录。
        documents: [
          {
            key: 'order-first',
            document_type: 'inpat_nondrug_order',
            title: '临时医嘱',
            content: '测试医嘱',
            record_time: '',
            submit_time: '',
            enabled: true,
          },
          ...documentResponse.data.documents,
        ],
        current_record: {
          admission_time: '2026-02-02T10:00:00+08:00',
          admission_time_source: 'inpat_registration',
          admission_time_state: 'exact',
        },
      },
    })

    const reviewAction = [...wrapper.findAll('button'), ...wrapper.findAll('a')].find(
      (node) => node.text() === '查看病历',
    )
    expect(reviewAction).toBeTruthy()
    await reviewAction!.trigger('click')
    await flushPromises()

    expect(getEditableMedicalRecordDocuments).toHaveBeenCalledWith('V001', {
      institute_id: 'H1',
      patient_id: 'P001',
      visit_id: 'V001',
      source_view: 'current',
    })
    const modalText = wrapper.find('.a-modal-stub').text()
    expect(modalText).toContain('查看病历')
    expect(wrapper.find('.editable-copy-notice').exists()).toBe(false)
    expect(wrapper.find('.record-compare-head').exists()).toBe(false)
    expect(modalText).not.toContain('病历信息')
    expect(wrapper.find('.editable-copy-form-grid').exists()).toBe(false)
    expect(wrapper.find('.record-compare-shell').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'QCRecordCompareWorkbench' }).props('dischargeTime')).toBe(
      '2026-06-26 08:31:00',
    )
    expect(wrapper.find('.record-result-column').exists()).toBe(false)
    expect(wrapper.find('.record-content-toolbar').text()).toContain('入院记录')
    expect(wrapper.get('[data-testid="record-admission-time"]').text()).toContain(
      '2026-02-02 10:00:00',
    )
    expect(modalText).toContain('入院记录')
    expect(wrapper.find('.editable-copy-document-directory-list.is-tree').exists()).toBe(true)
    const admissionToggle = wrapper.get('[data-testid="record-document-group-toggle-admission"]')
    expect(admissionToggle.attributes('aria-expanded')).toBe('true')
    await admissionToggle.trigger('click')
    expect(admissionToggle.attributes('aria-expanded')).toBe('false')
    await admissionToggle.trigger('click')
    expect(admissionToggle.attributes('aria-expanded')).toBe('true')

    await wrapper.get('[data-testid="record-document-search"]').setValue('头孢')
    expect(
      wrapper.get('[data-testid="record-document-group-toggle-order"]').attributes('aria-expanded'),
    ).toBe('true')
    expect(modalText).not.toContain('副本信息')
    expect(modalText).not.toContain('张三编辑副本')
    expect(modalText).not.toContain('源病历编辑副本')
    expect(modalText).not.toContain('新增文书')
    expect(modalText).not.toContain('新增医嘱')
    expect(modalText).not.toContain('保存为测试病历')
  })

  it('查看病历与查看结果的顶部信息使用同一份病历上下文', async () => {
    const wrapper = await mountView()
    const viewAction = wrapper.findAll('button').find((node) => node.text() === '查看病历')
    await viewAction!.trigger('click')
    await flushPromises()
    const banner = wrapper.findComponent({ name: 'MedicalRecordContextBanner' })
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('张三')
    expect(banner.text()).toContain('普外科')
    expect(banner.text()).toContain('2248248')
    expect(banner.text()).toContain('住院时间 2026-06-18 07:02:00 → 2026-06-26 08:31:00')
    expect(wrapper.find('.editable-copy-source-card').exists()).toBe(false)
    const resultAction = wrapper.findAll('.customer-sample-secondary-link').find((node) => node.text() === '查看结果')
    await resultAction!.trigger('click')
    await flushPromises()
    expect(latestRecordResultComparisonDrawerProps?.focus).toMatchObject(banner.props('context'))
    expect(createManualTestMedicalRecord).not.toHaveBeenCalled()
    expect(runManualSamplePool).not.toHaveBeenCalled()
  })

  it('单病历点击查看结果必须只打开病历对照页，不能进入批量结果抽屉', async () => {
    const wrapper = await mountView()

    const resultLink = wrapper
      .findAll('.customer-sample-secondary-link')
      .find((node) => node.text() === '查看结果')
    expect(resultLink).toBeTruthy()
    await resultLink!.trigger('click')
    await flushPromises()

    expect(latestRecordResultComparisonDrawerProps?.open).toBe(true)
    expect(latestRecordResultComparisonDrawerProps?.focus).toMatchObject({
      visitId: 'V001',
      instituteId: 'H1',
      patientId: 'P001',
      recordId: '2248248',
      admissionTime: '2026-06-18 07:02:00',
      dischargeTime: '2026-06-26 08:31:00',
      label: '张三 · 普外科 · 2248248',
    })
    expect(latestBatchResultDrawerProps?.open).not.toBe(true)
  })

  it('单病历查看结果只把当前病历坐标交给对照页，不在父页面回退到样本池任务', async () => {
    listSichuanWorkspaceBatchJobs.mockResolvedValue({
      success: true,
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 5,
      },
    })
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool({ latest_job_id: 'pool-latest-other-record' }),
        items: [
          buildRecord({
            id: 'V002',
            matched_visit_id: 'V002',
            mr_no: '2249001',
            patient_name: '李四',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()
    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('pool-latest-other-record')
    getSichuanWorkspaceBatchJob.mockClear()

    const resultLink = wrapper
      .findAll('.customer-sample-secondary-link')
      .find((node) => node.text() === '查看结果')
    expect(resultLink).toBeTruthy()
    await resultLink!.trigger('click')
    await flushPromises()

    expect(getSichuanWorkspaceBatchJob).not.toHaveBeenCalled()
    expect(latestBatchResultDrawerProps?.open).not.toBe(true)
    expect(latestRecordResultComparisonDrawerProps?.open).toBe(true)
    expect(latestRecordResultComparisonDrawerProps?.focus).toMatchObject({
      visitId: 'V002',
      recordId: '2249001',
    })
  })

  it('悬浮条单病例任务按冻结身份打开新版结果面板', async () => {
    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: {
        id: 'job-0609',
        status: 'completed',
        rule_set_key: 'luxian_0609_qc_v1',
        filters: {
          record_refs: [
            { institute_id: 'task-hospital', patient_id: 'task-patient', visit_id: 'task-visit' },
          ],
        },
        items: [],
      },
    })
    const wrapper = await mountView()
    await wrapper.get('[data-testid="qc-task-view-result"]').trigger('click')
    await flushPromises()
    await nextTick()
    expect(latestRecordResultComparisonDrawerProps?.open).toBe(true)
    expect(latestRecordResultComparisonDrawerProps?.focus).toMatchObject({
      instituteId: 'task-hospital',
      patientId: 'task-patient',
      visitId: 'task-visit',
    })
    expect(latestBatchResultDrawerProps?.open).not.toBe(true)
  })

  it('打开泸县0609任务详情时保留 scoped run 计数和映射字段', async () => {
    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: {
        id: 'job-0609',
        status: 'completed',
        rule_set_key: 'luxian_0609_qc_v1',
        rule_count: 3,
        customer_rule_count: 2,
        execution_rule_count: 3,
        filters: {
          rule_set_key: 'luxian_0609_qc_v1',
          selected_rule_ids: ['LX0609-03-01-01', 'LX0609-03-01-02'],
          scoped_customer_rule_ids: ['LX0609-03-01-01', 'LX0609-03-01-02'],
          rule_ids: ['LX-017', 'CL-250', 'SC-068'],
          record_rule_map: {
            V001: ['LX-017', 'CL-250', 'SC-068'],
          },
          customer_rule_count: 2,
          execution_rule_count: 3,
        },
        items: [
          {
            rule_id: 'LX0609-03-01-01',
            record_id: 'V001',
            status: 'data_gap',
            result_status: 'data_gap',
            is_compliant: false,
          },
        ],
      },
    })
    const wrapper = await mountView()

    const resultLink = wrapper.find('[data-testid="qc-task-view-result"]')
    expect(resultLink.exists()).toBe(true)
    await resultLink.trigger('click')
    await flushPromises()
    await nextTick()

    expect(getSichuanWorkspaceBatchJob).toHaveBeenLastCalledWith('job-0609')
    const detail = latestBatchResultDrawerProps?.batchJobDetail as {
      customer_rule_count?: number
      execution_rule_count?: number
      filters?: Record<string, unknown>
    }
    expect(detail.customer_rule_count).toBe(2)
    expect(detail.execution_rule_count).toBe(3)
    expect(detail.filters?.selected_rule_ids).toEqual(['LX0609-03-01-01', 'LX0609-03-01-02'])
    expect(detail.filters?.scoped_customer_rule_ids).toEqual(['LX0609-03-01-01', 'LX0609-03-01-02'])
    expect(detail.filters?.record_rule_map).toEqual({
      V001: ['LX-017', 'CL-250', 'SC-068'],
    })
    expect(getSichuanWorkspaceBatchJobDebugSnapshot).toHaveBeenCalledWith('job-0609', {
      rule_job_id: undefined,
      item_limit: undefined,
    })
    expect(latestBatchResultDrawerProps?.fetchBatchJobDebugSnapshot).toBeTypeOf('function')
  })

  it('只选中不可执行病历时提示并阻止发起验证', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord({
            id: 'V003',
            matched_visit_id: '',
            mr_no: '2250001',
            patient_name: '王五',
            match_status: 'unmatched',
            sync_status: 'missing',
            bundle_status: 'pending',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.warning).toHaveBeenCalledWith(
      '已选 1 份病历，完整范围未提交：未关联病历 1 份。请处理后重试',
    )
    expect(runManualSamplePool).not.toHaveBeenCalled()
  })

  it('允许已种入PG的合成样本直接发起验证', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool({ name: '泸县0609合成质控样本 v1' }),
        items: [
          buildRecord({
            id: 'sample-item-syn-001',
            matched_visit_id: 'LX0609_SYN_001',
            mr_no: 'LX0609_SYN_001',
            patient_name: '合成样本001',
            sync_status: 'synthetic_seeded',
            bundle_status: 'ready',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.warning).not.toHaveBeenCalledWith(
      '当前选中的病历还未完成匹配、同步或 bundle 准备，暂时无法发起验证',
    )
    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        ...buildRunIdentity('LX0609_SYN_001'),
        max_parallel_records: 16,
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
      },
      { timeout: 90000 },
    )
  })

  it('客户自建病历列表优先显示可记忆的病历标题', async () => {
    const backendCreatedAt = '2026-06-23T15:30:12'
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool({ id: 'customer-created-test-records-v1', name: '客户自建测试病历' }),
        items: [
          buildRecord({
            id: 'CUSTOMER_TEST_202606231530ABCDEF',
            matched_visit_id: 'CUSTOMER_TEST_202606231530ABCDEF',
            mr_no: 'CUSTOMER_TEST_202606231530ABCDEF',
            patient_name: '测试患者丙',
            patient_sex: '女',
            patient_age: '68',
            department: '消化内科',
            created_at: backendCreatedAt,
            sample_items: [
              {
                id: 'item-memory-title',
                created_at: backendCreatedAt,
                raw_payload: {
                  case_title: '会诊质量质控病历｜LX020/021/022｜202606231530',
                },
              },
            ],
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('会诊质量质控')
    expect(wrapper.text()).not.toContain('会诊质量质控病历')
    expect(wrapper.text()).not.toContain('会诊质量质控病历｜LX020/021/022')
    expect(wrapper.find('.customer-sample-patient-name').text()).toBe('测试患者丙 · 会诊质量质控')
    expect(wrapper.find('.customer-sample-patient-avatar').exists()).toBe(true)
    expect(wrapper.find('.customer-sample-patient-avatar').attributes('alt')).toBe('测试患者丙头像')
    expect(wrapper.find('.customer-sample-patient-avatar').attributes('src')).toContain(
      'patient-icon-elder-woman',
    )
    expect(wrapper.find('.customer-sample-created-time').text()).toBe(
      expectedCompactLocalTime(backendCreatedAt).slice(0, 10),
    )
    expect(wrapper.find('.customer-sample-patient-cell').text()).not.toContain('ABCDEF')
    const expectedCodeTime = expectedCompactLocalTime(backendCreatedAt)
      .slice(5)
      .replace('-', '')
      .replace(' ', '-')
      .replace(':', '')
    expect(wrapper.find('.customer-sample-record-code').text()).toBe(`测试-${expectedCodeTime}`)
    expect(wrapper.find('.customer-sample-record-code').attributes('title')).toBe(
      'CUSTOMER_TEST_202606231530ABCDEF',
    )
    expect(wrapper.find('.record-actions').text()).not.toContain('已关联病历')
    expect(wrapper.find('.record-actions').text()).not.toContain('已就绪')
    expect(wrapper.find('.record-actions').text()).not.toContain('查看详情')
    expect(wrapper.findAll('.customer-sample-secondary-link').map((node) => node.text())).toEqual([
      '查看病历',
      '查看结果',
      '创建副本',
    ])
  })

  it('真实样本没有病历标题时病历列不重复显示患者名', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool({ id: 'pool-0426', name: '0426' }),
        items: [
          buildRecord({
            id: 'V_REAL_001',
            matched_visit_id: 'V_REAL_001',
            mr_no: 'REAL_001',
            patient_name: '邹才林',
            department: '骨科',
            sample_items: [],
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })

    const wrapper = await mountView()

    expect(wrapper.find('.customer-sample-patient-name').text()).toBe('邹才林')
    expect(wrapper.find('.customer-sample-patient-name').text()).not.toBe('邹才林 · 邹才林')
  })

  it('病历标题已包含患者名时列表不重复拼接患者名', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool({ id: 'customer-created-test-records-v1', name: '客户自建测试病历' }),
        items: [
          buildRecord({
            id: 'CUSTOMER_TEST_EDIT_COPY',
            matched_visit_id: 'CUSTOMER_TEST_EDIT_COPY',
            mr_no: 'CUSTOMER_TEST_20260626024719B3BA68',
            patient_name: '邹才林',
            department: '康复科',
            sample_items: [
              {
                id: 'ct-edit-copy',
                raw_payload: {
                  case_title: '邹才林编辑副本',
                },
              },
            ],
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })

    const wrapper = await mountView()

    expect(wrapper.find('.customer-sample-patient-name').text()).toBe('邹才林 · 编辑副本')
    expect(wrapper.find('.customer-sample-patient-name').text()).not.toContain('邹才林 · 邹才林')
  })

  it('病历池列表隐藏验证范围长规则串并保留精简操作', async () => {
    const selectedRuleIds = [
      'LX0609-04-02-01',
      'LX0609-04-02-03',
      'LX0609-04-02-04',
      'LX0609-05-01-01',
      'LX0609-04-01-01',
      'LX0609-04-02-02',
      'LX0609-04-02-05',
      'LX0609-04-03-01',
      'LX0609-11-01-01',
      'LX0609-11-02-01',
      'LX0609-11-02-02',
      'LX0609-04-04-01',
      'LX0609-04-04-02',
      'LX0609-04-04-03',
      'LX0609-04-01-02',
      'LX0609-04-01-03',
    ]
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool({ id: 'customer-created-test-records-v1', name: '客户自建测试病历' }),
        items: [
          buildRecord({
            id: 'CUSTOMER_TEST_202606251031A1B2C3',
            matched_visit_id: 'CUSTOMER_TEST_202606251031A1B2C3',
            mr_no: 'CUSTOMER_TEST_202606251031A1B2C3',
            patient_name: '王某某',
            department: '普通外科',
            candidate_rule_ids: selectedRuleIds,
            issue_preview: [`按质控点创建：${selectedRuleIds.join('、')}。`],
            issue_preview_text: `按质控点创建：${selectedRuleIds.join('、')}。`,
            sample_items: [
              {
                id: 'item-long-rule-summary',
                row_no: 1,
                manual_issue_text: `按质控点创建：${selectedRuleIds.join('、')}。`,
                issue_category: '手术麻醉',
                raw_payload: {
                  case_title:
                    '手术麻醉质控病历｜LX003/024/025/028/029/030/031/032/033/034/035/036/037/038/039/040｜0625-1031',
                  selected_rule_ids: selectedRuleIds,
                },
              },
            ],
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })

    const wrapper = await mountView()

    expect(wrapper.find('.customer-sample-patient-name').text()).toBe('王某某 · 手术麻醉质控')
    expect(wrapper.find('.customer-sample-family-chip').exists()).toBe(false)
    expect(wrapper.find('.customer-sample-rule-count-chip').exists()).toBe(false)
    expect(wrapper.find('.customer-sample-rule-id-chip').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('按质控点创建 · 手术麻醉')
    expect(wrapper.text()).not.toContain('手术麻醉16个质控点')
    expect(wrapper.text()).not.toContain('LX0609-05-01-01、LX0609-04-01-01、LX0609-04-02-02')
    const actionCellText = wrapper.find('.customer-sample-action-cell').text()
    expect(actionCellText).toContain('查看病历')
    expect(actionCellText).toContain('查看结果')
    expect(actionCellText).toContain('创建副本')
    expect(actionCellText).not.toContain('查看详情')
  })

  it('合成样本可勾选 LX0609 质控点并只提交 selected_rule_ids', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool({ name: '泸县0609合成质控样本 v1' }),
        items: [
          buildRecord({
            id: 'sample-item-syn-001',
            matched_visit_id: 'LX0609_SYN_001',
            mr_no: 'LX0609_SYN_001',
            patient_name: '合成样本001',
            sync_status: 'synthetic_seeded',
            bundle_status: 'ready',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()

    await expandLuxianFamily(wrapper, '会诊质量')
    const lx020 = wrapper.find('input.luxian-rule-checkbox[value="LX0609-03-01-01"]')
    const lx021 = wrapper.find('input.luxian-rule-checkbox[value="LX0609-03-01-02"]')
    expect(lx020.exists()).toBe(true)
    expect(lx021.exists()).toBe(true)
    await lx020.setValue(true)
    await lx021.setValue(true)

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        ...buildRunIdentity('LX0609_SYN_001'),
        max_parallel_records: 16,
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
        selected_rule_ids: ['LX0609-03-01-01', 'LX0609-03-01-02'],
      },
      { timeout: 90000 },
    )
  })

  it('已同步病历可创建编辑副本，保存时不修改源病历并记录来源信息', async () => {
    const wrapper = await mountView()

    const copyAction = wrapper
      .findAll('.customer-sample-secondary-link')
      .find((node) => node.text() === '创建副本')
    expect(copyAction).toBeTruthy()
    await copyAction!.trigger('click')
    await flushPromises()
    await nextTick()

    expect(getEditableMedicalRecordDocuments).toHaveBeenCalledWith('V001', {
      institute_id: 'H1',
      patient_id: 'P001',
      visit_id: 'V001',
    })
    expect(wrapper.find('.a-modal-stub').text()).toContain('原始同步病历保持只读')
    expect(wrapper.find('.editable-copy-document-workbench').exists()).toBe(true)
    expect(wrapper.find('.editable-copy-document-directory').text()).toContain('医嘱')
    expect(wrapper.find('.editable-copy-document-directory').text()).toContain(
      '长期 3 条 · 临时 2 条',
    )

    const textareas = wrapper.findAll('textarea')
    const documentTextarea = textareas.find((node) => node.element.value.includes('患者因腹痛入院'))
    expect(documentTextarea).toBeTruthy()
    await documentTextarea!.setValue('编辑后的入院记录正文，保留临床上下文并补充质控关注点。')

    const saveButton = wrapper.findAll('button').find((node) => node.text() === '保存为测试病历')
    expect(saveButton).toBeTruthy()
    await saveButton!.trigger('click')
    await flushPromises()

    expect(createManualTestMedicalRecord).toHaveBeenCalledTimes(1)
    const payload = createManualTestMedicalRecord.mock.calls[0][0]
    expect(payload.documents).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          title: '入院记录',
          content: '编辑后的入院记录正文，保留临床上下文并补充质控关注点。',
        }),
      ]),
    )
    const courseDocument = payload.documents.find(
      (item: { title?: string }) => item.title === '日常病程记录',
    )
    expect(courseDocument).toBeTruthy()
    expect(courseDocument.record_time).toBeUndefined()
    expect(courseDocument.submit_time).toBeUndefined()
    expect(payload.source).toEqual(
      expect.objectContaining({
        type: 'customer_source_editable_copy',
        source_pool_id: 'pool-1',
        source_record_id: 'V001',
        source_visit_id: 'V001',
      }),
    )
    expect(runManualSamplePool).not.toHaveBeenCalled()
  })

  it('编辑副本支持新增文书、医嘱并从副本删除源文书', async () => {
    const wrapper = await mountView()

    const copyAction = wrapper
      .findAll('.customer-sample-secondary-link')
      .find((node) => node.text() === '创建副本')
    expect(copyAction).toBeTruthy()
    await copyAction!.trigger('click')
    await flushPromises()

    const documentNavCount = wrapper.findAll('.editable-copy-document-nav-item').length

    const addDocumentButton = wrapper.findAll('button').find((node) => node.text() === '新增文书')
    expect(addDocumentButton).toBeTruthy()
    await addDocumentButton!.trigger('click')
    await nextTick()

    expect(wrapper.findAll('.editable-copy-document-nav-item')).toHaveLength(documentNavCount + 1)
    const newDocumentTextarea = wrapper
      .findAll('textarea')
      .find((node) => node.element.value.includes('请填写日常病程记录正文'))
    expect(newDocumentTextarea).toBeTruthy()
    await newDocumentTextarea!.setValue('新增的日常病程记录正文，说明患者治疗经过和复核关注点。')

    const addOrderButton = wrapper.findAll('button').find((node) => node.text() === '新增医嘱')
    expect(addOrderButton).toBeTruthy()
    await addOrderButton!.trigger('click')
    await nextTick()

    expect(wrapper.findAll('.editable-copy-document-nav-item')).toHaveLength(documentNavCount + 1)
    const orderGroupNavItem = wrapper
      .findAll('.editable-copy-document-nav-item')
      .find((node) => node.text().includes('医嘱'))
    expect(orderGroupNavItem).toBeTruthy()
    await orderGroupNavItem!.trigger('click')
    await nextTick()
    expect(wrapper.findAll('.editable-copy-order-table tbody tr').length).toBeGreaterThanOrEqual(2)
    const newOrderTextarea = wrapper
      .findAll('textarea')
      .find((node) => node.element.value.includes('请填写医嘱名称'))
    expect(newOrderTextarea).toBeTruthy()
    await newOrderTextarea!.setValue('临时医嘱：头孢曲松 2g 静滴 qd，开立医师陈医师。')

    const admissionNavItem = wrapper
      .findAll('.editable-copy-document-nav-item')
      .find((node) => node.text().includes('入院记录'))
    expect(admissionNavItem).toBeTruthy()
    await admissionNavItem!.trigger('click')
    await nextTick()

    const removeFromCopyButton = wrapper
      .find('.editable-copy-document-editor')
      .findAll('button')
      .find((node) => node.text() === '从副本删除')
    expect(removeFromCopyButton).toBeTruthy()
    await removeFromCopyButton!.trigger('click')
    await nextTick()

    expect(wrapper.find('.editable-copy-document-editor').text()).toContain('恢复')

    const saveButton = wrapper.findAll('button').find((node) => node.text() === '保存为测试病历')
    expect(saveButton).toBeTruthy()
    await saveButton!.trigger('click')
    await flushPromises()

    const payload = createManualTestMedicalRecord.mock.calls[0][0]
    const documentContents = payload.documents.map((item: { content: string }) => item.content)
    expect(documentContents).not.toContain('患者因腹痛入院，完善相关检查后收入普通外科。')
    expect(documentContents).toContain('新增的日常病程记录正文，说明患者治疗经过和复核关注点。')
    expect(documentContents).toContain('临时医嘱：头孢曲松 2g 静滴 qd，开立医师陈医师。')
  })

  it('医嘱在查看/编辑副本中按长期和临时分类并按时间倒序展示', async () => {
    const wrapper = await mountView()

    const copyAction = wrapper
      .findAll('.customer-sample-secondary-link')
      .find((node) => node.text() === '创建副本')
    expect(copyAction).toBeTruthy()
    await copyAction!.trigger('click')
    await flushPromises()

    const orderGroupNavItem = wrapper
      .findAll('.editable-copy-document-nav-item')
      .find((node) => node.text().includes('长期 3 条 · 临时 2 条'))
    expect(orderGroupNavItem).toBeTruthy()
    await orderGroupNavItem!.trigger('click')
    await nextTick()

    expect(wrapper.find('.editable-copy-order-type-switch').text()).toContain('长期医嘱')
    expect(wrapper.find('.editable-copy-order-type-switch').text()).toContain('临时医嘱')
    expect(wrapper.find('.editable-copy-order-table').text()).toContain('开始时间')
    expect(wrapper.find('.editable-copy-order-table').text()).toContain('医嘱类型')
    expect(wrapper.find('.editable-copy-order-table').text()).toContain('医嘱项目')
    expect(wrapper.find('.editable-copy-order-table').text()).toContain('停止时间')
    expect(wrapper.find('.editable-copy-order-table').text()).toContain('医嘱状态')

    expect(wrapper.find('.editable-copy-order-type-switch button.is-active').text()).toBe(
      '临时医嘱',
    )
    const temporaryOrderText = wrapper.find('.editable-copy-order-table tbody').text()
    expect(temporaryOrderText).toContain('2026-06-02 16:30:00')
    expect(temporaryOrderText).toContain('头孢曲松')
    expect(temporaryOrderText).toContain('氨溴索注射液')
    expect(temporaryOrderText).not.toContain('II级护理')
    expect(temporaryOrderText).not.toContain('长期')

    const longOrderButton = wrapper
      .findAll('.editable-copy-order-type-switch button')
      .find((node) => node.text() === '长期医嘱')
    expect(longOrderButton).toBeTruthy()
    await longOrderButton!.trigger('click')
    await nextTick()

    const longRows = wrapper.findAll('.editable-copy-order-table tbody tr')
    expect(longRows).toHaveLength(3)
    const longOrderText = wrapper.find('.editable-copy-order-table tbody').text()
    expect(longRows[0].text()).toContain('奥美拉唑')
    expect(longOrderText).toContain('II级护理')
    expect(longOrderText).toContain('护理')
    expect(longOrderText).toContain('大活络胶囊')
  })

  it('编辑副本保存并验证时只运行新测试病历和已选 LX0609 质控点', async () => {
    const wrapper = await mountView()

    await expandLuxianFamily(wrapper, '会诊质量')
    const lx020 = wrapper.find('input.luxian-rule-checkbox[value="LX0609-03-01-01"]')
    const lx021 = wrapper.find('input.luxian-rule-checkbox[value="LX0609-03-01-02"]')
    await lx020.setValue(true)
    await lx021.setValue(true)

    const copyAction = wrapper
      .findAll('.customer-sample-secondary-link')
      .find((node) => node.text() === '创建副本')
    expect(copyAction).toBeTruthy()
    await copyAction!.trigger('click')
    await flushPromises()

    const runButton = wrapper.findAll('button').find((node) => node.text() === '保存并验证')
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(createManualTestMedicalRecord).toHaveBeenCalledTimes(1)
    expect(createManualTestMedicalRecord.mock.calls[0][0].selected_rule_ids).toEqual([
      'LX0609-03-01-01',
      'LX0609-03-01-02',
    ])
    expect(runManualSamplePool).toHaveBeenCalledWith(
      'customer-created-test-records-v1',
      {
        ...buildRunIdentity('CUSTOMER_TEST_EDIT_COPY', {
          patientId: 'P_EDIT_COPY',
          sampleItemId: 'ct-edit-copy',
        }),
        max_parallel_records: 1,
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
        selected_rule_ids: ['LX0609-03-01-01', 'LX0609-03-01-02'],
      },
      { timeout: 90000 },
    )
  })

  it('0426真实样本池已关联但未同步时明确阻断而不静默发起验证', async () => {
    listManualSamplePools.mockResolvedValueOnce({
      success: true,
      data: {
        items: [
          buildPool({
            id: 'pool-0426',
            name: '0426',
            total_items: 1,
            matched_items: 1,
            ready_items: 0,
          }),
        ],
        total: 1,
        page: 1,
        page_size: 50,
      },
    })
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool({
          id: 'pool-0426',
          name: '0426',
          total_items: 1,
          matched_items: 1,
          ready_items: 0,
        }),
        items: [
          buildRecord({
            id: 'sample-item-0426-001',
            matched_visit_id: 'VISIT_0426_001',
            mr_no: '0426-001',
            patient_name: '0426样本患者',
            sync_status: 'missing',
            bundle_status: 'pending',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()

    await expandLuxianFamily(wrapper, '肿瘤病理')
    const lx013 = wrapper.find('input.luxian-rule-checkbox[value="LX0609-06-02-03"]')
    expect(lx013.exists()).toBe(true)
    await lx013.setValue(true)

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.warning).toHaveBeenCalledWith(
      '已选 1 份病历，完整范围未提交：尚未同步 1 份。请处理后重试',
    )
    expect(runManualSamplePool).not.toHaveBeenCalled()
    expect(lx013.element).toHaveProperty('checked', true)
    expect(recordCheckboxes[0].element).toHaveProperty('checked', true)
  })

  it('单病历选择多组规则时提交单任务，由引擎执行族并发调度', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool({ name: '泸县0609合成质控样本 v1' }),
        items: [
          buildRecord({
            id: 'sample-item-syn-001',
            matched_visit_id: 'LX0609_SYN_001',
            mr_no: 'LX0609_SYN_001',
            patient_name: '合成样本001',
            sync_status: 'synthetic_seeded',
            bundle_status: 'ready',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()

    const familyButtons = wrapper
      .findAll('button')
      .filter((node) => node.text().includes('选择本组'))
    expect(familyButtons.length).toBeGreaterThanOrEqual(2)
    await familyButtons[0].trigger('click')
    await familyButtons[1].trigger('click')

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledTimes(1)
    const submittedPayload = runManualSamplePool.mock.calls[0][1] as {
      max_parallel_records?: number
      selected_rule_ids?: string[]
      group_by_luxian_family?: boolean
    }
    expect(submittedPayload).toEqual(
      expect.objectContaining({
        max_parallel_records: 16,
        selected_rule_ids: [
          'LX0609-01-01-01',
          'LX0609-01-01-02',
          'LX0609-01-02-01',
          'LX0609-02-01-01',
          'LX0609-02-01-02',
          'LX0609-02-01-03',
          'LX0609-02-01-04',
          'LX0609-02-01-05',
          'LX0609-09-01-01',
          'LX0609-12-01-01',
          'LX0609-12-01-02',
        ],
      }),
    )
    expect(submittedPayload).not.toHaveProperty('group_by_luxian_family')
  })

  it('批量病历全选规则族时保留原有父子任务并发', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord(),
          buildRecord({ id: 'V002', matched_visit_id: 'V002', sample_item_ids: ['item-2'] }),
        ],
        total: 2,
        page: 1,
        page_size: 20,
      },
    })
    const allRuleIds = Object.keys(luxian0609RuleNames).sort()
    runManualSamplePool.mockResolvedValueOnce({
      success: true,
      data: {
        pool_id: 'pool-1',
        job_id: 'parent-job-1',
        job_kind: 'parent',
        child_job_ids: ['child-basic', 'child-tumor'],
        family_scopes: [
          { key: 'basic_timeliness', name: '基础时限', rule_ids: ['LX0609-01-01-01'] },
          { key: 'tumor_pathology', name: '肿瘤病理', rule_ids: ['LX0609-06-02-03'] },
        ],
        child_jobs: [
          {
            id: 'child-basic',
            rule_code: 'LX0609',
            rule_name: '基础时限',
            scope: 'running',
            status: 'queued',
            family_key: 'basic_timeliness',
            family_name: '基础时限',
            filters: { scoped_customer_rule_ids: ['LX0609-01-01-01'] },
          },
          {
            id: 'child-tumor',
            rule_code: 'LX0609',
            rule_name: '肿瘤病理',
            scope: 'running',
            status: 'queued',
            family_key: 'tumor_pathology',
            family_name: '肿瘤病理',
            filters: { scoped_customer_rule_ids: ['LX0609-06-02-03'] },
          },
        ],
        sample_item_count: 1,
        selected_record_count: 1,
        record_count: 1,
        rule_count: 59,
        customer_rule_count: 49,
        execution_rule_count: 59,
        selected_rule_ids: allRuleIds,
        scoped_customer_rule_ids: allRuleIds,
        record_ids: ['V001'],
        rule_ids: ['SC-023'],
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
        rule_set_name: '泸县0609质控点验证 v1',
      },
    })
    const wrapper = await mountView()
    await flushPromises()

    const selectAllButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('全选8个质控族'))
    expect(selectAllButton).toBeTruthy()
    await selectAllButton!.trigger('click')
    await nextTick()

    expect(wrapper.text()).toContain('当前将运行：全部 49 个质控点')
    expect(wrapper.text()).toContain('取消全部勾选')
    expect(wrapper.text()).toContain('已选 5/5')

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)
    await recordCheckboxes[1].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledTimes(1)
    const submittedPayload = runManualSamplePool.mock.calls[0][1] as {
      max_parallel_records?: number
      selected_rule_ids?: string[]
      group_by_luxian_family?: boolean
    }
    expect(submittedPayload.max_parallel_records).toBe(16)
    expect(submittedPayload.group_by_luxian_family).toBe(true)
    expect((submittedPayload.selected_rule_ids || []).sort()).toEqual(allRuleIds)
    expect(message.success).toHaveBeenCalledWith(
      expect.objectContaining({ content: '已创建泸县0609总任务，8 个质控族已并发入队' }),
    )
    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('parent-job-1')
    const statusBar = wrapper.find('[data-testid="customer-sample-qc-task-status"]')
    expect(statusBar.exists()).toBe(true)
    expect(statusBar.text()).toContain('最近质控任务')
    expect(statusBar.find('[data-testid="qc-task-view-result"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('child-basic')
    expect(wrapper.text()).not.toContain('child-tumor')
  })

  it('创建测试病历时带入当前已选 LX0609 质控点范围', async () => {
    const wrapper = await mountView()

    const familyButtons = wrapper
      .findAll('button')
      .filter((node) => node.text().includes('选择本组'))
    expect(familyButtons.length).toBeGreaterThanOrEqual(3)
    await familyButtons[2].trigger('click')
    await nextTick()

    const createButton = wrapper.find('.customer-sample-create-action')
    expect(createButton.exists()).toBe(true)
    await createButton.trigger('click')

    expect(routerPush).toHaveBeenLastCalledWith({
      name: 'WorkstationV4SyntheticCaseNew',
      query: {
        ruleIds: 'LX0609-06-01-02,LX0609-06-01-04,LX0609-06-01-05,LX0609-06-03-03,LX0609-06-03-04',
        ruleFamily: 'exam_lab',
      },
    })
  })

  it('选中范围包含不可执行病历时整体阻断并保留完整选择', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord(),
          buildRecord({
            id: 'V004',
            matched_visit_id: '',
            mr_no: '2250002',
            patient_name: '赵六',
            match_status: 'unmatched',
            sync_status: 'missing',
            bundle_status: 'pending',
          }),
        ],
        total: 2,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)
    await recordCheckboxes[1].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.warning).toHaveBeenCalledWith(
      '已选 2 份病历，完整范围未提交：未关联病历 1 份。请处理后重试',
    )
    expect(runManualSamplePool).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('1 份当前阻塞（不会缩小范围执行）')
  })

  it('匹配歧义与病历包未就绪时分别说明阻塞原因', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord({
            id: 'V-ambiguous',
            matched_visit_id: '',
            match_status: 'ambiguous',
            sync_status: 'missing',
            bundle_status: 'pending',
          }),
          buildRecord({
            id: 'V-bundle-pending',
            matched_visit_id: 'V002',
            match_status: 'matched',
            sync_status: 'synced',
            bundle_status: 'pending',
          }),
        ],
        total: 2,
        page: 1,
        page_size: 20,
      },
    })
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)
    await recordCheckboxes[1].setValue(true)
    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.warning).toHaveBeenCalledWith(
      '已选 2 份病历，完整范围未提交：匹配有歧义 1 份，病历包未就绪 1 份。请处理后重试',
    )
    expect(runManualSamplePool).not.toHaveBeenCalled()
  })

  it('发起验证成功后应自动打开结果抽屉并显示成功提示', async () => {
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始0609质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.success).toHaveBeenCalledWith(
      expect.objectContaining({
        content:
          '任务已创建，正在打开进度。luxian_0609_qc_v1 / 泸县0609质控点验证 v1，覆盖 1 条样本 / 1 份病历 / 5 条规则，并发 16 份病历',
      }),
    )
    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-2')
    expect(wrapper.find('.batch-result-drawer-stub').exists()).toBe(true)
  })

  it('切换到 SC 样本规则模式后应按 sc 模式提交', async () => {
    const wrapper = await mountView()

    const modeButton = wrapper.findAll('button').find((node) => node.text() === 'SC 样本规则模式')
    expect(modeButton).toBeTruthy()
    await modeButton!.trigger('click')

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始样本验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        ...buildRunIdentity('V001'),
        max_parallel_records: 16,
        validation_mode: 'sc',
        rule_set_key: '',
      },
      undefined,
    )
  })

  it('SC 全池运行不由前端跨页拼接病例三坐标', async () => {
    const wrapper = await mountView()
    const modeButton = wrapper.findAll('button').find((node) => node.text() === 'SC 样本规则模式')
    await modeButton!.trigger('click')

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始样本验证'))
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        max_parallel_records: 16,
        validation_mode: 'sc',
        rule_set_key: '',
      },
      undefined,
    )
  })

  it('切换到硬门槛程序规则模式后应允许 bundle 未就绪但已同步病历提交', async () => {
    const wrapper = await mountView()

    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: {
          ...buildPool(),
          programmatic_items: 1,
        },
        items: [
          buildRecord({
            id: 'V008',
            matched_visit_id: 'V008',
            bundle_status: 'pending',
            sync_status: 'synced',
            coverage_types: ['programmatic'],
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })

    const modeButton = wrapper
      .findAll('button')
      .find((node) => node.text() === '硬门槛程序规则模式')
    expect(modeButton).toBeTruthy()
    await modeButton!.trigger('click')
    await flushPromises()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始样本验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        ...buildRunIdentity('V008'),
        max_parallel_records: 16,
        validation_mode: 'programmatic',
        rule_set_key: 'sample_programmatic_gate_v1',
      },
      undefined,
    )
  })

  it('切换到正式终末全量内涵 84 条后应按 sc_content_full_v1 提交且不要求 bundle ready', async () => {
    const wrapper = await mountView()

    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord({
            id: 'V084',
            matched_visit_id: 'V084',
            bundle_status: 'pending',
            sync_status: 'synced',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    runManualSamplePool.mockResolvedValueOnce({
      success: true,
      data: {
        pool_id: 'pool-1',
        job_id: 'job-84',
        sample_item_count: 1,
        selected_record_count: 1,
        record_count: 1,
        rule_count: 84,
        record_ids: ['V084'],
        rule_ids: ['SC-001'],
        validation_mode: 'formal_fast_screen_full',
        rule_set_key: 'sc_content_full_v1',
        rule_set_name: '内涵质控全量 v1',
      },
    })

    await selectRuleSet(wrapper, 'sc_content_full_v1')

    expect(wrapper.text()).toContain('SC 内涵质控全量 v1')
    expect(getManualSamplePoolRecords).toHaveBeenLastCalledWith(
      'pool-1',
      expect.objectContaining({
        include_in_batch_1: undefined,
      }),
    )

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始SC质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        ...buildRunIdentity('V084'),
        max_parallel_records: 16,
        validation_mode: 'formal_fast_screen_full',
        rule_set_key: 'sc_content_full_v1',
      },
      { timeout: 90000 },
    )
    expect(message.success).toHaveBeenCalledWith(
      expect.objectContaining({
        content:
          '任务已创建，正在打开进度。sc_content_full_v1 / 内涵质控全量 v1，覆盖 1 条样本 / 1 份病历 / 84 条规则，并发 16 份病历',
      }),
    )
  })

  it('正式84条未选择病历时禁用主按钮且不会提交整池', async () => {
    const wrapper = await mountView()

    await selectRuleSet(wrapper, 'sc_content_full_v1')

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('请先选择病历'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.warning).toHaveBeenCalledWith('请先选择要质控的病历')
    expect(runManualSamplePool).not.toHaveBeenCalled()
  })

  it('正式84条发起期间重复点击不会重复提交', async () => {
    let resolveRun: (value: unknown) => void = () => {}
    runManualSamplePool.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRun = resolve
      }),
    )

    const wrapper = await mountView()

    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord({
            id: 'V084',
            matched_visit_id: 'V084',
            bundle_status: 'pending',
            sync_status: 'synced',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })

    await selectRuleSet(wrapper, 'sc_content_full_v1')

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始SC质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await nextTick()
    await runButton!.trigger('click')

    expect(runManualSamplePool).toHaveBeenCalledTimes(1)
    expect(runButton!.attributes('disabled')).toBeDefined()

    resolveRun({
      success: true,
      data: {
        pool_id: 'pool-1',
        job_id: 'job-84',
        sample_item_count: 1,
        selected_record_count: 1,
        record_count: 1,
        rule_count: 84,
        record_ids: ['V084'],
        rule_ids: ['SC-001'],
        validation_mode: 'formal_fast_screen_full',
        rule_set_key: 'sc_content_full_v1',
        rule_set_name: '内涵质控全量 v1',
      },
    })
    await flushPromises()
  })

  it('正式84条请求超时后应按最近任务恢复并打开进度', async () => {
    const recoveredJob = {
      id: 'job-timeout',
      status: 'running',
      rule_set_key: 'sc_content_full_v1',
      record_ids: ['V084'],
      filters: {
        record_refs: buildRunIdentity('V084').record_refs,
      },
      created_at: new Date().toISOString(),
    }
    listManualSamplePools
      .mockResolvedValueOnce({
        success: true,
        data: { items: [buildPool()], total: 1, page: 1, page_size: 50 },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          items: [
            buildPool({
              latest_job_id: 'job-timeout',
              latest_job_status: 'running',
            }),
          ],
          total: 1,
          page: 1,
          page_size: 50,
        },
      })
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [buildRecord()],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })
    getSichuanWorkspaceBatchJob
      .mockResolvedValueOnce({ success: true, data: recoveredJob })
      .mockResolvedValueOnce({ success: true, data: recoveredJob })
    runManualSamplePool.mockResolvedValueOnce({
      success: false,
      message: '创建客户样本验证任务失败',
      errorType: 'timeout',
    })

    const wrapper = await mountView()

    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord({
            id: 'V084',
            matched_visit_id: 'V084',
            bundle_status: 'pending',
            sync_status: 'synced',
          }),
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })

    await selectRuleSet(wrapper, 'sc_content_full_v1')

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('开始SC质控'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        ...buildRunIdentity('V084'),
        max_parallel_records: 16,
        validation_mode: 'formal_fast_screen_full',
        rule_set_key: 'sc_content_full_v1',
      },
      { timeout: 90000 },
    )
    expect(message.info).toHaveBeenCalledWith('请求等待较久，正在确认后台任务状态')
    expect(message.success).toHaveBeenCalledWith(
      expect.objectContaining({ content: '任务已创建，正在执行质控' }),
    )
    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-timeout')
    expect(message.error).not.toHaveBeenCalledWith('创建客户样本验证任务失败')
    expect(wrapper.find('.batch-result-drawer-stub').exists()).toBe(true)
  })

  it('程序规则模式同步样本病历时不再限制内涵和首批', async () => {
    const wrapper = await mountView()

    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: {
          ...buildPool(),
          programmatic_items: 1,
        },
        items: [buildRecord({ coverage_types: ['programmatic'] })],
        total: 1,
        page: 1,
        page_size: 20,
      },
    })

    const modeButton = wrapper
      .findAll('button')
      .find((node) => node.text() === '硬门槛程序规则模式')
    expect(modeButton).toBeTruthy()
    await modeButton!.trigger('click')
    await flushPromises()

    const syncButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('同步样本病历'))
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    expect(syncManualSamplePoolRecords).toHaveBeenLastCalledWith('pool-1', {
      only_intrinsic: false,
      include_in_batch_1: false,
    })
  })

  it('正式终末全量内涵 84 条同步样本病历时不限制内涵和首批', async () => {
    const wrapper = await mountView()

    await selectRuleSet(wrapper, 'sc_content_full_v1')

    const syncButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('同步样本病历'))
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')
    await flushPromises()

    expect(syncManualSamplePoolRecords).toHaveBeenLastCalledWith('pool-1', {
      only_intrinsic: false,
      include_in_batch_1: false,
    })
  })

  it('停止当前任务成功后立即重跑会创建新任务，不复用已取消任务', async () => {
    runManualSamplePool
      .mockResolvedValueOnce({
        success: true,
        data: {
          pool_id: 'pool-1',
          job_id: 'job-canceled',
          sample_item_count: 1,
          record_count: 1,
          rule_count: 5,
          rule_set_key: 'luxian_0609_qc_v1',
          rule_set_name: '泸县0609质控点验证 v1',
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          pool_id: 'pool-1',
          job_id: 'job-new',
          sample_item_count: 1,
          record_count: 1,
          rule_count: 5,
          rule_set_key: 'luxian_0609_qc_v1',
          rule_set_name: '泸县0609质控点验证 v1',
        },
      })
    getSichuanWorkspaceBatchJob.mockImplementation(async (jobId: string) => ({
      success: true,
      data: {
        id: jobId,
        status: jobId === 'job-canceled' ? 'running' : 'queued',
      },
    }))
    cancelSichuanWorkspaceBatchJob.mockResolvedValueOnce({
      success: true,
      data: { id: 'job-canceled', status: 'canceled' },
    })

    const wrapper = await mountView()
    const checkbox = wrapper.findAll('input.record-checkbox')[0]
    await checkbox.setValue(true)
    await nextTick()

    const firstRunButton = wrapper
      .get('[data-testid="customer-sample-work-dock"]')
      .findAll('button')
      .find((node) => node.text() === '开始质控')
    expect(firstRunButton).toBeTruthy()
    await firstRunButton!.trigger('click')
    await flushPromises()

    const cancelButton = wrapper.find('[data-testid="qc-task-cancel"]')
    expect(cancelButton.exists()).toBe(true)
    await cancelButton.trigger('click')
    await flushPromises()
    expect(cancelSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-canceled')

    await checkbox.setValue(true)
    await nextTick()
    const rerunButton = wrapper
      .get('[data-testid="customer-sample-work-dock"]')
      .findAll('button')
      .find((node) => node.text() === '开始质控')
    expect(rerunButton).toBeTruthy()
    await rerunButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledTimes(2)
    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-new')
    expect(message.info).not.toHaveBeenCalledWith('任务已创建，正在执行质控')
  })

  it('停止任务失败时保留去重状态，不会误发新的重复任务', async () => {
    runManualSamplePool.mockResolvedValueOnce({
      success: true,
      data: {
        pool_id: 'pool-1',
        job_id: 'job-still-running',
        sample_item_count: 1,
        record_count: 1,
        rule_count: 5,
        rule_set_key: 'luxian_0609_qc_v1',
        rule_set_name: '泸县0609质控点验证 v1',
      },
    })
    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { id: 'job-still-running', status: 'running' },
    })
    cancelSichuanWorkspaceBatchJob.mockResolvedValueOnce({
      success: false,
      message: '停止任务失败',
    })

    const wrapper = await mountView()
    const checkbox = wrapper.findAll('input.record-checkbox')[0]
    await checkbox.setValue(true)
    await nextTick()
    const runButton = wrapper
      .get('[data-testid="customer-sample-work-dock"]')
      .findAll('button')
      .find((node) => node.text() === '开始质控')
    await runButton!.trigger('click')
    await flushPromises()

    await wrapper.find('[data-testid="qc-task-cancel"]').trigger('click')
    await flushPromises()
    expect(message.error).toHaveBeenCalledWith('停止任务失败')

    await checkbox.setValue(true)
    await nextTick()
    const rerunButton = wrapper
      .get('[data-testid="customer-sample-work-dock"]')
      .findAll('button')
      .find((node) => node.text() === '开始质控')
    await rerunButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledTimes(1)
    expect(message.info).toHaveBeenCalledWith('任务已创建，正在执行质控')
  })

  it('创建质控任务时在底部工作条显示清晰进度，完成后自动隐藏', async () => {
    let resolveRun: (value: unknown) => void = () => {}
    runManualSamplePool.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveRun = resolve
      }),
    )

    const wrapper = await mountView()
    await wrapper.findAll('input.record-checkbox')[0].setValue(true)
    await nextTick()
    const runButton = wrapper
      .get('[data-testid="customer-sample-work-dock"]')
      .findAll('button')
      .find((node) => node.text() === '开始质控')
    await runButton!.trigger('click')
    await nextTick()

    const workDock = wrapper.get('[data-testid="customer-sample-work-dock"]')
    expect(workDock.text()).toContain('正在创建质控任务')
    expect(workDock.text()).toContain('任务创建完成后将自动显示实时执行进度')
    expect(workDock.text()).toContain('正在创建…')

    resolveRun({
      success: true,
      data: {
        pool_id: 'pool-1',
        job_id: 'job-created',
        sample_item_count: 1,
        record_count: 1,
        rule_count: 5,
        rule_set_key: 'luxian_0609_qc_v1',
        rule_set_name: '泸县0609质控点验证 v1',
      },
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('正在创建质控任务')
  })
  describe('病历池说明句统计口径', () => {
    const modes = [
      ['luxian_0609_qc_v1', '，可按全量或选定 LX0609 质控点发起验证。'],
      ['sc_content_full_v1', '、已同步 20 份。'],
      ['sc_sample_running_v1', '，文书已就绪 20 份。'],
    ]

    it.each(modes)('%s 分页时明确显示本页数量', async (ruleSetKey, suffix) => {
      listManualSampleValidationRuleSets.mockResolvedValue({
        success: true,
        data: {
          items: buildRuleSets().map((rule) => ({
            ...rule,
            advanced: false,
            display_group: 'main',
          })),
        },
      })
      getManualSamplePoolRecords.mockResolvedValue({
        success: true,
        data: {
          pool: buildPool(),
          items: Array.from({ length: 20 }, (_, index) =>
            buildRecord({
              id: 'scope-' + index,
              matched_visit_id: 'scope-' + index,
            }),
          ),
          total: 27,
          page: 1,
          page_size: 20,
        },
      })
      const wrapper = await mountView()
      await selectRuleSet(wrapper, ruleSetKey)
      expect(wrapper.text()).toContain('共 27 份病历；本页 20 份中已关联 20 份' + suffix)
    })

    it.each(modes)('%s 本页即全部时保持原说明句', async (ruleSetKey, suffix) => {
      listManualSampleValidationRuleSets.mockResolvedValue({
        success: true,
        data: {
          items: buildRuleSets().map((rule) => ({
            ...rule,
            advanced: false,
            display_group: 'main',
          })),
        },
      })
      getManualSamplePoolRecords.mockResolvedValue({
        success: true,
        data: {
          pool: buildPool(),
          items: Array.from({ length: 20 }, (_, index) =>
            buildRecord({
              id: 'scope-' + index,
              matched_visit_id: 'scope-' + index,
            }),
          ),
          total: 20,
          page: 1,
          page_size: 20,
        },
      })
      const wrapper = await mountView()
      await selectRuleSet(wrapper, ruleSetKey)
      expect(wrapper.text()).toContain('共 20 份病历；其中已关联 20 份' + suffix)
      expect(wrapper.text()).not.toContain('本页 20 份中')
    })
  })
})
