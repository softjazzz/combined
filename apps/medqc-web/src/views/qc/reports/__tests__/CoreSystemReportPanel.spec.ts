import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CoreSystemReportPanel from '../CoreSystemReportPanel.vue'

const mocks = vi.hoisted(() => ({ get: vi.fn(), export: vi.fn() }))
vi.mock('@/api/coreSystemReports', () => ({
  getCoreSystemReport: mocks.get,
  exportCoreSystemReport: mocks.export,
}))
const actor = reactive({ id: 'synthetic-user' })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: actor }) }))
const systems = Array.from({ length: 18 }, (_, index) => ({
  id: `CORE-${String(index + 1).padStart(2, '0')}`,
  name: `合成制度${index + 1}`,
  record_count: index ? null : 1,
  problem_records: index ? null : 0,
  problem_rate: index ? null : 0,
  points: index
    ? []
    : [
        {
          rule_id: 'R1',
          rule_name: '合成质控点',
          rule_set_key: 'synthetic',
          rule_set_version: 'v1',
          record_count: 1,
          problem_records: 0,
        },
      ],
}))
const row = {
  institute_id: 'H1',
  patient_id: 'P1',
  visit_id: 'V1',
  patient_name: '合成患者',
  department: '内科',
  doctor: '合成医生',
  coverage: 'known',
  completed_at: '2026-10-01T00:00:00Z',
  root_job_id: 'J1',
  envelope_id: 'E1',
  rule_set_key: 'synthetic',
  rule_set_version: 'v1',
  points: [
    {
      rule_id: 'R1',
      rule_name: '合成质控点',
      status: 'compliant',
      is_confirmed_issue: false,
      system_ids: ['CORE-01'],
    },
  ],
}
const result = {
  as_of: '2026-10-01T00:00:00Z',
  contract: '已配置质控点范围的问题率',
  scope: { scope_label: '当前在院病历' },
  summary: { candidate_records: 1, unknown_records: 0, unknown_points: 0, unavailable_records: 0 },
  systems,
  reference: {
    reference_date: '2018-04-18',
    source_url: 'https://www.nhc.gov.cn/reference',
    reference_note: '2018版参考，不代表最新院方政策',
    systems: systems.map((s) => ({ ...s, text: '（一）定义\n合成定义\n（二）基本要求\n合成要求' })),
  },
  items: [row],
  total: 1,
  page: 1,
  page_size: 20,
}
const render = () =>
  mount(CoreSystemReportPanel, {
    global: {
      stubs: { 'a-drawer': { props: ['open'], template: '<div v-if="open"><slot /></div>' } },
    },
  })
