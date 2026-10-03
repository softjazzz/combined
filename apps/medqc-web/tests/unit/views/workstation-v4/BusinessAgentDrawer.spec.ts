import { defineComponent, ref, type ComponentPublicInstance, type PropType } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  BusinessAgentAccess,
  BusinessEvidenceDocument,
  BusinessAgentContext,
  BusinessAgentTurn,
  BusinessAgentReference,
} from '@/api/businessAgent'

const mocks = vi.hoisted(() => ({
  duplicateSecond: false,
  guideline: false,
  managerDrilldown: false,
  statisticsChart: false,
  history: undefined as BusinessAgentTurn[] | undefined,
  access: vi.fn(),
  send: vi.fn(),
  activate: vi.fn(),
  reference: vi.fn(),
  evidenceDocument: vi.fn(),
  feedback: vi.fn(),
  submitFeedback: vi.fn(),
  confirmAction: vi.fn(),
  readAction: vi.fn(),
}))
vi.mock('@/api/businessAgent', () => ({
  businessAgentApi: {
    access: mocks.access,
    reference: mocks.reference,
    evidenceDocument: mocks.evidenceDocument,
    feedback: mocks.feedback,
    submitFeedback: mocks.submitFeedback,
    confirmAction: mocks.confirmAction,
    readAction: mocks.readAction,
  },
}))
vi.mock('@/views/workstation-v4/composables/useBusinessAgent', () => ({
  useBusinessAgent: () => ({
    sessionId: ref('session-a'),
    turns: ref(
      mocks.history || [
        {
          run_id: 'run-a',
          question: '查看问题',
          answer: '保存结论',
          references: [
            ...(mocks.guideline
              ? [
                  {
                    id: 'guideline:a:0',
                    kind: 'guideline',
                    title: '仅相关的规范',
                    locator: '检索片段',
                  },
                ]
              : []),
            ...(mocks.managerDrilldown
              ? [
                  {
                    id: 'stats-a',
                    kind: 'statistics',
                    title: '原统计',
                    ...(mocks.statisticsChart
                      ? {
                          chart: {
                            type: 'bar',
                            metric: '不合规次数',
                            unit: '次',
                            points: [{ label: '图表规则甲', value: 9 }],
                            caption: '按正式不合规次数降序展示前 5 条规则，不计算占比。',
                          },
                        }
                      : {}),
                  },
                  { id: 'record-a', kind: 'record', title: '下钻病例' },
                ]
              : []),
            {
              id: 'result-a',
              position: 1,
              kind: 'saved_result',
              title: '保存问题',
              rule_id: 'LX0609-01',
            },
            { id: 'result-second', position: 2, kind: 'saved_result', title: '第二条保存问题' },
            ...(mocks.duplicateSecond
              ? [{ id: 'other-second', position: 2, kind: 'saved_result', title: '另一页第二条' }]
              : []),
          ],
          result_pages: [
            {
              job_id: 'task-a',
              record_ref: 'record-a',
              statuses: ['non_compliant'],
              page: 1,
              page_size: 2,
              total: 75,
              matched_total: 4,
              returned: 2,
              has_more: true,
              status_counts: { compliant: 71, non_compliant: 4 },
              reference_ids: ['result-a', 'result-second'],
            },
          ],
          elapsed_ms: 100,
          tool_calls: 1,
          status: 'completed',
        },
      ],
    ),
    loading: ref(false),
    error: ref(''),
    activate: mocks.activate,
    send: mocks.send,
    stop: vi.fn(),
    reset: vi.fn(),
  }),
}))
import BusinessAgentDrawer from '@/views/workstation-v4/components/BusinessAgentDrawer.vue'

const Select = defineComponent({ props: { value: String, options: Array }, template: '<div />' })
const Range = defineComponent({
  props: { value: Array as PropType<string[]> },
  emits: ['update:value'],
  template: '<div />',
})
function mountDrawer(
  userContext: BusinessAgentContext = { view: 'manager' },
  allowCaseSelection = false,
) {
  return shallowMount(BusinessAgentDrawer, {
    props: { open: true, userContext, allowCaseSelection },
    global: {
      stubs: {
        BusinessAgentAnswer: false,
        BusinessAgentChart: false,
        BusinessAgentWelcome: false,
        'a-drawer': { template: '<div><slot /></div>' },
        'a-modal': { template: '<div><slot /></div>' },
        'a-button': {
          props: { disabled: Boolean, href: String },
          template:
            '<a v-if="href" :href="href"><slot /></a><button v-else :disabled="disabled"><slot /></button>',
        },
        'a-select': Select,
        'a-range-picker': Range,
        'a-alert': { props: ['message'], template: '<div>{{ message }}</div>' },
        'a-textarea': true,
      },
    },
  })
}

