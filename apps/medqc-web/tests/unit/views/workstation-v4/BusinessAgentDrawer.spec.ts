import { defineComponent, ref, type PropType } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  BusinessAgentAccess,
  BusinessEvidenceDocument,
  BusinessAgentContext,
} from '@/api/businessAgent'

const mocks = vi.hoisted(() => ({
  duplicateSecond: false,
  access: vi.fn(),
  send: vi.fn(),
  activate: vi.fn(),
  reference: vi.fn(),
  evidenceDocument: vi.fn(),
}))
vi.mock('@/api/businessAgent', () => ({
  businessAgentApi: {
    access: mocks.access,
    reference: mocks.reference,
    evidenceDocument: mocks.evidenceDocument,
  },
}))
vi.mock('@/views/workstation-v4/composables/useBusinessAgent', () => ({
  useBusinessAgent: () => ({
    sessionId: ref('session-a'),
    turns: ref([
      {
        run_id: 'run-a',
        question: '查看问题',
        answer: '保存结论',
        references: [
          { id: 'result-a', position: 1, kind: 'saved_result', title: '保存问题' },
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
    ]),
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
        'a-drawer': { template: '<div><slot /></div>' },
        'a-modal': { template: '<div><slot /></div>' },
        'a-button': {
          props: { disabled: Boolean },
          template: '<button :disabled="disabled"><slot /></button>',
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
    mocks.activate.mockResolvedValue(undefined)
    mocks.send.mockResolvedValue(undefined)
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
      '本页 2 条，匹配共 4 条，保存结果共 75 条',
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
