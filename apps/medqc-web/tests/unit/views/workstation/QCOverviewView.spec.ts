import { defineComponent, h, nextTick } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

// 本文件的日期断言以北京时间为基准，不能依赖开发机或CI宿主时区。
const originalTimezone = process.env.TZ
beforeAll(() => { process.env.TZ = 'Asia/Shanghai' })
afterAll(() => {
  if (originalTimezone === undefined) delete process.env.TZ
  else process.env.TZ = originalTimezone
})

const apiGet = vi.hoisted(() => vi.fn())
const routeState = vi.hoisted(() => ({
  query: {} as Record<string, string | string[]>,
  path: '/workstation-v5',
  activeRoute: null as null | { query: Record<string, string | string[]>; path: string },
}))
const routerPush = vi.hoisted(() => vi.fn())
const routerReplace = vi.hoisted(() => vi.fn())
const authState = vi.hoisted(() => ({
  isDemoAccount: false,
  roles: ['admin'] as string[],
}))

vi.mock('@/services/apiService', () => ({
  ApiService: { get: apiGet },
}))

vi.mock('vue-router', async () => {
  const { reactive, nextTick } = await import('vue')
  return {
    useRoute: () => {
      const route = reactive({
        query: { ...routeState.query },
        path: routeState.path,
        get fullPath() {
          const params = new URLSearchParams()
          for (const [k, v] of Object.entries(this.query as Record<string, string | string[]>)) {
            if (Array.isArray(v)) v.forEach((item) => params.append(k, String(item)))
            else if (v !== undefined) params.set(k, String(v))
          }
          return `${this.path}?${params.toString()}`
        },
      })
      routeState.activeRoute = route
      routerReplace.mockImplementation(
        async ({ query }: { query: Record<string, string | string[]> }) => {
          route.query = query
          await nextTick()
        },
      )
      return route
    },
    useRouter: () => ({ push: routerPush, replace: routerReplace }),
  }
})

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return { is_demo_account: authState.isDemoAccount, roles: authState.roles }
    },
    get userRoles() {
      return authState.roles
    },
  }),
}))

import QCOverviewView from '@/views/workstation/QCOverviewView.vue'
import type { ClinicalQcHomePayload } from '@/views/workstation/types'

const HomeHeroBarStub = defineComponent({
  name: 'HomeHeroBar',
  setup() {
    return () => h('div', { 'data-testid': 'home-filter' })
  },
})

