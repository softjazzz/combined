/* eslint-disable vue/one-component-per-file */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineComponent, nextTick, reactive } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { AxiosHeaders, type AxiosResponse } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { SPECIAL_RECORD_TYPES } from '@/api/specialRecordReports'
import SpecialRecordReportView from '@/views/qc/reports/SpecialRecordReportView.vue'
import StaffAnalysisView from '@/views/qc/reports/StaffAnalysisView.vue'
import ManualQualityReportPanel from '@/views/qc/reports/ManualQualityReportPanel.vue'
import WorkstationLayout from '@/components/layout/WorkstationLayout.vue'
import { syncSharedMessageCenterUnreadCount } from '@/views/workstation/useMessageCenter'

const authState = reactive({
  authenticated: true,
  user: {
    id: 'admin-fix-1',
    email: 'admin@medqc.com',
    institute_id: 'H1',
    department: '心内科',
    roles: ['admin', 'qc_manager'] as string[],
    is_demo_account: false,
  },
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get isAuthenticated() {
      return authState.authenticated
    },
    get user() {
      return authState.user.id ? authState.user : null
    },
    get userRoles() {
      return authState.user.roles
    },
    get userName() {
      return authState.user.email
    },
    hasRole(role: string) {
      return authState.user.roles.includes(role)
    },
    signOut: vi.fn(),
  }),
}))

vi.mock('@/components/layout/RuntimeBuildStatus.vue', () => ({
  default: { template: '<div class="runtime-build-status">v1</div>' },
}))
vi.mock('@/views/workstation-v4/components/GlobalAssistantHost.vue', () => ({
  default: { template: '<div />' },
}))
vi.mock('@/components/layout/WorkstationConfirmDialog.vue', () => ({
  default: { template: '<div />' },
}))

