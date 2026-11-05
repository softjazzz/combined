import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RecordPoolPreviewPanel from '@/views/workstation-v4/components/workbench/RecordPoolPreviewPanel.vue'
import type { WorkbenchRow } from '@/views/workstation-v4/components/workbench/BatchTablePanel.vue'

const row: WorkbenchRow = {
  id: 'record-1',
  recordKey: 'key-1',
  patientName: '患者甲',
  visitId: 'V-1',
  department: '神经内科',
  stageStatus: '待处理',
  riskReason: '',
  updatedAt: '2026-08-08',
  admissionDate: '2026-08-01',
  dischargeDate: '2026-08-08',
  hospitalizationStatus: 'discharged',
  isDemo: false,
  latestQcSummary: {
    status: 'ready',
    completedAt: '2026-08-08T01:20:00Z',
    statusCounts: { non_compliant: 2, data_gap: 1 },
  },
}

describe('RecordPoolPreviewPanel 病历池右侧预览', () => {
  it('未选中病历时展示引导文案', () => {
    const wrapper = mount(RecordPoolPreviewPanel, { props: { row: null } })
    expect(wrapper.text()).toContain('点击左侧任一病历')
    expect(wrapper.find('[data-testid="record-pool-preview-open"]').exists()).toBe(false)
  })

  it('展示住院信息，并与运行/终末质控列表共用质控结果口径', () => {
    const wrapper = mount(RecordPoolPreviewPanel, { props: { row } })
    const text = wrapper.text()
    expect(text).toContain('患者甲')
    expect(text).toContain('住院号 V-1')
    expect(text).toContain('已出院')
    expect(text).toContain('神经内科')
    expect(text).toContain('7 天')
    expect(text).toContain('需优先复核')
    expect(text).toContain('确定问题 2 · 待核实 1')
  })

  it('查看病历与质控此病历沿用病历池原有事件', async () => {
    const wrapper = mount(RecordPoolPreviewPanel, { props: { row } })
    await wrapper.get('[data-testid="record-pool-preview-open"]').trigger('click')
    await wrapper.get('[data-testid="record-pool-preview-qc"]').trigger('click')
    expect(wrapper.emitted('open-record')).toEqual([['key-1']])
    expect(wrapper.emitted('run-qc')).toEqual([['key-1']])
  })

  it('住院状态与列表同口径：无核验状态时按出院日期推断；无年份日期不推算住院天数', () => {
    const wrapper = mount(RecordPoolPreviewPanel, {
      props: {
        row: {
          ...row,
          hospitalizationStatus: undefined,
          admissionDate: '03-29',
          dischargeDate: '04-02',
        },
      },
    })
    const text = wrapper.text()
    expect(text).toContain('已出院')
    expect(text).toContain('04-02')
    expect(text).toContain('住院天数—')
  })
})


it('CDM日期精度和未确认在院状态原样展示', () => {
  const wrapper = mount(RecordPoolPreviewPanel, { props: { row: {
    ...row, sourceId: 'independent_cdm', hospitalizationStatus: 'unknown',
    admissionPrecision: 'date', dischargeDate: '', materialCompleteness: '首页未观察到',
  } } })
  expect(wrapper.text()).toContain('状态未知')
  expect(wrapper.text()).toContain('2026-08-01（仅日期）')
  expect(wrapper.text()).toContain('独立CDM · 首页未观察到')
  expect(wrapper.text()).not.toContain('00:00:00')
})
