import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiGet = vi.hoisted(() => vi.fn())
const routerPush = vi.hoisted(() => vi.fn())
const routerReplace = vi.hoisted(() => vi.fn())
const routeState = vi.hoisted(() => ({
  path: '/workstation-v5/stats',
  query: {} as Record<string, string | undefined>,
}))
const authState = vi.hoisted(() => ({
  user: { is_demo_account: false, roles: ['admin'] } as {
    is_demo_account?: boolean
    roles?: string[]
  } | null,
}))

vi.mock('@/services/apiService', () => ({ ApiService: { get: apiGet } }))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get user() {
      return authState.user
    },
  }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({
    get path() {
      return routeState.path
    },
    get query() {
      return routeState.query
    },
    get fullPath() {
      return `${routeState.path}?${JSON.stringify(routeState.query)}`
    },
  }),
  useRouter: () => ({
    push: routerPush,
    replace: routerReplace,
  }),
}))

import LuxianQcAnalyticsView from '@/views/workstation-v4/LuxianQcAnalyticsView.vue'

const Stub = defineComponent({
  setup(_, { slots, attrs }) {
    return () => h('div', attrs, slots.default?.())
  },
})

const ButtonStub = defineComponent({
  emits: ['click'],
  setup(_, { slots, attrs, emit }) {
    return () =>
      h(
        'button',
        {
          type: 'button',
          ...attrs,
          onClick: () => emit('click'),
        },
        slots.default?.(),
      )
  },
})

