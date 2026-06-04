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
      workbenchRows: [],
      selectedWorkbenchKeys: [],
      tableSummaryText: '当前筛选：中医科 / 入出院日期 2026-05-25 至 2026-05-27 / 共 19 份',
      displayLoading: false,
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
      ...overrides,
    },
    global: {
      stubs: {
        PriorityLane: passthroughStub('PriorityLane'),
        BatchTablePanel: passthroughStub('BatchTablePanel'),
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
})
