import { computed, defineComponent } from 'vue'
import { WORKSTATION_REMINDER_PANEL } from '@/views/workstation/notificationNavigation'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// 用普通函数而非 vi.fn：避免测试框架给被拒绝的 Promise 再挂一条无人处理的分支。
const handler = vi.hoisted(() => ({ run: async (): Promise<unknown> => ({}) }))
vi.mock('@/api/businessAgent', () => ({ businessAgentApi: { access: () => handler.run() } }))

import WorkstationV4AssistView from '@/views/workstation-v4/components/WorkstationV4AssistView.vue'

// 面板外壳只负责渲染 chat 插槽，便于单独验证“对话”页签的上下文与跨页签请求。
const PanelStub = defineComponent({
  name: 'WorkstationAssistPanel',
  props: ['availableTabs'],
  template: '<div><slot name="chat" :active="true" /></div>',
})
const ChatStub = defineComponent({
  name: 'BusinessAgentDrawer',
  props: {
    open: Boolean,
    embedded: Boolean,
    userContext: Object,
    panels: Array,
    summary: Object,
    prefill: Object,
  },
  emits: ['open-panel', 'update:open'],
  template: '<div data-testid="chat-stub" />',
})

const RECORD = {
  id: 'V',
  instituteId: 'H',
  patientId: 'P',
  visitId: 'V',
  name: '合成患者',
  department: '外一科',
  dischargeDate: '2026-09-30',
}

function baseProps(extra: Record<string, unknown> = {}) {
  return {
    visible: true,
    assistTab: 'chat',
    chatEnabled: true,
    activeDocType: 'progress_note',
    documentsList: [],
    suggestions: [],
    icdTargetOptions: [],
    filteredAssistNotifications: [],
    filteredNotificationOverviewItems: [],
    overviewDepartments: [],
    overviewTypes: [],
    overviewSeverities: [],
    selectedRecord: RECORD as never,
    ...extra,
  } as never
}

async function mountView(extra: Record<string, unknown> = {}) {
  const wrapper = shallowMount(WorkstationV4AssistView, {
    props: baseProps(extra),
    global: { stubs: { WorkstationAssistPanel: PanelStub, BusinessAgentDrawer: ChatStub } },
  })
  await flushPromises()
  return wrapper
}

