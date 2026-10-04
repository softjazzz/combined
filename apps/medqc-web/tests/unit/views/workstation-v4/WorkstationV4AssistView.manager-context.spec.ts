// 病例入口的真实父子组件链路：WorkstationV4AssistView（宿主）+ BusinessAgentDrawer（对话）
// + 真实会话组合式函数。只模拟 HTTP 接口层，因此能证明宿主传入的范围、边界被真实对话组件消费。
import { defineComponent, ref, type PropType } from 'vue'
import { flushPromises, mount, shallowMount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  BusinessAgentAccess,
  BusinessAgentContext,
  BusinessAgentReference,
  BusinessAgentSession,
  BusinessAgentTurn,
} from '@/api/businessAgent'

const api = vi.hoisted(() => ({
  access: vi.fn(),
  create: vi.fn(),
  restore: vi.fn(),
  chat: vi.fn(),
  stop: vi.fn(),
  confirmAction: vi.fn(),
  readAction: vi.fn(),
  reference: vi.fn(),
  evidenceDocument: vi.fn(),
  feedback: vi.fn(),
  submitFeedback: vi.fn(),
}))
vi.mock('@/api/businessAgent', () => ({ businessAgentApi: api }))

import BusinessAgentDrawer from '@/views/workstation-v4/components/BusinessAgentDrawer.vue'
import WorkstationV4AssistView from '@/views/workstation-v4/components/WorkstationV4AssistView.vue'

const Select = defineComponent({
  props: {
    value: String,
    options: Array as PropType<unknown[]>,
    disabled: Boolean,
  },
  emits: ['update:value'],
  template: '<div />',
})
const Range = defineComponent({
  props: { value: Array as PropType<string[]> },
  emits: ['update:value'],
  template: '<div />',
})
const panelChatVisible = ref(true)
const Panel = defineComponent({
  setup: () => ({ panelChatVisible }),
  template: '<div><slot name="chat" :active="panelChatVisible" /></div>',
})

const RECORD_A = {
  id: 'VA',
  visitId: 'VA',
  patientId: 'PA',
  instituteId: 'H',
  name: '合成甲',
  department: '科室甲',
  dischargeDate: '2026-09-30',
}
const RECORD_B_SAME_DEPT = { ...RECORD_A, id: 'VB', visitId: 'VB', patientId: 'PB', name: '合成乙' }
const RECORD_C_OTHER_DEPT = {
  ...RECORD_A,
  id: 'VC',
  visitId: 'VC',
  patientId: 'PC',
  department: '科室乙',
}
const BOTH_DEPARTMENTS: BusinessAgentAccess = {
  doctor_case_count: 0,
  doctor_cases: [],
  manager_scopes: [
    { institute_id: 'H', department: '科室甲' },
    { institute_id: 'H', department: '科室乙' },
  ],
}
const ONLY_DEPARTMENT_A: BusinessAgentAccess = {
  doctor_case_count: 0,
  doctor_cases: [],
  manager_scopes: [{ institute_id: 'H', department: '科室甲' }],
}

// 授权接口会被宿主和对话组件各调用一次；这里集中放行所有挂起的请求。
function deferAccess() {
  const pending: ((value: BusinessAgentAccess) => void)[] = []
  api.access.mockImplementation(
    () => new Promise<BusinessAgentAccess>((resolve) => pending.push(resolve)),
  )
  return (value: BusinessAgentAccess) => {
    pending.splice(0).forEach((resolve) => resolve(value))
    // 之后（例如对话组件在宿主之后发起）的调用直接返回同一授权。
    api.access.mockResolvedValue(value)
  }
}

const sessions = new Map<string, BusinessAgentSession>()
let sessionCounter = 0
let wrappers: VueWrapper[] = []

function turn(runId: string, answer: string, references: BusinessAgentReference[] = []) {
  return {
    run_id: runId,
    question: '问',
    answer,
    references,
    status: 'completed',
    tool_calls: 1,
    elapsed_ms: 1,
  } as BusinessAgentTurn
}

