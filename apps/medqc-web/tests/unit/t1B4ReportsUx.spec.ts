import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineComponent, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { AxiosHeaders, type AxiosResponse } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { SPECIAL_RECORD_TYPES } from '@/api/specialRecordReports'
import RecordQualityReportView from '@/views/qc/reports/RecordQualityReportView.vue'
import SpecialRecordReportView from '@/views/qc/reports/SpecialRecordReportView.vue'
import FrontpageQualityReportView from '@/views/qc/reports/FrontpageQualityReportView.vue'
import StaffAnalysisView from '@/views/qc/reports/StaffAnalysisView.vue'
import SpecialReportCharts from '@/views/qc/reports/SpecialReportCharts.vue'

const routeState = reactive({
  path: '/dashboard/qc/reports/test',
  query: {} as Record<string, string>,
})
const routerReplace = vi.fn(async (loc: { path?: string; query?: Record<string, string> }) => {
  routeState.query = { ...(loc.query || {}) }
})
const routerPush = vi.fn(async (loc: { path?: string; query?: Record<string, string> }) => {
  routeState.query = { ...(loc.query || {}) }
})

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ replace: routerReplace, push: routerPush }),
}))

const authUser = reactive({
  id: 'u-b4',
  institute_id: 'H1',
  department: '内科',
  roles: ['qc_manager'] as string[],
  is_demo_account: false,
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return authUser.id ? authUser : null
    },
    get userRoles() {
      return authUser.roles
    },
    hasRole(role: string) {
      return authUser.roles.includes(role)
    },
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  DatePicker: {
    props: ['value'],
    emits: ['update:value'],
    template:
      '<input class="mock-date-picker" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
  },
}))

vi.mock('vue-echarts', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      name: 'VChart',
      props: {
        option: { type: Object, required: true },
        autoresize: { type: Boolean, default: false },
      },
      setup(props, { attrs }) {
        return () =>
          h('div', {
            class: 'mock-vchart',
            'aria-label': attrs['aria-label'] as string | undefined,
            'data-title': (props.option as { title?: { text?: string } }).title?.text || '',
          })
      },
    }),
  }
})

const SelectStub = defineComponent({
  name: 'ASelect',
  props: ['value', 'options', 'allowClear'],
  emits: ['update:value'],
  template: '<select class="mock-select" />',
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

function readReportFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), 'src/views/qc/reports', relativePath), 'utf8')
}

function makeRecordQualityReport(recordTotal: number) {
  return {
    scope: { scene: 'running' as const },
    score_standard: {
      status: 'no_standard' as const,
      standard_id: null,
      standard_name: null,
      standard_updated_at: null,
    },
    source_status: { review: 'available' as const, manual_defect: 'available' as const },
    kpis: {
      record_total: recordTotal,
      qc_ready_total: recordTotal,
      qc_unavailable_total: 0,
      scored_total: 0,
      average_score: null,
      top_grade_rate: null,
      review_approved_total: 0,
      auto_defect_total: recordTotal > 0 ? 3 : 0,
      manual_defect_total: 0,
      manual_defect_rejected_total: 0,
      veto_defect_total: 0,
      veto_record_total: 0,
    },
    grade_distribution: [],
    score_distribution: [],
    defect_level_distribution: [],
    defect_type_distribution: [],
    document_distribution: [],
    top_rules: [],
    top_categories: recordTotal > 0 ? [{ name: '完整性', defect_total: 2 }] : [],
    top_types: [],
    top_veto_rules: [],
    top_documents: [],
    classification_unknown: null,
    department_rows:
      recordTotal > 0
        ? [
            {
              name: '心内科',
              record_total: recordTotal,
              qc_ready_total: recordTotal,
              average_score: null,
              top_grade_rate: null,
              review_approved_total: 0,
              reviewed_total: 0,
              top_grade_total: 0,
              defect_total: 3,
              average_defect_total: 1,
              auto_defect_total: 3,
              manual_defect_total: 0,
              veto_defect_total: 0,
              veto_record_total: 0,
              records_with_defect: 1,
            },
          ]
        : [],
    doctor_rows: [],
    unavailable_dimensions: [],
  }
}

