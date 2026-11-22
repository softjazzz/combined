import { setDatePickerValue } from '../../../../../tests/utils/setDatePickerValue'
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
const replace = vi.fn(async ({ query }: { query: { scene: string } }) => {
  route.query.scene = query.scene
})

vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace }) }))
vi.mock('@/stores/auth', async () => {
  const { reactive } = await import('vue')
  state.auth = reactive(state.authState)
  return {
    useAuthStore: () => ({
      get user() {
        return state.auth.userId ? { id: state.auth.userId } : null
      },
      get userRoles() {
        return state.auth.roles
      },
    }),
  }
})
vi.mock('@/api/staffAnalysis', () => ({
  getStaffAnalysis: state.getReport,
  getStaffAnalysisDetails: state.getDetails,
  exportStaffAnalysis: state.exportReport,
}))

const appliedFilters = {
  period: 'this_month',
  scene: 'all',
  institute_id: null,
  department: null,
  task_id: null,
  start_date: null,
  end_date: null,
  as_of: '2026-09-28T23:59:59+08:00',
}
const allReport = {
  period: 'this_month',
  period_label: '本月',
  range: { start: '2026-09-01T00:00:00Z', end: '2026-09-28T00:00:00Z' },
  scene: 'all',
  filters: appliedFilters,
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
    active_staff_count: 2,
    record_reviewer_count: 2,
    record_review_count: 4,
    reviewed_case_count: 2,
    initial_count: 3,
    recheck_count: 1,
    avg_record_reviews_per_active_staff: 2,
    avg_reviewed_cases_per_reviewer: 1.5,
    avg_reviewed_cases_per_active_staff: 1.5,
    avg_rechecked_cases_per_active_staff: 0.5,
    avg_manual_defects_per_active_staff: 0.5,
    avg_rejected_defects_per_active_staff: 0,
    rechecked_case_count: 1,
    urged_defect_count: 1,
    confirmed_defect_count: null,
    manual_defect_created_count: 1,
    manual_review_approved_count: 1,
    manual_review_rejected_count: 0,
    appeal_approved_count: 0,
    appeal_rejected_count: 1,
  },
  staff: [
    {
      user_id: 'staff-1',
      name: '张质控',
      rank: 1,
      record_review_count: 3,
      reviewed_case_count: 2,
      initial_count: 2,
      recheck_count: 1,
      rechecked_case_count: 1,
      urged_defect_count: 1,
      confirmed_defect_count: null,
      manual_defect_created_count: 1,
      manual_review_approved_count: 1,
      manual_review_rejected_count: 0,
      appeal_approved_count: 0,
      appeal_rejected_count: 1,
    },
  ],
}
const detailsPage = {
  filters: appliedFilters,
  metric: 'reviewed_case_count',
  user_id: 'staff-1',
  total: 21,
  page: 1,
  page_size: 20,
  unavailable_reason: null,
  items: [
    {
      event_id: 'event-1',
      event_type: 'record_review',
      occurred_at: '2026-09-27T01:00:00Z',
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      task_id: 'task-1',
      department: '心内科',
      stage: 'initial',
      decision: 'approved',
      defect_id: null,
      appeal_id: null,
    },
  ],
}