function hostProps(record: unknown) {
  return {
    visible: true,
    assistTab: 'chat',
    activeDocType: '',
    contentQCCount: 0,
    assistBadgeCount: 0,
    notificationUnreadCount: 0,
    frontpageGenerating: false,
    qcRefreshSeed: 0,
    selectedId: '',
    profileAnalyzed: false,
    profileAnalyzing: false,
    aiProfileModalVisible: false,
    combinedMedicalText: '',
    drgLoading: false,
    drgDetailModalVisible: false,
    overviewViewMode: 'overview',
    overviewDepartmentFilter: 'all',
    overviewTypeFilter: 'all',
    overviewSeverityFilter: 'all',
    notificationReadFilter: 'unread',
    notificationLoading: false,
    overviewLoading: false,
    suggestionDrawerVisible: false,
    suggestionsLoading: false,
    icdDrawerVisible: false,
    icdApplyTarget: 'mainDiagnosis',
    isOtherTarget: false,
    icdApplyIndex: 1,
    icdApplyLabel: '',
    formatRelativeTime: () => '',
    getSuggestionTitle: () => '',
    suggestionSeverityTag: () => '',
    documentsList: [],
    suggestions: [],
    icdTargetOptions: [],
    filteredAssistNotifications: [],
    filteredNotificationOverviewItems: [],
    overviewDepartments: [],
    overviewTypes: [],
    overviewSeverities: [],
    selectedRecord: record,
  } as never
}

const stubs = {
  WorkstationAssistPanel: Panel,
  BusinessAgentDrawer: false,
  BusinessAgentWelcome: false,
  BusinessAgentAnswer: false,
  BusinessAgentChart: false,
  'a-select': Select,
  'a-range-picker': Range,
  'a-button': { template: '<button><slot /></button>' },
  'a-modal': { template: '<div><slot /></div>' },
  'a-alert': { props: ['message'], template: '<div>{{ message }}</div>' },
  'a-textarea': true,
  'a-spin': true,
  'a-segmented': true,
  'a-tag': true,
  'a-empty': true,
  'a-drawer': true,
  'a-input-number': true,
}

function mountAssist(record: unknown = RECORD_A) {
  const wrapper = shallowMount(WorkstationV4AssistView, {
    props: hostProps(record),
    global: { stubs },
  })
  wrappers.push(wrapper as unknown as VueWrapper)
  return wrapper
}

async function setRecord(wrapper: ReturnType<typeof mountAssist>, record: unknown) {
  await wrapper.setProps({ selectedRecord: record } as never)
  await flushPromises()
}

async function setDates(wrapper: ReturnType<typeof mountAssist>) {
  wrapper.findComponent(Range).vm.$emit('update:value', ['2026-09-01', '2026-09-30'])
  await flushPromises()
}

async function ask(wrapper: ReturnType<typeof mountAssist>) {
  const prompt = wrapper
    .findAll('button')
    .find((button) =>
      ['当前范围哪些质控问题最多？', '列出这些问题对应的病例', '查询规则的当前启用状态'].includes(
        button.text(),
      ),
    )
  await prompt!.trigger('click')
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '发送')!
    .trigger('click')
  await flushPromises()
}

function lastCreateContext(): BusinessAgentContext {
  return api.create.mock.calls.at(-1)![0]
}

beforeEach(() => {
  panelChatVisible.value = true
  sessionStorage.clear()
  localStorage.clear()
  sessions.clear()
  sessionCounter = 0
  for (const mock of Object.values(api)) mock.mockReset()
  api.access.mockResolvedValue(BOTH_DEPARTMENTS)
  api.stop.mockResolvedValue(undefined)
  api.create.mockImplementation(async (context: BusinessAgentContext) => {
    const session = { session_id: `s${++sessionCounter}`, context, turns: [] }
    sessions.set(session.session_id, session)
    return session
  })
  api.restore.mockImplementation(async (sessionId: string) => sessions.get(sessionId))
  api.chat.mockImplementation(async (sessionId: string, runId: string) => {
    const answered = turn(runId, `回答来自 ${sessionId}`)
    sessions.get(sessionId)!.turns.push(answered)
    return answered
  })
})

afterEach(() => {
  for (const wrapper of wrappers.splice(0)) wrapper.unmount()
})

