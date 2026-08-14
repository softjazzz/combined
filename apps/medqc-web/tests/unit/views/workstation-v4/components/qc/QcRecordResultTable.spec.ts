import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import QcRecordResultTable from '@/views/workstation-v4/components/qc/QcRecordResultTable.vue'

const rows = [
  {
    recordKey: '["H-1","P-1","V-1"]',
    instituteId: 'H-1',
    patientId: 'P-1',
    patientName: '患者甲',
    patientSex: '女',
    patientAge: 68,
    visitId: 'V-1',
    department: '重症医学科',
    bedNumber: '12 床',
    admissionTime: '2026-08-09 08:00',
    dischargeTime: '2026-08-12 10:00',
    resultStatus: 'priority' as const,
    resultLabel: '需优先复核',
    issueSummary: '存在确定问题 2 项',
    latestQcTime: '2026-08-12T11:30:45.123456',
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

  it('复用病历池的头像与患者主次信息层级', () => {
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', rows },
    })

    expect(wrapper.find('.qc-record-result-table__patient-cell').exists()).toBe(true)
    expect(wrapper.get('.qc-record-result-table__avatar').attributes('alt')).toBe('患者甲头像')
    expect(wrapper.get('.qc-record-result-table__patient-name').text()).toBe('患者甲')
    expect(wrapper.get('.qc-record-result-table__visit-line').text()).toContain('住院号：V-1')
  })

  it('支持逐行选择与当前页全选，并且勾选不会打开结果', async () => {
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', rows, selectedRecordKeys: [] },
    })

    await wrapper.get('input[aria-label="选择患者甲"]').setValue(true)
    expect(wrapper.emitted('update:selectedRecordKeys')).toEqual([[[rows[0].recordKey]]])
    expect(wrapper.emitted('open-result')).toBeUndefined()

    await wrapper.setProps({ selectedRecordKeys: [rows[0].recordKey] })
    await wrapper.get('input[aria-label="选择当前页全部病历"]').setValue(false)
    expect(wrapper.emitted('update:selectedRecordKeys')?.at(-1)).toEqual([[]])
  })

  it('固定展示选择列与七列业务字段，并按病历阶段显示实际时间字段', () => {
    const running = mount(QcRecordResultTable, { props: { carePhase: 'inpatient', rows } })
    const final = mount(QcRecordResultTable, { props: { carePhase: 'discharged', rows } })

    expect(running.findAll('thead th')).toHaveLength(8)
    expect(running.text()).toContain('入院时间')
    expect(running.text()).toContain('2026-08-09 08:00')
    expect(final.text()).toContain('出院时间')
    expect(final.text()).toContain('2026-08-12 10:00')
    expect(running.text()).toContain('2026-08-12 11:30')
    expect(running.text()).not.toContain('T11:30:45.123456')
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

  it('明确区分资料待核实、未质控和结果校验异常，且未知来源不伪装为资料缺失', () => {
    const wrapper = mount(QcRecordResultTable, {
      props: {
        carePhase: 'inpatient',
        rows: [
          {
            ...rows[0],
            recordKey: '["H","P","data-gap"]',
            resultStatus: 'data-gap' as const,
            resultLabel: '资料待核实',
            issueSummary: '待核实 3',
          },
          {
            ...rows[0],
            recordKey: '["H","P","not-run"]',
            resultStatus: 'not-run' as const,
            resultLabel: '未质控',
            issueSummary: '暂无结果',
            sourceLabel: '资料同步待核实' as const,
          },
          {
            ...rows[0],
            recordKey: '["H","P","technical"]',
            resultStatus: 'technical-error' as const,
            resultLabel: '结果校验异常',
            issueSummary: '请复核结果交付',
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('资料待核实')
    expect(wrapper.text()).toContain('未质控')
    expect(wrapper.text()).toContain('结果校验异常')
    expect(wrapper.text()).toContain('请复核结果交付')
    expect(wrapper.text()).not.toContain('来源未知')
    expect(wrapper.text()).toContain('资料同步待核实')
    expect(wrapper.text()).not.toContain('资料完整')
  })

  it('未质控按钮显示暂无结果，缺床位时不渲染占位副标题', () => {
    const wrapper = mount(QcRecordResultTable, {
      props: {
        carePhase: 'inpatient',
        rows: [
          {
            ...rows[0],
            bedNumber: '',
            resultStatus: 'not-run' as const,
            resultLabel: '未质控',
            issueSummary: '暂无结果',
          },
        ],
      },
    })

    expect(wrapper.get('button').text()).toBe('暂无结果')
    expect(wrapper.text()).not.toContain('床位待接入')
  })
})