const mounted: VueWrapper[] = []
function render(): VueWrapper {
  const wrapper = mount(StaffAnalysisView, {
    global: {
      stubs: {
        RecordReviewWorkflowDrawer: {
          name: 'RecordReviewWorkflowDrawer',
          props: ['open', 'reviewId'],
          emits: ['changed', 'close'],
          template: '<section v-if="open" class="record-review-workflow" />',
        },
        ModernAppealWorkflowDrawer: {
          name: 'ModernAppealWorkflowDrawer',
          props: ['open', 'appealId'],
          emits: ['changed', 'close'],
          template: '<section v-if="open" class="modern-appeal-workflow" />',
        },
        ManualQualityReportPanel: {
          name: 'ManualQualityReportPanel',
          template: '<section class="manual-report-entry">人工报表入口</section>',
        },
        'a-drawer': {
          name: 'ReportDrawerStub',
          props: ['open', 'title', 'width', 'rootStyle'],
          emits: ['update:open'],
          template:
            '<aside v-if="open" class="drawer"><h3>{{ title }}</h3><button class="drawer-close" @click="$emit(\'update:open\', false)">关闭</button><slot /></aside>',
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
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

describe('StaffAnalysisView', () => {
  it('病历审核事件直达精确历史，操作后刷新原筛选，换角色清空抽屉', async () => {
    const wrapper = render()
    await settle()
    await wrapper.get('[aria-label="查看张质控的审核次数明细"]').trigger('click')
    await settle()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '查看审核')!
      .trigger('click')
    const workflow = wrapper.getComponent({ name: 'RecordReviewWorkflowDrawer' })
    expect(workflow.props('reviewId')).toBe('event-1')
    const previous = state.getReport.mock.calls.at(-1)?.[0]
    workflow.vm.$emit('changed')
    await settle()
    expect(state.getReport.mock.calls.at(-1)?.[0]).toEqual(previous)
    state.auth.roles = ['doctor']
    await settle()
    expect(wrapper.find('.record-review-workflow').exists()).toBe(false)
  })
  it('申诉事件下钻到指定历史，审核成功刷新原工作分析，换账号关闭抽屉', async () => {
    state.getDetails.mockResolvedValue({
      success: true,
      data: {
        ...detailsPage,
        metric: 'appeal_approved_count',
        total: 1,
        items: [
          {
            ...detailsPage.items[0],
            event_type: 'appeal_approved',
            appeal_id: 'appeal-1',
            stage: null,
            decision: 'approved',
          },
        ],
      },
    })
    const wrapper = render()
    await settle()
    await wrapper.get('[aria-label="查看张质控的申诉通过明细"]').trigger('click')
    await settle()
    expect(wrapper.text()).toContain('申诉审核')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '查看申诉')!
      .trigger('click')
    const workflow = wrapper.findComponent({ name: 'ModernAppealWorkflowDrawer' })
    expect(workflow.props('appealId')).toBe('appeal-1')
    const calls = state.getReport.mock.calls.length
    workflow.vm.$emit('changed')
    await settle()
    expect(state.getReport.mock.calls.length).toBe(calls + 1)
    state.auth.userId = 'another-user'
    await settle()
    expect(wrapper.find('.modern-appeal-workflow').exists()).toBe(false)
  })
  it('人工报表操作成功后用原筛选刷新工作分析', async () => {
    const wrapper = render()
    await flushPromises()
    const before = state.getReport.mock.calls[0][0]
    await wrapper.get('[data-testid="staff-report-tab-manual"]').trigger('click')
    await flushPromises()
    wrapper.getComponent({ name: 'ManualQualityReportPanel' }).vm.$emit('changed')
    await flushPromises()
    expect(state.getReport).toHaveBeenCalledTimes(2)
    expect(state.getReport.mock.calls[1][0]).toEqual(before)
  })
  it('下钻抽屉宽度不超过窄窗口', async () => {
    const wrapper = render()
    await settle()
    expect(wrapper.findComponent({ name: 'ReportDrawerStub' }).props('width')).toBe(
      'min(880px, 100vw)',
    )
    expect(wrapper.findComponent({ name: 'ReportDrawerStub' }).props('rootStyle')).toEqual({
      zIndex: 1100,
    })
  })

  it('初审缺陷缺少明细时显示未知并分页展示已知部分', async () => {
    const coverage = {
      initial_review_count: 3,
      covered_initial_review_count: 1,
      missing_initial_review_count: 2,
      known_defect_count: 21,
    }
    state.getReport.mockResolvedValue({
      success: true,
      data: {
        ...allReport,
        defect_snapshot_coverage: coverage,
        staff: [{ ...allReport.staff[0], defect_snapshot_coverage: coverage }],
      },
    })
    state.getDetails.mockResolvedValue({
      success: true,
      data: {
        ...detailsPage,
        metric: 'confirmed_defect_count',
        total: null,
        known_total: 21,
        total_complete: false,
        unavailable_reason: 'snapshot_incomplete',
        defect_snapshot_coverage: coverage,
        items: [
          {
            ...detailsPage.items[0],
            event_type: 'initial_defect_confirmed',
            source: 'auto',
            defect_id: 'rule-1',
          },
        ],
      },
    })
    const wrapper = render()
    await settle()
    expect(wrapper.get('[data-testid="staff-defect-snapshot-coverage"]').text()).toContain(
      '可核实初审记录 1 / 3',
    )
    expect(wrapper.get('[data-testid="staff-defect-snapshot-coverage"]').text()).toContain(
      '排名未知',
    )
    await wrapper.get('[aria-label="查看张质控的质控缺陷明细"]').trigger('click')
    await settle()
    expect(wrapper.get('[data-testid="staff-details-known-only"]').text()).toContain(
      '总数未知，可核实 21',
    )
    expect(wrapper.get('.drawer').text()).toContain('自动 · rule-1')
    await wrapper.findAll('.pager button')[1]!.trigger('click')
    await settle()
    expect(state.getDetails).toHaveBeenLastCalledWith(
      'staff-1',
      expect.objectContaining({ as_of: appliedFilters.as_of }),
      'confirmed_defect_count',
      2,
      20,
    )
    await wrapper.get('[data-testid="staff-rank-metric"]').setValue('confirmed_defect_count')
    await settle()
    expect(state.getReport).toHaveBeenLastCalledWith(
      { period: 'this_month', scene: 'all' },
      'confirmed_defect_count',
    )
  })
  it('缺少已知明细总数时不显示为零', async () => {
    const coverage = {
      initial_review_count: 1,
      covered_initial_review_count: 0,
      missing_initial_review_count: 1,
      known_defect_count: 0,
    }
    state.getReport.mockResolvedValue({
      success: true,
      data: {
        ...allReport,
        staff: [{ ...allReport.staff[0], defect_snapshot_coverage: coverage }],
      },
    })
    state.getDetails.mockResolvedValue({
      success: true,
      data: {
        ...detailsPage,
        metric: 'confirmed_defect_count',
        total: null,
        total_complete: false,
        unavailable_reason: 'snapshot_incomplete',
      },
    })
    const wrapper = render()
    await settle()
    await wrapper.get('[aria-label="查看张质控的质控缺陷明细"]').trigger('click')
    await settle()
    expect(wrapper.get('[data-testid="staff-details-known-only"]').text()).toContain('可核实 未知')
    expect(wrapper.find('.pager').exists()).toBe(false)
  })
  it('展示四项人均并向服务端查询所选排名指标', async () => {
    const wrapper = render()
    await settle()
    for (const label of ['人均质控病历', '人均复审病历', '人均人工缺陷', '人均驳回缺陷']) {
      expect(wrapper.text()).toContain(label)
    }
    await wrapper.get('[data-testid="staff-rank-metric"]').setValue('urged_defect_count')
    await settle()
    expect(state.getReport).toHaveBeenLastCalledWith(
      { period: 'this_month', scene: 'all' },
      'urged_defect_count',
    )
  })
  it('复用既有报告页面的人工质控tab入口', async () => {
    const wrapper = render()
    await settle()
    expect(wrapper.get('[data-testid="staff-report-tab-staff"]').attributes('aria-selected')).toBe(
      'true',
    )
    expect(wrapper.get('.mq-page-head .mq-page-title').text()).toBe('质控员工作分析')
    await wrapper.get('[data-testid="staff-report-tab-manual"]').trigger('click')
    await settle()
    expect(wrapper.get('.manual-report-entry').text()).toContain('人工报表入口')
    expect(wrapper.get('[data-testid="staff-report-tab-manual"]').classes()).toContain('is-active')
    expect(wrapper.get('.mq-page-head .mq-page-title').text()).toBe('人工质控报表')
    // 人工页签不显示质控员导出，避免误导出另一张报表
    expect(wrapper.get('.mq-page-head').text()).not.toContain('导出 CSV')
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
    expect(wrapper.get('[data-testid="staff-context-unavailable"]').text()).toContain(
      '2 条工作事件',
    )
    const departmentOptions = wrapper
      .get('[data-testid="staff-department-filter"]')
      .findAll('option')
    expect(departmentOptions.map((option) => option.text())).toEqual([
      '全部科室',
      '心内科（H1）',
      '心内科（H2）',
    ])
    expect(wrapper.text()).toContain('全局三坐标去重')
  })

  it('submits composite department, task and paired Shanghai calendar dates without substring identity', async () => {
    const wrapper = render()
    await settle()
    await wrapper
      .get('[data-testid="staff-department-filter"]')
      .setValue(JSON.stringify(['H2', '心内科']))
    await wrapper.get('[data-testid="staff-task-filter"]').setValue('task-1')
    await setDatePickerValue(wrapper.get('[data-testid="staff-start-date"] input'), '2026-09-01')
    await setDatePickerValue(wrapper.get('[data-testid="staff-end-date"] input'), '2026-09-28')
    await wrapper.get('.primary').trigger('click')
    await settle()
    expect(state.getReport).toHaveBeenLastCalledWith({
      period: 'this_month',
      scene: 'all',
      institute_id: 'H2',
      department: '心内科',
      task_id: 'task-1',
      start_date: '2026-09-01',
      end_date: '2026-09-28',
    })

    await wrapper.get('[data-testid="staff-start-date"] .ant-picker-clear').trigger('mouseup')
    await wrapper.get('[data-testid="staff-end-date"] .ant-picker-clear').trigger('mouseup')
    await wrapper.get('.primary').trigger('click')
    await settle()
    expect(state.getReport).toHaveBeenLastCalledWith({
      period: 'this_month',
      scene: 'all',
      institute_id: 'H2',
      department: '心内科',
      task_id: 'task-1',
    })
  })

  it('rejects an unpaired or reversed custom date range before requesting', async () => {
    const wrapper = render()
    await settle()
    await setDatePickerValue(wrapper.get('[data-testid="staff-start-date"] input'), '2026-09-28')
    await wrapper.get('.primary').trigger('click')
    expect(wrapper.get('.filter-error').text()).toContain('必须同时填写')
    expect(state.getReport).toHaveBeenCalledTimes(1)
    await setDatePickerValue(wrapper.get('[data-testid="staff-end-date"] input'), '2026-09-01')
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
      'staff-1',
      { period: 'this_month', scene: 'all', as_of: appliedFilters.as_of },
      'reviewed_case_count',
      1,
      20,
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
      'staff-1',
      expect.objectContaining({ as_of: appliedFilters.as_of }),
      'reviewed_case_count',
      2,
      20,
    )
  })

  it('keeps scene-unattributable appeal values unknown and does not make them drilldown buttons', async () => {
    state.getReport.mockResolvedValue({
      success: true,
      data: {
        ...allReport,
        scene: 'running',
        filters: { ...appliedFilters, scene: 'running' },
        unavailable_metrics: {
          appeal_approved_count: 'scene_not_attributable',
          appeal_rejected_count: 'scene_not_attributable',
        },
        summary: { ...allReport.summary, appeal_approved_count: null, appeal_rejected_count: null },
        staff: [
          { ...allReport.staff[0], appeal_approved_count: null, appeal_rejected_count: null },
        ],
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
        unavailable_metrics: {
          appeal_approved_count: 'filter_not_attributable',
          appeal_rejected_count: 'filter_not_attributable',
        },
        summary: { ...allReport.summary, appeal_approved_count: null, appeal_rejected_count: null },
        staff: [
          { ...allReport.staff[0], appeal_approved_count: null, appeal_rejected_count: null },
        ],
      },
    })
    const wrapper = render()
    await settle()
    const appealMetric = wrapper
      .findAll('.metric')
      .find((metric) => metric.text().includes('申诉处理'))
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
    state.getReport
      .mockImplementationOnce(() => oldReport.promise)
      .mockResolvedValueOnce({
        success: true,
        data: { ...allReport, period: 'this_week', period_label: '本周', staff: [] },
      })
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
    state.getReport
      .mockImplementationOnce(() => oldReport.promise)
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
    await wrapper
      .findAll('.head-actions button')
      .find((button) => button.text().includes('导出 CSV'))!
      .trigger('click')
    expect(state.exportReport).toHaveBeenCalledWith({
      period: 'this_month',
      scene: 'all',
      as_of: appliedFilters.as_of,
    })
    state.auth.userId = 'admin-2'
    await settle()
    delayed.resolve({ success: true, data: new Blob(['late']) })
    await settle()
    expect(click).not.toHaveBeenCalled()
    expect(createObjectURL).not.toHaveBeenCalled()
  })
})