function mountAnalyticsView() {
  return shallowMount(LuxianQcAnalyticsView, {
    global: {
      stubs: {
        'a-button': ButtonStub,
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

function makePayload(overrides: Record<string, unknown> = {}) {
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
      distinct_record_total: 1520,
      completed_event_total: 2340,
      records_with_non_compliant: 1120,
      records_with_data_gap: 340,
      canonical_invalid_or_missing_total: 12,
    },
    status_distribution: [
      { status: 'non_compliant', count: 1120 },
      { status: 'data_gap', count: 340 },
      { status: 'uncertain', count: 60 },
      { status: 'compliant', count: 4000 },
      { status: 'not_applicable', count: 100 },
      { status: 'not_executed', count: 0 },
    ],
    department_distribution: [
      {
        department: '心血管内科与冠心病重症监护病区（一病区）',
        distinct_record_total: 1234,
        non_compliant_record_total: 1000,
        data_gap_record_total: 200,
        uncertain_record_total: 34,
        problem_record_total: 1234,
        primary_non_compliant_record_total: 1000,
        primary_data_gap_record_total: 200,
        primary_uncertain_record_total: 34,
      },
    ],
    physician_distribution: [
      {
        physician: '欧阳司马长风主治医师（心血管病区）',
        distinct_record_total: 1088,
        non_compliant_record_total: 888,
        data_gap_record_total: 150,
        uncertain_record_total: 50,
        problem_record_total: 1088,
        primary_non_compliant_record_total: 888,
        primary_data_gap_record_total: 150,
        primary_uncertain_record_total: 50,
      },
    ],
    rule_distribution: [
      {
        rule_id: 'LX0609-01-01-01',
        rule_name: '三类状态齐全规则',
        non_compliant_count: 1020,
        data_gap_count: 35,
        uncertain_count: 15,
        evaluated_count: 1500,
      },
      {
        rule_id: 'LX0609-01-02-01',
        rule_name: '无确定问题仅待核实与待判断规则',
        non_compliant_count: 0,
        data_gap_count: 24,
        uncertain_count: 8,
        evaluated_count: 1500,
      },
      {
        rule_id: 'LX0609-01-03-01',
        rule_name: '仅待判断规则',
        non_compliant_count: 0,
        data_gap_count: 0,
        uncertain_count: 11,
        evaluated_count: 1500,
      },
    ],
    completion_time_series: Array.from({ length: 16 }, (_, idx) => ({
      bucket: `2026-08-${String(idx + 1).padStart(2, '0')}`,
      completed_event_total: idx === 5 ? 1250 : (idx + 1) * 40,
    })),
    data_health: { canonical_invalid_or_missing_total: 12 },
    ...overrides,
  }
}

const vueSource = readFileSync(
  resolve(__dirname, '../../src/views/workstation-v4/LuxianQcAnalyticsView.vue'),
  'utf8',
)
const styleBlock = vueSource.slice(vueSource.indexOf('<style scoped>'))

describe('Batch D: 统计分析响应式、柱图防溢出、语义色、科室留白与 WCAG AA 无障碍精修', () => {
  beforeEach(() => {
    apiGet.mockReset()
    apiGet.mockResolvedValue({ success: true, data: makePayload() })
    routerPush.mockReset()
    routerReplace.mockReset()
    routeState.path = '/workstation-v5/stats'
    routeState.query = {}
    authState.user = { is_demo_account: false, roles: ['admin'] }
  })

  it('1. v7.1 基础覆写样式位于所有 @media 之前，且 <=1440px 允许筛选栏换行、<=1280px 标题左对齐', () => {
    const firstMediaMatch = styleBlock.match(/^@media\s*\(/m)
    const firstMediaIdx = firstMediaMatch?.index ?? -1
    expect(firstMediaIdx).toBeGreaterThan(0)

    const beforeMedia = styleBlock.slice(0, firstMediaIdx)
    const afterMedia = styleBlock.slice(firstMediaIdx)

    // v7.1 液态玻璃覆写必须在所有 @media 之前，避免覆盖响应式规则
    expect(beforeMedia).toContain('v7.1 液态玻璃基础覆写')
    expect(beforeMedia).toContain('align-items: flex-end;')
    expect(afterMedia).not.toContain('v7.1 液态玻璃')
    expect(afterMedia).not.toContain('align-items: flex-end;')

    // 1440px 断点允许工具栏折行防溢出
    expect(afterMedia).toMatch(/@media\s*\(max-width:\s*1440px\)\s*\{[\s\S]*?\.analytics-toolbar\s*\{[\s\S]*?flex-wrap:\s*wrap;/)
    // 1280px 断点保持标题左对齐和纵向排列
    expect(afterMedia).toMatch(/@media\s*\(max-width:\s*1280px\)\s*\{[\s\S]*?\.analytics-heading\s*\{[\s\S]*?align-items:\s*flex-start;[\s\S]*?flex-direction:\s*column;/)
    // 980px / 640px 断点完整保留
    expect(afterMedia).toContain('@media (max-width: 980px)')
    expect(afterMedia).toContain('@media (max-width: 640px)')
  })

  it('2. 完成节奏柱状图支持 >12 天横向滚动，柱体置于独立 flex:1 min-height:0 轨道内防顶出容器', async () => {
    const wrapper = mountAnalyticsView()
    await flush()

    const trendChart = wrapper.get('[data-testid="analytics-trend"]')
    const bars = trendChart.findAll('.rhythm-bar')
    expect(bars).toHaveLength(16)

    // 最高柱 1,250 在独立 .rhythm-bar-track 轨道内按 100% 渲染，不与顶部数值/底部日期争抢 170px
    const maxBar = bars[5]
    expect(maxBar.get('span').text()).toBe('1,250')
    expect(maxBar.get('.rhythm-bar-track i').attributes('style')).toContain('height: 100%')
    expect(maxBar.get('small').text()).toBe('08-06')

    expect(styleBlock).toMatch(/\.rhythm-chart\s*\{[\s\S]*?overflow-x:\s*auto;/)
    expect(styleBlock).toMatch(/\.rhythm-bar-track\s*\{[\s\S]*?flex:\s*1;[\s\S]*?min-height:\s*0;/)
  })

  it('3. 规则问题标签使用显式语义色类名（is-danger/is-warning/is-neutral），移除 :first-child/:nth-child 规则', async () => {
    const wrapper = mountAnalyticsView()
    await flush()

    const ruleButtons = wrapper.findAll('[data-testid="analytics-rule-chart"] .rule-list button')
    expect(ruleButtons).toHaveLength(3)

    // 规则 1：确定 / 待核实 / 待判断 -> 依次为 is-danger / is-warning / is-neutral
    const tags0 = ruleButtons[0].findAll('.rule-breakdown em')
    expect(tags0.map((el) => el.classes())).toEqual([['is-danger'], ['is-warning'], ['is-neutral']])
    expect(tags0[0].text()).toBe('确定 1,020')

    // 规则 2：无确定问题 -> 第一个 em（待核实）必须是 is-warning 而非红色 is-danger
    const tags1 = ruleButtons[1].findAll('.rule-breakdown em')
    expect(tags1.map((el) => el.classes())).toEqual([['is-warning'], ['is-neutral']])
    expect(tags1[0].text()).toContain('待核实 24')
    expect(tags1[1].text()).toContain('待判断 8')

    // 规则 3：仅待判断 -> 唯一 em 必须是 is-neutral
    const tags2 = ruleButtons[2].findAll('.rule-breakdown em')
    expect(tags2.map((el) => el.classes())).toEqual([['is-neutral']])
    expect(tags2[0].text()).toContain('待判断 11')

    expect(styleBlock).not.toContain('.rule-breakdown em:first-child')
    expect(styleBlock).not.toContain('.rule-breakdown em:nth-child')
    expect(styleBlock).toContain('.rule-breakdown em.is-danger')
    expect(styleBlock).toContain('.rule-breakdown em.is-warning')
    expect(styleBlock).toContain('.rule-breakdown em.is-neutral')
  })

  it('4. 科室报告医师排行满宽无留白、排行数值列 minmax(40px,auto) + 千分位、长名补 :title、堆叠条浮点百分比不溢出', async () => {
    // 4a. 全院视图：验证长名 :title、千分位数值与浮点百分比堆叠条
    apiGet.mockResolvedValueOnce({
      success: true,
      data: makePayload({
        department_distribution: [
          {
            department: '心血管内科与冠心病重症监护病区（一病区）',
            distinct_record_total: 6,
            non_compliant_record_total: 1,
            data_gap_record_total: 1,
            uncertain_record_total: 4,
            problem_record_total: 6,
            primary_non_compliant_record_total: 1,
            primary_data_gap_record_total: 1,
            primary_uncertain_record_total: 4,
          },
        ],
        physician_distribution: [
          {
            physician: '欧阳司马长风主治医师（心血管病区）',
            distinct_record_total: 1234,
            non_compliant_record_total: 1000,
            data_gap_record_total: 200,
            uncertain_record_total: 34,
            problem_record_total: 1234,
            primary_non_compliant_record_total: 1000,
            primary_data_gap_record_total: 200,
            primary_uncertain_record_total: 34,
          },
        ],
      }),
    })

    const hospitalWrapper = mountAnalyticsView()
    await flush()

    expect(hospitalWrapper.find('[data-testid="analytics-department-chart"]').exists()).toBe(true)
    expect(
      hospitalWrapper.get('[data-testid="analytics-physician-chart"]').classes(),
    ).not.toContain('is-full-span')

    // 长科室名 / 长医师名补 :title
    const deptName = hospitalWrapper.get('.department-row .department-name')
    expect(deptName.attributes('title')).toBe('心血管内科与冠心病重症监护病区（一病区）')
    const physName = hospitalWrapper.get('.physician-row .physician-name')
    expect(physName.attributes('title')).toBe('欧阳司马长风主治医师（心血管病区）')

    // 千分位展示
    expect(hospitalWrapper.get('.physician-row strong').text()).toBe('1,234')
    expect(hospitalWrapper.findAll('[data-testid="analytics-kpi"] strong')[0].text()).toBe('1,520')

    // 堆叠条段宽使用浮点百分比（1/6, 1/6, 4/6 -> 16.66%, 16.66%, 66.66%，总和 <= 100%，不会如 Math.round 溢出成 101%）
    const deptRow = hospitalWrapper.get('.department-row')
    const dangerStyle = deptRow.get('.bar-danger').attributes('style') || ''
    const warningStyle = deptRow.get('.bar-warning').attributes('style') || ''
    const uncertainStyle = deptRow.get('.bar-uncertain').attributes('style') || ''
    const parseWidth = (s: string) => Number(s.match(/width:\s*([\d.]+)%/)?.[1] ?? 0)
    const wDanger = parseWidth(dangerStyle)
    const wWarning = parseWidth(warningStyle)
    const wUncertain = parseWidth(uncertainStyle)
    expect(wDanger).toBeCloseTo(16.66, 1)
    expect(wWarning).toBeCloseTo(16.66, 1)
    expect(wUncertain).toBeCloseTo(66.66, 1)
    expect(wDanger + wWarning + wUncertain).toBeLessThanOrEqual(100)
    hospitalWrapper.unmount()

    // 4b. 科室报告视图：隐藏科室排行后，医师排行面板加 .is-full-span 撑满整行
    routeState.query = {
      view: 'department',
      department: '心血管内科与冠心病重症监护病区（一病区）',
    }
    const deptWrapper = mountAnalyticsView()
    await flush()

    expect(deptWrapper.find('[data-testid="analytics-department-chart"]').exists()).toBe(false)
    expect(deptWrapper.get('[data-testid="analytics-physician-chart"]').classes()).toContain(
      'is-full-span',
    )
    deptWrapper.unmount()

    // 4c. CSS 验证：满宽类名与 minmax(40px, auto) 数值列
    expect(styleBlock).toMatch(/\.analytics-physician-panel\.is-full-span\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1;/)
    expect(styleBlock).toMatch(/\.department-row\s*\{[\s\S]*?minmax\(40px,\s*auto\)/)
    expect(styleBlock).toMatch(/\.physician-row\s*\{[\s\S]*?minmax\(40px,\s*auto\)/)
    expect(styleBlock).not.toMatch(/grid-template-columns:[^\n;]*\b(?:28px|32px)\b/)
  })

  it('5. 拉齐 WCAG AA 对比度与无障碍语义（筛选 aria-label、图表 role=img、错误 role=alert、focus-visible）', async () => {
    // 5a. CSS 对比度与焦点环检查
    expect(styleBlock).not.toMatch(/color:\s*rgba\(\s*29,\s*29,\s*31,\s*0\.(?:3\d?|4\d?)\s*\)/)
    expect(styleBlock).toContain('var(--mq-text-secondary)')
    expect(styleBlock).toContain('var(--mq-text-tertiary)')
    expect(styleBlock).toContain('.department-row:focus-visible')
    expect(styleBlock).toContain('.rule-list button:focus-visible')

    // 5b. 正常态 ARIA 语义检查
    const wrapper = mountAnalyticsView()
    await flush()

    expect(wrapper.find('[aria-label="质控完成时间范围"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="筛选科室"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="已完成任务 ID"]').exists()).toBe(true)

    const statusRing = wrapper.get('.status-ring')
    expect(statusRing.attributes('role')).toBe('img')
    expect(statusRing.attributes('aria-label')).toContain('质控结论分布')
    expect(statusRing.attributes('aria-label')).toContain('需重点关注')
    expect(statusRing.attributes('aria-label')).toContain('确定问题')

    const rhythmChart = wrapper.get('[data-testid="analytics-trend"]')
    expect(rhythmChart.attributes('role')).toBe('img')
    expect(rhythmChart.attributes('aria-label')).toContain('近期质控完成量趋势')
    expect(rhythmChart.attributes('aria-label')).toContain('2026-08-06 完成 1,250 次')

    const deptTrack = wrapper.get('.department-row .department-track')
    expect(deptTrack.attributes('role')).toBe('img')
    expect(deptTrack.attributes('aria-label')).toContain('心血管内科与冠心病重症监护病区（一病区）')
    expect(deptTrack.attributes('aria-label')).toContain('1,234')

    // 5c. 演示账号下图表 aria-label 也不泄露待核实/待判断
    wrapper.unmount()
    authState.user = { is_demo_account: true, roles: ['admin'] }
    const demoWrapper = mountAnalyticsView()
    await flush()
    const demoTrackLabel = demoWrapper.get('.department-row .department-track').attributes('aria-label') || ''
    expect(demoTrackLabel).toContain('确定问题')
    expect(demoTrackLabel).not.toContain('待核实')
    expect(demoTrackLabel).not.toContain('待判断')
    demoWrapper.unmount()

    // 5d. 错误态 role="alert" 检查
    authState.user = { is_demo_account: false, roles: ['admin'] }
    apiGet.mockRejectedValueOnce(new Error('后端统计服务超时'))
    const errWrapper = mountAnalyticsView()
    await flush()

    const errorEl = errWrapper.get('[data-testid="analytics-error"]')
    expect(errorEl.attributes('role')).toBe('alert')
    expect(errorEl.text()).toContain('后端统计服务超时')
    errWrapper.unmount()
  })
})
