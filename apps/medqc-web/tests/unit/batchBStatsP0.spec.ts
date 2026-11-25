import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.hoisted(() => vi.fn())
const getLuxianQcResultAnalysis = vi.hoisted(() => vi.fn())
const routerPush = vi.hoisted(() => vi.fn())
const routeState = vi.hoisted(() => ({ query: {} as Record<string, string | undefined> }))
const authState = vi.hoisted(() => ({
  user: { is_demo_account: false, roles: ['admin'] } as {
    is_demo_account?: boolean
    roles?: string[]
  } | null,
}))

vi.mock('@/services/apiService', () => ({ ApiService: { get: apiGet } }))
vi.mock('@/services/luxian-qc-result-analysis-service', () => ({
  getLuxianQcResultAnalysis,
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return authState.user
    },
  }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({
    query: routeState.query,
    get fullPath() {
      return JSON.stringify(routeState.query)
    },
  }),
  useRouter: () => ({ push: routerPush }),
}))

import {
  clinicalSourceForRequest,
  resetClinicalSourceMode,
  setClinicalSourceMode,
  setPageClinicalSource,
} from '@/utils/clinical-source'
import LuxianQcAnalyticsView from '@/views/workstation-v4/LuxianQcAnalyticsView.vue'
import QcRecordResultAnalysisPanel from '@/views/workstation-v4/components/qc/QcRecordResultAnalysisPanel.vue'
import AnalyticsDrilldownBar from '@/views/workstation-v4/components/workbench/AnalyticsDrilldownBar.vue'
import {
  ANALYTICS_PROBLEM_RESULT_STATUS_PARAM,
  analyticsResultStatusLabel,
  parseAnalyticsResultStatuses,
  readAnalyticsDrilldown,
} from '@/views/workstation-v4/utils/analyticsDrilldown'

const Stub = defineComponent({
  setup(_, { slots, attrs }) {
    return () => h('button', attrs, slots.default?.())
  },
})

function mountAnalyticsView() {
  return shallowMount(LuxianQcAnalyticsView, {
    global: {
      stubs: {
        'a-button': Stub,
        'a-range-picker': Stub,
        'a-select': Stub,
        'a-input': Stub,
        'a-spin': Stub,
        'a-empty': Stub,
      },
    },
  })
}

async function flush() {
  await Promise.resolve()
  await nextTick()
  await flushPromises()
}

function makeAnalyticsPayload(overrides: Record<string, unknown> = {}) {
  return {
    scope: {
      time_basis: 'qc_completed_at',
      completed_from: null,
      completed_to: null,
      department: null,
      job_id: null,
      rule_set_key: 'luxian_0609_qc_v1',
      rule_set_version: '2026-06-09',
      generated_at: '2026-08-08T12:00:00+08:00',
    },
    kpis: {
      distinct_record_total: 10,
      completed_event_total: 12,
      records_with_non_compliant: 2,
      records_with_data_gap: 4,
      canonical_invalid_or_missing_total: 3,
    },
    status_distribution: [
      { status: 'non_compliant', count: 3 },
      { status: 'data_gap', count: 5 },
      { status: 'uncertain', count: 2 },
      { status: 'compliant', count: 20 },
      { status: 'not_applicable', count: 4 },
      { status: 'not_executed', count: 0 },
    ],
    department_distribution: [
      {
        department: '心内科',
        distinct_record_total: 2,
        non_compliant_record_total: 1,
        data_gap_record_total: 2,
        uncertain_record_total: 2,
        problem_record_total: 2,
        primary_non_compliant_record_total: 1,
        primary_data_gap_record_total: 1,
        primary_uncertain_record_total: 0,
      },
      {
        department: '骨科',
        distinct_record_total: 1,
        non_compliant_record_total: 0,
        data_gap_record_total: 0,
        uncertain_record_total: 1,
        problem_record_total: 1,
        primary_non_compliant_record_total: 0,
        primary_data_gap_record_total: 0,
        primary_uncertain_record_total: 1,
      },
    ],
    physician_distribution: [
      {
        physician: '张医生',
        distinct_record_total: 2,
        non_compliant_record_total: 1,
        data_gap_record_total: 2,
        uncertain_record_total: 2,
        problem_record_total: 2,
        primary_non_compliant_record_total: 1,
        primary_data_gap_record_total: 1,
        primary_uncertain_record_total: 0,
      },
      {
        physician: '李医生',
        distinct_record_total: 1,
        non_compliant_record_total: 0,
        data_gap_record_total: 0,
        uncertain_record_total: 1,
        problem_record_total: 1,
        primary_non_compliant_record_total: 0,
        primary_data_gap_record_total: 0,
        primary_uncertain_record_total: 1,
      },
    ],
    rule_distribution: [
      {
        rule_id: 'LX0609-01-01-01',
        rule_name: '入院记录时限',
        non_compliant_count: 2,
        data_gap_count: 3,
        uncertain_count: 1,
        evaluated_count: 10,
      },
      {
        rule_id: 'LX0609-01-02-01',
        rule_name: '仅资料待核实规则',
        non_compliant_count: 0,
        data_gap_count: 4,
        uncertain_count: 1,
        evaluated_count: 10,
      },
    ],
    completion_time_series: null,
    data_health: { canonical_invalid_or_missing_total: 3 },
    ...overrides,
  }
}