describe('智能助手面板的对话页签', () => {
  it('消息不要求先选病例，无病例时不开放质控或DRG页签', async () => {
    const messages = await mountView({
      selectedRecord: null,
      assistTab: 'message',
      chatEnabled: false,
    })
    expect(messages.findComponent(PanelStub).exists()).toBe(true)
    expect(messages.findComponent(PanelStub).props('availableTabs')).toEqual(['message'])
    messages.unmount()
    const qc = await mountView({ selectedRecord: null, assistTab: 'form', chatEnabled: false })
    expect(qc.findComponent(PanelStub).exists()).toBe(false)
    qc.unmount()
  })
  beforeEach(() => {
    handler.run = async () => ({ doctor_case_count: 1, doctor_cases: [] })
  })

  it('以内嵌方式沿用当前病例坐标、当前文书和画像入口声明', async () => {
    handler.run = async () => ({
      doctor_case_count: 1,
      doctor_cases: [{ institute_id: 'H', patient_id: 'P', visit_id: 'V' }],
      manager_scopes: [],
    })
    const chat = (await mountView()).findComponent(ChatStub)
    expect(chat.props('embedded')).toBe(true)
    expect(chat.props('open')).toBe(true)
    expect(chat.props('panels')).toEqual(['profile'])
    expect(chat.props('userContext')).toMatchObject({
      view: 'doctor',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
      patient_name: '合成患者',
      document_id: 'progress_note',
    })
  })

  it('授权返回前不初始化对话，避免先按医生身份请求再切换', async () => {
    let release: (value: unknown) => void = () => undefined
    handler.run = () => new Promise((resolve) => (release = resolve))
    const wrapper = shallowMount(WorkstationV4AssistView, {
      props: baseProps(),
      global: { stubs: { WorkstationAssistPanel: PanelStub, BusinessAgentDrawer: ChatStub } },
    })
    await flushPromises()
    expect(wrapper.findComponent(ChatStub).props('open')).toBe(false)
    release({ doctor_case_count: 0, manager_scopes: [] })
    await flushPromises()
    expect(wrapper.findComponent(ChatStub).props('open')).toBe(true)
  })

  it('纯管理账号（只有科室授权）进入病例时保留管理者身份和科室授权', async () => {
    handler.run = async () => ({
      doctor_case_count: 0,
      doctor_cases: [],
      manager_scopes: [{ institute_id: 'H', department: '外一科' }],
    })
    const context = (await mountView()).findComponent(ChatStub).props('userContext')
    expect(context).toEqual({
      view: 'manager',
      institute_id: 'H',
      department: '外一科',
      care_phase: 'discharged',
    })
  })

  it('没有出院日期的病例视为在院，管理者上下文按在院范围', async () => {
    handler.run = async () => ({
      doctor_case_count: 0,
      manager_scopes: [{ institute_id: 'H', department: '外一科' }],
    })
    const wrapper = await mountView({ selectedRecord: { ...RECORD, dischargeDate: '' } })
    expect(wrapper.findComponent(ChatStub).props('userContext')).toMatchObject({
      view: 'manager',
      care_phase: 'inpatient',
    })
  })

  it('同时有该病例的医生授权时仍按医生模式', async () => {
    handler.run = async () => ({
      doctor_case_count: 1,
      doctor_cases: [{ institute_id: 'H', patient_id: 'P', visit_id: 'V' }],
      manager_scopes: [{ institute_id: 'H', department: '外一科' }],
    })
    const context = (await mountView()).findComponent(ChatStub).props('userContext')
    expect(context).toMatchObject({ view: 'doctor', patient_id: 'P' })
  })

  it('管理授权的科室与病例科室不一致时不冒用管理身份，仍按医生模式由后端判定', async () => {
    handler.run = async () => ({
      doctor_case_count: 0,
      manager_scopes: [{ institute_id: 'H', department: '内科' }],
    })
    const context = (await mountView()).findComponent(ChatStub).props('userContext')
    expect(context).toMatchObject({ view: 'doctor' })
  })

  it('授权读取失败时按医生模式尝试，不阻塞对话', async () => {
    handler.run = async () => {
      throw new Error('403')
    }
    const chat = (await mountView()).findComponent(ChatStub)
    expect(chat.props('open')).toBe(true)
    expect(chat.props('userContext')).toMatchObject({ view: 'doctor' })
  })

  it('只响应与当前病例三坐标一致的画像请求，并仅切换页签', async () => {
    handler.run = async () => ({
      doctor_case_count: 1,
      doctor_cases: [{ institute_id: 'H', patient_id: 'P', visit_id: 'V' }],
    })
    const wrapper = await mountView()
    const chat = wrapper.findComponent(ChatStub)
    chat.vm.$emit('open-panel', {
      panel: 'profile',
      institute_id: 'H',
      patient_id: 'P2',
      visit_id: 'V',
    })
    expect(wrapper.emitted('tab-change')).toBeUndefined()
    chat.vm.$emit('open-panel', {
      panel: 'profile',
      institute_id: 'H',
      patient_id: 'P',
      visit_id: 'V',
    })
    expect(wrapper.emitted('tab-change')).toEqual([['profile']])
    expect(wrapper.emitted('open-ai-profile')).toBeUndefined()
  })

  it('待办摘要沿用面板计数，并把未读消息入口交给面板切页签', async () => {
    const wrapper = await mountView({
      contentQCCount: 2,
      assistBadgeCount: 29,
      notificationUnreadCount: 30,
    })
    const chat = wrapper.findComponent(ChatStub)
    expect(chat.props('summary')).toEqual({ pending: 31, unread: 30 })
    chat.vm.$emit('open-tab', 'message')
    expect(wrapper.emitted('tab-change')).toEqual([['message']])
  })

  it('预填对话输入并切到对话页签；相同文字再次预填也有新的标记', async () => {
    const wrapper = await mountView()
    const exposed = wrapper.vm as unknown as { prefillChat: (text: string) => void }
    exposed.prefillChat('问一下')
    exposed.prefillChat('问一下')
    expect(wrapper.emitted('tab-change')).toEqual([['chat'], ['chat']])
  })

  it('内涵质控的“问助手”只带规则标识预填对话，不带页面上的实时结论', async () => {
    const AllSlotsPanel = defineComponent({
      name: 'WorkstationAssistPanel',
      template: '<div><slot name="chat" :active="true" /><slot name="content" /></div>',
    })
    const ContentStub = defineComponent({
      name: 'ContentQCTab',
      emits: ['ask-assistant', 'issues-change'],
      template: '<div />',
    })
    const wrapper = shallowMount(WorkstationV4AssistView, {
      props: baseProps({ assistTab: 'content' }),
      global: {
        stubs: {
          WorkstationAssistPanel: AllSlotsPanel,
          BusinessAgentDrawer: ChatStub,
          ContentQCTab: ContentStub,
        },
      },
    })
    await flushPromises()
    wrapper
      .findComponent(ContentStub)
      .vm.$emit('ask-assistant', { ruleId: 'LX0609-01-01-01', ruleName: '首次病程记录' })
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('tab-change')).toEqual([['chat']])
    const prefill = wrapper.findComponent(ChatStub).props('prefill') as { text: string }
    expect(prefill.text).toContain('LX0609-01-01-01')
    expect(prefill.text).toContain('首次病程记录')
  })
})