describe('病例入口：授权与范围传到真实对话组件', () => {
  it('纯管理账号按匹配科室进入，保持管理者身份并带出院范围', async () => {
    const wrapper = mountAssist()
    await flushPromises()
    await setDates(wrapper)
    await ask(wrapper)
    expect(lastCreateContext()).toMatchObject({
      view: 'manager',
      institute_id: 'H',
      department: '科室甲',
      care_phase: 'discharged',
    })
    expect(lastCreateContext()).not.toHaveProperty('patient_id')
  })

  it('没有出院日期的病例使用在院范围，不被对话组件的初始值覆盖，且范围不可在助手内改动', async () => {
    const wrapper = mountAssist({ ...RECORD_A, dischargeDate: '' })
    await flushPromises()
    await setDates(wrapper)
    await ask(wrapper)
    expect(lastCreateContext().care_phase).toBe('inpatient')
    const [department, phase] = wrapper.findAllComponents(Select)
    expect(department.props('disabled')).toBe(true)
    expect(phase.props('disabled')).toBe(true)
  })

  it('同时有该病例的医生授权时医生优先', async () => {
    api.access.mockResolvedValue({
      doctor_case_count: 1,
      doctor_cases: [{ institute_id: 'H', patient_id: 'PA', visit_id: 'VA' }],
      manager_scopes: [{ institute_id: 'H', department: '科室甲' }],
    })
    const wrapper = mountAssist()
    await flushPromises()
    expect(wrapper.findComponent(BusinessAgentDrawer).props('userContext')).toMatchObject({
      view: 'doctor',
      patient_id: 'PA',
    })
  })
})