function makeResultAnalysisPayload(ruleId = '') {
  const selected = ruleId ? { rule_id: ruleId, rule_name: '入院记录时限' } : null
  return {
    scope: {
      care_phase: 'inpatient',
      department: null,
      doctor: null,
      rule_id: ruleId || null,
      result_status: null,
      completed_from: null,
      completed_to: null,
    },
    kpis: {
      scoped_record_total: 8,
      ready_record_total: 5,
      unavailable_result_total: 2,
    },
    status_distribution: [
      { status: 'non_compliant', count: 3 },
      { status: 'data_gap', count: 4 },
      { status: 'uncertain', count: 2 },
      { status: 'compliant', count: 12 },
      { status: 'not_applicable', count: 4 },
      { status: 'not_executed', count: 5 },
    ],
    rule_distribution: [
      {
        rule_id: 'LX0609-01-01-01',
        rule_name: '入院记录时限',
        evaluated_count: 5,
        non_compliant_count: 3,
        data_gap_count: 2,
        uncertain_count: 1,
        issue_count: 6,
        department_distribution: [
          {
            department: '重症医学科',
            record_total: 5,
            non_compliant_count: 3,
            data_gap_count: 2,
            uncertain_count: 1,
          },
        ],
      },
    ],
    physician_distribution: [
      {
        physician: '张医生',
        record_total: 5,
        non_compliant_count: 3,
        data_gap_count: 2,
        uncertain_count: 1,
      },
    ],
    selected_rule: selected,
    record_page: {
      page: 1,
      page_size: 20,
      total: selected ? 2 : 0,
      items: selected
        ? [
            {
              record_key: '["H","P1","V1"]',
              institute_id: 'H',
              patient_id: 'P1',
              visit_id: 'V1',
              patient_name: '患者甲',
              department: '重症医学科',
              attending_physician: '张医生',
              status: 'non_compliant',
              completed_at: '2026-08-19T08:00:00+00:00',
            },
            {
              record_key: '["H","P2","V2"]',
              institute_id: 'H',
              patient_id: 'P2',
              visit_id: 'V2',
              patient_name: '患者乙',
              department: '重症医学科',
              attending_physician: '张医生',
              status: 'data_gap',
              completed_at: '2026-08-19T09:00:00+00:00',
            },
          ]
        : [],
    },
  }
}

