import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import StaffAnalysisView from '@/views/qc/reports/StaffAnalysisView.vue'

const state = vi.hoisted(() => ({
  authState: { userId: 'admin-1', roles: ['qc_manager'] as string[] },
  auth: null as unknown as { userId: string; roles: string[] },
  getReport: vi.fn(),
  getDetails: vi.fn(),
  exportReport: vi.fn(),
}))
const route = reactive({ path: '/dashboard/qc/reports/staff-analysis', query: { scene: 'all' } })
const replace = vi.fn(async ({ query }: { query: { scene: string } }) => { route.query.scene = query.scene })

vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace }) }))
vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  state.auth = reactive(state.authState)
  return { useAuthStore: () => ({
    get user() { return state.auth.userId ? { id: state.auth.userId } : null },
    get userRoles() { return state.auth.roles },
  }) }
})
vi.mock('@/api/staffAnalysis', () => ({
  getStaffAnalysis: state.getReport,
  getStaffAnalysisDetails: state.getDetails,
  exportStaffAnalysis: state.exportReport,
}))

const appliedFilters = {
  period: 'this_month', scene: 'all', institute_id: null, department: null, task_id: null,
  start_date: null, end_date: null, as_of: '2026-09-28T23:59:59+08:00',
}
const allReport = {
  period: 'this_month', period_label: '本月',
  range: { start: '2026-09-01T00:00:00Z', end: '2026-09-28T00:00:00Z' },
  scene: 'all', filters: appliedFilters,
  filter_options: {
    departments: [
      { institute_id: 'H1', department_name: '心内科' },
      { institute_id: 'H2', department_name: '心内科' },
    ],
    tasks: [{ task_id: 'task-1', task_name: '九月抽查' }],
  },
  filter_options_unavailable_reason: null,
  context_unavailable_count: 2,
  unavailable_reason: null,
  unavailable_metrics: {},
  summary: {
    active_staff_count: 2, record_reviewer_count: 2, record_review_count: 4,
    reviewed_case_count: 2, initial_count: 3, recheck_count: 1,
    avg_record_reviews_per_active_staff: 2, avg_reviewed_cases_per_reviewer: 1.5,
    avg_reviewed_cases_per_active_staff: 1.5, avg_rechecked_cases_per_active_staff: 0.5,
    avg_manual_defects_per_active_staff: 0.5, avg_rejected_defects_per_active_staff: 0,
    rechecked_case_count: 1, urged_defect_count: 1,
    manual_defect_created_count: 1, manual_review_approved_count: 1,
    manual_review_rejected_count: 0, appeal_approved_count: 0, appeal_rejected_count: 1,
  },
  staff: [{
    user_id: 'staff-1', name: '张质控', rank: 1,
    record_review_count: 3, reviewed_case_count: 2, initial_count: 2, recheck_count: 1,
    rechecked_case_count: 1, urged_defect_count: 1,
    manual_defect_created_count: 1, manual_review_approved_count: 1,
    manual_review_rejected_count: 0, appeal_approved_count: 0, appeal_rejected_count: 1,
  }],
}
const detailsPage = {
  filters: appliedFilters, metric: 'reviewed_case_count', user_id: 'staff-1', total: 21, page: 1, page_size: 20,
  unavailable_reason: null,
  items: [{
    event_id: 'event-1', event_type: 'record_review', occurred_at: '2026-09-27T01:00:00Z',
    institute_id: 'H1', patient_id: 'P1', visit_id: 'V1', task_id: 'task-1', department: '心内科',
    stage: 'initial', decision: 'approved', defect_id: null, appeal_id: null,
  }],
}

