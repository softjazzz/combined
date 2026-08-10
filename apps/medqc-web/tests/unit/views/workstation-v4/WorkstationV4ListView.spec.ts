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
    showQualityColumns: {
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
  },
  setup(_props, { attrs, slots }) {
    return () => h('div', attrs, slots.default?.())
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
      hospFilter: 'all',
      hospOptions: [
        { value: 'all', label: '全部住院状态' },
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
        InboxOutlined: true,
        SearchOutlined: true,
      },
    },
  })
}

describe('WorkstationV4ListView filters', () => {
  it('uses the full-scope canonical summary for record-pool KPI instead of page rows', () => {
    const wrapper = mountListView({
      workbenchRows: [],
      displayServerTotal: 1,
    })

    expect(wrapper.text()).toContain('已完成质控')
    expect(wrapper.text()).toContain('8')
    expect(wrapper.text()).toContain('确定问题')
    expect(wrapper.text()).toContain('6')
    expect(wrapper.text()).toContain('资料待补')
    expect(wrapper.text()).toContain('4')
    expect(wrapper.findAll('.wv4-analysis-kpi-card')).toHaveLength(4)
    expect(wrapper.text()).not.toContain('结果校验异常')
    expect(wrapper.text()).not.toContain('当前正在处理中的病历数')
  })

  it('passes the source and canonical result state to the record-pool table without treating unknown as ready', () => {
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
    expect(table.props('showQualityColumns')).toBe(true)
    expect(table.props('rows')[0]).toMatchObject({
      sourceState: { status: 'unknown' },
      latestQcSummary: { status: 'not_run' },
    })
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

  it('shows the current hospital status and emits a server-side filter change for the record pool', async () => {
    const wrapper = mountListView({ hospFilter: 'inpatient' })

    const hospitalSelect = wrapper.find('select.workbench-hosp-select')
    expect(hospitalSelect.exists()).toBe(true)
    expect((hospitalSelect.element as HTMLSelectElement).value).toBe('inpatient')

    await hospitalSelect.setValue('discharged')

    expect(wrapper.emitted('selectHospFilter')?.[0]).toEqual(['discharged'])
  })

  it('does not render the hospital-status filter for a stage queue', () => {
    const wrapper = mountListView({
      currentStageFilter: 'frontpage_generate',
      isStageQueueMode: true,
    })

    expect(wrapper.find('select.workbench-hosp-select').exists()).toBe(false)
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
})