beforeEach(() => {
  vi.resetAllMocks()
  actor.id = 'synthetic-user'
  mocks.get.mockResolvedValue(result)
})
describe('核心制度专题页面', () => {
  it('继承共有筛选白名单，上海草稿与API保持同一时间窗口，人工来源不混入', async () => {
    const initialFilters = {
      scene: 'final' as const,
      department: '内科',
      doctor: '合成医生',
      completed_from: '2026-10-01T08:00',
      completed_to: '2026-10-01T01:00:30.123Z',
      defect_source: 'manual' as const,
      institute_id: '禁止继承机构',
      system_id: 'CORE-01',
    }
    const wrapper = mount(CoreSystemReportPanel, {
      props: { initialFilters },
      global: { stubs: { 'a-drawer': true } },
    })
    await flushPromises()
    expect(mocks.get).toHaveBeenLastCalledWith(
      {
        scene: 'final',
        institute_id: '',
        department: '内科',
        doctor: '合成医生',
        completed_from: '2026-10-01T00:00:00.000Z',
        completed_to: '2026-10-01T01:00:30.123Z',
        system_id: '',
        rule_id: '',
        problems_only: false,
      },
      1,
    )
    const dates = wrapper.findAll('input[type="datetime-local"]')
    expect((dates[0].element as HTMLInputElement).value).toBe('2026-10-01T08:00')
    expect((dates[1].element as HTMLInputElement).value).toBe('2026-10-01T09:00:30.123')
    expect(wrapper.text()).toContain('人工缺陷未纳入')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.get.mock.calls[0][0]).toEqual(mocks.get.mock.lastCall?.[0])
    wrapper.unmount()
  })
  it.each(['场景', '账号'])('切换%s重置继承筛选并忽略旧请求', async (change) => {
    let old!: (value: typeof result) => void
    mocks.get
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            old = resolve
          }),
      )
      .mockResolvedValue({ ...result, items: [], total: 0 })
    const wrapper = mount(CoreSystemReportPanel, {
      props: { initialFilters: { scene: 'running', doctor: '已查询医生' } },
      global: { stubs: { 'a-drawer': true } },
    })
    await wrapper.findAll('input')[0].setValue('旧机构')
    if (change === '场景')
      await wrapper.setProps({ initialFilters: { scene: 'final', doctor: '已查询医生' } })
    else actor.id = 'new-user'
    await flushPromises()
    old(result)
    await flushPromises()
    expect(mocks.get).toHaveBeenLastCalledWith(
      expect.objectContaining({
        scene: change === '场景' ? 'final' : 'running',
        doctor: '已查询医生',
        institute_id: '',
      }),
      1,
    )
    expect(wrapper.text()).not.toContain('合成患者')
    wrapper.unmount()
  })
  it('场景变更隔离旧导出，旧响应不释放新导出的忙状态', async () => {
    let old!: (value: Blob) => void
    let current!: (value: Blob) => void
    mocks.export
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            old = resolve
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            current = resolve
          }),
      )
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:synthetic'),
      revokeObjectURL: vi.fn(),
    })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const wrapper = mount(CoreSystemReportPanel, {
      props: { initialFilters: { scene: 'running' } },
      global: { stubs: { 'a-drawer': true } },
    })
    try {
      await flushPromises()
      const button = wrapper.get('header button')
      await button.trigger('click')
      await wrapper.setProps({ initialFilters: { scene: 'final' } })
      await flushPromises()
      expect(button.attributes('disabled')).toBeUndefined()
      await button.trigger('click')
      old(new Blob(['old']))
      await flushPromises()
      expect(click).not.toHaveBeenCalled()
      expect(button.attributes('disabled')).toBeDefined()
      current(new Blob(['current']))
      await flushPromises()
      expect(click).toHaveBeenCalledTimes(1)
      expect(button.attributes('disabled')).toBeUndefined()
    } finally {
      wrapper.unmount()
      vi.unstubAllGlobals()
      vi.restoreAllMocks()
    }
  })
  it('制度缺陷排行按确认条目计数，下钻和导出保持仅问题病例', async () => {
    mocks.get.mockResolvedValue({
      ...result,
      summary: { ...result.summary, unknown_defects: 3 },
      top_systems: [{ id: 'CORE-01', name: '合成制度1', defect_total: 2 }],
      systems: systems.map((system) => ({
        ...system,
        defect_total: system.id === 'CORE-01' ? 2 : null,
      })),
    })
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:synthetic'),
      revokeObjectURL: vi.fn(),
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    mocks.export.mockResolvedValue(new Blob(['synthetic']))
    const wrapper = render()
    try {
      await flushPromises()
      const unknownDefects = wrapper
        .findAll('.core-metric')
        .find((card) => card.text().startsWith('未知分类确认缺陷'))!
      expect(unknownDefects.get('strong').text()).toBe('3')
      expect(wrapper.get('[data-testid="core-defect-top"]').text()).toContain('合成制度1 · 2 条')
      await wrapper.get('[data-testid="core-defect-top"] button').trigger('click')
      await flushPromises()
      expect(mocks.get).toHaveBeenLastCalledWith(
        expect.objectContaining({ system_id: 'CORE-01', problems_only: true }),
        1,
      )
      await wrapper.get('header button').trigger('click')
      await flushPromises()
      expect(mocks.export).toHaveBeenCalledWith(
        expect.objectContaining({ system_id: 'CORE-01', problems_only: true }),
      )
    } finally {
      wrapper.unmount()
      vi.unstubAllGlobals()
      vi.restoreAllMocks()
    }
  })
  it('主报表的终末场景作为制度查询初始场景', async () => {
    const wrapper = mount(CoreSystemReportPanel, {
      props: { initialScene: 'final' },
      global: { stubs: { 'a-drawer': true } },
    })
    await flushPromises()
    expect(mocks.get).toHaveBeenLastCalledWith(expect.objectContaining({ scene: 'final' }), 1)
    wrapper.unmount()
  })
  it('完成时间按上海时区提交，逆序窗口不发送查询', async () => {
    const wrapper = render()
    await flushPromises()
    const dates = wrapper.findAll('input[type="datetime-local"]')
    await dates[0].setValue('2026-10-01T08:00')
    await dates[1].setValue('2026-10-01T09:00')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.get).toHaveBeenLastCalledWith(
      expect.objectContaining({
        completed_from: '2026-10-01T00:00:00.000Z',
        completed_to: '2026-10-01T01:00:00.000Z',
      }),
      1,
    )
    const count = mocks.get.mock.calls.length
    await dates[0].setValue('2026-10-02T08:00')
    await wrapper.get('form').trigger('submit')
    expect(mocks.get).toHaveBeenCalledTimes(count)
    expect(wrapper.get('[role="alert"]').text()).toContain('上海时间窗口')
    wrapper.unmount()
  })
  it('18制度列表保留真实0/无配置，原文与冻结缺陷点可打开', async () => {
    const wrapper = render()
    await flushPromises()
    expect(wrapper.text()).toContain('合成制度18')
    expect(wrapper.text()).toContain('0.0%')
    expect(wrapper.text()).toContain('无配置数据')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '原文与缺陷点')!
      .trigger('click')
    expect(wrapper.text()).toContain('（一）定义')
    expect(wrapper.text()).toContain('2018版参考')
    expect(wrapper.text()).toContain('synthetic/v1')
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '病例下钻')!
      .trigger('click')
    await flushPromises()
    expect(mocks.get).toHaveBeenLastCalledWith(
      expect.objectContaining({ system_id: 'CORE-01', rule_id: 'R1' }),
      1,
    )
  })
  it('病例详情保留三坐标、冻结job和envelope而非重新判定', async () => {
    const wrapper = render()
    await flushPromises()
    // 覆盖状态用胶囊展示，状态文案与映射不变
    const statuses = wrapper.findAll('tbody .mq-status')
    expect(statuses.length).toBeGreaterThan(0)
    for (const status of statuses) {
      if (status.text() === '已核验分类') expect(status.classes()).toEqual(['mq-status'])
    }
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '详情')!
      .trigger('click')
    expect(wrapper.text()).toContain('H1 / P1 / V1')
    expect(wrapper.text()).toContain('运行 J1 · 结果 E1')
    expect(wrapper.text()).toContain('非确认问题')
  })
  it('来源失败明确错误，不显示空制度合规表', async () => {
    mocks.get.mockRejectedValue(new Error('来源不可用'))
    const wrapper = render()
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toBe('来源不可用')
    expect(wrapper.find('table').exists()).toBe(false)
  })
  it('CSV使用已经应用的筛选而非未查询的草稿', async () => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:synthetic'),
      revokeObjectURL: vi.fn(),
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    mocks.export.mockResolvedValue(new Blob(['synthetic']))
    const wrapper = render()
    await flushPromises()
    await wrapper.findAll('input')[0].setValue('H1')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    await wrapper.findAll('input')[0].setValue('H2')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '导出 CSV')!
      .trigger('click')
    await flushPromises()
    expect(mocks.export).toHaveBeenCalledWith(expect.objectContaining({ institute_id: 'H1' }))
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })
  it('较早响应和卸载后响应不覆盖新的筛选结果', async () => {
    let old: ((value: typeof result) => void) | undefined
    mocks.get
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            old = resolve
          }),
      )
      .mockResolvedValueOnce({ ...result, total: 0, items: [] })
    const wrapper = render()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    old?.(result)
    await flushPromises()
    expect(wrapper.text()).not.toContain('合成患者')
    wrapper.unmount()
  })
})
