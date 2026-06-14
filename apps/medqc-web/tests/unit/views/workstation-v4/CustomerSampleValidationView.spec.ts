/* eslint-disable vue/one-component-per-file */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import CustomerSampleValidationView from '@/views/workstation-v4/CustomerSampleValidationView.vue'

const {
  message,
  listManualSamplePools,
  getSheet2ExactReviewAcceptancePackage,
  getLatestManualSamplePoolSyncJob,
  getManualSamplePoolSyncJob,
  getManualSamplePoolRecords,
  importManualSamplePoolByUpload,
  exportLuxian0609EvaluationReport,
  listManualSampleValidationRuleSets,
  matchManualSamplePool,
  runManualSamplePool,
  syncManualSamplePoolRecords,
  getSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
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
  },
  listManualSamplePools: vi.fn(),
  getSheet2ExactReviewAcceptancePackage: vi.fn(),
  getLatestManualSamplePoolSyncJob: vi.fn(),
  getManualSamplePoolSyncJob: vi.fn(),
  getManualSamplePoolRecords: vi.fn(),
  importManualSamplePoolByUpload: vi.fn(),
  exportLuxian0609EvaluationReport: vi.fn(),
  listManualSampleValidationRuleSets: vi.fn(),
  matchManualSamplePool: vi.fn(),
  runManualSamplePool: vi.fn(),
  syncManualSamplePoolRecords: vi.fn(),
  getSichuanWorkspaceBatchJob: vi.fn(),
  exportSichuanWorkspaceBatchJob: vi.fn(),
  writeFile: vi.fn(),
  bookNew: vi.fn(() => ({ sheets: [] })),
  aoaToSheet: vi.fn(() => ({})),
  bookAppendSheet: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message,
}))

vi.mock('@/services/manual-case-sample-service', () => ({
  listManualSamplePools,
  getSheet2ExactReviewAcceptancePackage,
  getLatestManualSamplePoolSyncJob,
  getManualSamplePoolSyncJob,
  getManualSamplePoolRecords,
  importManualSamplePoolByUpload,
  exportLuxian0609EvaluationReport,
  listManualSampleValidationRuleSets,
  matchManualSamplePool,
  runManualSamplePool,
  syncManualSamplePoolRecords,
}))

