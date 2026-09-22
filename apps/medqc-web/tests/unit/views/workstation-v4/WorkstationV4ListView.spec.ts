import { defineComponent, h } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import WorkstationV4ListView from '@/views/workstation-v4/components/WorkstationV4ListView.vue'

const SelectStub = defineComponent({
  name: 'ASelect',
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  emits: ['update:value'],
  setup(props, { attrs, emit, slots }) {
    return () =>
      h(
        'select',
        {
          ...attrs,
          value: props.value,
          onChange: (event: Event) => {
            emit('update:value', (event.target as HTMLSelectElement).value)
          },
        },
        slots.default?.(),
      )
  },
})

const SelectOptionStub = defineComponent({
  name: 'ASelectOption',
  props: {
    value: {
      type: String,
      required: true,
    },
  },
  setup(props, { slots }) {
    return () => h('option', { value: props.value }, slots.default?.())
  },
})

const SegmentedStub = defineComponent({
  name: 'ASegmented',
  props: {
    value: {
      type: String,
      default: '',
    },
    options: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () =>
      h(
        'select',
        {
          ...attrs,
          value: props.value,
          onChange: (event: Event) => {
            emit('update:value', (event.target as HTMLSelectElement).value)
          },
        },
        (props.options as Array<{ value: string; label: string }>).map((option) =>
          h('option', { value: option.value }, option.label),
        ),
      )
  },
})

const passthroughStub = (name: string, tag = 'div') =>
  defineComponent({
    name,
    setup(_props, { attrs, slots }) {
      return () => h(tag, attrs, slots.default?.())
    },
  })