vi.mock('ant-design-vue', async () => {
  const actual = await vi.importActual<typeof import('ant-design-vue')>('ant-design-vue')
  return {
    ...actual,
    message: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
    DatePicker: {
      props: ['value'],
      emits: ['update:value'],
      template:
        '<input class="mock-date-picker" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    },
  }
})

function okResponse<T>(data: T) {
  return {
    status: 200,
    statusText: 'OK',
    data: { success: true, data },
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  } as AxiosResponse
}

function makeSpecialReportPayload() {
  return {
    scope: {
      institute_id: 'H1',
      discharged_from: '2025-11-26',
      discharged_to: '2026-11-25',
      record_type: 'death' as const,
      record_type_state: 'positive' as const,
      timezone: 'Asia/Shanghai' as const,
      archive_status: 'unverified' as const,
      result_source: 'frozen',
      classification_version_seq: 1,
    },
    summary: {
      cohort_total: 12,
      record_total: 3,
      unavailable_result_total: 0,
      unknown_type_total: 0,
      graded_total: 3,
      ungraded_total: 0,
      grade_ratio_denominator: 'graded_total' as const,
      known_result_total: 3,
      selected_unavailable_result_total: 0,
      defect_ratio_denominator: 'confirmed_auto_defect_total' as const,
    },
    types: SPECIAL_RECORD_TYPES.map((key) => ({
      key,
      label: key,
      count: 3,
      known_positive_total: 3,
      unknown_total: 0,
      status: 'known' as const,
    })),
    top_departments: [{ name: '心内科', count: 3 }],
    grade_distribution: [{ grade: '甲级', count: 3, ratio: 1 }],
    top_defects: [],
    score_standard: {
      status: 'configured' as const,
      standard_id: 'STD-1',
      standard_version_seq: 1,
      binding_version_seq: 1,
      standard_name: '专用评分标准',
    },
  }
}

function makeStaffReportPayload(overrides: Record<string, unknown> = {}) {
  return {
    period: 'this_month',
    period_label: '本月',
    range: { start: '2026-11-01T00:00:00Z', end: '2026-11-25T00:00:00Z' },
    scene: 'all',
    filters: {
      period: 'this_month',
      scene: 'all',
      institute_id: null,
      department: null,
      task_id: null,
      start_date: null,
      end_date: null,
      as_of: '2026-11-25T12:00:00Z',
    },
    filter_options: {
      departments: [{ institute_id: 'H1', department_name: '心内科' }],
      tasks: [{ task_id: 'task-1', task_name: '终末抽查' }],
    },
    filter_options_unavailable_reason: null,
    context_unavailable_count: 0,
    unavailable_reason: null,
    unavailable_metrics: {},
    summary: {
      active_staff_count: 1,
      record_reviewer_count: 1,
      record_review_count: 5,
      reviewed_case_count: 3,
      rechecked_case_count: 1,
      initial_count: 4,
      recheck_count: 1,
      avg_record_reviews_per_active_staff: 5,
      avg_reviewed_cases_per_reviewer: 3,
      avg_reviewed_cases_per_active_staff: 3,
      avg_rechecked_cases_per_active_staff: 1,
      avg_manual_defects_per_active_staff: 1,
      avg_rejected_defects_per_active_staff: 0,
      manual_defect_created_count: 1,
      manual_review_approved_count: 1,
      manual_review_rejected_count: 0,
      appeal_approved_count: 0,
      appeal_rejected_count: 0,
      urged_defect_count: 0,
      confirmed_defect_count: 2,
    },
    staff: [
      {
        user_id: 'u1',
        name: '张质控',
        rank: 1,
        record_review_count: 5,
        reviewed_case_count: 3,
        rechecked_case_count: 1,
        initial_count: 4,
        recheck_count: 1,
        manual_defect_created_count: 1,
        manual_review_approved_count: 1,
        manual_review_rejected_count: 0,
        appeal_approved_count: 0,
        appeal_rejected_count: 0,
        urged_defect_count: 0,
        confirmed_defect_count: 2,
      },
    ],
    ...overrides,
  }
}

function makeManualReportPayload(overrides: Record<string, unknown> = {}) {
  return {
    as_of: '2026-11-25T08:00:00Z',
    timezone: 'Asia/Shanghai',
    assumption: '已确认统计口径',
    filters: { start_date: '2026-11-01', end_date: '2026-11-25', scene: 'all' as const },
    summary: {
      entered: 1,
      review: { pending: 1, approved: 0, rejected: 0, unknown: 0 },
      rectification: { pending: 1, submitted: 0, approved: 0, rejected: 0, unassigned: 0, unknown: 0 },
    },
    filter_options: {
      institutes: ['H1'],
      departments: [{ institute_id: 'H1', department: '心内科' }],
      creators: [{ id: 'u1', name: '张质控' }],
      tasks: [{ id: 'T1', name: '抽查任务1' }],
    },
    items: [
      {
        id: 'D1',
        institute_id: 'H1',
        patient_id: 'P1',
        visit_id: 'V1',
        department: '心内科',
        creator_id: 'u1',
        creator_name: '张质控',
        scene: 'final',
        task_id: 'T1',
        task_name: '抽查任务1',
        task_record_id: 'TR1',
        run_number: 1,
        rule_name: '出院小结主诉与病程记录不一致缺陷',
        created_at: '2026-11-05T02:00:00Z',
        review_status: 'pending',
        rectification_status: 'pending',
        source_verified: true,
        root_job_id: 'J1',
        envelope_id: 'E1',
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
    ...overrides,
  }
}

function createAsyncReportRouter(initialPath: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/workstation-v5/reports/special-records',
        component: SpecialRecordReportView,
      },
      {
        path: '/workstation-v5/reports/staff-analysis',
        component: StaffAnalysisView,
      },
      {
        path: '/workstation-v5',
        component: WorkstationLayout,
        children: [
          { path: 'worklist', component: defineComponent({ template: '<div>病历池</div>' }) },
          { path: 'messages', component: defineComponent({ template: '<div>消息中心</div>' }) },
        ],
      },
    ],
  })
  // 模拟真实路由中的异步守卫，确保 router.replace 异步回流不会触发二次加载
  router.beforeEach(async (_to, _from, next) => {
    await Promise.resolve()
    next()
  })
  return { router, ready: () => router.push(initialPath).then(() => router.isReady()) }
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
  authState.authenticated = true
  authState.user.id = 'admin-fix-1'
  authState.user.institute_id = 'H1'
  authState.user.roles = ['admin', 'qc_manager']
  authState.user.is_demo_account = false
  syncSharedMessageCenterUnreadCount(null, { emitEvent: false })
})

