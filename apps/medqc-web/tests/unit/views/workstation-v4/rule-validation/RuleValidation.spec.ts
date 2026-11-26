import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'

const { visibilityState } = vi.hoisted(() => ({
  visibilityState: { confirmedResultsOnly: false },
}))

vi.mock('@/composables/useQcResultVisibility', () => ({
  useQcResultVisibility: () => ({
    confirmedResultsOnly: ref(visibilityState.confirmedResultsOnly),
  }),
}))

import * as api from '@/services/rule-validation-service'
import type {
  ComparisonRow,
  RuleDetail,
  RuleListItem,
  ValidationCase,
} from '@/services/rule-validation-service'
import RuleValidationListView from '@/views/workstation-v4/rule-validation/RuleValidationListView.vue'
import RuleValidationDetailView from '@/views/workstation-v4/rule-validation/RuleValidationDetailView.vue'
import CaseReviewDrawer from '@/views/workstation-v4/rule-validation/CaseReviewDrawer.vue'
import ApprovalModal from '@/views/workstation-v4/rule-validation/ApprovalModal.vue'
import { expectedStatuses, formatTime, statusLabel } from '@/views/workstation-v4/rule-validation/presentation'

vi.mock('@/services/rule-validation-service', () => ({
  listValidationRules: vi.fn(),
  getValidationRule: vi.fn(),
  listCandidateCases: vi.fn(),
  saveCaseAnswer: vi.fn(),
  removeCaseAnswer: vi.fn(),
  startValidationRun: vi.fn(),
  getValidationRun: vi.fn(),
  reviewCase: vi.fn(),
  concludeRule: vi.fn(),
  approveRule: vi.fn(),
}))
const push = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { ruleId: 'LX0609-06-01-01' }, query: {} }),
  useRouter: () => ({ push, replace: vi.fn() }),
}))
vi.mock('ant-design-vue', () => ({ message: { success: vi.fn(), warning: vi.fn() } }))

const wrap = { template: '<div><slot /></div>' }
const textarea = defineComponent({
  props: ['value'],
  emits: ['update:value'],
  template: `<textarea :value="value" @input="$emit('update:value', $event.target.value)" />`,
})
const stubs = {
  ASpin: wrap,
  AModal: true,
  ADrawer: { props: ['open'], template: '<div v-if="open"><slot /></div>' },
  AAlert: { props: ['message'], template: '<p class="alert">{{ message }}</p>' },
  AInput: textarea,
  ATextarea: textarea,
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
  CaseAnswerModal: true,
  ApprovalModal: true,
  MqIconTile: true,
}

const coverage = (gaps: string[] = []) =>
  ({
    counts: {
      compliant: { synthetic: 1, real_copy: 1 },
      non_compliant: { synthetic: 1, real_copy: 0 },
      not_applicable: { synthetic: 0, real_copy: 0 },
      data_gap: { synthetic: 0, real_copy: 0 },
    },
    gaps,
    acceptance_cases: 1,
  }) as RuleDetail['coverage']

function listItem(overrides: Partial<RuleListItem>): RuleListItem {
  return {
    rule_id: 'LX0609-06-01-01',
    name: '医嘱与病程一致性',
    source_document: 'CT/MRI检查记录',
    release_scope: 'acceptance_only',
    policy_summary: '',
    stage: 'reviewing',
    case_count: 3,
    coverage: coverage(['not_applicable', 'data_gap']),
    latest_run: null,
    ...overrides,
  }
}

const caseA: ValidationCase = {
  item_id: 'a',
  case_title: '合成 · 已记录',
  record_ref: { institute_id: 'I', patient_id: 'P', visit_id: 'A' },
  source_kind: 'synthetic',
  evaluation_as_of_date: '2026-07-05',
  expected_status: 'compliant',
  human_reason: '病程已记录',
  purpose: 'development',
  answer_revision: 1,
}
const caseB: ValidationCase = {
  ...caseA,
  item_id: 'b',
  case_title: '真实副本 · 未记录',
  source_kind: 'real_copy',
  expected_status: 'non_compliant',
  purpose: 'acceptance',
}
const run = {
  id: 'run-1',
  rule_id: 'LX0609-06-01-01',
  cases: [caseA, caseB],
  job_id: 'job-1',
  state: 'bound' as const,
  execution_version: { lx0609_task_runtime: { implementation: { kind: 'process' } } },
  build_kind: 'development' as const,
  created_by: 'u',
  created_at: '2026-09-29T06:20:00',
  regression_cases: [],
  scope_rule_ids: ['LX0609-06-01-01'],
  regression_gaps: [],
  impact: null,
}
const rows: ComparisonRow[] = [
  {
    ...caseA,
    rule_id: 'LX0609-06-01-01',
    role: 'candidate',
    actual_status: 'compliant',
    comparison: 'same',
    result: { status: 'compliant', customer_conclusion: '病程已记录检查目的' },
  },
  {
    ...caseB,
    rule_id: 'LX0609-06-01-01',
    role: 'candidate',
    actual_status: 'compliant',
    comparison: 'different',
    result: {
      status: 'compliant',
      evidence: [{ document_title: '日常病程', evidence_excerpt: '片段' }],
    },
  },
]