function makeFrontpageReport(caseTotal: number) {
  return {
    scope: { sources: ['frontpage_formal_qc', 'coding_qc'] },
    kpis: {
      case_total: caseTotal,
      problem_case_total: caseTotal > 0 ? 1 : 0,
      problem_rate: caseTotal > 0 ? 0.5 : null,
      frontpage_case_total: caseTotal,
      coding_case_total: caseTotal,
      noncoding_defect_total: caseTotal > 0 ? 2 : 0,
      coding_defect_total: caseTotal > 0 ? 1 : 0,
      noncoding_problem_case_total: caseTotal > 0 ? 1 : 0,
      coding_problem_case_total: caseTotal > 0 ? 1 : 0,
    },
    sources: [
      {
        source_key: 'frontpage_formal_qc' as const,
        label: '非编码（首页质控）',
        severity_distribution: caseTotal > 0 ? [{ severity: 'error', defect_total: 2 }] : [],
        category_distribution: caseTotal > 0 ? [{ category: 'required', defect_total: 2 }] : [],
        top_rules: [],
      },
      {
        source_key: 'coding_qc' as const,
        label: '编码（编码质控）',
        severity_distribution: [],
        category_distribution: [],
        top_rules: [],
      },
    ],
    department_rows: [],
  }
}

function makeSpecialReport() {
  return {
    scope: {
      institute_id: 'H1',
      discharged_from: '2026-10-01',
      discharged_to: '2026-10-30',
      record_type: 'death' as const,
      record_type_state: 'positive' as const,
      timezone: 'Asia/Shanghai' as const,
      archive_status: 'unverified' as const,
      result_source: 'frozen',
      classification_version_seq: 1,
    },
    summary: {
      cohort_total: 10,
      record_total: 2,
      unavailable_result_total: 0,
      unknown_type_total: 0,
      graded_total: 2,
      ungraded_total: 0,
      grade_ratio_denominator: 'graded_total' as const,
      known_result_total: 2,
      selected_unavailable_result_total: 0,
      defect_ratio_denominator: 'confirmed_auto_defect_total' as const,
    },
    types: SPECIAL_RECORD_TYPES.map((key) => ({
      key,
      label: key,
      count: 2,
      known_positive_total: 2,
      unknown_total: 0,
      status: 'known' as const,
    })),
    top_departments: [{ name: '内科', count: 2 }],
    grade_distribution: [{ grade: '甲级', count: 2, ratio: 1 }],
    top_defects: [
      {
        rule_id: 'R1',
        name: '主诉缺失',
        severity: '严重',
        category: '内涵',
        type: '完整性',
        document: '入院记录',
        is_veto: false,
        count: 2,
        ratio: 1,
      },
    ],
    score_standard: {
      status: 'configured' as const,
      standard_id: 'STD-1',
      standard_version_seq: 1,
      binding_version_seq: 1,
      standard_name: '专用标准',
    },
  }
}