describe('Batch B P0: 临床源透传、统计分析与结果分析演示隔离、下钻问题状态、排行去重', () => {
  beforeEach(() => {
    resetClinicalSourceMode()
    window.history.replaceState({}, '', '/workstation-v5/stats')
    apiGet.mockReset()
    apiGet.mockResolvedValue({ success: true, data: makeAnalyticsPayload() })
    getLuxianQcResultAnalysis.mockReset()
    getLuxianQcResultAnalysis.mockImplementation((query: { ruleId?: string }) =>
      Promise.resolve(makeResultAnalysisPayload(query.ruleId)),
    )
    routerPush.mockReset()
    routeState.query = {}
    authState.user = { is_demo_account: false, roles: ['admin'] }
  })

  describe('1. clinical-source.ts: workstation / frontpage-qc / quality-reports 兼容透传与安全回退', () => {
    const newPaths = [
      '/api/v1/workstation/qc-home',
      '/api/v1/workstation/analytics/luxian-0609?job_id=job-1',
      '/api/v1/workstation/qc-result-analysis/luxian-0609',
      '/api/v1/frontpage-qc/records',
      '/api/v1/frontpage-qc/analytics',
      '/api/v1/quality-reports/record-quality',
      '/api/v1/quality-reports/frontpage-quality',
    ]

    it('legacy_compat 模式下透传页签或激活来源，切源后全模块与病历池保持同源', () => {
      setClinicalSourceMode('legacy_compat', 'legacy_pg')
      setPageClinicalSource('legacy_pg')
      for (const path of newPaths) {
        expect(clinicalSourceForRequest(path)).toBe('legacy_pg')
      }
      setPageClinicalSource('independent_cdm')
      for (const path of newPaths) {
        expect(clinicalSourceForRequest(path)).toBe('independent_cdm')
      }
      // 客户样本验证页不附带临床源 header
      window.history.replaceState({}, '', '/workstation-v5/customer-sample-validation?source_id=legacy_pg')
      for (const path of newPaths) {
        expect(clinicalSourceForRequest(path)).toBeUndefined()
      }
    })

    it('fixed_donghua_cdm 模式下默认不强加 header 保留本地安全回退，仅 URL 显式 independent_cdm 时透传', () => {
      window.history.replaceState({}, '', '/workstation-v5/stats')
      for (const path of newPaths) {
        expect(clinicalSourceForRequest(path)).toBeUndefined()
      }
      // URL 带旧 source_id=legacy_pg 也不强加 header（防破坏回退或误触发 409）
      window.history.replaceState({}, '', '/workstation-v5/frontpage-qc?source_id=legacy_pg')
      for (const path of newPaths) {
        expect(clinicalSourceForRequest(path)).toBeUndefined()
      }
      // 页面 URL 显式带 source_id=independent_cdm 时透传
      window.history.replaceState({}, '', '/workstation-v5/reports/record-quality?source_id=independent_cdm')
      for (const path of newPaths) {
        expect(clinicalSourceForRequest(path)).toBe('independent_cdm')
      }
      // 请求 URL 自身显式带 source_id=independent_cdm 时透传
      window.history.replaceState({}, '', '/workstation-v5/stats')
      expect(clinicalSourceForRequest('/api/v1/workstation/qc-home?source_id=independent_cdm')).toBe(
        'independent_cdm',
      )
      // 原有病历池接口行为不变
      expect(clinicalSourceForRequest('/api/medical-records/workstation')).toBe('independent_cdm')
      expect(clinicalSourceForRequest('/api/v1/emr/V/documents?job_id=old')).toBeUndefined()
    })
  })

  describe('2. 演示账号隔离（confirmedResultsOnly）', () => {
    it('LuxianQcAnalyticsView 在演示账号下隐藏资料待核实 KPI、data_gap/uncertain 图例与排行段、数据健康栏并净化工程文案', async () => {
      authState.user = { is_demo_account: true, roles: ['admin'] }
      const wrapper = mountAnalyticsView()
      await flush()

      const text = wrapper.text()
      expect(wrapper.findAll('[data-testid="analytics-kpi"]')).toHaveLength(3)
      expect(wrapper.find('[data-testid="analytics-data-health"]').exists()).toBe(false)
      expect(text).not.toContain('资料待核实')
      expect(text).not.toContain('待核实')
      expect(text).not.toContain('待判断')
      expect(text).not.toContain('历史候选待核验')
      expect(text).not.toContain('Canonical')
      expect(text).not.toContain('技术异常')

      // 结论结构只保留确定问题/合规/不适用等非隐藏状态，需重点关注只计确定问题 (3)
      const conclusionText = wrapper.get('[data-testid="analytics-conclusion-structure"]').text()
      expect(conclusionText).toContain('确定问题')
      expect(conclusionText).toContain('3需重点关注')
      expect(conclusionText).toContain('共 27 条有效结论')

      // 科室与医师排行只展示确定问题，隐藏仅 uncertain 的骨科/李医生，且不渲染橙/灰柱段
      const deptRows = wrapper.findAll('[data-testid="analytics-department-chart"] .department-row')
      expect(deptRows).toHaveLength(1)
      expect(deptRows[0].text()).toContain('心内科')
      expect(deptRows[0].get('strong').text()).toBe('1')
      expect(deptRows[0].find('.bar-warning').exists()).toBe(false)
      expect(deptRows[0].find('.bar-uncertain').exists()).toBe(false)

      const physRows = wrapper.findAll('[data-testid="analytics-physician-chart"] .physician-row')
      expect(physRows).toHaveLength(1)
      expect(physRows[0].text()).toContain('张医生')
      expect(physRows[0].get('strong').text()).toBe('1')

      // Top 5 规则过滤掉无确定问题的规则，仅呈现确定问题数
      const ruleButtons = wrapper.findAll('[data-testid="analytics-rule-chart"] .rule-list button')
      expect(ruleButtons).toHaveLength(1)
      expect(ruleButtons[0].text()).toContain('LX0609-01-01-01')
      expect(ruleButtons[0].get('.rule-count strong').text()).toBe('2')
    })

    it('sync_admin 即使带 is_demo_account=true 仍展示完整统计口径', async () => {
      authState.user = { is_demo_account: true, roles: ['sync_admin'] }
      const wrapper = mountAnalyticsView()
      await flush()

      expect(wrapper.findAll('[data-testid="analytics-kpi"]')).toHaveLength(4)
      expect(wrapper.find('[data-testid="analytics-data-health"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('资料待核实')
      expect(wrapper.text()).toContain('历史候选待核验')
    })

    it('QcRecordResultAnalysisPanel 在演示账号下隐藏资料待核实/待判断入口与列并净化文案', async () => {
      authState.user = { is_demo_account: true, roles: ['admin'] }
      const wrapper = mount(QcRecordResultAnalysisPanel, {
        props: { carePhase: 'inpatient' },
        global: { stubs: { 'a-date-picker': Stub } },
      })
      await flush()

      // 状态导航仅保留 5 项（全部、确定问题、合规、不适用、未执行）
      expect(wrapper.findAll('.qc-result-analysis__status-button')).toHaveLength(5)
      const text = wrapper.text()
      expect(text).toContain('确定问题')
      expect(text).not.toContain('资料待核实')
      expect(text).not.toContain('待判断')
      expect(text).not.toContain('待核实')
      expect(text).not.toContain('Canonical')

      // 结论结构总条数排除 data_gap(4) 与 uncertain(2)：3+12+4+5 = 24
      expect(wrapper.get('.qc-result-analysis__insights').text()).toContain('24 条')

      // 展开科室行也不含待核实/待判断
      await wrapper.get('.qc-result-analysis__expand').trigger('click')
      await nextTick()
      const deptRowText = wrapper.get('.qc-result-analysis__department-row').text()
      expect(deptRowText).toContain('确定 3')
      expect(deptRowText).not.toContain('待核实')
      expect(deptRowText).not.toContain('待判断')

      // 选中质控点下钻时，过滤掉 data_gap 病历，只展示确定问题病历
      await wrapper.get('.qc-result-analysis__rule-table tbody tr').trigger('click')
      await flush()
      const recordRows = wrapper.findAll('.qc-result-analysis__record-table tbody tr')
      expect(recordRows).toHaveLength(1)
      expect(recordRows[0].text()).toContain('患者甲')
      expect(recordRows[0].text()).not.toContain('患者乙')
    })
  })

  describe('3. Top 5 规则下钻问题状态与病历池口径对齐', () => {
    it('普通账号下钻显式传入 analytics_result_status=non_compliant,data_gap,uncertain', async () => {
      authState.user = { is_demo_account: false, roles: ['admin'] }
      const wrapper = mountAnalyticsView()
      await flush()

      await wrapper.get('[data-testid="analytics-rule-chart"] .rule-list button').trigger('click')

      expect(routerPush).toHaveBeenCalledWith({
        path: '/workstation-v5/worklist',
        query: expect.objectContaining({
          source: 'analytics',
          analytics_scope: 'final',
          analytics_rule_id: 'LX0609-01-01-01',
          analytics_result_status: ANALYTICS_PROBLEM_RESULT_STATUS_PARAM,
          analytics_rule_name: '入院记录时限',
        }),
      })
    })

    it('演示账号下钻固定传入 analytics_result_status=non_compliant', async () => {
      authState.user = { is_demo_account: true, roles: ['admin'] }
      const wrapper = mountAnalyticsView()
      await flush()

      await wrapper.get('[data-testid="analytics-rule-chart"] .rule-list button').trigger('click')

      expect(routerPush).toHaveBeenCalledWith({
        path: '/workstation-v5/worklist',
        query: expect.objectContaining({
          source: 'analytics',
          analytics_scope: 'final',
          analytics_rule_id: 'LX0609-01-01-01',
          analytics_result_status: 'non_compliant',
        }),
      })
    })

    it('analyticsDrilldown 与 AnalyticsDrilldownBar 支持逗号分隔多状态解析与中文标签', () => {
      expect(parseAnalyticsResultStatuses('non_compliant, data_gap, uncertain')).toEqual([
        'non_compliant',
        'data_gap',
        'uncertain',
      ])
      expect(analyticsResultStatusLabel('non_compliant,data_gap,uncertain')).toBe('存在问题')
      expect(analyticsResultStatusLabel('non_compliant')).toBe('确定问题')
      expect(analyticsResultStatusLabel('non_compliant,uncertain')).toBe('确定问题 / 待判断')

      const drilldown = readAnalyticsDrilldown({
        source: 'analytics',
        analytics_scope: 'final',
        analytics_rule_id: 'LX0609-01-01-01',
        analytics_result_status: 'non_compliant,data_gap,uncertain',
      })!
      const bar = mount(AnalyticsDrilldownBar, {
        props: { drilldown, total: 6 },
        global: { stubs: { 'a-button': Stub } },
      })
      expect(bar.get('[data-testid="analytics-drilldown-result-status"]').text()).toBe(
        '结论状态 存在问题',
      )
    })
  })

  describe('4. 科室/医师排行去重并集计数与纯 uncertain 非零展示', () => {
    it('消费 Batch A problem_record_total 与 primary_* 分桶，不超总病历数且纯 uncertain 不再显示数字 0', async () => {
      authState.user = { is_demo_account: false, roles: ['admin'] }
      const wrapper = mountAnalyticsView()
      await flush()

      const deptRows = wrapper.findAll('[data-testid="analytics-department-chart"] .department-row')
      expect(deptRows).toHaveLength(2)

      // 心内科：distinct=2, nc=1, dg=2, unc=2 -> problem_record_total=2，主分桶 1/1/0
      expect(deptRows[0].text()).toContain('心内科')
      expect(deptRows[0].get('strong').text()).toBe('2')
      expect(deptRows[0].get('.bar-danger').attributes('style')).toContain('width: 50%')
      expect(deptRows[0].get('.bar-warning').attributes('style')).toContain('width: 50%')
      expect(deptRows[0].find('.bar-uncertain').exists()).toBe(false)

      // 骨科：纯 uncertain=1 -> 右侧数字为 1（不再是 0），灰柱宽 50%（相对 max=2）
      expect(deptRows[1].text()).toContain('骨科')
      expect(deptRows[1].get('strong').text()).toBe('1')
      expect(deptRows[1].find('.bar-danger').exists()).toBe(false)
      expect(deptRows[1].find('.bar-warning').exists()).toBe(false)
      expect(deptRows[1].get('.bar-uncertain').attributes('style')).toContain('width: 50%')

      // 医师排行同理
      const physRows = wrapper.findAll('[data-testid="analytics-physician-chart"] .physician-row')
      expect(physRows).toHaveLength(2)
      expect(physRows[0].get('strong').text()).toBe('2')
      expect(physRows[1].text()).toContain('李医生')
      expect(physRows[1].get('strong').text()).toBe('1')
    })

    it('无新字段的旧后端返回时向后兼容回退：仍计入 uncertain 且不超 distinct_record_total', async () => {
      authState.user = { is_demo_account: false, roles: ['admin'] }
      apiGet.mockResolvedValueOnce({
        success: true,
        data: makeAnalyticsPayload({
          department_distribution: [
            {
              department: '重叠旧科室',
              distinct_record_total: 2,
              non_compliant_record_total: 1,
              data_gap_record_total: 2,
              uncertain_record_total: 2,
            },
            {
              department: '纯待判断旧科室',
              distinct_record_total: 1,
              non_compliant_record_total: 0,
              data_gap_record_total: 0,
              uncertain_record_total: 1,
            },
          ],
          physician_distribution: [
            {
              physician: '纯待判断医师',
              distinct_record_total: 1,
              non_compliant_record_total: 0,
              data_gap_record_total: 0,
              uncertain_record_total: 1,
            },
          ],
        }),
      })
      const wrapper = mountAnalyticsView()
      await flush()

      const deptRows = wrapper.findAll('[data-testid="analytics-department-chart"] .department-row')
      expect(deptRows).toHaveLength(2)
      expect(deptRows[0].text()).toContain('重叠旧科室')
      expect(deptRows[0].get('strong').text()).toBe('2')
      expect(deptRows[1].text()).toContain('纯待判断旧科室')
      expect(deptRows[1].get('strong').text()).toBe('1')

      const physRows = wrapper.findAll('[data-testid="analytics-physician-chart"] .physician-row')
      expect(physRows).toHaveLength(1)
      expect(physRows[0].text()).toContain('纯待判断医师')
      expect(physRows[0].get('strong').text()).toBe('1')
    })
  })
})
