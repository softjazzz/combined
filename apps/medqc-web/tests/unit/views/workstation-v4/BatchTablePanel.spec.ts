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

function mountTable(summary: Record<string, unknown>) {
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
          isDemo: false,
          sourceState: { status: 'unknown', lastSyncAt: null, reasonCode: null },
          latestQcSummary: summary,
        },
      ],
      selectedRowKeys: [],
      summaryText: '',
      showSelection: false,
      showPrimaryAction: false,
      showQualityColumns: true,
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
      },
    },
  })
}

describe('BatchTablePanel 病历池质控投影', () => {
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
        },
      },
    })

    await wrapper.findAll('button').at(1)?.trigger('click')

    expect(wrapper.emitted('open-record')).toEqual([['["H-2","P-2","V-100"]']])
  })

  it('separates unknown source state from a not-run QC result', () => {
    const wrapper = mountTable({ status: 'not_run' })

    expect(wrapper.text()).toContain('资料同步状态待核实')
    expect(wrapper.text()).toContain('尚未运行质控')
    expect(wrapper.text()).toContain('当前规则版本尚未生成结果')
    expect(wrapper.text()).not.toContain('资料不足')
  })

  it('renders canonical ready counts and keeps data gaps distinct from technical errors', () => {
    const wrapper = mountTable({
      status: 'ready',
      totalRuleCount: 75,
      statusCounts: { non_compliant: 2, data_gap: 3 },
    })

    expect(wrapper.text()).toContain('已完成 · 75 条规则')
    expect(wrapper.text()).toContain('确定问题 2 项；资料待补 3 项')
  })

  it('renders a canonical delivery error as result validation error rather than data gap', () => {
    const wrapper = mountTable({
      status: 'technical_error',
      reasonCode: 'canonical_envelope_missing',
    })

    expect(wrapper.text()).toContain('结果校验异常')
    expect(wrapper.text()).toContain('质控结果未完整交付')
    expect(wrapper.text()).not.toContain('资料待补')
  })
})