function makeStaffReport() {
  return {
    period: 'this_month',
    period_label: '本月',
    range: { start: '2026-10-01T00:00:00Z', end: '2026-10-30T00:00:00Z' },
    scene: 'all',
    filters: {
      period: 'this_month',
      scene: 'all',
      institute_id: null,
      department: null,
      task_id: null,
      start_date: null,
      end_date: null,
      as_of: '2026-10-30T23:59:59+08:00',
    },
    filter_options: { departments: [], tasks: [] },
    filter_options_unavailable_reason: null,
    context_unavailable_count: 0,
    unavailable_reason: null,
    unavailable_metrics: {},
    summary: {
      active_staff_count: 1,
      record_reviewer_count: 1,
      record_review_count: 2,
      reviewed_case_count: 2,
      initial_count: 2,
      recheck_count: 0,
      avg_record_reviews_per_active_staff: 2,
      avg_reviewed_cases_per_reviewer: 2,
      avg_reviewed_cases_per_active_staff: 2,
      avg_rechecked_cases_per_active_staff: 0,
      avg_manual_defects_per_active_staff: 0,
      avg_rejected_defects_per_active_staff: 0,
      rechecked_case_count: 0,
      urged_defect_count: 0,
      confirmed_defect_count: 1,
      manual_defect_created_count: 0,
      manual_review_approved_count: 0,
      manual_review_rejected_count: 0,
      appeal_approved_count: 0,
      appeal_rejected_count: 0,
    },
    staff: [
      {
        user_id: 's1',
        name: '王质控',
        rank: 1,
        record_review_count: 2,
        reviewed_case_count: 2,
        initial_count: 2,
        recheck_count: 0,
        rechecked_case_count: 0,
        urged_defect_count: 0,
        confirmed_defect_count: 1,
        manual_defect_created_count: 0,
        manual_review_approved_count: 0,
        manual_review_rejected_count: 0,
        appeal_approved_count: 0,
        appeal_rejected_count: 0,
      },
    ],
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
  localStorage.clear()
  routeState.path = '/dashboard/qc/reports/test'
  routeState.query = {}
  authUser.id = 'u-b4'
  authUser.institute_id = 'H1'
  authUser.roles = ['qc_manager']
  authUser.is_demo_account = false
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('T1-B4 1. 消除 4 处嵌套 <main> 地标', () => {
  it('四大质量报表根节点均改为 <section>，无嵌套 <main>', async () => {
    const specialReport = makeSpecialReport()
    vi.spyOn(ApiService, 'requestRaw').mockImplementation(async (cfg) => {
      const url = String(cfg.url || '')
      if (url.includes('frontpage-quality')) return okResponse(makeFrontpageReport(2))
      if (url.includes('special-records/records')) {
        return okResponse({
          total: 0,
          page: 1,
          page_size: 20,
          items: [],
          scope: specialReport.scope,
          score_standard: specialReport.score_standard,
        })
      }
      if (url.includes('special-records/defects')) {
        return okResponse({
          total: 0,
          page: 1,
          page_size: 20,
          items: [],
          scope: specialReport.scope,
          score_standard: specialReport.score_standard,
        })
      }
      if (url.includes('special-records')) return okResponse(specialReport)
      if (url.includes('staff-work')) return okResponse(makeStaffReport())
      return okResponse(makeRecordQualityReport(2))
    })

    const views = [
      mount(RecordQualityReportView, {
        global: {
          stubs: {
            'a-drawer': true,
            CoreSystemReportPanel: true,
            RecordRemediationAnalysisPanel: true,
          },
        },
      }),
      mount(SpecialRecordReportView, {
        global: {
          stubs: {
            'a-select': SelectStub,
            'a-drawer': true,
            SpecialReportConfigDrawer: true,
            SpecialReportCharts: true,
          },
        },
      }),
      mount(FrontpageQualityReportView, {
        global: { stubs: { 'a-drawer': true } },
      }),
      mount(StaffAnalysisView, {
        global: {
          stubs: {
            'a-drawer': true,
            ManualQualityReportPanel: true,
            ModernAppealWorkflowDrawer: true,
            RecordReviewWorkflowDrawer: true,
          },
        },
      }),
    ]
    await flushPromises()

    for (const wrapper of views) {
      expect(wrapper.find('main').exists()).toBe(false)
      expect(wrapper.element.tagName).toBe('SECTION')
      expect(wrapper.classes()).toContain('mq-page')
      wrapper.unmount()
    }
  })
})

describe('T1-B4 2. 1280px–1440px 宽表首列固定与非关键列收窄', () => {
  it('staff-analysis.css 固定前两列（排名/操作人）并配置实底色与右侧阴影', () => {
    const css = readReportFile('styles/staff-analysis.css')
    expect(css).toMatch(/\.staff-table\s*\{[^}]*overflow:\s*visible;/)
    expect(css).toMatch(
      /\.staff-table th:nth-child\(-n \+ 2\),\s*\.staff-table td:nth-child\(-n \+ 2\)\s*\{[^}]*position:\s*sticky;/,
    )
    expect(css).toMatch(/\.staff-table th:nth-child\(1\),\s*\.staff-table td:nth-child\(1\)\s*\{[^}]*left:\s*0;/)
    expect(css).toMatch(
      /\.staff-table th:nth-child\(2\),\s*\.staff-table td:nth-child\(2\)\s*\{[^}]*left:\s*68px;[^}]*box-shadow:/,
    )
    expect(css).toMatch(/background:\s*var\(--mq-bg-surface,\s*#ffffff\)/)
    expect(css).toMatch(/\.staff-table thead th:nth-child\(-n \+ 2\)\s*\{[^}]*background:\s*#f4f6fa;/)
  })

  it('reportPage.css、RecordQualityReportView 与 SpecialRecordReportView 宽表启用首列固定与窄列样式', async () => {
    const css = readReportFile('reportPage.css')
    expect(css).toMatch(/\.mq-table--sticky-first\s*\{[^}]*overflow:\s*visible;/)
    expect(css).toMatch(
      /\.mq-table--sticky-first th:first-child,\s*\.mq-table--sticky-first td:first-child:not\(\[colspan\]\)\s*\{[^}]*position:\s*sticky;[^}]*left:\s*0;/,
    )
    expect(css).toMatch(/\.mq-table--sticky-first thead th:first-child\s*\{[^}]*background:\s*#f4f6fa;/)
    expect(css).toMatch(/\.mq-table--sticky-first \.col-compact\s*\{/)

    const specialReport = makeSpecialReport()
    vi.spyOn(ApiService, 'requestRaw').mockImplementation(async (cfg) => {
      const url = String(cfg.url || '')
      if (url.includes('special-records/records')) {
        return okResponse({
          total: 0,
          page: 1,
          page_size: 20,
          items: [],
          scope: specialReport.scope,
          score_standard: specialReport.score_standard,
        })
      }
      if (url.includes('special-records/defects')) {
        return okResponse({
          total: 0,
          page: 1,
          page_size: 20,
          items: [],
          scope: specialReport.scope,
          score_standard: specialReport.score_standard,
        })
      }
      if (url.includes('special-records')) return okResponse(specialReport)
      return okResponse(makeRecordQualityReport(3))
    })

    const recordWrapper = mount(RecordQualityReportView, {
      global: {
        stubs: {
          'a-drawer': true,
          CoreSystemReportPanel: true,
          RecordRemediationAnalysisPanel: true,
        },
      },
    })
    await flushPromises()
    const stickyTables = recordWrapper.findAll('table.mq-table--sticky-first')
    expect(stickyTables).toHaveLength(2)
    expect(recordWrapper.findAll('th.col-compact').length).toBeGreaterThan(0)
    recordWrapper.unmount()

    const specialWrapper = mount(SpecialRecordReportView, {
      global: {
        stubs: {
          'a-select': SelectStub,
          'a-drawer': true,
          SpecialReportConfigDrawer: true,
          SpecialReportCharts: true,
        },
      },
    })
    await flushPromises()
    expect(specialWrapper.find('table.mq-table--sticky-first').exists()).toBe(true)
    expect(specialWrapper.find('th.col-id').text()).toBe('病例身份')
    const detailModeBtn = specialWrapper
      .findAll('.mq-segmented__item')
      .find((btn) => btn.text() === '明细')
    await detailModeBtn?.trigger('click')
    await flushPromises()
    expect(specialWrapper.findAll('table.mq-table--sticky-first')).toHaveLength(2)
    expect(specialWrapper.findAll('th.col-id').map((el) => el.text())).toEqual([
      '缺陷名称',
      '病例身份',
    ])
    specialWrapper.unmount()
  })
})

describe('T1-B4 3. 1280px 卡片网格断点与 ECharts 防挤压/消死区', () => {
  it('SpecialReportCharts 提升 3 列断点至 1360px、grid.left 自适应并替换低对比 #bcd6ff', () => {
    const source = readReportFile('SpecialReportCharts.vue')
    expect(source).toMatch(/@media\s*\(max-width:\s*1360px\)/)
    expect(source).not.toMatch(/@media\s*\(max-width:\s*1180px\)/)
    expect(source).not.toContain('--mq-brand-200')
    expect(source).not.toMatch(/#bcd6ff/i)

    const wrapper = mount(SpecialReportCharts, {
      props: {
        departments: [
          { name: '心内科', count: 5 },
          { name: '骨科', count: 3 },
        ],
        grades: [
          { grade: '甲级', count: 6, ratio: 0.75 },
          { grade: '乙级', count: 2, ratio: 0.25 },
        ],
        defects: [
          {
            rule_id: 'R1',
            name: '入院记录现病史内容不完整规范',
            severity: '严重',
            category: '内涵',
            type: '完整性',
            document: '入院记录',
            is_veto: false,
            count: 4,
            ratio: 0.5,
          },
        ],
      },
    })

    const charts = wrapper.findAllComponents({ name: 'VChart' })
    expect(charts).toHaveLength(3)

    const deptOption = charts[0]!.props('option') as { color: string[] }
    expect(deptOption.color.every((c) => c && c.toLowerCase() !== '#bcd6ff')).toBe(true)

    const barOption = charts[2]!.props('option') as {
      grid: { left: number; containLabel?: boolean }
      yAxis: { axisLabel: { overflow: string } }
    }
    expect(barOption.grid.containLabel).toBe(true)
    expect(barOption.grid.left).toBeLessThanOrEqual(24)
    expect(barOption.yAxis.axisLabel.overflow).toBe('truncate')
    wrapper.unmount()
  })

  it('reportPage.css、FrontpageQualityReportView、record-remediation-analysis.css 与 core-system-report.css 断点提至 1360px 且首页 2 卡消死区', async () => {
    const reportCss = readReportFile('reportPage.css')
    expect(reportCss).toMatch(/@media\s*\(max-width:\s*1360px\)[\s\S]*\.distribution-grid\s*\{/)
    expect(reportCss).not.toMatch(/@media\s*\(max-width:\s*1180px\)/)
    expect(reportCss).toMatch(/\.distribution-grid--two\s*\{\s*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/)

    const remediationCss = readReportFile('styles/record-remediation-analysis.css')
    expect(remediationCss).toMatch(/@media\s*\(max-width:\s*1360px\)[\s\S]*\.remediation-groups\s*\{/)

    const coreCss = readReportFile('styles/core-system-report.css')
    expect(coreCss).toMatch(/@media\s*\(max-width:\s*1360px\)[\s\S]*\.core-metrics\s*\{/)
    expect(coreCss).not.toMatch(/@media\s*\(max-width:\s*1180px\)/)

    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(okResponse(makeFrontpageReport(2)))
    const fpWrapper = mount(FrontpageQualityReportView, {
      global: { stubs: { 'a-drawer': true } },
    })
    await flushPromises()
    expect(fpWrapper.find('.distribution-grid.distribution-grid--two').exists()).toBe(true)
    expect(fpWrapper.find('.filters .filter-actions').exists()).toBe(true)
    fpWrapper.unmount()
  })
})

describe('T1-B4 4. WAI-ARIA Tabs、键盘无障碍与 0 病例空态引导', () => {
  it('RecordQualityReportView 补齐 tabpanel/aria-controls/方向键切换、无孤立 label、Top 20 aria-pressed 与 0 病例空态引导', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(okResponse(makeRecordQualityReport(0)))
    const wrapper = mount(RecordQualityReportView, {
      attachTo: document.body,
      global: {
        stubs: {
          'a-drawer': true,
          CoreSystemReportPanel: { template: '<div data-testid="core-panel-stub">核心制度</div>' },
          RecordRemediationAnalysisPanel: true,
        },
      },
    })
    await flushPromises()

    // 1. WAI-ARIA Tabs + 方向键切换
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs).toHaveLength(2)
    const [qualityTab, coreTab] = tabs as [typeof tabs[0], typeof tabs[0]]
    expect(qualityTab.attributes('id')).toBe('record-report-tab-quality')
    expect(qualityTab.attributes('aria-controls')).toBe('record-report-panel-quality')
    expect(qualityTab.attributes('aria-selected')).toBe('true')
    expect(qualityTab.attributes('tabindex')).toBe('0')
    expect(coreTab.attributes('id')).toBe('record-report-tab-core')
    expect(coreTab.attributes('aria-controls')).toBe('record-report-panel-core')
    expect(coreTab.attributes('aria-selected')).toBe('false')
    expect(coreTab.attributes('tabindex')).toBe('-1')

    const qualityPanel = wrapper.get('#record-report-panel-quality')
    const corePanel = wrapper.get('#record-report-panel-core')
    expect(qualityPanel.attributes('role')).toBe('tabpanel')
    expect(qualityPanel.attributes('aria-labelledby')).toBe('record-report-tab-quality')
    expect(qualityPanel.attributes('hidden')).toBeUndefined()
    expect(corePanel.attributes('role')).toBe('tabpanel')
    expect(corePanel.attributes('aria-labelledby')).toBe('record-report-tab-core')
    expect(corePanel.attributes('hidden')).toBeDefined()

    // 2. 场景标签无孤立 <label>，关联到 role="group"
    for (const label of wrapper.findAll('label')) {
      const forId = label.attributes('for')
      const hasNestedControl = Boolean(label.find('input, select, textarea').exists())
      expect(Boolean(forId && wrapper.find(`#${forId}`).exists()) || hasNestedControl).toBe(true)
    }
    const sceneGroup = wrapper.get('[aria-labelledby="report-scene-label"]')
    expect(sceneGroup.attributes('role')).toBe('group')
    expect(wrapper.get('#report-scene-label').text()).toBe('场景')

    // 3. Top 20 切换组带 aria-pressed 且切换更新
    const topGroup = wrapper.get('[aria-label="缺陷 Top 20 维度"]')
    expect(topGroup.attributes('role')).toBe('group')
    const topButtons = topGroup.findAll('button')
    expect(topButtons[0]!.attributes('aria-pressed')).toBe('true')
    expect(topButtons[1]!.attributes('aria-pressed')).toBe('false')
    await topButtons[1]!.trigger('click')
    expect(topButtons[0]!.attributes('aria-pressed')).toBe('false')
    expect(topButtons[1]!.attributes('aria-pressed')).toBe('true')

    // 4. 0 病例空态上下文引导（无 URL scene 参数时默认进入终末病历）
    const emptyGuide = wrapper.get('[data-testid="report-empty-guide"]')
    expect(emptyGuide.text()).toContain('0 份')
    expect(emptyGuide.text()).toContain('切换到运行病历')

    // 带筛选条件时提供“重置筛选条件”按钮
    await wrapper.get('#report-department').setValue('无数据科室')
    await wrapper.get('.filters .primary').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="report-empty-guide"]').text()).toContain('重置筛选条件')

    // 5. 方向键在 tablist 内切换并移动焦点
    ;(qualityTab.element as HTMLButtonElement).focus()
    await qualityTab.trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()
    expect(coreTab.attributes('aria-selected')).toBe('true')
    expect(coreTab.attributes('tabindex')).toBe('0')
    expect(qualityTab.attributes('tabindex')).toBe('-1')
    expect(document.activeElement).toBe(coreTab.element)
    expect(corePanel.attributes('hidden')).toBeUndefined()
    expect(qualityPanel.attributes('hidden')).toBeDefined()

    await coreTab.trigger('keydown', { key: 'ArrowLeft' })
    await flushPromises()
    expect(qualityTab.attributes('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(qualityTab.element)

    wrapper.unmount()
  })

  it('StaffAnalysisView 补齐 tabpanel/aria-controls 与方向键导航', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(okResponse(makeStaffReport()))
    const wrapper = mount(StaffAnalysisView, {
      attachTo: document.body,
      global: {
        stubs: {
          'a-drawer': true,
          ManualQualityReportPanel: { template: '<div data-testid="manual-panel-stub">人工报表</div>' },
          ModernAppealWorkflowDrawer: true,
          RecordReviewWorkflowDrawer: true,
        },
      },
    })
    await flushPromises()

    const staffTab = wrapper.get('[data-testid="staff-report-tab-staff"]')
    const manualTab = wrapper.get('[data-testid="staff-report-tab-manual"]')
    expect(staffTab.attributes('id')).toBe('staff-report-tab-staff')
    expect(staffTab.attributes('aria-controls')).toBe('staff-report-panel-staff')
    expect(staffTab.attributes('tabindex')).toBe('0')
    expect(manualTab.attributes('id')).toBe('staff-report-tab-manual')
    expect(manualTab.attributes('aria-controls')).toBe('staff-report-panel-manual')
    expect(manualTab.attributes('tabindex')).toBe('-1')

    const staffPanel = wrapper.get('#staff-report-panel-staff')
    const manualPanel = wrapper.get('#staff-report-panel-manual')
    expect(staffPanel.attributes('role')).toBe('tabpanel')
    expect(staffPanel.attributes('aria-labelledby')).toBe('staff-report-tab-staff')
    expect(staffPanel.attributes('hidden')).toBeUndefined()
    expect(manualPanel.attributes('role')).toBe('tabpanel')
    expect(manualPanel.attributes('aria-labelledby')).toBe('staff-report-tab-manual')
    expect(manualPanel.attributes('hidden')).toBeDefined()

    ;(staffTab.element as HTMLButtonElement).focus()
    await staffTab.trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()
    expect(manualTab.attributes('aria-selected')).toBe('true')
    expect(manualTab.attributes('tabindex')).toBe('0')
    expect(staffTab.attributes('tabindex')).toBe('-1')
    expect(document.activeElement).toBe(manualTab.element)
    expect(manualPanel.attributes('hidden')).toBeUndefined()
    expect(staffPanel.attributes('hidden')).toBeDefined()

    await manualTab.trigger('keydown', { key: 'Home' })
    await flushPromises()
    expect(staffTab.attributes('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(staffTab.element)
    wrapper.unmount()
  })

  it('FrontpageQualityReportView 0 病例空态展示上下文引导并支持重置筛选', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(okResponse(makeFrontpageReport(0)))
    const wrapper = mount(FrontpageQualityReportView, {
      global: { stubs: { 'a-drawer': true } },
    })
    await flushPromises()

    const emptyGuide = wrapper.get('[data-testid="frontpage-empty-guide"]')
    expect(emptyGuide.text()).toContain('0 份')
    expect(emptyGuide.text()).toContain('刷新数据')

    await wrapper.get('#fp-department').setValue('无结果科室')
    await wrapper.get('.filters .primary').trigger('click')
    await flushPromises()
    const filteredGuide = wrapper.get('[data-testid="frontpage-empty-guide"]')
    expect(filteredGuide.text()).toContain('重置筛选条件')
    await filteredGuide.get('button').trigger('click')
    await flushPromises()
    expect((wrapper.get('#fp-department').element as HTMLInputElement).value).toBe('')
    wrapper.unmount()
  })
})