afterEach(() => {
  syncSharedMessageCenterUnreadCount(null, { emitEvent: false })
  vi.restoreAllMocks()
})

describe('P1 #5b 特殊病历报表默认 365 天日期窗', () => {
  it('默认出院日期窗为近 365 天（起止差 364 天 <= 366 天后端上限），首屏命中历史出院特殊病历', async () => {
    const specialPayload = makeSpecialReportPayload()
    const reqSpy = vi.spyOn(ApiService, 'requestRaw').mockImplementation(async (cfg) => {
      const url = String(cfg.url || '')
      if (url.endsWith('/records') || url.endsWith('/defects')) {
        return okResponse({
          total: 0,
          page: 1,
          page_size: 20,
          items: [],
          scope: specialPayload.scope,
          score_standard: specialPayload.score_standard,
        })
      }
      return okResponse(specialPayload)
    })

    const { router, ready } = createAsyncReportRouter('/workstation-v5/reports/special-records')
    await ready()
    const wrapper = mount(SpecialRecordReportView, {
      global: {
        plugins: [router],
        stubs: {
          SpecialReportConfigDrawer: true,
          SpecialReportCharts: true,
          'a-select': {
            props: ['value', 'options'],
            emits: ['update:value'],
            template: '<select :value="value" />',
          },
        },
      },
    })
    await flushPromises()

    const summaryCall = reqSpy.mock.calls.find(
      (call) => String(call[0]?.url || '') === '/api/v1/quality-reports/special-records',
    )
    expect(summaryCall).toBeDefined()
    const params = summaryCall?.[0]?.params as Record<string, string>
    expect(params.discharged_from).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(params.discharged_to).toMatch(/^\d{4}-\d{2}-\d{2}$/)

    const fromMs = Date.parse(`${params.discharged_from}T00:00:00Z`)
    const toMs = Date.parse(`${params.discharged_to}T00:00:00Z`)
    const diffDays = Math.round((toMs - fromMs) / 86_400_000)
    expect(diffDays).toBe(364)
    expect(diffDays).toBeLessThanOrEqual(365)

    // 重置仍恢复 365 天默认窗口
    const dateInputs = wrapper.findAll('input.mock-date-picker')
    await dateInputs[0]!.setValue('2026-10-01')
    await dateInputs[1]!.setValue('2026-10-10')
    await wrapper.findAll('button').find((b) => b.text() === '重置')!.trigger('click')
    await flushPromises()
    const lastSummary = [...reqSpy.mock.calls]
      .reverse()
      .find((call) => String(call[0]?.url || '') === '/api/v1/quality-reports/special-records')
    const resetParams = lastSummary?.[0]?.params as Record<string, string>
    const resetDiffDays = Math.round(
      (Date.parse(`${resetParams.discharged_to}T00:00:00Z`) -
        Date.parse(`${resetParams.discharged_from}T00:00:00Z`)) /
        86_400_000,
    )
    expect(resetDiffDays).toBe(364)

    wrapper.unmount()
  })
})

