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
  return mount(RecordQualityReportView, {
    global: {
      stubs: {
        'a-drawer': drawerStub,
        RecordRemediationAnalysisPanel: true,
        'a-tabs': {
          props: ['activeKey'],
          template:
            '<div><button data-testid="core-tab" @click="$emit(\'update:activeKey\', \'core\')">核心制度</button><slot /></div>',
        },
        'a-tab-pane': { template: '<div />' },
        CoreSystemReportPanel: {
          name: 'CoreSystemReportPanel',
          props: ['initialFilters'],
          template: '<div data-testid="core-panel">制度专题</div>',
        },
      },
    },
  })
}

describe('RecordQualityReportView', () => {
  it('四维排行用对应筛选下钻，未知分类可查看且导出不丢筛选', async () => {
    state.getReport.mockResolvedValue({ success: true, data: { ...report,
      top_categories: [{ name: '合成大类', defect_total: 2 }],
      top_types: [{ name: '合成类型', defect_total: 2 }],
      top_veto_rules: [{ name: 'LX0609-001', rule_id: 'LX0609-001', defect_total: 1 }],
      classification_unknown: { defect_category: 1, defect_type: 1 },
    } })
    state.getRecords.mockResolvedValue({ success: true, data: { total: 1, page: 1, page_size: 20, items: [] } })
    state.exportReport.mockResolvedValue({ success: false })
    const wrapper = render()
    await flush()
    await wrapper.get('.top-row').trigger('click')
    await flush()
    expect(state.getRecords).toHaveBeenLastCalledWith(expect.objectContaining({ defect_category: '合成大类' }))
    await wrapper.get('.drawer-actions button').trigger('click')
    expect(state.exportReport).toHaveBeenLastCalledWith(expect.objectContaining({ defect_category: '合成大类' }), 'records', undefined)
    const veto = wrapper.findAll('.top-head button').find((button) => button.text() === '单否')
    await veto?.trigger('click')
    await wrapper.get('.top-row').trigger('click')
    expect(state.getRecords).toHaveBeenLastCalledWith(expect.objectContaining({ rule_id: 'LX0609-001', has_veto: true }))
    const unknown = wrapper.findAll('.top-panel .notice button').find((button) => button.text().includes('类型未知'))
    await unknown?.trigger('click')
    expect(state.getRecords).toHaveBeenLastCalledWith(expect.objectContaining({ unknown_classification: 'defect_type' }))
    wrapper.unmount()
  })
  it('按真实等级展示比例并导出已显示列，使用已查询筛选', async () => {
    state.getReport.mockResolvedValue({ success: true, data: {
      ...report,
      kpis: { ...report.kpis, top_grade_name: '优秀' },
      grade_distribution: [{ grade: '优秀', count: 1 }, { grade: '待改进', count: 1 }],
      department_rows: [{ ...report.kpis, name: '合成科室', top_grade_total: 1,
        defect_total: 4, average_defect_total: 2, grade_rates: { 优秀: 0.5, 待改进: 0.5 } }],
    } })
    state.exportReport.mockResolvedValue({ success: false })
    const wrapper = render()
    await flush()
    expect(wrapper.text()).toContain('优秀病历数')
    expect(wrapper.text()).toContain('待改进占比')
    expect(wrapper.text()).toContain('50.0%')
    await wrapper.get('input[value="auto_defect_total"]').setValue(false)
    await wrapper.get('#report-department').setValue('尚未查询')
    const exportButton = wrapper.findAll('.page-head button').find((button) => button.text().includes('科室 CSV'))
    await exportButton?.trigger('click')
    expect(state.exportReport).toHaveBeenCalledWith(
      { scene: 'running', defect_source: 'all' }, 'departments',
      expect.arrayContaining(['top_grade_total', 'grade_rate:优秀', 'grade_rate:待改进', 'average_defect_total']),
    )
    expect(state.exportReport.mock.calls[0][2]).not.toContain('auto_defect_total')
    wrapper.unmount()
  })
  it('核心制度入口传已查询过滤，不传后续未查询的草稿', async () => {
    const wrapper = render()
    await flush()
    await wrapper.get('#report-department').setValue('内科')
    await wrapper.get('#report-doctor').setValue('合成医生')
    await wrapper.get('#report-from').setValue('2026-10-01T08:00')
    await wrapper.get('#report-to').setValue('2026-10-01T09:00')
    await wrapper.get('#report-source').setValue('manual')
    await wrapper.get('.filters .primary').trigger('click')
    await flush()
    await wrapper.get('#report-department').setValue('未查询科室')
    await wrapper.get('[data-testid="core-tab"]').trigger('click')
    expect(
      wrapper.findComponent({ name: 'CoreSystemReportPanel' }).props('initialFilters'),
    ).toEqual({
      scene: 'running',
      department: '内科',
      doctor: '合成医生',
      completed_from: '2026-10-01T08:00',
      completed_to: '2026-10-01T09:00',
      defect_source: 'manual',
    })
    wrapper.unmount()
  })
  it('opens the core-system report from the existing report tab', async () => {
    const wrapper = render()
    await flush()
    await wrapper.get('[data-testid="core-tab"]').trigger('click')
    expect(wrapper.find('[data-testid="core-panel"]').exists()).toBe(true)
    expect(wrapper.get('.page-head').isVisible()).toBe(false)
  })
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
    expect(wrapper.findAll('.data-panel').length).toBe(3)
  })

  it('serves the final scene as discharged cases with an unverified-archive notice', async () => {
    routeState.query.scene = 'final'
    state.getReport.mockResolvedValue({
      success: true,
      data: {
        ...report,
        scope: {
          scene: 'final',
          scope_basis: 'discharged_with_qc_result',
          archive_status: 'unverified',
        },
      },
    })
    const wrapper = render()
    await flush()
    expect(state.getReport).toHaveBeenCalledWith(expect.objectContaining({ scene: 'final' }))
    expect(wrapper.text()).toContain('未核验归档')
    expect(wrapper.get('[data-testid="archive-unverified"]').text()).toContain(
      '医院归档标记尚未接入',
    )
    expect(wrapper.findAll('.metric').length).toBeGreaterThan(0)
  })

  it('does not show the archive notice in running scene', async () => {
    const wrapper = render()
    await flush()
    expect(wrapper.find('[data-testid="archive-unverified"]').exists()).toBe(false)
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
