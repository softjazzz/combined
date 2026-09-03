import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import BatchTablePanel from '@/views/workstation-v4/components/workbench/BatchTablePanel.vue'

const TableStub = defineComponent({
  name: 'ATable',
  props: {
    columns: {
      type: Array,
      default: () => [],
    },
    dataSource: {
      type: Array,
      default: () => [],
    },
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

const PopconfirmStub = defineComponent({
  name: 'APopconfirm',
  props: {
    disabled: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['confirm'],
  setup(_props, { slots }) {
    return () => h('div', { 'data-testid': 'filter-qc-confirm' }, slots.default?.())
  },
})

function mountTable() {
  return mount(BatchTablePanel, {
    props: {
      rows: [
        {
          id: 'record-1',
          patientName: '患者甲',
          visitId: 'V-1',
          department: '内科',
          stageStatus: '待处理',
          riskReason: '',
          updatedAt: '2026-08-08',
          admissionDate: '2026-08-01',
          dischargeDate: '2026-08-08',
          isDemo: false,
          sourceState: { status: 'unknown', lastSyncAt: null, reasonCode: null },
          latestQcSummary: {
            status: 'ready',
            totalRuleCount: 75,
            statusCounts: { non_compliant: 2, data_gap: 3 },
          },
        },
      ],
      selectedRowKeys: [],
      summaryText: '',
      showSelection: false,
      showPrimaryAction: false,
      recordPoolMode: true,
    },
    global: {
      stubs: {
        ATable: TableStub,
        AButton: defineComponent({
          name: 'AButton',
          setup(_props, { attrs, slots }) {
            return () => h('button', attrs, slots.default?.())
          },
        }),
        APopconfirm: PopconfirmStub,
      },
    },
  })
}

describe('BatchTablePanel 病历池列表', () => {
  it('shows an unverified status without claiming that the patient is inpatient', () => {
    const wrapper = mountTable()
    const row = wrapper.props('rows')[0]
    row.hospitalizationStatus = 'unknown'
    row.dischargeDate = '-'
    return wrapper.setProps({ rows: [row] }).then(() => {
      expect(wrapper.text()).toContain('待核验')
      expect(wrapper.text()).not.toContain('尚未出院')
    })
  })

  it('renders task progress directly below the action toolbar and before the table', () => {
    const wrapper = mount(BatchTablePanel, {
      props: {
        rows: [],
        selectedRowKeys: [],
        summaryText: '',
        showPrimaryAction: true,
      },
      slots: {
        'task-status': '<div data-testid="live-task-progress">实时任务进度</div>',
      },
      global: {
        stubs: {
          ATable: TableStub,
          AButton: defineComponent({
            name: 'AButton',
            setup(_props, { attrs, slots }) {
              return () => h('button', attrs, slots.default?.())
            },
          }),
          APopconfirm: PopconfirmStub,
        },
      },
    })

    const status = wrapper.find('[data-testid="batch-table-task-status"]')
    const table = wrapper.find('[data-testid="table-stub"]')
    expect(status.exists()).toBe(true)
    expect(status.text()).toContain('实时任务进度')
    expect(
      status.element.compareDocumentPosition(table.element) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('shows a secondary full-filter QC action with the server total', () => {
    const wrapper = mount(BatchTablePanel, {
      props: {
        rows: [],
        selectedRowKeys: [],
        summaryText: '',
        showPrimaryAction: true,
        showFilterQcAction: true,
        filterQcCount: 19,
      },
      global: {
        stubs: {
          ATable: TableStub,
          APopconfirm: PopconfirmStub,
          AButton: defineComponent({
            name: 'AButton',
            setup(_props, { attrs, slots }) {
              return () => h('button', attrs, slots.default?.())
            },
          }),
        },
      },
    })

    const button = wrapper.find('[data-testid="filter-qc-action"]')
    expect(button.exists()).toBe(true)
    expect(button.text()).toBe('质控当前筛选（19）')
    expect(button.attributes('disabled')).toBeUndefined()
  })

  it.each([
    { count: 0, loading: false },
    { count: 19, loading: true },
  ])(
    'disables the full-filter QC action for $count records when loading=$loading',
    ({ count, loading }) => {
      const wrapper = mount(BatchTablePanel, {
        props: {
          rows: [],
          selectedRowKeys: [],
          summaryText: '',
          showFilterQcAction: true,
          filterQcCount: count,
          filterQcLoading: loading,
        },
        global: {
          stubs: {
            ATable: TableStub,
            APopconfirm: PopconfirmStub,
            AButton: defineComponent({
              name: 'AButton',
              setup(_props, { attrs, slots }) {
                return () => h('button', attrs, slots.default?.())
              },
            }),
          },
        },
      })

      expect(wrapper.find('[data-testid="filter-qc-action"]').attributes('disabled')).toBeDefined()
    },
  )

  it('hides the full-filter QC action when it is not enabled', () => {
    const wrapper = mountTable()
    expect(wrapper.find('[data-testid="filter-qc-action"]').exists()).toBe(false)
  })

  it('shows the formal QC action and prevents repeat submission while it is loading', async () => {
    const wrapper = mount(BatchTablePanel, {
      props: {
        rows: [],
        selectedRowKeys: ['["H-1","P-1","V-1"]'],
        summaryText: '',
        showSelection: true,
        showPrimaryAction: true,
        primaryActionLabel: '质控所选（1）',
        primaryActionLoading: true,
      },
      global: {
        stubs: {
          ATable: TableStub,
          AButton: defineComponent({
            name: 'AButton',
            setup(_props, { attrs, slots }) {
              return () => h('button', attrs, slots.default?.())
            },
          }),
          APopconfirm: PopconfirmStub,
        },
      },
    })

    const button = wrapper.find('button')
    expect(button.text()).toBe('质控所选（1）')
    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('click')
    expect(wrapper.emitted('batch-extract')).toBeUndefined()
  })

  it('uses the backend triple record key for duplicate-visit rows and detail selection', async () => {
    const wrapper = mount(BatchTablePanel, {
      props: {
        rows: [
          {
            id: 'V-100',
            recordKey: '["H-1","P-1","V-100"]',
            patientName: '患者甲',
            visitId: 'V-100',
            department: '内科',
            stageStatus: '待处理',
            riskReason: '',
            updatedAt: '2026-08-08',
            isDemo: false,
          },
          {
            id: 'V-100',
            recordKey: '["H-2","P-2","V-100"]',
            patientName: '患者乙',
            visitId: 'V-100',
            department: '外科',
            stageStatus: '待处理',
            riskReason: '',
            updatedAt: '2026-08-08',
            isDemo: false,
          },
        ],
        selectedRowKeys: [],
        summaryText: '',
        showSelection: false,
        showPrimaryAction: false,
      },
      global: {
        stubs: {
          ATable: TableStub,
          AButton: defineComponent({
            name: 'AButton',
            setup(_props, { attrs, slots }) {
              return () => h('button', attrs, slots.default?.())
            },
          }),
          APopconfirm: PopconfirmStub,
        },
      },
    })

    await wrapper.findAll('button').at(1)?.trigger('click')

    expect(wrapper.emitted('open-record')).toEqual([['["H-2","P-2","V-100"]']])
  })

  it('renders only patient, department, hospitalization and action columns in record-pool mode', () => {
    const wrapper = mountTable()
    const table = wrapper.getComponent({ name: 'ATable' })
    const keys = (table.props('columns') as Array<{ key: string }>).map((column) => column.key)

    expect(keys).toEqual(['patient', 'department', 'admissionDischarge', 'action'])
    expect(wrapper.text()).toContain('2026-08-01')
    expect(wrapper.text()).toContain('2026-08-08')
    expect(wrapper.text()).toContain('已出院')
    expect(wrapper.text()).toContain('入院')
    expect(wrapper.text()).toContain('出院')
    expect(wrapper.text()).not.toContain('资料同步状态待核实')
    expect(wrapper.text()).not.toContain('已完成 · 75 条规则')
    expect(wrapper.text()).not.toContain('确定问题 2 项')
  })

  it('marks records without a discharge date as inpatient and explains the missing date', async () => {
    const wrapper = mountTable()
    await wrapper.setProps({
      rows: [
        {
          id: 'record-2',
          patientName: '患者乙',
          visitId: 'V-2',
          department: '外科',
          stageStatus: '待处理',
          riskReason: '',
          updatedAt: '2026-08-09',
          admissionDate: '2026-08-09',
          dischargeDate: '-',
          isDemo: false,
        },
      ],
    })

    expect(wrapper.text()).toContain('在院')
    expect(wrapper.text()).toContain('尚未出院')
  })
})
