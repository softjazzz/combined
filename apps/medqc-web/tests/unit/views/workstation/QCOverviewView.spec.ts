import { defineComponent, h, nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.hoisted(() => vi.fn())
const routeState = vi.hoisted(() => ({
  query: {} as Record<string, string>,
  path: '/workstation-v4',
}))
const routerPush = vi.hoisted(() => vi.fn())
const authState = vi.hoisted(() => ({ isDemoAccount: false }))

vi.mock('@/services/apiService', () => ({
  ApiService: { get: apiGet },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: routerPush, replace: vi.fn() }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { is_demo_account: authState.isDemoAccount },
  }),
}))

import QCOverviewView from '@/views/workstation/QCOverviewView.vue'

const HomeHeroBarStub = defineComponent({
  name: 'HomeHeroBar',
  setup() {
    return () => h('div', { 'data-testid': 'home-filter' })
  },
})

const clinicalQcPayload = {
  date: '2026-08-08',
  department_options: ['神经外科'],
  scope: {
    hospital_scope: 'all',
    department: null,
    scene: 'final',
    rule_set_key: 'luxian_0609_qc_v1',
    rule_set_version: 'v1',
    generated_at: '2026-08-08T09:30:00+08:00',
  },
  clinical_qc: {
    scope: {
      hospital_scope: 'all',
      department: null,
      scene: 'final',
      rule_set_key: 'luxian_0609_qc_v1',
      rule_set_version: 'v1',
      generated_at: '2026-08-08T09:30:00+08:00',
    },
    kpis: {
      records_total: 18,
      qc_pending_total: 3,
      qc_completed_total: 13,
      high_risk_review_total: 2,
    },
    data_health: {
      source_sync_status: 'unknown',
      source_error_total: 0,
      technical_error_total: 2,
      running_task_total: null,
      running_task_state: 'unknown',
      last_successful_qc_at: '2026-08-08T09:20:00+08:00',
    },
    canonical_status_counts: { compliant: 10, non_compliant: 2, data_gap: 3 },
    priority_items: [
      {
        record_key: '["H1","P1","V1"]',
        institute_id: 'H1',
        patient_id: 'P1',
        visit_id: 'V1',
        patient_name: '测试患者',
        department: '神经外科',
        priority_kind: 'non_compliant',
        status_counts: { non_compliant: 2, data_gap: 1 },
        completed_at: '2026-08-08T09:20:00+08:00',
      },
    ],
    department_distribution: [
      {
        department: '神经外科',
        records_total: 18,
        high_risk_review_total: 2,
        data_gap_record_total: 3,
        uncertain_record_total: 0,
      },
    ],
    rule_family_distribution: [],
    trend: null,
    comparison: null,
  },
}

async function flushHomeLoad() {
  await Promise.resolve()
  await Promise.resolve()
  await nextTick()
}

function mountView() {
  return shallowMount(QCOverviewView, {
    global: {
      stubs: {
        HomeHeroBar: HomeHeroBarStub,
        'a-empty': true,
        'a-button': true,
        'a-tag': true,
        'a-spin': true,
      },
    },
  })
}

