import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { normalizeWorklistItem } from '../normalize'
import { mapWorklistItemToRecord, worklistRecordKey } from '../workstationDataController'
import BatchTablePanel from '../components/workbench/BatchTablePanel.vue'

const TableStub = {
  name: 'a-table',
  props: ['dataSource', 'rowKey', 'rowSelection'],
  template: `
    <div>
      <div v-for="row in dataSource" :key="rowKey(row)">
        <slot name="bodyCell" :column="{ key: 'patient' }" :record="row" />
        <slot name="bodyCell" :column="{ key: 'action' }" :record="row" />
      </div>
    </div>
  `,
}

function worklistRow(patientId: string, identityStatus?: 'ambiguous' | 'unverified') {
  return normalizeWorklistItem({
    institute_id: 'hospital-1',
    patient_id: patientId,
    visit_id: 'shared-visit',
    workflow_type: 'frontpage',
    identity_status: identityStatus,
    queue_status: 'unknown',
    latest_qc_result_id: 'legacy-result',
    active_defect_count: 4,
  })
}

function panelRow(patientId: string, identityStatus?: 'ambiguous' | 'unverified') {
  const item = worklistRow(patientId, identityStatus)
  return {
    id: worklistRecordKey(item),
    recordKey: worklistRecordKey(item),
    identityStatus,
    patientName: patientId,
    visitId: item.visitId,
    department: '内科',
    stageStatus: '状态未知',
    riskReason: '历史质控归属未核实',
    updatedAt: '-',
    isDemo: false,
  }
}

describe('聚合待办三坐标身份保护', () => {
  it('同住院号不同患者保留两条独立行，未核实旧结果不能标成已完成', () => {
    const first = worklistRow('patient-1', 'ambiguous')
    const second = worklistRow('patient-2', 'unverified')
    const firstRecord = mapWorklistItemToRecord(first)
    const secondRecord = mapWorklistItemToRecord(second)

    expect(firstRecord.recordKey).not.toBe(secondRecord.recordKey)
    expect(firstRecord.visitId).toBe(secondRecord.visitId)
    expect(firstRecord.identityStatus).toBe('ambiguous')
    expect(secondRecord.identityStatus).toBe('unverified')
    expect(firstRecord.status).toBe('pending')
    expect(secondRecord.status).toBe('pending')
  })

  it('身份未核实行不可选择，歧义行不可打开，唯一未核实行仍可查看', async () => {
    const rows = [
      panelRow('patient-1', 'ambiguous'),
      panelRow('patient-2', 'unverified'),
      panelRow('patient-3'),
    ]
    const wrapper = mount(BatchTablePanel, {
      props: { rows, selectedRowKeys: [], summaryText: '', showSelection: true },
      global: {
        stubs: {
          'a-table': TableStub,
          'a-button': {
            props: ['disabled'],
            emits: ['click'],
            template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
          },
          'a-popconfirm': { template: '<div><slot /></div>' },
        },
      },
    })

    const selection = wrapper.findComponent(TableStub).props('rowSelection') as {
      getCheckboxProps: (row: (typeof rows)[number]) => { disabled: boolean }
      onChange: (keys: string[]) => void
    }
    expect(selection.getCheckboxProps(rows[0]).disabled).toBe(true)
    expect(selection.getCheckboxProps(rows[1]).disabled).toBe(true)
    expect(selection.getCheckboxProps(rows[2]).disabled).toBe(false)
    selection.onChange(rows.map((row) => row.recordKey))
    expect(wrapper.emitted('update:selectedRowKeys')?.[0]).toEqual([[rows[2].recordKey]])

    const buttons = wrapper.findAll('.batch-table-panel__detail-button')
    expect(buttons[0].attributes('disabled')).toBeDefined()
    expect(buttons[1].attributes('disabled')).toBeUndefined()
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    expect(wrapper.emitted('open-record')).toEqual([[rows[1].recordKey]])
    expect(wrapper.text()).toContain('身份歧义')
    expect(wrapper.text()).toContain('归属未核实')
  })
})