const BatchTablePanelStub = defineComponent({
  name: 'BatchTablePanel',
  props: {
    rows: {
      type: Array,
      default: () => [],
    },
    recordPoolMode: {
      type: Boolean,
      default: false,
    },
    showSelection: {
      type: Boolean,
      default: false,
    },
    showPrimaryAction: {
      type: Boolean,
      default: false,
    },
    primaryActionLabel: {
      type: String,
      default: '',
    },
    primaryActionLoading: {
      type: Boolean,
      default: false,
    },
    showFilterQcAction: {
      type: Boolean,
      default: false,
    },
    filterQcCount: {
      type: Number,
      default: 0,
    },
    filterQcLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['filter-qc', 'update:selectedRowKeys', 'batch-extract', 'open-record'],
  setup(_props, { attrs, slots }) {
    return () =>
      h('div', attrs, [
        h(
          'div',
          { 'data-testid': 'batch-table-toolbar-actions-slot' },
          slots['toolbar-actions']?.(),
        ),
        h('div', { 'data-testid': 'batch-table-task-status-slot' }, slots['task-status']?.()),
      ])
  },
})

function mountListView(overrides: Record<string, unknown> = {}) {
  return shallowMount(WorkstationV4ListView, {
    props: {
      activePriorityGroup: 'all',
      priorityGroups: [],
      priorityCardsFiltered: [],
      isStageQueueMode: false,
      searchText: '',
      dateRange: ['2026-05-25', '2026-05-27'],
      dateField: 'visit',
      departmentSelectOptions: [
        { name: '全部科室', total: 100, warningCount: 0 },
        { name: '中医科', total: 19, warningCount: 0 },
      ],
      quickDepartments: [
        { name: '全部科室', total: 100, warningCount: 0 },
        { name: '中医科', total: 19, warningCount: 0 },
      ],
      activeDept: '全部科室',
      doctorSelectOptions: [
        { name: '全部主管医师', total: 100 },
        { name: '陈医师', total: 19 },
      ],
      activeDoctor: '全部主管医师',
      hospFilter: 'all',
      syncScope: 'all',
      inpatientSort: 'default',
      hospitalizationStatusVerifying: false,
      hospOptions: [
        { value: 'all', label: '全部病历' },
        { value: 'inpatient', label: '在院' },
        { value: 'discharged', label: '已出院' },
      ],
      workbenchRows: [],
      selectedWorkbenchKeys: [],
      tableSummaryText: '当前筛选：中医科 / 入出院日期 2026-05-25 至 2026-05-27 / 共 19 份',
      displayLoading: false,
      batchActionLoading: false,
      stageMeta: {
        batchActionText: '批量处理',
        singleActionText: '处理',
        tableTitle: '病历池',
      },
      currentStageFilter: '',
      listRecords: [],
      stageEmptyText: '暂无数据',
      displayServerTotalPages: 1,
      currentPage: 1,
      pageSize: 20,
      displayServerTotal: 19,
      qcSummary: {
        totalRecords: 19,
        readyRecords: 8,
        notRunRecords: 10,
        technicalErrorRecords: 1,
        statusCounts: {
          compliant: 240,
          non_compliant: 6,
          data_gap: 4,
        },
        runningState: 'unknown',
      },
      recordPoolQcTask: null,
      loadError: false,
      ...overrides,
    },
    global: {
      stubs: {
        PriorityLane: passthroughStub('PriorityLane'),
        BatchTablePanel: BatchTablePanelStub,
        ACard: passthroughStub('ACard'),
        AInput: passthroughStub('AInput'),
        AButton: passthroughStub('AButton', 'button'),
        ARangePicker: passthroughStub('ARangePicker'),
        AProgress: passthroughStub('AProgress'),
        ATabs: passthroughStub('ATabs'),
        ATabPane: passthroughStub('ATabPane'),
        ASelect: SelectStub,
        ASelectOption: SelectOptionStub,
        ASegmented: SegmentedStub,
        FrontpageTenderValidationDrawer: defineComponent({
          name: 'FrontpageTenderValidationDrawer',
          props: {
            open: {
              type: Boolean,
              default: false,
            },
          },
          setup(props) {
            return () => h('div', { 'data-testid': 'frontpage-tender-drawer', open: props.open })
          },
        }),
        RecordPoolQcTaskHistory: defineComponent({
          name: 'RecordPoolQcTaskHistory',
          setup() {
            return () =>
              h('button', { 'data-testid': 'record-pool-qc-task-history-entry' }, '最近质控任务')
          },
        }),
        InboxOutlined: true,
        SearchOutlined: true,
      },
    },
  })
}

describe('WorkstationV4ListView filters', () => {
  it('keeps QC result metrics and redundant subtitles out of the record pool', () => {
    const wrapper = mountListView({
      workbenchRows: [],
      displayServerTotal: 1,
    })

    expect(wrapper.find('.wv4-analysis-overview__subtitle').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('已完成质控')
    expect(wrapper.text()).not.toContain('确定问题')
    expect(wrapper.text()).not.toContain('资料待补')
    expect(wrapper.findAll('.wv4-analysis-kpi-card')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('结果校验异常')
    expect(wrapper.text()).not.toContain('当前正在处理中的病历数')
  })

  it('renders the record-pool header and filters as one accessible workbench surface', () => {
    const wrapper = mountListView()

    const surface = wrapper.find('.wv4-record-pool-hero')
    expect(surface.attributes('aria-labelledby')).toBe('workstation-list-overview-title')
    expect(surface.find('#workstation-list-overview-title').text()).toBe('病历池')
    expect(surface.find('.workbench-dept-filter__count').exists()).toBe(false)
    expect(surface.findAll('.workbench-dept-select__count')).toHaveLength(0)
    expect(surface.find('#record-pool-dept-label').text()).toBe('科室')
    expect(surface.find('#record-pool-doctor-label').text()).toBe('主管医师')
    expect(surface.find('#record-pool-date-label').text()).toBe('入出院日期')
    expect(wrapper.classes()).toContain('record-pool-refined')
    expect(surface.find('.wv4-record-pool-filter__notice').exists()).toBe(false)
    expect(surface.find('.wv4-record-pool-filter__summary').text()).toContain('当前筛选')
    expect(
      surface.find('.workbench-hosp-filter .wv4-record-pool-filter__sync-shortcut').exists(),
    ).toBe(true)
    expect(
      surface
        .find('.wv4-analysis-overview__header .wv4-record-pool-filter__sync-shortcut')
        .exists(),
    ).toBe(false)
  })

  it('uses the compact record-pool table instead of quality-result columns', () => {
    const wrapper = mountListView({
      workbenchRows: [
        {
          id: 'record-1',
          patientName: '患者甲',
          visitId: 'V-1',
          department: '内科',
          stageStatus: '待处理',
          riskReason: '',
          updatedAt: '2026-08-08',
          isDemo: false,
          sourceState: { status: 'unknown', lastSyncAt: null, reasonCode: null },
          latestQcSummary: { status: 'not_run' },
        },
      ],
    })

    const table = wrapper.findComponent({ name: 'BatchTablePanel' })
    expect(table.props('recordPoolMode')).toBe(true)
  })

  it('enables triple-identity selection and the selected-record QC action in the formal record pool', () => {
    const wrapper = mountListView({
      selectedWorkbenchKeys: ['["H-1","P-1","V-1"]', '["H-2","P-2","V-2"]'],
      batchActionLoading: true,
    })

    const table = wrapper.findComponent({ name: 'BatchTablePanel' })
    expect(table.props('showSelection')).toBe(true)
    expect(table.props('showPrimaryAction')).toBe(true)
    expect(table.props('primaryActionLabel')).toBe('质控所选（2）')
    expect(table.props('primaryActionLoading')).toBe(true)
    expect(table.props('showFilterQcAction')).toBe(true)
    expect(table.props('filterQcCount')).toBe(19)
    expect(table.props('filterQcLoading')).toBe(true)
  })

  it('shows the persistent task progress inside the visible batch toolbar surface', () => {
    const task = {
      id: 'job-1',
      rule_code: 'LX0609',
      rule_name: '泸县0609质控',
      scope: 'all',
      status: 'running',
      total_records: 4,
    }
    const wrapper = mountListView({ recordPoolQcTask: task })

    const table = wrapper.findComponent({ name: 'BatchTablePanel' })
    const statusBar = table.findComponent({ name: 'RecordPoolQcTaskStatusBar' })
    expect(statusBar.exists()).toBe(true)
    expect(statusBar.props('job')).toEqual(task)
  })

  it('keeps a persistent recent QC task entry in the record-pool toolbar', () => {
    const wrapper = mountListView()

    expect(wrapper.find('[data-testid="record-pool-qc-task-history-entry"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('最近质控任务')
  })

  it('forwards the full server-filter QC action from the record pool', async () => {
    const wrapper = mountListView()
    const table = wrapper.findComponent({ name: 'BatchTablePanel' })

    table.vm.$emit('filter-qc')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('filter-qc')).toHaveLength(1)
  })

  it('forwards cleared selection and selected-record tasks without changing identity keys', async () => {
    const recordKey = '["H-1","P-1","V-1"]'
    const wrapper = mountListView({ selectedWorkbenchKeys: [recordKey] })
    const table = wrapper.findComponent({ name: 'BatchTablePanel' })

    table.vm.$emit('update:selectedRowKeys', [])
    table.vm.$emit('batch-extract', [recordKey])
    table.vm.$emit('open-record', recordKey)
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:selectedRowKeys')).toEqual([[[]]])
    expect(wrapper.emitted('batch-extract')).toEqual([[[recordKey]]])
    expect(wrapper.emitted('open-record')).toEqual([[recordKey]])
    expect(wrapper.props('selectedWorkbenchKeys')).toEqual([recordKey])
  })

  it('keeps the stage queue batch action wording and selection behavior unchanged', () => {
    const wrapper = mountListView({
      currentStageFilter: 'frontpage_generate',
      isStageQueueMode: true,
      selectedWorkbenchKeys: ['stage-key'],
      stageMeta: {
        batchActionText: '批量生成',
        singleActionText: '生成',
        tableTitle: '参考首页生成队列',
      },
    })

    const table = wrapper.findComponent({ name: 'BatchTablePanel' })
    expect(table.props('showSelection')).toBe(true)
    expect(table.props('showPrimaryAction')).toBe(true)
    expect(table.props('primaryActionLabel')).toBe('批量生成')
    expect(table.props('showFilterQcAction')).toBe(false)
    expect(table.props('recordPoolMode')).toBe(false)
  })

  it('renders a customer-facing query failure state', () => {
    const wrapper = mountListView({ loadError: true })

    expect(wrapper.find('[role="alert"]').text()).toContain('病历池暂未加载成功')
  })

  it('renders filter summary text', () => {
    const wrapper = mountListView()

    expect(wrapper.text()).toContain('当前筛选：中医科')
    expect(wrapper.text()).toContain('共 19 份')
  })

  it('does not render qc agent entry on list view', () => {
    const wrapper = mountListView()

    expect(wrapper.find('[data-testid="qc-agent-entry"]').exists()).toBe(false)
  })

  it('emits selectDept when searchable department select changes', async () => {
    const wrapper = mountListView()

    await wrapper.find('select.workbench-dept-select').setValue('中医科')

    expect(wrapper.emitted('selectDept')?.[0]).toEqual(['中医科'])
  })

  it('shows a searchable attending physician selector and emits a server-side filter change', async () => {
    const wrapper = mountListView({ activeDoctor: '陈医师' })

    const doctorSelect = wrapper.find('select.workbench-doctor-select')
    expect(doctorSelect.exists()).toBe(true)
    expect((doctorSelect.element as HTMLSelectElement).value).toBe('陈医师')

    await doctorSelect.setValue('全部主管医师')

    expect(wrapper.emitted('selectDoctor')?.[0]).toEqual(['全部主管医师'])
  })

  it('shows the current hospital status and emits a server-side filter change for the record pool', async () => {
    const wrapper = mountListView({ hospFilter: 'inpatient' })

    const statusFilter = wrapper.find('.workbench-hosp-filter')
    expect(statusFilter.attributes('aria-label')).toBe('住院状态筛选')
    expect(statusFilter.text()).toContain('住院状态')
    expect(statusFilter.text()).toContain('全部病历')
    expect(statusFilter.text()).toContain('在院')
    expect(statusFilter.text()).toContain('已出院')

    const hospitalSelect = wrapper.find('select.workbench-hosp-segmented')
    expect(hospitalSelect.exists()).toBe(true)
    expect((hospitalSelect.element as HTMLSelectElement).value).toBe('inpatient')

    await hospitalSelect.setValue('discharged')

    expect(wrapper.emitted('selectHospFilter')?.[0]).toEqual(['discharged'])
  })

  it('offers a dedicated lightweight verification shortcut for patients still hospitalized today', async () => {
    const wrapper = mountListView({
      syncScope: 'today_inpatient',
      dateField: 'admission',
    })
    const shortcut = wrapper.find('.wv4-record-pool-filter__sync-shortcut')

    expect(shortcut.text()).toContain('当日在院 · 已核验')
    expect(wrapper.find('#record-pool-date-label').text()).toBe('入院日期')
    await shortcut.trigger('click')
    expect(wrapper.emitted('toggleTodayInpatient')).toHaveLength(1)
  })

  it('shows server-side admission sorting only for inpatient records', async () => {
    const wrapper = mountListView({ hospFilter: 'inpatient', inpatientSort: 'longest' })
    const sortSelect = wrapper.find('select.wv4-record-pool-filter__inpatient-sort')

    expect(sortSelect.exists()).toBe(true)
    expect((sortSelect.element as HTMLSelectElement).value).toBe('longest')
    expect(sortSelect.text()).toContain('住院最久优先')

    await sortSelect.setValue('recent')
    expect(wrapper.emitted('selectInpatientSort')?.[0]).toEqual(['recent'])

    await wrapper.setProps({ hospFilter: 'discharged', syncScope: 'all' })
    expect(wrapper.find('select.wv4-record-pool-filter__inpatient-sort').exists()).toBe(false)
  })

  it('does not render the hospital-status filter for a stage queue', () => {
    const wrapper = mountListView({
      currentStageFilter: 'frontpage_generate',
      isStageQueueMode: true,
    })

    expect(wrapper.find('.workbench-hosp-filter').exists()).toBe(false)
    expect(wrapper.find('select.workbench-doctor-select').exists()).toBe(false)
  })

  it('opens tender field validation drawer from frontpage generate queue', async () => {
    const wrapper = mountListView({
      currentStageFilter: 'frontpage_generate',
      stageMeta: {
        batchActionText: '批量生成',
        singleActionText: '生成',
        tableTitle: '参考首页生成队列',
        pageTitle: '参考首页生成队列',
      },
    })

    await wrapper.find('[data-testid="frontpage-tender-validation-entry"]').trigger('click')

    expect(wrapper.find('[data-testid="frontpage-tender-drawer"]').attributes('open')).toBe('true')
    expect(wrapper.find('[data-testid="qc-agent-entry"]').exists()).toBe(false)
  })

  it('keeps the frontpage generation queue KPI on its own server total', () => {
    const wrapper = mountListView({
      currentStageFilter: 'frontpage_generate',
      displayServerTotal: 23,
    })

    expect(wrapper.text()).toContain('待生成总量')
    expect(wrapper.text()).toContain('23')
  })

  it('shows the analytics drill-down scope and lets the user exit it', async () => {
    const wrapper = mountListView({
      drilldownScopeParts: ['科室：ICU', '结果状态：确定问题'],
    })

    const scope = wrapper.get('[data-testid="workstation-drilldown-scope"]')
    expect(scope.text()).toContain('统计下钻范围')
    expect(scope.text()).toContain('科室：ICU')
    expect(scope.text()).toContain('结果状态：确定问题')

    await wrapper.get('[data-testid="workstation-clear-drilldown"]').trigger('click')

    expect(wrapper.emitted('clear-drilldown')).toHaveLength(1)
  })

  it('keeps the drill-down scope out of the header when no drill-down is active', () => {
    const wrapper = mountListView({ drilldownScopeParts: [] })

    expect(wrapper.find('[data-testid="workstation-drilldown-scope"]').exists()).toBe(false)
  })
})
