import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '@/services/rule-validation-service'
import type { RuleDetail, ValidationCase } from '@/services/rule-validation-service'
import RuleValidationDetailView from '@/views/workstation-v4/rule-validation/RuleValidationDetailView.vue'

vi.mock('@/services/rule-validation-service', () => ({
  getValidationRule: vi.fn(),
  startValidationRun: vi.fn(),
  concludeRule: vi.fn(),
}))

const mockRoute = reactive({
  params: { ruleId: 'RULE-A' },
  query: {},
})

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
}))

vi.mock('ant-design-vue', () => ({
  message: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
}))

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
  CaseReviewDrawer: true,
  ApprovalModal: true,
  MqIconTile: true,
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

const sampleCase: ValidationCase = {
  item_id: 'case-1',
  case_title: '测试病例',
  record_ref: { institute_id: 'H-1', patient_id: 'P-1', visit_id: 'V-1' },
  source_kind: 'synthetic',
  evaluation_as_of_date: '2026-07-05',
  expected_status: 'compliant',
  human_reason: '依据',
  purpose: 'development',
  answer_revision: 1,
}

function buildDetail(ruleId: string, inProgress: boolean): RuleDetail {
  return {
    rule: {
      rule_id: ruleId,
      name: `规则-${ruleId}`,
      source_document: '测试文书',
      release_scope: 'acceptance_only',
      policy_summary: '口径',
      impact: null,
    },
    stage: 'reviewing',
    cases: [sampleCase],
    coverage: {
      counts: {
        compliant: { synthetic: 1, real_copy: 0 },
        non_compliant: { synthetic: 0, real_copy: 0 },
        not_applicable: { synthetic: 0, real_copy: 0 },
        data_gap: { synthetic: 0, real_copy: 0 },
      },
      gaps: [],
      acceptance_cases: 1,
    },
    runs: [
      {
        id: `run-${ruleId}`,
        rule_id: ruleId,
        cases: [sampleCase],
        job_id: `job-${ruleId}`,
        state: inProgress ? 'creating' : 'bound',
        execution_version: {},
        build_kind: 'development',
        created_by: 'tester',
        created_at: '2026-10-01T10:00:00',
        regression_cases: [],
        scope_rule_ids: [ruleId],
        regression_gaps: [],
        impact: null,
      },
    ],
    latest_run_rows: [
      {
        ...sampleCase,
        rule_id: ruleId,
        role: 'candidate',
        actual_status: inProgress ? null : 'compliant',
        comparison: inProgress ? 'pending' : 'same',
      },
    ],
    acceptance_blockers: [],
    regression_gaps: [],
    events: [],
  }
}

describe('RuleValidationDetailView 卸载与切页在途请求轮询竞态保护', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.resetAllMocks()
    mockRoute.params.ruleId = 'RULE-A'
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('组件卸载时首次 getValidationRule 仍在途：响应返回后绝不再排程轮询', async () => {
    const req = deferred<{ success: true; data: RuleDetail }>()
    vi.mocked(api.getValidationRule).mockReturnValueOnce(req.promise as any)

    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    expect(api.getValidationRule).toHaveBeenCalledTimes(1)

    // 请求尚未返回即卸载组件
    wrapper.unmount()

    // 在途请求返回“运行中”状态
    req.resolve({ success: true, data: buildDetail('RULE-A', true) })
    await flushPromises()

    // 推进多个轮询周期（30s），绝不能再触发 getValidationRule
    await vi.advanceTimersByTimeAsync(30_000)
    await flushPromises()
    expect(api.getValidationRule).toHaveBeenCalledTimes(1)
  })

  it('轮询请求正在进行时卸载组件：在途轮询返回后绝不再排程下一次轮询', async () => {
    const secondPoll = deferred<{ success: true; data: RuleDetail }>()
    vi.mocked(api.getValidationRule)
      .mockResolvedValueOnce({ success: true, data: buildDetail('RULE-A', true) })
      .mockReturnValueOnce(secondPoll.promise as any)

    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()
    expect(api.getValidationRule).toHaveBeenCalledTimes(1)

    // 推进 5s 触发下一次轮询，此时第 2 次请求在途
    await vi.advanceTimersByTimeAsync(5_000)
    expect(api.getValidationRule).toHaveBeenCalledTimes(2)

    // 在第 2 次轮询请求尚未返回时卸载组件
    wrapper.unmount()

    // 迟到的轮询返回仍为“运行中”
    secondPoll.resolve({ success: true, data: buildDetail('RULE-A', true) })
    await flushPromises()

    await vi.advanceTimersByTimeAsync(30_000)
    await flushPromises()
    expect(api.getValidationRule).toHaveBeenCalledTimes(2)
  })

  it('切页切换 ruleId 时旧规则请求仍在途：旧响应被丢弃且绝不覆盖新规则或重启旧轮询', async () => {
    const ruleAReq = deferred<{ success: true; data: RuleDetail }>()
    const ruleBReq = deferred<{ success: true; data: RuleDetail }>()
    vi.mocked(api.getValidationRule)
      .mockReturnValueOnce(ruleAReq.promise as any)
      .mockReturnValueOnce(ruleBReq.promise as any)

    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    expect(api.getValidationRule).toHaveBeenNthCalledWith(1, 'RULE-A')

    // RULE-A 请求在途时切页到 RULE-B
    mockRoute.params.ruleId = 'RULE-B'
    await flushPromises()
    expect(api.getValidationRule).toHaveBeenNthCalledWith(2, 'RULE-B')

    // 新规则 RULE-B 先完成（非运行中，不需轮询）
    ruleBReq.resolve({ success: true, data: buildDetail('RULE-B', false) })
    await flushPromises()
    expect(wrapper.text()).toContain('规则-RULE-B')

    // 旧规则 RULE-A 迟到返回“运行中”
    ruleAReq.resolve({ success: true, data: buildDetail('RULE-A', true) })
    await flushPromises()

    // 页面仍显示 RULE-B，且推进 30s 绝不触发轮询
    expect(wrapper.text()).toContain('规则-RULE-B')
    expect(wrapper.text()).not.toContain('规则-RULE-A')

    await vi.advanceTimersByTimeAsync(30_000)
    await flushPromises()
    expect(api.getValidationRule).toHaveBeenCalledTimes(2)

    wrapper.unmount()
  })

  it('startValidationRun 仍在途时卸载组件：响应返回后绝不触发二次加载或轮询', async () => {
    const startReq = deferred<{ success: true; data: { run_id: string; job_id: string } }>()
    vi.mocked(api.getValidationRule).mockResolvedValueOnce({
      success: true,
      data: buildDetail('RULE-A', false),
    })
    vi.mocked(api.startValidationRun).mockReturnValueOnce(startReq.promise as any)

    const wrapper = mount(RuleValidationDetailView, { global: { stubs } })
    await flushPromises()
    expect(api.getValidationRule).toHaveBeenCalledTimes(1)

    await wrapper.get('[data-testid="start-run"]').trigger('click')
    expect(api.startValidationRun).toHaveBeenCalledTimes(1)

    // 请求在途时卸载
    wrapper.unmount()

    startReq.resolve({ success: true, data: { run_id: 'run-2', job_id: 'job-2' } })
    await flushPromises()

    await vi.advanceTimersByTimeAsync(30_000)
    await flushPromises()
    expect(api.getValidationRule).toHaveBeenCalledTimes(1)
  })
})