const mounted: VueWrapper[] = []
function render(): VueWrapper {
  const wrapper = mount(StaffAnalysisView, {
    global: {
      stubs: {
        'a-tabs': { props: ['activeKey'], emits: ['update:activeKey'], template: '<nav><button class="manual-tab" @click="$emit(\'update:activeKey\', \'manual\')">人工质控报表</button><slot /></nav>' },
        'a-tab-pane': true,
        ManualQualityReportPanel: { template: '<section class="manual-report-entry">人工报表入口</section>' },
        'a-drawer': {
          props: ['open', 'title'],
          emits: ['update:open'],
          template: '<aside v-if="open" class="drawer"><h3>{{ title }}</h3><button class="drawer-close" @click="$emit(\'update:open\', false)">关闭</button><slot /></aside>',
        },
      },
    },
  })
  mounted.push(wrapper)
  return wrapper
}
async function settle(): Promise<void> {
  await flushPromises()
  await nextTick()
}
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('StaffAnalysisView', () => {
  it('展示四项人均并向服务端查询所选排名指标', async () => {
    const wrapper = render()
    await settle()
    for (const label of ['人均质控病历', '人均复审病历', '人均人工缺陷', '人均驳回缺陷']) {
      expect(wrapper.text()).toContain(label)
    }
    await wrapper.get('[data-testid="staff-rank-metric"]').setValue('urged_defect_count')
    await settle()
    expect(state.getReport).toHaveBeenLastCalledWith(
      { period: 'this_month', scene: 'all' }, 'urged_defect_count',
    )
  })
  it('复用既有报告页面的人工质控tab入口', async () => {
    const wrapper = render()
    await settle()
    await wrapper.get('.manual-tab').trigger('click')
    await settle()
    expect(wrapper.get('.manual-report-entry').text()).toContain('人工报表入口')
  })
  beforeEach(() => {
    vi.clearAllMocks()
    state.auth.userId = 'admin-1'
    state.auth.roles = ['qc_manager']
    route.query.scene = 'all'
    state.getReport.mockResolvedValue({ success: true, data: allReport })
    state.getDetails.mockResolvedValue({ success: true, data: detailsPage })
    state.exportReport.mockResolvedValue({ success: true, data: new Blob(['csv']) })
  })
  afterEach(() => mounted.splice(0).forEach((wrapper) => wrapper.unmount()))

  it('shows verified counts, context warning and same-name departments with institute identity', async () => {
    const wrapper = render()
    await settle()
    expect(state.getReport).toHaveBeenCalledWith({ period: 'this_month', scene: 'all' })
    expect(wrapper.text()).toContain('张质控')
    expect(wrapper.get('[data-testid="staff-context-unavailable"]').text()).toContain('2 条工作事件')
    const departmentOptions = wrapper.get('[data-testid="staff-department-filter"]').findAll('option')
    expect(departmentOptions.map((option) => option.text())).toEqual(['全部科室', '心内科（H1）', '心内科（H2）'])
    expect(wrapper.text()).toContain('全局三坐标去重')
  })

  it('submits composite department, task and paired Shanghai calendar dates without substring identity', async () => {
    const wrapper = render()
    await settle()
    await wrapper.get('[data-testid="staff-department-filter"]').setValue(JSON.stringify(['H2', '心内科']))
    await wrapper.get('[data-testid="staff-task-filter"]').setValue('task-1')
    await wrapper.get('[data-testid="staff-start-date"]').setValue('2026-09-01')
    await wrapper.get('[data-testid="staff-end-date"]').setValue('2026-09-28')
    await wrapper.get('.primary').trigger('click')
    await settle()
    expect(state.getReport).toHaveBeenLastCalledWith({
      period: 'this_month', scene: 'all', institute_id: 'H2', department: '心内科',
      task_id: 'task-1', start_date: '2026-09-01', end_date: '2026-09-28',
    })
  })

  it('rejects an unpaired or reversed custom date range before requesting', async () => {
    const wrapper = render()
    await settle()
    await wrapper.get('[data-testid="staff-start-date"]').setValue('2026-09-28')
    await wrapper.get('.primary').trigger('click')
    expect(wrapper.get('.filter-error').text()).toContain('必须同时填写')
    expect(state.getReport).toHaveBeenCalledTimes(1)
    await wrapper.get('[data-testid="staff-end-date"]').setValue('2026-09-01')
    await wrapper.get('.primary').trigger('click')
    expect(wrapper.get('.filter-error').text()).toContain('不能晚于')
    expect(state.getReport).toHaveBeenCalledTimes(1)
  })

  it('opens connected metric details with frozen as_of and supports real pagination controls', async () => {
    state.getDetails
      .mockResolvedValueOnce({ success: true, data: detailsPage })
      .mockResolvedValueOnce({ success: true, data: { ...detailsPage, page: 2, items: [] } })
    const wrapper = render()
    await settle()
    await wrapper.findAll('.metric-link')[0]!.trigger('click')
    await settle()
    expect(state.getDetails).toHaveBeenCalledWith(
      'staff-1', { period: 'this_month', scene: 'all', as_of: appliedFilters.as_of },
      'reviewed_case_count', 1, 20,
    )
    expect(wrapper.get('.drawer').text()).toContain('H1 / P1 / V1')
    expect(wrapper.get('.drawer').text()).toContain('心内科')
    expect(wrapper.get('.drawer').text()).toContain('初审')
    expect(wrapper.get('.drawer').text()).toContain('通过')
    expect(wrapper.get('.drawer').text()).not.toContain('initial')
    expect(wrapper.get('.drawer').text()).not.toContain('approved')
    await wrapper.findAll('.pager button')[1]!.trigger('click')
    await settle()
    expect(state.getDetails).toHaveBeenLastCalledWith(
      'staff-1', expect.objectContaining({ as_of: appliedFilters.as_of }), 'reviewed_case_count', 2, 20,
    )
  })

  it('keeps scene-unattributable appeal values unknown and does not make them drilldown buttons', async () => {
    state.getReport.mockResolvedValue({
      success: true,
      data: {
        ...allReport, scene: 'running', filters: { ...appliedFilters, scene: 'running' },
        unavailable_metrics: { appeal_approved_count: 'scene_not_attributable', appeal_rejected_count: 'scene_not_attributable' },
        summary: { ...allReport.summary, appeal_approved_count: null, appeal_rejected_count: null },
        staff: [{ ...allReport.staff[0], appeal_approved_count: null, appeal_rejected_count: null }],
      },
    })
    route.query.scene = 'running'
    const wrapper = render()
    await settle()
    const cells = wrapper.get('tbody tr').findAll('td')
    expect(cells.at(-3)?.text()).toBe('未知')
    expect(cells.at(-2)?.text()).toBe('未知')
    expect(wrapper.findAll('.metric-link')).toHaveLength(9)
  })

  it('labels filter-unattributable appeal metrics without treating them as zero', async () => {
    state.getReport.mockResolvedValue({
      success: true,
      data: {
        ...allReport,
        unavailable_metrics: { appeal_approved_count: 'filter_not_attributable', appeal_rejected_count: 'filter_not_attributable' },
        summary: { ...allReport.summary, appeal_approved_count: null, appeal_rejected_count: null },
        staff: [{ ...allReport.staff[0], appeal_approved_count: null, appeal_rejected_count: null }],
      },
    })
    const wrapper = render()
    await settle()
    const appealMetric = wrapper.findAll('.metric').find((metric) => metric.text().includes('申诉处理'))
    expect(appealMetric?.text()).toContain('未知')
    expect(appealMetric?.text()).toContain('当前筛选无法可靠归属')
  })

  it.each([
    ['task_source_unavailable', '任务选项暂不可用'],
    ['department_source_unavailable', '科室选项暂不可用'],
    ['unknown_source', '筛选选项暂不可用'],
  ])('labels unavailable options by their source: %s', async (reason, expected) => {
    state.getReport.mockResolvedValue({
      success: true,
      data: { ...allReport, filter_options_unavailable_reason: reason },
    })
    const wrapper = render()
    await settle()
    expect(wrapper.get('.filter-hint').text()).toBe(expected)
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
  })

  it('discards a late report after the applied period filter changes', async () => {
    const oldReport = deferred<{ success: boolean; data: typeof allReport }>()
    state.getReport.mockImplementationOnce(() => oldReport.promise)
      .mockResolvedValueOnce({ success: true, data: { ...allReport, period: 'this_week', period_label: '本周', staff: [] } })
    const wrapper = render()
    await wrapper.findAll('.segmented')[0]!.findAll('button')[0]!.trigger('click')
    await wrapper.get('.primary').trigger('click')
    await settle()
    oldReport.resolve({ success: true, data: allReport })
    await settle()
    expect(state.getReport).toHaveBeenLastCalledWith({ period: 'this_week', scene: 'all' })
    expect(wrapper.text()).toContain('本周')
    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
  })

  it('discards late report and detail responses after account switch or logout', async () => {
    const oldReport = deferred<{ success: boolean; data: typeof allReport }>()
    state.getReport.mockImplementationOnce(() => oldReport.promise)
      .mockResolvedValueOnce({ success: true, data: { ...allReport, staff: [] } })
    const wrapper = render()
    state.auth.userId = 'admin-2'
    await settle()
    oldReport.resolve({ success: true, data: allReport })
    await settle()
    expect(wrapper.findAll('tbody tr')).toHaveLength(0)

    state.getReport.mockResolvedValue({ success: true, data: allReport })
    state.auth.userId = 'admin-1'
    await settle()
    const oldDetails = deferred<{ success: boolean; data: typeof detailsPage }>()
    state.getDetails.mockImplementationOnce(() => oldDetails.promise)
    await wrapper.findAll('.metric-link')[0]!.trigger('click')
    state.auth.userId = ''
    await settle()
    oldDetails.resolve({ success: true, data: detailsPage })
    await settle()
    expect(wrapper.find('.drawer').exists()).toBe(false)
    expect(wrapper.text()).toContain('请先登录')
  })

  it('exports the frozen report snapshot and suppresses a late download after account change', async () => {
    const createObjectURL = vi.fn(() => 'blob:staff')
    const revokeObjectURL = vi.fn()
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const delayed = deferred<{ success: boolean; data: Blob }>()
    state.exportReport.mockImplementationOnce(() => delayed.promise)
    const wrapper = render()
    await settle()
    await wrapper.findAll('.head-actions button')[1]!.trigger('click')
    expect(state.exportReport).toHaveBeenCalledWith({
      period: 'this_month', scene: 'all', as_of: appliedFilters.as_of,
    })
    state.auth.userId = 'admin-2'
    await settle()
    delayed.resolve({ success: true, data: new Blob(['late']) })
    await settle()
    expect(click).not.toHaveBeenCalled()
    expect(createObjectURL).not.toHaveBeenCalled()
  })
})
