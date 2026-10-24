import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FrontpageQualityReportView from '@/views/qc/reports/FrontpageQualityReportView.vue'

const state = vi.hoisted(() => ({
  getReport: vi.fn(),
  getRecords: vi.fn(),
  exportReport: vi.fn(),
}))
vi.mock('@/api/frontpageQualityReport', () => ({
  getFrontpageQualityReport: state.getReport,
  getFrontpageQualityRecords: state.getRecords,
  exportFrontpageQualityReport: state.exportReport,
}))
vi.mock('ant-design-vue', () => ({ message: { error: vi.fn() } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 'manager' } }) }))

const drawerStub = {
  props: ['open', 'width', 'rootStyle'],
  template: '<div v-if="open"><slot /></div>',
}
const metrics = {
  case_total: 3,
  problem_case_total: 2,
  problem_rate: 0.6667,
  frontpage_case_total: 2,
  coding_case_total: 2,
  noncoding_defect_total: 2,
  coding_defect_total: 2,
  noncoding_problem_case_total: 1,
  coding_problem_case_total: 2,
}
const report = {
  scope: { sources: ['frontpage_formal_qc', 'coding_qc'] },
  kpis: metrics,
  sources: [
    {
      source_key: 'frontpage_formal_qc',
      label: '非编码（首页质控）',
      severity_distribution: [{ severity: 'error', defect_total: 1 }],
      category_distribution: [{ category: 'required', defect_total: 1 }],
      top_rules: [{ rule_code: 'FP-1', rule_name: '主诊断必填', defect_total: 1 }],
    },
    {
      source_key: 'coding_qc',
      label: '编码（编码质控）',
      severity_distribution: [],
      category_distribution: [],
      top_rules: [{ rule_code: 'CR-1', rule_name: '编码格式', defect_total: 2 }],
    },
  ],
  department_rows: [{ department: '内科', ...metrics, case_total: 2, problem_rate: 1 }],
}
const recordsPage = {
  page: 1,
  page_size: 20,
  total: 1,
  items: [
    {
      institute_id: 'LX',
      patient_id: 'p3',
      visit_id: 'v1',
      patient_name: '病例p3',
      department: '内科',
      doctor: '甲医生',
      frontpage_analysis_date: null,
      frontpage_defect_total: null,
      coding_analysis_date: '2026-09-20T02:00:00',
      coding_defect_total: 1,
    },
  ],
}

async function flush() {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}
function render() {
  return mount(FrontpageQualityReportView, { global: { stubs: { 'a-drawer': drawerStub } } })
}

describe('FrontpageQualityReportView', () => {
  it('下钻抽屉宽度不超过窄窗口', async () => {
    const wrapper = render()
    await flush()
    expect(wrapper.findComponent(drawerStub).props('width')).toBe('min(900px, 100vw)')
    expect(wrapper.findComponent(drawerStub).props('rootStyle')).toEqual({ zIndex: 1100 })
  })

  beforeEach(() => {
    vi.clearAllMocks()
    state.getReport.mockResolvedValue({ success: true, data: report })
    state.getRecords.mockResolvedValue({ success: true, data: recordsPage })
  })

  it('shows coding and non-coding totals and the department rows', async () => {
    const wrapper = render()
    await flush()
    const text = wrapper.text()
    expect(text).toContain('问题病案率 66.7%')
    expect(text).toContain('非编码缺陷')
    expect(text).toContain('编码缺陷')
    expect(text).toContain('主诊断必填')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
  })

  it('switches source and drills down by rule with the matching source filter', async () => {
    const wrapper = render()
    await flush()
    const codingTab = wrapper
      .findAll('.segmented button')
      .find((button) => button.text().startsWith('编码'))
    await codingTab!.trigger('click')
    await wrapper.find('.top-row').trigger('click')
    await flush()
    expect(state.getRecords).toHaveBeenCalledWith(
      expect.objectContaining({ source: 'coding', rule_code: 'CR-1', page: 1 }),
    )
    // 该来源没有结果时显示“未质控”，不显示 0。
    expect(wrapper.text()).toContain('未质控')
    expect(wrapper.text()).toContain('1 条缺陷')
  })

  it('explains an undeployed data source instead of showing zeros', async () => {
    state.getReport.mockResolvedValue({ success: false, status: 503, code: 'schema_unavailable' })
    const wrapper = render()
    await flush()
    expect(wrapper.get('[data-testid="report-error"]').text()).toContain('首页质控数据源未部署')
    expect(wrapper.findAll('.metric')).toHaveLength(0)
  })

  it('rejects an inverted time window before requesting', async () => {
    const wrapper = render()
    await flush()
    state.getReport.mockClear()
    await wrapper.get('#fp-from').setValue('2026-09-30T00:00')
    await wrapper.get('#fp-to').setValue('2026-09-01T00:00')
    const query = wrapper.findAll('button').find((button) => button.text().includes('查询'))
    await query!.trigger('click')
    expect(state.getReport).not.toHaveBeenCalled()
  })
})