describe('P1 #10a & #10b 质控员工作分析单请求与自定义日期取消周期高亮', () => {
  it('异步路由守卫下查询/切周期/自定义日期/重置均严格仅发 1 次请求，且自定义日期取消快捷周期高亮并清理 URL 过期 period', async () => {
    const reqSpy = vi.spyOn(ApiService, 'requestRaw').mockImplementation(async () =>
      okResponse(makeStaffReportPayload()),
    )

    const { router, ready } = createAsyncReportRouter('/workstation-v5/reports/staff-analysis')
    await ready()
    const wrapper = mount(StaffAnalysisView, {
      global: {
        plugins: [router],
        stubs: {
          ManualQualityReportPanel: { template: '<div data-testid="manual-panel" />' },
          ModernAppealWorkflowDrawer: true,
          RecordReviewWorkflowDrawer: true,
          'a-drawer': true,
        },
      },
    })
    await flushPromises()
    expect(reqSpy).toHaveBeenCalledTimes(1)

    const periodButtons = () => wrapper.findAll('.segmented')[0]!.findAll('button')

    // 1. 切换「上周」并查询 -> 严格仅发 1 次请求，URL 写入 period=last_week
    reqSpy.mockClear()
    await periodButtons()[1]!.trigger('click')
    expect(periodButtons()[1]!.classes()).toContain('is-active')
    await wrapper.get('.primary').trigger('click')
    await flushPromises()
    expect(reqSpy).toHaveBeenCalledTimes(1)
    expect(reqSpy.mock.calls[0]?.[0]?.params).toMatchObject({
      period: 'last_week',
      scene: 'all',
    })
    expect(router.currentRoute.value.query.period).toBe('last_week')

    // 2. 手动修改自定义起止日期并点击查询 -> 严格仅发 1 次请求、所有快捷周期取消高亮、URL 不再残留 period=last_week
    reqSpy.mockClear()
    await wrapper.get('[data-testid="staff-start-date"] input').setValue('2026-09-01')
    await wrapper.get('[data-testid="staff-end-date"] input').setValue('2026-09-30')
    await nextTick()
    for (const btn of periodButtons()) {
      expect(btn.classes()).not.toContain('is-active')
      expect(btn.attributes('aria-pressed')).toBe('false')
    }

    await wrapper.get('.primary').trigger('click')
    await flushPromises()
    expect(reqSpy).toHaveBeenCalledTimes(1)
    expect(reqSpy.mock.calls[0]?.[0]?.params).toMatchObject({
      period: 'this_month',
      scene: 'all',
      start_date: '2026-09-01',
      end_date: '2026-09-30',
    })
    expect(router.currentRoute.value.query.period).toBeUndefined()
    expect(router.currentRoute.value.query.start_date).toBe('2026-09-01')
    expect(router.currentRoute.value.query.end_date).toBe('2026-09-30')
    for (const btn of periodButtons()) {
      expect(btn.classes()).not.toContain('is-active')
      expect(btn.attributes('aria-pressed')).toBe('false')
    }

    // 3. 在自定义日期状态下点选「本周」快捷周期 -> 自动清空自定义日期并高亮「本周」，查询严格 1 次请求
    reqSpy.mockClear()
    await periodButtons()[0]!.trigger('click')
    expect(periodButtons()[0]!.classes()).toContain('is-active')
    await wrapper.get('.primary').trigger('click')
    await flushPromises()
    expect(reqSpy).toHaveBeenCalledTimes(1)
    expect(reqSpy.mock.calls[0]?.[0]?.params).toEqual({
      period: 'this_week',
      scene: 'all',
    })
    expect(router.currentRoute.value.query.period).toBe('this_week')
    expect(router.currentRoute.value.query.start_date).toBeUndefined()
    expect(router.currentRoute.value.query.end_date).toBeUndefined()

    // 4. 点击「重置」-> 严格仅发 1 次请求，恢复「本月」高亮且清理 URL
    reqSpy.mockClear()
    await wrapper.findAll('.filter-actions button').find((b) => b.text() === '重置')!.trigger('click')
    await flushPromises()
    expect(reqSpy).toHaveBeenCalledTimes(1)
    expect(periodButtons()[2]!.classes()).toContain('is-active')
    expect(router.currentRoute.value.query.period).toBeUndefined()

    // 5. 切到人工质控报表 Tab 不重复触发 staff-work 请求
    reqSpy.mockClear()
    await wrapper.get('[data-testid="staff-report-tab-manual"]').trigger('click')
    await flushPromises()
    expect(reqSpy).not.toHaveBeenCalled()
    expect(router.currentRoute.value.query.tab).toBe('manual')

    wrapper.unmount()
  })
})