function detail(overrides: Partial<RuleDetail> = {}): RuleDetail {
  return {
    rule: {
      rule_id: 'LX0609-06-01-01',
      name: '医嘱与病程一致性',
      source_document: 'CT/MRI检查记录',
      release_scope: 'acceptance_only',
      policy_summary: '口径',
      impact: null,
    },
    stage: 'reviewing',
    cases: [caseA, caseB],
    coverage: coverage(['not_applicable', 'data_gap']),
    runs: [run],
    latest_run_rows: rows,
    acceptance_blockers: ['存在状态不一致、缺少结果或执行失败的病例'],
    regression_gaps: [],
    events: [
      {
        id: 'e1',
        rule_id: 'LX0609-06-01-01',
        run_id: 'run-1',
        item_id: 'a',
        kind: 'case_review',
        decision: 'confirmed',
        note: '证据对',
        payload: {},
        actor: 'r',
        created_at: '2026-09-29T07:00:00',
      },
    ],
    ...overrides,
  }
}

const button = (wrapper: ReturnType<typeof mount>, text: string) =>
  wrapper.findAll('button').find((b) => b.text().includes(text))!

beforeEach(() => {
  vi.resetAllMocks()
  visibilityState.confirmedResultsOnly = false
})

describe('规则验收列表', () => {
  it('旧 UTC 时间和带时区时间跨日后显示同一北京时间', () => {
    expect(formatTime('2026-11-20 16:30:00')).toBe('11-21 00:30')
    expect(formatTime('2026-11-21T00:30:00+08:00')).toBe('11-21 00:30')
  })

  it('资料不足选项使用各规则集原生编码，不转换执行结果', () => {
    expect(expectedStatuses('LX0916-001')).toEqual(['compliant', 'non_compliant', 'not_applicable', 'data_quality_gap'])
    expect(expectedStatuses('LX0609-06-01-03')).toEqual(['compliant', 'non_compliant', 'not_applicable', 'data_gap'])
    expect(statusLabel('data_quality_gap').label).toBe('资料不足')
  })
  it('切换到0916请求独立目录并说明只接入测试', async () => {
    vi.mocked(api.listValidationRules).mockResolvedValue({ success: true, data: { items: [] } })
    const wrapper = mount(RuleValidationListView, { global: { stubs } })
    await flushPromises()
    await wrapper.get('[data-testid="rule-set-select"]').setValue('luxian_0916_qc_v1')
    await flushPromises()
    expect(api.listValidationRules).toHaveBeenLastCalledWith(
      false,
      'luxian_0916_qc_v1',
      expect.objectContaining({ skipErrorToast: true, signal: expect.any(AbortSignal) }),
    )
    expect(wrapper.text()).toContain('逐规则批准上线尚未接通')
    wrapper.unmount()
  })
  it('只列待验收规则，按阶段汇总并链接到详情', async () => {
    vi.mocked(api.listValidationRules).mockResolvedValue({
      success: true,
      data: {
        items: [
          listItem({}),
          listItem({
            rule_id: 'LX0609-06-01-03',
            name: '报告单完整性',
            stage: 'pending_approval',
            case_count: 8,
            coverage: coverage(),
          }),
          listItem({
            rule_id: 'LX0609-06-01-04',
            name: '已上线规则',
            release_scope: 'default',
            stage: 'released',
          }),
        ],
      },
    })
    const wrapper = mount(RuleValidationListView, { global: { stubs } })
    await flushPromises()

    expect(api.listValidationRules).toHaveBeenCalledWith(
      false,
      'luxian_0609_qc_v1',
      expect.objectContaining({ skipErrorToast: true, signal: expect.any(AbortSignal) }),
    )
    const rowsText = wrapper.findAll('[data-testid="rule-row"]').map((r) => r.text())
    expect(rowsText).toHaveLength(2)
    expect(rowsText[0]).toContain('待复核')
    expect(rowsText[0]).toContain('缺 2 类')
    expect(rowsText[1]).toContain('待批准')
    expect(wrapper.text()).toContain('2 条规则待验收')
    expect(wrapper.text()).toContain('11') // 待验收规则的测试病例合计
  })

  it('切换到已上线时带上 include_released 重新加载，只显示已上线规则', async () => {
    vi.mocked(api.listValidationRules).mockResolvedValue({
      success: true,
      data: {
        items: [
          listItem({}),
          listItem({
            rule_id: 'LX0609-06-01-04',
            name: '已上线规则',
            release_scope: 'default',
            stage: 'released',
          }),
        ],
      },
    })
    const wrapper = mount(RuleValidationListView, { global: { stubs } })
    await flushPromises()
    await wrapper.find('[data-testid="scope-released"]').trigger('click')
    await flushPromises()

    expect(api.listValidationRules).toHaveBeenLastCalledWith(
      true,
      'luxian_0609_qc_v1',
      expect.objectContaining({ skipErrorToast: true, signal: expect.any(AbortSignal) }),
    )
    const rowsText = wrapper.findAll('[data-testid="rule-row"]').map((r) => r.text())
    expect(rowsText).toEqual([expect.stringContaining('已上线规则')])
  })
})

