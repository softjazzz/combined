import fs from 'node:fs'
import path from 'node:path'
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
  setup(props, { attrs, slots }) {
    return () => h('div', { ...attrs, 'data-value': props.value }, slots.default?.())
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
    return () => h('div', { 'data-option-value': props.value }, slots.default?.())
  },
})

const passthroughStub = (name: string, tag = 'div') =>
  defineComponent({
    name,
    setup(_props, { attrs, slots }) {
      return () => h(tag, attrs, slots.default?.())
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
      dateRange: null,
      dateField: 'visit',
      departmentSelectOptions: [
        { name: '全部科室', total: 538, warningCount: 0 },
        { name: '内科', total: 220, warningCount: 0 },
        { name: '外科', total: 318, warningCount: 0 },
      ],
      quickDepartments: [],
      activeDept: '全部科室',
      doctorSelectOptions: [{ name: '全部主管医师', total: 538 }],
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
      tableSummaryText: '当前筛选：全部科室 / 待首页质控（正式数据） / 共 7 份',
      displayLoading: false,
      batchActionLoading: false,
      stageMeta: {
        pageTitle: '正式首页质控队列',
        tableTitle: '待首页质控（正式数据）',
        batchActionText: '批量首页质控',
        singleActionText: '进入首页质控',
      },
      currentStageFilter: '',
      listRecords: [],
      stageEmptyText: '暂无数据',
      displayServerTotalPages: 1,
      currentPage: 1,
      pageSize: 15,
      displayServerTotal: 7,
      qcScopeTotal: 538,
      qcSummaryState: 'ready',
      recordPoolQcTask: null,
      loadError: false,
      ...overrides,
    },
    global: {
      stubs: {
        AAlert: false,
        BatchTablePanel: passthroughStub('BatchTablePanel'),
        RecordPoolPreviewPanel: passthroughStub('RecordPoolPreviewPanel'),
        RecordPoolQcTaskHistory: passthroughStub('RecordPoolQcTaskHistory', 'button'),
        RecordPoolQcTaskStatusBar: passthroughStub('RecordPoolQcTaskStatusBar'),
        AnalyticsDrilldownBar: passthroughStub('AnalyticsDrilldownBar'),
        FrontpageTenderValidationDrawer: passthroughStub('FrontpageTenderValidationDrawer'),
        AInput: passthroughStub('AInput'),
        AButton: passthroughStub('AButton', 'button'),
        ARangePicker: passthroughStub('ARangePicker'),
        ASegmented: passthroughStub('ASegmented'),
        ASelect: SelectStub,
        ASelectOption: SelectOptionStub,
        SearchOutlined: true,
      },
    },
  })
}

const refinedCssPath = path.resolve(
  __dirname,
  '../../src/views/workstation-v4/styles/record-pool-refined.css',
)
const workstationViewCssPath = path.resolve(
  __dirname,
  '../../src/views/workstation-v4/styles/workstation-v4-view.css',
)

