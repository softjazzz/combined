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
  it('紧凑复核模式为五列，合并患者科室信息并保留完整提示与摘要', () => {
    const issueSummary = '确定问题 2 · 待核实 18 · 自定义说明'
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', compactReview: true, rows: [{ ...rows[0], issueSummary }] },
    })
    expect(wrapper.findAll('thead th').map((item) => item.text())).toEqual([
      '',
      '患者 / 科室',
      '问题摘要',
      '最近质控',
      '预览',
    ])
    expect(wrapper.findAll('tbody td')).toHaveLength(5)
    expect(wrapper.get('.qc-record-result-table__compact-meta').attributes('title')).toBe(
      'V-1 · 重症医学科 · 12 床',
    )
    expect(wrapper.get('.qc-record-result-table__avatar').attributes('alt')).toBe('患者甲头像')
    expect(wrapper.get('.qc-record-result-table__summary').attributes('title')).toBe(issueSummary)
    expect(
      wrapper.findAll('.qc-record-result-table__summary-item').map((item) => item.text()),
    ).toEqual(['确定问题 2', '待核实 18', '自定义说明'])
    expect(wrapper.text()).not.toContain('2026-08-09 08:00')
    expect(wrapper.text()).toContain('2026-08-12 11:30')
  })

  it('紧凑列表的当前预览与批量勾选独立，鼠标和键盘勾选不打开预览', async () => {
    const wrapper = mount(QcRecordResultTable, {
      props: {
        carePhase: 'inpatient',
        compactReview: true,
        activeRecordKey: rows[0].recordKey,
        rows,
      },
    })
    const row = wrapper.get('tr[data-record-key]')
    expect(row.classes()).toContain('qc-record-result-table__row--active')
    expect(row.classes()).not.toContain('qc-record-result-table__row--selected')
    const checkbox = wrapper.get('tbody input')
    await checkbox.trigger('click')
    await checkbox.trigger('change')
    await checkbox.trigger('keydown', { key: ' ' })
    await checkbox.trigger('keydown', { key: 'Enter' })
    await checkbox.setValue(true)
    expect(wrapper.emitted('open-result')).toBeUndefined()
    expect(wrapper.emitted('update:selectedRecordKeys')?.at(-1)).toEqual([[rows[0].recordKey]])
    await wrapper.setProps({ selectedRecordKeys: [rows[0].recordKey], activeRecordKey: undefined })
    expect(row.classes()).not.toContain('qc-record-result-table__row--active')
    expect(row.classes()).toContain('qc-record-result-table__row--selected')
    await row.trigger('click')
    await wrapper.get('button[aria-label="查看病历预览"]').trigger('click')
    expect(wrapper.emitted('open-result')).toEqual([[rows[0].recordKey], [rows[0].recordKey]])
  })

  it('紧凑空态跨五列，默认空态仍跨七列', () => {
    const compact = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', compactReview: true, rows: [] },
    })
    const normal = mount(QcRecordResultTable, { props: { carePhase: 'inpatient', rows: [] } })
    expect(compact.get('tbody td').attributes('colspan')).toBe('5')
    expect(normal.get('tbody td').attributes('colspan')).toBe('7')
  })

  it('运行页只按展示分隔符分组摘要，保留原文和未知说明，不影响终末页', () => {
    const issueSummary = '确定问题 2 · 待核实 18 · 待判断 1 · 自定义说明'
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', rows: [{ ...rows[0], issueSummary }] },
    })
    expect(
      wrapper.findAll('.qc-record-result-table__summary-item').map((item) => item.text()),
    ).toEqual(['确定问题 2', '待核实 18', '待判断 1', '自定义说明'])
    expect(wrapper.get('.qc-record-result-table__summary').attributes('title')).toBe(issueSummary)
    const finalView = mount(QcRecordResultTable, {
      props: { carePhase: 'discharged', rows: [{ ...rows[0], issueSummary }] },
    })
    expect(finalView.find('.qc-record-result-table__summary-item').exists()).toBe(false)
    expect(finalView.get('.qc-record-result-table__summary').text()).toBe(issueSummary)
  })

  it('每份病历只渲染一行并使用后端三坐标 recordKey', () => {
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', rows },
    })

    const renderedRows = wrapper.findAll('tbody tr[data-record-key]')
    expect(renderedRows).toHaveLength(1)
    expect(renderedRows[0].attributes('data-record-key')).toBe(rows[0].recordKey)
  })

  it('运行病历使用专属外观并保留患者头像，住院号保留完整悬停文本', () => {
    const wrapper = mount(QcRecordResultTable, {
      props: {
        carePhase: 'inpatient',
        rows: [{ ...rows[0], visitId: 'LONG-VISIT-ID-202608090001' }],
      },
    })

    expect(wrapper.classes()).toContain('qc-record-result-table--inpatient')
    expect(wrapper.get('.qc-record-result-table__avatar').attributes('alt')).toBe('患者甲头像')
    expect(wrapper.find('.qc-record-result-table__visit-label').exists()).toBe(false)
    expect(wrapper.get('.qc-record-result-table__patient-name').text()).toBe('患者甲')
    expect(wrapper.get('.qc-record-result-table__visit-id').attributes('title')).toBe(
      'LONG-VISIT-ID-202608090001',
    )
    expect(wrapper.get('.qc-record-result-table__summary').text()).toBe(rows[0].issueSummary)
  })

  it('出院病历保留头像、住院号标签及已有结果按钮样式钩子', () => {
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'discharged', rows },
    })

    expect(wrapper.classes()).not.toContain('qc-record-result-table--inpatient')
    expect(wrapper.find('.qc-record-result-table__patient-cell').exists()).toBe(true)
    expect(wrapper.get('.qc-record-result-table__avatar').attributes('alt')).toBe('患者甲头像')
    expect(wrapper.get('.qc-record-result-table__patient-name').text()).toBe('患者甲')
    expect(wrapper.get('.qc-record-result-table__visit-line').text()).toContain('住院号：V-1')
    expect(wrapper.get('button').classes()).toContain(
      'qc-record-result-table__result-button--available',
    )
  })

  it('支持逐行选择与当前页全选，并且勾选不会打开结果', async () => {
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', rows, selectedRecordKeys: [] },
    })

    await wrapper.get('input[aria-label="选择患者甲"]').setValue(true)
    expect(wrapper.emitted('update:selectedRecordKeys')).toEqual([[[rows[0].recordKey]]])
    expect(wrapper.emitted('open-result')).toBeUndefined()

    await wrapper.setProps({ selectedRecordKeys: [rows[0].recordKey] })
    expect(wrapper.get('tr[data-record-key]').attributes('aria-selected')).toBe('true')
    expect(wrapper.get('tr[data-record-key]').classes()).toContain(
      'qc-record-result-table__row--selected',
    )
    await wrapper.get('input[aria-label="选择当前页全部病历"]').setValue(false)
    expect(wrapper.emitted('update:selectedRecordKeys')?.at(-1)).toEqual([[]])
  })

  it('固定展示选择列与七列业务字段，并按病历阶段显示实际时间字段', () => {
    const running = mount(QcRecordResultTable, { props: { carePhase: 'inpatient', rows } })
    const final = mount(QcRecordResultTable, { props: { carePhase: 'discharged', rows } })

    expect(running.findAll('thead th')).toHaveLength(7)
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

  it('运行病历保留整行键盘打开结果行为', async () => {
    const wrapper = mount(QcRecordResultTable, {
      props: { carePhase: 'inpatient', rows },
    })

    const row = wrapper.get('tr[data-record-key]')
    expect(row.attributes('tabindex')).toBe('0')
    await row.trigger('keydown', { key: 'Enter' })
    await row.trigger('keydown', { key: ' ' })
    expect(wrapper.emitted('open-result')).toEqual([[rows[0].recordKey], [rows[0].recordKey]])
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

    expect(wrapper.text()).toContain('待核实 3')
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
