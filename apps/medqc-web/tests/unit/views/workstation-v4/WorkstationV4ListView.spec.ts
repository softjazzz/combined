import { defineComponent, h } from 'vue'
import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'

import { message } from 'ant-design-vue'
import { clinicalSourcesApi } from '@/api/clinicalSources'
import { ApiService, apiClient } from '@/services/apiService'
import * as currentMedicalRecordService from '@/services/current-medical-record'
import * as sichuanService from '@/services/sichuan-rule-workspace-service'
import CurrentMedicalRecordDrawer from '@/views/workstation-v4/components/CurrentMedicalRecordDrawer.vue'
import WorkstationV4ListView from '@/views/workstation-v4/components/WorkstationV4ListView.vue'
import WorkstationV4View from '@/views/workstation-v4/WorkstationV4View.vue'
import BatchTablePanel from '@/views/workstation-v4/components/workbench/BatchTablePanel.vue'
import RecordPoolPreviewPanel from '@/views/workstation-v4/components/workbench/RecordPoolPreviewPanel.vue'
import RecordPoolQcTaskHistory from '@/views/workstation-v4/components/workbench/RecordPoolQcTaskHistory.vue'
import { resetClinicalSourceOptionsCache } from '@/views/workstation-v4/composables/usePatientRecords'
import { resolveResultPresentation } from '@/views/workstation-v4/components/qc/latestQcSummaryPresentation'
import {
  runRecordPoolFilterQc,
  runRecordPoolQc,
} from '@/views/workstation-v4/workstationBatchController'
import type { PatientRecord } from '@/views/workstation-v4/types'

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
  emits: ['filter-qc', 'update:selectedRowKeys', 'batch-extract', 'open-record', 'select-row'],
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
      qcScopeTotal: 19,
      qcSummaryState: 'ready',
      recordPoolQcTask: null,
      loadError: false,
      ...overrides,
    },
    global: {
      stubs: {
        AAlert: false,
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

  it('列表失败时显示重试，后台摘要失败时保留病历池列表', async () => {
    const wrapper = mountListView({ loadError: true, qcSummaryState: 'unavailable', currentPage: 2 })
    const error = wrapper.get('[role="alert"]')

    expect(error.text()).toContain('病历列表加载失败')
    expect(error.text()).not.toContain('质控摘要暂不可用')
    await error.get('button').trigger('click')
    expect(wrapper.emitted('refresh')).toHaveLength(1)

    await wrapper.setProps({ loadError: false })
    expect(wrapper.get('[role="alert"]').text()).toContain('质控摘要暂不可用')
    expect(wrapper.findComponent({ name: 'BatchTablePanel' }).exists()).toBe(true)
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

  it('保留单边日期并允许清空日期范围', () => {
    const wrapper = mountListView()
    const picker = wrapper.getComponent({ name: 'ARangePicker' })
    picker.vm.$emit('update:value', ['2026-05-25', null])
    picker.vm.$emit('update:value', [null, '2026-05-27'])
    picker.vm.$emit('update:value', null)

    expect(wrapper.emitted('update:dateRange')).toEqual([
      [['2026-05-25', '']],
      [['', '2026-05-27']],
      [null],
    ])
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

  it('病历池为左列表 + 右预览：点击行切换预览，预览按钮沿用原有事件', async () => {
    const rows = [
      { id: 'a', recordKey: 'key-a', patientName: '患者甲', visitId: 'V-A' },
      { id: 'b', recordKey: 'key-b', patientName: '患者乙', visitId: 'V-B' },
    ]
    const wrapper = mountListView({ workbenchRows: rows })
    const preview = wrapper.findComponent({ name: 'RecordPoolPreviewPanel' })
    expect((preview.props('row') as { recordKey: string }).recordKey).toBe('key-a')

    wrapper.findComponent({ name: 'BatchTablePanel' }).vm.$emit('select-row', 'key-b')
    await wrapper.vm.$nextTick()
    expect((preview.props('row') as { recordKey: string }).recordKey).toBe('key-b')

    preview.vm.$emit('open-record', 'key-b')
    preview.vm.$emit('run-qc', 'key-b')
    expect(wrapper.emitted('open-record')?.at(-1)).toEqual(['key-b'])
    expect(wrapper.emitted('preview-run-qc')?.at(-1)).toEqual(['key-b'])
    expect(wrapper.emitted('batch-extract')).toBeUndefined()
  })

  it('首页与结算清单阶段队列不显示病历预览', () => {
    const wrapper = mountListView({ isStageQueueMode: true })
    expect(wrapper.findComponent({ name: 'RecordPoolPreviewPanel' }).exists()).toBe(false)
  })

  it('P0-1: blocks filter-QC with a warning when hospFilter is unknown or analytics drilldown is active', async () => {
    const unknownWrapper = mountListView({ hospFilter: 'unknown' })
    expect(unknownWrapper.findComponent({ name: 'BatchTablePanel' }).props('showFilterQcAction')).toBe(
      false,
    )
    expect(unknownWrapper.get('[data-testid="filter-qc-blocked-warning"]').text()).toContain(
      '状态未知',
    )
    expect(unknownWrapper.get('[data-testid="filter-qc-blocked-warning"]').text()).toContain(
      '质控所选',
    )

    const drilldownWrapper = mountListView({
      analyticsDrilldown: {
        ruleId: 'LX0609-01-01',
        scope: 'final',
        resultStatus: 'non_compliant',
      },
    })
    expect(
      drilldownWrapper.findComponent({ name: 'BatchTablePanel' }).props('showFilterQcAction'),
    ).toBe(false)
    expect(drilldownWrapper.get('[data-testid="filter-qc-blocked-warning"]').text()).toContain(
      '统计分析下钻',
    )
    expect(drilldownWrapper.get('[data-testid="filter-qc-blocked-warning"]').text()).toContain(
      '质控所选',
    )
  })

  it('wires RecordPoolQcTaskStatusBar results-updated/completed to refresh once per finished task', async () => {
    const task = {
      id: 'job-finish-1',
      rule_code: 'LX0609',
      rule_name: '泸县0609质控',
      scope: 'all' as const,
      status: 'running' as const,
      total_records: 2,
    }
    const wrapper = mountListView({ recordPoolQcTask: task })
    const statusBar = wrapper.findComponent({ name: 'RecordPoolQcTaskStatusBar' })
    expect(statusBar.exists()).toBe(true)

    statusBar.vm.$emit('results-updated')
    statusBar.vm.$emit('completed')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('refresh')).toHaveLength(1)

    await wrapper.setProps({ recordPoolQcTask: { ...task, id: 'job-finish-2' } })
    statusBar.vm.$emit('completed')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('refresh')).toHaveLength(2)
  })
})

describe('P0-1, P0-3, P0-4 & confirmedOnly contract regressions', () => {
  it('P0-4: returns 未质控 when summary is absent and summaryState is ready, only returning 暂不可用 when unavailable', () => {
    expect(resolveResultPresentation(undefined, 'ready')).toEqual({
      resultStatus: 'not-run',
      resultLabel: '未质控',
      issueSummary: '暂无结果',
      latestQcTime: '—',
    })
    expect(resolveResultPresentation(undefined, 'pending')).toEqual({
      resultStatus: 'unknown',
      resultLabel: '质控摘要加载中',
      issueSummary: '质控摘要加载中',
      latestQcTime: '—',
    })
    expect(resolveResultPresentation(undefined, 'unavailable')).toEqual({
      resultStatus: 'unknown',
      resultLabel: '质控摘要暂不可用',
      issueSummary: '质控摘要暂不可用',
      latestQcTime: '—',
    })
  })

  it('confirmedOnly hides non-confirmed and internal failure labels and shows only confirmed issues or neutral copy', () => {
    const withConfirmed = resolveResultPresentation(
      {
        status: 'ready',
        executionStatus: 'partial_failed',
        failedRuleCount: 2,
        totalRuleCount: 10,
        completedAt: '2026-08-08T01:20:00Z',
        statusCounts: { non_compliant: 3, data_gap: 2, uncertain: 1 },
      },
      'ready',
      { confirmedOnly: true },
    )
    expect(withConfirmed.resultStatus).toBe('priority')
    expect(withConfirmed.resultLabel).toBe('需优先复核')
    expect(withConfirmed.issueSummary).toBe('有 3 项确定问题')
    expect(withConfirmed.issueSummary).not.toContain('待核实')
    expect(withConfirmed.issueSummary).not.toContain('待判断')
    expect(withConfirmed.issueSummary).not.toContain('部分执行失败')

    const onlyDataGap = resolveResultPresentation(
      {
        status: 'ready',
        completedAt: '2026-08-08T01:20:00Z',
        statusCounts: { data_gap: 2, uncertain: 1 },
      },
      'ready',
      { confirmedOnly: true },
    )
    expect(onlyDataGap.resultStatus).toBe('completed')
    expect(onlyDataGap.resultLabel).toBe('已完成')
    expect(onlyDataGap.issueSummary).toBe('未发现确定问题')

    const failedNoConfirmed = resolveResultPresentation(
      {
        status: 'technical_error',
        failureStage: 'material_capture',
        completedAt: '2026-08-08T01:20:00Z',
      },
      'ready',
      { confirmedOnly: true },
    )
    expect(failedNoConfirmed.resultStatus).toBe('not-run')
    expect(failedNoConfirmed.resultLabel).toBe('未质控')
    expect(failedNoConfirmed.issueSummary).not.toContain('资料准备失败')
    expect(failedNoConfirmed.issueSummary).not.toContain('结果校验异常')
  })

  it('P0-1: runRecordPoolFilterQc refuses unknown hospital status and active analytics drilldown instead of falling back to all', async () => {
    const createSpy = vi
      .spyOn(sichuanService, 'createSichuanWorkspaceBatchJob')
      .mockResolvedValue({ success: true, data: { id: 'job-x', status: 'queued' } as never })
    const warnSpy = vi.spyOn(message, 'warning').mockImplementation(() => (() => undefined) as never)
    try {
      await runRecordPoolFilterQc({
        total: 12,
        hospitalStatus: 'unknown',
        syncScope: 'all',
        department: '全部科室',
        doctor: '全部主管医师',
        keyword: '',
        dateField: 'visit',
        dateRange: null,
        getBatchExtracting: () => false,
        setBatchExtracting: vi.fn(),
      })
      expect(createSpy).not.toHaveBeenCalled()
      expect(warnSpy).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining('状态未知') }),
      )

      warnSpy.mockClear()
      await runRecordPoolFilterQc({
        total: 12,
        hospitalStatus: 'discharged',
        syncScope: 'all',
        department: '全部科室',
        doctor: '全部主管医师',
        keyword: '',
        dateField: 'visit',
        dateRange: null,
        hasAnalyticsDrilldown: true,
        getBatchExtracting: () => false,
        setBatchExtracting: vi.fn(),
      })
      expect(createSpy).not.toHaveBeenCalled()
      expect(warnSpy).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining('统计分析下钻') }),
      )
    } finally {
      createSpy.mockRestore()
      warnSpy.mockRestore()
    }
  })

  it('P0-3: runRecordPoolQc with preserveSelection never clears or overwrites table checkboxes on success or error', async () => {
    const recordKey = '["H-1","P-1","V-1"]'
    const sampleRecord: PatientRecord = {
      id: 'V-1',
      recordKey,
      visitId: 'V-1',
      instituteId: 'H-1',
      patientId: 'P-1',
      bedNo: '',
      name: '患者甲',
      sex: '女',
      age: 40,
      insurance: '',
      department: '内科',
      admissionDate: '',
      dischargeDate: '',
      days: 0,
      diagnosis: '',
      diagnosisCode: '',
      doctor: '',
      status: 'pending',
    }
    const setSelectedWorkbenchKeys = vi.fn()
    const createSpy = vi
      .spyOn(sichuanService, 'createSichuanWorkspaceBatchJob')
      .mockResolvedValueOnce({
        success: true,
        data: { id: 'job-preview-1', status: 'queued' } as never,
      })
      .mockResolvedValueOnce({
        success: false,
        message: '服务繁忙',
      })
    const loadingSpy = vi.spyOn(message, 'loading').mockImplementation(() => (() => undefined) as never)
    const successSpy = vi.spyOn(message, 'success').mockImplementation(() => (() => undefined) as never)
    const errorSpy = vi.spyOn(message, 'error').mockImplementation(() => (() => undefined) as never)

    try {
      await runRecordPoolQc({
        keys: [recordKey],
        preserveSelection: true,
        getBatchExtracting: () => false,
        setBatchExtracting: vi.fn(),
        findBatchRecordByKey: () => sampleRecord,
        setSelectedWorkbenchKeys,
      })
      expect(setSelectedWorkbenchKeys).not.toHaveBeenCalled()

      await runRecordPoolQc({
        keys: [recordKey],
        preserveSelection: true,
        getBatchExtracting: () => false,
        setBatchExtracting: vi.fn(),
        findBatchRecordByKey: () => sampleRecord,
        setSelectedWorkbenchKeys,
      })
      expect(setSelectedWorkbenchKeys).not.toHaveBeenCalled()

      await runRecordPoolQc({
        keys: ['missing-key'],
        preserveSelection: true,
        getBatchExtracting: () => false,
        setBatchExtracting: vi.fn(),
        findBatchRecordByKey: () => null,
        setSelectedWorkbenchKeys,
      })
      expect(setSelectedWorkbenchKeys).not.toHaveBeenCalled()
    } finally {
      createSpy.mockRestore()
      loadingSpy.mockRestore()
      successSpy.mockRestore()
      errorSpy.mockRestore()
    }
  })
})

