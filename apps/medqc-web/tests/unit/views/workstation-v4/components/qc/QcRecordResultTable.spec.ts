import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import QcRecordResultTable from '@/views/workstation-v4/components/qc/QcRecordResultTable.vue'

const rows = [
  {
    recordKey: '["H-1","P-1","V-1"]',
    patientName: '患者甲',
    visitId: 'V-1',
    department: '重症医学科',
    bedNumber: '12 床',
    admissionTime: '2026-08-09 08:00',
    dischargeTime: '2026-08-12 10:00',
    resultStatus: 'priority' as const,
    resultLabel: '需优先复核',
    issueSummary: '存在确定问题 2 项',
    latestQcTime: '2026-08-12 11:30',
  },
]

describe('QcRecordResultTable', () => {
  it('每份病历只渲染一行并使用后端三坐标 recordKey', () => {
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', rows },
    })

    const renderedRows = wrapper.findAll('tbody tr[data-record-key]')
    expect(renderedRows).toHaveLength(1)
    expect(renderedRows[0].attributes('data-record-key')).toBe(rows[0].recordKey)
  })

  it('固定展示七列，并按病历阶段显示实际时间字段', () => {
    const running = mount(QcRecordResultTable, { props: { carePhase: 'inpatient', rows } })
    const final = mount(QcRecordResultTable, { props: { carePhase: 'discharged', rows } })

    expect(running.findAll('thead th')).toHaveLength(7)
    expect(running.text()).toContain('入院时间')
    expect(running.text()).toContain('2026-08-09 08:00')
    expect(final.text()).toContain('出院时间')
    expect(final.text()).toContain('2026-08-12 10:00')
  })

  it('行点击和查看结果按钮发出同一个 recordKey', async () => {
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', rows },
    })

    await wrapper.find('tr[data-record-key]').trigger('click')
    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('open-result')).toEqual([[rows[0].recordKey], [rows[0].recordKey]])
  })

  it('通过横向滚动和不换行单元格保持窄屏表格可读', () => {
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', rows },
    })

    expect(wrapper.find('.qc-record-result-table__scroll').exists()).toBe(true)
    expect(wrapper.find('.qc-record-result-table__table').classes()).toContain(
      'qc-record-result-table__table',
    )
  })
})