// 2026-10-23 客户要求：医生病历页恢复为原“智能分析面板”弹窗，不带对话。
describe('医生病历页默认的分析面板', () => {
  it('管理员隐藏消息入口与角标，旧消息链接不唤起面板，其他分析页签保留', async () => {
    const wrapper = shallowMount(WorkstationV4AssistView, {
      props: baseProps({ assistTab: 'form', chatEnabled: false, notificationUnreadCount: 12 }),
      global: {
        provide: { [WORKSTATION_REMINDER_PANEL as symbol]: computed(() => false) },
        stubs: { WorkstationAssistPanel: PanelStub, BusinessAgentDrawer: ChatStub },
      },
    })
    const panel = wrapper.findComponent(PanelStub)
    expect(panel.props('availableTabs')).not.toContain('message')
    expect(panel.props('availableTabs')).toContain('form')
    expect(panel.attributes('message-count')).toBe('0')
    await wrapper.setProps({ assistTab: 'message' })
    expect(wrapper.findComponent(PanelStub).exists()).toBe(false)
    wrapper.unmount()
  })

  it('消息样式重排后仍逐条派发原处理对象和已读事件', async () => {
    const MessagePanel = defineComponent({
      name: 'WorkstationAssistPanel',
      template: '<div><slot name="message" /></div>',
    })
    const notification = {
      id: 'notification-id',
      title: '整改结果',
      content: '完整整改说明',
      is_read: false,
      created_at: '2026-10-25T12:00:00Z',
    }
    const wrapper = shallowMount(WorkstationV4AssistView, {
      props: baseProps({
        selectedRecord: null,
        assistTab: 'message',
        chatEnabled: false,
        overviewViewMode: 'detail',
        notificationUnreadCount: 1,
        filteredAssistNotifications: [notification],
        formatRelativeTime: () => '刚刚',
      }),
      global: { stubs: { WorkstationAssistPanel: MessagePanel } },
    })
    expect(wrapper.get('.assist-message-inbox__body').text()).toBe('完整整改说明')
    expect(wrapper.get('.assist-message-inbox__body').classes()).not.toContain('text-xs')
    const actions = wrapper.findAll('.assist-message-inbox__item a-button')
    await actions[0].trigger('click')
    await actions[1].trigger('click')
    expect(wrapper.emitted('assist-notification-click')).toEqual([[notification]])
    expect(wrapper.emitted('mark-assist-notification-read')).toEqual([[notification]])
    wrapper.unmount()
  })

  it('未开启对话时使用分析面板样式，去掉对话页签，不读取助手授权', async () => {
    let accessCalls = 0
    handler.run = async () => {
      accessCalls += 1
      return {}
    }
    const PropsPanel = defineComponent({
      name: 'WorkstationAssistPanel',
      props: { variant: String, availableTabs: Array, defaultTab: String },
      template: '<div><slot name="chat" :active="true" /></div>',
    })
    const wrapper = shallowMount(WorkstationV4AssistView, {
      props: baseProps({ chatEnabled: undefined, assistTab: 'form' }),
      global: { stubs: { WorkstationAssistPanel: PropsPanel, BusinessAgentDrawer: ChatStub } },
    })
    await flushPromises()
    const panel = wrapper.findComponent(PropsPanel)
    expect(panel.props('variant')).toBe('analysis')
    expect(panel.props('availableTabs')).not.toContain('chat')
    expect(panel.props('availableTabs')).toContain('content')
    expect(wrapper.findComponent(ChatStub).exists()).toBe(false)
    expect(accessCalls).toBe(0)
  })
})