describe('Record pool UI polish, loading UX & accessibility regressions', () => {
  it('renders the record-pool heading as h1 with accessible aria-labels on search and select controls', () => {
    const wrapper = mountListView()
    const title = wrapper.get('#workstation-list-overview-title')
    expect(title.element.tagName).toBe('H1')
    expect(title.classes()).toContain('wv4-analysis-overview__title')
    expect(title.classes()).toContain('mq-page-title')

    expect(wrapper.get('.workbench-controls__search-input').attributes('aria-label')).toBe(
      '搜索患者、住院号、科室',
    )
    expect(wrapper.get('select.workbench-dept-select').attributes('aria-label')).toBe('科室筛选')
    expect(wrapper.get('select.workbench-doctor-select').attributes('aria-label')).toBe(
      '主管医师筛选',
    )
    expect(wrapper.get('select.workbench-hosp-segmented').attributes('aria-label')).toBe('住院状态')
  })

  it('provides a retry button on the qcSummary unavailable alert that emits refresh', async () => {
    const wrapper = mountListView({ loadError: false, qcSummaryState: 'unavailable' })
    const alert = wrapper.get('[role="alert"]')
    expect(alert.classes()).toContain('wv4-list__status-alert')
    expect(alert.classes()).toContain('wv4-list__status-alert--warning')

    const retryBtn = wrapper.get('[data-testid="retry-qc-summary"]')
    expect(retryBtn.text()).toBe('重试')
    await retryBtn.trigger('click')
    expect(wrapper.emitted('refresh')).toHaveLength(1)
  })

  it('shows title tooltips and crisp loading copy on RecordPoolPreviewPanel', () => {
    const wrapper = mount(RecordPoolPreviewPanel, {
      props: {
        row: {
          id: 'r-1',
          recordKey: 'k-1',
          patientName: '欧阳非常长患者姓名',
          visitId: 'VISIT_2026_VERY_LONG_0001',
          department: '心血管内科',
          stageStatus: '待处理',
          riskReason: '',
          updatedAt: '2026-08-08',
          isDemo: false,
        },
        qcLoading: true,
      },
    })

    expect(wrapper.get('.pool-preview__name').attributes('title')).toBe('欧阳非常长患者姓名')
    expect(wrapper.get('.pool-preview__visit').attributes('title')).toBe(
      '住院号 VISIT_2026_VERY_LONG_0001',
    )
    const qcButton = wrapper.get('[data-testid="record-pool-preview-qc"]')
    expect(qcButton.text()).toContain('创建中…')
    expect(qcButton.attributes('disabled')).toBeDefined()
    expect(qcButton.attributes('aria-busy')).toBe('true')
  })

  it('supports keyboard Enter/Space row preview selection, aria-current, non-focusable visit id, and crisp loading copy in BatchTablePanel', () => {
    const TableStub = defineComponent({
      name: 'ATable',
      props: {
        columns: { type: Array, default: () => [] },
        dataSource: { type: Array, default: () => [] },
      },
      setup(props, { slots }) {
        return () =>
          h(
            'div',
            { 'data-testid': 'table-stub' },
            (props.dataSource as Record<string, unknown>[]).flatMap((record) =>
              (props.columns as Array<Record<string, unknown>>).map((column) =>
                h('div', { 'data-column': String(column.key || '') }, [
                  slots.bodyCell?.({ column, record }),
                ]),
              ),
            ),
          )
      },
    })

    const wrapper = mount(BatchTablePanel, {
      props: {
        rows: [
          {
            id: 'r-1',
            recordKey: 'key-1',
            patientName: '患者甲',
            visitId: 'V-1',
            department: '内科',
            stageStatus: '待处理',
            riskReason: '',
            updatedAt: '2026-08-08',
            isDemo: false,
          },
          {
            id: 'r-2',
            recordKey: 'key-2',
            patientName: '患者乙',
            visitId: 'V-2',
            department: '外科',
            stageStatus: '待处理',
            riskReason: '',
            updatedAt: '2026-08-08',
            isDemo: false,
          },
        ],
        selectedRowKeys: ['key-1'],
        summaryText: '',
        recordPoolMode: true,
        activeRowKey: 'key-1',
        showPrimaryAction: true,
        primaryActionLabel: '质控所选（1）',
        primaryActionLoading: true,
        showFilterQcAction: true,
        filterQcCount: 19,
        filterQcLoading: true,
      },
      global: {
        stubs: {
          ATable: TableStub,
          AButton: passthroughStub('AButton', 'button'),
          APopconfirm: passthroughStub('APopconfirm'),
        },
      },
    })

    expect(wrapper.get('.batch-table-panel__visit-id').attributes('tabindex')).toBeUndefined()
    expect(wrapper.get('.batch-table-panel__action--primary').text()).toBe('创建中…')
    expect(wrapper.get('[data-testid="filter-qc-action"]').text()).toBe('创建中…')

    const table = wrapper.getComponent({ name: 'ATable' })
    const customRow = (table.vm.$attrs['custom-row'] ?? table.vm.$attrs.customRow) as (
      record: Record<string, unknown>,
    ) => {
      tabindex?: number
      'aria-current'?: string
      onKeydown?: (event: KeyboardEvent) => void
    }

    const activeRowAttrs = customRow({ id: 'r-1', recordKey: 'key-1' })
    const inactiveRowAttrs = customRow({ id: 'r-2', recordKey: 'key-2' })
    expect(activeRowAttrs.tabindex).toBe(0)
    expect(activeRowAttrs['aria-current']).toBe('true')
    expect(inactiveRowAttrs.tabindex).toBe(0)
    expect(inactiveRowAttrs['aria-current']).toBeUndefined()

    const rowEl = document.createElement('tr')
    const preventDefault = vi.fn()
    inactiveRowAttrs.onKeydown?.({
      key: 'Enter',
      target: rowEl,
      currentTarget: rowEl,
      preventDefault,
    } as unknown as KeyboardEvent)
    inactiveRowAttrs.onKeydown?.({
      key: ' ',
      target: rowEl,
      currentTarget: rowEl,
      preventDefault,
    } as unknown as KeyboardEvent)
    const buttonEl = document.createElement('button')
    inactiveRowAttrs.onKeydown?.({
      key: 'Enter',
      target: buttonEl,
      currentTarget: rowEl,
      preventDefault,
    } as unknown as KeyboardEvent)

    expect(preventDefault).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('select-row')).toEqual([['key-2'], ['key-2']])
  })

  it('retries loading documents from CurrentMedicalRecordDrawer error alert', async () => {
    vi.useFakeTimers()
    const loadSpy = vi
      .spyOn(currentMedicalRecordService, 'loadCurrentMedicalRecord')
      .mockResolvedValueOnce({ success: false, message: '读取超时', errorType: 'timeout' })
      .mockResolvedValueOnce({
        success: true,
        data: { documents: [], caseKey: '["H-1","P-1","V-1"]' } as never,
      })

    try {
      const wrapper = mount(CurrentMedicalRecordDrawer, {
        props: {
          record: {
            id: 'V-1',
            visitId: 'V-1',
            instituteId: 'H-1',
            patientId: 'P-1',
            bedNo: '',
            name: '患者甲',
            sex: '女',
            age: 40,
            insurance: '',
            department: '内科',
            admissionDate: '2026-08-01',
            dischargeDate: '2026-08-08',
            days: 7,
            diagnosis: '',
            diagnosisCode: '',
            doctor: '',
            status: 'pending',
          },
        },
        global: {
          stubs: {
            ADrawer: passthroughStub('ADrawer'),
            QCRecordCompareWorkbench: defineComponent({
              name: 'QCRecordCompareWorkbench',
              setup() {
                return () => h('div', { 'data-testid': 'drawer-workbench' })
              },
            }),
            ReadonlyMedicalRecordHeader: true,
            RecordViewCloseIcon: true,
            HospitalLoading: true,
          },
        },
      })

      await flushPromises()
      await vi.runAllTimersAsync()
      await flushPromises()
      expect(wrapper.find('.current-medical-record-drawer__error').exists()).toBe(true)
      const retryBtn = wrapper.get('[data-testid="retry-current-medical-record"]')
      await retryBtn.trigger('click')
      await flushPromises()
      await vi.runAllTimersAsync()
      await flushPromises()

      expect(loadSpy).toHaveBeenCalledTimes(2)
      expect(wrapper.find('[data-testid="drawer-workbench"]').exists()).toBe(true)
      wrapper.unmount()
    } finally {
      loadSpy.mockRestore()
      vi.useRealTimers()
    }
  })
})