const clinicalQcPayload = {
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
} satisfies ClinicalQcHomePayload

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
    authState.roles = ['admin']
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

  it('明确显示部分失败与全部失败份数，不归入完成数量', async () => {
    apiGet.mockResolvedValue({ success: true, data: {
      ...clinicalQcPayload,
      clinical_qc: { ...clinicalQcPayload.clinical_qc,
        kpis: { ...clinicalQcPayload.clinical_qc.kpis,
          qc_completed_total: 11, qc_partial_failed_total: 1, qc_failed_total: 1,
        },
      },
    } })
    const wrapper = mountView()
    await flushHomeLoad()
    expect(wrapper.text()).toContain('部分失败 1 份、执行失败 1 份')
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
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
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
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
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
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
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
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect((wrapper.get('select[aria-label="统计科室"]').element as HTMLSelectElement).value).toBe(
      department,
    )
    wrapper.unmount()
  })

  it('三个工作入口进入对应页面，且均保留筛选条件', async () => {
    routeState.query = { department: '神经外科', keyword: '心衰' }
    const wrapper = mountView()
    await flushHomeLoad()
    const entries = wrapper.findAll('.qc-home-shortcuts button')
    expect(entries).toHaveLength(3)
    await entries[0].trigger('click')
    expect(routerPush).toHaveBeenLastCalledWith({
      path: '/workstation-v5/worklist',
      query: { source: 'dashboard', department: '神经外科', keyword: '心衰' },
    })
    await entries[1].trigger('click')
    expect(routerPush).toHaveBeenLastCalledWith({
      path: '/workstation-v5/records/running',
      query: { department: '神经外科', keyword: '心衰' },
    })
    await entries[2].trigger('click')
    expect(routerPush).toHaveBeenLastCalledWith({
      path: '/workstation-v5/records/final',
      query: { department: '神经外科', keyword: '心衰' },
    })
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
      { label: '有确定问题的病历', value: '2份', helper: '需重点复核与整改' },
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
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
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
    await wrapper.get('[data-testid="analysis-metric"]').setValue('average')
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

    await wrapper.get('[data-testid="analysis-sort"]').setValue('risk')
    await nextTick()
    expect(wrapper.findAll('[data-testid="defect-analysis-row"]')[0].text()).toContain('张主任医师')

    await wrapper.get('[data-testid="analysis-sort"]').setValue('gap')
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

  it('真实展示 data_health 同步状态与运行中任务数，不再恒定输出待核实/待接入', async () => {
    apiGet.mockResolvedValue({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          data_health: {
            source_sync_status: 'synced',
            source_error_total: 0,
            technical_error_total: 0,
            running_task_total: 3,
            running_task_state: 'running',
            last_successful_qc_at: '2026-08-08T01:20:00',
          },
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    const healthItems = wrapper.findAll('[data-testid="health-status-item"]')
    expect(healthItems[0].text()).toContain('已同步')
    expect(healthItems[0].text()).not.toContain('待核实')
    expect(healthItems[1].text()).toContain('运行中（3 个）')
    expect(healthItems[1].text()).not.toContain('待接入')
    // 无时区后缀的 UTC 时间按 Asia/Shanghai 正确转换为 09:20
    expect(healthItems[3].text()).toContain('2026-08-08 09:20')
  })

  it.each([
    ['healthy', 'idle', 0, '正常', '空闲'],
    ['degraded', 'idle', null, '部分异常', '空闲'],
    ['failed', 'running', null, '同步失败', '运行中'],
  ])(
    '按真实状态映射 data_health (%s / %s)',
    async (syncStatus, taskState, taskTotal, expectedSync, expectedTask) => {
      apiGet.mockResolvedValue({
        success: true,
        data: {
          ...clinicalQcPayload,
          clinical_qc: {
            ...clinicalQcPayload.clinical_qc,
            data_health: {
              ...clinicalQcPayload.clinical_qc.data_health,
              source_sync_status: syncStatus,
              running_task_state: taskState,
              running_task_total: taskTotal,
            },
          },
        },
      })
      const wrapper = mountView()
      await flushHomeLoad()

      const healthItems = wrapper.findAll('[data-testid="health-status-item"]')
      expect(healthItems[0].text()).toContain(expectedSync)
      expect(healthItems[1].text()).toContain(expectedTask)
    },
  )

  it('眉标按 hospital_scope、当前科室及 rule_set_key 动态展示，不再写死全院或泸县0609质控点', async () => {
    routeState.query = { department: '心内科' }
    apiGet.mockResolvedValue({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          scope: {
            ...clinicalQcPayload.clinical_qc.scope,
            hospital_scope: 'doctor',
            department: '心内科',
            rule_set_key: 'hospital_custom_qc',
            rule_set_version: 'v2',
          },
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    const scopeText = wrapper.get('[data-testid="home-scope"]').text()
    expect(scopeText).toContain('本人负责病历')
    expect(scopeText).toContain('心内科')
    expect(scopeText).toContain('hospital_custom_qc v2')
    expect(scopeText).not.toContain('全院')
    expect(scopeText).not.toContain('泸县0609质控点')
    expect(wrapper.get('[data-testid="home-kpis"]').text()).toContain('本人负责病历 · 心内科')

    apiGet.mockResolvedValueOnce({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          scope: {
            ...clinicalQcPayload.clinical_qc.scope,
            hospital_scope: 'institute',
            department: null,
            rule_set_key: 'luxian_0609_qc_v1',
            rule_set_version: 'v1',
          },
        },
      },
    })
    await wrapper.get('select[aria-label="统计科室"]').setValue('all')
    await flushHomeLoad()
    const instScopeText = wrapper.get('[data-testid="home-scope"]').text()
    expect(instScopeText).toContain('本院区')
    expect(instScopeText).toContain('泸县0609质控点')
    expect(instScopeText).not.toContain('全院')
  })

  it.each([['doctor'], ['super_admin']])(
    '角色 %s 仅展示选择病历质控，隐藏无权访问的运行/终末病历质控入口',
    async (role) => {
      authState.roles = [role]
      const wrapper = mountView()
      await flushHomeLoad()

      const buttons = wrapper.findAll('.qc-home-shortcuts button')
      expect(buttons).toHaveLength(1)
      expect(buttons[0].text()).toBe('选择病历质控')
    },
  )

  it.each([['admin'], ['qc_manager'], ['sync_admin']])(
    '角色 %s 展示全部三个质控工作入口',
    async (role) => {
      authState.roles = [role]
      const wrapper = mountView()
      await flushHomeLoad()

      const buttons = wrapper.findAll('.qc-home-shortcuts button')
      expect(buttons.map((b) => b.text())).toEqual(['选择病历质控', '运行病历质控', '终末病历质控'])
    },
  )

  it('演示账号通过 confirmedResultsOnly 统一隐藏技术异常、未全部完成、非确定结论及待核实维度', async () => {
    authState.isDemoAccount = true
    authState.roles = ['admin']
    apiGet.mockResolvedValue({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          kpis: {
            ...clinicalQcPayload.clinical_qc.kpis,
            qc_completed_total: 11,
            qc_partial_failed_total: 2,
            qc_failed_total: 1,
          },
          canonical_status_counts: {
            non_compliant: 12,
            compliant: 30,
            data_gap: 8,
            uncertain: 4,
            not_applicable: 15,
            not_executed: 3,
          },
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    const health = wrapper.get('[data-testid="data-health"]').text()
    expect(health).not.toContain('技术异常')
    expect(health).not.toContain('未全部完成')
    expect(wrapper.find('[data-testid="qc-execution-failures"]').exists()).toBe(false)

    const conclusion = wrapper.get('[data-testid="qc-conclusion-chart"]').text()
    expect(conclusion).toContain('确定问题 12')
    expect(conclusion).toContain('合规 30')
    expect(conclusion).not.toContain('资料待核实')
    expect(conclusion).not.toContain('待判断')
    expect(conclusion).not.toContain('不适用')
    expect(conclusion).not.toContain('未执行')

    const defects = wrapper.get('[data-testid="defect-analysis-chart"]').text()
    expect(defects).not.toContain('待核实')
    const sortOptions = wrapper
      .findAll('[data-testid="analysis-sort"] option')
      .map((node) => node.attributes('value'))
    expect(sortOptions).toEqual(['metric', 'risk'])

    // sync_admin 即使带演示账号标记，仍保留完整诊断视图
    wrapper.unmount()
    authState.roles = ['sync_admin']
    const syncAdminWrapper = mountView()
    await flushHomeLoad()
    expect(syncAdminWrapper.get('[data-testid="data-health"]').text()).toContain('技术异常')
    expect(syncAdminWrapper.find('[data-testid="qc-execution-failures"]').exists()).toBe(true)
    expect(syncAdminWrapper.get('[data-testid="qc-conclusion-chart"]').text()).toContain('资料待核实 8')
    expect(syncAdminWrapper.get('[data-testid="defect-analysis-chart"]').text()).toContain('待核实')
    syncAdminWrapper.unmount()
  })

  it('保留完整科室选项并在加载失败时维持工具栏可用以支持恢复', async () => {
    apiGet
      .mockResolvedValueOnce({
        success: true,
        data: {
          ...clinicalQcPayload,
          department_options: ['神经外科', '心内科', '呼吸内科'],
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          ...clinicalQcPayload,
          department_options: ['心内科'],
        },
      })
      .mockResolvedValueOnce({ success: false, error: '503 unavailable', data: null })

    const wrapper = mountView()
    await flushHomeLoad()

    const select = wrapper.get('select[aria-label="统计科室"]')
    await select.setValue('心内科')
    await flushHomeLoad()
    expect(select.findAll('option').map((o) => o.attributes('value'))).toEqual([
      'all',
      '神经外科',
      '心内科',
      '呼吸内科',
    ])

    await select.setValue('呼吸内科')
    await flushHomeLoad()
    expect(wrapper.find('[data-testid="home-load-error"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="home-load-error"]').attributes('role')).toBe('alert')
    expect(wrapper.find('.qc-home-toolbar').exists()).toBe(true)
    expect((wrapper.get('select[aria-label="统计科室"]').element as HTMLSelectElement).value).toBe(
      '呼吸内科',
    )
  })

  it('不嵌套 main 标签，移除 KPI 水印并对零值 KPI 完全中性化', async () => {
    apiGet.mockResolvedValueOnce({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          kpis: {
            records_total: 18,
            qc_pending_total: 0,
            qc_completed_total: 18,
            high_risk_review_total: 0,
          },
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    expect(wrapper.find('main.mq-page').exists()).toBe(false)
    expect(wrapper.find('div.mq-page').exists()).toBe(true)
    expect(wrapper.find('.qc-home-metric__watermark').exists()).toBe(false)

    const riskCard = wrapper.get('.qc-home-metric--risk')
    expect(riskCard.classes()).toContain('is-zero')
    expect(riskCard.get('mq-icon-tile-stub').attributes('tone')).toBe('neutral')
  })

  it('支持再次点击已选中科室取消筛选，并正确设置 aria-pressed、is-physician、title 与 aria-hidden', async () => {
    const wrapper = mountView()
    await flushHomeLoad()

    const deptBtn = wrapper.get('[data-testid="analysis-object-department"]')
    const physBtn = wrapper.get('[data-testid="analysis-object-physician"]')
    expect(deptBtn.attributes('aria-pressed')).toBe('true')
    expect(physBtn.attributes('aria-pressed')).toBe('false')

    const row = wrapper.get('[data-testid="defect-analysis-row"]')
    expect(row.attributes('aria-pressed')).toBe('false')
    expect(row.get('.qc-home-defect-analysis__meta strong').attributes('title')).toBe('神经外科')
    expect(row.get('.qc-home-defect-analysis__metric').attributes('aria-hidden')).toBeUndefined()
    expect(row.get('.qc-home-defect-analysis__track').attributes('aria-hidden')).toBe('true')

    await row.trigger('click')
    await flushHomeLoad()
    expect(wrapper.get('[data-testid="defect-analysis-row"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('[data-testid="defect-analysis-row"]').classes()).toContain('is-active')

    // 再次点击已选中科室，切换回全部科室
    apiGet.mockClear()
    await wrapper.get('[data-testid="defect-analysis-row"]').trigger('click')
    await flushHomeLoad()
    expect(apiGet).toHaveBeenCalledWith(
      '/api/v1/workstation/qc-home',
      expect.objectContaining({ department: undefined }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(wrapper.get('[data-testid="defect-analysis-row"]').attributes('aria-pressed')).toBe('false')

    await physBtn.trigger('click')
    await nextTick()
    expect(physBtn.attributes('aria-pressed')).toBe('true')
    expect(wrapper.findAll('[data-testid="defect-analysis-row"]')[0].classes()).toContain('is-physician')
  })

  it('平均缺陷数小于 1 时按实际最大值满幅缩放，且非零进度条标记 is-nonzero', async () => {
    apiGet.mockResolvedValueOnce({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          department_distribution: [
            {
              department: '心内科',
              records_total: 10,
              completed_record_total: 10,
              high_risk_review_total: 2,
              data_gap_record_total: 0,
              uncertain_record_total: 0,
              defect_total: 4,
              average_defect_count: 0.4,
            },
            {
              department: '呼吸内科',
              records_total: 10,
              completed_record_total: 10,
              high_risk_review_total: 1,
              data_gap_record_total: 0,
              uncertain_record_total: 0,
              defect_total: 1,
              average_defect_count: 0.1,
            },
            {
              department: '骨科',
              records_total: 10,
              completed_record_total: 10,
              high_risk_review_total: 0,
              data_gap_record_total: 0,
              uncertain_record_total: 0,
              defect_total: 0,
              average_defect_count: 0,
            },
          ],
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    await wrapper.get('[data-testid="analysis-metric"]').setValue('average')
    await nextTick()

    const bars = wrapper.findAll('.qc-home-defect-analysis__track i')
    expect(bars[0].attributes('style')).toContain('width: 100%')
    expect(bars[0].classes()).toContain('is-nonzero')
    expect(bars[1].attributes('style')).toContain('width: 25%')
    expect(bars[1].classes()).toContain('is-nonzero')
    expect(bars[2].attributes('style')).toContain('width: 0%')
    expect(bars[2].classes()).not.toContain('is-nonzero')
  })

  it('使用 SVG 圆环展示结论结构，百分比严格归一化至 100%，极小非零切片保留最小可见弧长，并反映部分失败态', async () => {
    apiGet.mockResolvedValueOnce({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          kpis: {
            ...clinicalQcPayload.clinical_qc.kpis,
            qc_partial_failed_total: 2,
          },
          canonical_status_counts: {
            non_compliant: 1,
            data_gap: 1,
            compliant: 1000,
          },
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    const ring = wrapper.get('.qc-home-conclusion__ring')
    expect(ring.attributes('role')).toBe('img')
    expect(ring.attributes('aria-label')).toContain('含未全部完成病历')
    expect(ring.find('svg.qc-home-conclusion__svg').exists()).toBe(true)

    const circles = ring.findAll('svg.qc-home-conclusion__svg circle')
    // 1 背景轨 + 3 切片弧
    expect(circles).toHaveLength(4)
    const firstDash = Number(circles[1].attributes('stroke-dasharray')?.split(' ')[0] || 0)
    expect(firstDash).toBeGreaterThanOrEqual(6)

    const percents = wrapper
      .findAll('.qc-home-conclusion__percent')
      .map((node) => Number(node.text().replace('%', '')))
    const sumTenths = percents.reduce((acc, pct) => acc + Math.round(pct * 10), 0)
    expect(sumTenths).toBe(1000)
  })

  it('当 records_total 为 0 时渲染清晰空态提示，并将关键词与清除按钮包裹为同一不拆行分组', async () => {
    routeState.query = { keyword: '罕见病历关键字' }
    apiGet.mockResolvedValueOnce({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          kpis: {
            records_total: 0,
            qc_pending_total: 0,
            qc_completed_total: 0,
            high_risk_review_total: 0,
          },
          canonical_status_counts: {},
          department_distribution: [],
          physician_distribution: [],
        },
      },
    })
    const wrapper = mountView()
    await flushHomeLoad()

    expect(wrapper.find('[data-testid="home-zero-records"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="home-zero-records"]').text()).toContain('当前筛选范围内暂无纳入病历')
    const keywordGroup = wrapper.get('.qc-home-toolbar__keyword-group')
    expect(keywordGroup.find('.qc-home-toolbar__keyword').attributes('title')).toBe('关键词：罕见病历关键字')
    expect(keywordGroup.find('[aria-label="清除关键词"]').exists()).toBe(true)
  })

  it('科室切换同步至 URL（all 时移除 department）且不触发重复请求，并忽略无关查询参数变更', async () => {
    const wrapper = mountView()
    await flushHomeLoad()
    expect(apiGet).toHaveBeenCalledWith(
      '/api/v1/workstation/qc-home',
      expect.objectContaining({ priority_limit: 0 }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )

    apiGet.mockClear()
    routerReplace.mockClear()
    await wrapper.get('select[aria-label="统计科室"]').setValue('神经外科')
    await flushHomeLoad()
    expect(routerReplace).toHaveBeenCalledWith({ query: { department: '神经外科' } })
    expect(apiGet).toHaveBeenCalledTimes(1)

    // 无关 query 变化不触发重新拉取，也不覆盖当前科室选择
    apiGet.mockClear()
    routeState.activeRoute!.query = { ...routeState.activeRoute!.query, utm: 'banner' }
    await flushHomeLoad()
    expect(apiGet).not.toHaveBeenCalled()
    expect((wrapper.get('select[aria-label="统计科室"]').element as HTMLSelectElement).value).toBe(
      '神经外科',
    )

    // 切回全部科室时从 URL 移除 department，保留其他参数且仅请求一次
    routerReplace.mockClear()
    await wrapper.get('select[aria-label="统计科室"]').setValue('all')
    await flushHomeLoad()
    expect(routerReplace).toHaveBeenCalledWith({ query: { utm: 'banner' } })
    expect(apiGet).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('兼容数组型与带空白的 URL 筛选参数', async () => {
    routeState.query = { department: ['  神经外科  ', '心内科'], keyword: ['  心衰  '] }
    const wrapper = mountView()
    await flushHomeLoad()

    expect(apiGet).toHaveBeenLastCalledWith(
      '/api/v1/workstation/qc-home',
      expect.objectContaining({ department: '神经外科', keyword: '心衰', priority_limit: 0 }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect((wrapper.get('select[aria-label="统计科室"]').element as HTMLSelectElement).value).toBe(
      '神经外科',
    )
    expect(wrapper.get('[data-testid="home-scope"]').text()).toContain('关键词：心衰')
    wrapper.unmount()
  })

  it('缺陷分析行向非演示用户透明展示未全部完成份数，对演示用户隐藏', async () => {
    apiGet.mockResolvedValue({
      success: true,
      data: {
        ...clinicalQcPayload,
        clinical_qc: {
          ...clinicalQcPayload.clinical_qc,
          department_distribution: [
            {
              ...clinicalQcPayload.clinical_qc.department_distribution[0],
              partial_failed_record_total: 2,
            },
          ],
          physician_distribution: [
            {
              ...clinicalQcPayload.clinical_qc.physician_distribution[0],
              partial_failed_record_total: 1,
            },
          ],
        },
      },
    })

    const wrapper = mountView()
    await flushHomeLoad()
    expect(wrapper.get('[data-testid="defect-analysis-row"]').text()).toContain(
      '纳入 18 份 · 完成 13 份 · 未全部完成 2 份',
    )
    await wrapper.get('[data-testid="analysis-object-physician"]').trigger('click')
    await nextTick()
    expect(wrapper.get('[data-testid="defect-analysis-row"]').text()).toContain(
      '纳入 10 份 · 完成 8 份 · 未全部完成 1 份',
    )
    wrapper.unmount()

    authState.isDemoAccount = true
    const demoWrapper = mountView()
    await flushHomeLoad()
    expect(demoWrapper.get('[data-testid="defect-analysis-row"]').text()).not.toContain('未全部完成')
    demoWrapper.unmount()
  })
})