describe('Worklist layout, hidden verify button & stage count fixes', () => {
  it('P0: hides the 「核验当日在院 / 当日在院 · 已核验」 button in all syncScope states while keeping props intact', () => {
    const defaultWrapper = mountListView({ syncScope: 'all' })
    expect(defaultWrapper.find('.wv4-record-pool-filter__sync-shortcut').exists()).toBe(false)
    expect(defaultWrapper.text()).not.toContain('核验当日在院')
    expect(defaultWrapper.text()).not.toContain('当日在院 · 已核验')

    const verifiedWrapper = mountListView({
      syncScope: 'today_inpatient',
      dateField: 'admission',
      hospitalizationStatusVerifying: true,
    })
    expect(verifiedWrapper.find('.wv4-record-pool-filter__sync-shortcut').exists()).toBe(false)
    expect(verifiedWrapper.text()).not.toContain('核验当日在院')
    expect(verifiedWrapper.text()).not.toContain('当日在院 · 已核验')
    // Props linkage with parent state stays intact (inpatient sort still visible)
    expect(verifiedWrapper.find('.wv4-record-pool-filter__inpatient-sort').exists()).toBe(true)
    expect(verifiedWrapper.find('#record-pool-date-label').text()).toBe('入院日期')
  })

  it('P2: aligns stage=frontpage_qc activeDepartmentTotal with displayServerTotal (7) instead of contradictory full-library count (538)', () => {
    const wrapper = mountListView({
      isStageQueueMode: true,
      currentStageFilter: 'frontpage_qc',
      activeDept: '全部科室',
      displayServerTotal: 7,
      qcScopeTotal: 538,
      departmentSelectOptions: [
        { name: '全部科室', total: 538, warningCount: 0 },
        { name: '内科', total: 220, warningCount: 0 },
      ],
    })

    const countBadge = wrapper.get('.workbench-dept-filter__count')
    expect(countBadge.text().trim()).toBe('7')
    expect(countBadge.attributes('aria-label')).toBe('当前阶段共 7 份病历')
    // Contradictory full-library totals (538 / 220) are not rendered in option count pills
    expect(wrapper.findAll('.workbench-dept-select__count')).toHaveLength(0)
  })

  it('P2: preserves stage department option counts when they match the stage server total and no keyword search is active', async () => {
    const wrapper = mountListView({
      isStageQueueMode: true,
      currentStageFilter: 'frontpage_qc',
      activeDept: '全部科室',
      searchText: '',
      displayServerTotal: 7,
      departmentSelectOptions: [
        { name: '全部科室', total: 7, warningCount: 0 },
        { name: '内科', total: 4, warningCount: 0 },
        { name: '外科', total: 3, warningCount: 0 },
      ],
    })

    expect(wrapper.get('.workbench-dept-filter__count').text().trim()).toBe('7')
    expect(wrapper.findAll('.workbench-dept-select__count').map((el) => el.text().trim())).toEqual([
      '7',
      '4',
      '3',
    ])

    // When keyword search narrows the list, hide mismatched per-department option counts
    await wrapper.setProps({ searchText: '张', displayServerTotal: 2 })
    expect(wrapper.get('.workbench-dept-filter__count').text().trim()).toBe('2')
    expect(wrapper.findAll('.workbench-dept-select__count')).toHaveLength(0)
  })

  it('P1 & P2: enforces 1280×800 / 1366×860 layout, non-clipped action column, first-screen preview actions, nowrap toolbar & stage table rules in CSS', () => {
    const refinedCss = fs.readFileSync(refinedCssPath, 'utf-8')
    const viewCss = fs.readFileSync(workstationViewCssPath, 'utf-8')

    // 1) Split layout narrows right preview column at <= 1420px (1366px) and <= 1320px (1280px)
    expect(refinedCss).toContain('@media (max-width: 1420px)')
    expect(refinedCss).toContain('grid-template-columns: minmax(0, 1fr) 292px;')
    expect(refinedCss).toContain('@media (max-width: 1320px)')
    expect(refinedCss).toContain('grid-template-columns: minmax(0, 1fr) 272px;')

    // 2) Record-pool table uses fixed 100% layout + explicit col widths so action column is never clipped
    expect(refinedCss).toContain(
      '.wv4-list :deep(.batch-table-panel--record-pool .ant-table-content > table)',
    )
    expect(refinedCss).toContain('width: 100% !important;')
    expect(refinedCss).toContain('table-layout: fixed !important;')
    expect(refinedCss).toContain(
      '.wv4-list :deep(.batch-table-panel--record-pool colgroup col.ant-table-selection-col + col + col + col + col + col + col)',
    )
    expect(refinedCss).toContain('width: 66px !important;')

    // 3) Right preview stays 2-column compact and pins bottom action buttons in first screen at 1280×800
    expect(refinedCss).toContain('.wv4-list :deep(.pool-preview__facts)')
    expect(refinedCss).toContain('grid-template-columns: repeat(2, minmax(0, 1fr));')
    expect(refinedCss).toContain('.wv4-list :deep(.pool-preview__actions)')
    expect(refinedCss).toContain('position: sticky;')
    expect(refinedCss).toContain('bottom: 0;')
    expect(refinedCss).toContain('@media (max-height: 820px)')
    expect(viewCss).toContain('@media (max-width: 1420px), (max-height: 880px)')

    // 4) Toolbar buttons & pills never wrap into two lines when rows are selected
    expect(refinedCss).toContain('.wv4-list :deep(.batch-table-panel__action.ant-btn),')
    expect(refinedCss).toContain('.wv4-list :deep(.record-pool-task-history__entry.ant-btn),')
    expect(refinedCss).toContain('.wv4-list :deep(.batch-table-panel__clear-selection.ant-btn)')
    expect(refinedCss).toContain('white-space: nowrap !important;')

    // 5) Stage queue status tag stays single-line and stage table eliminates desktop horizontal overflow
    expect(refinedCss).toContain('.wv4-list :deep(.batch-table-panel__tag)')
    expect(refinedCss).toContain('white-space: nowrap;')
    expect(refinedCss).toContain(
      '.wv4-list :deep(.batch-table-panel:not(.batch-table-panel--record-pool) .ant-table-content > table)',
    )
  })
})
