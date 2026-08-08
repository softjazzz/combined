import { defineComponent, h, nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.hoisted(() => vi.fn())
const routeState = vi.hoisted(() => ({ query: {} as Record<string, string>, path: '/workstation-v4' }))
const routerPush = vi.hoisted(() => vi.fn())

vi.mock('@/services/apiService', () => ({
  ApiService: { get: apiGet },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: routerPush, replace: vi.fn() }),
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

  it('在请求失败时提供清晰的客户可见提示', async () => {
    apiGet.mockResolvedValue({ success: false, error: 'network failed', data: null })
    const wrapper = mountView()
    await flushHomeLoad()

    expect(wrapper.get('[data-testid="home-load-error"]').text()).toContain('暂时无法加载')
  })
})
