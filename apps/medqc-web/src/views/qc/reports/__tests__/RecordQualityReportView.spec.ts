import { mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RecordQualityReportView from '@/views/qc/reports/RecordQualityReportView.vue'

const state = vi.hoisted(() => ({
  getReport: vi.fn(),
  getRecords: vi.fn(),
  exportReport: vi.fn(),
  userId: 'user-1',
}))
const routeState = reactive({ query: { scene: 'running' } as { scene: string } })
vi.mock('vue-router', () => ({ useRoute: () => routeState, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return { id: state.userId }
    },
  }),
}))
vi.mock('@/api/qualityReports', () => ({
  getRecordQualityReport: state.getReport,
  getRecordQualityRecords: state.getRecords,
  exportRecordQualityReport: state.exportReport,
}))
vi.mock('ant-design-vue', () => ({ message: { error: vi.fn() } }))

const drawerStub = { props: ['open'], template: '<div v-if="open"><slot /></div>' }
const report = {
  scope: { scene: 'running' },
  score_standard: {
    status: 'no_standard',
    standard_id: null,
    standard_name: null,
    standard_updated_at: null,
  },
  source_status: { review: 'unavailable', manual_defect: 'unavailable' },
  kpis: {
    record_total: 3,
    qc_ready_total: 1,
    qc_unavailable_total: 0,
    scored_total: null,
    average_score: null,
    top_grade_rate: null,
    review_approved_total: null,
    auto_defect_total: 1,
    manual_defect_total: null,
    veto_defect_total: null,
  },
  grade_distribution: null,
  score_distribution: null,
  defect_level_distribution: null,
  document_distribution: null,
  top_rules: null,
  top_departments: null,
  top_doctors: null,
  top_documents: null,
  department_rows: [],
  doctor_rows: [],
  unavailable_dimensions: [],
}

async function flush() {
  await Promise.resolve()
  await nextTick()
  await Promise.resolve()
  await nextTick()
}
function render() {
  return mount(RecordQualityReportView, { global: { stubs: { 'a-drawer': drawerStub } } })
}

describe('RecordQualityReportView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    routeState.query.scene = 'running'
    state.userId = 'user-1'
    state.getReport.mockResolvedValue({ success: true, data: report })
  })

  it('shows the current inpatient scope and unavailable metrics honestly', async () => {
    const wrapper = render()
    await flush()
    expect(wrapper.text()).toContain('当前在院病历')
    expect(wrapper.text()).toContain('未配置评分标准')
    expect(wrapper.text()).toContain('人工缺陷')
    expect(wrapper.text()).toContain('不可用')
    expect(wrapper.findAll('.data-panel').length).toBe(2)
  })

  it('shows the archive blocker instead of discharged cases in final scene', async () => {
    routeState.query.scene = 'final'
    state.getReport.mockResolvedValue({
      success: false,
      status: 409,
      code: 'archive_scope_unverified',
    })
    const wrapper = render()
    await flush()
    expect(wrapper.get('[data-testid="report-error"]').text()).toContain('终末归档范围尚未核实')
    expect(wrapper.findAll('.metric')).toHaveLength(0)
  })

  it('ignores a late response after a newer refresh', async () => {
    let resolveOld: ((value: unknown) => void) | undefined
    state.getReport
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOld = resolve
          }),
      )
      .mockResolvedValueOnce({ success: false, code: 'range_too_large', message: '范围过大' })
    const wrapper = render()
    await wrapper.get('.page-head button').trigger('click')
    await flush()
    resolveOld?.({ success: true, data: report })
    await flush()
    expect(wrapper.get('[data-testid="report-error"]').text()).toContain('范围过大')
    expect(wrapper.findAll('.metric')).toHaveLength(0)
  })
})
