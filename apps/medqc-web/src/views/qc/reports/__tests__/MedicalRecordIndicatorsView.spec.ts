import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MedicalRecordIndicatorsView from '@/views/qc/reports/MedicalRecordIndicatorsView.vue'

const state = vi.hoisted(() => ({
  getReport: vi.fn(),
  getBreakdown: vi.fn(),
  getCases: vi.fn(),
  exportReport: vi.fn(),
}))
vi.mock('@/api/medicalRecordIndicators', () => ({
  getMedicalRecordIndicators: state.getReport,
  getMedicalRecordIndicatorBreakdown: state.getBreakdown,
  getMedicalRecordIndicatorCases: state.getCases,
  exportMedicalRecordIndicators: state.exportReport,
}))

const partial = {
  code: 'MER-TL-01',
  name: '入院记录24小时内完成率',
  formula: '按时完成 / 同期住院病例',
  numerator: '按时完成',
  denominator: '同期住院病例',
  data_source: 'LX0609-001',
  availability: 'partial',
  blocker: '当前仅为出院队列已核实子集',
  cohort_total: 3,
  eligible_total: 2,
  numerator_total: 1,
  not_applicable_total: 0,
  unknown_total: 1,
  verified_subset_rate: 50,
  official_rate: null,
  calculation_status: 'partial',
}
const blocked = {
  ...partial,
  code: 'MER-TQ-01',
  name: '出院患者病历2日归档率',
  data_source: '无',
  availability: 'blocked',
  blocker: '缺归档时间与工作日历；不得用出院时间代替',
  eligible_total: null,
  numerator_total: null,
  not_applicable_total: null,
  unknown_total: 3,
  verified_subset_rate: null,
  calculation_status: 'blocked',
}

async function flush() {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}

describe('MedicalRecordIndicatorsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.getReport.mockResolvedValue({
      success: true,
      data: {
        scope: {
          basis: 'discharged_case_cohort',
          description: '按出院日期筛选的病历队列',
          archive_status: 'unverified',
        },
        summary: { indicator_total: 27, partial_total: 2, blocked_total: 25, cohort_total: 3 },
        indicators: [partial, blocked],
      },
    })
    state.getBreakdown.mockResolvedValue({
      success: true,
      data: { items: [{ ...partial, name: '内科' }] },
    })
    state.getCases.mockResolvedValue({
      success: true,
      data: { total: 0, page: 1, page_size: 20, items: [] },
    })
  })

  it('separates verified subset rates from official rates and shows exact blockers', async () => {
    const wrapper = mount(MedicalRecordIndicatorsView)
    await flush()
    const text = wrapper.text()
    expect(text).toContain('已接真实来源2')
    expect(text).toContain('阻塞指标25')
    expect(text).toContain('50.00%')
    expect(text).toContain('官方率不会用已核实子集率替代')
    expect(text).toContain('不得用出院时间代替')
    expect(state.getBreakdown).toHaveBeenCalledWith(expect.anything(), 'MER-TL-01', 'department')
  })

  it('keeps unknown as an explicit case filter', async () => {
    const wrapper = mount(MedicalRecordIndicatorsView)
    await flush()
    await wrapper.get('select[aria-label="病例状态"]').setValue('unknown')
    await flush()
    expect(state.getCases).toHaveBeenLastCalledWith(expect.anything(), 'MER-TL-01', 'unknown', 1)
  })

  it('shows unknown source counts in summary and blocked breakdown', async () => {
    const wrapper = mount(MedicalRecordIndicatorsView)
    await flush()
    const row = wrapper.findAll('tbody tr').find((item) => item.text().includes('MER-TQ-01'))!
    expect(row.text()).toContain('分子 未知 / 已核实分母 未知 / 未知 3')
    state.getBreakdown.mockResolvedValue({
      success: true,
      data: { items: [{ ...blocked, name: '内科' }] },
    })
    await row.get('button').trigger('click')
    await flush()
    expect(wrapper.get('.distribution-grid').text()).toContain('未知 / 3')
    expect(wrapper.get('.distribution-grid').text()).not.toContain('0 / 3')
  })
})