vi.mock('@/services/sichuan-rule-workspace-service', () => ({
  getSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
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
  },
  setup(props) {
    return () =>
      h('div', {
        class: 'batch-result-drawer-stub',
        'data-open': props.open ? 'true' : 'false',
        style: props.open ? '' : 'display:none;',
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
        'q-c-review-drawer': QCReviewDrawerStub,
        'semantic-rules-batch-result-drawer': SemanticRulesBatchResultDrawerStub,
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

describe('CustomerSampleValidationView', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:luxian-0609-report'),
      revokeObjectURL: vi.fn(),
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
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
    getLatestManualSamplePoolSyncJob.mockResolvedValue({ success: true, data: null })
    getManualSamplePoolSyncJob.mockResolvedValue({
      success: true,
      data: {
        id: 'sync-job-1',
        pool_id: 'pool-1',
        status: 'running',
        summary: { progress: { step_label: '正在同步', total_candidates: 2, eligible_visits: 2 } },
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
    getSichuanWorkspaceBatchJob.mockResolvedValue({
      success: true,
      data: { id: 'job-2', status: 'completed' },
    })
    exportSichuanWorkspaceBatchJob.mockResolvedValue({ success: true, data: new Blob() })
    exportLuxian0609EvaluationReport.mockResolvedValue({
      success: true,
      data: new Blob(['report']),
    })
  })

  it('默认选中泸县0609规则集并展示规则集摘要', async () => {
    const wrapper = await mountView()

    expect(listManualSampleValidationRuleSets).toHaveBeenCalled()
    expect(wrapper.text()).toContain('验证规则集')
    expect(wrapper.text()).toContain('泸县0609质控点验证 v1')
    expect(wrapper.text()).toContain('59')
    expect(wrapper.text()).toContain('场景 运行中病历')
    expect(wrapper.text()).toContain('闸门未过 3/9')
    expect(wrapper.text()).toContain('三类样本齐备 0')
    expect(wrapper.text()).toContain('误报 0')
    expect(wrapper.text()).toContain('漏报 0')
    expect(wrapper.text()).toContain('不可判定 0')
    expect(wrapper.text()).toContain('页面待闭环 4/8')
    expect(wrapper.text()).toContain('已达正式口径 6')
    expect(wrapper.text()).toContain('证据待补强 10')
    expect(wrapper.text()).toContain('跨文书待完善 14')
    expect(wrapper.text()).toContain('跨表联查待接入 15')
    expect(wrapper.text()).toContain('待实现规则 4')
  })

  it('规则集目录接口失败时使用内置 fallback', async () => {
    listManualSampleValidationRuleSets.mockResolvedValueOnce({
      success: false,
      message: 'rule sets unavailable',
    })

    const wrapper = await mountView()

    expect(wrapper.text()).toContain('泸县0609质控点验证 v1')
    expect(wrapper.text()).toContain('SC 内涵质控全量 v1')
    expect(wrapper.text()).toContain('内置目录')
  })

  it('可从更多操作导出泸县0609专项评估报告', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('导出泸县0609报告')
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

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起泸县0609验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        record_ids: ['V001'],
        max_parallel_records: 2,
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
      },
      undefined,
    )
    expect(message.success).toHaveBeenCalled()
  })

  it('客户样本复现模式未选择病历时保持整池提交行为', async () => {
    const wrapper = await mountView()

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起泸县0609验证'))
    expect(runButton).toBeTruthy()
    expect(runButton!.attributes('disabled')).toBeUndefined()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        record_ids: [],
        max_parallel_records: 4,
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
      },
      undefined,
    )
  })

  it('点击同步样本病历后展示同步进度区块', async () => {
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
    expect(wrapper.text()).toContain('样本病历同步进度')
    expect(wrapper.text()).toContain('正在同步')
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
              step_label: '正在同步病历文书',
              total_candidates: 3,
              eligible_visits: 2,
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
              step_label: '继续同步病历文书',
              total_candidates: 3,
              eligible_visits: 2,
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

    expect(wrapper.text()).toContain('1/3')
    expect(wrapper.text()).toContain('正在同步病历文书')

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(wrapper.text()).toContain('2/3')
    expect(wrapper.text()).toContain('继续同步病历文书')

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(getManualSamplePoolSyncJob).toHaveBeenCalledTimes(3)
    expect(listManualSamplePools.mock.calls.length).toBeGreaterThan(initialPoolCalls)
    expect(getManualSamplePoolRecords.mock.calls.length).toBeGreaterThan(initialRecordCalls)
  })

  it('支持下载简化后的客户样本导入模板', async () => {
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
    expect(aoaToSheet).toHaveBeenCalledWith([['住院号'], ['2248248'], ['161241']])
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
    expect(message.success).toHaveBeenCalledWith('导入成功，共写入 2 条样本')
    expect(wrapper.text()).toContain('当前样本池')
    expect(wrapper.text()).toContain('第二轮样本池')
    expect(wrapper.text()).toContain('新患者')
  })

  it('点击查看病历后打开病历联审抽屉', async () => {
    const wrapper = await mountView()

    const reviewAction = [...wrapper.findAll('button'), ...wrapper.findAll('a')].find(
      (node) => node.text() === '查看病历',
    )
    expect(reviewAction).toBeTruthy()
    await reviewAction!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.qc-review-drawer-stub').exists()).toBe(true)
  })

  it('点击查看结果后打开批量任务结果抽屉', async () => {
    const wrapper = await mountView()

    const resultLink = wrapper.findAll('a').find((node) => node.text() === '查看结果')
    expect(resultLink).toBeTruthy()
    await resultLink!.trigger('click')
    await flushPromises()

    expect(getSichuanWorkspaceBatchJob).toHaveBeenCalledWith('job-1')
    expect(wrapper.find('.batch-result-drawer-stub').exists()).toBe(true)
  })

  it('只选中不可执行病历时提示并阻止发起验证', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord({
            id: 'V003',
            matched_visit_id: 'V003',
            mr_no: '2250001',
            patient_name: '王五',
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

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起泸县0609验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.warning).toHaveBeenCalledWith(
      '当前选中的病历还未完成匹配、同步或 bundle 准备，暂时无法发起验证',
    )
    expect(runManualSamplePool).not.toHaveBeenCalled()
  })

  it('选中部分不可执行病历时仅提交可执行病历并提示跳过数量', async () => {
    getManualSamplePoolRecords.mockResolvedValueOnce({
      success: true,
      data: {
        pool: buildPool(),
        items: [
          buildRecord(),
          buildRecord({
            id: 'V004',
            matched_visit_id: 'V004',
            mr_no: '2250002',
            patient_name: '赵六',
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

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起泸县0609验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.info).toHaveBeenCalledWith('已选 2 份病历，其中 1 份可执行，1 份将自动跳过')
    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        record_ids: ['V001'],
        max_parallel_records: 4,
        validation_mode: 'customer',
        rule_set_key: 'luxian_0609_qc_v1',
      },
      undefined,
    )
  })

  it('发起验证成功后应自动打开结果抽屉并显示成功提示', async () => {
    const wrapper = await mountView()

    const recordCheckboxes = wrapper.findAll('input.record-checkbox')
    await recordCheckboxes[0].setValue(true)

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起泸县0609验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(message.success).toHaveBeenCalledWith(
      expect.objectContaining({
        content:
          '任务已创建，正在打开进度。luxian_0609_qc_v1 / 泸县0609质控点验证 v1，覆盖 1 条样本 / 1 份病历 / 5 条规则，并发 4 份病历',
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

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('发起样本验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        record_ids: ['V001'],
        max_parallel_records: 4,
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

    const runButton = wrapper.findAll('button').find((node) => node.text().includes('发起样本验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        record_ids: ['V008'],
        max_parallel_records: 4,
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

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起SC全量验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        record_ids: ['V084'],
        max_parallel_records: 4,
        validation_mode: 'formal_fast_screen_full',
        rule_set_key: 'sc_content_full_v1',
      },
      { timeout: 90000 },
    )
    expect(message.success).toHaveBeenCalledWith(
      expect.objectContaining({
        content:
          '任务已创建，正在打开进度。sc_content_full_v1 / 内涵质控全量 v1，覆盖 1 条样本 / 1 份病历 / 84 条规则，并发 4 份病历',
      }),
    )
  })

  it('正式84条未选择病历时禁用主按钮且不会提交整池', async () => {
    const wrapper = await mountView()

    await selectRuleSet(wrapper, 'sc_content_full_v1')

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('请选择病历后发起SC全量验证'))
    expect(runButton).toBeTruthy()
    expect(runButton!.attributes('disabled')).toBeDefined()
    await runButton!.trigger('click')
    await flushPromises()

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

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起SC全量验证'))
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

    const runButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('发起SC全量验证'))
    expect(runButton).toBeTruthy()
    await runButton!.trigger('click')
    await flushPromises()

    expect(runManualSamplePool).toHaveBeenCalledWith(
      'pool-1',
      {
        record_ids: ['V084'],
        max_parallel_records: 4,
        validation_mode: 'formal_fast_screen_full',
        rule_set_key: 'sc_content_full_v1',
      },
      { timeout: 90000 },
    )
    expect(message.info).toHaveBeenCalledWith('请求等待较久，正在确认后台任务状态')
    expect(message.success).toHaveBeenCalledWith(
      expect.objectContaining({ content: '任务已创建，正在打开进度' }),
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
})