describe('P1 #10a & #10c 人工质控报表单请求、1280px 操作列无裁切与分页避让悬浮助手', () => {
  it('挂载/查询/重置均严格仅发 1 次 GET /api/v1/manual-quality-reports 请求，不与日期预刷新重复并发', async () => {
    const reqSpy = vi.spyOn(ApiService, 'requestRaw').mockImplementation(async () =>
      okResponse(makeManualReportPayload()),
    )

    const wrapper = mount(ManualQualityReportPanel, {
      global: {
        stubs: {
          ManualDefectWorkflowDrawer: true,
          CaseRectificationCreate: true,
          'a-spin': { template: '<div><slot /></div>' },
          'a-table': {
            name: 'ATableStub',
            props: ['dataSource', 'columns', 'scroll', 'tableLayout'],
            template: '<div class="table-stub" />',
          },
          'a-pagination': true,
          'a-drawer': true,
          'a-descriptions': true,
          'a-descriptions-item': true,
        },
      },
    })
    await flushPromises()
    // 初始挂载（切换进入人工质控报表）仅发 1 次请求
    expect(reqSpy).toHaveBeenCalledTimes(1)

    // 表格取消 scroll.x = 1000 硬撑宽，采用 fixed 布局 + 合理列宽保证 1280px 下操作列完整可见
    const tableStub = wrapper.getComponent({ name: 'ATableStub' })
    expect(tableStub.props('scroll')).toBeUndefined()
    expect(tableStub.props('tableLayout')).toBe('fixed')
    const cols = tableStub.props('columns') as Array<{ title: string; width?: number }>
    expect(cols.at(-1)?.title).toBe('操作')
    const fixedWidthSum = cols.reduce((sum, col) => sum + (col.width ?? 0), 0)
    expect(fixedWidthSum).toBeLessThanOrEqual(780)

    // 点击查询严格仅发 1 次请求
    reqSpy.mockClear()
    await wrapper.findAll('select')[4]!.setValue('final')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(reqSpy).toHaveBeenCalledTimes(1)

    // 修改日期后点击重置：严格仅发 1 次请求（不额外并发 refreshOptionsForDateRange）
    const dateInputs = wrapper.findAll('input.mock-date-picker')
    await dateInputs[0]!.setValue('2026-09-01')
    await dateInputs[1]!.setValue('2026-09-15')
    await flushPromises()

    reqSpy.mockClear()
    await wrapper.findAll('button').find((b) => b.text() === '重置')!.trigger('click')
    await flushPromises()
    expect(reqSpy).toHaveBeenCalledTimes(1)

    // 样式检查：保留根网格 minmax(0, 1fr)，且底部分页栏右侧留白避让右下角悬浮智能助手
    const css = readFileSync(
      resolve(process.cwd(), 'src/views/qc/reports/styles/manual-quality-report.css'),
      'utf8',
    )
    expect(css).toMatch(/\.manual-report\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/)
    const pagerRule = css.match(/\.manual-pager\s*\{([^}]+)\}/)?.[1] || ''
    const paddingRightMatch = pagerRule.match(/padding:\s*[^;]*?\s+(\d+)px\s+[^;]*;/)
    expect(Number(paddingRightMatch?.[1] || 0)).toBeGreaterThanOrEqual(100)

    wrapper.unmount()
  })
})