function deferredPromise<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('Batch 4 P1 worklist URL hygiene, assist overlay & concurrency guards', () => {
  it('RecordPoolQcTaskHistory discards stale loadJobs, openJob and fetchDebugSnapshot responses after superseding or closeDetail', async () => {
    const firstList = deferredPromise<{ success: boolean; data: { items: Array<Record<string, unknown>> } }>()
    const secondList = deferredPromise<{ success: boolean; data: { items: Array<Record<string, unknown>> } }>()
    const firstJob = deferredPromise<{ success: boolean; data: Record<string, unknown> }>()
    const secondJob = deferredPromise<{ success: boolean; data: Record<string, unknown> }>()
    const firstDebug = deferredPromise<{ success: boolean; data: Record<string, unknown> }>()

    const listSpy = vi
      .spyOn(sichuanService, 'listSichuanWorkspaceBatchJobs')
      .mockReturnValueOnce(firstList.promise as never)
      .mockReturnValueOnce(secondList.promise as never)
    const getJobSpy = vi
      .spyOn(sichuanService, 'getSichuanWorkspaceBatchJob')
      .mockReturnValueOnce(firstJob.promise as never)
      .mockReturnValueOnce(secondJob.promise as never)
    const getDebugSpy = vi
      .spyOn(sichuanService, 'getSichuanWorkspaceBatchJobDebugSnapshot')
      .mockReturnValueOnce(firstDebug.promise as never)

    const BatchDrawerStub = defineComponent({
      name: 'SemanticRulesBatchResultDrawer',
      props: {
        open: { type: Boolean, default: false },
        batchJobDetail: { type: Object, default: null },
        batchJobDetailLoading: { type: Boolean, default: false },
        batchJobDebugSnapshot: { type: Object, default: null },
        batchJobDebugLoading: { type: Boolean, default: false },
        close: { type: Function, default: () => {} },
      },
      setup(props) {
        return () =>
          h('div', {
            'data-testid': 'task-history-detail-stub',
            'data-open': String(props.open),
            'data-job-id': String((props.batchJobDetail as { id?: string } | null)?.id || ''),
            'data-debug-job-id': String(
              (props.batchJobDebugSnapshot as { job_id?: string } | null)?.job_id || '',
            ),
          })
      },
    })

    try {
      const wrapper = mount(RecordPoolQcTaskHistory, {
        global: {
          stubs: {
            ADrawer: passthroughStub('ADrawer'),
            AButton: passthroughStub('AButton', 'button'),
            ASpin: passthroughStub('ASpin'),
            AEmpty: passthroughStub('AEmpty'),
            SemanticRulesBatchResultDrawer: BatchDrawerStub,
          },
        },
      })

      // 并发 loadJobs：较新请求先返回，晚到的旧请求不得覆盖列表
      await wrapper.get('[data-testid="record-pool-qc-task-history-entry"]').trigger('click')
      await wrapper.get('.record-pool-task-history__toolbar button').trigger('click')

      secondList.resolve({
        success: true,
        data: {
          items: [
            { id: 'job-new', rule_set_key: 'luxian_0609_qc_v1', status: 'completed', scope: 'all' },
            { id: 'job-old', rule_set_key: 'luxian_0609_qc_v1', status: 'completed', scope: 'all' },
          ],
        },
      })
      await flushPromises()
      firstList.resolve({
        success: true,
        data: {
          items: [{ id: 'job-stale', rule_set_key: 'luxian_0609_qc_v1', status: 'failed', scope: 'all' }],
        },
      })
      await flushPromises()
      expect(wrapper.findAll('.record-pool-task-history__item')).toHaveLength(2)

      // 并发 openJob：先点 job-new 再点 job-old，晚到的 job-new 不得覆盖 job-old
      const items = wrapper.findAll('.record-pool-task-history__item')
      await items[0]!.trigger('click')
      await items[1]!.trigger('click')

      secondJob.resolve({
        success: true,
        data: { id: 'job-old', rule_set_key: 'luxian_0609_qc_v1', status: 'completed' },
      })
      await flushPromises()
      expect(wrapper.get('[data-testid="task-history-detail-stub"]').attributes('data-job-id')).toBe('job-old')

      firstJob.resolve({
        success: true,
        data: { id: 'job-new', rule_set_key: 'luxian_0609_qc_v1', status: 'completed' },
      })
      await flushPromises()
      expect(wrapper.get('[data-testid="task-history-detail-stub"]').attributes('data-job-id')).toBe('job-old')

      // closeDetail 后迟到的 debug snapshot 响应必须丢弃
      const drawerStub = wrapper.getComponent(BatchDrawerStub)
      ;(drawerStub.props('close') as () => void)()
      await flushPromises()
      firstDebug.resolve({ success: true, data: { job_id: 'job-old' } })
      await flushPromises()
      expect(wrapper.get('[data-testid="task-history-detail-stub"]').attributes('data-open')).toBe('false')
      expect(
        wrapper.get('[data-testid="task-history-detail-stub"]').attributes('data-debug-job-id'),
      ).toBe('')
      wrapper.unmount()
    } finally {
      listSpy.mockRestore()
      getJobSpy.mockRestore()
      getDebugSpy.mockRestore()
    }
  })

  it('WorkstationV4View: clears URL query on handleClearFilters, blocks stale localStorage assistTab overlay in list mode, guards concurrency, and avoids duplicate stage mount fetch', async () => {
    resetClinicalSourceOptionsCache()
    window.localStorage.setItem(
      'workstation_v4_session',
      JSON.stringify({
        frontpageTab: 'fields',
        assistPanelVisible: true,
        assistTab: 'message',
        icdDrawerVisible: false,
        icdApplyTarget: 'mainDiagnosis',
        icdApplyIndex: 1,
      }),
    )

    const optionsSpy = vi.spyOn(clinicalSourcesApi, 'options').mockResolvedValue({
      default_source: 'independent_cdm',
      sources: [{ id: 'independent_cdm', name: '东华CDM', enabled: true }],
    })
    const getRawSpy = vi.spyOn(ApiService, 'getRaw').mockResolvedValue({
      data: { records: [], departments: [], doctors: [], total: 0, page: 1 },
    } as never)
    const postRawSpy = vi.spyOn(ApiService, 'postRaw').mockResolvedValue({
      data: { records: [], qc_summary: { total_records: 0 } },
    } as never)
    const stageResp1 = deferredPromise<{ data: { data: { items: Array<Record<string, unknown>>; total: number } } }>()
    const stageResp2 = deferredPromise<{ data: { data: { items: Array<Record<string, unknown>>; total: number } } }>()
    const apiGetSpy = vi
      .spyOn(apiClient, 'get')
      .mockReturnValueOnce(stageResp1.promise as never)
      .mockReturnValueOnce(stageResp2.promise as never)
    const verify1 = deferredPromise<{ data: { total: number; inpatient: number; discharged: number; unknown: number } }>()
    const apiPostSpy = vi.spyOn(apiClient, 'post').mockReturnValueOnce(verify1.promise as never)
    const successSpy = vi.spyOn(message, 'success').mockImplementation(() => (() => undefined) as never)

    const WorkstationV4ListViewStub = defineComponent({
      name: 'WorkstationV4ListView',
      props: {
        analyticsDrilldown: { type: Object, default: null },
        syncScope: { type: String, default: 'all' },
        workbenchRows: { type: Array, default: () => [] },
      },
      emits: ['clear-filters', 'toggle-today-inpatient', 'select-hosp-filter'],
      setup(props) {
        return () =>
          h('div', {
            'data-testid': 'workstation-list-stub',
            'data-has-drilldown': String(Boolean(props.analyticsDrilldown)),
            'data-sync-scope': props.syncScope,
            'data-row-count': String(props.workbenchRows.length),
          })
      },
    })

    const WorkstationV4AssistViewStub = defineComponent({
      name: 'WorkstationV4AssistView',
      setup() {
        return () => h('div', { 'data-testid': 'workstation-assist-stub' })
      },
    })

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/workstation-v5/worklist', component: WorkstationV4View },
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
      ],
    })

    try {
      await router.push(
        '/workstation-v5/worklist?source=analytics&department=ICU&keyword=张三&analytics_scope=final&analytics_rule_id=R-1&keep=1',
      )
      await router.isReady()

      const wrapper = mount(WorkstationV4View, {
        global: {
          plugins: [createPinia(), router],
          stubs: {
            WorkstationV4ListView: WorkstationV4ListViewStub,
            WorkstationV4AssistView: WorkstationV4AssistViewStub,
            CurrentMedicalRecordDrawer: true,
            WorkstationV4DetailView: true,
            WorkstationV4RulesView: true,
            AModal: true,
            ASegmented: true,
            ATextarea: true,
            AButton: true,
          },
        },
      })
      await flushPromises()

      // 1) Stale localStorage assistTab === 'message' must NOT mount WorkstationV4AssistView in list mode
      expect(wrapper.find('[data-testid="workstation-assist-stub"]').exists()).toBe(false)

      // 2) handleClearFilters strips department, keyword, source, analytics_* from route.query
      const listStub = wrapper.getComponent(WorkstationV4ListViewStub)
      expect(listStub.attributes('data-has-drilldown')).toBe('true')
      listStub.vm.$emit('clear-filters')
      await flushPromises()

      expect(router.currentRoute.value.query).toEqual({ keep: '1' })
      expect(listStub.attributes('data-has-drilldown')).toBe('false')

      // 3) toggleTodaySyncedInpatient ignores stale verify response if superseded by hospFilter change
      listStub.vm.$emit('toggle-today-inpatient')
      await flushPromises()
      listStub.vm.$emit('select-hosp-filter', 'discharged')
      await flushPromises()
      verify1.resolve({ data: { total: 5, inpatient: 3, discharged: 1, unknown: 1 } })
      await flushPromises()
      expect(listStub.attributes('data-sync-scope')).toBe('all')
      expect(successSpy).not.toHaveBeenCalled()

      // 4) Explicit ?assist=message in list mode opens assist panel
      await router.replace('/workstation-v5/worklist?assist=message')
      await flushPromises()
      expect(wrapper.find('[data-testid="workstation-assist-stub"]').exists()).toBe(true)

      wrapper.unmount()

      // 5) Aggregated stage mount fetches fetchStageWorklist ONCE (no duplicate mount fetch) and guards stale responses
      apiGetSpy.mockClear()
      await router.push('/workstation-v5/worklist?stage=coding_qc')
      await flushPromises()

      const stageWrapper = mount(WorkstationV4View, {
        global: {
          plugins: [createPinia(), router],
          stubs: {
            WorkstationV4ListView: WorkstationV4ListViewStub,
            WorkstationV4AssistView: WorkstationV4AssistViewStub,
            CurrentMedicalRecordDrawer: true,
            WorkstationV4DetailView: true,
            WorkstationV4RulesView: true,
            AModal: true,
            ASegmented: true,
            ATextarea: true,
            AButton: true,
          },
        },
      })
      await flushPromises()
      expect(apiGetSpy).toHaveBeenCalledTimes(1)

      // Trigger a newer stage fetch; resolve newer first, then older -> older must not overwrite newer
      const stageListStub = stageWrapper.getComponent(WorkstationV4ListViewStub)
      stageListStub.vm.$emit('clear-filters')
      await flushPromises()
      expect(apiGetSpy).toHaveBeenCalledTimes(2)

      stageResp2.resolve({
        data: {
          data: {
            items: [{ visit_id: 'V-NEW', patient_name: '最新阶段病历', workflow_type: 'coding' }],
            total: 1,
          },
        },
      })
      await flushPromises()
      expect(stageListStub.attributes('data-row-count')).toBe('1')

      stageResp1.resolve({
        data: {
          data: {
            items: [
              { visit_id: 'V-OLD-1', patient_name: '旧1', workflow_type: 'coding' },
              { visit_id: 'V-OLD-2', patient_name: '旧2', workflow_type: 'coding' },
            ],
            total: 2,
          },
        },
      })
      await flushPromises()
      expect(stageListStub.attributes('data-row-count')).toBe('1')
      stageWrapper.unmount()
    } finally {
      window.localStorage.removeItem('workstation_v4_session')
      optionsSpy.mockRestore()
      getRawSpy.mockRestore()
      postRawSpy.mockRestore()
      apiGetSpy.mockRestore()
      apiPostSpy.mockRestore()
      successSpy.mockRestore()
    }
  })
})