describe('病例入口：切换科室与病例', () => {
  it('跨科室切换后实际使用新科室', async () => {
    const wrapper = mountAssist()
    await flushPromises()
    await setDates(wrapper)
    await ask(wrapper)
    expect(lastCreateContext().department).toBe('科室甲')
    await setRecord(wrapper, RECORD_C_OTHER_DEPT)
    expect(wrapper.text()).not.toContain('回答来自 s1')
    await ask(wrapper)
    expect(lastCreateContext().department).toBe('科室乙')
    expect(api.create).toHaveBeenCalledTimes(2)
  })

  it('新科室没有管理授权时不回退到其它授权科室：明确报错、不发起请求、旧会话不残留', async () => {
    api.access.mockResolvedValue(ONLY_DEPARTMENT_A)
    const wrapper = mountAssist()
    await flushPromises()
    await setDates(wrapper)
    await ask(wrapper)
    expect(api.create).toHaveBeenCalledTimes(1)
    await setRecord(wrapper, RECORD_C_OTHER_DEPT)
    // 宿主对无匹配管理授权的病例交回医生模式，由后端按授权判定；这里账号没有医生授权，直接报错。
    expect(wrapper.text()).toContain('没有此入口的明确授权范围')
    expect(wrapper.text()).not.toContain('回答来自 s1')
    const send = wrapper.findAll('button').find((button) => button.text() === '发送')
    expect(send?.attributes('disabled')).toBeDefined()
    expect(api.create).toHaveBeenCalledTimes(1)
    expect(api.chat).toHaveBeenCalledTimes(1)
  })

  it('对话组件自身防线：宿主指定的科室没有匹配授权时报错且不选取唯一的其它科室', async () => {
    api.access.mockResolvedValue(ONLY_DEPARTMENT_A)
    const wrapper = mount(BusinessAgentDrawer, {
      props: {
        open: true,
        embedded: true,
        userContext: {
          view: 'manager',
          institute_id: 'H',
          department: '科室乙',
          care_phase: 'discharged',
        },
        caseKey: 'case-c',
      },
      global: { stubs: { ...stubs, WorkstationAssistPanel: false } },
    })
    wrappers.push(wrapper as unknown as VueWrapper)
    await flushPromises()
    expect(wrapper.text()).toContain('没有管理授权')
    expect(wrapper.findAllComponents(Select)[0].props('value')).toBe('')
    expect(api.restore).not.toHaveBeenCalled()
    expect(api.create).not.toHaveBeenCalled()
  })

  it('同科室 A→B→A：各病例独立会话，切换时清空，回到 A 恢复 A 的会话', async () => {
    const wrapper = mountAssist()
    await flushPromises()
    await setDates(wrapper)
    await ask(wrapper)
    expect(wrapper.text()).toContain('回答来自 s1')

    await setRecord(wrapper, RECORD_B_SAME_DEPT)
    expect(wrapper.text()).not.toContain('回答来自 s1')
    await ask(wrapper)
    expect(wrapper.text()).toContain('回答来自 s2')
    expect(api.create).toHaveBeenCalledTimes(2)
    // 管理者上下文相同，但病例边界不同：必须是两个独立会话。
    expect(api.create.mock.calls[0][0]).toEqual(api.create.mock.calls[1][0])

    await setRecord(wrapper, RECORD_A)
    expect(api.restore).toHaveBeenLastCalledWith('s1')
    expect(wrapper.text()).toContain('回答来自 s1')
    expect(wrapper.text()).not.toContain('回答来自 s2')
    expect(api.create).toHaveBeenCalledTimes(2)
  })

  it('切换病例时停止旧轮次，旧病例迟到的回答不会出现在新病例', async () => {
    let finishLate: (value: BusinessAgentTurn) => void = () => undefined
    api.chat.mockImplementation(
      (sessionId: string, runId: string) =>
        new Promise<BusinessAgentTurn>((resolve) => {
          finishLate = (value) =>
            resolve({ ...value, run_id: runId, answer: `迟到回答 ${sessionId}` })
        }),
    )
    const wrapper = mountAssist()
    await flushPromises()
    await setDates(wrapper)
    await ask(wrapper)
    expect(api.chat).toHaveBeenCalledTimes(1)

    await setRecord(wrapper, RECORD_B_SAME_DEPT)
    expect(api.stop).toHaveBeenCalledWith('s1', expect.any(String))
    finishLate(turn('late', 'x'))
    await flushPromises()
    expect(wrapper.text()).not.toContain('迟到回答')
    expect(wrapper.text()).not.toContain('回答来自')
  })

  it('旧病例的待确认操作与引用不能在新病例入口继续使用', async () => {
    const action: BusinessAgentReference = {
      id: 'action:1',
      kind: 'action',
      action_id: '1',
      title: '单病例复检',
      status: 'previewed',
      allowed: true,
      confirmation_hash: 'a'.repeat(64),
      expires_at: new Date(Date.now() + 600000).toISOString(),
      text: '待确认',
    }
    api.chat.mockImplementation(async (sessionId: string, runId: string) => {
      const answered = turn(runId, `回答来自 ${sessionId}`, [action])
      sessions.get(sessionId)!.turns.push(answered)
      return answered
    })
    const wrapper = mountAssist()
    await flushPromises()
    await setDates(wrapper)
    await ask(wrapper)
    expect(wrapper.find('[data-testid="business-agent-action-confirm"]').exists()).toBe(true)

    await setRecord(wrapper, RECORD_B_SAME_DEPT)
    expect(wrapper.find('[data-testid="business-agent-action-confirm"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('单病例复检')
    expect(api.confirmAction).not.toHaveBeenCalled()
  })
})

describe('病例入口：授权返回前不激活会话', () => {
  async function seedStoredSession() {
    const first = mountAssist()
    await flushPromises()
    await setDates(first)
    await ask(first)
    first.unmount()
    wrappers = wrappers.filter((item) => item !== (first as unknown as VueWrapper))
    api.restore.mockClear()
    api.create.mockClear()
    api.chat.mockClear()
  }

  it('授权迟迟未返回时不恢复、不创建、不发送；返回后才恢复历史会话', async () => {
    await seedStoredSession()
    const release = deferAccess()
    const wrapper = mountAssist()
    await flushPromises()
    expect(api.restore).not.toHaveBeenCalled()
    expect(api.create).not.toHaveBeenCalled()
    expect(api.chat).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('回答来自')

    release(BOTH_DEPARTMENTS)
    await flushPromises()
    await setDates(wrapper)
    expect(api.restore).toHaveBeenCalledWith('s1')
    expect(wrapper.text()).toContain('回答来自 s1')
    expect(api.create).not.toHaveBeenCalled()
  })

  it('授权读取失败时明确展示原因，不恢复旧会话也不沿用旧身份', async () => {
    await seedStoredSession()
    api.access.mockImplementation(async () => {
      throw new Error('403')
    })
    const wrapper = mountAssist()
    await flushPromises()
    expect(wrapper.text()).toContain('访问范围读取失败')
    expect(api.restore).not.toHaveBeenCalled()
    expect(api.create).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('回答来自')
  })

  it('宿主授权在切换病例期间才返回时，只按最新病例激活', async () => {
    const release = deferAccess()
    const wrapper = mountAssist(RECORD_A)
    await flushPromises()
    await wrapper.setProps({ selectedRecord: RECORD_C_OTHER_DEPT } as never)
    release(BOTH_DEPARTMENTS)
    await flushPromises()
    await setDates(wrapper)
    await ask(wrapper)
    expect(api.create).toHaveBeenCalledTimes(1)
    expect(lastCreateContext().department).toBe('科室乙')
  })
})

describe('全局管理问数入口不回归', () => {
  function mountGlobal() {
    const wrapper = mount(BusinessAgentDrawer, {
      props: {
        open: true,
        embedded: true,
        allowCaseSelection: true,
        userContext: { view: 'manager' },
      },
      global: { stubs: { ...stubs, WorkstationAssistPanel: false } },
    })
    wrappers.push(wrapper as unknown as VueWrapper)
    return wrapper
  }

  it('多科室账号先由用户选择科室和范围，选择后按所选范围建立科室级会话', async () => {
    const wrapper = mountGlobal()
    await flushPromises()
    const [department, phase] = wrapper.findAllComponents(Select)
    expect(department.props('disabled')).toBe(false)
    expect(phase.props('disabled')).toBe(false)
    expect(department.props('value')).toBe('')
    expect(api.restore).not.toHaveBeenCalled()

    department.vm.$emit('update:value', JSON.stringify(['H', '科室乙']))
    phase.vm.$emit('update:value', 'inpatient')
    wrapper.findComponent(Range).vm.$emit('update:value', ['2026-09-01', '2026-09-30'])
    await flushPromises()
    await ask(wrapper as never)
    expect(lastCreateContext()).toMatchObject({
      view: 'manager',
      department: '科室乙',
      care_phase: 'inpatient',
    })
  })

  it('只有一个授权科室时自动选中，默认出院范围', async () => {
    api.access.mockResolvedValue(ONLY_DEPARTMENT_A)
    const wrapper = mountGlobal()
    await flushPromises()
    expect(wrapper.findAllComponents(Select)[0].props('value')).toBe(
      JSON.stringify(['H', '科室甲']),
    )
    wrapper.findComponent(Range).vm.$emit('update:value', ['2026-09-01', '2026-09-30'])
    await flushPromises()
    await ask(wrapper as never)
    expect(lastCreateContext()).toMatchObject({ department: '科室甲', care_phase: 'discharged' })
  })
})

it('隐藏对话后切换病例应立即停止旧轮次', async () => {
  api.chat.mockImplementation(() => new Promise(() => {}))
  const wrapper = mountAssist()
  await flushPromises()
  await setDates(wrapper)
  await ask(wrapper)
  expect(api.chat).toHaveBeenCalledTimes(1)
  panelChatVisible.value = false
  await flushPromises()
  await setRecord(wrapper, RECORD_B_SAME_DEPT)
  expect(api.stop).toHaveBeenCalledWith('s1', expect.any(String))
})

it('同病例隐藏再显示对话不应停止进行中的轮次', async () => {
  api.chat.mockImplementation(() => new Promise(() => {}))
  const wrapper = mountAssist()
  await flushPromises()
  await setDates(wrapper)
  await ask(wrapper)
  expect(api.chat).toHaveBeenCalledTimes(1)
  panelChatVisible.value = false
  await flushPromises()
  expect(api.stop).not.toHaveBeenCalled()
  panelChatVisible.value = true
  await flushPromises()
  expect(api.stop).not.toHaveBeenCalled()
})
