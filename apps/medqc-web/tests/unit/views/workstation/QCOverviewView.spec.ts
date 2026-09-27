import { defineComponent, h, nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.hoisted(() => vi.fn())
const routeState = vi.hoisted(() => ({
  query: {} as Record<string, string>,
  path: '/workstation-v5',
}))
const routerPush = vi.hoisted(() => vi.fn())
const routerReplace = vi.hoisted(() => vi.fn())
const authState = vi.hoisted(() => ({ isDemoAccount: false }))

vi.mock('@/services/apiService', () => ({
  ApiService: { get: apiGet },
}))

vi.mock('vue-router', async () => {
  const { reactive, nextTick } = await import('vue')
  return {
    useRoute: () => {
      const route = reactive({
        ...routeState,
        get fullPath() {
          return `${this.path}?${new URLSearchParams(this.query).toString()}`
        },
      })
      routerReplace.mockImplementation(async ({ query }: { query: Record<string, string> }) => {
        route.query = query
        await nextTick()
      })
      return route
    },
    useRouter: () => ({ push: routerPush, replace: routerReplace }),
  }
})

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
        status_counts: { non_compliant: 2, data_gap: 1, uncertain: 1 },
        completed_at: '2026-08-08T09:20:00+08:00',
      },
    ],
    department_distribution: [
      {
        department: '神经外科',
        records_total: 18,
        completed_record_total: 13,
        high_risk_review_total: 2,
        data_gap_record_total: 3,
        uncertain_record_total: 0,
        defect_total: 12,
        average_defect_count: 0.92,
      },
    ],
    physician_distribution: [
      {
        physician: '张主任医师',
        records_total: 10,
        completed_record_total: 8,
        high_risk_review_total: 2,
        data_gap_record_total: 1,
        uncertain_record_total: 0,
        defect_total: 11,
        average_defect_count: 1.38,
      },
      {
        physician: '李主治医师',
        records_total: 8,
        completed_record_total: 5,
        high_risk_review_total: 1,
        data_gap_record_total: 2,
        uncertain_record_total: 0,
        defect_total: 9,
        average_defect_count: 1.8,
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
        QcMetricCardStrip: false,
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
    routerReplace.mockClear()
    routeState.query = {}
    authState.isDemoAccount = false
  })

  it('以客户可读范围和真实 KPI 展示概况，不重复病历池', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    expect(wrapper.get('[data-testid="home-scope"]').text()).toContain('全院')
    expect(wrapper.get('[data-testid="home-scope"]').text()).toContain('泸县0609质控点')
    expect(wrapper.get('[data-testid="home-scope"]').text()).not.toContain('luxian_0609_qc_v1')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('18')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('有确定问题的病历')
    expect(wrapper.find('[data-testid="priority-queue"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('测试患者')
    expect(wrapper.text()).not.toContain('较昨日')
    expect(wrapper.text()).not.toContain('近7天')
    expect(wrapper.find('[data-testid="home-trend"]').exists()).toBe(false)
  })

  it('移除搜索栏后在范围行保留科室筛选和刷新', async () => {
    const wrapper = mountView()
    await flushHomeLoad()
    expect(wrapper.find('.qc-home-filter-bar').exists()).toBe(false)
    const select = wrapper.get('select[aria-label="统计科室"]')
    const option = select.findAll('option').find((entry) => entry.attributes('value') !== 'all')
    expect(option).toBeDefined()
    await select.setValue(option!.attributes('value'))
    await flushHomeLoad()
    expect(apiGet).toHaveBeenLastCalledWith(
      '/api/v1/workstation/qc-home',
      expect.objectContaining({ department: option!.attributes('value') }),
    )
    const calls = apiGet.mock.calls.length
    await wrapper.get('[aria-label="刷新首页数据"]').trigger('click')
    await flushHomeLoad()
    expect(apiGet.mock.calls.length).toBe(calls + 1)
  })

  it('旧链接关键词可见且清除后仅刷新一次，保留其余查询条件', async () => {
    routeState.query = { keyword: '测试关键词', department: '神经外科', source: 'bookmark' }
    const wrapper = mountView()
    await flushHomeLoad()
    expect(apiGet).toHaveBeenLastCalledWith(
      '/api/v1/workstation/qc-home',
      expect.objectContaining({ keyword: '测试关键词', department: '神经外科' }),
    )
    expect(wrapper.get('[data-testid="home-scope"]').text()).toContain('关键词：测试关键词')
    apiGet.mockClear()
    await wrapper.get('[aria-label="清除关键词"]').trigger('click')
    await flushHomeLoad()
    expect(routerReplace).toHaveBeenCalledWith({
      query: { department: '神经外科', source: 'bookmark' },
    })
    expect(apiGet).toHaveBeenCalledTimes(1)
    expect(apiGet).toHaveBeenLastCalledWith(
      '/api/v1/workstation/qc-home',
      expect.objectContaining({ keyword: undefined, department: '神经外科' }),
    )
    expect(wrapper.find('[aria-label="清除关键词"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it.each(['all', '神经外科'])('更换科室为 %s 后清除关键词保持当前范围', async (department) => {
    routeState.query = { keyword: '测试关键词', department: '旧科室', source: 'bookmark' }
    const wrapper = mountView()
    await flushHomeLoad()
    await wrapper.get('select[aria-label="统计科室"]').setValue(department)
    await flushHomeLoad()
    apiGet.mockClear()
    await wrapper.get('[aria-label="清除关键词"]').trigger('click')
    await flushHomeLoad()
    expect(routerReplace).toHaveBeenLastCalledWith({
      query: department === 'all' ? { source: 'bookmark' } : { department, source: 'bookmark' },
    })
    expect(apiGet).toHaveBeenCalledTimes(1)
    expect(apiGet).toHaveBeenLastCalledWith(
      '/api/v1/workstation/qc-home',
      expect.objectContaining({
        keyword: undefined,
        department: department === 'all' ? undefined : department,
      }),
    )
    expect((wrapper.get('select[aria-label="统计科室"]').element as HTMLSelectElement).value).toBe(
      department,
    )
    wrapper.unmount()
  })

  it('三个工作入口进入对应页面，病历池保留筛选条件', async () => {
    const wrapper = mountView()
    await flushHomeLoad()
    const entries = wrapper.findAll('.qc-home-shortcuts button')
    expect(entries).toHaveLength(3)
    await entries[0].trigger('click')
    expect(routerPush).toHaveBeenLastCalledWith({
      path: '/workstation-v5/worklist',
      query: { source: 'dashboard', department: undefined, keyword: undefined },
    })
    await entries[1].trigger('click')
    expect(routerPush).toHaveBeenLastCalledWith('/workstation-v5/records/running')
    await entries[2].trigger('click')
    expect(routerPush).toHaveBeenLastCalledWith('/workstation-v5/records/final')
  })

  it('待质控作为主卡展示，其余三项 KPI 按运营顺序排列', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    const hero = wrapper.get('.qc-home-hero')
    expect(hero.get('.qc-home-hero__label').text()).toContain('待质控')
    expect(hero.get('.qc-home-hero__value').text()).toBe('3/ 18 份')

    expect(wrapper.get('[data-testid="home-kpis"]').attributes('aria-label')).toBe('质控指标汇总')
    const cards = wrapper.findAll('.qc-home-metrics > .qc-home-metric')
    expect(cards).toHaveLength(3)
    expect(
      cards.map((card) => ({
        label: card.get('.qc-home-metric__label').text(),
        value: card.get('.qc-home-metric__value').text(),
        helper: card.get('.qc-home-metric__helper').text(),
      })),
    ).toEqual([
      { label: '有确定问题的病历', value: '2份', helper: '含确定问题的病历' },
      { label: '已完成', value: '13份', helper: '已生成正式质控结果' },
      { label: '纳入病历', value: '18份', helper: '当前筛选范围' },
    ])
  })

  it('进度比例全部由现有 KPI 计算', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    // 待质控 3 / 纳入 18 = 16.7%；完成 13 / 18 = 72.2%；问题 2 / 已完成 13 = 15.4%
    expect(wrapper.get('.qc-home-hero__progress').text()).toContain('占纳入病历 16.7%')
    const legend = wrapper.get('.qc-home-rings__legend').text()
    expect(legend).toContain('问题率15.4')
    expect(legend).toContain('完成率72.2')
    expect(legend).toContain('待质控16.7')
  })

  it('将技术异常和未知资料状态放入数据运行状态，不计入高风险队列', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    const health = wrapper.get('[data-testid="data-health"]').text()
    expect(health).toContain('技术异常2 份')
    expect(health).toContain('资料同步待核实')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('有确定问题的病历')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('2')
  })

  it('将数据运行状态组织为可扫描的状态单元', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    const healthItems = wrapper.findAll('[data-testid="health-status-item"]')
    expect(healthItems).toHaveLength(4)
    expect(healthItems[0].text()).toContain('资料同步')
    expect(healthItems[0].text()).toContain('待核实')
    expect(healthItems[1].text()).toContain('质控任务')
    expect(healthItems[1].text()).toContain('待接入')
    expect(healthItems[3].text()).toContain('最近成功质控')
    expect(healthItems[3].text()).toContain('2026-08-08 09:20')
  })

  it('演示账号不展示内部技术异常，但保留客户需要的数据状态', async () => {
    authState.isDemoAccount = true
    const wrapper = mountView()
    await flushHomeLoad()

    const health = wrapper.get('[data-testid="data-health"]').text()
    expect(health).toContain('资料同步')
    expect(health).toContain('质控任务')
    expect(health).toContain('最近成功质控')
    expect(health).not.toContain('技术异常')

    expect(wrapper.get('[data-testid="defect-analysis-chart"]').text()).toContain('神经外科')
    expect(wrapper.find('[data-testid="qc-coverage-chart"]').exists()).toBe(false)
  })

  it('将科室缺陷分析收敛为当前指标的前八项', async () => {
    apiGet.mockResolvedValue({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          department_distribution: Array.from({ length: 9 }, (_, index) => ({
            department: `科室${index + 1}`,
            records_total: index + 10,
            completed_record_total: index + 5,
            high_risk_review_total: index + 1,
            data_gap_record_total: 0,
            uncertain_record_total: 0,
            defect_total: index + 1,
            average_defect_count: Number(((index + 1) / (index + 5)).toFixed(2)),
          })),
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    const chartRows = wrapper.findAll('[data-testid="defect-analysis-row"]')
    expect(chartRows).toHaveLength(8)
    expect(chartRows[0].text()).toContain('科室9')
    expect(wrapper.get('[data-testid="defect-analysis-chart"]').text()).toContain(
      '其余 1 个科室已收起',
    )
  })

  it('使用同一首页响应展示科室待办分布，且不把技术异常混入医疗风险', async () => {
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

    const workload = wrapper.get('[data-testid="defect-analysis-chart"]').text()
    expect(workload).toContain('神经外科')
    expect(workload).toContain('高风险 2')
    expect(workload).toContain('待核实 3')
    expect(workload).toContain('缺陷总数')
    expect(workload).toContain('12')
    expect(workload).not.toContain('结果校验异常')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('有确定问题的病历')
    expect(wrapper.find('[data-testid="priority-queue"]').exists()).toBe(false)
  })

  it('点击科室待办行后切换到该科室范围', async () => {
    const wrapper = mountView()
    await flushHomeLoad()
    apiGet.mockClear()

    await wrapper.get('[data-testid="defect-analysis-row"]').trigger('click')
    await flushHomeLoad()

    expect(apiGet).toHaveBeenCalledWith(
      '/api/v1/workstation/qc-home',
      expect.objectContaining({ department: '神经外科' }),
    )
  })

  it('支持在科室与主治医师之间切换，医生行不伪造后端筛选', async () => {
    const wrapper = mountView()
    await flushHomeLoad()
    apiGet.mockClear()

    await wrapper.get('[data-testid="analysis-object-physician"]').trigger('click')
    await nextTick()

    const analysis = wrapper.get('[data-testid="defect-analysis-chart"]')
    expect(analysis.text()).toContain('张主任医师')
    expect(analysis.text()).toContain('李主治医师')
    expect(analysis.findAll('[data-testid="defect-analysis-row"]')[0].element.tagName).toBe('DIV')
    expect(apiGet).not.toHaveBeenCalled()
  })

  it('支持缺陷总数与平均缺陷数切换，并以已完成病历为平均值口径', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    await wrapper.get('[data-testid="analysis-object-physician"]').trigger('click')
    await wrapper.get('[data-testid="analysis-metric-average"]').trigger('click')
    await nextTick()

    const rows = wrapper.findAll('[data-testid="defect-analysis-row"]')
    expect(rows[0].text()).toContain('李主治医师')
    expect(rows[0].text()).toContain('1.80')
    expect(rows[0].text()).toContain('完成 5 份')
    expect(wrapper.get('[data-testid="defect-analysis-chart"]').text()).toContain(
      '缺陷仅统计确定问题',
    )
  })

  it('支持按当前指标、高风险病历和资料待核实由多到少排序', async () => {
    const wrapper = mountView()
    await flushHomeLoad()
    await wrapper.get('[data-testid="analysis-object-physician"]').trigger('click')

    await wrapper.get('[data-testid="analysis-sort-risk"]').trigger('click')
    await nextTick()
    expect(wrapper.findAll('[data-testid="defect-analysis-row"]')[0].text()).toContain('张主任医师')

    await wrapper.get('[data-testid="analysis-sort-gap"]').trigger('click')
    await nextTick()
    expect(wrapper.findAll('[data-testid="defect-analysis-row"]')[0].text()).toContain('李主治医师')
  })

  it('主治医师统计未返回时展示真实空态', async () => {
    apiGet.mockResolvedValue({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          physician_distribution: [],
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()
    await wrapper.get('[data-testid="analysis-object-physician"]').trigger('click')
    await nextTick()

    expect(
      wrapper.get('[data-testid="defect-analysis-chart"] a-empty-stub').attributes('description'),
    ).toBe('当前范围内暂无主治医师统计')
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

  it('为零结论提供空状态，且不再展示重复的质控覆盖比例', async () => {
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

    expect(wrapper.find('[data-testid="qc-coverage-chart"]').exists()).toBe(false)
    expect(
      wrapper.get('[data-testid="qc-conclusion-chart"] a-empty-stub').attributes('description'),
    ).toBe('暂无已完成质控结论')
  })

  it('将工作入口与第二屏分析区分层展示', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    const workspace = wrapper.get('[data-testid="home-workspace"]')
    expect(workspace.findAll('button')).toHaveLength(3)
    expect(workspace.find('[data-testid="data-health"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="data-health"]').exists()).toBe(true)
    expect(workspace.find('[data-testid="defect-analysis-chart"]').exists()).toBe(false)

    const analysis = wrapper.get('[data-testid="home-analysis"]')
    expect(analysis.find('[data-testid="defect-analysis-chart"]').exists()).toBe(true)
    expect(analysis.find('[data-testid="qc-conclusion-chart"]').exists()).toBe(true)
    expect(analysis.find('[data-testid="department-distribution"]').exists()).toBe(false)
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