describe('P2 侧栏折叠/展开防文字重叠与保留未读红点角标', () => {
  it('侧栏收起与展开保留 99+ 未读徽标，且品牌区与底部账号区具备 overflow/nowrap/min-width 裁切与平滑显隐保护', async () => {
    vi.spyOn(ApiService, 'isAuthenticated').mockReturnValue(true)
    vi.spyOn(ApiService, 'get').mockResolvedValue({
      success: true,
      data: { items: [], total: 120, unread_count: 120 },
    } as never)

    const { router, ready } = createAsyncReportRouter('/workstation-v5/worklist')
    await ready()

    const wrapper = mount(
      defineComponent({ template: '<router-view />' }),
      {
        global: {
          plugins: [router],
          stubs: {
            MqIcon: true,
            MqIconTile: true,
            'a-tooltip': { template: '<span><slot /></span>' },
            'a-dropdown': { template: '<div class="dropdown-stub"><slot /><slot name="overlay" /></div>' },
            'a-popover': { template: '<div><slot /></div>' },
            'a-menu': { template: '<div><slot /></div>' },
            'a-menu-item': { template: '<div><slot /></div>' },
            'a-menu-divider': true,
          },
        },
      },
    )
    await flushPromises()

    expect(wrapper.get('[data-testid="ws-message-unread-badge"]').text()).toBe('99+')
    expect(wrapper.find('.ws-brand__title').text()).toBe('病案质控系统')
    expect(wrapper.find('.ws-user__role').text()).toBe('系统管理员')

    // 收起侧栏：文字节点卸载，99+ 徽标完整保留
    await wrapper.get('.ws-sider__toggle').trigger('click')
    await nextTick()
    expect(wrapper.find('.ws-shell--collapsed').exists()).toBe(true)
    expect(wrapper.find('.ws-brand__copy').exists()).toBe(false)
    expect(wrapper.find('.ws-user__meta').exists()).toBe(false)
    expect(wrapper.get('[data-testid="ws-message-unread-badge"]').text()).toBe('99+')

    // 再次展开侧栏：文字与 99+ 徽标正常恢复
    await wrapper.get('.ws-sider__toggle').trigger('click')
    await nextTick()
    expect(wrapper.find('.ws-shell--collapsed').exists()).toBe(false)
    expect(wrapper.find('.ws-brand__title').text()).toBe('病案质控系统')
    expect(wrapper.find('.ws-user__role').text()).toBe('系统管理员')
    expect(wrapper.get('[data-testid="ws-message-unread-badge"]').text()).toBe('99+')

    // 样式防挤压/防重叠契约检查
    const layoutSource = readFileSync(
      resolve(process.cwd(), 'src/components/layout/WorkstationLayout.vue'),
      'utf8',
    )
    expect(layoutSource).toMatch(/\.ws-sider\s*\{[^}]*overflow:\s*hidden;/)
    expect(layoutSource).toMatch(/\.ws-sider__head\s*\{[^}]*min-width:\s*0;[^}]*overflow:\s*hidden;/)
    expect(layoutSource).toMatch(
      /\.ws-brand__copy\s*\{[^}]*min-width:\s*0;[^}]*overflow:\s*hidden;[^}]*white-space:\s*nowrap;/,
    )
    expect(layoutSource).toMatch(
      /\.ws-user\s*\{[^}]*min-width:\s*0;[^}]*overflow:\s*hidden;[^}]*white-space:\s*nowrap;/,
    )
    expect(layoutSource).toMatch(
      /\.ws-user__meta\s*\{[^}]*min-width:\s*0;[^}]*overflow:\s*hidden;[^}]*white-space:\s*nowrap;/,
    )
    expect(layoutSource).toMatch(
      /\.ws-user__role\s*\{[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis;[^}]*white-space:\s*nowrap;/,
    )
    expect(layoutSource).toContain('@keyframes ws-sider-label-in')

    wrapper.unmount()
  })
})