describe('规则验收详情', () => {
  it('0916 明示整包执行并阻止生成0609发布单', async () => {
    const data = detail({ stage: 'pending_approval' })
    data.rule = { ...data.rule, rule_id: 'LX0916-001', rule_set_key: 'luxian_0916_qc_v1',
      publication_supported: false, publication_note: '0916 逐规则发布尚未接通',
      execution_mode: 'full_pack', execution_rule_ids: Array.from({ length: 32 }, (_, i) => `LX0916-${i + 1}`) }
    vi.mocked(api.getValidationRule).mockResolvedValue({ success: true, data })
    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('完整规则包（32条）')
    expect(wrapper.text()).toContain('只对照本规则')
    expect(wrapper.text()).toContain('模型版本尚未冻结')
    expect(wrapper.text()).toContain('0916 逐规则发布尚未接通')
    expect(wrapper.get('[data-testid="open-approval"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
  it('展示病例、逐例对照与未满足的通过条件；存在阻碍时不能验收通过', async () => {
    vi.mocked(api.getValidationRule).mockResolvedValue({ success: true, data: detail() })
    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()

    expect(api.getValidationRule).toHaveBeenCalledWith(
      'LX0609-06-01-01',
      expect.objectContaining({ skipErrorToast: true, signal: expect.any(AbortSignal) }),
    )
    expect(wrapper.findAll('[data-testid="case-row"]')).toHaveLength(2)
    const compare = wrapper.findAll('[data-testid="compare-row"]').map((r) => r.text())
    expect(compare[0]).toContain('已确认')
    expect(compare[1]).toContain('不一致')
    expect(compare[1]).toContain('待核对')
    expect(wrapper.text()).toContain('还有 1 例未确认')
    expect(wrapper.text()).toContain('执行版本：开发版本')

    await wrapper.find('textarea[aria-label="验收意见"]').setValue('已核对')
    expect(wrapper.find('[data-testid="accept-rule"]').attributes('disabled')).toBeDefined()
    expect(button(wrapper, '记录不通过').attributes('disabled')).toBeUndefined()
  })

  it('无阻碍时须填写覆盖缺口说明才能通过，并提交最新运行', async () => {
    const confirmedRows = rows.map((r) => ({
      ...r,
      comparison: 'same' as const,
      actual_status: r.expected_status,
    }))
    vi.mocked(api.getValidationRule).mockResolvedValue({
      success: true,
      data: detail({
        stage: 'pending_conclusion',
        latest_run_rows: confirmedRows,
        acceptance_blockers: [],
        events: ['a', 'b'].map((item) => ({
          id: item,
          rule_id: 'LX0609-06-01-01',
          run_id: 'run-1',
          item_id: item,
          kind: 'case_review' as const,
          decision: 'confirmed',
          note: 'ok',
          payload: {},
          actor: 'r',
          created_at: '2026-09-29T07:00:00',
        })),
      }),
    })
    vi.mocked(api.concludeRule).mockResolvedValue({ success: true, data: {} as never })
    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()

    const accept = () => wrapper.find('[data-testid="accept-rule"]')
    await wrapper.find('textarea[aria-label="验收意见"]').setValue('两例均核对')
    expect(accept().attributes('disabled')).toBeDefined()
    await wrapper.find('textarea[aria-label="覆盖缺口说明"]').setValue('不适用、资料不足暂无病例')
    expect(accept().attributes('disabled')).toBeUndefined()
    await accept().trigger('click')
    await flushPromises()

    expect(api.concludeRule).toHaveBeenCalledWith('LX0609-06-01-01', {
      run_id: 'run-1',
      decision: 'accepted',
      note: '两例均核对',
      gap_ack: '不适用、资料不足暂无病例',
    })
  })

  it('共享抽取批次规则显示同族回归，回归有差异或缺保护集时列入通过条件', async () => {
    const impact = {
      impact: 'shared_batch' as const,
      label: '共享抽取批次',
      executor_key: 'exam_lab',
      basis: '检查检验族按选中规则拼接抽取 Prompt',
      peer_rule_ids: ['LX0609-06-01-04', 'LX0609-06-01-05'],
    }
    const peerCase = {
      ...caseA,
      item_id: 'p',
      case_title: '同族保护集病例',
      rule_id: 'LX0609-06-01-04',
    }
    const gap = { rule_id: 'LX0609-06-01-05', name: '同族规则', reason: '尚无验收通过的运行' }
    vi.mocked(api.getValidationRule).mockResolvedValue({
      success: true,
      data: detail({
        rule: { ...detail().rule, impact },
        runs: [
          {
            ...run,
            impact,
            regression_cases: [peerCase],
            scope_rule_ids: ['LX0609-06-01-01', 'LX0609-06-01-04'],
            regression_gaps: [gap],
          },
        ],
        latest_run_rows: [
          ...rows,
          {
            ...peerCase,
            role: 'regression',
            actual_status: 'non_compliant',
            comparison: 'different',
          },
        ],
        regression_gaps: [gap],
      }),
    })
    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()

    expect(wrapper.find('[data-testid="impact-label"]').text()).toBe('共享抽取批次')
    // 回归行不进入本规则的逐例对照
    expect(wrapper.findAll('[data-testid="compare-row"]')).toHaveLength(2)
    const regression = wrapper.findAll('[data-testid="regression-row"]').map((r) => r.text())
    expect(regression).toEqual([expect.stringContaining('LX0609-06-01-04')])
    expect(regression[0]).toContain('不一致')
    expect(wrapper.find('[data-testid="regression-gap"]').text()).toContain('LX0609-06-01-05')
    expect(wrapper.text()).toContain('同族回归对照')
    expect(wrapper.text()).toContain('同族回归缺口')
    expect(wrapper.find('textarea[aria-label="覆盖缺口说明"]').exists()).toBe(true)
  })

  it('没有同族保护病例时显示尚未验证，不标记无差异', async () => {
    const impact = {
      impact: 'shared_batch' as const, label: '共享抽取批次', executor_key: 'exam_lab',
      basis: '共享抽取', peer_rule_ids: ['LX0609-06-01-04'],
    }
    const gap = { rule_id: 'LX0609-06-01-04', name: '已上线同族', reason: '没有保护集' }
    vi.mocked(api.getValidationRule).mockResolvedValue({ success: true, data: detail({
      rule: { ...detail().rule, impact },
      runs: [{ ...run, impact, regression_cases: [], regression_gaps: [gap] }],
      regression_gaps: [gap], latest_run_rows: rows,
    }) })
    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('同族回归尚未验证')
    expect(wrapper.text()).not.toContain('同族回归无差异')
  })

  it('运行本规则后重新加载详情', async () => {
    vi.mocked(api.getValidationRule).mockResolvedValue({
      success: true,
      data: detail({ runs: [], latest_run_rows: null, stage: 'ready_to_run', events: [] }),
    })
    vi.mocked(api.startValidationRun).mockResolvedValue({
      success: true,
      data: { run_id: 'run-2', job_id: 'job-2' },
    })
    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()

    await wrapper.find('[data-testid="start-run"]').trigger('click')
    await flushPromises()
    expect(api.startValidationRun).toHaveBeenCalledWith('LX0609-06-01-01')
    expect(api.getValidationRule).toHaveBeenCalledTimes(2)
  })
})

describe('逐例核对抽屉', () => {
  it('状态不一致时不能确认通过，只能记录问题', async () => {
    vi.mocked(api.reviewCase).mockResolvedValue({ success: true, data: {} as never })
    const wrapper = mount(CaseReviewDrawer, {
      props: { runId: 'run-1', runTime: '09-29 14:20', rows, index: 1, reviews: [] },
      global: { stubs },
    })
    expect(wrapper.text()).toContain('真实副本 · 未记录')
    expect(wrapper.text()).toContain('日常病程')
    await wrapper.find('textarea[aria-label="核对意见"]').setValue('系统误判为合规')
    expect(wrapper.find('[data-testid="confirm-case"]').attributes('disabled')).toBeDefined()
    await button(wrapper, '记录问题').trigger('click')
    await flushPromises()

    expect(api.reviewCase).toHaveBeenCalledWith('run-1', 'b', 'problem', '系统误判为合规')
    expect(wrapper.emitted('reviewed')).toHaveLength(1)
  })
})

it('逐例核对保留公开事实中的全部事件值', () => {
  const row = {
    ...rows[0],
    result: {
      ...rows[0].result,
      customer_display_facts: {
        event_results: [
          { missing_items: ['手术指征'], interval_hours: 27 },
          { missing_items: ['麻醉方式'], interval_hours: 31 },
        ],
      },
    },
  }
  const wrapper = mount(CaseReviewDrawer, {
    props: { runId: 'run-public-facts', runTime: '09-30', rows: [row], index: 0, reviews: [] },
    global: { stubs },
  })
  expect(wrapper.text()).toContain('结构化判定事实')
  for (const value of ['手术指征', '麻醉方式', '27', '31']) expect(wrapper.text()).toContain(value)
})

describe('受限演示账号只读门禁与驳回后状态复位', () => {
  it('confirmedResultsOnly=true 时隐藏规则详情「核对证据」按钮与抽屉提交控件', async () => {
    visibilityState.confirmedResultsOnly = true
    vi.mocked(api.getValidationRule).mockResolvedValue({ success: true, data: detail() })
    const detailWrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()
    expect(detailWrapper.findAll('button').some((b) => b.text().includes('核对证据'))).toBe(false)
    detailWrapper.unmount()

    const drawerWrapper = mount(CaseReviewDrawer, {
      props: { runId: 'run-1', runTime: '09-29 14:20', rows, index: 0, reviews: [] },
      global: { stubs },
    })
    expect(drawerWrapper.text()).toContain('病程已记录检查目的')
    expect(drawerWrapper.find('textarea[aria-label="核对意见"]').exists()).toBe(false)
    expect(drawerWrapper.find('[data-testid="confirm-case"]').exists()).toBe(false)
    expect(drawerWrapper.findAll('button').some((b) => b.text().includes('记录问题'))).toBe(false)
    drawerWrapper.unmount()
  })

  it('ApprovalModal 驳回成功后重置意见并触发 done 与 close 关闭弹窗', async () => {
    vi.mocked(api.approveRule).mockResolvedValue({ success: true, data: {} as never })
    const wrapper = mount(ApprovalModal, {
      props: {
        open: true,
        detail: detail({ stage: 'pending_approval' }),
        approval: null,
      },
      global: {
        stubs: {
          ...stubs,
          AModal: { props: ['open'], template: '<div v-if="open"><slot /></div>' },
        },
      },
    })
    const noteInput = wrapper.get('textarea[aria-label="批准意见"]')
    await noteInput.setValue('覆盖场景不足，退回补充')
    await button(wrapper, '驳回').trigger('click')
    await flushPromises()

    expect(api.approveRule).toHaveBeenCalledWith(
      'LX0609-06-01-01',
      'rejected',
      '覆盖场景不足，退回补充',
    )
    expect(wrapper.emitted('done')).toHaveLength(1)
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect((noteInput.element as HTMLTextAreaElement).value).toBe('')
    wrapper.unmount()
  })
})