describe('QCOverviewView', () => {
  beforeEach(() => {
    apiGet.mockReset()
    apiGet.mockResolvedValue({ success: true, data: clinicalQcPayload })
    routerPush.mockReset()
    routeState.query = {}
    authState.isDemoAccount = false
  })

  it('只展示权威 clinical_qc 指标、范围和结构化优先项，不展示固定涨跌或趋势', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    expect(wrapper.get('[data-testid="home-scope"]').text()).toContain('全院')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('18')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('高风险待复核')
    expect(wrapper.get('[data-testid="priority-queue"]').text()).toContain('测试患者')
    expect(wrapper.get('[data-testid="priority-queue"]').text()).toContain('确定问题 2 项')
    expect(wrapper.text()).not.toContain('较昨日')
    expect(wrapper.text()).not.toContain('近7天')
    expect(wrapper.find('[data-testid="home-trend"]').exists()).toBe(false)
  })

  it('将技术异常和未知资料状态放入数据运行状态，不计入高风险队列', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    const health = wrapper.get('[data-testid="data-health"]').text()
    expect(health).toContain('技术异常 2 份')
    expect(health).toContain('资料同步状态待核实')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('高风险待复核')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('2')
  })

  it('演示账号不展示内部技术异常，但保留客户需要的数据状态', async () => {
    authState.isDemoAccount = true
    const wrapper = mountView()
    await flushHomeLoad()

    const health = wrapper.get('[data-testid="data-health"]').text()
    expect(health).toContain('资料同步状态')
    expect(health).toContain('运行中任务')
    expect(health).toContain('最近成功质控')
    expect(health).not.toContain('技术异常')

    const coverage = wrapper.get('[data-testid="qc-coverage-chart"]').text()
    expect(coverage).toContain('已完成 13')
    expect(coverage).toContain('待质控 3')
    expect(coverage).not.toContain('结果校验异常')
  })

  it('将科室分布收敛为按待复核数量排序的前八个横向柱状图', async () => {
    apiGet.mockResolvedValue({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          department_distribution: Array.from({ length: 9 }, (_, index) => ({
            department: `科室${index + 1}`,
            records_total: index + 10,
            high_risk_review_total: index + 1,
            data_gap_record_total: 0,
            uncertain_record_total: 0,
          })),
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    const chartRows = wrapper.findAll('[data-testid="department-chart-row"]')
    expect(chartRows).toHaveLength(8)
    expect(chartRows[0].text()).toContain('科室9')
    expect(wrapper.get('[data-testid="department-chart"]').text()).toContain('其余 1 个科室已收起')
  })

  it('使用同一首页响应展示质控覆盖构成，且不把技术异常混入医疗风险', async () => {
    apiGet.mockResolvedValue({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          kpis: {
            ...clinicalQcPayload.clinical_qc.kpis,
            records_total: 454,
            qc_completed_total: 5,
            qc_pending_total: 220,
          },
          data_health: {
            ...clinicalQcPayload.clinical_qc.data_health,
            technical_error_total: 229,
          },
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    const coverage = wrapper.get('[data-testid="qc-coverage-chart"]').text()
    expect(coverage).toContain('已完成 5')
    expect(coverage).toContain('待质控 220')
    expect(coverage).toContain('结果校验异常 229')
    expect(coverage).not.toContain('统计范围待核实')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('高风险待复核')
    expect(wrapper.get('[data-testid="priority-queue"]').text()).not.toContain('结果校验异常')
  })

  it('将完成态 Canonical 结论以可读图例展示，技术异常不进入结论结构', async () => {
    apiGet.mockResolvedValue({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          canonical_status_counts: {
            non_compliant: 33,
            data_gap: 70,
            uncertain: 5,
            compliant: 72,
            not_applicable: 139,
            not_executed: 4,
          },
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    const conclusion = wrapper.get('[data-testid="qc-conclusion-chart"]').text()
    expect(conclusion).toContain('已完成病历中的规则结论')
    expect(conclusion).toContain('确定问题 33')
    expect(conclusion).toContain('资料待核实 70')
    expect(conclusion).toContain('待判断 5')
    expect(conclusion).toContain('合规 72')
    expect(conclusion).toContain('不适用 139')
    expect(conclusion).toContain('未执行 4')
    expect(conclusion).not.toContain('技术异常')
  })

  it('在覆盖计数未闭合时明确提示统计范围待核实，并为零结论提供空状态', async () => {
    apiGet.mockResolvedValue({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          kpis: {
            ...clinicalQcPayload.clinical_qc.kpis,
            records_total: 18,
            qc_completed_total: 5,
            qc_pending_total: 3,
          },
          canonical_status_counts: {},
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    expect(wrapper.get('[data-testid="qc-coverage-chart"]').text()).toContain('统计范围待核实')
    expect(
      wrapper.get('[data-testid="qc-conclusion-chart"] a-empty-stub').attributes('description'),
    ).toBe('暂无已完成质控结论')
  })

  it('将工作入口与第二屏分析区分层展示', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    const workspace = wrapper.get('[data-testid="home-workspace"]')
    expect(workspace.find('[data-testid="priority-queue"]').exists()).toBe(true)
    expect(workspace.find('[data-testid="data-health"]').exists()).toBe(true)
    expect(workspace.find('[data-testid="department-chart"]').exists()).toBe(false)

    const analysis = wrapper.get('[data-testid="home-analysis"]')
    expect(analysis.find('[data-testid="qc-coverage-chart"]').exists()).toBe(true)
    expect(analysis.find('[data-testid="qc-conclusion-chart"]').exists()).toBe(true)
    expect(analysis.find('[data-testid="department-chart"]').exists()).toBe(true)
  })

  it('在请求失败时提供清晰的客户可见提示', async () => {
    apiGet.mockResolvedValue({ success: false, error: 'network failed', data: null })
    const wrapper = mountView()
    await flushHomeLoad()

    expect(wrapper.get('[data-testid="home-load-error"]').text()).toContain('暂时无法加载')
  })

  it('首次请求期间显示全院质控概览加载状态，不短暂展示空页面', () => {
    apiGet.mockReturnValueOnce(new Promise(() => undefined))

    const wrapper = mountView()

    expect(wrapper.get('[data-testid="home-loading"]').text()).toContain('正在加载全院质控概览')
    expect(wrapper.find('[data-testid="home-empty"]').exists()).toBe(false)
  })
})