describe('管理助手范围选择', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.duplicateSecond = false
    mocks.guideline = false
    mocks.managerDrilldown = false
    mocks.statisticsChart = false
    mocks.history = undefined
    mocks.activate.mockResolvedValue(undefined)
    mocks.send.mockResolvedValue(undefined)
  })
  it.each([
    {
      name: '管理者固定规则验收路径',
      view: 'manager',
      kind: 'rule',
      entry: '/workstation-v4/rules/validation/LX0609-01-01-01',
      visible: true,
    },
    {
      name: '外站路径',
      view: 'manager',
      kind: 'rule',
      entry: 'https://example.com/workstation-v4/rules/validation/LX0609-01-01-01',
      visible: false,
    },
    {
      name: '另一规则路径',
      view: 'manager',
      kind: 'rule',
      entry: '/workstation-v4/rules/validation/LX0609-01-01-02',
      visible: false,
    },
    {
      name: '路径附带查询参数',
      view: 'manager',
      kind: 'rule',
      entry: '/workstation-v4/rules/validation/LX0609-01-01-01?next=https://example.com',
      visible: false,
    },
    {
      name: '医生视图',
      view: 'doctor',
      kind: 'rule',
      entry: '/workstation-v4/rules/validation/LX0609-01-01-01',
      visible: false,
    },
    {
      name: '普通来源',
      view: 'manager',
      kind: 'saved_result',
      entry: '/workstation-v4/rules/validation/LX0609-01-01-01',
      visible: false,
    },
    {
      name: '旧规则来源无入口字段',
      view: 'manager',
      kind: 'rule',
      entry: undefined,
      visible: false,
    },
    {
      name: '当前目录规则来源附带入口字段',
      view: 'manager',
      kind: 'rule',
      id: 'rule:LX0609-01-01-01',
      entry: '/workstation-v4/rules/validation/LX0609-01-01-01',
      visible: false,
    },
  ] satisfies {
    name: string
    view: 'manager' | 'doctor'
    kind: BusinessAgentReference['kind']
    id?: string
    entry: string | undefined
    visible: boolean
  }[])('$name仅显示已核验的本地验收入口', async ({ view, kind, id, entry, visible }) => {
    const referenceId = id || (kind === 'rule' ? 'rule-validation:LX0609-01-01-01' : 'saved:source')
    const validation = referenceId === 'rule-validation:LX0609-01-01-01'
    const reference: BusinessAgentReference = {
      id: referenceId,
      kind,
      rule_id: 'LX0609-01-01-01',
      title: '已保存来源',
      text: '来源内容仍正常显示',
      ...(entry ? { entry_path: entry } : {}),
    }
    mocks.history = [
      {
        run_id: 'rule-source',
        question: '查询规则',
        answer: '查看来源',
        references: [reference],
        status: 'completed',
        elapsed_ms: 0,
        tool_calls: 1,
      },
    ]
    mocks.access.mockResolvedValue({
      doctor_case_count: 1,
      manager_scopes: [{ institute_id: 'H', department: '内科' }],
    })
    mocks.reference.mockResolvedValue(reference)
    const wrapper = mountDrawer({
      view,
      institute_id: 'H',
      department: '内科',
      patient_id: 'P',
      visit_id: 'V',
    })
    await flushPromises()
    await wrapper
      .findAll('button')
      .find(
        (button) =>
          button.text() ===
          (validation ? '查看验收记录' : kind === 'rule' ? '查看规则详情' : '查看依据与详情'),
      )!
      .trigger('click')
    await flushPromises()
    const link = wrapper.find('[data-testid="business-agent-rule-validation-link"]')
    expect(link.exists()).toBe(visible)
    if (validation) {
      expect(wrapper.text()).toContain('已保存的规则验收摘要')
      expect(wrapper.text()).not.toContain('当前规则目录口径；')
    }
    if (visible) {
      expect(link.element.tagName).toBe('A')
      expect(link.attributes('href')).toBe('/workstation-v4/rules/validation/LX0609-01-01-01')
      expect(link.text()).toBe('打开规则验收记录')
    }
    expect(wrapper.text()).toContain('来源内容仍正常显示')
    expect(wrapper.text()).not.toContain('验收通过')
    wrapper.unmount()
  })
  it('反馈读取失败不可提交，重试回显既有反馈且不再提供提交按钮', async () => {
    mocks.access.mockResolvedValue({ doctor_case_count: 1, manager_scopes: [] })
    mocks.feedback.mockRejectedValueOnce({ response: { status: 503 } })
    const wrapper = mountDrawer({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    await flushPromises()
    await wrapper.findAll('[data-testid="business-agent-feedback-open"]')[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="business-agent-feedback-submit"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('反馈服务暂不可用')
    mocks.feedback.mockResolvedValueOnce({
      target: {
        reference_id: 'result-a',
        institute_id: 'H',
        patient_id: 'P',
        visit_id: 'V',
        rule_id: 'R',
        title: '问题',
      },
      data: {
        id: 'saved',
        reference_id: 'result-a',
        status: 'submitted',
        comment: '此前已提交理由',
        created_at: '2026-10-02',
      },
    })
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '重新核对反馈对象')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('此前已提交理由')
    expect(wrapper.find('[data-testid="business-agent-feedback-submit"]').exists()).toBe(false)
    expect(mocks.submitFeedback).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('异议理由必填、失败同标识重试且提交中防重复', async () => {
    mocks.access.mockResolvedValue({ doctor_case_count: 1, manager_scopes: [] })
    const target = {
      reference_id: 'result-a',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
      rule_id: 'R',
      title: '保存问题',
    }
    mocks.feedback.mockResolvedValue({ target, data: null })
    const wrapper = mountDrawer({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    await flushPromises()
    await wrapper.findAll('[data-testid="business-agent-feedback-open"]')[0].trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="business-agent-feedback-target"]').text()).toContain('患者 P')
    const submit = wrapper.get('[data-testid="business-agent-feedback-submit"]')
    expect(submit.attributes('disabled')).toBeDefined()
    wrapper
      .findComponent<ComponentPublicInstance>('[data-testid="business-agent-feedback-comment"]')
      .vm.$emit('update:value', ' 原判定存在异议 ')
    await flushPromises()
    mocks.submitFeedback.mockRejectedValueOnce({ response: { status: 503 } })
    await submit.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('未确认提交成功')
    const firstPayload = mocks.submitFeedback.mock.calls[0][1]
    let finish!: (value: unknown) => void
    mocks.submitFeedback.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    await submit.trigger('click')
    await submit.trigger('click')
    expect(mocks.submitFeedback).toHaveBeenCalledTimes(2)
    expect(mocks.submitFeedback.mock.calls[1][1]).toEqual(firstPayload)
    expect(firstPayload.comment).toBe('原判定存在异议')
    expect(wrapper.text()).not.toContain('异议反馈已提交')
    finish({
      id: 'feedback-a',
      reference_id: 'result-a',
      status: 'submitted',
      comment: firstPayload.comment,
      created_at: '2026-10-02',
    })
    await flushPromises()
    expect(wrapper.text()).toContain('异议反馈已提交')
    expect(wrapper.find('[data-testid="business-agent-feedback-submit"]').exists()).toBe(false)
    expect(mocks.send).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('切换患者取消反馈提交且迟到成功不会串入新患者', async () => {
    mocks.access.mockResolvedValue({ doctor_case_count: 1, manager_scopes: [] })
    mocks.feedback.mockResolvedValue({
      target: {
        reference_id: 'result-a',
        institute_id: 'H',
        patient_id: 'P',
        visit_id: 'V',
        rule_id: 'R',
        title: '问题',
      },
      data: null,
    })
    const wrapper = mountDrawer({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    await flushPromises()
    await wrapper.findAll('[data-testid="business-agent-feedback-open"]')[0].trigger('click')
    await flushPromises()
    wrapper
      .findComponent<ComponentPublicInstance>('[data-testid="business-agent-feedback-comment"]')
      .vm.$emit('update:value', '异议理由')
    await flushPromises()
    let finish!: (value: unknown) => void
    mocks.submitFeedback.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    await wrapper.get('[data-testid="business-agent-feedback-submit"]').trigger('click')
    const signal = mocks.submitFeedback.mock.calls[0][2] as AbortSignal
    await wrapper.setProps({
      userContext: { view: 'doctor', institute_id: 'H', patient_id: 'OTHER', visit_id: 'OTHER' },
    })
    expect(signal.aborted).toBe(true)
    finish({ status: 'submitted', comment: '迟到反馈' })
    await flushPromises()
    expect(wrapper.text()).not.toContain('异议反馈已提交')
    expect(wrapper.text()).not.toContain('迟到反馈')
    wrapper.unmount()
  })
  it('管理下钻可定位原汇总，不请求刷新；切换范围清除返回位置', async () => {
    mocks.managerDrilldown = true
    mocks.access.mockResolvedValue({
      doctor_case_count: 0,
      manager_scopes: [{ institute_id: 'H', department: 'D' }],
    })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.find('[data-testid="business-agent-return-summary"]').exists()).toBe(false)
    wrapper.findComponent(Range).vm.$emit('update:value', ['2026-09-01', '2026-09-30'])
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '查看病例问题')!
      .trigger('click')
    await flushPromises()
    const target = wrapper.get('[data-run-id="run-a"]').element as HTMLElement
    target.scrollIntoView = vi.fn()
    target.focus = vi.fn()
    const before = mocks.send.mock.calls.length
    await wrapper.get('[data-testid="business-agent-return-summary"]').trigger('click')
    expect(target.scrollIntoView).toHaveBeenCalledWith({ block: 'start' })
    expect(target.focus).toHaveBeenCalledWith({ preventScroll: true })
    expect(mocks.send).toHaveBeenCalledTimes(before)
    expect(mocks.reference).not.toHaveBeenCalled()
    wrapper.findComponent(Range).vm.$emit('update:value', ['2026-08-01', '2026-08-31'])
    await flushPromises()
    expect(wrapper.find('[data-testid="business-agent-return-summary"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('内嵌模式不渲染抽屉外壳、自带标题和关闭按钮，仍保留新建会话', async () => {
    const wrapper = shallowMount(BusinessAgentDrawer, {
      props: { open: true, embedded: true, userContext: { view: 'manager' } },
      global: {
        stubs: {
          BusinessAgentAnswer: false,
          BusinessAgentChart: false,
          BusinessAgentWelcome: false,
          'a-drawer': { template: '<aside data-testid="drawer-shell"><slot /></aside>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': Select,
          'a-range-picker': Range,
          'a-alert': { props: ['message'], template: '<div>{{ message }}</div>' },
          'a-textarea': true,
        },
      },
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="drawer-shell"]').exists()).toBe(false)
    expect(wrapper.find('.business-agent--embedded').exists()).toBe(true)
    expect(wrapper.find('.ba-head__title').exists()).toBe(false)
    expect(wrapper.find('.ba-avatar--lg').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="关闭"]').exists()).toBe(false)
    expect(wrapper.find('button[aria-label="新建会话"]').exists()).toBe(true)
    wrapper.unmount()
  })
  it('欢迎页显示宿主给的待办摘要，点未读消息请求宿主切到消息页签；无摘要时不显示', async () => {
    const mountWith = (summary: { pending: number; unread: number } | null) =>
      shallowMount(BusinessAgentDrawer, {
        props: { open: true, embedded: true, userContext: { view: 'manager' }, summary },
        global: {
          stubs: {
            BusinessAgentAnswer: false,
            BusinessAgentWelcome: false,
            'a-select': Select,
            'a-range-picker': Range,
            'a-button': { template: '<button><slot /></button>' },
            'a-modal': { template: '<div><slot /></div>' },
            'a-textarea': true,
          },
        },
      })
    mocks.history = []
    mocks.access.mockResolvedValue({
      doctor_case_count: 0,
      manager_scopes: [{ institute_id: 'H', department: 'D' }],
    })
    const wrapper = mountWith({ pending: 31, unread: 30 })
    await flushPromises()
    expect(wrapper.get('[data-testid="business-agent-todo"]').text()).toContain('31')
    await wrapper.get('[data-testid="business-agent-todo-messages"]').trigger('click')
    expect(wrapper.emitted('open-tab')).toEqual([['message']])
    wrapper.unmount()
    const bare = mountWith(null)
    await flushPromises()
    expect(bare.find('[data-testid="business-agent-todo"]').exists()).toBe(false)
    bare.unmount()
  })
  it('统计卡带图表数据时在卡片内显示图表，没有图表数据时不显示', async () => {
    mocks.managerDrilldown = true
    mocks.statisticsChart = true
    mocks.access.mockResolvedValue({
      doctor_case_count: 0,
      manager_scopes: [{ institute_id: 'H', department: 'D' }],
    })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.find('[data-testid="business-agent-chart"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('图表规则甲')
    wrapper.unmount()
    mocks.statisticsChart = false
    const plain = mountDrawer()
    await flushPromises()
    expect(plain.find('[data-testid="business-agent-chart"]').exists()).toBe(false)
    plain.unmount()
  })
  it('恢复已有统计历史后不猜测下钻位置，点击病例才建立返回锚点', async () => {
    mocks.managerDrilldown = true
    mocks.access.mockResolvedValue({
      doctor_case_count: 0,
      manager_scopes: [{ institute_id: 'H', department: 'D' }],
    })
    const wrapper = mountDrawer()
    await flushPromises()
    expect(wrapper.text()).toContain('原统计')
    expect(wrapper.find('[data-testid="business-agent-return-summary"]').exists()).toBe(false)
    expect(mocks.send).not.toHaveBeenCalled()
    expect(mocks.reference).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it.each([false, true])(
    '混合历史回填按病例首次来源返回；缺原轮=%s时不猜汇总',
    async (missingOrigin) => {
      const references = (suffix: string): BusinessAgentTurn['references'] => [
        { id: `stats-${suffix}`, kind: 'statistics', title: `统计${suffix}` },
        { id: `record-${suffix}`, kind: 'record', title: `病例${suffix}` },
      ]
      const makeTurn = (
        run_id: string,
        refs: BusinessAgentTurn['references'],
      ): BusinessAgentTurn => ({
        run_id,
        question: run_id,
        answer: run_id,
        references: refs,
        elapsed_ms: 1,
        tool_calls: 1,
        status: 'completed',
      })
      mocks.history = [
        ...(!missingOrigin ? [makeTurn('original-a', references('a'))] : []),
        makeTurn('original-b', references('b')),
        {
          ...makeTurn('explanation', [...references('a'), ...references('b')]),
          reference_scope: 'prior_turns',
          tool_calls: 0,
        },
      ]
      mocks.access.mockResolvedValue({
        doctor_case_count: 0,
        manager_scopes: [{ institute_id: 'H', department: 'D' }],
      })
      const wrapper = mountDrawer()
      await flushPromises()
      wrapper.findComponent(Range).vm.$emit('update:value', ['2026-09-01', '2026-09-30'])
      await flushPromises()
      const buttons = wrapper.get('[data-run-id="explanation"]').findAll('button')
      await buttons.find((node) => node.text() === '查看病例问题')!.trigger('click')
      await flushPromises()
      const back = wrapper.find('[data-testid="business-agent-return-summary"]')
      if (missingOrigin) expect(back.exists()).toBe(false)
      else {
        const target = wrapper.get('[data-run-id="original-a"]').element as HTMLElement
        target.scrollIntoView = vi.fn()
        target.focus = vi.fn()
        await back.trigger('click')
        expect(target.focus).toHaveBeenCalled()
        expect(mocks.send).toHaveBeenCalledTimes(1)
        expect(mocks.reference).not.toHaveBeenCalled()
      }
      wrapper.unmount()
    },
  )
  it('同会话先统计后提醒，打开提醒病例清除旧汇总且不误返之前统计', async () => {
    const makeTurn = (
      run_id: string,
      references: BusinessAgentTurn['references'],
    ): BusinessAgentTurn => ({
      run_id,
      references,
      question: run_id,
      answer: run_id,
      elapsed_ms: 1,
      tool_calls: 1,
      status: 'completed',
    })
    mocks.history = [
      makeTurn('statistics', [
        { id: 'stats-a', kind: 'statistics', title: '之前统计' },
        { id: 'record-statistics', kind: 'record', title: '统计病例' },
      ]),
      makeTurn('followups', [{ id: 'record-followup', kind: 'record', title: '提醒关联病例' }]),
    ]
    mocks.access.mockResolvedValue({
      doctor_case_count: 0,
      manager_scopes: [{ institute_id: 'H', department: 'D' }],
    })
    const wrapper = mountDrawer()
    await flushPromises()
    wrapper.findComponent(Range).vm.$emit('update:value', ['2026-09-01', '2026-09-30'])
    await flushPromises()
    await wrapper
      .get('[data-run-id="statistics"]')
      .findAll('button')
      .find((button) => button.text() === '查看病例问题')!
      .trigger('click')
    expect(wrapper.find('[data-testid="business-agent-return-summary"]').exists()).toBe(true)
    await wrapper
      .get('[data-run-id="followups"]')
      .findAll('button')
      .find((button) => button.text() === '查看病例问题')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="business-agent-return-summary"]').exists()).toBe(false)
    expect(mocks.send).toHaveBeenLastCalledWith(
      '查看“提醒关联病例”的保存质控问题',
      expect.objectContaining({ view: 'manager' }),
      'record-followup',
    )
    wrapper.unmount()
  })
  it('规则未读取时按明确编号及保存引用发起查询', async () => {
    mocks.access.mockResolvedValue({ doctor_case_count: 1, manager_scopes: [] })
    const wrapper = mountDrawer({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '查询这条规则')!
      .trigger('click')
    expect(mocks.send).toHaveBeenCalledWith(
      '查询规则 LX0609-01 的当前目录口径、启用状态与依据',
      expect.objectContaining({ view: 'doctor' }),
      'result-a',
    )
    expect(wrapper.get('[data-testid="business-agent-readonly-notice"]').text()).toContain(
      '查看提醒与整改记录',
    )
    expect(wrapper.text()).toContain('异议反馈需本人填写理由并提交')
    wrapper.unmount()
  })
  it('宿主声明画像面板时医生视图可请求打开同病例面板，管理视图不显示', async () => {
    mocks.access.mockResolvedValue({ doctor_case_count: 1, manager_scopes: [] })
    const wrapper = mountDrawer({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="business-agent-open-profile"]').exists()).toBe(false)
    await wrapper.setProps({ panels: ['profile'] })
    await wrapper.get('[data-testid="business-agent-open-profile"]').trigger('click')
    expect(wrapper.emitted('open-panel')).toEqual([
      [{ panel: 'profile', institute_id: 'H', patient_id: 'P', visit_id: 'V' }],
    ])
    expect(wrapper.text()).toContain('打开面板不会自动分析')
    wrapper.unmount()
    const manager = mountDrawer({ view: 'manager', institute_id: 'H', department: 'D' })
    await manager.setProps({ panels: ['profile'] })
    await flushPromises()
    expect(manager.find('[data-testid="business-agent-open-profile"]').exists()).toBe(false)
    manager.unmount()
  })
  it('操作预览仅在用户点击后确认，确认后展示正式任务状态且不能再次确认', async () => {
    const future = new Date(Date.now() + 600000).toISOString()
    const preview: BusinessAgentReference = {
      id: 'action:1',
      kind: 'action',
      action_id: '1',
      title: '单病例复检 · 1条规则',
      status: 'previewed',
      allowed: true,
      confirmation_hash: 'a'.repeat(64),
      expires_at: future,
      text: '操作：单病例复检；状态：待确认',
    }
    mocks.history = [
      {
        run_id: 'action',
        question: '再检查一下',
        answer: '已生成复检预览，请确认',
        references: [
          preview,
          {
            ...preview,
            id: 'action:2',
            action_id: '2',
            allowed: false,
            text: '不能执行：同步失败',
          },
          { ...preview, id: 'action:3', action_id: '3', expires_at: '2000-01-01T00:00:00Z' },
        ],
        status: 'completed',
        elapsed_ms: 0,
        tool_calls: 1,
      },
    ]
    mocks.access.mockResolvedValue({ doctor_case_count: 1, manager_scopes: [] })
    mocks.confirmAction.mockResolvedValue({
      ...preview,
      status: 'submitted',
      confirmation_hash: null,
      job_id: 'job-1',
      text: '正式任务 job-1：queued',
    })
    mocks.readAction.mockResolvedValue({
      ...preview,
      status: 'submitted',
      text: '正式任务 job-1：completed',
    })
    const wrapper = mountDrawer({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    await flushPromises()
    const confirms = wrapper.findAll('[data-testid="business-agent-action-confirm"]')
    // 不可执行或已过期的预览不提供确认按钮。
    expect(confirms).toHaveLength(1)
    expect(mocks.confirmAction).not.toHaveBeenCalled()
    await confirms[0].trigger('click')
    await flushPromises()
    expect(mocks.confirmAction).toHaveBeenCalledWith('session-a', '1', 'a'.repeat(64))
    expect(wrapper.find('[data-testid="business-agent-action-confirm"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('正式任务 job-1：queued')
    await wrapper.get('[data-testid="business-agent-action-refresh"]').trigger('click')
    await flushPromises()
    expect(mocks.readAction).toHaveBeenCalledWith('session-a', '1')
    expect(wrapper.text()).toContain('正式任务 job-1：completed')
    expect(wrapper.text()).toContain('停止对话不会取消已创建任务')
    wrapper.unmount()
  })
  it('确认冲突时提示重新预览且不显示成功', async () => {
    mocks.history = [
      {
        run_id: 'action',
        question: '复检',
        answer: '预览',
        references: [
          {
            id: 'action:1',
            kind: 'action',
            action_id: '1',
            title: '单病例复检',
            status: 'previewed',
            allowed: true,
            confirmation_hash: 'b'.repeat(64),
            expires_at: new Date(Date.now() + 600000).toISOString(),
            text: '待确认',
          },
        ],
        status: 'completed',
        elapsed_ms: 0,
        tool_calls: 1,
      },
    ]
    mocks.access.mockResolvedValue({ doctor_case_count: 1, manager_scopes: [] })
    mocks.confirmAction.mockRejectedValue({ response: { status: 409 } })
    const wrapper = mountDrawer({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    await flushPromises()
    await wrapper.get('[data-testid="business-agent-action-confirm"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('预览已失效；请重新发起预览。本次未提交任务')
    expect(wrapper.text()).not.toContain('正式任务')
    wrapper.unmount()
  })
  it('医生不合规问题可请求参考草稿，草稿卡复制后提示不等于整改', async () => {
    const draftText = '参考草稿：不替代正式保存建议\n草稿：\n【待医生补充：检查原因】'
    mocks.history = [
      {
        run_id: 'draft',
        question: '起草',
        answer: '已生成参考草稿',
        references: [
          { id: 'result-n', kind: 'saved_result', title: '缺检查原因', status: 'non_compliant' },
          { id: 'result-g', kind: 'saved_result', title: '资料不足', status: 'data_gap' },
          { id: 'draft:1', kind: 'draft', title: '参考草稿 · 缺检查原因', text: draftText },
        ],
        status: 'completed',
        elapsed_ms: 0,
        tool_calls: 2,
      },
    ]
    mocks.access.mockResolvedValue({ doctor_case_count: 1, manager_scopes: [] })
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    const wrapper = mountDrawer({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    await flushPromises()
    const requests = wrapper.findAll('[data-testid="business-agent-draft-request"]')
    expect(requests).toHaveLength(1)
    await requests[0].trigger('click')
    expect(mocks.send).toHaveBeenCalledWith(
      expect.stringContaining('“缺检查原因”起草一段参考补充文字'),
      expect.objectContaining({ view: 'doctor' }),
      'result-n',
    )
    expect(wrapper.get('[data-testid="business-agent-draft-text"]').text()).toContain('待医生补充')
    await wrapper.get('[data-testid="business-agent-draft-copy"]').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith(draftText)
    expect(wrapper.get('[data-testid="business-agent-draft-copied"]').text()).toContain(
      '复制不等于整改完成',
    )
    wrapper.unmount()
  })
  it('已读取的规则验收记录不冒充对应规则详情', async () => {
    mocks.history = [
      {
        run_id: 'validation',
        question: '查看验收',
        answer: '验收摘要',
        references: [
          {
            id: 'rule-validation:LX0609-01-01-01',
            kind: 'rule',
            rule_id: 'LX0609-01-01-01',
            title: '规则验收记录',
          },
        ],
        status: 'completed',
        elapsed_ms: 0,
        tool_calls: 1,
      },
      {
        run_id: 'issue',
        question: '查看问题',
        answer: '保存问题',
        references: [
          { id: 'result-v', kind: 'saved_result', title: '保存问题', rule_id: 'LX0609-01-01-01' },
        ],
        status: 'completed',
        elapsed_ms: 0,
        tool_calls: 1,
      },
    ]
    mocks.access.mockResolvedValue({
      doctor_case_count: 0,
      manager_scopes: [{ institute_id: 'H', department: 'D' }],
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const issue = wrapper.get('[data-run-id="issue"]')
    expect(issue.findAll('button').some((button) => button.text() === '查看对应规则')).toBe(false)
    expect(issue.findAll('button').some((button) => button.text() === '查询这条规则')).toBe(true)
    expect(
      wrapper
        .get('[data-run-id="validation"]')
        .findAll('button')
        .some((button) => button.text() === '查看验收记录'),
    ).toBe(true)
    wrapper.unmount()
  })
  it('规范候选明确提示不等于回答依据，仍可读取原文', async () => {
    mocks.guideline = true
    mocks.access.mockResolvedValue({ doctor_case_count: 1, manager_scopes: [] })
    mocks.reference.mockResolvedValue({
      id: 'guideline:a:0',
      kind: 'guideline',
      title: '规范',
      text: '保存原文',
    })
    const wrapper = mountDrawer({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="business-agent-retrieval-notice"]').text()).toContain(
      '不代表均支持上方回答',
    )
    expect(wrapper.text()).toContain('检索资料 · 待核对适用性')
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '查看规范原文')!
      .trigger('click')
    await flushPromises()
    expect(mocks.reference).toHaveBeenCalledWith('session-a', 'guideline:a:0')
    expect(wrapper.text()).toContain('保存原文')
    wrapper.unmount()
  })
  it('首页医生只从服务端授权病例选择，切换患者更新三坐标', async () => {
    mocks.access.mockResolvedValue({
      doctor_case_count: 2,
      doctor_cases: [
        { institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' },
        { institute_id: 'H1', patient_id: 'P2', visit_id: 'V2' },
      ],
      manager_scopes: [],
    })
    const wrapper = mountDrawer({ view: 'manager' }, true)
    await flushPromises()
    const picker = wrapper.findComponent(Select)
    expect(picker.props('options')).toHaveLength(2)
    const query = () =>
      wrapper
        .findAll('button')
        .find((button) => button.text() === '这份病历有哪些已保存的质控问题？')!
    expect(query().attributes('disabled')).toBeDefined()
    picker.vm.$emit('update:value', '["H1","P1","V1"]')
    await flushPromises()
    await query().trigger('click')
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '发送')!
      .trigger('click')
    expect(mocks.send).toHaveBeenLastCalledWith(expect.any(String), {
      view: 'doctor',
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
    })
    picker.vm.$emit('update:value', '["H1","P2","V2"]')
    await flushPromises()
    expect(mocks.activate).toHaveBeenLastCalledWith({
      view: 'doctor',
      institute_id: 'H1',
      patient_id: 'P2',
      visit_id: 'V2',
    })
    picker.vm.$emit('update:value', '["H1","OTHER","V3"]')
    await flushPromises()
    expect(query().attributes('disabled')).toBeDefined()
    expect(wrapper.text()).not.toContain('科室问数')
  })
  it('首页双范围账号可切换病例和科室，旧后端不猜病例列表', async () => {
    mocks.access.mockResolvedValue({
      doctor_case_count: 1,
      doctor_cases: [{ institute_id: 'H1', patient_id: 'P1', visit_id: 'V1' }],
      manager_scopes: [{ institute_id: 'H1', department: '本科室' }],
    })
    const wrapper = mountDrawer({ view: 'manager' }, true)
    await flushPromises()
    expect(wrapper.text()).toContain('管理问数范围')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '病例问题')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('授权病例')
    expect(mocks.activate).toHaveBeenLastCalledWith({ view: 'doctor' })
    wrapper.unmount()
    mocks.access.mockResolvedValue({ doctor_case_count: 1, manager_scopes: [] })
    const legacy = mountDrawer({ view: 'manager' }, true)
    await flushPromises()
    expect(legacy.text()).toContain('没有可选择的授权病例')
    expect(legacy.findComponent(Select).props('options')).toEqual([])
  })
  it('仅使用服务端授权机构/科室，完整日期后才能发送', async () => {
    mocks.access.mockResolvedValue({
      doctor_case_count: 0,
      manager_scopes: [{ institute_id: 'H1', department: '本科室' }],
    })
    const wrapper = mountDrawer()
    await flushPromises()
    const scope = wrapper.findAllComponents(Select)[0]
    expect(scope.props('options')).toEqual([{ value: '["H1","本科室"]', label: '本科室 · H1' }])
    expect(
      wrapper
        .findAll('button')
        .find((node) => node.text() === '发送')!
        .attributes('disabled'),
    ).toBeDefined()
    wrapper.findComponent(Range).vm.$emit('update:value', ['2026-09-01', '2026-09-30'])
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '当前范围哪些质控问题最多？')!
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '发送')!
      .trigger('click')
    expect(mocks.send).toHaveBeenCalledWith('当前范围哪些质控问题最多？', {
      view: 'manager',
      institute_id: 'H1',
      department: '本科室',
      care_phase: 'discharged',
      completed_from: '2026-09-01T00:00:00+08:00',
      completed_to: '2026-09-30T23:59:59+08:00',
    })
    wrapper.unmount()
  })
  it('关闭后迟到的授权响应不能重新填入范围', async () => {
    let finish!: (value: BusinessAgentAccess) => void
    mocks.access.mockImplementationOnce(
      () =>
        new Promise<BusinessAgentAccess>((resolve) => {
          finish = resolve
        }),
    )
    const wrapper = mountDrawer()
    await wrapper.setProps({ open: false })
    finish({
      doctor_case_count: 0,
      manager_scopes: [{ institute_id: 'H2', department: '其他科室' }],
    })
    await flushPromises()
    expect(wrapper.findAllComponents(Select)[0].props('options')).toEqual([])
    expect(mocks.send).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('显示准确页范围并把第二条快捷追问绑定同页稳定id', async () => {
    mocks.access.mockResolvedValue({ doctor_case_count: 2, manager_scopes: [] })
    const context = { view: 'doctor' as const, institute_id: 'H', patient_id: 'P', visit_id: 'V' }
    const wrapper = mountDrawer(context)
    await flushPromises()
    expect(wrapper.get('[data-testid="business-agent-result-page"]').text()).toContain(
      '本页 2 / 匹配 4 条',
    )
    expect(wrapper.get('[data-testid="business-agent-result-page"]').text()).toContain('后续页')
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '第二条为什么不合规？')!
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '发送')!
      .trigger('click')
    expect(mocks.send).toHaveBeenCalledWith('第二条为什么不合规？', context, 'result-second')
    wrapper.unmount()
  })
  it('多个页面都有第二条时阻止快捷问发送，具体卡片仍绑定自己的id', async () => {
    mocks.duplicateSecond = true
    mocks.access.mockResolvedValue({ doctor_case_count: 2, manager_scopes: [] })
    const context = { view: 'doctor' as const, institute_id: 'H', patient_id: 'P', visit_id: 'V' }
    const wrapper = mountDrawer(context)
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '第二条为什么不合规？')!
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '发送')!
      .trigger('click')
    expect(mocks.send).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('存在多个第二条，请点击具体问题卡片的“解释这条”。')
    await wrapper
      .findAll('button')
      .filter((node) => node.text() === '解释这条')
      .at(-1)!
      .trigger('click')
    expect(mocks.send).toHaveBeenCalledWith(
      '解释“另一页第二条”，查看病历证据与规则依据',
      context,
      'other-second',
    )
    wrapper.unmount()
  })
  it('按保存问题选择证据并正确高亮包含表情的 Unicode 坐标', async () => {
    mocks.access.mockResolvedValue({ doctor_case_count: 2, manager_scopes: [] })
    mocks.reference.mockResolvedValue({
      id: 'result-a',
      title: '保存问题',
      kind: 'saved_result',
      evidence: [
        { source_ref: 'src-a', source_type: 'admission_record', evidence_excerpt: '原文摘录' },
      ],
    })
    mocks.evidenceDocument.mockResolvedValue({
      title: '入院记录',
      state: 'located',
      source_view: 'current',
      content: '😀乙原文摘录丁',
      quote: '原文摘录',
      note: '当前文书',
      start: 2,
      end: 6,
      offset_unit: 'unicode_code_points',
    })
    const wrapper = mountDrawer()
    await wrapper.setProps({
      userContext: { view: 'doctor', institute_id: 'H', patient_id: 'P', visit_id: 'V' },
    })
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '查看依据与详情')!
      .trigger('click')
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '查看对应文书原文')!
      .trigger('click')
    await flushPromises()
    expect(mocks.evidenceDocument).toHaveBeenCalledWith('session-a', 'result-a', 0)
    expect(wrapper.get('[data-testid="business-agent-document-location"]').text()).toBe('原文摘录')
    expect(wrapper.get('[data-testid="business-agent-document"]').text()).toBe('😀乙原文摘录丁')
    wrapper.unmount()
  })
  it('切换患者后丢弃迟到的文书原文', async () => {
    mocks.access.mockResolvedValue({ doctor_case_count: 2, manager_scopes: [] })
    mocks.reference.mockResolvedValue({
      id: 'result-a',
      kind: 'saved_result',
      evidence: [{ source_ref: 'src-a', source_type: 'admission_record' }],
    })
    let finish!: (value: BusinessEvidenceDocument) => void
    mocks.evidenceDocument.mockImplementationOnce(
      () =>
        new Promise<BusinessEvidenceDocument>((resolve) => {
          finish = resolve
        }),
    )
    const wrapper = mountDrawer()
    await wrapper.setProps({
      userContext: { view: 'doctor', institute_id: 'H', patient_id: 'P', visit_id: 'V' },
    })
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '查看依据与详情')!
      .trigger('click')
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((node) => node.text() === '查看对应文书原文')!
      .trigger('click')
    await wrapper.setProps({
      userContext: { view: 'doctor', institute_id: 'H', patient_id: 'P2', visit_id: 'V2' },
    })
    finish({
      title: '旧患者文书',
      state: 'quote_not_found',
      source_view: 'current',
      content: '旧患者原文',
      quote: '',
      note: '旧响应',
    })
    await flushPromises()
    expect(wrapper.find('[data-testid="business-agent-document"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
